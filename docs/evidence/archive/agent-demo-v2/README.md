# Agent in action / Agent 调试演示

[Home](../../../../README.md) · [Setup](../../../guide.md) · [Installation video](../../../video-walkthrough.md)

## English

https://github.com/user-attachments/assets/bef00220-182e-430e-bce1-a1f487d904b2

## 中文

https://github.com/user-attachments/assets/3294e374-5c43-4b67-8e20-b8a6f319d8f7

Both 1m56s silent editions show the **same fresh agent session and Verdi capture**.
The Chinese edition uses the original messages; English is a labeled translation,
not a second English-language run. Tool names, arguments and results are unchanged.

两版使用同一次真实运行：中文为原文，英文为明确标注的翻译。工具调用、波形和时间线一致。

## Why this replaces the earlier recording

The former agent mistakenly selected an unrelated local Virtuoso skill before
correcting itself. Verdi Bridge has no Virtuoso dependency. For this new recording,
the skill was disabled only in the CLI invocation, and case instructions explicitly
limited debugging to Verdi MCP. No global skill configuration was changed. The new
agent neither mentions nor loads that skill. We reran the conversation rather than
silently rewriting the previous agent's statements. [Previous recording notes](../agent-demo-v1/README.md).

旧版开头的 Virtuoso 来自 agent 误选本机技能，不是本项目的依赖。新版在启动时禁用了
该技能，并重新录制了真实会话；没有直接修改旧对话来掩盖错误。

## What is shown

- Left: actual user-facing Codex events, typeset and synchronized. This is not a
  screenshot of a native chat UI. English text is translated from the Chinese original.
- Right: continuous low-frame-rate capture of the same live Verdi GUI. Source/database
  path bars are redacted. There is no scripted tool-call sequence.
- Approximately 99.6 seconds of raw capture. Some idle intervals are compressed and
  reading holds added; each edition is approximately 116.3 seconds. At the end, an
  additional excerpt of the real final answer is displayed with the final GUI frame.
- The agent receives the log, RTL, testbench and generic case instructions, but no
  signal list, fault location or diagnosis. This uses a known injected AXI-Lite case;
  it is a product demonstration, not a fresh blind evaluation.

## Observed outcome and limits

The agent attempted **20 MCP calls: 18 completed and two failed validation** (absolute
waveform paths and radix spelling). It corrected the arguments and continued.
It compared input strobe `1` with register-side strobe `f`, identified the constant
assignment at RTL line 122, and left the GUI at that statement with the cursor at
75 ns. No RTL was edited and no simulation rerun.

The transcript preserves an imprecise timing phrase: its final answer calls 70 ns
the handshake time. In this testbench the W inputs are asserted at the 70 ns falling
edge; transfer occurs at the **75 ns rising edge**. The video and English translation
retain the actual answer, while this note clarifies the distinction. The strobe
mismatch and source diagnosis remain supported by the samples.

## Evidence

[Prompt](prompt.txt) ·
[Case instructions](case-instructions.md) ·
[Invocation](invocation.json) ·
[Original events](events.json) ·
[Original final answer](answer.md) ·
[English translations](translations-en.json)

Published event records include user-facing messages and MCP events. Machine paths
are redacted; shell-output bulk and internal reasoning are excluded. Original local
recordings and event streams are retained. The existing [blind experiment](../../../blind-validation.md)
is separate. See [official skill configuration](https://learn.chatgpt.com/docs/build-skills)
for disabling an unrelated skill without deleting it.
