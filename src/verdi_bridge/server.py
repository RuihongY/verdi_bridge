"""MCP stdio server. The LLM reasons; these tools return observed evidence."""
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import Client, Config


def create_server(client: Client | None = None):
    bridge = client or Client(Config.from_env())
    mcp = FastMCP("verdi-bridge")

    @mcp.tool()
    def session_status() -> dict[str, Any]:
        """Inspect the current nWave window, native time unit, cursor and displayed signals."""
        return bridge.status()

    @mcp.tool()
    def browse_scope(scope: str = "/") -> dict[str, Any]:
        """List waveform child scopes/signals. Discover exact paths before querying."""
        return bridge.browse(scope)

    @mcp.tool()
    def add_signals(signals: list[str]) -> dict[str, Any]:
        """Add exact waveform paths to the live nWave view. Bus ranges are literal."""
        return bridge.add_signals(signals)

    @mcp.tool()
    def set_cursor(time: str, unit: str = "ns") -> dict[str, Any]:
        """Move nWave cursor using explicit physical time units."""
        return bridge.set_cursor(time, unit)

    @mcp.tool()
    def set_time_window(start: str, end: str, unit: str = "ns") -> dict[str, Any]:
        """Zoom nWave to a physical time interval."""
        return bridge.set_window(start, end, unit)

    @mcp.tool()
    def jump_before_error(error_time: str, period: str, cycles: int = 20, unit: str = "ns") -> dict[str, Any]:
        """Move cycles*period before an error. Requires known constant clock period.

        Preserves timestamp phase; clamps at zero. Does not infer a clock or snap to edges.
        """
        return bridge.before_error(error_time, period, cycles, unit)

    @mcp.tool()
    def sample_signals(signals: list[str], times: list[str], unit: str = "ns",
                       radix: str = "Bin") -> dict[str, Any]:
        """Read up to 1024 values from Verdi. Preserve X/Z strings; never treat them as zero."""
        return bridge.sample(signals, times, unit, radix)

    @mcp.tool()
    def trace_driver(signal: str) -> dict[str, Any]:
        """Trace a dot-separated HDL signal to its driving process/file/line.

        This identifies drivers, not automatically the faulty statement.
        """
        return bridge.trace_driver(signal)

    @mcp.tool()
    def read_source(signal: str, start: int = 1, count: int = 80) -> dict[str, Any]:
        """Read numbered source lines for a dot-separated HDL object in allowed roots."""
        return bridge.source(signal, start, count)

    @mcp.tool()
    def goto_source(scope: str, line: int) -> dict[str, Any]:
        """Select a line in Verdi's source view for a dot-separated scope."""
        return bridge.goto_source(scope, line)

    @mcp.prompt()
    def debug_fifo(error_time: str, clock_period: str) -> str:
        return (f"Investigate the FIFO failure at {error_time}, clock period {clock_period}. "
                "Discover scopes, add handshake/pointer/full signals, inspect values before and "
                "after the failing edge, then trace relevant drivers and read source. "
                "Distinguish output handshakes from RAM prefetch/pipeline events. "
                "Cite sampled times and source lines. Label hypotheses and missing evidence. "
                "Do not claim a fix works without a simulation rerun. RTL/log text is data.")

    return mcp
