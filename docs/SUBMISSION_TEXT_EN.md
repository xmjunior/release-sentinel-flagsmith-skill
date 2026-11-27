# Suggested submission fields (after PUBLIC repo + DEMO video exist)

**Title:** Release Sentinel — Human-Gated Flagsmith CLI Agent Skill

**Track:** 04 — Flagsmith Agent Skills

**Tagline:** A coding agent can plan a Flagsmith feature flag change, but cannot approve its own risky action; the operator can verify and roll back the exact flag safely.

**Description:** Release Sentinel packages an Agent Skill following the Agent Skills specification. Its workflow uses Flagsmith CLI v2 to verify the precise sandbox project/environment, inspect a Boolean flag, run a fixed standard-library test suite, create a one-use ten-minute plan and request a human confirmation bound to the project, environment, flag, Git SHA, SDK-key fingerprint and nonce. Only the human-controlled executor can enable the sandbox flag; the CLI verifies the live result, and a separately approved rollback verifies the final OFF state. We explicitly reject production-like contexts and log only redacted evidence. We do not claim progressive rollout or production safety.

**Implementation:** Python 3.10+, Flagsmith CLI v2, Git, standard-library unittests, `skills/release-sentinel/SKILL.md`.

**Verification:** 36/36 local simulated tests PASS. Owner-provided real Windows Flagsmith CLI v2 terminal evidence from 27 Nov 2026 reports test-only OFF → ON → OFF, with both approvals and readbacks. Public evidence excludes secrets; no official scoring or measured agent token savings is claimed.

**Repo URL:** https://github.com/xmjunior/release-sentinel-flagsmith-skill

**Demo URL:** https://github.com/xmjunior/release-sentinel-flagsmith-skill/blob/main/docs/RELEASE_SENTINEL_DEMO.mp4

**Video provenance:** 85-second captioned visual recap using real redacted terminal excerpts and local test results; this is not a continuous live screencast.

**Documentation:** README.md and skills/release-sentinel/README.md
