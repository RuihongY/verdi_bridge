The bug is in `rtl/axil_reg_if_wr.v:95`.

At the first failing transaction:

- Input write data: `0xac000001`
- Input `s_axil_wstrb`: `4'h1`
- Register output data: `0xac000001`
- Register output `reg_wr_strb`: `4'hf`
- First checker error: 85 ns, `register_payload`

The DUT captures the write strobe using:

```verilog
s_axil_wstrb_next = {STRB_WIDTH{1'b1}};
```

This forces every register write to use all byte lanes, ignoring the accepted AXI-Lite `s_axil_wstrb`. It should capture `s_axil_wstrb` instead. This explains all 12 reported payload errors because the test uses varying strobes.

Verdi is left showing the relevant AW/W and register-side waveforms around 45–95 ns, with the cursor at the first write event and the source positioned on line 95. No RTL was modified.