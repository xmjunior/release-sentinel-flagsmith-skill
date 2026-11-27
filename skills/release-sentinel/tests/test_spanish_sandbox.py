"""New 27 Nov sandbox compatibility checks against Flagsmith v2's documented JSON contract.
No network, credentials, production or mutation against Flagsmith Cloud.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'sentinel.py'
spec = importlib.util.spec_from_file_location('sentinel_spanish_sandbox', PATH)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

ORG = 42000  # synthetic organisation ID, NEVER a real account
PROJECT = 782345  # dummy project ID, not a real or inferred Flagsmith ID
ENV_ID = 913
SDK = 'DUMMY_SDK_KEY_NOT_REAL'

class SandboxContextTests(unittest.TestCase):
    def args(self, **kwargs):
        return argparse.Namespace(organisation=kwargs.get('organisation', ORG),
                 project=kwargs.get('project', PROJECT),
                 environment_name=kwargs.get('environment_name', 'Desarrollo'),
                 flag=kwargs.get('flag','demo_release'))

    def replies(self, *, organisation=ORG, project=PROJECT, env_name='Desarrollo', sdk_key=SDK):
        calls=[]
        def fake(argv):
            calls.append(list(argv))
            if argv == ['--version']: return 'flagsmith v2.0.0'
            if argv:
                if argv[-2:] == ['auth','status']:
                    return {'credentialSource':'$FLAGSMITH_API_KEY'}
                if argv[-3:-1] == ['project','get']:
                    return {'id':project, 'name':'MEGALAB Sandbox', 'organisation':organisation}
                if argv[-3:-1] == ['environment','get']:
                    return {'id':ENV_ID, 'project':project, 'name':env_name, 'api_key':sdk_key}
                if argv[-3:-1] == ['flag','get']:
                    return {'feature':'demo_release','enabled':False}
            raise AssertionError('Unexpected CLI JSON request: '+str(argv))
        return fake,calls

    def test_spanish_development_name_accepted_only_with_matching_context(self):
        c=s.require_test_context({'id':PROJECT,'name':'MEGALAB Sandbox'},
              {'id':ENV_ID,'project':PROJECT,'name':'Desarrollo','api_key':SDK},
              PROJECT,'Desarrollo',SDK)
        self.assertEqual(c['environment_name'], 'Desarrollo')
        self.assertNotIn(SDK, str(c))

    def test_org_and_project_different_scopes(self):
        a=self.args()
        self.assertEqual(s.cli_scope(a), ['--organisation','42000','--project',str(PROJECT)])
        self.assertNotEqual(a.organisation,a.project)

    def test_preflight_reads_exact_org_project_and_environment(self):
        fake,calls=self.replies()
        with patch.dict(os.environ,{'FLAGSMITH_ENVIRONMENT':SDK}),patch.object(s,'cli', side_effect=lambda a:'flagsmith v2.0.0'),patch.object(s,'cli_json',side_effect=fake):
            scope,ver=s.preflight(self.args())
        self.assertEqual(ver,'flagsmith v2.0.0')
        self.assertEqual(scope['organisation_id'],ORG)
        self.assertEqual(scope['project_id'],PROJECT)
        self.assertEqual(scope['environment_name'],'Desarrollo')
        self.assertEqual(scope['environment_key_sha256'],s.sha(SDK))
        self.assertIn(['--organisation','42000','--project',str(PROJECT),'environment','get','Desarrollo'],calls)

    def test_wrong_organisation_fails_closed(self):
        fake,_=self.replies(organisation=99999)
        with patch.dict(os.environ,{'FLAGSMITH_ENVIRONMENT':SDK}),patch.object(s,'cli',return_value='flagsmith v2.0.0'),patch.object(s,'cli_json',side_effect=fake):
            with self.assertRaisesRegex(s.Blocked,'approved organisation'):
                s.preflight(self.args())

    def test_wrong_sdk_key_fails_closed(self):
        with self.assertRaisesRegex(s.Blocked,'SDK key'):
            s.require_test_context({'id':PROJECT,'name':'MEGALAB Sandbox'},
                 {'id':ENV_ID,'project':PROJECT,'name':'Desarrollo','api_key':'OTHER'},
                  PROJECT,'Desarrollo',SDK)

    def test_production_remains_denied(self):
        with self.assertRaises(s.Blocked):
            s.require_test_context({'id':PROJECT,'name':'MEGALAB Sandbox'},
                 {'id':ENV_ID,'project':PROJECT,'name':'Produccion','api_key':SDK},
                  PROJECT,'Produccion',SDK)

    def test_all_read_write_scopes_include_org_but_no_mutations_without_approval(self):
        calls=[]
        def fake_json(x):
            calls.append(x)
            return {'feature':'demo_release','enabled':False}
        with patch.object(s,'cli_json',side_effect=fake_json):
            self.assertFalse(s.get_state(self.args()))
        self.assertEqual(calls[0], ['--organisation','42000','--project',str(PROJECT),'flag','get','demo_release'])
        with patch.object(s,'cli',side_effect=lambda x: calls.append(x) or ''):
            s.change(self.args(), True)
        self.assertEqual(calls[-1],['--organisation','42000','--project',str(PROJECT),'--no-input','--yes','flag','enable','demo_release'])

    def test_invalid_organisation_rejected(self):
        with self.assertRaises(s.Blocked): s.cli_scope(self.args(organisation=-1))

if __name__ == '__main__': unittest.main()
