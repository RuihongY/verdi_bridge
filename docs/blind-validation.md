# Independent-agent blind diagnosis

On 2026-10-13, a separate injector prepared three new single-statement bugs in
open-source UART, AXI-Lite and round-robin arbiter RTL. An independent diagnostic
agent started without conversation history or mutation locations. Its first-ranked
diagnosis matched the injected statement and cause in **3/3 cases**. Applying its
submitted repairs produced **9/9 passing simulations**.

| Case | Fault identified before reveal | Observed waveform evidence | Repaired seeds 1 / 7 / 42 |
|---|---|---|---|
| A: arbiter | `arbiter.v:119`: masked winner uses unmasked encoded index | At 56 ns, one-hot grant is `0x2` but encoded grant is `0`; at 54 ns, masked index is `1` while next encoded grant is `0` | Pass / Pass / Pass |
| B: UART | `uart_tx.v:97`: preload concatenation puts padding below payload | Input `0x35` becomes shift-register `0x6b` at 56 ns; eight serial data samples decode as `0x6b` | Pass / Pass / Pass |
| C: AXI-Lite | `axil_reg_if_wr.v:122`: incoming WSTRB replaced with all ones | Input strobe is `1` at 74 ns; backend write strobe is `0xf` at 76 and 84 ns, with correct address/data | Pass / Pass / Pass |

These are different mutations from the [earlier known-mutation experiment](multidesign-validation.md).
Upstream revisions, hashes, exact injected statements and tests are recorded in
the revealed [ground truth](evidence/blind-20261013/ground-truth.json).

## Procedure and results

The injector first verified nine clean baseline runs and nine failing mutant runs
using the existing independent testbenches and seeds 1, 7 and 42. No testbench edits
were needed. Cases were fixed before diagnosis began. The diagnostic agent received
only mutated RTL, testbenches, error logs, waveforms and generic bridge instructions.
Reading baseline RTL, previous reports, repository history, upstream sources and
the private mutation manifest was prohibited.

It inspected source and then adaptively chose signals and sample times through
three live Verdi sessions. Its six recorded MCP sessions made **21 tool calls**, all
successful: status, scope discovery, adding signals, jumping before errors, sampling,
driver tracing and reading source. Each case used seven calls. This was agent-selected
debugging; the recorder only transported calls and saved results.

The coordinator froze the diagnosis and proposed patches with SHA256 before opening
the injector's manifest. Diagnosis SHA256:
`415cc4bc835ee6ab40a6526713c7182d83f0ffbb904ee5fe2e1b5f61da4e04f4`.
The submitted replacements were applied without substituting oracle fixes. All
nine repaired runs passed, and the repaired source hashes matched the original
upstream files. The complete experiment comprised 27 simulations: baseline 9 pass,
mutant 9 fail, repaired 9 pass. UART and AXI-Lite completed 12 transactions per run;
the arbiter checked 100 rounds per run.

VCS was U-2023.03-SP2_Full64; Verdi was T-2022.06-SP2-1. The original injector manifest
has a VCS version-label typo; the evaluation uses the compile-log version.
See the [frozen diagnosis](evidence/blind-20261013/diagnosis/diagnosis.json),
[MCP plans and transcripts](evidence/blind-20261013/diagnosis/),
[simulation evaluation](evidence/blind-20261013/evaluation.json) and
[protocol](evidence/blind-20261013/protocol.md). Published copies redact machine paths;
the recorded freeze hashes apply to the original local copies.

## What this establishes

The agent localized three previously undisclosed injected bugs and supported its
repairs with real waveform observations. Driver tracing alone did not identify the
fault: it returned an output assignment or register declaration, so source inspection
and causal interpretation were necessary. AXI-Lite evidence explicitly distinguishes
the checker’s pre-NBA observation at 85 ns from the settled waveform at that timestamp.

This is procedural blindness on a shared filesystem, with a fresh agent context and
an access audit, not OS-enforced isolation. Three small, single-site faults do not
establish general accuracy, large-design performance, or absence of model familiarity
with public RTL. Testbenches were reused and supplied specific failure messages.
Source was read before waveform selection; no RTL-only control was run, so this
experiment cannot measure the incremental benefit of the waveform bridge. Seeds
exercise the same three bugs, not nine independent bugs. No separate FSM was tested.

A stronger follow-up would use larger multi-module cases and a matched RTL-plus-log
control, with equal budgets and withheld tests. This run demonstrates that the bridge
supports a working diagnosis loop; it does not show that waveform access is necessary
for these particular faults.
