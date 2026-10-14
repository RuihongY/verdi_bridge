# Changelog

## 0.3.1 — 2026-10-13

- Prepare PyPI distribution metadata, MCP Registry manifest, and an OIDC publishing workflow.
- Lead English/Chinese documentation with live waveform observation and GUI navigation.
- Add pip/uvx installation instructions and a central validation index; all paired-pilot
  outcomes and limitations remain public. No runtime tool behavior changes.

## 0.3.0 — 2026-10-13

- Convert physical times exactly to integer native ticks; reject off-grid times and
  ticks beyond 2^53−1. Preserve exact `(start, end]` comparisons and decimal output.
- **Migration:** Dec is now unsigned (like UDec); request SDec for two’s complement.
  `find_signals` is literal by default; pass `glob=True` for wildcard paths. Bus
  brackets stay literal. Configure `VERDI_BRIDGE_LOG_ROOTS` separately for log reads.
- Bound interval work with a cooperative 200 ms default budget and resumable
  per-signal partial results. One blocking vendor call cannot be preempted.
- Default both polling intervals to 10 ms; cache signal listings within a request.
  Clock windows default to a physical 100 ns regardless of requested unit.
- Remove constant driver type fields; document per-Client and GUI serialization.
- 42 automated tests plus live Verdi checks. A 2×2 transport experiment measured
  106 ms to 47 ms persistent median latency after lowering polling.
- Run and publish an eight-mutation paired pilot: 8/8 exact localization in both
  arms, zero diagnostic tool calls. No accuracy or agent call-count benefit shown.

Upgrade Python and the loaded Tcl adapter together in a fresh session directory.
The wire arguments changed; mixing adapter/package versions is unsupported.

## 0.2.1 — 2026-10-13

- Detect an exited SSH process before writing another request, even if a surviving
  descendant still holds a pipe. Never continue or replay through a dead transport.
- Make the local SSH shim exec its helper consistently on macOS and Linux.
- The initial v0.2.0 tag failed Linux CI on this disconnect scenario. Its history
  is retained; v0.2.1 is the release build.

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
