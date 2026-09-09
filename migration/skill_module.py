#!/usr/bin/env python3
"""单一 Skills 模块：清单定位、按设备应用、精确影响分析和四端收据查询。"""
import argparse
import base64
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def git(repo, *args, optional=False):
    p = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=30)
    if p.returncode and not optional:
        raise RuntimeError(p.stderr.decode('utf-8', errors='replace'))
    return p.stdout.decode('utf-8') if p.returncode == 0 else None


def relative(value):
    p = Path(value)
    if p.is_absolute() or not p.parts or any(x in {'.', '..'} for x in p.parts) or '\\' in value or ':' in value:
        raise ValueError(f'非法包内路径：{value}')
    return p


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def load(root):
    m = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if set(m) != {'version', 'devices', 'skills'} or m['version'] != 1:
        raise ValueError('不支持的模块清单')
    for name, d in m['devices'].items():
        if not re.fullmatch(r'[a-z0-9-]+', name) or d['platform'] not in {'macos', 'linux', 'windows'}:
            raise ValueError(f'非法设备：{name}')
        if not re.fullmatch(r'[a-zA-Z0-9_]+@[0-9.]+', d['ssh']):
            raise ValueError(f'非法 SSH 目标：{name}')
    for name, entry in m['skills'].items():
        if not re.fullmatch(r'[a-z0-9-]+', name) or set(entry) != {'source', 'devices'}:
            raise ValueError(f'非法 Skill：{name}')
        if not entry['devices'] or set(entry['devices']) - m['devices'].keys():
            raise ValueError(f'未知或空设备范围：{name}')
        source = root / relative(entry['source'])
        if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
            raise ValueError(f'源路径不能外逸或使用链接：{name}')
        if not (source / 'SKILL.md').is_file():
            raise ValueError(f'缺少入口：{name}')
        if f'name: {name}\n' not in (source / 'SKILL.md').read_text(encoding='utf-8'):
            raise ValueError(f'入口名称与清单不同：{name}')
        for p in source.rglob('*'):
            if p.is_symlink() or getattr(p, 'is_junction', lambda: False)():
                raise ValueError(f'源不能含链接：{p}')
            if p.is_file() and (p.name.startswith('.env') or p.name in {'credentials.json', 'auth.json'}):
                raise ValueError(f'凭据不能进入模块：{p}')
    global_entry = m['skills'].get('decision-grade-reporting', {})
    if set(global_entry.get('devices', [])) != set(m['devices']):
        raise ValueError('每台设备必须启用统一协作规则')
    return m


def files_for(root, m, device):
    if device not in m['devices']:
        raise ValueError(f'设备未登记：{device}')
    files = {}
    for name, e in m['skills'].items():
        if device not in e['devices']:
            continue
        source = root / e['source']
        for p in source.rglob('*'):
            if p.is_file():
                files[(Path(name) / p.relative_to(source)).as_posix()] = p
    return files


def linked(p):
    return p.is_symlink() or getattr(p, 'is_junction', lambda: False)()


def unlink(p):
    if getattr(p, 'is_junction', lambda: False)():
        p.rmdir()
    else:
        p.unlink()


def directory_link(target, dest):
    if os.name == 'nt':
        p = subprocess.run(['cmd', '/D', '/C', 'mklink', '/J', str(dest), str(target)], capture_output=True)
        if p.returncode:
            raise RuntimeError(p.stderr.decode(errors='replace'))
    else:
        dest.symlink_to(target, target_is_directory=True)


