# Contributing

Use Python 3.11+ and Tcl 8.6+. Run `uv sync`, `uv run pytest`, and
`uv run ruff check .`. Package with `uv build`.

Add tests for argument escaping, session/race behavior and time units when changing
the transport. Test vendor API changes on a real licensed Verdi instance and record
the exact version. The fake GUI tests only our protocol, not Synopsys behavior.
Do not add generic Tcl evaluation to the MCP surface.

Bug reports should include tool name, sanitized arguments, Verdi version, native time
unit, and expected/observed results. Do not upload proprietary RTL, FSDB files,
license server settings, credentials, or vendor documentation.

Benchmark additions need a pinned source revision, compatible license, passing
baseline, independent checker, deterministic mutation and honest diagnosis record.
Report missing evidence and failed cases. Keep mutation ground truth separate from
future blinded diagnosis inputs. A replay script is not a new LLM evaluation.
