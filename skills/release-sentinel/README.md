# Release Sentinel — operator guide

**Version:** Flagsmith CLI v2; Python >=3.10; Git. A **dedicated sandbox** with a Boolean flag is mandatory.

## Safety boundary

- Only explicitly enrolled, clearly labelled **test/sandbox** projects and environments. Never Production.
- The CLI's management login and SDK environment key are **different credentials**. Browser login via `flagsmith login` is private to the operator. `FLAGSMITH_ENVIRONMENT` is the client-side SDK environment key retrieved for the **same** environment.
- The operator must control the terminal; never paste credentials into an AI chat. The operator manually types the exact scope challenge; agent self-approval is forbidden.
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
python $script plan @scope       # fixed unit test suite; 10-minute one-use plan
python $script apply @scope      # human-only approval; live enable and verify ON
python $script rollback @scope   # fresh human approval; live disable and verify OFF
python $script inspect @scope    # read-only; final OFF
```

**Do not run apply if the flag is already enabled, the context is production-like, the window has expired, or the Git SHA changed.** The code blocks ambiguous or unsafe cases. If enable unexpectedly succeeds but verification fails, the script attempts a bounded emergency disable. If final OFF is not verified, stop and investigate; do not report success.

## What the agent may and may not do

Allowed: read the skill, review context **without credentials**, prepare an operator plan, explain blocked or failed tests, inspect redacted audit summaries.

Not allowed: supply the human approval, access the private operator terminal/keychain, enroll on the human's behalf, run `--yes` independently, change production, claim official contest acceptance or invented token measurements.

## Tests

```bash
python -B -m unittest discover -s skills/release-sentinel/tests -p 'test_*.py' -v
```

The suite uses mocked CLI responses. It verifies approvals, expirations, Git SHA drift, nonce reuse, production labels, rollback and invalid responses; it does **not** itself contact Flagsmith Cloud. To demonstrate real functionality, capture an authorized test-only OFF → ON → OFF cycle with its genuine CLI readbacks.

## Important limitations

- This is a **test-environment Boolean flag switch with rollback**, not a safe general-purpose production rollout controller.
- Interactive approval on a compromised terminal is insufficient protection; provider RBAC and a stronger authorization service are needed for production use.
- The script uses real Git HEAD and clean status. Run from a cloned repo (not a ZIP opened directly, and not inside another project), with a clean worktree and all tests present.
- Never paste raw `environment get --json`, screenshots containing SDK keys, `.release-sentinel` state files, or actual operator approval challenges into a public issue or demo.
