"""真实 Git 双 checkout 验收；所有数据和工具目录隔离在临时目录。"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

BIN = pathlib.Path(os.environ.get('SKILLSTOW_BIN', pathlib.Path(__file__).resolve().parents[1] / 'target/debug/skillstow')).resolve()

def run(*args, cwd=None, code=0):
    p = subprocess.run([str(a) for a in args], cwd=cwd, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=40)
    assert p.returncode == code, (args, p.returncode, p.stdout, p.stderr)
    return p.stdout

def git(repo, *args):
    return run('git', '-C', repo, *args).strip()

def write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)

class SyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='skillstow-e2e-')
        self.root = pathlib.Path(self.tmp.name).resolve()
        self.origin = self.root / 'origin.git'
        run('git', 'init', '--bare', '--initial-branch=main', self.origin)
        self.a = self.root/'a'; self.b = self.root/'b'
        run('git', 'clone', self.origin, self.a)
        for k,v in [('user.name', 'Test'), ('user.email','test@example.invalid')]: git(self.a, 'config', k, v)
        self.platform = {'darwin':'macos', 'linux':'linux', 'win32':'windows'}[sys.platform]
        self.manifest = f'''[tools.codex]
path = "{self.root.as_posix()}/unused"
[skills.review.variants.universal]
path = "skills/review/common"
[skills.review.variants.b]
path = "skills/review/b"
device = "b"
[devices.a]
platform = "{self.platform}"
enabled = ["review"]
[devices.b]
platform = "{self.platform}"
enabled = ["review"]
'''
        write(self.a/'skillstow.toml', self.manifest)
        for variant in ['common','b']:
            write(self.a/f'skills/review/{variant}/SKILL.md', '---\nname: review\ndescription: Test\n---\nInitial\n')
            write(self.a/f'skills/review/{variant}/references/check.md', f'{variant} resource\n')
        git(self.a,'add','-A'); git(self.a,'commit','-m','initial'); git(self.a,'push','-u','origin','main')
        run('git','clone',self.origin,self.b)
        for k,v in [('user.name','Test'),('user.email','test@example.invalid')]: git(self.b,'config',k,v)
        self.configs = {}
        for name,repo in [('a',self.a),('b',self.b)]:
            cfg = self.root/name.replace(name,'state-'+name)/'config.toml'
            write(cfg, f'repo = "{repo.as_posix()}"\ndevice = "{name}"\ntools = ["codex"]\n[overrides]\ncodex = "{self.root.as_posix()}/tool-{name}"\n')
            self.configs[name] = cfg
            self.cli(name, 'sync')
    def tearDown(self): self.tmp.cleanup()
    def cli(self, name, *args, code=0): return run(BIN, '--config', self.configs[name], *args, code=code)
    def test_complete_resources_variants_and_idempotence(self):
        self.assertEqual((self.root/'tool-a/review/references/check.md').read_text(),'common resource\n')
        self.assertEqual((self.root/'tool-b/review/references/check.md').read_text(),'b resource\n')
        head = git(self.a,'rev-parse','HEAD')
        self.cli('a','sync'); self.cli('a','status')
        self.assertEqual(head,git(self.a,'rev-parse','HEAD'))
    def test_edit_isolation_background_and_cross_device_maintenance(self):
        self.cli('a','edit','begin')
        write(self.a/'skills/review/common/references/check.md','edited common\n')
        write(self.a/'skills/review/b/references/check.md','maintained b from a\n')
        self.cli('a','sync','--background')
        self.assertEqual((self.root/'tool-a/review/references/check.md').read_text(),'common resource\n')
        self.cli('a','sync',code=2)
        self.cli('a','edit','finish')
        self.cli('b','sync')
        self.assertEqual((self.root/'tool-b/review/references/check.md').read_text(),'maintained b from a\n')
    def test_concurrent_distinct_changes_merge(self):
        write(self.a/'skills/review/common/references/a.md','from a')
        write(self.b/'skills/review/b/references/b.md','from b')
        self.cli('a','sync'); self.cli('b','sync'); self.cli('a','sync')
        self.assertTrue((self.a/'skills/review/b/references/b.md').exists())
        self.assertTrue((self.b/'skills/review/common/references/a.md').exists())
    def test_conflict_keeps_edit_and_published_content(self):
        self.cli('b','edit','begin')
        write(self.a/'skills/review/common/SKILL.md','version A\n')
        write(self.b/'skills/review/common/SKILL.md','version B\n')
        self.cli('a','sync')
        self.cli('b','edit','finish',code=2)
        self.assertTrue((self.configs['b'].parent/'editing').exists())
        self.assertIn('Initial',(self.configs['b'].parent/'published/skills/review/common/SKILL.md').read_text())
        write(self.b/'skills/review/common/SKILL.md','merged A and B\n')
        git(self.b,'add','-A'); git(self.b,'-c','core.editor=true','rebase','--continue')
        self.cli('b','edit','finish')
        self.assertFalse((self.configs['b'].parent/'editing').exists())
    def test_foreign_files_survive(self):
        foreign = self.root/'tool-a/foreign/SKILL.md'; write(foreign,'user owned')
        self.cli('a','sync',code=1)
        self.assertEqual(foreign.read_text(),'user owned')
        self.cli('a','status',code=1)
    def test_two_device_variants_are_ambiguous_even_with_platform(self):
        before=git(self.origin,'rev-parse','main')
        write(self.a/'skills/review/other/SKILL.md','---\nname: review\ndescription: Test\n---\n')
        write(self.a/'skillstow.toml',self.manifest+f'\n[skills.review.variants.other]\npath = "skills/review/other"\ndevice = "b"\nplatform = "{self.platform}"\n')
        self.cli('a','sync','--approve-removals',code=2)
        self.assertEqual(before,git(self.origin,'rev-parse','main'))
    def test_invalid_candidate_never_published(self):
        before = git(self.origin,'rev-parse','main')
        write(self.a/'skillstow.toml', self.manifest.replace('enabled = ["review"]','enabled = ["missing"]',1))
        self.cli('a','sync',code=2)
        self.assertEqual(before,git(self.origin,'rev-parse','main'))
    def test_symlink_inside_package_rejected(self):
        if os.name == 'nt': self.skipTest('requires symlink privilege')
        (self.a/'skills/review/common/leak').symlink_to(self.a/'skillstow.toml')
        self.cli('a','sync',code=2)
    def test_removing_managed_link_does_not_remove_package(self):
        write(self.a/'skillstow.toml', self.manifest.replace('enabled = ["review"]','enabled = []',1))
        self.cli('a','sync',code=2)
        self.cli('a','sync','--approve-removals')
        self.assertFalse((self.root/'tool-a/review').exists())
        self.assertTrue((self.configs['a'].parent/'published/skills/review/common/SKILL.md').exists())
    def test_background_waits_for_stability(self):
        before=git(self.a,'rev-parse','HEAD')
        write(self.a/'skills/review/common/references/new.md','new')
        self.cli('a','sync','--background')
        self.assertEqual(before,git(self.a,'rev-parse','HEAD'))
        stamp=self.configs['a'].parent/'quiet'
        fingerprint=stamp.read_text().split()[0]
        stamp.write_text(f'{fingerprint} 0')
        self.cli('a','sync','--background')
        self.assertNotEqual(before,git(self.a,'rev-parse','HEAD'))
    def test_ignored_resource_blocks_publication(self):
        before=git(self.origin,'rev-parse','main')
        write(self.a/'.gitignore','secret-resource.txt\n')
        write(self.a/'skills/review/common/secret-resource.txt','required content')
        self.cli('a','sync',code=2)
        self.assertEqual(before,git(self.origin,'rev-parse','main'))
    def test_prepublication_hook_blocks_invalid_runtime(self):
        before=git(self.origin,'rev-parse','main')
        cfg=self.configs['a']
        cfg.write_text(cfg.read_text().replace('[overrides]',f'before_publish = ["{sys.executable}", "-c", "raise SystemExit(1)"]\n[overrides]'))
        write(self.a/'skills/review/common/references/new.md','candidate')
        self.cli('a','sync',code=2)
        self.assertEqual(before,git(self.origin,'rev-parse','main'))
    def test_adapter_failure_not_reported_applied(self):
        cfg=self.configs['a']
        text=cfg.read_text().replace('[overrides]',f'after_apply = ["{sys.executable}", "-c", "raise SystemExit(1)"]\n[overrides]')
        cfg.write_text(text)
        self.cli('a','sync',code=2)
        self.cli('a','status',code=1)
    def test_invalid_variant_and_dependency_stop_publication(self):
        before=git(self.origin,'rev-parse','main')
        write(self.a/'skillstow.toml',self.manifest.replace('[skills.review.variants.universal]','[skills.review]\nrequires = ["missing"]\n[skills.review.variants.universal]'))
        self.cli('a','sync',code=2)
        self.assertEqual(before,git(self.origin,'rev-parse','main'))
    def test_dirty_published_tree_is_preserved(self):
        write(self.root/'tool-a/review/references/check.md','external edit')
        self.cli('a','sync',code=2)
        self.assertEqual((self.root/'tool-a/review/references/check.md').read_text(),'external edit')

if __name__ == '__main__': unittest.main(verbosity=2)
