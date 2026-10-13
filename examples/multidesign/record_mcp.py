"""Record arbitrary MCP tool calls from a JSON plan, with no design-specific logic.

This is a reproducible tool-call recorder, NOT an autonomous diagnosis algorithm.
Plans are selected by the investigator; every argument and response is retained.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def record(plan, destination):
    transcript = {"method": "investigator-selected MCP calls", "calls": []}
    params = StdioServerParameters(command=sys.executable,
        args=["-c", "from verdi_bridge.cli import main; main()", "serve"], env=dict(os.environ))
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                transcript["tools"] = [t.name for t in (await session.list_tools()).tools]
                for call in plan:
                    result = await session.call_tool(call['tool'], call.get('arguments', {}))
                    entry = {**call, "is_error": result.isError, "result": result.structuredContent}
                    if result.structuredContent is None:
                        entry['content'] = [c.model_dump() for c in result.content]
                    transcript['calls'].append(entry)
                    if result.isError:
                        raise RuntimeError(f"Tool failed: {call['tool']}")
    finally:
        Path(destination).write_text(json.dumps(transcript, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('plan')
    parser.add_argument('output')
    args = parser.parse_args()
    asyncio.run(record(json.loads(Path(args.plan).read_text()), args.output))
