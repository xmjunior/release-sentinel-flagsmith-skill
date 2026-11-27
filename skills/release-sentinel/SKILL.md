---
name: release-sentinel
description: Safely inspect, test, approve and revert a Flagsmith v2 boolean feature flag in an explicitly authorized sandbox. Use when an AI coding agent proposes a feature-flag change and needs human-gated enable, verified readback, emergency rollback and redacted evidence.
compatibility: Python 3.10+, Git, Flagsmith CLI v2, operator-owned test-only project, interactive human terminal; network needed only for CLI to Flagsmith Cloud. No production automation.
---
# Release Sentinel — Human-gated Flagsmith CLI skill

Use this skill when an agent needs to **inspect → plan → approve → enable → verify → rollback → verify** a boolean flag in a **dedicated test environment**. The human, not the coding agent, owns approval and credentials.

1. **Scope read-only.** Ask the operator to supply a *nonsecret* numeric project ID, actual environment name and flag name. Verify that the human has privately authenticated the official Flagsmith CLI v2 and holds the SDK environment key in their own trusted shell. Never request the SDK/Admin key in the chat, prompt, PR or logs.
2. **Enroll (human-only).** In a clean Git checkout, the operator runs `scripts/sentinel.py enroll` with explicit `--project` and `--environment-name` (and optional `--organisation`). The operator types the complete one-time sandbox challenge in their own terminal. Enrollment stores a pinned allowlist **outside Git** at `~/.release-sentinel/sandbox.json`.
3. **Inspect.** The operator executes `inspect` for the exact scoped flag. If the flag is enabled or the project/environment is not clearly a test sandbox, do not create an enable plan.
4. **Plan.** The operator executes `plan`. The fixed Python standard-library regression suite must pass, the working tree must be clean, the original flag must be OFF, and a Git-commit/SDK-fingerprint-scoped **single-use** nonce expires in 10 minutes. No arbitrary test command can be supplied by the agent.
5. **Enable: HAND OFF TO HUMAN.** The coding agent MUST NOT type, forge, copy or automatically approve the challenge. The human reviews the full scope and types it in a trusted TTY. Only the approved executor may call Flagsmith `flag enable --yes`, then immediately verify live ON readback. If the result is uncertain, attempt an emergency disable of the same scope and verify OFF; report failure if OFF cannot be proven.
6. **Rollback: HAND OFF TO HUMAN.** The operator runs `rollback` and separately approves the exact disable challenge, even if the worktree has become dirty. Verify live OFF. Never claim completion without OFF readback.
7. **Report:** Git SHA; test count; sandbox project/environment/flag (no keys); initial OFF, live ON, final OFF; any blocked or unverified steps. Read the operator-oriented [`README.md`](README.md) before running. Redacted logs and plans remain outside Git.

### Limits / safe behavior
- **Production is unsupported.** Context checks reject production-like labels, but these checks do not replace provider-side RBAC. Do not use privileged production credentials.
- **No progressive rollout, canary, metric monitoring or automatic shipment.** `flag enable` affects the default value for one test environment. Never call it a percentage rollout.
- **No autonomous confirmations, no cloud writes without a human**, no paid APIs, no contest submissions and no production deployments.
- A terminal approval is not cryptographically strong if an untrusted agent controls that terminal. Keep the operator terminal and keys outside agent control.

Detailed usage: [`README.md`](README.md). Executable: `scripts/sentinel.py`. The Agent Skills format is defined at https://agentskills.io/specification.
