# Release Sentinel — Human-Gated Flagsmith CLI Agent Skill

**Toggle Wars 2026 · Track 04: Flagsmith Agent Skills**

Release Sentinel gives coding agents a reproducible path to propose a **test-only** Boolean feature flag change **without being allowed to authorize it**. It combines Flagsmith CLI v2, pinned sandbox identity, deterministic regression tests, one-use 10-minute plans, verified rollback and redacted evidence.

## How it works

```text
Agent reads SKILL.md
         |
Human enrolls private sandbox scope once
         |
Inspect OFF  -->  Fixed regression suite  -->  One-use 10-minute plan
         |
Human approves exact ENABLE challenge in trusted terminal
         |
Flagsmith v2 enables flag  -->  Verify ON readback
         |
Human approves separate DISABLE challenge
         |
Flagsmith v2 disables flag  -->  Verify OFF readback
```

## Why this is different from an unsafe CLI wrapper

- **No self-approval:** human-only TTY challenges bind the Git SHA, environment, flag, SDK-key fingerprint and nonce.
- **No cross-environment writes:** explicit project and environment checks with a human-enrolled local allowlist; production-like contexts rejected.
- **No imaginary tests:** fixed Python `unittest` suite, counted through structured test results and checked before each plan.
- **Rollback with evidence:** live Flagsmith CLI readback, recovery attempt on uncertain enable, no false PASS if OFF cannot be proven.
- **Fail closed:** stale plan, dirty Git, wrong SDK key, nonce reuse or ambiguous live state blocks the operation.

## Agent Skill layout

```text
skills/release-sentinel/
    SKILL.md                  # Agent Skills contract — read first
    README.md                 # Operator instructions / limitations
    scripts/sentinel.py       # Exact reviewed Flagsmith v2 executor
    tests/test_*.py           # Deterministic mocked adversarial tests
```

Agent Skills spec: https://agentskills.io/specification

## Run the 36 local tests

Requirements: Python 3.10+, Git, Flagsmith CLI v2 for **live** runs; local unit tests require Python only.

```bash
python -B -m unittest discover -s skills/release-sentinel/tests -p 'test_*.py' -v
```

For a real run in **your own dedicated test sandbox**, follow [the operator guide](skills/release-sentinel/README.md) and keep all credentials in the operator's private terminal. The agent must not type the approval challenge.

## Evidence — what is known and what is not

- **36/36 mocked local regressions PASS** on the independently packaged release. The tests are not Cloud verification.
- On 27 November 2026, the operator supplied a real Windows terminal capture reporting `INSPECT PASS` (OFF), `PLAN PASS` (36), `SANDBOX ENABLE VERIFIED` (ON), `SANDBOX ROLLBACK VERIFIED` (OFF) and a final **OFF → ON → OFF PASS** in a nonproduction Flagsmith Cloud environment. This is **operator-observed terminal evidence**, not independent organizer acceptance.
- **Not claimed:** official competition submission, prize, automatic production rollout, published token counts or verified token efficiency. The included edited demo video contains authentic redacted operator screenshots, but is not a continuous live screencast. A full live screencast would strengthen the entry.

## Demo video (85 seconds)

[Watch the short demo video](docs/RELEASE_SENTINEL_DEMO.mp4). It combines the real 36-test local run, workflow explanation, and **redacted operator-supplied Flagsmith CLI terminal excerpts** of the authorized test-only OFF → ON → OFF cycle. It is a captioned visual recap, **not a continuous live screencast**, and contains no keys or private project identifiers. No official scoring or measured token savings is claimed.

## Security and scope

This skill intentionally supports **only test-environment default Boolean enable/disable**. It does not implement percentage rollout, health monitoring, staged canary or production access. It is not a production deployment platform; a compromised operator terminal can defeat TTY approval. Use least-privilege Flagsmith credentials.

## Hackathon submission

Track 04 requires a **public GitHub repository**, README with setup and Flagsmith usage, and a short **working demo video**. The public repo includes a link to a captioned 85-second demo recap video and the source. A continuous live screencast would strengthen the submission; the video is not an official score. Official rules: https://www.wemakedevs.org/hackathons/flagsmith/rules. Competition deadline: **29 November 2026 20:00 IST (11:30 BRT)**.

The skill is self-contained; no source files or private repository are needed to run its unit tests.
