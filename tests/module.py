"""验证单源、设备范围、迁移保留、冲突及失败回滚；可在 Windows 原生 Python 运行。"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('module', Path(__file__).resolve().parents[1] / 'migration/skill_module.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ModuleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='skillstow-module-')
        self.base = Path(self.temp.name).resolve()
        self.repo = self.base / 'repo'; self.root = self.repo / 'system'
        self.root.mkdir(parents=True)
        subprocess.run(['git', 'init', '-b', 'main', str(self.repo)], check=True, capture_output=True)
        self.m = {'version': 1, 'devices': {
            'a': {'platform': 'linux', 'ssh': 'test@100.64.0.1'},
            'b': {'platform': 'windows', 'ssh': 'test@100.64.0.2'}}, 'skills': {}}
        for name, devices in [('decision-grade-reporting', ['a', 'b']), ('review', ['a', 'b']), ('special', ['b'])]:
            self.m['skills'][name] = {'source': f'shared/{name}', 'devices': devices}
            self.write(f'shared/{name}/SKILL.md', f'---\nname: {name}\ndescription: Test\n---\nOriginal\n')
        self.write('shared/decision-grade-reporting/references/global-collaboration.md', 'Global\n')
        self.manifest()
        subprocess.run(['git', '-C', str(self.repo), 'add', '-A'], check=True)
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'initial'], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(self.repo), 'update-ref', 'refs/remotes/origin/main', 'HEAD'], check=True)
        for name in ['a', 'b']:
            (self.base / name / '.codex/skills/legacy').mkdir(parents=True)
            (self.base / name / '.codex/skills/legacy/SKILL.md').write_text('old')

    def tearDown(self):
        # Windows junction 不能交给递归目录清理猜测；先明确移除链接自身。
        for name in ['a', 'b']:
            for client in ['.agents', '.claude']:
                p = self.base / name / client / 'skills'
                if module.linked(p): module.unlink(p)
        self.temp.cleanup()

    def write(self, rel, text):
        p = self.root / rel; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')

    def manifest(self):
        self.write('manifest.json', json.dumps(self.m))

    def apply(self, name, adopt=False):
        module.apply(self.root, module.load(self.root), name, self.base / name, adopt)

    def test_scope_single_source_and_client_links(self):
        self.apply('a', True); self.apply('b', True)
        self.assertFalse((self.base / 'a/.codex/skills/special/SKILL.md').exists())
        self.assertTrue((self.base / 'b/.claude/skills/special/SKILL.md').exists())
        self.write('shared/review/SKILL.md', '---\nname: review\ndescription: Test\n---\nUpdated\n')
        self.apply('a'); self.apply('b')
        for name in ['a', 'b']:
            self.assertIn('Updated', (self.base / name / '.agents/skills/review/SKILL.md').read_text())
            self.assertFalse((self.base / name / '.codex/skills/legacy/SKILL.md').exists())

    def test_same_version_is_idempotent_and_does_not_create_runtime(self):
        self.apply('a', True)
        home = self.base / 'a'; backups = home / '.local/state/skillstow/backups'
        before = set(backups.iterdir())
        self.apply('a')
        self.assertEqual(before, set(backups.iterdir()))
        self.assertFalse((home / '.codex/state/skill-runtime').exists())

    def test_resource_delete_preserves_credentials_and_unmanaged_content(self):
        self.write('shared/review/references/check.md', 'resource')
        self.apply('a', True)
        active = self.base / 'a/.codex/skills'
        (active / 'foreign').mkdir(); (active / 'foreign/data').write_text('keep')
        (active / '.system').mkdir(); (active / '.system/marker').write_text('plugin')
        (self.root / 'shared/review/references/check.md').unlink()
        self.apply('a')
        self.assertFalse((active / 'review/references/check.md').exists())
        self.assertEqual((active / 'foreign/data').read_text(), 'keep')
        self.assertEqual((active / '.system/marker').read_text(), 'plugin')

    def test_executable_resource_keeps_mode(self):
        if os.name == 'nt': self.skipTest('Unix executable mode')
        self.write('shared/review/scripts/run.sh', '#!/bin/sh\nexit 0\n')
        (self.root / 'shared/review/scripts/run.sh').chmod(0o755)
        self.apply('a', True)
        target = self.base / 'a/.codex/skills/review/scripts/run.sh'
        self.assertEqual(target.stat().st_mode & 0o777, 0o755)

    def test_drift_is_rejected_before_any_write(self):
        self.apply('a', True)
        active = self.base / 'a/.codex/skills/review/SKILL.md'
        active.write_text('external')
        with self.assertRaisesRegex(ValueError, '外部修改'): self.apply('a')
        self.assertEqual(active.read_text(), 'external')

    def test_legacy_runtime_migration_keeps_local_credentials(self):
        home = self.base / 'a'; active = home / '.codex/skills'
        secret = active / '.catalog/local/credentials.json'
        secret.parent.mkdir(parents=True); secret.write_text('local-placeholder')
        state = home / '.local/state/skillstow/runtime.json'
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps({'files': {'legacy/SKILL.md': module.digest(active / 'legacy/SKILL.md')}}))
        self.apply('a')
        self.assertEqual(secret.read_text(), 'local-placeholder')
        self.assertFalse((active / 'legacy/SKILL.md').exists())

    def test_adopt_removes_only_root_link_preserving_external_target(self):
        home = self.base / 'a'; target = self.base / 'external'
        target.mkdir(); (target / 'SKILL.md').write_text('old external skill')
        link = home / '.codex/skills/external'
        module.directory_link(target, link)
        self.apply('a', True)
        self.assertFalse(link.exists())
        self.assertEqual((target / 'SKILL.md').read_text(), 'old external skill')

    def test_adopt_selected_link_becomes_local_directory_and_rolls_back(self):
        home = self.base / 'a'; target = self.base / 'external'
        target.mkdir(); (target / 'SKILL.md').write_text('old external review')
        link = home / '.codex/skills/review'; module.directory_link(target, link)
        self.write('shared/review/references/new.md', 'new')
        blocker = home / '.agents/skills'; blocker.mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError, '真实目录'): self.apply('a', True)
        self.assertTrue(module.linked(link))
        self.assertEqual((target / 'SKILL.md').read_text(), 'old external review')
        blocker.rmdir()
        self.apply('a', True)
        self.assertFalse(module.linked(link))
        self.assertIn('Original', (link / 'SKILL.md').read_text())
        self.assertEqual((target / 'SKILL.md').read_text(), 'old external review')

    def test_failed_application_rolls_back_files_and_links(self):
        home = self.base / 'a'; target = home / '.agents/skills'
        target.mkdir(parents=True); (target / 'user-file').write_text('user')
        with self.assertRaisesRegex(RuntimeError, '真实目录'): self.apply('a', True)
        self.assertEqual((home / '.codex/skills/legacy/SKILL.md').read_text(), 'old')
        self.assertFalse((home / '.codex/skills/review/SKILL.md').exists())
        self.assertEqual((target / 'user-file').read_text(), 'user')

    def test_invalid_scope_path_and_identity_fail(self):
        for change in [{'source': '../escape'}, {'devices': ['unknown']}, {'source': 'shared/special'}]:
            original = dict(self.m['skills']['review'])
            self.m['skills']['review'].update(change); self.manifest()
            with self.assertRaises(ValueError): module.load(self.root)
            self.m['skills']['review'] = original

    def test_exact_impact_includes_scope_removal(self):
        self.write('shared/special/SKILL.md', '---\nname: special\ndescription: Test\n---\nUpdate\n')
        with patch.object(module, 'emit') as emit:
            self.assertEqual(module.impact(self.repo, self.root, self.m), 0)
            self.assertEqual(emit.call_args.args[0]['impact'][0]['devices'], ['b'])
        self.m['skills']['review']['devices'] = ['a']; self.manifest()
        with patch.object(module, 'emit'):
            self.assertEqual(module.impact(self.repo, self.root, self.m), 3)

    def test_only_obsolete_telemetry_hooks_are_removed(self):
        value = {'hooks': {'PostToolUse': [{'hooks': [{'command': 'python hook_skill_use.py'}, {'command': 'python3', 'args': ['hook_skill_use.py']}, {'command': 'keep-me'}]}]}, 'other': 1}
        actual = module.without_telemetry(value)
        self.assertEqual(actual['hooks']['PostToolUse'][0]['hooks'], [{'command': 'keep-me'}])
        self.assertEqual(actual['other'], 1)

    def test_device_rules_are_scoped_and_update_with_sync(self):
        self.m['devices']['a'].update(ssh='user@cluster.example.org', global_rules='devices/a/rules.md')
        self.write('devices/a/rules.md', 'Cluster event rules\n'); self.manifest()
        self.apply('a', True); self.apply('b', True)
        self.assertEqual((self.base / 'a/.codex/AGENTS.md').read_text(), 'Global\n\nCluster event rules\n')
        self.assertEqual((self.base / 'b/.codex/AGENTS.md').read_text(), 'Global\n')
        self.assertEqual((self.base / 'a/.claude/CLAUDE.md').read_text(), '@../.codex/AGENTS.md\n')
        self.write('devices/a/rules.md', 'Updated rules\n'); self.apply('a')
        self.assertIn('Updated rules', (self.base / 'a/.codex/AGENTS.md').read_text())
        self.m['devices']['a']['global_rules'] = '../outside'; self.manifest()
        with self.assertRaises(ValueError): module.load(self.root)


if __name__ == '__main__':
    unittest.main(verbosity=2)
