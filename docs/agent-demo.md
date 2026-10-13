# Agent in action / Agent 调试演示

[Home](../README.md) · [Setup](guide.md) · [Installation video](video-walkthrough.md)

## English: original English conversation

https://github.com/user-attachments/assets/b041c1bd-4be5-4040-b281-2f15001b1e35

This **1m38s** silent video records a separate English-language agent run: an
English prompt, original English replies and the actual MCP calls chosen by that
agent. It is not a translation of the Chinese run. The existing Chinese video is
retained below; the two editions debug the same example in separate sessions.

## 中文：原生中文会话

https://github.com/user-attachments/assets/3294e374-5c43-4b67-8e20-b8a6f319d8f7

中文版保持原录制。英文版现在是另一次独立运行：英文提问、agent 原生英文回复，
并同步录制实际 Verdi 操作，不再使用翻译版。

## English recording method

The CLI receives the error log, RTL, testbench and generic case instructions.
No fault location, signal list or tool-call sequence is provided. An unrelated
local Virtuoso skill is disabled for this invocation; Verdi Bridge has no Virtuoso
dependency. There are no global configuration changes.

Left: the actual user-facing Codex events, typeset with synchronized timestamps,
not a native client screenshot. Right: continuous low-frame-rate capture of the
same live Verdi session, with machine paths redacted. Some idle intervals are
compressed and opening/closing reading holds added. Raw capture lasts
82.1 seconds; the video lasts 97.6 seconds.

The agent made 20 MCP calls: 18 completed, and two argument-validation errors
(absolute waveform paths and radix spelling) were corrected by the agent. They
remain in the recording and transcript. The final GUI is at RTL line 122, cursor
84 ns, with a 35–105 ns waveform window. No RTL was edited and no simulation rerun.

This is a selected product demonstration using a known injected AXI-Lite case,
not a new blind evaluation. An earlier English take found the strobe defect but
reported/navigated to line 95. That take is excluded from this video; its
[answer is retained](evidence/agent-demo-native-en/earlier-take-wrong-line.md).
Before recording again, the generic instructions were amended to require checking
numbered source and distinguishing driver locations from faulty statements. No
correct line number or diagnosis was supplied.

A timing imprecision is preserved in the final answer: it calls 70–74 ns a
handshake interval. VALID and READY are asserted then; the actual transfer occurs
at the 75 ns rising clock edge. The observed strobe mismatch and faulty constant
assignment at line 122 are supported by the waveform/source evidence.

## English evidence

[English prompt](evidence/agent-demo-native-en/prompt.txt) ·
[Case instructions](evidence/agent-demo-native-en/case-instructions.md) ·
[Invocation](evidence/agent-demo-native-en/invocation.json) ·
[Actual events](evidence/agent-demo-native-en/events.json) ·
[Original English answer](evidence/agent-demo-native-en/answer.md)

Published records contain user-facing messages and MCP events; machine paths are
redacted, and shell-output bulk/internal reasoning are omitted. Full local raw
captures and events are retained. See [Chinese recording notes](agent-demo-v2.md)
for its separate evidence and limitations. The former translated English version
is historical and no longer the main English demo. The [blind trial](blind-validation.md)
is a separate experiment.
