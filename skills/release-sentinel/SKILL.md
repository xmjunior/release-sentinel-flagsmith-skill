---
name: release-sentinel
description: Safely inspect, test, approve and revert a Flagsmith v2 boolean feature flag in an explicitly authorized sandbox. Use when an AI coding agent proposes a feature-flag change and needs human-gated enable, verified readback, emergency rollback and redacted evidence.
compatibility: Python 3.10+, Git, Flagsmith CLI v2, operator-owned test-only project, interactive human terminal; network needed only for CLI to Flagsmith Cloud. No production automation.
---
# Release Sentinel — Human-gated Flagsmith CLI skill

Use this skill when an agent needs to **inspect → plan → approve → enable → verify → rollback → verify** a boolean flag in a **dedicated test environment**. The human, not the coding agent, owns approval and credentials.

1. **Scope read-only.** Ask the operator to supply a *nonsecret* numeric project ID, actual environment name and flag name (plus optional numeric organisation ID). Verify that the human has privately authenticated the official Flagsmith CLI v2 and holds the SDK environment key in their own trusted shell. Never request the SDK/Admin key in chat, prompts, PRs or logs.
2. **Enroll (human-only).** In a clean Git checkout, the operator runs `scripts/sentinel.py enroll` with explicit `--project` and `--environment-name` (and optional `--organisation`). The executor isolates `flagsmith` in a temporary directory, pins `https://api.flagsmith.com`, strips inherited `FLAGSMITH_*` context overrides (preserving only `FLAGSMITH_ENVIRONMENT` and `FLAGSMITH_API_KEY`) and validates SemVer v2 CLI versions. The operator types the complete one-time sandbox challenge in their own terminal; enrollment stores a pinned allowlist **outside Git** at `~/.release-sentinel/sandbox.json`.
3. **Inspect.** Execute `inspect` for the exact scoped flag. Production-like project/environment names are rejected, while legitimate feature flag names (e.g. `product_search`, `live_chat`) are permitted inside an enrolled test sandbox. If the flag is already enabled, do not create an enable plan.
4. **Plan.** Execute `plan`. The fixed Python standard-library regression suite (55 tests) runs in a secret-scrubbed subprocess and must pass with structured test counts >0, the Git worktree must be clean, the original flag must be OFF, and a Git-commit/SDK-fingerprint-scoped **single-use** nonce expires in 10 minutes. No arbitrary test command can be supplied by the agent.
5. **Enable: HAND OFF TO HUMAN.** The coding agent MUST NOT type, forge, copy or automatically approve the challenge. The human reviews the full scope and types it in a trusted interactive TTY. Immediately after confirmation, the executor revalidates the 10-minute TTL, `~/.release-sentinel/sandbox.json` allowlist, clean Git SHA, live OFF flag state and active `plan.json` nonce before consuming the nonce and running `flag enable --yes`, then verifies live ON readback and Git stability. If enable times out, fails verification, drifts in Git or is interrupted, the executor attempts an emergency disable for that same scope and verifies OFF; even on a second interrupt it records `EMERGENCY_ROLLBACK_UNVERIFIED` and never reports PASS unless OFF is proven.
6. **Rollback: HAND OFF TO HUMAN.** The operator runs `rollback` and separately approves a fresh disable challenge (allowed even with a dirty worktree), after which the executor revalidates the allowlist, disables the flag and verifies live OFF readback.
7. **Report:** Git SHA; test count; sandbox project/environment/flag (no keys); initial OFF, live ON, final OFF; any blocked or unverified steps; and explicit declaration of any unmeasured metric (such as token usage). Read the operator-oriented [`README.md`](README.md) before running. Redacted logs and plans remain outside Git.

### Limits / safe behavior
- **Production is unsupported.** Context checks reject production-like project/environment labels, but do not replace provider-side RBAC. Do not use privileged production credentials.
- **No progressive rollout, canary, metric monitoring or automatic shipment.** `flag enable` affects the default value for one test environment. Never call it a percentage rollout.
- **No autonomous confirmations, no cloud writes without a human**, no paid APIs and no production deployments.
- A terminal approval is not cryptographically strong if an untrusted agent controls that terminal. Keep the operator terminal and keys outside agent control.

Detailed usage: [`README.md`](README.md). Executable: `scripts/sentinel.py`. The Agent Skills format is defined at https://agentskills.io/specification.
