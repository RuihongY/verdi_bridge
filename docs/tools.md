# Tool reference

[Home](../README.md) · [Setup](guide.md)

All ten tools operate on the current nWave window. GUI operations change the visible
session; no tool edits RTL, runs a shell, compiles a design or executes arbitrary Tcl.

| MCP tool | Arguments | Result |
|---|---|---|
| `session_status` | None | Window handle, native time unit, cursor, viewport, displayed signals |
| `browse_scope` | `scope="/"` | Child scopes and signal names, relative to the requested scope |
| `add_signals` | `signals` | Displayed signals after adding 1–128 exact waveform paths |
| `set_cursor` | `time`, `unit="ns"` | Actual cursor position and native time unit |
| `set_time_window` | `start`, `end`, `unit="ns"` | Actual viewport and native time unit |
| `jump_before_error` | `error_time`, `period`, `cycles=20`, `unit="ns"` | Cursor and whether the target was clamped at zero |
| `sample_signals` | `signals`, `times`, `unit="ns"`, `radix="Bin"` | Values with signal, time and unit attached |
| `trace_driver` | `signal` | Verdi's driver location list |
| `read_source` | `signal`, `start=1`, `count=80` | Source path, definition line and numbered source text |
| `goto_source` | `scope`, `line` | Selected scope and source line |

Waveform paths use `/tb/dut/signal[3:0]`; source/driver tools use `tb.dut.signal`.
Time strings accept fs, ps, ns, us, ms and s. Sampling accepts Bin, Hex or UDec;
X/Z values stay strings. Requests permit at most 128 signals, 128 times and 1024
signal/time pairs. Source reads permit 1–200 lines inside the configured roots.

`jump_before_error` requires a known, constant clock period. It preserves the error
timestamp's phase; it does not identify a clock, count gated-clock edges or snap to
an edge. Use explicit timestamps for variable or gated clocks.

A driver's returned line is not necessarily the fault. It may be a declaration,
initializer, reset assignment or another site in the driving process. Inspect the
returned source and waveform before drawing a conclusion.

## CLI

Connection settings come from `VERDI_BRIDGE_*` environment variables; see [setup](guide.md).
The CLI names below correspond to Python client methods, so some differ from MCP names.

```sh
uv run verdi-bridge status
uv run verdi-bridge call browse '{"scope":"/tb/dut"}'
uv run verdi-bridge call add_signals '{"signals":["/tb/dut/full"]}'
uv run verdi-bridge call before_error '{"error_time":"435","period":"10","cycles":20}'
uv run verdi-bridge call sample '{"signals":["/tb/dut/full"],"times":["426","436"],"radix":"Bin"}'
uv run verdi-bridge call trace_driver '{"signal":"tb.dut.full"}'
```

`verdi-bridge tcl-path` locates the bundled adapter. `verdi-bridge serve` starts the
MCP stdio server. Invoke `uv run verdi-bridge --help` for the command list.

## Python

```python
from verdi_bridge.client import Client, Config

bridge = Client(Config.from_env())
print(bridge.browse("/tb/dut"))
bridge.add_signals(["/tb/dut/full"])
bridge.before_error("435", "10", cycles=20)
print(bridge.sample(["/tb/dut/full"], ["426", "436"], radix="Bin"))
print(bridge.trace_driver("tb.dut.full"))
```

Use signal names discovered in your design; the snippets above are examples.
`BridgeError` reports transport or Verdi errors. A timeout does not guarantee that
a GUI mutation never executed. Do not automatically retry it without checking state.
