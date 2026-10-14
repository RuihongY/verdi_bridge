# Tool reference

[Home](../README.md) · [Setup](guide.md)

Eighteen typed tools operate in the connected Verdi session. No tool edits RTL,
compiles a design, or evaluates arbitrary Tcl/shell code. File and log reads are
restricted to separate `VERDI_BRIDGE_SOURCE_ROOTS` / `VERDI_BRIDGE_LOG_ROOTS` and require an open nWave window.

| MCP tool | Arguments | Result |
|---|---|---|
| `session_status` | None | Window, native units, cursor, viewport, first 200 displayed signals and their total |
| `browse_scope` | `scope="/"`, `offset=0`, `limit=500` | One page of child scopes then signals; totals and `next_offset` |
| `find_signals` | `pattern`, `scope="/"`, `max=100`, `depth=16`, `glob=False`, `budget_ms=1000` | Absolute matching paths; truncation flag and reasons (max results, depth, scope limit, time budget) |
| `add_signals` | `signals` | Add 1–128 exact paths to nWave |
| `set_cursor` | `time`, `unit="ns"` | Actual cursor |
| `set_time_window` | `start`, `end`, `unit="ns"` | Actual viewport |
| `jump_before_error` | `error_time`, `period=None`, `cycles=20`, `unit="ns"`, `clock_signal=None`, `window=None` | Cursor, clamping and edge-snap status |
| `sample_signals` | `signals`, `times`, `unit="ns"`, `radix="Bin"`, `budget_ms=2000` | Values at explicit points; `pending_signals` when the budget runs out |
| `count_changes` | `signals`, `start`, `end`, `unit="ns"`, `budget_ms=2000` | Per signal: change count, first/last change, Hex values at start and end |
| `sample_on_clock` | `clock`, `signals`, `start`, `end`, `unit="ns"`, `radix="Hex"`, `edge="rising"`, `sample="pre"`, `max_cycles=64`, `budget_ms=2000` | One row of values per clock edge; `resume_from` when truncated |
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

## Large waveforms

Every query runs on Verdi's GUI thread, so each tool has a bounded cost and returns
partial results instead of blocking the GUI. Measured on Verdi T-2022.06-SP2-1 over
SSH, with an FSDB holding 20 000 signals in one flat scope and 2 M changes on one bus:

| Cost | Measured |
|---|---|
| Round trip per call | ~0.11 s |
| First access to a signal in a 20 000-signal flat scope | ~0.15 s per signal (Verdi load; small scopes ~3 ms) |
| Value at a time, signal already loaded | ~0.3 ms |
| Change listing (`get_value_changes`) | ~4 500 changes/s |
| Change counting (`count_changes`) | ~11 000 changes/s |

Practical consequences:

- Sample many signals in several calls: `sample_signals` stops between signals once
  `budget_ms` is spent and lists the rest in `pending_signals`.
- Summarize before listing. `count_changes` shows which signals are active and when;
  `sample_on_clock` turns per-edge sampling into one table. Then fetch details for a
  short window.
- Page wide scopes with `browse_scope` `offset`/`limit`, and scope `find_signals`
  to the relevant subtree; whole-hierarchy searches stop at their budget.
- Raise `VERDI_BRIDGE_TIMEOUT` if single vendor calls are slow on your FSDB. A budget
  cannot interrupt one vendor call.

### Headless NPI engine

`count_changes`, `get_value_changes` (and so `find_transitions`, `measure_clock`),
`sample_signals` and `sample_on_clock` can also run through Verdi's Python NPI FSDB
reader in a separate, short-lived process on the Verdi host. It opens the FSDB shown
in the active nWave window, never touches the GUI, and exits after each request, so
any license it checks out is released immediately. Results have the same shape and
values as the GUI path, plus `engine` (and `engine_note` when it explains a choice).

`VERDI_BRIDGE_ENGINE` selects the path:

| Value | Behavior |
|---|---|
| `auto` (default) | `count_changes` uses NPI first. Other queries start in the GUI (~0.1 s) and are redone through NPI only when the GUI ran out of `budget_ms`. Falls back to the GUI when NPI is unavailable. |
| `gui` | Never start NPI. |
| `npi` | Always use NPI; report an error if it is unavailable. |

Measured on the same FSDB (Verdi T-2022.06-SP2-1 NPI, host Python 3.6.8):

| Query | GUI only | `auto` |
|---|---|---|
| 128 cold signals × 8 times, 20 000-signal scope | 19 s in one blocking call | 4.0 s, complete |
| Count all changes of a 2 M-change bus and its clock | ~9 min (extrapolated from 11 000 changes/s) | 9.5 s, complete |
| Count whole-run changes of 128 cold signals | 94 s in 9 calls | 3.8 s, one call |
| One warm sample | 0.12 s | 0.12 s (GUI) |

NPI costs about 0.6 s per call (process start, NPI init, FSDB open), which is why small
queries stay in the GUI. NPI needs a readable FSDB (not a VCD), `VERDI_HOME` and
the license variables of the Verdi process, and a Python 3.6+ interpreter on the
Verdi host that can import Verdi's `pynpi` (`VERDI_BRIDGE_NPI_PYTHON`, default
`python3`). Without a license the FSDB cannot be opened and `auto` uses the GUI.
NPI collapses several changes at one timestamp into one, like the GUI skipping
glitches (not yet checked on an FSDB that records glitches); `sample="pre"` reads one
FSDB tick before an edge.

#### Multi-gigabyte FSDBs

The engine loads only the queried time window. Aliased or sparse signals are slow to
resolve that way (~0.15 s each), so after two slow first reads it loads the remaining
signals from time 0 in one batch, which is fast for them. Results report the choice
in `npi_load` and the engine's peak memory in `npi_peak_mb`. Loading everything
from time 0 instead would have needed 3.2 GB for 256 busy signals of the file below.

Each engine process runs under an address-space limit (`VERDI_BRIDGE_NPI_MAX_MB`,
default half of the host's RAM; NPI itself maps ~0.5 GB). A query that exceeds it
fails in the engine, not on the shared host, and `auto` answers through the GUI.

Measured with a 2.7 GB FSDB (256 random 32-bit registers, 1 M changes each, plus a
2 M-change clock):

| Step | Result |
|---|---|
| Verdi opens the FSDB and loads the adapter | 7.2 s, 338 MB RSS |
| GUI: changes of one register over 1 µs at 90% of the run | 1.5 s (cold) |
| GUI: `sample_on_clock`, 4 registers × 64 cycles | 0.18 s |
| NPI: values of 128 registers at 9 ms | 1.3 s, 93 MB peak |
| NPI: changes of 128 registers over 100 ns at 9 ms | 0.6 s, 93 MB peak |
| NPI: `sample_on_clock`, 32 registers × 128 cycles | 0.6 s, 83 MB peak |
| NPI: count all 4 M changes of two registers and the clock | 8.7 s, 105 MB peak |
| NPI: count 128 registers over the whole run (128 M changes) | stops at its 10 s budget with `resume_from`; 1.8 GB peak |

On the 20 000-signal FSDB, whose signals are aliases, 128 cold signals at 10 ms took
7.3 s through `auto` (2 slow reads, then one load from time 0; 130 MB peak), where
the GUI alone needs ~0.15 s per signal.

GUI and NPI results were identical wherever the GUI finished within its budget.

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
