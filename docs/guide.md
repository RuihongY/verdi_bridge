# Getting started

[Home](../README.md) · [Tool reference](tools.md) · [Architecture](architecture.md)

## 1. Install on the client

```sh
pip install verdi-bridge
verdi-bridge tcl-path
```

Keep the printed absolute path to `bridge.tcl`. The Python client requires 3.11+.
Use your existing licensed Verdi environment; this project does not install Verdi
or configure a license server. Recorded runs used Verdi T-2022.06-SP2-1 with Tcl 8.6.11.

## 2. Load the adapter in Verdi

Run these commands **on the Verdi host**. Substitute your source/waveform paths:

```sh
export VERDI_BRIDGE_DIR=$(mktemp -d /tmp/verdi-bridge.XXXXXXXX)
export VERDI_BRIDGE_SOURCE_ROOTS=/absolute/path/to/design
export VERDI_BRIDGE_LOG_ROOTS=/absolute/path/to/simulation-run
printf '%s\n' "$VERDI_BRIDGE_DIR"  # keep this exact directory for the client
verdi -sv design.sv tb.sv -top tb -ssf simulation.fsdb \
  -play /absolute/path/to/bridge.tcl
```

For SSH use, first copy `bridge.tcl` to an existing directory you own on that host:

```sh
scp "$(uvx verdi-bridge tcl-path)" user@eda-host:/absolute/remote/path/bridge.tcl
```

The Verdi host needs Python 3.6+ for the SSH transport helper; it does not need the
MCP Python package. Each GUI needs a separate private bridge directory. The adapter
uses Verdi's event loop and does not open a TCP listener.

`VERDI_BRIDGE_SOURCE_ROOTS` is a colon-separated list of allowed source directories.
If omitted, it defaults to Verdi's working directory. Load the RTL as well as the
waveform to use source and driver tools. Select the intended nWave window when
multiple waveform windows are open.

### Existing GUI

This loading path is implemented but has not been separately validated against an
arbitrary pre-existing user session. Create a private directory on the Verdi host,
then run in Verdi's Tcl console:

```tcl
set env(VERDI_BRIDGE_DIR) /absolute/private/session-directory
set env(VERDI_BRIDGE_SOURCE_ROOTS) /absolute/path/to/design
set env(VERDI_BRIDGE_LOG_ROOTS) /absolute/path/to/simulation-run
source /absolute/path/to/bridge.tcl
```

The directory must already exist with owner-only permissions (0700). Do not load
the adapter twice in the same GUI. To detach, run `::vb::stop` in that Tcl console.

## 3. Check the connection

On the **client**, set the same directory that the host printed in step 2:

```sh
export VERDI_BRIDGE_DIR=/tmp/verdi-bridge.YOUR_SESSION
# Set these only for an SSH connection:
export VERDI_BRIDGE_HOST=user@eda-host
# Optional, when reusing an existing SSH ControlMaster:
export VERDI_BRIDGE_CONTROL_PATH=/tmp/your-ssh-control.sock

uvx verdi-bridge status
```

For a local GUI, omit HOST and CONTROL_PATH. SSH uses BatchMode and normal host-key
verification. Establish working SSH authentication yourself before connecting.
The status result includes the current window, native time unit, cursor, viewport
and displayed signals. A directory existing on disk is not proof the GUI is alive.

## 4. Configure your MCP client

Add a stdio MCP server using uvx (or the installed `verdi-bridge` executable). Replace all
paths and hostnames below. Different clients may wrap this configuration differently.

```json
{
  "mcpServers": {
    "verdi": {
      "command": "uvx",
      "args": ["verdi-bridge==0.3.1", "serve"],
      "env": {
        "VERDI_BRIDGE_DIR": "/tmp/verdi-bridge.YOUR_SESSION",
        "VERDI_BRIDGE_HOST": "user@eda-host",
        "VERDI_BRIDGE_CONTROL_PATH": "/tmp/your-ssh-control.sock"
      }
    }
  }
}
```

Omit HOST and CONTROL_PATH from the JSON for local use. Only the MCP client launches
`serve`; do not paste normal CLI output into its stdio stream.

Try a request with enough context to identify the failure and clock:

> The error occurred at 435 ns and this clock has a 10 ns period. Browse the DUT,
> add the relevant handshake and state signals, move 20 cycles earlier, and explain
> the first divergence using sampled values and source lines.

The assistant selects tools and reasons about evidence. The MCP server does not
run its own LLM or require a model API key. Configure your chosen client appropriately
before sending confidential design data to a model.

## Troubleshooting

| Symptom | What to check |
|---|---|
| `session` file missing | Verdi has not loaded the adapter. Look for startup/license errors or a modal dialog. |
| VCD load hangs | A second load may ask to overwrite the converted FSDB. Resolve the dialog or open `.vcd.fsdb`. |
| Permission error | Use a new `mktemp -d` directory owned by the Verdi user. |
| `gui.lock` exists | Another GUI may own the directory. Use a fresh directory; do not remove an active lock. |
| Signal missing | Browse the containing scope and use the exact name including its bus range. |
| Source unavailable | Load RTL and check the source-root allowlist and Verdi's working directory. |
| Timeout | The GUI may be busy. Inspect its state before retrying: a claimed operation may still complete. |

After a killed GUI, use a new session directory. Old results cannot satisfy new
requests because requests carry unique IDs and a session identifier. Late results
may remain on disk for inspection.

See [the trust boundary](../SECURITY.md) and [tested limitations](validation.md).

## Upgrading

Update both the Python package and the Tcl adapter; restart in a fresh private
GUI/session directory. Existing loaded Tcl does not acquire the new operations
from a Python upgrade. Remote clients reuse one SSH/helper by default; set
`VERDI_BRIDGE_PERSISTENT=0` for the previous one-shot transport.

`VERDI_BRIDGE_LOG_ROOTS` is an independent colon-separated allowlist for `read_log`.
Both root lists default to the GUI working directory; keep them narrow.
`VERDI_BRIDGE_POLL_MS` defaults to 10 ms (range 1–1000) on each side. Set it
in both environments if changing both the Tcl and helper polling intervals.


## Develop from source

```sh
git clone https://github.com/RuihongY/verdi_bridge.git
cd verdi_bridge
uv sync
uv run verdi-bridge tcl-path
```

When using uvx, pin the same version for `tcl-path` and `serve`; copy the adapter
again when upgrading. See the [changelog](../CHANGELOG.md) for migration notes.
