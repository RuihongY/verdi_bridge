# Blind diagnosis protocol

Three new single-cause mutations in UART, AXI-Lite and arbiter RTL. The injector
checks baseline and mutant on seeds 1, 7 and 42 before releasing cases. No cases
may be replaced after diagnosis begins. Diagnosis receives mutated RTL, the
testbench, failing simulation logs and waveforms, plus a live Verdi MCP session.
It receives no pristine RTL, patch, mutation manifest or earlier experiment reports.

The investigator starts with no inherited conversation. Isolation is procedural:
the agents share a filesystem, and allowed paths are explicitly scoped. This is
not an OS-enforced adversarial isolation experiment. Source inspection is allowed;
this evaluates an LLM using RTL, failures and waveform evidence, not waves alone.

Before ground truth is opened, diagnosis must freeze diagnosis.json with one
top-ranked root cause per case, exact source statement/line, causal explanation,
waveform timestamps/values, proposed executable repair, confidence and limitations.
At most three ranked hypotheses per case. No execution of repairs until freeze.
Save all MCP call plans and responses. Root records SHA256 of diagnosis and repair
files before opening the private manifest. The agent gets no correctness feedback
before this point.

Score separately: top-one semantic cause and faulty statement; evidence support;
whether the proposed repair passes the same three seeds. Report all cases,
including failures and infrastructure issues. Three seeded tests are not proof
of equivalence or general performance. Known designs and reused testbenches make
this a small controlled study, not a representative real-world accuracy estimate.
