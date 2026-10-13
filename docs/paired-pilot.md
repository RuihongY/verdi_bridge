# Eight-mutation paired pilot — 2026-10-13

[Home](../README.md) · [Larger evaluation protocol](paired-evaluation.md) ·
[Evidence](evidence/paired-pilot-v0.3/) · [Reproduction](../examples/paired_pilot/README.md)

**Both arms localized 8/8 exact fault statements. Neither arm used any tools.**
Giving the model access to Verdi did not improve accuracy in this pilot. The
mutations were apparent enough from the small RTL modules and checker logs that
the model answered without inspecting waves. This is a ceiling result, not
validation that interval tools improve agent diagnosis or reduce agent calls.

## Conditions and isolation

- A received numbered mutated RTL, testbench, and the complete seed-1 simulation log.
- B received the identical prompt plus all sixteen bridge tools connected to a
  fresh licensed Verdi session for that case. Tool use was optional in both arms.
- Codex CLI 0.147.0; model alias `gpt-5.6-sol`; medium reasoning; fresh ephemeral
  context; 240-second wall limit per diagnosis. The provider's immutable model
  snapshot was not exposed. No custom token cap was set; token usage is recorded.
- Paired order was randomized with seed 20261013, with two case pairs in flight.
  GUI startup was outside the diagnosis timer. Reported times include CLI/MCP startup.
- Shell, browser, apps, plugins, skills search, image tools and agent delegation
  were disabled; web search was disabled. Working directories were empty, repository
  instruction loading disabled, and user configuration ignored. The case inputs
  were embedded in the prompt. B's source/log roots were restricted to its case.
- The mutation manifest was not supplied to diagnosticians. This was procedural
  tool/context isolation on a shared host, not an OS-level confidentiality boundary.
  Now-public inputs must not be reused as undisclosed test cases.

A separate infrastructure-only [MCP smoke test](evidence/hardening-v0.3/mcp-smoke.jsonl)
successfully called `session_status` using the same CLI/tool configuration.
Therefore zero diagnostic tool calls is an observed model choice, not evidence
that the MCP server was absent. The smoke test is excluded from diagnosis metrics.

The initial requested alias `gpt-6-astra` was rejected by this CLI before inference
in all sixteen attempts. These [infrastructure failures](evidence/paired-pilot-v0.3/infrastructure-failures.json)
are retained separately. A compatibility preflight then passed, and all sixteen
scored runs used `gpt-5.6-sol`; no diagnosis was selectively rerun.

## Frozen cases and simulation checks

Sources use the same pinned upstream revisions and MIT notices as the existing
[multidesign fixtures](../examples/multidesign/README.md). This pilot introduced
new mutations, without reusing the earlier blind trial's changes.

| Case | Design | Mutation | Exact fault | A | B |
|---|---|---|---|---|---|
| 01 | UART | Doubled start-bit prescaler | uart_tx.v:95 | Correct | Correct |
| 02 | UART | Additional right shift skips payload bits | uart_tx.v:105 | Correct | Correct |
| 03 | UART | Stop bit driven low | uart_tx.v:109 | Correct | Correct |
| 04 | AXI-Lite | Captured address XOR 4 | axil_reg_if_wr.v:115 | Correct | Correct |
| 05 | AXI-Lite | Captured data halfwords swapped | axil_reg_if_wr.v:121 | Correct | Correct |
| 06 | AXI-Lite | Response creation depends on BREADY | axil_reg_if_wr.v:111 | Correct | Correct |
| 07 | Arbiter | Encoded winner XOR 1 | arbiter.v:146 | Correct | Correct |
| 08 | Arbiter | One-hot grant shifted right | arbiter.v:144 | Correct | Correct |

VCS U-2023.03-SP2_Full64 simulation screening used seeds 1, 7 and 42:
**9/9 baseline passes and 24/24 accepted-mutant detections**. These are 8 bugs,
not 24 independent bugs. One earlier shortened-start-bit candidate escaped the
checker on all three seeds and was excluded **before model diagnosis**; its RTL
and logs are retained. In total, screening included 36 simulation runs.
No repair simulations were performed for this diagnosis-only pilot.

The [manifest freeze](evidence/paired-pilot-v0.3/freeze.json) precedes inference.
[Answer hashes](evidence/paired-pilot-v0.3/answers-freeze.json) were frozen before
scripted exact-file/line scoring. Explanations are published for inspection; no
separate arm-blinded causal grader was run.

## Measurements and limits

| Metric | A: RTL + testbench + log | B: same + Verdi tools |
|---|---:|---:|
| Exact statement / file localization | 8/8 | 8/8 |
| Total diagnostic tool calls | 0 | 0 |
| Median diagnosis wall time | 9.45 s | 10.42 s |
| Diagnosis errors / timeouts | 0 / 0 | 0 / 0 |

[Per-case results and tokens](evidence/paired-pilot-v0.3/evaluation.json) and
[public event traces / answers](evidence/paired-pilot-v0.3/runs/) preserve all
scored outcomes. Private runtime paths are redacted; internal reasoning is not
published. Each case's `prompt.txt` is the identical input used in A and B.

The CLI exposes one user turn and final responses, not a reliable count of internal
model reasoning rounds. We therefore report final-answer correctness, not an
invented “first correct reasoning round.” All eight pairs agree; this small,
correlated, saturated sample cannot establish a general accuracy benefit or lack
of benefit. Wall-time differences are descriptive and include model variability.
There was no point-only arm, so this also does not isolate interval-tool value.

The next held-out set should include less conspicuous control/timing faults,
longer traces and larger RTL contexts with multiple plausible causes, with its
selection rules fixed before diagnosis. Keep this pilot in the development set.
Forcing wave calls on these disclosed cases would test integration, not establish
that agents naturally debug better with the bridge.
