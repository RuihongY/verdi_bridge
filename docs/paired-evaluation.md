# Paired RTL-only versus live-Verdi evaluation protocol

[Home](../README.md) · [Existing blind trial](blind-validation.md)

**Status: planned, not a reported accuracy result.** The three existing blind
cases are already disclosed. Reusing them tests integration, not fresh blindness.
A count of 20–30 alone does not establish statistical significance; diversity,
independence, effect size and uncertainty matter.

## Freeze before running

Use 24 fresh mutations: eight UART, eight AXI-Lite, eight arbiter/FSM. Cover different
fault mechanisms, not only constants at one line. Pin upstream commits and fixture
hashes. Keep each original/replacement pair, exact fault lines, seed and oracle in
a manifest inaccessible to the diagnostician. Compile and run each candidate:
exclude compile failures, equivalent/undetected mutants and nondeterministic cases
before either evaluation arm sees them. Record all exclusions and reasons.

`examples/multidesign/specs.json` is the existing mutation specification;
`plans/*.json` records investigator tool calls, not a mutation generator. Extend
the former, and strengthen checkers where necessary; don't blindly multiply plans.

## Matched conditions

- A: mutated RTL, testbench, sim.log; no waves, bridge, answers or network.
- B: identical inputs plus a fresh Verdi session and bridge for that case only.
- Optional C: same as B but using the old point-only toolset to isolate interval tools.
- Use one exact model/version and identical reasoning settings, prompt, token and
  wall-time budgets. Fresh context per case/arm. Randomize paired order.
- Restrict A from wave files and B from mutation manifests; separate processes and
  read-only directories. No repository browsing or prior public answers.
- Require numbered file/line candidates, a causal explanation, and an explicit
  final answer. Record every tool request/response, model turn, tokens and elapsed
  time, plus failures and timeouts. No edits or simulation reruns during diagnosis.

## Score and report

Primary outcome: exact fault statement identified in the first final answer.
Score against the frozen manifest, and separately review causal explanations with
arm labels hidden. Report top-1 exact localization and file-level localization.
Measure the first model turn with an explicit correct statement, with failures
censored at the budget. Count **all** tool calls plus bridge-only calls: A naturally
has zero bridge calls, so comparing only MCP counts across A/B would be misleading.
Report tokens, wall time, transport failures and truncation as well.

Report paired per-case outcomes and effect sizes with confidence intervals; use an
exact paired test for binary accuracy when appropriate. Group by design and fault
family to expose correlated mutations. Multiple random seeds per mutation are
repeated measurements, not additional independent bugs. Publish manifests only
after diagnoses and hashes are frozen. Keep discovery/pilot cases out of the test set.

The old blind trace contains 21 calls: three each of session status, scope browse,
signal addition, pre-error jump, **batched** sampling, driver trace and source read.
There is no repeated binary-search sampling in that trace. No halving of agent
calls is claimed by the interval-tool implementation.
