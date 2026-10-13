# Working in this repository

Verdi Bridge connects an MCP client to a licensed, live Verdi GUI. Start with
README.md, docs/architecture.md and docs/tools.md.

- Keep tool arguments as data. Do not add arbitrary Tcl or shell evaluation to MCP.
- Consult installed vendor documentation before introducing Verdi API calls.
  Do not redistribute vendor documentation, binaries or license settings.
- Preserve request IDs, session checks, source-root boundaries and timeout semantics.
- Keep core operations independent of any particular RTL module or testbench.
- Distinguish simulator doubles from real-Verdi validation. Record the vendor version.
- A driver location is not a fault label. Known injected mutations are not blind accuracy.
- Keep upstream revision, hash and license notices with benchmark fixtures.
- Exclude credentials, personal hostnames, runtime directories, FSDB/VCD and proprietary RTL
  from commits. Public benchmark traces and logs are intentionally retained in docs/evidence.

Run `uv sync`, `uv run pytest`, `uv run ruff check .`, and `uv build` for code changes.
Documentation changes need link/example checks; they do not require rerunning licensed
simulation. Real EDA experiments require an explicitly authorized, licensed environment.
