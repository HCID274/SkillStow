"""真实 Git 双 checkout 与模块适配器验收；仓库、设备 home 和状态都隔离在临时目录。"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
BIN = pathlib.Path(os.environ.get('SKILLSTOW_BIN', REPO / 'target/debug/skillstow')).resolve()
ADAPTER = REPO / 'migration/skill_module.py'
PLATFORM = {'darwin': 'macos', 'win32': 'windows'}.get(sys.platform, sys.platform)


def run(*args, code=0, env=None):
    p = subprocess.run([str(a) for a in args], text=True, encoding='utf-8', capture_output=True,
                       stdin=subprocess.DEVNULL, timeout=60, env=env)
    assert p.returncode == code, (args, p.returncode, p.stdout, p.stderr)
    return p.stdout


def git(repo, *args):
    return run('git', '-C', repo, *args).strip()


def write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def skill(name, body='Initial'):
    return f'---\nname: {name}\ndescription: Test\n---\n{body}\n'


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='skillstow-e2e-')
        self.root = pathlib.Path(self.tmp.name).resolve()
        self.origin = self.root / 'origin.git'
        run('git', 'init', '--bare', '--initial-branch=main', self.origin)
        self.a, self.b = self.root / 'a', self.root / 'b'
        run('git', 'clone', self.origin, self.a)
        self.identity(self.a)
        self.manifest = {'version': 1, 'devices': {
            'a': {'platform': PLATFORM, 'ssh': 'test@127.0.0.1'},
            'b': {'platform': PLATFORM, 'ssh': 'test@127.0.0.1'}}, 'skills': {
            'decision-grade-reporting': {'source': 'shared/decision-grade-reporting', 'devices': ['a', 'b']},
            'review': {'source': 'shared/review', 'devices': ['a', 'b']},
            'special': {'source': 'devices/b/special', 'devices': ['b']}}}
        self.write_manifest(self.a)
        for name, source in [(n, e['source']) for n, e in self.manifest['skills'].items()]:
            write(self.a / 'system' / source / 'SKILL.md', skill(name))
        write(self.a / 'system/shared/decision-grade-reporting/references/global-collaboration.md', 'Global\n')
        write(self.a / 'system/shared/review/references/check.md', 'common resource\n')
        git(self.a, 'add', '-A'); git(self.a, 'commit', '-m', 'initial'); git(self.a, 'push', '-u', 'origin', 'main')
        run('git', 'clone', self.origin, self.b)
        self.identity(self.b)
        self.configs = {}
        for name, repo in [('a', self.a), ('b', self.b)]:
            cfg = self.root / f'state-{name}/config.toml'
            adapter = json.dumps([sys.executable, '-X', 'utf8', str(ADAPTER)])
            write(cfg, f'repo = {json.dumps(str(repo))}\ndevice = "{name}"\nmodule_adapter = {adapter}\n')
            self.configs[name] = cfg
            self.cli(name, 'sync')

    def tearDown(self):
        # Windows junction 不能交给递归目录清理猜测；先移除客户端入口链接自身。
        sys.path.insert(0, str(ADAPTER.parent))
        import skill_module
        for name in ['a', 'b']:
            for client in ['.agents', '.claude']:
                p = self.home(name) / client / 'skills'
                if skill_module.linked(p):
                    skill_module.unlink(p)
        self.tmp.cleanup()

    def identity(self, repo):
        for k, v in [('user.name', 'Test'), ('user.email', 'test@example.invalid')]:
            git(repo, 'config', k, v)

    def write_manifest(self, repo):
        write(repo / 'system/manifest.json', json.dumps(self.manifest, indent=2))

    def home(self, name):
        return self.root / f'home-{name}'

    def active(self, name, rel):
        return self.home(name) / '.codex/skills' / rel

    def cli(self, name, *args, code=0):
        home = str(self.home(name))
        env = {**os.environ, 'HOME': home, 'USERPROFILE': home}
        return run(BIN, '--config', self.configs[name], *args, code=code, env=env)

    def receipt(self, name):
        return (self.configs[name].parent / 'receipt.toml').read_text()

    def test_scope_resources_and_idempotence(self):
        self.assertEqual(self.active('a', 'review/references/check.md').read_text(), 'common resource\n')
        self.assertFalse(self.active('a', 'special').exists())
        self.assertTrue((self.home('b') / '.claude/skills/special/SKILL.md').is_file())
        self.assertEqual((self.home('a') / '.codex/AGENTS.md').read_text(), 'Global\n')
        head = git(self.a, 'rev-parse', 'HEAD')
        self.cli('a', 'sync'); self.cli('a', 'status')
        self.assertEqual(head, git(self.a, 'rev-parse', 'HEAD'))

    def test_background_noop_is_silent_and_skips_adapter(self):
        before = self.receipt('a')
        self.assertEqual(self.cli('a', 'sync', '--background'), '')
        self.assertEqual(before, self.receipt('a'))

    def test_background_receives_remote_update(self):
        write(self.a / 'system/shared/review/references/check.md', 'updated from a\n')
        self.cli('a', 'sync')
        self.assertIn('application=applied', self.cli('b', 'sync', '--background'))
        self.assertEqual(self.active('b', 'review/references/check.md').read_text(), 'updated from a\n')
        self.cli('b', 'status')

    def test_edit_isolation_and_cross_device_maintenance(self):
        self.cli('a', 'edit', 'begin')
        write(self.a / 'system/devices/b/special/references/note.md', 'maintained b from a\n')
        self.assertIn('editing', self.cli('a', 'sync', '--background'))
        self.cli('a', 'sync', code=2)
        self.cli('a', 'edit', 'finish')
        self.cli('b', 'sync')
        self.assertEqual(self.active('b', 'special/references/note.md').read_text(), 'maintained b from a\n')
        self.assertFalse(self.active('a', 'special').exists())

    def test_concurrent_distinct_changes_merge(self):
        write(self.a / 'system/shared/review/references/a.md', 'from a')
        write(self.b / 'system/devices/b/special/references/b.md', 'from b')
        self.cli('a', 'sync'); self.cli('b', 'sync'); self.cli('a', 'sync')
        self.assertTrue((self.a / 'system/devices/b/special/references/b.md').exists())
        self.assertTrue(self.active('b', 'review/references/a.md').exists())

    def test_conflict_keeps_edit_and_published_content(self):
        self.cli('b', 'edit', 'begin')
        write(self.a / 'system/shared/review/references/check.md', 'version A\n')
        write(self.b / 'system/shared/review/references/check.md', 'version B\n')
        self.cli('a', 'sync')
        self.cli('b', 'edit', 'finish', code=2)
        self.assertTrue((self.configs['b'].parent / 'editing').exists())
        self.assertEqual(self.active('b', 'review/references/check.md').read_text(), 'common resource\n')
        write(self.b / 'system/shared/review/references/check.md', 'merged A and B\n')
        git(self.b, 'add', '-A'); git(self.b, '-c', 'core.editor=true', 'rebase', '--continue')
        self.cli('b', 'edit', 'finish')
        self.assertFalse((self.configs['b'].parent / 'editing').exists())
        self.assertEqual(self.active('b', 'review/references/check.md').read_text(), 'merged A and B\n')

    def test_receiver_does_not_need_a_working_push_endpoint(self):
        git(self.a, 'config', 'remote.origin.pushurl', str(self.root / 'no-push-endpoint.git'))
        self.cli('a', 'sync')
        self.cli('a', 'status')

    def test_unreachable_origin_preserves_edit_and_recovers(self):
        self.cli('a', 'edit', 'begin')
        write(self.a / 'system/shared/review/references/recovered.md', 'pending offline update')
        before = git(self.a, 'rev-parse', 'HEAD')
        git(self.a, 'remote', 'set-url', 'origin', str(self.root / 'unreachable.git'))
        self.cli('a', 'edit', 'finish', code=2)
        self.assertEqual(before, git(self.a, 'rev-parse', 'HEAD'))
        self.assertTrue((self.configs['a'].parent / 'editing').exists())
        git(self.a, 'remote', 'set-url', 'origin', str(self.origin))
        self.cli('a', 'edit', 'finish'); self.cli('b', 'sync')
        self.assertEqual(self.active('b', 'review/references/recovered.md').read_text(), 'pending offline update')

    def test_background_waits_for_stability(self):
        before = git(self.a, 'rev-parse', 'HEAD')
        write(self.a / 'system/shared/review/references/new.md', 'new')
        self.cli('a', 'sync', '--background')
        self.assertEqual(before, git(self.a, 'rev-parse', 'HEAD'))
        stamp = self.configs['a'].parent / 'quiet'
        stamp.write_text(f'{stamp.read_text().split()[0]} 0')
        self.cli('a', 'sync', '--background')
        self.assertNotEqual(before, git(self.a, 'rev-parse', 'HEAD'))

    def test_invalid_candidate_never_published(self):
        before = git(self.origin, 'rev-parse', 'main')
        self.manifest['skills']['review']['devices'] = ['a', 'missing']
        self.write_manifest(self.a)
        self.cli('a', 'sync', code=2)
        self.assertEqual(before, git(self.origin, 'rev-parse', 'main'))

    def test_symlink_inside_package_rejected(self):
        if os.name == 'nt':
            self.skipTest('requires symlink privilege')
        (self.a / 'system/shared/review/leak').symlink_to(self.a / 'system/manifest.json')
        self.cli('a', 'sync', code=2)

    def test_scope_removal_requires_approval(self):
        before = git(self.origin, 'rev-parse', 'main')
        self.manifest['skills']['review']['devices'] = ['a']
        self.write_manifest(self.a)
        self.cli('a', 'sync', code=2)
        self.assertEqual(before, git(self.origin, 'rev-parse', 'main'))
        self.cli('a', 'sync', '--approve-removals')
        self.cli('b', 'sync')
        self.assertFalse(self.active('b', 'review').exists())
        self.assertTrue(self.active('a', 'review/SKILL.md').exists())

    def test_external_drift_blocks_application_and_status(self):
        drifted = self.active('a', 'review/references/check.md')
        drifted.write_text('external edit')
        write(self.b / 'system/shared/review/references/check.md', 'from b\n')
        self.cli('b', 'sync')
        self.cli('a', 'sync', code=2)
        self.assertEqual(drifted.read_text(), 'external edit')
        self.assertIn('applied = false', self.receipt('a'))
        self.cli('a', 'status', code=1)

    def test_foreign_skill_survives(self):
        foreign = self.active('a', 'foreign/SKILL.md')
        write(foreign, 'user owned')
        write(self.b / 'system/shared/review/references/check.md', 'from b\n')
        self.cli('b', 'sync'); self.cli('a', 'sync')
        self.assertEqual(foreign.read_text(), 'user owned')


if __name__ == '__main__':
    unittest.main(verbosity=2)
