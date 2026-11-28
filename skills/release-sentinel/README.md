# Release Sentinel — operator guide

**Version:** Flagsmith CLI v2; Python >=3.10; Git. A **dedicated sandbox** with a Boolean flag is mandatory.

## Safety boundary

- Only explicitly enrolled, clearly labelled **test/sandbox** projects and environments. Never Production. Legitimate flag names (such as `product_search` or `live_chat`) are allowed once the project and environment pass sandbox verification.
- The CLI's management login and SDK environment key are **different credentials**. Browser login via `flagsmith login` is private to the operator. `FLAGSMITH_ENVIRONMENT` is the client-side SDK environment key for the **same** environment and is never passed on argv.
- Every Flagsmith CLI call runs inside an isolated empty temporary directory (with Windows-safe cleanup), pins `--api-url https://api.flagsmith.com`, strips inherited `FLAGSMITH_*` context variables other than `FLAGSMITH_ENVIRONMENT` and `FLAGSMITH_API_KEY`, and strictly verifies a SemVer v2 CLI version.
- The operator must control the terminal; never paste credentials into an AI chat. The operator manually types the exact scope challenge in a real interactive TTY; agent self-approval is forbidden.
- After human confirmation, `apply` revalidates the 10-minute plan TTL, `~/.release-sentinel/sandbox.json` allowlist, clean Git SHA, live OFF state and active `plan.json` nonce before consuming the nonce or mutating Flagsmith; `rollback` likewise revalidates the allowlist after confirmation.
- Enrollment, nonce markers and redacted evidence live in `~/.release-sentinel` outside Git. On a shared machine, secure this directory appropriately. No plan or secret is committed to the repository.
- The implementation **does not perform a canary**, percentage rollout, live health monitoring or production release.

## One-time setup

Install Git, Python 3.10+ and the official Flagsmith CLI v2 using the upstream instructions: https://github.com/Flagsmith/flagsmith-cli

In a **clean standalone clone** of this public repository, run:

```bash
flagsmith --version
flagsmith login
python -B -m unittest discover -s skills/release-sentinel/tests -p 'test_*.py' -v
```

In your **own trusted operator shell**, set `FLAGSMITH_ENVIRONMENT` to the **client-side** SDK key for the target test environment. Example for Windows PowerShell (masked input):

```powershell
$secret = Read-Host 'Test-only client-side SDK key' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try { $env:FLAGSMITH_ENVIRONMENT = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
Remove-Variable secret -ErrorAction SilentlyContinue
```

Choose your own authenticated sandbox IDs and flag. This next example uses **illustrative placeholders**, not actual account IDs. Replace before running.

```powershell
$script = 'skills/release-sentinel/scripts/sentinel.py'
$scope = @('--organisation','<ORG_ID>','--project','<PROJECT_ID>','--environment-name','<TEST_ENVIRONMENT>','--flag','<FLAG_NAME>')
python $script enroll @scope     # local allowlist; approve sandbox scope manually
python $script inspect @scope    # read-only; flag must be OFF
python $script plan @scope       # fixed 55-test suite (secret-scrubbed); 10-minute one-use plan
python $script apply @scope      # human-only approval; post-confirm rechecks; live enable and verify ON
python $script rollback @scope   # fresh human approval; live disable and verify OFF
python $script inspect @scope    # read-only; final OFF
```

**Do not run apply if the flag is already enabled, the context is production-like, the window has expired, the allowlist was revoked, another plan superseded `plan.json`, or the Git SHA changed.** The executor blocks these cases automatically. If enable times out, fails verification, drifts in Git or is interrupted, it attempts a bounded emergency disable and records `EMERGENCY_ROLLBACK_UNVERIFIED` even if interrupted again. If final OFF is not verified, stop and investigate; do not report success.

## What the agent may and may not do

Allowed: read the skill, review context **without credentials**, prepare an operator plan, explain blocked or failed tests, inspect redacted audit summaries.

Not allowed: supply the human approval, access the private operator terminal/keychain, enroll on the human's behalf, run `--yes` independently, change production, claim official contest acceptance or invented token measurements.

## Tests

```bash
python -B -m unittest discover -s skills/release-sentinel/tests -p 'test_*.py' -v
```

The 55-test suite runs in a secret-scrubbed subprocess (`FLAGSMITH_*`, `*_TOKEN`, `*_SECRET`, `*_API_KEY`, `*_PASSWORD` stripped) using mocked CLI responses. It verifies approvals, expirations, post-approval TOCTOU and policy revocation, superseded-plan concurrency, second-interrupt emergency rollback evidence, CLI context isolation, Windows temporary-directory lock handling, SemVer v2 parsing, Git SHA drift, nonce reuse, production labels and invalid responses; it does **not** itself contact Flagsmith Cloud. Live Cloud verification requires an authorized test-only OFF → ON → OFF cycle with real CLI readbacks (documented in `docs/E2E_EVIDENCE.md`).

## Important limitations

- This is a **test-environment Boolean flag switch with rollback**, not a safe general-purpose production rollout controller.
- Interactive approval on a compromised terminal is insufficient protection; provider RBAC and a stronger authorization service are needed for production use.
- Token efficiency is **not measured** by this script and is not claimed.
- The script uses real Git HEAD and clean status. Run from a cloned repo (not a ZIP opened directly, and not inside another project), with a clean worktree and all tests present.
- Never paste raw `environment get --json`, screenshots containing SDK keys, `.release-sentinel` state files, or actual operator approval challenges into a public issue or demo.
