#!/usr/bin/env python3
"""导出个人规范源与其共享 runtime；不导出插件、投影、状态或凭据。"""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import tarfile

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, default=Path.home()/'.codex/skills')
parser.add_argument('--output', type=Path, required=True)
a = parser.parse_args()
spec = importlib.util.spec_from_file_location('skillctl', a.root/'.runtime/skillctl.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
manifest = module.load_manifest()
parents = {Path('.runtime')}
for section in ('nodes','leaves','aliases'):
    for item in manifest.get(section,{}).values():
        source = item.get('source') or item.get('module')
        if source:
            p = Path(source)
            if p.is_absolute() or '..' in p.parts: raise ValueError(f'包外规范源：{p}')
            parents.add(p.parent)
files = {}
excluded = []
for parent in sorted(parents):
    for path in (a.root/parent).rglob('*'):
        rel = path.relative_to(a.root)
        if any(x in {'__pycache__','.git','.DS_Store','.projections','node_modules','.state','.cache'} for x in rel.parts): continue
        if path.is_dir(): continue
        name = path.name.lower()
        if name == 'credentials.json' or name.startswith('.env') or name in {'token','tokens.json','auth.json','secrets.json'} or name.endswith(('.key','.pem','.sqlite','.db')):
            excluded.append(str(rel)); continue
        if not path.is_file(): raise ValueError(f'特殊或失效文件：{rel}')
        files[str(rel)] = path.read_bytes()
# 屏蔽本机源文件导入产生的 pycache；不在导出包里保留生成物。
files['.gitignore'] = b'__pycache__/\n*.pyc\n'
files['SKILL.md'] = b'---\nname: personal-skill-system\ndescription: Personal Skills and their required shared runtime.\n---\n\nMaintain the canonical sources in this package through SkillStow.\n'
files['migration-inventory.json'] = json.dumps({'files':sorted(files), 'excluded_credentials':sorted(set(excluded)), 'external_requirements':['Python 3 (Unix runtime)','Existing tool installations and locally configured credentials'], 'leaves':sorted(manifest.get('leaves',{}))},ensure_ascii=False,indent=2).encode()
a.output.parent.mkdir(parents=True,exist_ok=True)
with tarfile.open(a.output,'w:gz',dereference=True) as tar:
    for name,data in sorted(files.items()):
        info = tarfile.TarInfo(name); info.size=len(data)
        original=a.root/name
        info.mode=(original.stat().st_mode & 0o777) if original.is_file() else 0o644
        tar.addfile(info,io.BytesIO(data))
print(json.dumps({'output':str(a.output),'files':len(files),'leaves':len(manifest.get('leaves',{})), 'excluded_credentials':len(set(excluded))}))
