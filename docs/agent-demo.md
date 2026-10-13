# Agent in action

[Home](../README.md) · [Setup guide](guide.md) · [Earlier installation video](video-walkthrough.md)

https://github.com/user-attachments/assets/6775f3ea-e09d-49c8-8896-746474410999

A natural-language request starts a real Codex CLI session connected to the Verdi
MCP server. The agent reads the supplied simulation log, RTL and testbench, chooses
signals, samples the actual waveform, and navigates to a suspected faulty statement.
No signal list, fault location or tool-call sequence is supplied to the agent.

The Chinese prompt begins: “现在有个 bug，帮我抓 bug 相关信号，分析问题。”
See the [complete prompt](evidence/agent-demo/prompt.txt),
[case instructions](evidence/agent-demo/case-instructions.md),
[invocation](evidence/agent-demo/invocation.json),
[actual conversation and MCP events](evidence/agent-demo/events.json), and
[original final answer](evidence/agent-demo/answer.md).

## What you are watching

- Left: the actual user-facing Codex messages and tool events, typeset and synchronized
  to the recording. This is not a screenshot of the native Codex chat interface.
- Right: a continuous, roughly 2 fps capture of the same live Verdi GUI. Source and
  waveform path bars are redacted. The running elapsed-time label refers to the raw capture.
- Idle gaps are compressed; opening/closing reading holds are added. The roughly
  63-second raw capture becomes an approximately 83-second silent video.
- The last ten seconds are an explicitly labeled paused replay of the 00:46 source
  evidence, next to an excerpt of the actual final answer. This is not a new GUI action.

This run uses the known injected AXI-Lite case from the [blind experiment](blind-validation.md).
It is a product demonstration, not another blind evaluation or an accuracy claim.
An earlier take failed because the non-interactive CLI lacked the intended MCP
approval setting. That failed setup take is excluded; the successful run is preserved.
The invocation approves only this configured bridge's tools for the already-authorized
session and leaves the shell read-only; it does not change the user's global configuration.
See [official MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
for per-server approval settings.

## Actual behavior, including mistakes

The agent attempted 16 MCP calls: 14 completed and two failed argument validation.
It initially omitted absolute signal paths and used the wrong radix spelling, then
corrected both after reading the errors. These events and its explanation remain in
both the transcript and video. It also initially browsed `tb.dut`, which returned no
signals, before finding the testbench-level signals.

It observed input strobe `1` versus backend strobe `f`, with matching address/data,
and selected RTL line 122, which forces all byte enables high. It proposed capturing
`s_axil_wstrb` instead. No source edits or new simulation were performed.

A presentation limitation is retained rather than concealed: after selecting line
122, the agent issued another driver trace, which left the GUI on the testbench's
strobe declaration. Its final answer says it had navigated to line 122; that action
did occur, but line 122 was no longer the final visible selection. The explicitly
labeled evidence replay shows the actual earlier line-122 frame.

The public event file contains user-facing messages and MCP events; shell-output
bulk, internal reasoning, local paths and machine identity are not published. A
full local raw recording and event stream were retained for audit. Setup and
installation steps remain in the [separate tutorial](video-walkthrough.md).
