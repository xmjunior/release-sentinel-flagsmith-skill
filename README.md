# Release Sentinel — Human-Gated Flagsmith CLI Agent Skill

**Toggle Wars 2026 · Track 04: Flagsmith Agent Skills**

Release Sentinel gives coding agents a reproducible path to propose a **test-only** Boolean feature flag change **without being allowed to authorize it**. It combines Flagsmith CLI v2, isolated CLI execution, pinned sandbox identity, deterministic regression tests, one-use 10-minute plans, post-approval revalidation, interrupt-safe rollback and redacted evidence.

## How it works

```text
Agent reads SKILL.md
         |
Human enrolls private sandbox scope once (~/.release-sentinel/sandbox.json)
         |
Inspect OFF  -->  Fixed 55-test suite (secret-scrubbed)  -->  One-use 10-minute plan
         |
Human approves exact ENABLE challenge in trusted interactive TTY
         |
Revalidate TTL, allowlist, Git SHA, live OFF state & active plan nonce
         |
Flagsmith v2 enables flag  -->  Verify ON readback (+ Git stability)
         |
Human approves separate DISABLE challenge  -->  Revalidate allowlist
         |
Flagsmith v2 disables flag  -->  Verify OFF readback
```

## Why this is different from an unsafe CLI wrapper

- **No self-approval:** human-only interactive TTY challenges bind the organisation (when supplied), project, environment ID/name, flag, Git SHA, SDK-key fingerprint and one-use nonce.
- **Isolated Flagsmith CLI v2 execution:** runs `flagsmith` in an isolated temporary directory (Windows lock-safe cleanup), pins `--api-url https://api.flagsmith.com`, strips inherited `FLAGSMITH_*` context overrides (preserving only `FLAGSMITH_ENVIRONMENT` and `FLAGSMITH_API_KEY`), never puts the SDK key on argv, and strictly validates SemVer v2 CLI versions.
- **No cross-environment or production writes:** explicit project/environment/SDK-key checks with a human-enrolled allowlist outside Git; production-like project/environment names are rejected while legitimate flag names (e.g. `product_search`, `live_chat`) remain supported inside authorized sandboxes.
- **Post-approval TOCTOU & concurrency hardening:** after human confirmation, `apply` re-checks expiry, allowlist policy, clean Git SHA, live OFF flag state and active `plan.json` nonce before consuming the nonce or mutating Flagsmith.
- **No imaginary tests:** fixed Python standard-library `unittest` suite executed in a secret-scrubbed subprocess and counted via structured `TextTestRunner` results.
- **Interrupt-safe rollback with evidence:** live Flagsmith CLI readback, emergency disable on uncertain enable/timeout/Git drift (recording `EMERGENCY_ROLLBACK_UNVERIFIED` even on a second `KeyboardInterrupt`), and no false PASS if OFF cannot be proven.

## Agent Skill layout

```text
skills/release-sentinel/
    SKILL.md                               # Agent Skills contract — read first
    README.md                              # Operator instructions / limitations
    scripts/sentinel.py                    # Hardened Flagsmith v2 executor
    tests/test_sentinel.py                 # Core P0/P1 safety regressions (15)
    tests/test_spanish_sandbox.py          # Multi-org/project/locale scope tests (8)
    tests/test_audit_regressions.py        # Expiry, Git SHA, API pinning & state tests (13)
    tests/test_coderabbit_regressions.py   # CLI isolation, SemVer v2 & flag-scope tests (11)
    tests/test_omega_regressions.py        # Post-confirm TOCTOU, concurrency, Windows & Ctrl+C tests (8)
```

Agent Skills spec: https://agentskills.io/specification

## Run the 55 local tests

Requirements: Python 3.10+, Git, Flagsmith CLI v2 for **live** runs; local unit tests require Python only.

```bash
python -B -m unittest discover -s skills/release-sentinel/tests -p 'test_*.py' -v
```

For a real run in **your own dedicated test sandbox**, follow [the operator guide](skills/release-sentinel/README.md) and keep all credentials in the operator's private terminal. The agent must not type the approval challenge.

## Evidence — what is verified and what is not measured

- **55/55 mocked local regressions PASS** (`unittest` and structured `sentinel.py` runner) plus offline verification against real Flagsmith CLI `v2.0.0` context isolation. Mocked tests are not Cloud verification.
- **Real Flagsmith Cloud E2E verified (28 November 2026):** full live Windows Flagsmith CLI `v2.0.0` cycle on hardened commit `f993328353f580608d1fd77598cb820f4c7bd5e5` — initial `inspect` OFF → `PLAN PASS` (55 tests) → human confirmation #1 → `ENABLE_VERIFIED` + independent Cloud readback `enabled: true` → human confirmation #2 → `ROLLBACK_VERIFIED` + independent Cloud readback `enabled: false`. See [docs/E2E_EVIDENCE.md](docs/E2E_EVIDENCE.md).
- **Explicitly NOT measured / NOT claimed:** live agent token consumption or token-efficiency savings (**NOT MEASURED**), official organizer acceptance or prize, automatic production rollout, percentage canary or health-based auto-rollback.

## Demo video (85 seconds)

[Watch the short demo video](docs/RELEASE_SENTINEL_DEMO.mp4). It combines local test execution, workflow explanation, and **redacted operator Flagsmith CLI terminal excerpts** of the authorized test-only OFF → ON → OFF cycle. It is a captioned visual recap (recorded on the baseline 36-test release; the workflow is unchanged while the hardened release expands the suite to 55/55 tests and adds the post-approval/CLI/Windows protections documented above), **not a continuous live screencast**, and contains no keys or private identifiers.

## Security, scope and license

This skill intentionally supports **only test-environment default Boolean enable/disable**. It does not implement percentage rollout, health monitoring, staged canary or production access. A compromised operator terminal can defeat TTY approval; use least-privilege Flagsmith credentials.

Licensed under the [MIT License](LICENSE).

## Hackathon submission

Track 04 requires a **public GitHub repository**, README with setup and Flagsmith usage, and a short **working demo video**. Official rules: https://www.wemakedevs.org/hackathons/flagsmith/rules. Competition deadline: **29 November 2026 20:00 IST (11:30 BRT)**.

The skill is self-contained; no private repository is needed to run its 55 unit tests.
