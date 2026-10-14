# Validation results and limits

[Home](../README.md)

Verdi Bridge adds access to simulation observations and GUI navigation. These
records distinguish working tool integration from measured improvements in agent
diagnosis. No accuracy or agent call-count improvement is established so far.

| Record | What it establishes |
|---|---|
| [Original FIFO validation](validation.md) | Real MCP/Verdi integration and two known injected faults |
| [UART, AXI-Lite and arbiter](multidesign-validation.md) | 27 baseline/mutant/repaired simulation runs with known faults |
| [Three-case blind trial](blind-validation.md) | Fresh-context diagnosis of three injected statements; no RTL-only arm |
| [Eight-case paired pilot](paired-pilot.md) | Both arms located 8/8; the bridge-enabled arm used no tools |
| [Interval semantics](interval-validation.md) | Vendor transition API observations, including a distinct-timestamp narrow pulse |
| [v0.3 hardening](hardening-validation.md) | Exact ticks, bounded queries, independent roots and measured transport latency |
| [Larger paired protocol](paired-evaluation.md) | Planned held-out comparison; not a completed experiment |

The paired pilot reached a ceiling on small, conspicuous mutations. It cannot
show that wave access improves diagnosis. All outcomes, exclusions and traces
remain in the linked reports. The bridge returns observations, not fault labels.

The recorded environment used licensed Verdi T-2022.06-SP2-1 on Linux with a macOS
client. Arbitrary pre-existing GUI attachment has not been separately validated.
The vendor search API skips glitches, so same-timestamp/delta-cycle completeness
is not promised. Query budgets are cooperative; a blocking vendor call cannot be
interrupted. See [tool semantics](tools.md) for exact boundaries and truncation.
