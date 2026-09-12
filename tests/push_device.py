"""本地 bundle 接收集成测试：不允许网络，验证成功、幂等、身份和漂移拒绝。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ReceiveTest(unittest.TestCase):
    def test_receive_identity_drift_and_idempotence(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); source = base/'source'; home = base/'home'
            def git(repo, *args):
                return subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True).stdout.decode().strip()
            source.mkdir(); git(source,'init','-b','main');git(source,'config','user.name','Test');git(source,'config','user.email','test@example.invalid')
            skill=source/'system/shared/decision-grade-reporting';(skill/'references').mkdir(parents=True)
            (skill/'SKILL.md').write_text('---\nname: decision-grade-reporting\n---\n')
            (skill/'references/global-collaboration.md').write_text('Rules\n')
            (source/'system/manifest.json').write_text(json.dumps({'version':1,'devices':{'receiver':{'platform':'linux','ssh':'user@example.org'}},'skills':{'decision-grade-reporting':{'source':'shared/decision-grade-reporting','devices':['receiver']}}}))
            (source/'skillstow.toml').write_text('[devices.receiver]\nplatform="linux"\n')
            git(source,'add','.');git(source,'commit','-m','初始')
            repo=home/'.local/share/skillstow/workspace';repo.parent.mkdir(parents=True)
            subprocess.run(['git','clone',str(source),str(repo)],check=True,capture_output=True)
            shutil.copy2(ROOT/'migration/skill_module.py',repo.parent/'skill_module.py')
            config=home/'.config/skillstow';config.mkdir(parents=True)
            (config/'config.toml').write_text(f'repo="{repo}"\ndevice="receiver"\n')
            env={**os.environ,'HOME':str(home),'GIT_CONFIG_NOSYSTEM':'1'}
            subprocess.run(['python3',str(repo.parent/'skill_module.py'),'--repo',str(repo),'apply','--device','receiver','--adopt'],check=True,capture_output=True,env=env)
            (skill/'references/global-collaboration.md').write_text('Updated\n');git(source,'add','.');git(source,'commit','-m','更新')
            commit=git(source,'rev-parse','HEAD');bundle=base/'payload.bundle';git(source,'bundle','create',str(bundle),'HEAD')
            def receive(sha):
                return subprocess.run(['python3',str(ROOT/'migration/push_device.py'),'receive',sha],input=bundle.read_bytes(),capture_output=True,env=env)
            self.assertNotEqual(receive('0'*40).returncode,0)
            self.assertNotEqual(git(repo,'rev-parse','HEAD'),commit)
            (repo/'dirty').write_text('user work');self.assertNotEqual(receive(commit).returncode,0);(repo/'dirty').unlink()
            success=receive(commit);self.assertEqual(success.returncode,0,success.stderr.decode())
            self.assertEqual((home/'.codex/AGENTS.md').read_text(),'Updated\n')
            state=home/'.local/state/skillstow';before=set((state/'backups').iterdir())
            self.assertEqual(receive(commit).returncode,0);self.assertEqual(before,set((state/'backups').iterdir()))
            (home/'.codex/skills/decision-grade-reporting/SKILL.md').write_text('local change')
            self.assertNotEqual(receive(commit).returncode,0)
            self.assertEqual((home/'.codex/skills/decision-grade-reporting/SKILL.md').read_text(),'local change')

if __name__=='__main__':unittest.main()