class Journal:
    """只记录本次实际改动的文件和目录链接；失败时恢复，绝不递归删除链接目标。"""
    def __init__(self, backup):
        self.backup, self.entries = backup, []

    def save(self, p):
        if any(item[0] == p for item in self.entries):
            return
        self.backup.mkdir(parents=True, exist_ok=True)
        slot = self.backup / str(len(self.entries))
        if linked(p):
            old = ('link', os.readlink(p), getattr(p, 'is_junction', lambda: False)() or p.is_dir())
        elif p.is_file():
            shutil.copy2(p, slot)
            old = ('file', str(slot))
        elif p.exists():
            raise RuntimeError(f'拒绝替换真实目录：{p}')
        else:
            old = ('missing',)
        self.entries.append((p, old))
        (self.backup / 'journal.json').write_text(json.dumps([(str(a), b) for a, b in self.entries]), encoding='utf-8')

    def write(self, p, data, mode=0o644):
        if p.is_file() and not linked(p) and p.read_bytes() == data and (os.name == "nt" or p.stat().st_mode & 0o777 == mode):
            return
        self.save(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=p.parent)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
            os.chmod(temp, mode)
            os.replace(temp, p)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def remove(self, p):
        if linked(p) or p.exists():
            self.save(p)
            unlink(p)

    def link(self, p, target):
        if linked(p):
            try:
                if p.resolve() == target.resolve():
                    return
            except OSError:
                # 老 Windows junction 可能带有不可遍历标记；保留目标并只重建链接自身。
                pass
        self.save(p)
        if linked(p) or p.exists():
            unlink(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        directory_link(target, p)

    def rollback(self):
        for p, old in reversed(self.entries):
            if linked(p) or p.exists():
                if not linked(p) and p.is_dir():
                    for child in sorted(p.rglob('*'), key=lambda x: len(x.parts), reverse=True):
                        if child.is_dir() and not linked(child): child.rmdir()
                    p.rmdir()
                else:
                    unlink(p)
            if old[0] == 'file':
                shutil.copy2(old[1], p)
            elif old[0] == 'link':
                if old[2]:
                    directory_link(Path(old[1]), p)
                else:
                    p.symlink_to(old[1])


def without_telemetry(value):
    if isinstance(value, list):
        return [without_telemetry(x) for x in value if not (
            isinstance(x, dict) and 'command' in x and any(s in json.dumps(x) for s in ('skill-use-telemetry.py', 'hook_skill_use.py')))]
    if isinstance(value, dict):
        return {k: without_telemetry(v) for k, v in value.items()}
    return value


def apply(root, m, device, home, adopt):
    active = home / '.codex/skills'
    state = home / '.local/state/skillstow/module.json'
    old = json.loads(state.read_text(encoding='utf-8')) if state.exists() else None
    files = files_for(root, m, device)
    hashes = {rel: digest(p) for rel, p in files.items()}
    legacy = home / '.local/state/skillstow/runtime.json'
    if old:
        owned = old['files']
    elif legacy.exists():
        owned = json.loads(legacy.read_text(encoding='utf-8'))['files']
    elif adopt:
        owned = {}
    else:
        raise ValueError('首次接入需 --adopt；先核查原内容及备份范围')
    selected_names = {Path(rel).parts[0] for rel in files}
    if not old and adopt and active.exists():
        # 首次精简也纳入旧 runtime 清单外的个人 Skill；插件和本机秘密不接管。
        for d in active.iterdir():
            if d.name.startswith('.') or (linked(d) and d.name not in selected_names) or not (d / 'SKILL.md').is_file():
                continue
            for item in d.rglob('*'):
                if item.is_file() and not linked(item) and item.name not in {'credentials.json', 'auth.json', 'secrets.json', 'tokens.json'} and not item.name.startswith('.env') and item.suffix not in {'.key', '.pem', '.db', '.sqlite'}:
                    owned.setdefault(item.relative_to(active).as_posix(), digest(item))
    drift = [rel for rel, h in owned.items() if digest(active / relative(rel)) not in {h, hashes.get(rel)}]
    drift += [rel for rel, h in hashes.items() if rel not in owned and (active / rel).exists() and digest(active / rel) != h]
    if drift:
        raise ValueError('活动目录存在外部修改：' + ', '.join(drift))
    journal = Journal(state.parent / 'backups' / f'module-{time.time_ns()}')
    try:
        if not old and adopt:
            for name in selected_names:
                p = active / name
                if linked(p):
                    journal.remove(p)
                    p.mkdir()
        for rel, source in files.items():
            journal.write(active / rel, source.read_bytes(), source.stat().st_mode & 0o777)
        for rel in owned.keys() - files.keys():
            journal.remove(active / relative(rel))
        # 旧 runtime 生成的入口只移除链接；数据库、凭据和插件目录保留在原地。
        if not old and active.exists():
            for p in active.iterdir():
                if linked(p) and p.name not in {Path(rel).parts[0] for rel in files} and ('.projections' in str(p.resolve()) or (adopt and (p / 'SKILL.md').is_file())):
                    journal.remove(p)
        for client in ('.agents', '.claude'):
            journal.link(home / client / 'skills', active)
        global_source = active / 'decision-grade-reporting/references/global-collaboration.md'
        journal.write(home / '.codex/AGENTS.md', global_source.read_bytes())
        journal.write(home / '.claude/CLAUDE.md', b'@../.codex/skills/decision-grade-reporting/references/global-collaboration.md\n')
        for rel in ('.codex/hooks.json', '.claude/settings.json'):
            p = home / rel
            if p.exists():
                original = json.loads(p.read_text(encoding='utf-8'))
                cleaned = without_telemetry(original)
                if cleaned != original:
                    journal.write(p, (json.dumps(cleaned, ensure_ascii=False, indent=2) + '\n').encode())
        if any(digest(active / rel) != h for rel, h in hashes.items()):
            raise RuntimeError('落盘校验失败')
        commit = (git(root.parent, 'rev-parse', 'HEAD', optional=True) or '').strip()
        if old and not journal.entries and old.get('commit') == commit and old['files'] == hashes:
            emit({'device': device, 'skills': old['skills'], 'files': len(files), 'changed_paths': 0})
            return
        record = {'device': device, 'commit': commit,
                  'files': hashes, 'skills': sorted({Path(rel).parts[0] for rel in files}),
                  'applied_at': int(time.time()), 'backup': str(journal.backup)}
        journal.write(state, (json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode())
    except BaseException:
        journal.rollback()
        raise
    emit({'device': device, 'skills': record['skills'], 'files': len(files), 'changed_paths': len(journal.entries), 'backup': str(journal.backup)})


def impact(repo, root, m):
    old_text = git(repo, 'show', 'origin/main:system/manifest.json', optional=True)
    old = json.loads(old_text) if old_text else {'skills': {}}
    changed = set((git(repo, 'diff', '--name-only', '-z', 'origin/main', '--') or '').split('\0'))
    changed |= set((git(repo, 'ls-files', '--others', '--exclude-standard', '-z') or '').split('\0'))
    deleted = set((git(repo, 'diff', '--name-only', '-z', '--diff-filter=D', 'origin/main', '--') or '').split('\0'))
    result, removal = [], old_text is None
    for name in sorted(old['skills'].keys() | m['skills'].keys()):
        before, after = old['skills'].get(name), m['skills'].get(name)
        sources = [f"system/{e['source']}/" for e in (before, after) if e]
        touched = any(f.startswith(s) for f in changed if f for s in sources)
        if before == after and not touched:
            continue
        devices = sorted(set((before or {}).get('devices', [])) | set((after or {}).get('devices', [])))
        destructive = bool(before and (not after or set(before['devices']) - set(after['devices']) or before['source'] != after['source']))
        destructive |= any(f.startswith(s) for f in deleted if f for s in sources)
        removal |= destructive
        result.append({'skill': name, 'devices': devices, 'removal_or_replacement': destructive})
    emit({'impact': result, 'removal_or_replacement': removal})
    return 3 if removal else 0


def read_receipt(home):
    receipt = home / '.config/skillstow/receipt.toml'
    module = home / '.local/state/skillstow/module.json'
    r = tomllib.loads(receipt.read_text(encoding='utf-8'))
    if module.exists():
        d = json.loads(module.read_text(encoding='utf-8'))
        r.update({'skills': d['skills'], 'module_commit': d['commit']})
    return r


def fleet(root, m, home):
    cache = home / '.local/state/skillstow/fleet.json'
    previous = json.loads(cache.read_text(encoding='utf-8')) if cache.exists() else {}
    own = home / '.config/skillstow/config.toml'
    local = tomllib.loads(own.read_text(encoding='utf-8')).get('device') if own.exists() else None
    def query(item):
        name, d = item
        try:
            if name == local:
                r = read_receipt(home)
            else:
                if d['platform'] == 'windows':
                    command = "$ProgressPreference='SilentlyContinue'; [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); Get-Content -Raw -Encoding UTF8 ($env:USERPROFILE+'\\.config\\skillstow\\receipt.toml')"
                    command = 'powershell.exe -NoProfile -NonInteractive -EncodedCommand ' + base64.b64encode(command.encode('utf-16le')).decode()
                else:
                    command = 'cat ~/.config/skillstow/receipt.toml'
                p = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=7', '-o', 'StrictHostKeyChecking=yes', d['ssh'], command], capture_output=True, timeout=12)
                if p.returncode:
                    raise RuntimeError(p.stderr.decode(errors='replace')[-400:])
                r = tomllib.loads(p.stdout.decode('utf-8-sig'))
            return name, {'observed_at': int(time.time()), 'reachable': True, 'receipt': r}
        except Exception as e:
            last = previous.get(name)
            if last and not last.get('reachable'):
                last = last.get('last_confirmed')
            return name, {'reachable': False, 'error': str(e), 'last_confirmed': last}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        result = dict(pool.map(query, m['devices'].items()))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    emit(result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path.cwd())
    commands = p.add_subparsers(dest='command', required=True)
    commands.add_parser('validate')
    commands.add_parser('impact')
    commands.add_parser('fleet')
    locate = commands.add_parser('locate'); locate.add_argument('skill')
    action = commands.add_parser('apply'); action.add_argument('--device', required=True)
    action.add_argument('--home', type=Path, default=Path.home()); action.add_argument('--adopt', action='store_true')
    a = p.parse_args(); root = a.repo.resolve() / 'system'
    m = load(root)
    if a.command == 'validate':
        registry = tomllib.loads((a.repo / 'skillstow.toml').read_text(encoding='utf-8'))
        if set(registry['devices']) != set(m['devices']) or any(registry['devices'][d]['platform'] != v['platform'] for d, v in m['devices'].items()):
            raise ValueError('模块设备与 SkillStow 设备不一致')
        emit({'valid': True, 'skills': len(m['skills']), 'devices': list(m['devices'])})
    elif a.command == 'locate':
        e = m['skills'][a.skill]
        emit({'skill': a.skill, 'source': str(root / e['source']), 'devices': e['devices'], 'manifest': str(root / 'manifest.json')})
    elif a.command == 'impact':
        return impact(a.repo, root, m)
    elif a.command == 'fleet':
        fleet(root, m, Path.home())
    else:
        apply(root, m, a.device, a.home, a.adopt)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
