#!/usr/bin/env python3
"""Mac 主动推送 Git bundle；接收端只做本地校验和应用，不访问网络。"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import tomllib


def run(*argv, **kwargs):
    return subprocess.run(argv, check=True, capture_output=True, **kwargs).stdout


def receive(commit):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('非法提交号')
    home = Path.home()
    config = home / '.config/skillstow'
    settings = tomllib.loads((config / 'config.toml').read_text())
    repo = Path(settings['repo'])
    state = home / '.local/state/skillstow'
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'receive.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if run('git', '-C', str(repo), 'status', '--porcelain').strip():
            raise ValueError('接收仓有本地修改，停止覆盖')
        with tempfile.NamedTemporaryFile(dir=state, suffix='.bundle') as bundle:
            while chunk := sys.stdin.buffer.read(1024 * 1024):
                bundle.write(chunk)
            bundle.flush()
            run('git', '-C', str(repo), 'bundle', 'verify', bundle.name)
            run('git', '-C', str(repo), 'fetch', bundle.name, 'HEAD')
        incoming = run('git', '-C', str(repo), 'rev-parse', 'FETCH_HEAD').decode().strip()
        if incoming != commit:
            raise ValueError('传输提交与预期不符')
        run('git', '-C', str(repo), 'merge', '--ff-only', commit)
        adapter = str(home / '.local/share/skillstow/skill_module.py')
        run(sys.executable, adapter, '--repo', str(repo), 'validate')
        run(sys.executable, adapter, '--repo', str(repo), 'apply', '--device', settings['device'])
        # 收据只有在应用成功后才更新；失败留待下次 Mac 推送重试。
        receipt = f'device = "{settings["device"]}"\ncommit = "{commit}"\napplied = true\nchecked_at = {int(time.time())}\n'
        temporary = config / 'receipt.toml.tmp'
        temporary.write_text(receipt)
        os.replace(temporary, config / 'receipt.toml')
        print(json.dumps({'commit': commit, 'applied': True, 'transport': 'mac-push'}))


def push(config):
    home = Path.home()
    settings = tomllib.loads(config.read_text())
    repo = Path(settings['repo'])
    local_receipt = tomllib.loads((config.parent / 'receipt.toml').read_text())
    commit = run('git', '-C', str(repo), 'rev-parse', 'HEAD').decode().strip()
    if not local_receipt.get('applied') or local_receipt['commit'] != commit:
        raise ValueError('Mac 尚未成功应用该提交，等待本机同步')
    if (config.parent / 'editing').exists() or run('git', '-C', str(repo), 'status', '--porcelain').strip():
        raise ValueError('维护仓正在编辑，等待已发布版本')
    manifest = json.loads((repo / 'system/manifest.json').read_text())
    for device, target in manifest['devices'].items():
        if target.get('sync_from') != settings['device']:
            continue
        state = home / '.local/state/skillstow' / ('push-' + device)
        state.mkdir(parents=True, exist_ok=True)
        with (state / 'lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            receipt_file = state / 'receipt.json'
            if receipt_file.exists() and json.loads(receipt_file.read_text()).get('commit') == commit:
                continue
            with tempfile.NamedTemporaryFile(dir=state, suffix='.bundle') as bundle:
                os.unlink(bundle.name)
                run('git', '-C', str(repo), 'bundle', 'create', bundle.name, 'HEAD')
                with open(bundle.name, 'rb') as source:
                    result = run('ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                                 '-o', 'StrictHostKeyChecking=yes', target['ssh'],
                                 '/usr/bin/python3.12 ~/.local/share/skillstow/push_device.py receive ' + commit,
                                 stdin=source, timeout=120)
            receipt = json.loads(result)
            if receipt.get('commit') != commit or receipt.get('applied') is not True:
                raise ValueError('目标收据不匹配')
            receipt_file.write_text(json.dumps(receipt) + '\n')
            print(json.dumps({'device': device, **receipt}))


def passive(argv):
    parser = argparse.ArgumentParser(description='本设备只接受 Mac 推送；不提供联网同步或发布。')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('command', choices=['status', 'locate'])
    parser.add_argument('skill', nargs='?')
    args = parser.parse_args(argv)
    settings = tomllib.loads(args.config.read_text())
    if args.command == 'status':
        print((args.config.parent / 'receipt.toml').read_text())
        print('transport=mac-push；编辑与同步请在 Mac 发起。')
    else:
        if not args.skill:
            parser.error('locate 需要 Skill 名称')
        print(run(sys.executable, str(Path.home()/'.local/share/skillstow/skill_module.py'),
                  '--repo', settings['repo'], 'locate', args.skill).decode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['push', 'receive'])
    parser.add_argument('value')
    args = parser.parse_args()
    if args.action == 'push':
        push(Path(args.value))
    else:
        receive(args.value)


if __name__ == '__main__':
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "passive":
            passive(sys.argv[2:])
        else:
            main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr.decode(errors='replace')[-1200:], file=sys.stderr)
        sys.exit(1)
