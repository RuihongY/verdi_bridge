<p align="center">
  <img src="assets/banner.svg" alt="Verdi Bridge" width="100%" />
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="docs/guide.md">安装与连接</a> ·
  <a href="docs/tools.md">工具接口</a> ·
  <a href="docs/multidesign-validation.md">实测报告</a>
</p>

让 AI 助手操作正在运行的 **Synopsys Verdi**，查看波形、追踪驱动、定位 RTL。
支持本机连接和 SSH 远程连接。

> “把 FIFO 的读写指针加进波形，跳到报错前 20 个周期，看看 full 为什么没撤。”
>
> “这笔 AXI-Lite 响应为什么在 BREADY 拉高之前就消失了？”

助手负责分析，桥接层通过 16 个 MCP 工具返回实际信号值和源码，并同步操作 Verdi 界面。

## 视频教程

输入“现在有个 bug，帮我抓相关信号、分析问题”，看 agent 自己选信号、查波形并定位源码。约 1 分 56 秒，中文原文无声演示：左侧为真实 Codex 会话事件的同步排版，右侧为同次运行的 Verdi 录屏，未预编排工具调用。

https://github.com/user-attachments/assets/3294e374-5c43-4b67-8e20-b8a6f319d8f7

[English 原生会话](https://github.com/user-attachments/assets/b041c1bd-4be5-4040-b281-2f15001b1e35) · [中文视频](https://github.com/user-attachments/assets/3294e374-5c43-4b67-8e20-b8a6f319d8f7)

[录制说明与真实调用记录](docs/agent-demo.md) · [安装教程](docs/video-walkthrough.md)

## 开始使用

```sh
git clone https://github.com/RuihongY/verdi_bridge.git
cd verdi_bridge
uv sync
uv run verdi-bridge tcl-path
```

然后按照[连接指南](docs/guide.md)，在 Verdi 中加载 Tcl 适配器，再配置 MCP 客户端。
需要已有的合法 Verdi 安装与许可证。客户端要求 Python 3.11+；远程服务器只需
Python 3.6+ 和 Verdi 内置的 Tcl 8.6。当前从仓库安装，尚未发布到 PyPI。

## 能做什么

- 递归搜索信号、浏览设计层级，把信号加入波形。
- 测量局部时钟周期和相位，向前定位并可选对齐到实际上升沿。
- 查询指定时刻的值或整个窗口内的变化点，保留 X/Z，支持无符号 Dec 和显式有符号 SDec。
- 读取错误日志，追踪驱动，按信号或文件读取带行号的源码并跳转。

工具没有写死 FIFO 的信号或诊断规则，同一套接口已用于 UART、AXI-Lite 和仲裁器。

## 实际验证

在 VCS 和 Verdi 上完成了 **27 次仿真**：

| 设计 | 发现的问题 | 修复后 |
|---|---|---|
| UART TX | 计数少 1，提前进入停止位 | 3 个种子全部通过 |
| AXI-Lite 写接口 | 背压期间 BVALID 没有保持 | 3 个种子全部通过 |
| 轮询仲裁器 | 掩码寄存器每拍被清零 | 3 个种子全部通过 |

原版 9/9 通过，注入版 9/9 被检查器检出，修复版 9/9 通过。
每类设计的种子 1 通过实际 MCP 调用检查了 Verdi 波形与源码。

[完整报告与截图](docs/multidesign-validation.md) ·
[复现步骤](examples/multidesign/README.md) ·
[FIFO 测试](examples/axis_fifo/README.md)

这些是已知注入案例，不是上游项目的原生 bug，也不是盲测准确率。
驱动追踪可能只返回初始化行，最终定位仍需结合源码与波形证据。

另一次[独立 agent 盲测](docs/blind-validation.md)采用三个新 bug：诊断 agent
以空白上下文开始，调用真实 MCP 21 次，三个首选定位均命中具体语句，提出的修复
通过 9/9 次仿真。答案先冻结，再揭晓注入记录。这是共享文件系统上的流程隔离；
这三个案例当时没有设置 RTL-only 对照。

新增区间查询和常驻 SSH helper 已通过[真实 Verdi 验证](docs/interval-validation.md)。
区间查询明确返回截断状态；底层 API 会跳过 glitches，不能保证 delta-cycle 完整性。
[24 个 mutation 的 A/B 对照协议](docs/paired-evaluation.md)已整理，实验尚未运行；
不宣称 agent 调用次数或准确率已有改善。

### v0.3 验证补充

时间边界改为整数 tick，Dec 为无符号、SDec 为显式有符号，查询有时间预算，
日志读取使用独立 allowlist。轮询降到 10 ms 后，实测持久连接中位延迟从
106 ms 降到 47 ms；见[语义与延迟验证](docs/hardening-validation.md)。

[8 个 mutation 的配对实验](docs/paired-pilot.md)已实际运行：只给 RTL、测试台和
日志时定位 8/8；额外提供 Verdi 工具时也为 8/8。两组都没有调用工具。
这批改动对源码阅读过于明显，不能据此宣称 bridge 提高准确率或减少 agent 调用。

## 当前状态

实验版 **v0.3.0**，实测版本为 Linux 上的 Verdi T-2022.06-SP2-1。
已验证新建 Verdi 会话的连接；接入任意已有 GUI 尚未单独验证。
桥接工具本身不会自动编译、修改或修复 RTL。

项目思路参考 [virtuoso-bridge-lite](https://github.com/Arcadia-1/virtuoso-bridge-lite)，
代码为独立实现，采用 MIT 许可。项目与 Synopsys 无隶属关系。

[参与开发](CONTRIBUTING.md) · [安全边界](SECURITY.md) ·
[提交问题](https://github.com/RuihongY/verdi_bridge/issues)
