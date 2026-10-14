# Changelog

## 0.3.3 — 2026-10-14

Large-waveform handling, measured against Verdi T-2022.06-SP2-1 with a 20 000-signal
flat scope, 2 M-change buses and a 2.7 GB FSDB (see the tool reference).

- `sample_signals` reads signal by signal with a `budget_ms` (default 2000). It
  returns finished samples plus `pending_signals` instead of blocking the GUI: 128
  slow-loading signals went from a 19 s call to 2.3 s partial results.
- New `count_changes`: change count, first/last change and boundary values per
  signal, without per-change value reads (~2.5x faster than listing changes).
- New `sample_on_clock`: one row of values per clock edge. `sample="pre"` reads one
  native tick before the edge (what flops capture); verified against live Verdi.
- `browse_scope` pages with `offset`/`limit` (default 500) and reports totals; a
  20 000-signal scope no longer returns 189 KB at once. `session_status` lists at
  most 200 displayed signals plus `signals_total`.
- New headless NPI engine (`npi_engine.py`): runs Verdi's Python NPI FSDB reader in a
  short-lived process on the Verdi host. `VERDI_BRIDGE_ENGINE=auto` (default) uses it
  first for `count_changes` and to finish GUI queries that exhausted their time
  budget; it falls back to the GUI when NPI is unavailable. Live results matched the
  GUI path field for field in 16 query types. A 2 M-change bus plus clock is counted
  in 9.5 s instead of ~9 minutes of GUI paging (extrapolated).
- The engine loads only the queried window and switches aliased/sparse signals to
  one load from time 0 after two slow reads. On a 2.7 GB FSDB, window queries over
  128 registers took 0.6–1.3 s at under 100 MB, where loading from time 0 needed
  3.2 GB. Results report `npi_load` and `npi_peak_mb`.
- Each engine process runs under an address-space limit (`VERDI_BRIDGE_NPI_MAX_MB`,
  default half of RAM); an engine that hits it fails alone and `auto` uses the GUI.
  Work directories of aborted engines are removed by the next engine start.
- `VERDI_BRIDGE_TIMEOUT` sets the client request timeout (1–600 s, default 15).
- JSON escaping in the adapter uses one `string map` pass instead of a per-character
  loop (~0.12 s/MiB before).
- The 0.3.2 fixes were checked live: default session directory creation, stale-lock
  takeover after a killed GUI, and the SSH bootstrap through tcsh, csh and bash with
  the host's Python 3.6.8.

**Migration:** `browse` and `sample` gained wire arguments. Upgrade the Python
package and the loaded Tcl adapter together.

## 0.3.2 — 2026-10-14

- SSH works when the remote login shell is csh/tcsh. The remote command is now a
  one-line bootstrap; the helper source travels over stdin. Previously tcsh failed
  and could run fragments of the helper source as shell commands.
- Responses are written and read as UTF-8 regardless of locale, so non-ASCII
  source/log text no longer breaks Python 3.6 helpers under `LANG=C`. Source and
  log lines decode as UTF-8 when valid, otherwise in the GUI's system encoding.
- File roots never include `/` or a directory containing `$HOME`. A GUI started
  from the home directory has file reads disabled until roots are set; explicit
  roots of that kind are rejected at startup.
- MCP tools run in worker threads, so a busy GUI no longer stalls pings,
  cancellation or other requests in the stdio server.
- `find_signals` takes a cooperative `budget_ms` (default 1000, max 2000) and
  reports `reasons` for truncation. Its breadth-first queue is now linear-time.
- `VERDI_BRIDGE_DIR` is optional: both sides default to `~/.verdi-bridge/session`,
  created with mode 0700. A lock left by a dead GUI on the same host is taken
  over, and stale requests/results are removed at startup.
- A foreign `*.req` file no longer blocks request handling, and polling survives
  filesystem errors.

**Migration:** `find_signals` gained a wire argument. Upgrade the Python package
and the loaded Tcl adapter together.

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
