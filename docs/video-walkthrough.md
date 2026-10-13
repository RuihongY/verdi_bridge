# Video walkthrough

[Home](../README.md) · [Setup guide](guide.md) · [Tool arguments](tools.md)

https://github.com/user-attachments/assets/19017ecd-0095-46d3-86dd-f408385808f3

This 1m46s silent tutorial combines setup instructions with a continuous, roughly
2.5 fps recording of an actual licensed Verdi T-2022.06-SP2-1 GUI. Captions identify
the calls being executed. Temporary source/database paths are redacted. The video
replays a known injected UART bug with scripted MCP calls; it is not an AI chat
recording or a fresh blind test. No GUI state or waveform was synthesized.

| Time | Step |
|---|---|
| 00:00 | Install the Python client |
| 00:09 | Load the adapter on the Verdi host |
| 00:21 | Configure the MCP client |
| 00:33 | 01  Connect to the live session |
| 00:39 | 02  Discover exact signal names |
| 00:45 | 03  Add UART signals to nWave |
| 00:52 | 04  Show the first UART frame |
| 00:58 | 05  Go 20 cycles before the error |
| 01:04 | 06  Inspect the failing bit |
| 01:10 | 07  Query actual waveform values |
| 01:17 | 08  Trace the register driver |
| 01:23 | 09  Read the loading logic |
| 01:30 | 10  Navigate to the faulty statement |

Follow the [setup guide](guide.md) for copyable installation commands, host setup,
SSH options and the complete MCP configuration. Replace the example paths and
use the exact session directory created on your Verdi host. For local use, omit
`VERDI_BRIDGE_HOST`; an SSH host needs Python 3.6+ and working authentication.

Once connected, ask your MCP-enabled assistant:

> The UART checker failed at 455 ns and the clock period is 10 ns. Browse the DUT,
> add the payload, handshake, TX output and shift register, then go 20 cycles
> before the error. Compare sampled values and inspect the logic loading the
> shift register. Explain the cause using observed values and source lines.

The shown jump lands at 255 ns. Input `0x35` becomes `0x06b` in the shift register
at 56 ns. Source line 97 places padding below the payload. The bridge retrieves
values and operates Verdi; interpretation belongs to the assistant. Driver trace
can return a declaration, so source inspection is still necessary.

All ten recorded MCP calls succeeded. Inspect the
[actual call transcript](evidence/video-walkthrough/mcp-transcript.json).
The source and mutation are documented in the [blind trial](blind-validation.md).
The recording does not apply a repair or run a simulation. Its replayed diagnosis
had previously passed the independent repair checks reported there.

[Watch on GitHub](https://github.com/RuihongY/verdi_bridge/issues/1) ·
[Download MP4](https://github.com/user-attachments/assets/19017ecd-0095-46d3-86dd-f408385808f3)
