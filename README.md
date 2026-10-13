<p align="center">
  <img src="assets/banner.svg" alt="Verdi Bridge — connect AI agents to your live Verdi session" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/RuihongY/verdi_bridge/actions/workflows/test.yml"><img src="https://github.com/RuihongY/verdi_bridge/actions/workflows/test.yml/badge.svg" alt="Tests" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license" /></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11 or newer" /></a>
</p>

<p align="center">
  <a href="docs/guide.md"><b>Getting started</b></a> ·
  <a href="docs/tools.md">Tool reference</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="README.zh-CN.md">中文</a>
</p>

Let an AI agent inspect waveforms, trace signal drivers, and navigate RTL in a
**live Synopsys Verdi session**, locally or over SSH.

> “Add the FIFO read/write pointers, go 20 cycles before the error, and investigate why full stayed high.”
>
> “Why did this AXI-Lite response disappear before BREADY?”

The agent reasons about the design. Verdi Bridge provides ten typed MCP tools that
return waveform values and source evidence while operating the GUI you can inspect.

## Video walkthrough

Ask an agent to investigate a bug, then watch it choose signals, inspect live waveforms and navigate RTL. A 1m38s silent demo: an English prompt and original English agent replies beside synchronized Verdi capture. This is a separate English-language run, not a translation. Tool calls are selected by the agent, not a replay script.

https://github.com/user-attachments/assets/b041c1bd-4be5-4040-b281-2f15001b1e35

[English video](https://github.com/user-attachments/assets/b041c1bd-4be5-4040-b281-2f15001b1e35) · [中文视频](https://github.com/user-attachments/assets/3294e374-5c43-4b67-8e20-b8a6f319d8f7)

[How this was recorded](docs/agent-demo.md) · [Installation tutorial](docs/video-walkthrough.md)

## Quick start

```sh
git clone https://github.com/RuihongY/verdi_bridge.git
cd verdi_bridge
uv sync
uv run verdi-bridge tcl-path   # adapter to load in your Verdi session
```

Next, [load the adapter and connect your MCP client](docs/guide.md).
You need a licensed Verdi installation; no vendor software is bundled.
Python 3.11+ runs on the client; an SSH host only needs Python 3.6+ and Verdi's Tcl 8.6.
The package is installed from this repository, not a published PyPI release.

## What you can do

| Workflow | Tools |
|---|---|
| Find and display signals | `browse_scope`, `add_signals` |
| Navigate an error window | `set_cursor`, `set_time_window`, `jump_before_error` |
| Inspect actual waveform values | `sample_signals`, `session_status` |
| Follow drivers into RTL | `trace_driver`, `read_source`, `goto_source` |

Waveform queries preserve X/Z values. Time arguments carry explicit units.
The same interface works with different RTL designs; no FIFO-specific logic is
built into the bridge. See the [Python and CLI examples](docs/tools.md).

## Tested on real RTL

UART TX, an AXI-Lite write interface, and a round-robin arbiter were tested using
VCS and Verdi. Across **27 simulation runs**, all nine baseline runs passed, all
nine injected-bug runs failed their checkers, and all nine repaired runs passed.
The seed-1 cases were inspected through real MCP calls and a live Verdi GUI.

| Design | Observed fault |
|---|---|
| UART | A short frame counter entered the stop bit too early |
| AXI-Lite | BVALID disappeared while BREADY was low |
| Arbiter | The rotation mask was cleared instead of stored |

[Evidence and screenshots](docs/multidesign-validation.md) ·
[Reproduce these experiments](examples/multidesign/README.md) ·
[Earlier FIFO cases](examples/axis_fifo/README.md)

These are **known, locally injected mutations**, not upstream defects or a blinded
accuracy benchmark. Driver tracing can return an initializer rather than the fault;
source inspection and waveform reasoning remain necessary.

A separate [independent-agent blind trial](docs/blind-validation.md) used three
new bugs: the fresh-context diagnostician identified all three exact statements
with 21 live MCP calls, and its proposed repairs passed 9/9 runs. Answers were
frozen before revealing mutations. This was procedural isolation on a shared
filesystem, a small trial with no RTL-only comparison.

<details>
<summary>View a real Verdi debugging session</summary>

![UART waveform and source in Verdi](docs/evidence/multidesign/uart-multidesign.png)

</details>

## Project status

Experimental **v0.1.1**. Tested with Verdi T-2022.06-SP2-1 on Linux.
New-session startup is verified; attachment to an arbitrary existing GUI is not yet
separately validated. The bridge does not automatically compile, edit or repair RTL.

[Contributing](CONTRIBUTING.md) · [Trust boundary](SECURITY.md) ·
[Validation limits](docs/validation.md) · [Report an issue](https://github.com/RuihongY/verdi_bridge/issues)

Inspired by the agent-to-EDA-tool workflow of
[virtuoso-bridge-lite](https://github.com/Arcadia-1/virtuoso-bridge-lite).
This is an independent implementation. MIT licensed; see [third-party notices](NOTICE).
Not affiliated with Synopsys. Verdi is a Synopsys trademark.
