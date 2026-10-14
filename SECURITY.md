# Trust boundary

The bridge is intended for one trusted OS user and a local stdio MCP client, with
optional SSH to the same user's licensed EDA host. It exposes an operation allowlist,
not generic code execution. It does not provide isolation from another process
running as that user. Treat source/log content as untrusted data in LLM prompts.

Keep the bridge directory owner-only (0700), use trusted parent directories, and
allow only intended source and log roots. `VERDI_BRIDGE_SOURCE_ROOTS` governs
source reads; `VERDI_BRIDGE_LOG_ROOTS` independently governs logs. Both default
to the GUI working directory, except that `/` and any directory containing `$HOME`
are never used as roots, so a GUI started from the home directory cannot expose
`~/.ssh` or similar files to a prompt-injected request. Do not expose the filesystem to another user or
publish SSH credentials. Tool results contain design data: choose an appropriate
LLM deployment before connecting confidential designs.

The optional NPI engine runs as the same user on the Verdi host, reads only the FSDB
open in the active nWave window, and receives `VERDI_HOME` and the license variables
of the Verdi process. It may check out a Verdi license while it runs; it exits after
each request. It runs under an address-space limit and keeps vendor side files in
an owner-only directory under the system temporary directory, removing those of
engine processes that no longer exist. Set `VERDI_BRIDGE_ENGINE=gui` to disable it.

A timeout may leave an already running GUI action unresolved. Inspect the GUI and
status before retrying. Late results remain available for inspection until the
next GUI start, which removes them; UUID/session checks prevent their reuse as new results.

For private vulnerability reporting, contact the repository maintainer through the
hosting platform's private reporting mechanism if enabled. No public endpoint or
maintainer email is invented by this initial local release.
