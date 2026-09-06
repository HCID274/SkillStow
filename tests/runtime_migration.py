"""用真实 Mac 导出包验证迁移、重复应用、漂移保护和凭据保留。"""
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile

source=Path(sys.argv[1]).resolve()
adapter=Path(__file__).resolve().parents[1]/'migration/apply_runtime.py'
with tempfile.TemporaryDirectory(prefix='skillstow-runtime-test-') as tmp:
    t=Path(tmp); target=t/'skills'; state=t/'state/runtime.json'
    shutil.copytree(source,t/'source');source=t/'source'
    credential=target/'.catalog/local/credentials.json'
    credential.parent.mkdir(parents=True); credential.write_text('local-placeholder-not-a-real-key')
    env=dict(os.environ,SKILL_RUNTIME_STATE_DIR=str(t/'runtime-state'),SKILL_RUNTIME_PROJECTIONS_DIR=str(t/'projections'),SKILL_RUNTIME_LINK_ROOT=str(target))
    args=[sys.executable,str(adapter),str(source),'--target',str(target),'--state',str(state)]
    def call(extra=(),code=0):
        r=subprocess.run(args+list(extra),env=env,capture_output=True,text=True)
        assert r.returncode==code,(r.returncode,r.stdout,r.stderr)
    call(['--adopt']); call()
    assert credential.read_text()=='local-placeholder-not-a-real-key'
    f=target/'engineering/SKILL.md'; text=f.read_text()+'\nExternal change\n';f.write_text(text)
    call(code=1); assert f.read_text()==text
    (source/'engineering/SKILL.md').write_text(text);call()
    extra=source/'engineering/references/new.md';extra.parent.mkdir(exist_ok=True);extra.write_text('new resource')
    call();assert (target/'engineering/references/new.md').read_text()=='new resource'
    print('runtime migration: initial apply, idempotence, credential preservation, drift rejection/recovery, new resource application PASS')
