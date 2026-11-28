# Submission fields — Toggle Wars 2026 (Track 04)

**Title:** Release Sentinel — Human-Gated Flagsmith CLI Agent Skill

**Track:** 04 — Flagsmith Agent Skills

**Tagline:** A coding agent can plan a Flagsmith feature flag change, but cannot approve its own risky action; the operator can verify and roll back the exact flag safely.

**Description:** Release Sentinel packages an Agent Skill following the Agent Skills specification (MIT licensed). Its workflow uses Flagsmith CLI v2 inside an isolated temporary directory (pinning `https://api.flagsmith.com`, stripping inherited `FLAGSMITH_*` context overrides, never passing the SDK key on argv, and enforcing SemVer v2) to verify the precise enrolled sandbox project/environment, inspect a Boolean flag, run a fixed 55-test standard-library suite in a secret-scrubbed subprocess, create a one-use 10-minute plan and request human interactive TTY confirmation bound to the organisation, project, environment, flag, Git SHA, SDK-key fingerprint and nonce. Immediately after human confirmation, it revalidates the TTL, allowlist policy, clean Git SHA, live OFF flag state and active plan nonce before enabling the sandbox flag and verifying live ON readback; on timeout, drift or interruption it runs an interrupt-safe emergency disable and logs `EMERGENCY_ROLLBACK_UNVERIFIED` if OFF cannot be proven. A separately approved rollback verifies the final OFF state. We reject production-like project/environment contexts, log only redacted evidence outside Git, and explicitly do not claim progressive rollout, production safety or unmeasured token savings.

**Implementation:** Python 3.10+, Git, Flagsmith CLI v2, standard-library `unittest` (55 regressions), `skills/release-sentinel/SKILL.md`, MIT License.

**Verification:** 55/55 local mocked tests PASS + offline Flagsmith CLI v2.0.0 isolation verification. Real Windows Flagsmith CLI v2.0.0 E2E verified on 28 Nov 2026 against Flagsmith Cloud on commit `f993328353f580608d1fd77598cb820f4c7bd5e5`: initial OFF readback → `PLAN PASS` (55 tests) → human confirmation #1 → `ENABLE_VERIFIED` + live ON readback → human confirmation #2 → `ROLLBACK_VERIFIED` + live OFF readback. Public evidence omits secrets and private IDs; agent token savings are NOT MEASURED.

**Repo URL:** https://github.com/xmjunior/release-sentinel-flagsmith-skill

**Demo URL:** https://github.com/xmjunior/release-sentinel-flagsmith-skill/blob/main/docs/RELEASE_SENTINEL_DEMO.mp4

**Video provenance:** 85-second captioned visual recap using real redacted terminal excerpts and local test results (recorded on the baseline 36-test release; workflow unchanged, hardened release expands coverage to 55/55 tests); this is not a continuous live screencast.

**Documentation:** README.md, skills/release-sentinel/SKILL.md, skills/release-sentinel/README.md, docs/E2E_EVIDENCE.md
