已在 Verdi 中完成定位：

- 波形窗口：35–105 ns，光标停在 75 ns。
- 已加入 AW/W 握手、寄存器写接口、响应及错误计数等关键信号。
- 源码窗口已跳转到 `tb.dut` 的 RTL 第 122 行。

首笔事务的关键波形：

| 时间 | 信号 | 值 |
|---|---|---|
| 75 ns | `s_axil_wdata` / `reg_wr_data` | `ac000001` / `ac000001` |
| 75 ns | `s_axil_wstrb` / `reg_wr_strb` | `1` / `f` |
| 75 ns | `reg_wr_en` | `1` |
| 85 ns | `errors` / `sent` | `1` / `1` |

地址和数据正确，唯独写选通从输入 `4'b0001` 错变成 `4'b1111`。对应故障语句是 [axil_reg_if_wr.v](<demo-workspace>/case/rtl/axil_reg_if_wr.v:122)：

```verilog
s_axil_wstrb_next = {STRB_WIDTH{1'b1}};
```

这里把每笔写操作的 byte enable 强制成了全 1。按接口行为应当锁存输入的 `s_axil_wstrb`。因此 testbench 在 85 ns 报出首个 `register_payload`，并且 12 笔事务全部失败。

未修改 RTL，也未重新仿真。