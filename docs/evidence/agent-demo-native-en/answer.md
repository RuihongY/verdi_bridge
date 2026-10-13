The bug is in [rtl/axil_reg_if_wr.v](<demo-workspace>/case/rtl/axil_reg_if_wr.v:122):

```verilog
s_axil_wstrb_next = {STRB_WIDTH{1'b1}};
```

This forces every register write strobe to `4'hF` instead of capturing `s_axil_wstrb`.

Waveform evidence for the first transaction:

- At 70–74 ns, the W channel handshakes with `s_axil_wstrb = 4'h1`.
- `s_axil_wstrb_next` remains `4'hF`.
- During `reg_wr_en`, `reg_wr_strb` is consequently `4'hF`, although the expected strobe is `4'h1`.
- Address `0x0000` and data `0xAC000001` are correct; only the strobe mismatches.
- The testbench reports `register_payload` at 85 ns. All 12 transactions fail because their requested strobes differ from `4'hF`.

The intended assignment is evidently:

```verilog
s_axil_wstrb_next = s_axil_wstrb;
```

Verdi now shows the relevant waveforms around 35–105 ns, with the cursor at 84 ns, and its source window is left on the faulty statement at line 122. No RTL was modified.