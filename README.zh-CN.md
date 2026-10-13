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

助手负责分析，桥接层通过 10 个 MCP 工具返回实际信号值和源码，并同步操作 Verdi 界面。

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

- 浏览设计层级，把信号加入波形。
- 移动光标、缩放时间窗口，按已知时钟周期向前定位。
- 查询指定时刻的信号值，保留 X/Z。
- 追踪信号驱动，读取带行号的源码，在 Verdi 中跳转到对应位置。

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

## 当前状态

实验版 **v0.1.1**，实测版本为 Linux 上的 Verdi T-2022.06-SP2-1。
已验证新建 Verdi 会话的连接；接入任意已有 GUI 尚未单独验证。
桥接工具本身不会自动编译、修改或修复 RTL。

项目思路参考 [virtuoso-bridge-lite](https://github.com/Arcadia-1/virtuoso-bridge-lite)，
代码为独立实现，采用 MIT 许可。项目与 Synopsys 无隶属关系。

[参与开发](CONTRIBUTING.md) · [安全边界](SECURITY.md) ·
[提交问题](https://github.com/RuihongY/verdi_bridge/issues)
