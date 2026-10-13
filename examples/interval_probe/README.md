# Interval API fixture

This generates a **synthetic, known VCD**, not a simulated design or a model
benchmark. It tests whether a real Verdi query sees a one-tick pulse, X/Z and
signed full-width values. No proprietary waveform is included.

```sh
python examples/interval_probe/make_fixture.py /tmp/interval-probe
```

In your licensed environment, load `/tmp/interval-probe/tb.sv` and
`/tmp/interval-probe/wave.vcd` in Verdi using the normal [setup](../../docs/guide.md).
Set the source root to that directory. Query:

```sh
verdi-bridge call get_value_changes '{"signals":["/tb/pulse","/tb/signed_value[7:0]"],"start":"0","end":"10","radix":"Dec"}'
```

Expected pulse events: 5, 5.001, 6, 7, 8 ns. The interval is (0,10]. Signed values
start at 1, become -1 at 5.001 ns and 2 at 10 ns. A one-bit high is -1 in signed
Dec; use Bin for conventional 0/1 logic. X and Z remain strings. A 1 ps pulse has
distinct timestamps; this does **not** test same-timestamp glitches.
