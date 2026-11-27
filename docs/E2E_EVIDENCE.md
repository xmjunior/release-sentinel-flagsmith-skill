# Evidence note — authorized test-only demo

Date: 27 Nov 2026. The operator presented genuine Windows terminal output from Flagsmith CLI v2 showing:

1. Read-only inspect of a nonproduction environment: flag OFF.
2. Counted deterministic plan: 36/36 local tests PASS.
3. First human confirmation; CLI output `SANDBOX ENABLE VERIFIED` (ON).
4. Second independent human confirmation; CLI output `SANDBOX ROLLBACK VERIFIED` (OFF).
5. Final console banner reporting the test-only cycle OFF → ON → OFF PASS.

**Evidence provenance:** an operator-provided screenshot, not independent verification of Flagsmith's server logs. The actual operator's IDs, environment keys, key fingerprints, approval challenges, nonce values and Windows user directory are deliberately omitted from this public file. The locally generated private JSON evidence is not distributed.

Do not describe this as an official judge's result. No video URL, live token-count benchmark, hackathon submission receipt or prize outcome has yet been provided.
