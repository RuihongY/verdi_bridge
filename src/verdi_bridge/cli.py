import argparse
import json
from pathlib import Path

from .client import Client, Config


def main():
    parser = argparse.ArgumentParser(description="Live Verdi MCP bridge")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="Run MCP over stdio")
    sub.add_parser("status", help="Check connection using VERDI_BRIDGE_* environment")
    sub.add_parser("tcl-path", help="Print bundled bridge.tcl path")
    call = sub.add_parser("call", help="Call a typed client operation with JSON keyword args")
    call.add_argument("operation", choices=["browse", "add_signals", "set_cursor", "set_window",
                                           "before_error", "sample", "trace_driver", "source",
                                           "goto_source", "find_transitions", "get_value_changes",
                                           "find_signals", "measure_clock", "source_file", "read_log"])
    call.add_argument("arguments", nargs="?", default="{}")
    args = parser.parse_args()
    if args.command == "tcl-path":
        print(Path(__file__).with_name("bridge.tcl"))
    elif args.command == "serve":
        from .server import create_server
        create_server().run(transport="stdio")
    else:
        with Client(Config.from_env()) as client:
            result = (client.status() if args.command == "status" else
                      getattr(client, args.operation)(**json.loads(args.arguments)))
            print(json.dumps(result, indent=2))
