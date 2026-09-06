#!/usr/bin/env python3
"""把已发布的旧式 runtime 包应用到原位置，保留凭据、插件与设备状态。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

p = argparse.ArgumentParser()
p.add_argument('source', type=Path)
p.add_argument('--target', type=Path, default=Path.home()/'.codex/skills')
p.add_argument('--state', type=Path, default=Path.home()/'.local/state/skillstow/runtime.json')
p.add_argument('--adopt', action='store_true')
a = p.parse_args()
a.source = a.source.resolve()
inventory = json.loads((a.source/'migration-inventory.json').read_text())
files = sorted(str(p.relative_to(a.source)) for p in a.source.rglob('*')
               if p.is_file() and not any(x in {'__pycache__', '.git'} for x in p.relative_to(a.source).parts)
               and str(p.relative_to(a.source)) not in {'.gitignore', 'SKILL.md', 'migration-inventory.json'})
for rel in files:
    assert not Path(rel).is_absolute() and '..' not in Path(rel).parts
    assert (a.source/rel).is_file(), f'缺少资源：{rel}'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None

old = json.loads(a.state.read_text()) if a.state.exists() else None
if old is None and not a.adopt:
    raise SystemExit('首次接管需要明确 --adopt；先核对源包、目标和备份范围。')
new = {rel:digest(a.source/rel) for rel in files}
if old:
    drift = [rel for rel,h in old['files'].items() if digest(a.target/rel) not in {h, new.get(rel)}]
    drift += [rel for rel,h in new.items() if rel not in old['files'] and (a.target/rel).exists() and digest(a.target/rel) != h]
    if drift: raise SystemExit('活动目录有外部修改，先合并到维护仓：'+', '.join(drift))
changed = [rel for rel,h in new.items() if digest(a.target/rel) != h]
removed = [rel for rel in (old or {}).get('files',{}) if rel not in new]
# 先验证完整包；只调用实际 runtime 自带的只读校验入口。
if changed or removed or (old or {}).get('files') != new:
    subprocess.run(['python3','-B',str(a.source/'.runtime/skillctl.py'),'validate'],check=True)
backup = a.state.parent/('backups/'+str(time.time_ns()))
existing = set()
if changed or removed or (old or {}).get('files') != new:
    for rel in changed+removed:
        dest = a.target/rel
        if dest.exists() or dest.is_symlink():
            saved = backup/rel; saved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(dest,saved,follow_symlinks=False); existing.add(rel)
    try:
        # 清单最后写入；故障时用这次备份恢复所有受影响文件。
        for rel in sorted(changed,key=lambda r:r.endswith('manifest.json') or r.endswith('manifest.local.json')):
            dest=a.target/rel; dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.is_symlink(): dest.unlink()
            shutil.copy2(a.source/rel,dest)
        for rel in removed: (a.target/rel).unlink()
        subprocess.run(['python3','-B',str(a.target/'.runtime/skillctl.py'),'validate'],check=True)
        subprocess.run(['python3','-B',str(a.target/'.runtime/skillctl.py'),'refresh'],check=True)
    except BaseException:
        for rel in changed+removed:
            dest=a.target/rel
            if dest.exists() or dest.is_symlink(): dest.unlink()
            if rel in existing: shutil.copy2(backup/rel,dest,follow_symlinks=False)
        subprocess.run(['python3','-B',str(a.target/'.runtime/skillctl.py'),'refresh'],check=False)
        raise
    print(f'runtime: changed={len(changed)} removed={len(removed)} backup={backup}')
a.state.parent.mkdir(parents=True,exist_ok=True)
a.state.write_text(json.dumps({'source':str(a.source),'files':new},indent=2))
print(f'runtime applied: {len(files)} files')
