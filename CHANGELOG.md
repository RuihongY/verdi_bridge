# Changelog

## 0.2.0 — 2026-10-13

- Add bounded transition/window queries, recursive signal search, clock measurement,
  log reads, and direct source-file reads (16 MCP tools total).
- Add optional observed-clock edge snapping to `jump_before_error` and signed Dec.
- Reuse a remote SSH/helper connection; preserve per-request identity, timeout
  semantics and no automatic replay. Add explicit client cleanup and one-shot opt-out.
- Replace the FIFO-specific MCP prompt with generic `debug_failure`.
- Preserve raw driver locations and add structured entries with type `unknown`:
  the vendor API does not identify assignment types.
- Add real-Verdi evidence, synthetic narrow-pulse probe, SSH-branch tests and paired
  evaluation protocol. No new model accuracy or agent call-count claim.
- Move old agent demo materials under `docs/evidence/archive/` without deleting
  recordings or historical evidence. Current README links retain native EN/ZH demos.

Upgrade both the Python package and the loaded Tcl adapter. Restart the adapter in
an isolated fresh GUI/session directory; upgrading Python alone does not add GUI
operations. `debug_fifo` prompt clients must switch to `debug_failure`.

## 0.1.1 — 2026-10-13

Initial public ten-tool bridge with real-Verdi examples, multi-design injected
faults, independent-agent blind trial, and native English/Chinese demo recordings.
Installed from this repository; no PyPI upload.
