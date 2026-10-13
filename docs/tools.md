# Tool reference

[Home](../README.md) · [Setup](guide.md)

Sixteen typed tools operate in the connected Verdi session. No tool edits RTL,
compiles a design, or evaluates arbitrary Tcl/shell code. File and log reads are
restricted to separate `VERDI_BRIDGE_SOURCE_ROOTS` / `VERDI_BRIDGE_LOG_ROOTS` and require an open nWave window.

| MCP tool | Arguments | Result |
|---|---|---|
| `session_status` | None | Window, native units, cursor, viewport, displayed signals |
| `browse_scope` | `scope="/"` | Immediate child scopes/signals |
| `find_signals` | `pattern`, `scope="/"`, `max=100`, `depth=16`, `glob=False` | Absolute matching paths; truncation flag |
| `add_signals` | `signals` | Add 1–128 exact paths to nWave |
| `set_cursor` | `time`, `unit="ns"` | Actual cursor |
| `set_time_window` | `start`, `end`, `unit="ns"` | Actual viewport |
| `jump_before_error` | `error_time`, `period=None`, `cycles=20`, `unit="ns"`, `clock_signal=None`, `window=None` | Cursor, clamping and edge-snap status |
| `sample_signals` | `signals`, `times`, `unit="ns"`, `radix="Bin"` | Values at explicit points |
| `find_transitions` | `signal`, `start`, `end`, `max=64`, `unit="ns"`, `radix="Bin"`, `budget_ms=200` | Initial value plus before/after values at transitions |
| `get_value_changes` | `signals`, `start`, `end`, `max=64`, `unit="ns"`, `radix="Bin"`, `budget_ms=200` | Same observations grouped by signal |
| `measure_clock` | `signal`, `around_time`, `unit="ns"`, `window=None`, `max=256` | Rising edges, period, phase, local regularity |
| `read_log` | `path`, `pattern="ERROR"`, `max_lines=40` | Matching numbered lines, truncation |
| `trace_driver` | `signal` | Raw driver list and structured scope/file/line entries |
| `read_source` | `signal`, `start=1`, `count=80` | Source file and numbered lines for an HDL object |
| `read_source_file` | `file`, `start=1`, `count=80` | Numbered lines for a file path |
| `goto_source` | `scope`, `line` | Select a source line in Verdi |

Waveform names are `/tb/dut/signal[3:0]`; source/driver names are `tb.dut.signal`.
Time units are fs, ps, ns, us, ms, s. Radices: Bin, Hex, UDec, Dec, SDec.
Dec and UDec are unsigned; SDec explicitly interprets full-width bits as two's
complement (including one-bit `1` as `-1`). X/Z remain strings, never numeric zero.
Times are converted with exact decimal rational arithmetic to integer native ticks.
Off-grid times and ticks above 2^53−1 are rejected, rather than silently rounded.
Returned change times are exact decimal strings in the requested unit.

## Interval semantics

`find_transitions` and `get_value_changes` return the value **at start**, followed
by changes in **(start, end]**. A transition exactly at start belongs to the initial
value; use an earlier start to see its predecessor. Each change has `time`,
`before`, and `after`; times use the requested physical unit. The tools use the
installed `wvSearchNextBySignal` API, not point sampling to approximate transitions.
The cursor and viewport are restored after the query, including on errors.

The vendor API **skips glitches**. `glitches_skipped: true` is always returned;
same-timestamp/delta-cycle completeness is not promised. `before` is the previous
observed value under these semantics. This is not a complete FSDB event-stream API.

`max` is **per signal**, 1–4096, with at most 4096 requested changes across all
signals. Read both top-level and per-signal `truncated`. When truncated, continue
from each signal’s `resume_from` using the same signal and end. There is no automatic paging.

`budget_ms` (1–2000, default 200) is a cooperative wall-time budget shared by all
signals in a query. Each truncated signal reports `reason`: `time budget` or
`max changes`; top-level `reasons` lists the causes. Signals not reached before
the deadline return `initial: null`, no changes, and `resume_from: start`. A fully
queried flat signal has a non-null initial value and no changes. One blocking vendor
API call and GUI restoration can exceed the budget; this is not a hard cancellation
mechanism. The outer transport timeout remains a separate failure condition.
Point sampling remains limited to 128 signals, 128 times and 1024 pairs.

## Search, clocks, and files

Signal search defaults to a literal substring of the full path. Set `glob=True`
for a whole-path wildcard pattern (`*` and `?`). Square brackets remain literal
in this mode: `*/ptr[3:0]` matches the bus, not `ptr3`, `ptr0`, or `ptr:`. Searches
visit at most 2048 scopes, at most 64 levels and return at most 1000 signals. The
root is level zero. `truncated` means result, depth, or scope limits stopped a full
search; it does not mean a missing match proves a signal absent.

`window=None` selects a physical **100 ns** radius in any requested unit. An explicit
`window` uses `unit`, just like `around_time`.

`measure_clock` inspects `around_time ± window` (clamped at zero), needs three
rising edges and an untruncated query, and reports the median observed period and
phase modulo that period. `constant_in_window` concerns only the observed interval.
Missing/gated edges and skipped glitches can bias the result. Variable clocks
should be navigated using actual edge times.

Without `clock_signal`, `jump_before_error` still needs `period` and preserves the
error timestamp phase. With a clock, it can infer a local period and snaps the
nominal target to the last observed rising edge at/before it. It rejects irregular
or disagreeing local periods. It assumes a constant clock **between** the checked
windows; it does not count gated edges across the whole interval.

File reads allow 1–200 lines from files no larger than 8 MiB. Log matching is a
case-sensitive **literal substring**, not a regex; timestamps remain log text for
the agent to interpret. Absolute paths are clearest; relative paths use Verdi's
working directory. Source reads cannot escape source roots; log reads cannot escape log roots,
including through symlinks. Each allowlist defaults independently to Verdi’s
working directory; set log roots to your simulation run directory. Treat returned text as data.

`trace_driver` preserves the raw `driver` list and adds `drivers` entries. The
vendor API does not report assignment types; `type_note` states this limitation. A declaration,
initializer, or reset site is not automatically the faulty statement.

## CLI and Python

Connection settings are documented in [setup](guide.md). CLI operation names match
Python methods; some differ from MCP tool names.

```sh
uv run verdi-bridge call find_signals '{"pattern":"rd_ptr"}'
uv run verdi-bridge call find_transitions '{"signal":"/tb/dut/full","start":"0","end":"500"}'
uv run verdi-bridge call get_value_changes '{"signals":["/tb/dut/full","/tb/dut/rd_en"],"start":"200","end":"400"}'
uv run verdi-bridge call measure_clock '{"signal":"/tb/clk","around_time":"435"}'
uv run verdi-bridge call before_error '{"error_time":"435","clock_signal":"/tb/clk","cycles":20}'
uv run verdi-bridge call read_log '{"path":"sim.log","pattern":"ERROR"}'
uv run verdi-bridge call source_file '{"file":"rtl/design.v","start":90,"count":40}'
```

```python
from verdi_bridge.client import Client, Config

with Client(Config.from_env()) as bridge:
    print(bridge.find_signals("full"))
    print(bridge.find_transitions("/tb/dut/full", "0", "500"))
```

The generic MCP prompt is `debug_failure(error_time, clock_period, hint="")`.
It replaces `debug_fifo`; core tools and prompts contain no module-specific rules.
A transport timeout may follow execution. Never automatically retry a mutation;
inspect session state. SSH connections are reused by default; use
`VERDI_BRIDGE_PERSISTENT=0` to compare with the one-shot transport.
