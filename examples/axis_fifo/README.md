# External RTL mutation experiment

Source: [Alex Forencich's verilog-axis](https://github.com/alexforencich/verilog-axis),
`rtl/axis_fifo.v`, commit `48ff7a7e2ef782cf778d47910cf85835c64b1bce` (MIT).
This is a pinned historical implementation used as a benchmark, not a claim that
this deprecated repository is the current recommended IP. The two bugs below were
injected locally; they are **not bugs reported against upstream**.

```sh
uv run python examples/axis_fifo/prepare.py build/axis_fifo
# In your licensed VCS environment:
bash examples/axis_fifo/run_vcs.sh
```

`prepare.py` retains the upstream copyright/license header and records the SHA-256,
revision, original statement, changed statement and source line in `manifest.json`.
The upstream file is fetched on demand; no vendor libraries are distributed.
`check_results.py` requires a completed result for all nine runs, an error-free
baseline with 64 transfers, and a detected failure for each mutant. VCS's exit code
alone is not treated as a pass.

The checker uses an independent input/output scoreboard, validates output stability
under backpressure and enforces bounded progress. It does not read DUT pointers.
Three seeds vary output backpressure. Parameters are DEPTH=8, DATA_WIDTH=8,
RAM_PIPELINE=1, non-frame mode, no output FIFO, no sidebands.

| Variant | Seed 1 | Seed 7 | Seed 42 |
|---|---|---|---|
| Original | pass, 64/64 transfers | pass, 64/64 | pass, 64/64 |
| Stalled read pointer | detected, 435 ns | detected, 435 ns | detected, 425 ns |
| Wrong full comparison | timeout, 3340 ns | timeout, 3340 ns | timeout, 3340 ns |

## Diagnosis observed through MCP and real Verdi

For the stalled pointer, at 126 ns the write pointer is 8, read pointer 0 and full=1.
At 416 ns the output is valid and ready, but subsequent samples still show read
pointer 0 and repeated data 17. The first scoreboard mismatch is at 435 ns.
`trace_driver(tb.dut.rd_ptr_reg)` initially returned `axis_fifo.v:397`; after a
GUI restart it returned the initializer at line 189. Inspection of the driving
logic through the source tool shows at line 397
`rd_ptr_reg <= rd_ptr_reg;` inside the enabled read path. The pointer never advances,
causing repeated reads and keeping the full condition asserted. Restore `+ 1`.

For the bad comparison, at 46 ns both pointers are 0, full=1 and empty=1,
input valid=1 but ready=0. No transfer occurs in the entire test. Driver tracing
returns `axis_fifo.v:200`: full was incorrectly defined as pointer equality, the
empty condition. Restore the comparison that flips the read pointer's wrap bit.

Driver tracing is not a fault locator: it can land on an initializer, process or
reset assignment and the selected site can vary with GUI state. Source inspection
was required to identify the faulty statement. Both the initial and final pointer
traces are retained rather than discarding the less precise result.

## Reproduce GUI evidence

Start Verdi from `build/axis_fifo/<case>` with `axis_fifo.v`, this example's `tb.sv`,
and `seed-1/wave.vcd`, loading the project's bridge.tcl as described in the main
README. Set source roots to include this benchmark and the generated build directory.
Use `capture.py` with the same VERDI_BRIDGE_* client environment. It invokes real
MCP tools and saves structured responses. Example for the stalled pointer:

```sh
uv run python examples/axis_fifo/capture.py \
  --signal tb.dut.rd_ptr_reg --line 397 --start-line 375 \
  --error-time 435 --times 46 56 126 416 426 436 --output evidence.json
```

The recipe intentionally contains a selected suspect and line. It replays evidence
collection; it is not an automatic detector or a blinded evaluation. The author
who injected the bugs also inspected the evidence. The result is **2/2 successful
assisted localizations on known mutations**, not an estimate of general LLM accuracy.
No new model was trained; no external LLM API call is required by the package.
Future blind evaluation needs withheld mutation locations, disjoint designs, a fixed
agent/model configuration, a tool-call budget, and scoring independent of the injector.

Recorded run results and tool responses are in `docs/evidence/`. All returned X
values are preserved; the pre-valid output X values are not interpreted as errors.
