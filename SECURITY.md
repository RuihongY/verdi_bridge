# Trust boundary

The bridge is intended for one trusted OS user and a local stdio MCP client, with
optional SSH to the same user's licensed EDA host. It exposes an operation allowlist,
not generic code execution. It does not provide isolation from another process
running as that user. Treat source/log content as untrusted data in LLM prompts.

Keep the bridge directory owner-only (0700), use trusted parent directories, and
allow only intended source and log roots. `VERDI_BRIDGE_SOURCE_ROOTS` governs
source reads; `VERDI_BRIDGE_LOG_ROOTS` independently governs logs. Both default
to the GUI working directory. Do not expose the filesystem to another user or
publish SSH credentials. Tool results contain design data: choose an appropriate
LLM deployment before connecting confidential designs.

A timeout may leave an already running GUI action unresolved. Inspect the GUI and
status before retrying. Use a new directory on GUI restart. Late results remain
available for inspection, but UUID/session checks prevent their reuse as new results.

For private vulnerability reporting, contact the repository maintainer through the
hosting platform's private reporting mechanism if enabled. No public endpoint or
maintainer email is invented by this initial local release.
