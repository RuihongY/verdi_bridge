# UART, AXI-Lite and round-robin arbiter benchmark

Three different open RTL modules use the unchanged Verdi bridge. Sources are pinned
by revision and SHA-256 in `specs.json`; all retain their upstream MIT notices.
These are pinned historical implementations used as fixtures, not recommendations
of currently maintained IP. The defects are locally injected, not upstream bug reports.

| Case | Upstream module | Checker |
|---|---|---|
| UART | [verilog-uart](https://github.com/alexforencich/verilog-uart), uart_tx.v | Independent 8N1 serial decoder, 12 frames |
| AXI-Lite | [verilog-axi](https://github.com/alexforencich/verilog-axi), axil_reg_if_wr.v | AW/W queues, register-side writes, response hold and completion |
| Arbiter | [verilog-axis](https://github.com/alexforencich/verilog-axis), arbiter.v + priority_encoder.v | Cyclic behavioral scheduling model, 100 rounds |

## Reproduce simulation

From the project root, with Python 3.11+ and a configured licensed VCS environment:

```sh
uv run python examples/multidesign/prepare.py build/multidesign
bash examples/multidesign/run_vcs.sh build/multidesign baseline mutant
uv run python examples/multidesign/apply_repairs.py build/multidesign
bash examples/multidesign/run_vcs.sh build/multidesign repaired
uv run python examples/multidesign/check_results.py build/multidesign
```

The last command requires all 27 completed simulations: baseline and repaired cases
must have zero errors and complete the expected workload; mutants must fail.
Missing results or watchdog termination are errors, not passes. Seeds 1/7/42 vary
UART data/spacing, AXI-Lite channel skew/response backpressure, and arbiter requests.
This is three bugs under three seeds, not 27 independent bugs.

UART uses an 8-bit transmitter with prescale=2 and a 10 ns clock. AXI-Lite uses the
write register interface with 16-bit addresses, 32-bit data and immediate backend
acknowledgment. The arbiter is four-port, LSB-high-priority, nonblocking round robin.
Baseline tests passed before diagnosis. The replayable repairs were selected after
examining tool evidence and restore the original source, as verified by file hashes.

## Reproduce MCP evidence

Start a licensed Verdi GUI from `build/multidesign/<design>/mutant`:

```sh
# Set VERDI_BRIDGE_DIR and VERDI_BRIDGE_SOURCE_ROOTS as in the main README.
verdi -sv ./*.v /absolute/project/examples/multidesign/uart_tb.sv \
  -top tb -ssf seed-1/wave.vcd -play /absolute/path/to/bridge.tcl
```

Use `axil_tb.sv` or `arbiter_tb.sv` for the other designs. Repeated VCD loading can
prompt to overwrite a converted FSDB; opening the existing `.vcd.fsdb` avoids that.
On the client machine, with matching VERDI_BRIDGE_* environment:

```sh
uv run python examples/multidesign/record_mcp.py \
  examples/multidesign/plans/uart.json uart-evidence.json
```

The recorder has no design-specific logic. Plans contain actual investigator-selected
tool calls, including discovery, values around the failure and complete source reads.
They contain no fault-line parameter and do not load the ground-truth manifest.
This is still **not blinded**: the same investigator created and diagnosed the
mutants, and the plans are an evidence replay rather than an autonomous agent.
Only seed 1 was inspected in the real GUI; all three seeds were simulated.

See [detailed results, evidence and limits](../../docs/multidesign-validation.md).
Do not equate a driver's returned line with the faulty statement: UART and arbiter
traces landed on initializers, and source inspection was necessary to find the bugs.
