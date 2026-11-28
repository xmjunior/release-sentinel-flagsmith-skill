# Evidence note — authorized test-only E2E runs

## 28 November 2026 — Verified hardened release (`f993328353f580608d1fd77598cb820f4c7bd5e5`)

Executed in a real interactive Windows PowerShell operator terminal using Flagsmith CLI `v2.0.0` against `https://api.flagsmith.com` in an enrolled nonproduction sandbox (`sandbox-only` allowlist outside Git):

1. **Read-only initial inspect:** `flag get` returned `enabled: false` (OFF) against Flagsmith Cloud.
2. **Counted local regression suite + plan (`17:52:21Z`):** `PLAN_READY` recorded `55/55` local tests PASS bound to exact clean Git SHA `f993328353f580608d1fd77598cb820f4c7bd5e5` with a 10-minute single-use nonce.
3. **Live negative gate observed (`17:48:51Z`):** an unapproved/incorrect confirmation attempt was blocked (`BLOCKED: Human approval absent or incorrect`) with zero Cloud mutation.
4. **Human approval #1 → Enable (`18:02:07Z` → `18:02:09Z`):** after typing the exact one-time `ENABLE` challenge, `ENABLE_ATTEMPT` and `ENABLE_VERIFIED` succeeded; independent live Flagsmith Cloud `inspect` readback confirmed `enabled: true` (ON) and consumed `plan.json`.
5. **Human approval #2 → Rollback (`18:03:24Z` → `18:03:30Z`):** after typing a fresh one-time `DISABLE` challenge, `ROLLBACK_ATTEMPT` and `ROLLBACK_VERIFIED` succeeded; independent live Flagsmith Cloud `inspect` readback confirmed `enabled: false` (OFF).
6. **Post-run independent verification:** direct live Cloud `inspect` confirmed final state `enabled: false` (OFF) and consumed one-time plan (`plan.json` absent).

## 27 November 2026 — Baseline release (`e750e206` / `f33463e`)

Earlier operator-observed Windows terminal run on the baseline 36-test release likewise completed OFF → ON → OFF with two independent human confirmations and readbacks.

**Evidence provenance and privacy:** All runs were executed in the operator's dedicated test-only Flagsmith Cloud sandbox and verified via live CLI readbacks plus local redacted JSONL evidence (`~/.release-sentinel/state/evidence.jsonl`). Actual account/organisation/project/environment IDs, SDK keys, key fingerprints, approval challenges, nonces and local user paths are deliberately omitted from this public repository.

**Not claimed:** official organizer acceptance, leaderboard score, live token-count benchmark (NOT MEASURED), progressive percentage rollout or production readiness.
