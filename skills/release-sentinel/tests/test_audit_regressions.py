"""Reproductions of 27-Nov Antigravity PR14 audit; all Flagsmith calls mocked.
No real Flagsmith Cloud writes, no API keys and no user home state changes.
"""
from datetime import datetime, timedelta
import json
from pathlib import Path
import os
import subprocess
import unittest
from unittest.mock import patch

from test_sentinel import s, CliDouble
CLI_ORIGINAL = s.cli


class AntigravityRegressionTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.context={'project_id':123,'project_name':'megalab-test',
                'environment_id':456,'environment_name':'sandbox',
                'environment_key_sha256':s.sha('MY_SDK_KEY')}
        self.policy=self.root/'operator'/'sandbox.json'
        self.policy.parent.mkdir()
        self.policy.write_text(json.dumps({'mode':'sandbox-only','context':self.context}),encoding='utf-8')
        self.fake=CliDouble()
        patchers=[
            patch.object(s,'STATE',self.root/'outside_state'),
            patch.object(s,'REPO_ROOT',self.root/'repo'),
            patch.object(s,'POLICY_PATH',self.policy),
            patch.object(s,'git_state',return_value='a'*40),
            patch.object(s,'run_tests',return_value=23),
            patch.dict(os.environ,{'FLAGSMITH_ENVIRONMENT':'MY_SDK_KEY'}),
            patch.object(s,'cli',self.fake),
        ]
        for p in patchers:p.start();self.addCleanup(p.stop)
        self.argv=['--project','123','--environment-name','sandbox','--flag','demo_release']

    def act(self,action): return s.main([action,*self.argv])
    def plan(self):
        self.assertEqual(self.act('plan'),0)
        return json.loads((s.STATE/'plan.json').read_text(encoding='utf-8'))

    def test_01_expiry_during_human_confirmation_denied_without_enable(self):
        self.plan()
        normal=s.datetime
        class Late(normal):
            @classmethod
            def now(cls,tz=None):return normal.now(tz)+timedelta(minutes=11)
        with patch.object(s,'human_confirm', side_effect=lambda _:clock.start()):
            clock=patch.object(s,'datetime',Late)
            try:self.assertEqual(self.act('apply'),2)
            finally:clock.stop()
        self.assertFalse(any('enable' in x for x in self.fake.calls))

    def test_02_clean_head_changed_during_human_confirmation_denied(self):
        self.plan()
        def advance(_): sha_patch.start()
        sha_patch=patch.object(s,'git_state',return_value='b'*40)
        with patch.object(s,'human_confirm',side_effect=advance):
            try:self.assertEqual(self.act('apply'),2)
            finally:sha_patch.stop()
        self.assertFalse(any('enable' in x for x in self.fake.calls))

    def test_03_clean_head_changed_after_enable_triggers_emergency_rollback(self):
        self.plan()
        self.fake.operator_confirmed=True
        count={'n':0}
        def sha_switch(**_):
            count['n']+=1
            return 'b'*40 if count['n']>=3 else 'a'*40
        with patch.object(s,'git_state',side_effect=sha_switch),patch.object(s,'human_confirm',return_value=None):
            self.assertEqual(self.act('apply'),2)
        self.assertGreaterEqual(count['n'],3)
        self.assertFalse(self.fake.enabled)
        self.assertIn('EMERGENCY_ROLLBACK_VERIFIED',(s.STATE/'evidence.jsonl').read_text())

    def test_04_reused_nonce_refused_before_operator_prompt(self):
        plan=self.plan()
        (s.STATE/('used-'+plan['nonce'])).touch()
        with patch.object(s,'human_confirm') as confirm:
            self.assertEqual(self.act('apply'),2)
            confirm.assert_not_called()
        self.assertFalse(any('enable' in x for x in self.fake.calls))

    def test_05_forged_ttl_over_ten_minutes_denied(self):
        plan=self.plan()
        plan['expires_utc']=(datetime.fromisoformat(plan['created_utc'])+timedelta(minutes=20)).isoformat()
        (s.STATE/'plan.json').write_text(json.dumps(plan))
        with patch.object(s,'human_confirm') as confirm:
            self.assertEqual(self.act('apply'),2)
            confirm.assert_not_called()

    def test_06_naive_timestamp_and_malformed_json_fail_closed(self):
        plan=self.plan()
        for value in ('2030-01-01T00:00:00','not-a-date',None):
            with self.subTest(value=value):
                corrupt={**plan,'expires_utc':value}
                (s.STATE/'plan.json').write_text(json.dumps(corrupt))
                self.assertEqual(self.act('apply'),2)
        (s.STATE/'plan.json').write_text('{broken json')
        self.assertEqual(self.act('apply'),2)

    def test_07_keyboard_interrupt_on_operator_confirm_is_safe(self):
        self.plan()
        with patch.object(s,'human_confirm',side_effect=KeyboardInterrupt):
            self.assertEqual(self.act('apply'),2)
        self.assertFalse(self.fake.enabled)

    def test_08_substrings_ban_production_like_names(self):
        for name in ['dev-prod1','test-produccion','megalab-prd','demo-production2','prod','client1']:
            with self.subTest(name=name),self.assertRaises(s.Blocked):
                s.check_identifier(name,'environment')
        self.assertEqual(s.check_identifier('Development','environment'),'Development')

    def test_09_sdk_key_with_trailing_spaces_denied(self):
        with patch.dict(os.environ, {'FLAGSMITH_ENVIRONMENT':'MY_SDK_KEY '}):
            self.assertEqual(self.act('inspect'),2)
        self.assertFalse(any('flag' in x and 'enable' in x for x in self.fake.calls))

    def test_10_cli_pins_flagsmith_cloud_api_url(self):
        with patch.object(s,'cli',CLI_ORIGINAL),patch.object(s.shutil,'which',return_value='flagsmith'),patch.object(s,'run_command',return_value='flagsmith v2.0.0') as runner:
            self.assertEqual(s.cli(['--version']),'flagsmith v2.0.0')
        argv=runner.call_args.args[0]
        self.assertEqual(argv[:3],['flagsmith','--api-url','https://api.flagsmith.com'])

    def test_11_mismatched_api_status_rejected(self):
        def cli_bad(args):
            if args==['--version']: return 'flagsmith v2.0.0'
            if args==['--no-input','--json','auth','status']:
                return json.dumps({'credentialSource':'keychain','apiUrl':'https://attacker.invalid'})
            raise AssertionError('Unexpected CLI args: '+str(args))
        with patch.object(s,'cli',side_effect=cli_bad):
            self.assertEqual(self.act('inspect'),2)

    def test_12_spoofed_stdout_cannot_claim_tests_ran(self):
        mocked=subprocess.CompletedProcess(args=[],returncode=0,
                    stdout='Ran 23 tests in 0.01s\n\nOK\n',stderr='')
        from test_sentinel import RUN_TESTS_ORIGINAL
        with patch.object(s.subprocess,'run',return_value=mocked):
            with self.assertRaisesRegex(s.Blocked,'Tests failed'):
                RUN_TESTS_ORIGINAL()

    def test_13_external_state_location_by_default(self):
        # Read the source declaration: patched fixtures intentionally override STATE.
        source=Path(s.__file__).read_text(encoding='utf-8')
        self.assertIn("STATE = POLICY_PATH.parent / 'state'",source)


if __name__ == '__main__':unittest.main()
