"""Omega surgical audit regressions (28 Nov 2026).

All Flagsmith operations are mocked or strictly offline; no real credentials or Cloud mutations.
"""
from __future__ import annotations
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_sentinel import s, CliDouble

CLI_ORIGINAL = s.cli
RUN_TESTS_ORIGINAL = s.run_tests


class OmegaRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.context = {
            'project_id': 123,
            'project_name': 'megalab-test',
            'environment_id': 456,
            'environment_name': 'sandbox',
            'environment_key_sha256': s.sha('MY_SDK_KEY'),
        }
        self.policy = self.root / 'operator' / 'sandbox.json'
        self.policy.parent.mkdir()
        self.policy.write_text(
            json.dumps({'mode': 'sandbox-only', 'context': self.context}),
            encoding='utf-8',
        )
        self.fake = CliDouble()
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        patchers = [
            patch.object(s, 'STATE', self.root / 'outside_state'),
            patch.object(s, 'REPO_ROOT', self.root / 'repo'),
            patch.object(s, 'POLICY_PATH', self.policy),
            patch.object(s, 'git_state', return_value='a' * 40),
            patch.object(s, 'run_tests', return_value=47),
            patch.dict(os.environ, {'FLAGSMITH_ENVIRONMENT': 'MY_SDK_KEY'}),
            patch.object(s, 'cli', self.fake),
            patch('sys.stdout', self.stdout),
            patch('sys.stderr', self.stderr),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)
        self.argv = ['--project', '123', '--environment-name', 'sandbox', '--flag', 'demo_release']

    def test_01_flag_enabled_externally_during_confirm_blocks_without_mutation(self):
        self.assertEqual(s.main(['plan', *self.argv]), 0)

        def external_enable(_):
            self.fake.enabled = True
            self.fake.operator_confirmed = True

        with patch.object(s, 'human_confirm', side_effect=external_enable):
            self.assertEqual(s.main(['apply', *self.argv]), 2)
        self.assertFalse(any('enable' in c or 'disable' in c for c in self.fake.calls))
        self.assertTrue(self.fake.enabled)

    def test_02_policy_revoked_during_confirm_blocks_apply_and_rollback(self):
        self.assertEqual(s.main(['plan', *self.argv]), 0)

        def revoke(_):
            self.policy.unlink()
            self.fake.operator_confirmed = True

        with patch.object(s, 'human_confirm', side_effect=revoke):
            self.assertEqual(s.main(['apply', *self.argv]), 2)
        self.assertFalse(any('enable' in c for c in self.fake.calls))

        # Re-create policy, set flag ON, revoke during rollback prompt
        self.policy.write_text(
            json.dumps({'mode': 'sandbox-only', 'context': self.context}),
            encoding='utf-8',
        )
        self.fake.enabled = True
        with patch.object(s, 'human_confirm', side_effect=revoke):
            self.assertEqual(s.main(['rollback', *self.argv]), 2)
        self.assertFalse(any('disable' in c for c in self.fake.calls))

    def test_03_superseded_plan_cannot_apply_or_delete_newer_plan(self):
        argv_b = ['--project', '123', '--environment-name', 'sandbox', '--flag', 'other_flag']
        self.assertEqual(s.main(['plan', *self.argv]), 0)
        n1 = json.loads((s.STATE / 'plan.json').read_text(encoding='utf-8'))['nonce']
        holder = {}

        def overwrite_plan(_):
            self.fake.operator_confirmed = True
            # Fake flag get for other_flag
            with patch.object(s, 'get_state', return_value=False):
                self.assertEqual(s.main(['plan', *argv_b]), 0)
            holder['n2'] = json.loads((s.STATE / 'plan.json').read_text(encoding='utf-8'))['nonce']

        with patch.object(s, 'human_confirm', side_effect=overwrite_plan):
            self.assertEqual(s.main(['apply', *self.argv]), 2)
        self.assertFalse(any('enable' in c for c in self.fake.calls))
        self.assertTrue((s.STATE / 'plan.json').exists())
        remaining = json.loads((s.STATE / 'plan.json').read_text(encoding='utf-8'))
        self.assertEqual(remaining['nonce'], holder['n2'])
        self.assertNotEqual(n1, holder['n2'])
        self.assertFalse((s.STATE / ('used-' + n1)).exists())

    def test_04_second_keyboard_interrupt_in_emergency_disable_logs_unverified(self):
        self.assertEqual(s.main(['plan', *self.argv]), 0)
        self.fake.fail_enable = True
        self.fake.operator_confirmed = True
        orig_cli = self.fake

        def interrupt_on_disable(args):
            if 'disable' in args:
                raise KeyboardInterrupt()
            return orig_cli(args)

        with patch.object(s, 'cli', side_effect=interrupt_on_disable), \
             patch.object(s, 'human_confirm', return_value=None):
            rc = s.main(['apply', *self.argv])
        self.assertEqual(rc, 2)
        self.assertTrue(self.fake.enabled)
        ev = (s.STATE / 'evidence.jsonl').read_text(encoding='utf-8')
        self.assertIn('EMERGENCY_ROLLBACK_UNVERIFIED', ev)
        self.assertIn('NOT VERIFIED', self.stderr.getvalue())

    def test_05_cli_strips_all_inherited_flagsmith_context_vars(self):
        seen_env = {}

        def fake_run(argv, **kwargs):
            seen_env.update(kwargs['env'])
            return 'flagsmith version v2.0.0'

        injected = {
            'FLAGSMITH_ENVIRONMENT': 'MY_SDK_KEY',
            'FLAGSMITH_API_KEY': 'MOCK_ADMIN_KEY',
            'FLAGSMITH_ORGANISATION': '77777',
            'FLAGSMITH_PROJECT': '66666',
            'FLAGSMITH_CONFIG_PATH': 'C:/evil/flagsmith.json',
            'FLAGSMITH_ENVIRONMENT_KEY': 'WRONG_ENV',
            'FLAGSMITH_SDK_API_URL': 'https://evil-sdk.invalid',
            'FLAGSMITH_API_URL': 'https://evil-api.invalid',
            'FLAGSMITH_JSON_OUTPUT': 'true',
            'FLAGSMITH_NO_INPUT': 'false',
        }
        with patch.object(s, 'cli', CLI_ORIGINAL), \
             patch.dict(os.environ, injected), \
             patch.object(s.shutil, 'which', return_value='flagsmith'), \
             patch.object(s, 'run_command', side_effect=fake_run):
            self.assertEqual(s.cli(['--version']), 'flagsmith version v2.0.0')
        self.assertEqual(seen_env.get('FLAGSMITH_ENVIRONMENT'), 'MY_SDK_KEY')
        self.assertEqual(seen_env.get('FLAGSMITH_API_KEY'), 'MOCK_ADMIN_KEY')
        for stripped in (
            'FLAGSMITH_ORGANISATION', 'FLAGSMITH_PROJECT', 'FLAGSMITH_CONFIG_PATH',
            'FLAGSMITH_ENVIRONMENT_KEY', 'FLAGSMITH_SDK_API_URL', 'FLAGSMITH_API_URL',
            'FLAGSMITH_JSON_OUTPUT', 'FLAGSMITH_NO_INPUT',
        ):
            self.assertNotIn(stripped, seen_env)

    def test_06_cli_tempdir_windows_lock_or_oserror_fails_closed(self):
        # Verify TemporaryDirectory is configured with ignore_cleanup_errors=True
        # and creation OSError becomes Blocked instead of uncaught exception.
        orig_td = tempfile.TemporaryDirectory
        recorded_kwargs = {}

        def spy_td(*args, **kwargs):
            recorded_kwargs.update(kwargs)
            return orig_td(*args, **kwargs)

        with patch.object(s, 'cli', CLI_ORIGINAL), \
             patch.object(s.shutil, 'which', return_value='flagsmith'), \
             patch.object(s, 'run_command', return_value='flagsmith version v2.0.0'), \
             patch.object(s.tempfile, 'TemporaryDirectory', side_effect=spy_td):
            self.assertEqual(s.cli(['--version']), 'flagsmith version v2.0.0')
        self.assertTrue(recorded_kwargs.get('ignore_cleanup_errors'))

        with patch.object(s, 'cli', CLI_ORIGINAL), \
             patch.object(s.shutil, 'which', return_value='flagsmith'), \
             patch.object(s.tempfile, 'TemporaryDirectory', side_effect=PermissionError('locked')):
            self.assertEqual(s.main(['inspect', *self.argv]), 2)
        self.assertIn('BLOCKED', (s.STATE / 'evidence.jsonl').read_text(encoding='utf-8'))

    def test_07_semver_v2_prerelease_and_build_accepted_and_multiline_rejected(self):
        args = argparse.Namespace(organisation=42000, project=50001,
                                  environment_name='Development', flag='demo_release')

        def fake_json(argv):
            if argv[-2:] == ['auth', 'status']:
                return {'credentialSource': 'keychain', 'apiUrl': 'https://api.flagsmith.com'}
            if len(argv) >= 3 and argv[-3:-1] == ['project', 'get']:
                return {'id': 50001, 'name': 'MEGALAB Sandbox', 'organisation': 42000}
            if len(argv) >= 3 and argv[-3:-1] == ['environment', 'get']:
                return {'id': 100001, 'project': 50001, 'name': 'Development', 'api_key': 'MY_SDK_KEY'}
            raise AssertionError(argv)

        for good in (
            'flagsmith version v2.0.1-rc.1+build.42',
            'flagsmith version v2.1.0-alpha-1',
            'flagsmith version v2.0.0+git-abcdef',
        ):
            with self.subTest(good=good), \
                 patch.object(s, 'cli', return_value=good), \
                 patch.object(s, 'cli_json', side_effect=fake_json):
                _, got = s.preflight(args)
                self.assertEqual(got, good)

        with patch.object(s, 'cli', return_value='flagsmith\nversion\nv2.0.0'), \
             patch.object(s, 'cli_json', side_effect=fake_json):
            with self.assertRaisesRegex(s.Blocked, 'CLI v2'):
                s.preflight(args)

    def test_08_run_tests_scrubs_extended_secret_and_flagsmith_vars(self):
        captured = {}

        def fake_sub(command, **kwargs):
            captured.update(kwargs['env'])
            return subprocess.CompletedProcess(args=[], returncode=2, stdout='', stderr='')

        secrets_env = {
            'FLAGSMITH_ORGANISATION': '42000',
            'FLAGSMITH_TOKEN': 'mock',
            'AWS_SESSION_TOKEN': 'mock',
            'NPM_TOKEN': 'mock',
            'STRIPE_SECRET': 'mock',
            'DB_PASSWORD': 'mock',
            'SAFE_RUNTIME_VAR': 'keep',
        }
        with patch.dict(os.environ, secrets_env), \
             patch.object(s.subprocess, 'run', side_effect=fake_sub):
            with self.assertRaises(s.Blocked):
                RUN_TESTS_ORIGINAL()
        for k in ('FLAGSMITH_ORGANISATION', 'FLAGSMITH_TOKEN', 'AWS_SESSION_TOKEN',
                  'NPM_TOKEN', 'STRIPE_SECRET', 'DB_PASSWORD'):
            self.assertNotIn(k, captured)
        self.assertEqual(captured.get('SAFE_RUNTIME_VAR'), 'keep')


if __name__ == '__main__':
    unittest.main()
