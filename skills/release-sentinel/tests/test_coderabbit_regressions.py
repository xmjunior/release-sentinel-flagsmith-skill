"""Independent follow-up to CodeRabbit findings (27 Nov 2026).

No Flagsmith network calls, no real SDK credentials and no Cloud mutations.
Do not run security tests in a user credentialed terminal if untrusted code is present.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from test_sentinel import s


class CodeRabbitFollowup(unittest.TestCase):
    def args(self, **kwargs):
        return argparse.Namespace(organisation=42000, project=50001,
            environment_name=kwargs.get('environment_name', 'Development'),
            flag=kwargs.get('flag', 'demo_release'))

    def preflight_version(self, version):
        def fake_json(argv):
            if argv[-2:] == ['auth', 'status']:
                return {'credentialSource': 'keychain', 'apiUrl': 'https://api.flagsmith.com'}
            if len(argv) >= 3 and argv[-3:-1] == ['project', 'get']:
                return {'id': 50001, 'name': 'MEGALAB Sandbox', 'organisation': 42000}
            if len(argv) >= 3 and argv[-3:-1] == ['environment', 'get']:
                return {'id': 100001, 'project': 50001, 'name': 'Development', 'api_key': 'MOCK_SDK_KEY'}
            raise AssertionError('Unexpected CLI JSON request')
        with patch.dict(os.environ, {'FLAGSMITH_ENVIRONMENT': 'MOCK_SDK_KEY'}), \
             patch.object(s, 'cli', return_value=version), \
             patch.object(s, 'cli_json', side_effect=fake_json):
            return s.preflight(self.args())

    def test_01_valid_flagsmith_v2_full_word(self):
        for version in ('flagsmith v2.0.0', 'flagsmith version v2.0.0',
                        'flagsmith version v2.1.13-beta.2'):
            with self.subTest(version=version):
                context, got = self.preflight_version(version)
                self.assertEqual(context['environment_name'], 'Development')
                self.assertEqual(got, version)

    def test_02_v1_minor_2_does_not_pass_as_v2(self):
        with self.assertRaisesRegex(s.Blocked, 'CLI v2'):
            self.preflight_version('flagsmith v1.2.3')

    def test_03_node_v22_fragment_does_not_pass_as_cli_v2(self):
        with self.assertRaisesRegex(s.Blocked, 'CLI v2'):
            self.preflight_version('flagsmith/3.0.0 linux-x64 node-v22.2.0')

    def test_04_other_tool_version_cannot_pretend_to_be_flagsmith(self):
        for v in ('otherapp version v2.0.0', 'flagsmith v2.0.0\nunsafe aftertext',
                  'flagsmith v0.2.0', 'flagsmith v2.0', ''):
            with self.subTest(v=v), self.assertRaisesRegex(s.Blocked, 'CLI v2'):
                self.preflight_version(v)

    def test_05_valid_flag_names_not_confused_with_production_context(self):
        for flag in ('product_search', 'deliver_new_ui', 'client_redesign',
                     'live_chat', 'production_metrics'):
            with self.subTest(flag=flag):
                self.assertEqual(s.check_identifier(flag, 'flag', deny_production=False), flag)

    def test_06_project_and_environment_production_context_still_blocked(self):
        for value in ('Production', 'megalab-prd', 'live', 'client-service'):
            with self.subTest(value=value), self.assertRaises(s.Blocked):
                s.check_identifier(value, 'environment')

    def test_07_injection_like_flag_names_rejected(self):
        for flag in ('--yes', '../etc/passwd', '', 'a\n--yes', 'x;shutdown'):
            with self.subTest(flag=flag), self.assertRaises(s.Blocked):
                s.check_identifier(flag, 'flag', deny_production=False)

    def test_08_cli_ignores_untrusted_flagsmith_config_and_runs_isolated(self):
        marker = object()
        def fake_run(argv, **kwargs):
            self.assertEqual(argv[:3], ['flagsmith', '--api-url', 'https://api.flagsmith.com'])
            self.assertNotIn('MOCK_SDK_KEY', argv)
            self.assertNotIn('--environment', argv)  # CLI v2 expects SDK KEY, not Development name
            self.assertEqual(kwargs['env']['FLAGSMITH_ENVIRONMENT'], 'MOCK_SDK_KEY')
            self.assertNotIn('FLAGSMITH_CONFIG_PATH', kwargs['env'])
            self.assertNotIn('FLAGSMITH_ENVIRONMENT_KEY', kwargs['env'])
            self.assertNotIn('FLAGSMITH_SDK_API_URL', kwargs['env'])
            self.assertNotEqual(Path(kwargs['cwd']).resolve(), s.REPO_ROOT.resolve())
            self.assertTrue(Path(kwargs['cwd']).is_dir())
            self.assertFalse((Path(kwargs['cwd'])/'flagsmith.json').exists())
            return 'flagsmith version v2.0.0'
        with patch.dict(os.environ, {'FLAGSMITH_ENVIRONMENT': 'MOCK_SDK_KEY',
                                     'FLAGSMITH_CONFIG_PATH': 'C:/evil/flagsmith.json',
                                     'FLAGSMITH_ENVIRONMENT_KEY': 'WRONG_ENVIRONMENT',
                                     'FLAGSMITH_SDK_API_URL': 'https://attacker.invalid'}), \
             patch.object(s.shutil, 'which', return_value='flagsmith'), \
             patch.object(s, 'run_command', side_effect=fake_run):
            self.assertEqual(s.cli(['--version']), 'flagsmith version v2.0.0')

    def test_09_mutation_scope_never_exposes_sdk_key_as_argument(self):
        def fake_run(argv, **kwargs):
            self.assertNotIn('MOCK_SDK_KEY', ' '.join(argv))
            self.assertEqual(kwargs['env']['FLAGSMITH_ENVIRONMENT'], 'MOCK_SDK_KEY')
            self.assertIn('flag', argv)
            self.assertIn('enable', argv)
            self.assertIn('demo_release', argv)
            self.assertIn('--project', argv)
            self.assertIn('50001', argv)
            return '{}'
        with patch.dict(os.environ, {'FLAGSMITH_ENVIRONMENT': 'MOCK_SDK_KEY'}), \
             patch.object(s.shutil, 'which', return_value='flagsmith'), \
             patch.object(s, 'run_command', side_effect=fake_run):
            # Test CLI argument construction only; NO REAL flagsmith binary invoked.
            s.change(self.args(), enable=True)

    def test_10_regression_test_runner_does_not_inherit_sdk_and_api_secrets(self):
        fake=subprocess.CompletedProcess(args=[], returncode=2, stdout='', stderr='')
        def fake_subprocess(command, **kwargs):
            env=kwargs['env']
            for key in ('FLAGSMITH_ENVIRONMENT','FLAGSMITH_ENVIRONMENT_KEY',
                        'FLAGSMITH_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY',
                        'GH_TOKEN','GITHUB_TOKEN'):
                self.assertNotIn(key,env)
            self.assertEqual(env.get('TEST_PRESERVED'),'ok')
            return fake
        with patch.dict(os.environ, {'FLAGSMITH_ENVIRONMENT':'MOCK_SDK_KEY',
                                     'FLAGSMITH_ENVIRONMENT_KEY':'mock',
                                     'FLAGSMITH_API_KEY':'mock',
                                     'OPENAI_API_KEY':'mock','ANTHROPIC_API_KEY':'mock',
                                     'GH_TOKEN':'mock','GITHUB_TOKEN':'mock',
                                     'TEST_PRESERVED':'ok'}), \
             patch.object(s.subprocess,'run',side_effect=fake_subprocess):
            with self.assertRaises(s.Blocked):
                s.run_tests()


    def test_11_inspect_accepts_product_named_flag_in_authorized_sandbox(self):
        ctx = {'project_id': 50001, 'project_name': 'MEGALAB Sandbox',
               'environment_id': 100001, 'environment_name': 'Development',
               'environment_key_sha256': s.sha('MOCK_SDK_KEY'),
               'organisation_id': 42000}
        with patch.object(s, 'preflight', return_value=(ctx,'flagsmith version v2.0.0')), \
             patch.object(s, 'load_policy', return_value=None), \
             patch.object(s, 'get_state', return_value=False) as get:
            result = s.main(['inspect','--organisation','42000','--project','50001',
                             '--environment-name','Development', '--flag','product_search'])
        self.assertEqual(result, 0)
        self.assertEqual(get.call_args.args[0].flag,'product_search')

if __name__ == '__main__': unittest.main()
