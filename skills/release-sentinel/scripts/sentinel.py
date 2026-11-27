#!/usr/bin/env python3
"""Release Sentinel: sandbox-only Flagsmith v2 toggle with operator-bound, single-use approvals.

No automatic production operation, percentage rollout, or health-based automatic rollback.
No agent self-approval; interactive actions must be performed by the human operator.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
POLICY_PATH = Path.home() / '.release-sentinel' / 'sandbox.json'
# A repository checkout (even ignored paths) is NOT a safe home for approvals/nonces.
STATE = POLICY_PATH.parent / 'state'
SAFE = re.compile(r'^[A-Za-z][A-Za-z0-9_. -]{0,79}$')
DENIED_NAMES = re.compile(r'(?:prod|produccion|prd|live|customer|client)', re.I)
SAFE_CONTEXT = re.compile(r'^(test|qa|dev|desarrollo|sandbox|demo|staging|megalab)', re.I)


class Blocked(Exception):
    """A safety gate refused the requested operation."""


def sha(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_command(argv: list[str], *, timeout: int = 30, cwd: Path | None = None) -> str:
    """No shell; no command output is copied into error logs."""
    try:
        r = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout,
                           check=False)
    except subprocess.TimeoutExpired as exc:
        raise Blocked('Command timed out; effect may be unknown') from None
    except (OSError, ValueError) as exc:
        raise Blocked('Unable to start required command') from None
    if r.returncode != 0:
        raise Blocked(f'Required command failed (exit {r.returncode})')
    return r.stdout.strip()


def cli(args: list[str]) -> str:
    executable = shutil.which('flagsmith')
    if not executable:
        raise Blocked('Flagsmith CLI v2 not found; install it locally in the sandbox operator environment')
    # On Windows Python may delegate npm .cmd to cmd.exe even with shell=False.
    # All arguments supplied to the .cmd are fixed/sanitised; SDK key is only in env.
    # Pin the official management API: an inherited FLAGSMITH_API_URL must not
    # silently redirect authenticated reads or writes to an arbitrary host.
    return run_command([executable, '--api-url', 'https://api.flagsmith.com', *args], timeout=35)


def cli_json(args: list[str]) -> dict:
    raw = cli(['--no-input', '--json', *args])
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        raise Blocked('Flagsmith CLI returned non-JSON output') from None
    if not isinstance(data, dict):
        raise Blocked('Unexpected Flagsmith JSON structure')
    return data


def check_identifier(value: str, label: str) -> str:
    if not SAFE.fullmatch(value):
        raise Blocked(f'Invalid {label} name')
    if DENIED_NAMES.search(value):
        raise Blocked(f'Production-like {label} name forbidden')
    return value


def require_test_context(project: dict, environment: dict, project_id: int, name: str, key: str) -> dict:
    if type(project.get('id')) is not int or project['id'] != project_id:
        raise Blocked('Project ID does not match requested sandbox project')
    if type(environment.get('project')) is not int or environment['project'] != project_id:
        raise Blocked('Environment belongs to another project')
    if environment.get('name') != name or environment.get('api_key') != key:
        raise Blocked('Environment name/SDK key does not match the authenticated context')
    env_id = environment.get('id')
    if type(env_id) is not int or env_id <= 0:
        raise Blocked('Environment ID missing from Flagsmith metadata')
    project_name = check_identifier(str(project.get('name', '')), 'project')
    env_name = check_identifier(name, 'environment')
    # Name checks are defense-in-depth, NOT the sandbox authority.
    if not SAFE_CONTEXT.match(project_name) or not SAFE_CONTEXT.match(env_name):
        raise Blocked('Only clearly labelled test/sandbox projects and environments are supported')
    return {'project_id': project_id, 'project_name': project_name,
            'environment_id': env_id, 'environment_name': env_name, 'environment_key_sha256': sha(key)}


def cli_scope(args: argparse.Namespace) -> list[str]:
    """Explicit scope for every CLI read/write; project ID is not organisation ID."""
    scope = []
    org = getattr(args, 'organisation', None)
    if org is not None:
        if type(org) is not int or org <= 0:
            raise Blocked('Organisation must be a positive numeric ID')
        scope.extend(['--organisation', str(org)])
    scope.extend(['--project', str(args.project)])
    return scope


def preflight(args: argparse.Namespace) -> tuple[dict, str]:
    key = os.environ.get('FLAGSMITH_ENVIRONMENT', '')
    if not key or key != key.strip() or any(c.isspace() for c in key):
        raise Blocked('FLAGSMITH_ENVIRONMENT SDK key must be set privately in the operator terminal')
    # Do not print or log CLI responses: auth status can contain identity details.
    version = cli(['--version'])
    if not re.search(r'(?i)(^|\W)v?2\.[0-9]+', version):
        raise Blocked('Flagsmith CLI v2 is required')
    status = cli_json(['auth', 'status'])
    if not status.get('credentialSource'):
        raise Blocked('Admin API authentication missing; SDK key alone is insufficient')
    advertised_api = status.get('apiUrl') or status.get('api_url')
    if advertised_api is not None and advertised_api.rstrip('/') != 'https://api.flagsmith.com':
        raise Blocked('Management API host is not the approved Flagsmith Cloud instance')
    scope = cli_scope(args)
    project = cli_json([*scope, 'project', 'get', str(args.project)])
    org = getattr(args, 'organisation', None)
    if org is not None and (type(project.get('organisation')) is not int or project['organisation'] != org):
        raise Blocked('Project does not belong to the approved organisation')
    env = cli_json([*scope, 'environment', 'get', args.environment_name])
    context = require_test_context(project, env, args.project, args.environment_name, key)
    if org is not None:
        context['organisation_id'] = org
    return context, version[:80]


def load_policy(context: dict) -> None:
    if not POLICY_PATH.is_file() or POLICY_PATH.resolve().is_relative_to(REPO_ROOT.resolve()):
        raise Blocked('Operator sandbox allowlist missing outside repository; run enroll interactively')
    try:
        policy = json.loads(POLICY_PATH.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        raise Blocked('Cannot read operator sandbox allowlist') from None
    if policy.get('mode') != 'sandbox-only' or policy.get('context') != context:
        raise Blocked('Live context is not in the operator-approved sandbox allowlist')


def operator_scope(context: dict) -> str:
    """Display the exact organisation in each human confirmation when supplied."""
    return f"ORG{context['organisation_id']}/" if 'organisation_id' in context else ''


def human_confirm(challenge: str) -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise Blocked('Real operator must authorize in an interactive terminal; agent/pipe cannot approve')
    print('OPERATOR REVIEW: Verify this is an isolated sandbox; never approve production.')
    print('Type the ENTIRE one-time scope exactly, otherwise the operation is blocked:')
    print(challenge)
    try:
        typed = input('> ').strip()
    except (EOFError, KeyboardInterrupt):
        raise Blocked('Operator declined') from None
    if not secrets.compare_digest(typed, challenge):
        raise Blocked('Human approval absent or incorrect')


def evidence(event: str, **fields) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt': STATE.chmod(0o700)
    # No API credentials, raw responses or SDK keys are logged.
    with (STATE / 'evidence.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps({'utc': stamp(), 'event': event, **fields}, sort_keys=True) + '\n')


def git_state(require_clean: bool = True) -> str:
    rev = run_command(['git', '-C', str(REPO_ROOT), 'rev-parse', 'HEAD'])
    if not re.fullmatch(r'[0-9a-f]{40}', rev):
        raise Blocked('Cannot identify Git HEAD')
    if require_clean:
        changes = run_command(['git', '-C', str(REPO_ROOT), 'status', '--porcelain'])
        if changes:
            raise Blocked('Git worktree is dirty; plan/apply blocked')
    return rev


def get_state(args: argparse.Namespace) -> bool:
    data = cli_json([*cli_scope(args), 'flag', 'get', args.flag])
    if data.get('feature') != args.flag or type(data.get('enabled')) is not bool:
        raise Blocked('Flag JSON does not contain the expected feature and boolean enabled state')
    return data['enabled']


def run_tests() -> int:
    """Count *actual* unittest result objects, never a spoofable stdout 'Ran N'."""
    marker = '__RELEASE_SENTINEL_RESULT_' + secrets.token_hex(12) + '__'
    # An isolated interpreter executes only the fixed, checked-in unittest suite.
    # The final JSON comes from TextTestRunner's structured result.testsRun.
    harness = ("import json,sys,unittest\n"
               "suite=unittest.defaultTestLoader.discover(sys.argv[1], pattern='test_*.py')\n"
               "result=unittest.TextTestRunner(verbosity=2).run(suite)\n"
               f"print({marker!r}+json.dumps({{'testsRun': result.testsRun, 'ok': result.wasSuccessful()}}))\n"
               "sys.exit(0 if result.wasSuccessful() and result.testsRun>0 else 2)\n")
    command = [sys.executable, '-B', '-c', harness, str(SKILL_ROOT / 'tests')]
    try:
        proc = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True,
                              timeout=70, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Blocked('Trusted test runner failed or timed out') from None
    lines = proc.stdout.splitlines()
    try:
        if proc.returncode != 0 or not lines or not lines[-1].startswith(marker):
            raise ValueError('missing trusted result')
        result = json.loads(lines[-1][len(marker):])
        count = result['testsRun']
        if result.get('ok') is not True or type(count) is not int or count < 1:
            raise ValueError('no successful tests')
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise Blocked('Tests failed, were not counted, or ran zero test cases') from None
    return count


def create_plan(args: argparse.Namespace, context: dict, version: str) -> dict:
    rev = git_state(require_clean=True)
    before = get_state(args)
    if before:
        raise Blocked('Flag already enabled; refusing to plan an unknown existing state')
    n = run_tests()
    after_tests = git_state(require_clean=True)
    if after_tests != rev: raise Blocked('Git HEAD changed during test preflight')
    now = datetime.now(timezone.utc)
    plan = {'nonce': secrets.token_hex(12), 'created_utc': now.isoformat(),
            'expires_utc': (now + timedelta(minutes=10)).isoformat(),
            'operation': 'enable', 'flag': args.flag, 'context': context,
            'git_sha': rev, 'flag_before': before, 'tests_passed': n, 'cli_version': version}
    STATE.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt': STATE.chmod(0o700)
    path = STATE / 'plan.json'
    path.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding='utf-8')
    evidence('PLAN_READY', flag=args.flag, project=context['project_id'],
             environment=context['environment_name'], rev=rev, tests=n, nonce=plan['nonce'])
    return plan


def plan_still_valid(plan: dict) -> None:
    """Check UTC expiry and ten-minute TTL, including after human interaction."""
    try:
        created = datetime.fromisoformat(plan['created_utc'])
        expiry = datetime.fromisoformat(plan['expires_utc'])
        now = datetime.now(timezone.utc)
    except (KeyError, ValueError, TypeError, OverflowError):
        raise Blocked('Missing, expired or malformed operator plan') from None
    if created.tzinfo is None or expiry.tzinfo is None:
        raise Blocked('Operator plan must use timezone-aware timestamps')
    if created > now or expiry <= now or expiry <= created or expiry - created > timedelta(minutes=10):
        raise Blocked('Operator plan expired or has an invalid ten-minute TTL')


def load_plan(args: argparse.Namespace, context: dict, version: str) -> dict:
    path = STATE / 'plan.json'
    try:
        p = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(p, dict): raise ValueError('operator plan must be an object')
    except (OSError, ValueError, TypeError):
        raise Blocked('Missing, expired or malformed operator plan') from None
    plan_still_valid(p)
    if p.get('operation') != 'enable':
        raise Blocked('Operator plan has wrong operation')
    if p.get('context') != context or p.get('flag') != args.flag or p.get('cli_version') != version:
        raise Blocked('Operator plan does not match live Flagsmith context')
    if p.get('flag_before') is not False or type(p.get('tests_passed')) is not int or p['tests_passed'] < 1:
        raise Blocked('Operator plan has no eligible preflight/test result')
    if p.get('git_sha') != git_state(require_clean=True):
        raise Blocked('Git HEAD changed since plan')
    nonce = p.get('nonce', '')
    if not isinstance(nonce, str) or not re.fullmatch(r'[0-9a-f]{24}', nonce):
        raise Blocked('Invalid one-time nonce')
    if (STATE / ('used-' + nonce)).exists():
        raise Blocked('Approval nonce has already been consumed')
    if get_state(args) is not False:
        raise Blocked('Flag state changed after planning')
    return p


def use_once(plan: dict) -> None:
    used = STATE / ('used-' + plan['nonce'])
    try:
        fd = os.open(used, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        (STATE / 'plan.json').unlink()
    except (FileExistsError, FileNotFoundError):
        raise Blocked('Approval nonce has already been consumed') from None


def change(args: argparse.Namespace, enable: bool) -> None:
    cli([*cli_scope(args), '--no-input', '--yes',
         'flag', 'enable' if enable else 'disable', args.flag])


def verify_state(args: argparse.Namespace, enabled: bool) -> None:
    if get_state(args) is not enabled:
        raise Blocked('Post-write flag state verification failed')


def emergency_disable(args: argparse.Namespace, context: dict, reason: str) -> bool:
    # Authorized as part of the same human-approved ENABLE operation, for its exact scope.
    try:
        change(args, enable=False)
        verify_state(args, enabled=False)
    except Exception:
        evidence('EMERGENCY_ROLLBACK_UNVERIFIED', flag=args.flag, project=context['project_id'], reason=reason)
        return False
    evidence('EMERGENCY_ROLLBACK_VERIFIED', flag=args.flag, project=context['project_id'], reason=reason)
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Flagsmith v2 sandbox-only deterministic release skill')
    parser.add_argument('action', choices=('enroll', 'inspect', 'plan', 'apply', 'rollback'))
    parser.add_argument('--project', type=int, required=True)
    parser.add_argument('--organisation', type=int, help='Explicit organisation ID; distinct from project ID')
    parser.add_argument('--environment-name', required=True)
    parser.add_argument('--flag')
    args = parser.parse_args(argv)
    try:
        if args.project <= 0:
            raise Blocked('Project must be a positive numeric ID')
        check_identifier(args.environment_name, 'environment')
        if args.action != 'enroll' and not args.flag:
            raise Blocked('--flag is required for this action')
        if args.flag:
            check_identifier(args.flag, 'flag')
        context, version = preflight(args)
        if args.action == 'enroll':
            challenge = (f'ENROLL {operator_scope(context)}SANDBOX P{args.project}/E{context["environment_id"]}'
                         f'/{context["environment_name"]} SHA{context["environment_key_sha256"][:12]}')
            human_confirm(challenge)
            if POLICY_PATH.resolve().is_relative_to(REPO_ROOT.resolve()):
                raise Blocked('Operator sandbox policy cannot live inside code repository')
            POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
            POLICY_PATH.write_text(json.dumps({'mode':'sandbox-only','context':context}, indent=2), encoding='utf-8')
            if os.name != 'nt':
                POLICY_PATH.chmod(0o600)
            print('Sandbox context enrolled. No feature was modified.')
            return 0
        load_policy(context)
        if args.action == 'inspect':
            enabled = get_state(args)
            print(json.dumps({'flag': args.flag, 'enabled': enabled,
                              'project': args.project, 'environment': args.environment_name}))
            return 0
        if args.action == 'plan':
            plan = create_plan(args, context, version)
            print(f'PLAN PASS: {plan["tests_passed"]} local tests; nonce {plan["nonce"]}; expires in 10 minutes.')
            return 0
        if args.action == 'apply':
            plan = load_plan(args, context, version)
            challenge = (f'ENABLE {operator_scope(context)}P{args.project}/E{context["environment_id"]}/{context["environment_name"]}'
                         f'/{args.flag} SHA{plan["git_sha"][:12]} KEY{context["environment_key_sha256"][:12]}'
                         f' NONCE{plan["nonce"]}')
            human_confirm(challenge)
            # Approval may take longer than ten minutes; no stale approval is valid.
            plan_still_valid(plan)
            if git_state(require_clean=True) != plan['git_sha']:
                raise Blocked('Git HEAD changed during human approval')
            use_once(plan)
            evidence('ENABLE_ATTEMPT', flag=args.flag, project=args.project, nonce=plan['nonce'])
            try:
                change(args, enable=True)
                verify_state(args, enabled=True)
                if git_state(require_clean=True) != plan['git_sha']:
                    raise Blocked('Git HEAD changed after flag enable')
            except (Exception, KeyboardInterrupt):
                ok = emergency_disable(args, context, 'enable_timeout_verify_or_git_failure')
                raise Blocked('Enable failed/uncertain; emergency rollback ' + ('VERIFIED' if ok else 'NOT VERIFIED')) from None
            evidence('ENABLE_VERIFIED', flag=args.flag, project=args.project, nonce=plan['nonce'])
            print('SANDBOX ENABLE VERIFIED. No percentage rollout was performed.')
            return 0
        if args.action == 'rollback':
            # Deliberately do not require a clean tree. A dirty worktree cannot block recovery.
            before = get_state(args)
            if not before:
                evidence('ROLLBACK_NOOP_DISABLED', flag=args.flag, project=args.project)
                print('ALREADY DISABLED: live readback verified.')
                return 0
            nonce = secrets.token_hex(12)
            rev = git_state(require_clean=False)
            challenge = (f'DISABLE {operator_scope(context)}P{args.project}/E{context["environment_id"]}/{context["environment_name"]}'
                         f'/{args.flag} SHA{rev[:12]} KEY{context["environment_key_sha256"][:12]}'
                         f' NONCE{nonce}')
            human_confirm(challenge)
            evidence('ROLLBACK_ATTEMPT', flag=args.flag, project=args.project, nonce=nonce)
            change(args, enable=False)
            verify_state(args, enabled=False)
            evidence('ROLLBACK_VERIFIED', flag=args.flag, project=args.project, nonce=nonce)
            print('SANDBOX ROLLBACK VERIFIED.')
            return 0
        raise Blocked('Unknown action')
    except (Blocked, KeyboardInterrupt) as exc:
        # All Blocked messages are constants without user secrets or command output.
        message = str(exc) if isinstance(exc, Blocked) else 'Operator interrupted the operation'
        evidence('BLOCKED', action=args.action, reason=message)
        print('BLOCKED: ' + message, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
