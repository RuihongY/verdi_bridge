# Reproduce the eight-case pilot

[Results and limitations](../../docs/paired-pilot.md). These cases are now disclosed;
replaying them is not a fresh blind benchmark.

The committed [fixtures](../../docs/evidence/paired-pilot-v0.3/fixtures/) contain
MIT upstream RTL with original notices, the mutated files, independent testbenches,
all screening logs and the exact diagnosis prompts. Upstream commits/hashes and
changed statements are recorded alongside the fixtures. No VCD/FSDB or proprietary
EDA files are distributed. The excluded shortened-start candidate is retained.

1. In your licensed environment, compile each fixture's `*.v` and `tb.sv` with
   SystemVerilog enabled and top module `tb`. Run seeds `+SEED=1`, `7`, `42` in
   separate `seed-N` directories, saving `sim.log` and the testbench's `wave.vcd`.
   Check complete baseline results with zero errors and detected accepted mutants.
2. Provide a private remote `launch.sh CASE` at `PILOT_REMOTE_ROOT`. It must start
   a fresh GUI for that case, load its RTL and seed-1 wave, source the current
   bridge.tcl, restrict source roots to the case and log roots to `case/seed-1`,
   and print the private session directory as its final output line. The session
   directory must hold only that launch's `verdi.pid` and `xvfb.pid`; the harness
   terminates those processes after diagnosis. Configure licenses/display locally.
3. Install a compatible authenticated Codex CLI and run `uv sync` in this repo.
   The recorded run used CLI 0.147.0, `gpt-5.6-sol`, medium reasoning. Verify model
   compatibility and an MCP status call before spending on a batch.
4. Configure paths, then invoke the harness:

```sh
export PILOT_FIXTURES=/absolute/path/to/local/fixtures
export PILOT_OUTPUT=/absolute/path/to/new-results
export PILOT_SSH_HOST=user@your-eda-host
export PILOT_REMOTE_ROOT=/absolute/path/to/remote/pilot
# Optional: existing shared SSH socket.
export VERDI_BRIDGE_CONTROL_PATH=/absolute/path/to/control.sock
uv run python examples/paired_pilot/run.py
```

`run.py` is the recorded harness adapted to environment-provided paths and host
settings. It starts two independent pairs at a time, randomizes order with the
recorded seed, embeds identical numbered inputs, disables unrelated tools and
records answers, timed public events, usage and return codes. The budget is 240 s
per diagnosis; no custom token cap is set. It never gives the model the mutation
manifest and never edits RTL. GUI work is serialized within each session.
The replay script checks startup via the session file; perform the separate tool
preflight above. Isolate the remote roots from manifests and other cases.

Results include private invocation paths and stderr: sanitize before publishing.
Freeze all answers before comparing `file` and `line` against the manifest; report
all failures and tool calls, even if tools were available but unused. A and B are
matched per case, but seed simulations are not independent diagnosis cases.
