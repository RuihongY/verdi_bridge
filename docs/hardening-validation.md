# v0.3 hardening validation

[Home](../README.md) · [Tool semantics](tools.md) · [Paired agent pilot](paired-pilot.md)

42 automated tests passed locally with Python 3.12 and Tcl. The added cases cover
exact inclusive/exclusive boundaries across fs/ps/ns/us/ms/s, 1fs/2ps/10ps/0.1ns
native resolutions, the maximum accepted integer tick, off-grid rejection,
unsigned Dec versus signed SDec, literal bus brackets in explicit glob mode,
independent log roots, physical clock-window defaults, cooperative truncation,
GUI restoration and request-local scope caching. Fake GUI tests establish adapter
behavior, not vendor semantics.

[Live assertions](evidence/hardening-v0.3/live-checks.json) also passed against
licensed Verdi T-2022.06-SP2-1 on Linux over SSH: all six units returned the exact
75 ns end transition, explicit bus glob found only literal bus paths, one-bit Dec
returned 1 and SDec -1, a clock measured in ps used the physical default window,
log access rejected an RTL file outside log roots, and a 1 ms query budget returned
partial results while restoring cursor/viewport. A cooperative deadline cannot
interrupt a blocking vendor call. Delta-cycle completeness remains unclaimed.

## Transport measurements

Thirty warm `session_status` calls per condition, randomized and interleaved,
using the same SSH ControlMaster connection and two live GUI sessions (one AXI-Lite
baseline and one mutant). A warm-up call per condition was excluded. Evaluation
processes were also running on the host. These are single-host measurements, not
portable latency guarantees. P95 uses the nearest-rank definition.

| Tcl / helper poll | Transport | Median | P95 |
|---|---|---:|---:|
| 100 / 50 ms | One-shot SSH/helper | 273.3 ms | 535.9 ms |
| 100 / 50 ms | Persistent SSH/helper | 106.0 ms | 156.4 ms |
| 10 / 10 ms | One-shot SSH/helper | 218.7 ms | 490.4 ms |
| 10 / 10 ms | Persistent SSH/helper | 47.2 ms | 67.5 ms |

[Raw samples](evidence/hardening-v0.3/latency.json). Lower polling reduced the
persistent median by about 56%; connection/helper reuse still mattered substantially.
The result does not support a sub-30-ms claim or a halving of agent tool calls.
