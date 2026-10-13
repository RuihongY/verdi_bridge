"""Replay an explicitly selected investigation using a real MCP stdio client.

This is an evidence recorder, not an autonomous diagnostic agent or blind test.
Connection configuration comes from VERDI_BRIDGE_* environment variables.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SIGNALS = ["/tb/clk", "/tb/rst", "/tb/dut/wr_ptr_reg[3:0]", "/tb/dut/rd_ptr_reg[3:0]",
           "/tb/dut/full", "/tb/dut/empty", "/tb/s_axis_tvalid", "/tb/s_axis_tready",
           "/tb/m_axis_tvalid", "/tb/m_axis_tready", "/tb/m_axis_tdata[7:0]",
           "/tb/dut/pipe_ready", "/tb/dut/m_axis_tready_pipe"]


async def capture(args):
    output = {"method": "explicit evidence replay; not autonomous diagnosis"}
    params = StdioServerParameters(command=sys.executable,
        args=["-c", "from verdi_bridge.cli import main; main()", "serve"], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            output["tools"] = [t.name for t in (await session.list_tools()).tools]

            async def call(label, name, **kwargs):
                result = await session.call_tool(name, kwargs)
                if result.isError or result.structuredContent is None:
                    raise RuntimeError(str(result))
                output[label] = result.structuredContent

            await call("status", "session_status")
            await call("discovery", "browse_scope", scope="/tb/dut")
            await call("add", "add_signals", signals=SIGNALS)
            await call("jump", "jump_before_error", error_time=args.error_time, period="10", cycles=20)
            await call("zoom", "set_time_window", start="0", end=args.window_end)
            await call("samples", "sample_signals", signals=SIGNALS[2:], times=args.times, radix="UDec")
            await call("driver", "trace_driver", signal=args.signal)
            await call("source", "read_source", signal=args.signal, start=args.start_line, count=36)
            await call("navigate", "goto_source", scope="tb.dut", line=args.line)
    Path(args.output).write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output["driver"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--signal", required=True)
    parser.add_argument("--line", type=int, required=True)
    parser.add_argument("--start-line", type=int, required=True)
    parser.add_argument("--error-time", required=True)
    parser.add_argument("--times", nargs="+", required=True)
    parser.add_argument("--window-end", default="500")
    parser.add_argument("--output", required=True)
    asyncio.run(capture(parser.parse_args()))
