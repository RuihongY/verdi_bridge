已在 Verdi 中定位到 bug，并展示了关键波形；源码窗口现停在可疑语句 `axil_reg_if_wr.v:122`。

结论：

- 首次报错：85 ns，`register_payload`
- 70 ns 时 W 通道握手：
  - `s_axil_wstrb = 4'h1`
  - `s_axil_wdata = 32'hac000001`
- DUT 随后输出：
  - `reg_wr_data = 32'hac000001`，正确
  - `reg_wr_strb = 4'hf`，错误
- 所有 12 笔事务均完成但全部 payload 检查失败，与日志的 `errors=12 sent=12 received=12` 一致。

根因是第 122 行：

```verilog
s_axil_wstrb_next = {STRB_WIDTH{1'b1}};
```

这里把每笔写事务的 byte strobe 强制写成全 1，没有保存输入的 `s_axil_wstrb`。正确意图应当是锁存输入：

```verilog
s_axil_wstrb_next = s_axil_wstrb;
```

因此这是 W 通道 `WSTRB` 寄存逻辑错误，不是事务丢失、地址错位或响应超时。未修改 RTL，也未重新仿真。