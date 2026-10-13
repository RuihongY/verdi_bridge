# Verdi Bridge

A small open-source MCP server for controlling a live, licensed Synopsys Verdi GUI.
Version 0.1.1. Experimental; tested with Verdi T-2022.06-SP2-1 on Linux.

Ask your MCP-enabled assistant: “Add the FIFO read/write pointers, go 20 cycles
before this error, and investigate why full stayed asserted.” The assistant calls
typed tools and reasons from returned waveform values and RTL. The bridge itself
is not an autonomous root-cause engine.

## Install

Python 3.11+ locally; Tcl 8.6 in Verdi; remote Python 3.6+ if using SSH.

```sh
uv sync
uv run verdi-bridge tcl-path
```

## Start or attach

On the Verdi host, create a fresh private directory for each GUI session:

```sh
export VERDI_BRIDGE_DIR=$(mktemp -d /tmp/verdi-bridge.XXXXXXXX)
export VERDI_BRIDGE_SOURCE_ROOTS=/absolute/path/to/design
verdi -sv design.sv tb.sv -top tb -ssf simulation.fsdb -play /path/to/bridge.tcl
```

For an existing GUI, set `env(VERDI_BRIDGE_DIR)` and
`env(VERDI_BRIDGE_SOURCE_ROOTS)` in its Tcl console, then
`source /path/to/bridge.tcl`. Load RTL and waveform first. The adapter controls the
current nWave window; select the intended window when multiple are open.

The Tcl file is bundled in the wheel (`verdi-bridge tcl-path`). Copy it to the
Verdi host when running the Python server on a different machine. Use your normal
licensed EDA environment. No proprietary libraries or license are included.

## Connect an MCP client

Configure a generic stdio MCP server (replace all paths):

```json
{
  "mcpServers": {
    "verdi": {
      "command": "/absolute/path/to/verdi-bridge/.venv/bin/verdi-bridge",
      "args": ["serve"],
      "env": {
        "VERDI_BRIDGE_DIR": "/tmp/verdi-bridge.YOUR_SESSION",
        "VERDI_BRIDGE_HOST": "user@eda-host",
        "VERDI_BRIDGE_CONTROL_PATH": "/tmp/your-ssh-control.sock"
      }
    }
  }
}
```

Omit HOST and CONTROL_PATH for a local GUI/shared filesystem. SSH uses existing
credentials, BatchMode and host-key verification; it never asks an LLM for passwords.
Before MCP use, run `verdi-bridge status` with the same environment.

## Tools

| Tool | Purpose |
|---|---|
| session_status | Current window, cursor, viewport, time units, displayed signals |
| browse_scope | Discover scopes and exact waveform signal paths |
| add_signals | Add up to 128 signals |
| set_cursor / set_time_window | Move/zoom with explicit physical time units |
| jump_before_error | Offset by a known constant clock period |
| sample_signals | Read values at specified times; keep X/Z values as strings |
| trace_driver | Find the driving RTL process |
| read_source / goto_source | Read numbered RTL lines / navigate source GUI |

Waveform names use `/tb/dut/signal[3:0]`; source operations use `tb.dut.signal`.
Time units are fs/ps/ns/us/ms/s. Clock offsets preserve the error's phase and clamp
at zero; gated clocks and variable periods require explicit sample timestamps.
Read-source access is restricted to colon-separated source roots (default: GUI cwd).

## Validation and limitations

See the [UART / AXI-Lite / arbiter results](docs/multidesign-validation.md):
27 VCS runs across three designs, baseline/mutant/repaired variants, and three seeds.
All baseline and repaired runs passed; every mutant was detected. Seed-1 cases were
inspected through real MCP and Verdi. These are known mutations, not blind evaluation.

The [original validation record](docs/validation.md) and
[FIFO benchmark](examples/axis_fifo/README.md) are retained.
Run `uv run pytest` and `uv run ruff check .` without a vendor license. Protocol tests
use a Tcl simulator double; they do not replace the documented real-Verdi runs.

The bridge has no generic eval/exec tool and does not compile, edit RTL, or close
Verdi through MCP. Mutating tools affect the GUI only. Source text and waveform
values can leave your machine through your chosen LLM client; configure that client
for your design's data policy.

Requests use atomic files, unique IDs, session binding and a single GUI consumer.
A timeout is not proof a GUI action did not execute: inspect status before retrying.
The private directory is a same-user trust boundary, not an isolation sandbox.
Do not share it with untrusted processes. There is no TCP listener.

To detach, execute `::vb::stop` in Verdi's Tcl console. A killed GUI may leave its
lock behind: prefer a new session directory. Remove an old lock only after verifying
that its GUI is no longer running. Late responses may remain in the old directory.

Independent community project; not affiliated with or endorsed by Synopsys.
Verdi is a Synopsys trademark. MIT license applies to this project's code, not Verdi.

For VCD input, Verdi may convert it to FSDB. On subsequent launches, opening the
existing `.vcd.fsdb` avoids an overwrite confirmation dialog that can block `-play`.
See [troubleshooting](docs/validation.md#troubleshooting).
