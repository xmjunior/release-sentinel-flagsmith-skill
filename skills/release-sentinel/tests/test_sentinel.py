"""Regression tests for the audit's new P0/P1 findings. All Flagsmith calls are simulated."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[1] / 'scripts' / 'sentinel.py'
SPEC = importlib.util.spec_from_file_location('release_sentinel', FILE)
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)
RUN_TESTS_ORIGINAL = s.run_tests


class CliDouble:
    def __init__(self, *, enabled=False, fail_enable=False, bad_verify=False, project=123, env_name='sandbox'):
        self.enabled = enabled
        self.fail_enable = fail_enable
        self.bad_verify = bad_verify
        self.project = project
        self.env_name = env_name
        self.calls = []
        self.operator_confirmed = False

    def __call__(self, args):
        self.calls.append(list(args))
        if args == ['--version']:
            return 'flagsmith v2.0.0'
        if 'status' in args:
            return json.dumps({'credentialSource':'$FLAGSMITH_API_KEY','organisations':[{'id':1}]})
        if 'project' in args and 'get' in args:
            return json.dumps({'id':self.project,'name':'megalab-test'})
        if 'environment' in args and 'get' in args:
            return json.dumps({'id':456,'project':self.project,'name':self.env_name,
                               'api_key':'MY_SDK_KEY'})
        if 'flag' in args and 'get' in args:
            state = False if self.bad_verify else self.enabled
            return json.dumps({'feature':'demo_release','enabled':state})
        if 'flag' in args and ('enable' in args or 'disable' in args):
            if not self.operator_confirmed:
                raise AssertionError('Mutated without operator approval')
            if '--yes' not in args or '--no-input' not in args:
                raise AssertionError('Missing CLI confirmation')
            if 'enable' in args:
                self.enabled = True
                if self.fail_enable:
                    raise s.Blocked('Command timed out; effect may be unknown')
            else:
                self.enabled = False
            return '{}'
        raise AssertionError('Unexpected Flagsmith command ' + str(args))


class P0P1Regressions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.context = {'project_id':123,'project_name':'megalab-test',
                        'environment_id':456,'environment_name':'sandbox',
                        'environment_key_sha256':s.sha('MY_SDK_KEY')}
        self.policy = self.root / 'operator' / 'sandbox.json'
        self.policy.parent.mkdir()
        self.policy.write_text(json.dumps({'mode':'sandbox-only','context':self.context}), encoding='utf-8')
        self.patchers = [
            patch.object(s, 'STATE', self.root / 'repo' / '.sentinel'),
            patch.object(s, 'REPO_ROOT', self.root / 'repo'),
            patch.object(s, 'POLICY_PATH', self.policy),
            patch.object(s, 'git_state', return_value='a'*40),
            patch.object(s, 'run_tests', return_value=7),
            patch.dict(os.environ, {'FLAGSMITH_ENVIRONMENT':'MY_SDK_KEY'}),
        ]
        for p in self.patchers:
            p.start(); self.addCleanup(p.stop)
        self.fake = CliDouble()
        p = patch.object(s, 'cli', self.fake)
        p.start(); self.addCleanup(p.stop)
        self.out = patch('sys.stdout', new_callable=io.StringIO)
        self.out.start(); self.addCleanup(self.out.stop)
        self.err = patch('sys.stderr', new_callable=io.StringIO)
        self.err.start(); self.addCleanup(self.err.stop)
        self.argv = ['--project','123','--environment-name','sandbox','--flag','demo_release']

    def run_action(self, name):
        return s.main([name, *self.argv])

    def approve(self):
        def confirmed(challenge):
            self.fake.operator_confirmed = True
            self.assertIn('P123/E456/sandbox', challenge)
            self.assertIn(s.sha('MY_SDK_KEY')[:12], challenge)
            self.assertIn('NONCE', challenge)
        p = patch.object(s, 'human_confirm', side_effect=confirmed)
        p.start(); self.addCleanup(p.stop)

    def test_p0_apply_with_one_time_full_scope_approval(self):
        self.approve()
        self.assertEqual(self.run_action('plan'), 0)
        self.assertEqual(self.run_action('apply'), 0)
        self.assertTrue(self.fake.enabled)
        self.assertTrue(any('--yes' in c and 'enable' in c for c in self.fake.calls))
        self.assertFalse(any('--yes' in c and 'get' in c for c in self.fake.calls))
        log=(s.STATE/'evidence.jsonl').read_text()
        self.assertNotIn('MY_SDK_KEY', log)

    def test_p0_replay_same_approval_denied(self):
        self.approve()
        self.run_action('plan')
        self.assertEqual(self.run_action('apply'), 0)
        self.assertEqual(self.run_action('apply'), 2)
        self.assertEqual(sum(1 for c in self.fake.calls if 'enable' in c), 1)

    def test_p0_cross_environment_policy_denied(self):
        self.run_action('plan')
        self.fake.env_name = 'qa'
        result = s.main(['apply', '--project','123','--environment-name','qa','--flag','demo_release'])
        self.assertEqual(result, 2)
        self.assertFalse(any('enable' in c for c in self.fake.calls))

    def test_p0_cross_project_policy_denied(self):
        self.run_action('plan')
        self.fake.project = 789
        result = s.main(['apply','--project','789','--environment-name','sandbox','--flag','demo_release'])
        self.assertEqual(result, 2)
        self.assertFalse(any('enable' in c for c in self.fake.calls))

    def test_p0_arbitrary_tests_args_rejected(self):
        with self.assertRaises(SystemExit) as err:
            s.main(['plan', *self.argv, '--tests', 'python', '-c', 'print(1)'])
        self.assertEqual(err.exception.code, 2)
        self.assertFalse(self.fake.calls)

    def test_p0_legacy_static_approval_rejected(self):
        with self.assertRaises(SystemExit) as err:
            s.main(['apply', *self.argv, '--approve', 'ENABLE:demo_release'])
        self.assertEqual(err.exception.code, 2)
        self.assertFalse(self.fake.calls)

    def test_p1_zero_test_suite_not_counted_as_pass(self):
        zero = subprocess.CompletedProcess(args=[], returncode=0, stdout='', stderr='Ran 0 tests in 0.000s\n\nOK\n')
        with patch.object(s.subprocess, 'run', return_value=zero):
            with self.assertRaisesRegex(s.Blocked, 'zero test'):
                RUN_TESTS_ORIGINAL()

    def test_p1_enable_timeout_after_change_rolls_back(self):
        self.fake.fail_enable = True
        self.approve()
        self.assertEqual(self.run_action('plan'), 0)
        self.assertEqual(self.run_action('apply'), 2)
        self.assertFalse(self.fake.enabled)
        self.assertIn('EMERGENCY_ROLLBACK_VERIFIED', (s.STATE/'evidence.jsonl').read_text())

    def test_p1_failed_post_verify_rolls_back(self):
        self.approve()
        self.assertEqual(self.run_action('plan'), 0)
        self.fake.bad_verify = True
        self.assertEqual(self.run_action('apply'), 2)
        self.assertFalse(self.fake.enabled)

    def test_p1_rollback_succeeds_with_dirty_git(self):
        self.fake.enabled = True
        self.approve()
        def dirty_git(*, require_clean=True):
            if require_clean: raise s.Blocked('Dirty Git')
            return 'a'*40
        with patch.object(s,'git_state',side_effect=dirty_git):
            self.assertEqual(self.run_action('rollback'),0)
        self.assertFalse(self.fake.enabled)

    def test_p1_git_changes_after_enable_triggers_recovery(self):
        self.approve()
        self.run_action('plan')
        calls={'n':0}
        def git_changed(*,require_clean=True):
            calls['n'] += 1
            if require_clean and calls['n'] >= 3:
                raise s.Blocked('Git became dirty after enable')
            return 'a'*40
        with patch.object(s, 'git_state', side_effect=git_changed):
            self.assertEqual(self.run_action('apply'),2)
        self.assertFalse(self.fake.enabled)

    def test_p0_no_terminal_never_mutates(self):
        self.run_action('plan')
        with patch.object(s.sys.stdin,'isatty',return_value=False):
            self.assertEqual(self.run_action('apply'),2)
        self.assertFalse(any('enable' in c for c in self.fake.calls))

    def test_p0_production_names_denied(self):
        for bad in ['production','prod-east','live','customer-app']:
            with self.subTest(bad=bad), self.assertRaises(s.Blocked):
                s.check_identifier(bad,'environment')

    def test_p0_admin_auth_required(self):
        def no_auth(args):
            if args == ['--version']: return 'flagsmith v2.0.0'
            return '{"credentialSource": ""}'
        with patch.object(s, 'cli', side_effect=no_auth):
            self.assertEqual(self.run_action('inspect'),2)

    def test_p1_readback_fails_closed(self):
        self.fake.bad_verify=True
        self.assertEqual(self.run_action('inspect'),0)  # correct boolean, read-only inspection
        with patch.object(s, 'cli_json', return_value={'feature':'demo_release','wrong_field':False}):
            with self.assertRaises(s.Blocked):
                s.get_state(s.argparse.Namespace(project=123,flag='demo_release'))


if __name__ == '__main__':
    unittest.main()
