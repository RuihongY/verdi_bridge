# Interval tools and persistent transport — 2026-10-13

[Home](../README.md) · [Tool semantics](tools.md) · [Evaluation protocol](paired-evaluation.md)

Verified on licensed **Verdi T-2022.06-SP2-1**, Linux, with the Python/MCP client on
macOS and a Python 3.6 remote helper. Consulted the installed vendor Tcl reference
before introducing API calls. Vendor manuals and wave files are not redistributed.

## Real observations

- An AXI-Lite window query returned WSTRB changing at 70 ns, constant incorrect
  `wstrb_next=f`, and `reg_wr_en` rising at 75 ns/falling at 85 ns, in one request.
- Clock observation returned 10 ns period and 5 ns phase. The extended pre-error
  jump snapped to the observed 65 ns rising edge.
- Recursive search found both top-level and DUT strobe signals in one request.
- Log reading returned `FIRST_ERROR time_ns=85 kind=register_payload`; file reading
  returned the numbered faulty statement at line 122. An outside-root file failed.
- Exact-limit and over-limit queries distinguished complete/truncated results.
  Start-exclusive/end-inclusive behavior and cursor/viewport restoration passed.
- Signed reads returned 1 and -1 for four-bit `0001` and `1111`. In this installed
  release the documented `2Com` format produced an incorrect zero in a preliminary
  query, so Dec explicitly converts full-width Bin (`-lz`) values as two's complement.
- A [synthetic VCD fixture](../examples/interval_probe/README.md) loaded into real
  Verdi exposed both ends of a **1 ps pulse** at 5 and 5.001 ns, plus X/Z transitions
  and eight-bit signed values. This was not a simulator run or an accuracy benchmark.
- A real MCP stdio session listed all 16 tools and successfully invoked the six new
  tools plus the extended `jump_before_error` against the same live GUI.

Evidence: [client queries](evidence/interval-v0.2/live.json),
[assertions and timings](evidence/interval-v0.2/live-checks.json),
[pulse fixture](evidence/interval-v0.2/live-pulse.json),
[real MCP calls](evidence/interval-v0.2/live-mcp.json).

The search API skips glitches. Distinct-timestamp pulse success does not establish
same-timestamp/delta-cycle completeness. No fault type is inferred by these tools.

## Transport microbenchmark

Forty unchanged `status` calls, alternating order in four batches per mode, five
calls per batch. Both modes used the same SSH ControlMaster and Verdi session;
persistent mode started one helper per batch. This is a small local measurement,
not a general network or agent performance claim.

| Transport | Calls | Median, all calls | Median, excluding first call of each batch |
|---|---:|---:|---:|
| One-shot SSH/helper | 20 | 254.6 ms | 241.3 ms |
| Persistent SSH/helper | 20 | 133.4 ms | 109.0 ms |

The agent still needs to choose relevant signals and reason about the design.
The existing 21-call blind trial used three batched sample calls, not iterative
binary searches. No reduction in agent calls or improvement in accuracy is claimed.

## Automated checks

Python/Tcl behavioral-double tests cover interval boundaries, a one-tick pulse,
X/Z, signed values, GUI restoration on success/error, recursive search limits,
clock phase/snap, file/log boundaries including symlinks, MCP schemas/prompts,
concurrent correlation, stale requests and private-directory requirements.

The SSH branch is exercised via an executable local shim that runs the exact
remote shell command, including quotes, dollar signs and backticks in helper text.
Tests verify reuse, concurrent calls, helper errors, disconnect handling, explicit
reconnection and timeout without automatic replay. This shim is not a network test;
the real transport measurements above use SSH to the licensed environment.
