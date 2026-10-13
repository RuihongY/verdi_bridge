# Validation record — 2026-10-12

## What was actually exercised

- Real licensed Verdi **T-2022.06-SP2-1** and VCS **U-2023.03-SP2** on Linux.
- Python MCP server/client on macOS, remote stdlib helper on Python **3.6.8**,
  SSH ControlMaster transport, Tcl **8.6.11** in Verdi, Xvfb display.
- A real MCP stdio client initialized the protocol, discovered ten tools and
  invoked GUI operations, waveform sampling, source reading and driver tracing.
- Nine VCS runs: baseline plus two mutants, each with three backpressure seeds.
  Baseline passed all; both mutants were detected in all three runs.
- Seed-1 cases were investigated in real Verdi. Both changed statements were
  identified by inspecting sampled values and source with supporting waveform and source evidence. Seed-7/42 simulations
  were checked, but not separately investigated in the GUI.
- Nine automated Python/Tcl tests cover time conversion and clamping, X/Z
  preservation, literal Tcl metacharacters, blocked eval, source-root boundaries,
  concurrent request correlation, invalid/missing signals, timeouts/stale files,
  private directory permissions and MCP success/error responses.
- Source distribution and wheel built successfully; bundled Tcl is included.

The original simple FIFO smoke test preceded this package. The external benchmark
used the packaged transport and real MCP protocol rather than the old raw Tcl
request file. Evidence replay scripts explicitly select the suspect signal; this
is assisted diagnosis on known mutations, **not blind model evaluation**.

## Results

| Case | First error, seed 1 | Real-Verdi localization | Baseline control |
|---|---|---|---|
| Stalled read pointer | 435 ns, data mismatch | source line 397; trace returned 397 initially and initializer 189 on restart | 64 writes / 64 reads, zero errors |
| Wrong full comparison | 3340 ns, progress timeout | axis_fifo.v:200, empty mistaken for full | same |

The original implementation is the passing control. Restoring each changed statement
produces that original file; no automated repair service is claimed. See
[evidence](evidence/) for the mutation manifest, complete nine-run summary, and
structured MCP responses. Raw tool values and source line numbers are preserved.
The screenshots show the actual remote GUI, not a reconstructed waveform viewer.

## Practical limits

- Only one Verdi version and this FIFO parameter configuration have been tested.
- Existing-GUI console attachment is implemented but the recorded end-to-end runs
  launched a new GUI with `-play`; attachment to an arbitrary user's session has
  not been separately validated.
- GUI driver tracing returned both line 397 and initializer line 189 for the pointer
  across sessions. It can return an initialization/process/reset site instead of
  the faulty statement. The returned line alone is not a diagnosis.
- Browse results are relative to the requested scope as returned by Verdi.
  Waveform sampling requires exact bus ranges discovered by browsing.
- File transport is suitable for interactive debugging, not high-rate waveform
  streaming. Individual requests are serialized in the GUI; multi-call workflows
  are not transactional and the user can move the current window between calls.
- VCD/FSDB open, compilation and simulation are performed outside the MCP tools.
  The bridge does not independently infer clock periods, read logs or generate fixes.
- Tests using the fake GUI validate our protocol, not EDA semantics.
- Linux CI runs protocol/unit tests on Python 3.11 and 3.12. See the
  [GitHub Actions runs](https://github.com/RuihongY/verdi_bridge/actions/workflows/test.yml)
  for the current status; these checks do not use a vendor license.

## Troubleshooting

`session` missing: confirm that Verdi completed startup and ran bridge.tcl. Check
for modal dialogs, a missing waveform, license errors, or a stale gui.lock.
Opening a VCD a second time can prompt before overwriting its converted FSDB;
open the existing `.vcd.fsdb` directly or resolve the dialog in the GUI.

Permission error: make a new owner-only bridge directory with `mktemp -d`.
Do not reuse a different user's directory or a directory shared by multiple GUIs.

Source unavailable: load RTL and set VERDI_BRIDGE_SOURCE_ROOTS on the Verdi host
before loading the adapter. Paths resolve relative to the GUI's working directory.

Missing signal: browse the containing scope, then use the exact full path including
bus range. The bridge refuses to turn a missing signal into a plausible zero value.

Timeout: the GUI may be busy or a dialog may block it. An operation already claimed
by the GUI may complete later. Inspect the GUI/status before retrying; automatic
retries of GUI mutations are intentionally not performed.
