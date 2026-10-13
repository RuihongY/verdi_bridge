`timescale 1ns/1ps
module tb;
  reg clk=0, rst=1;
  always #5 clk=~clk;
  reg [7:0] s_axis_tdata=0;
  reg s_axis_tvalid=0;
  wire s_axis_tready, txd, busy;
  uart_tx dut(.clk(clk),.rst(rst),.s_axis_tdata(s_axis_tdata),
    .s_axis_tvalid(s_axis_tvalid),.s_axis_tready(s_axis_tready),
    .txd(txd),.busy(busy),.prescale(16'd2));
  // 10 ns clock, prescale=2, 8 clocks per prescale -> 160 ns/bit.
  localparam BIT_NS=160;
  reg [7:0] expected[0:31];
  integer sent=0, received=0, errors=0, first_error=-1, seed=1, random_state=1;
  reg [7:0] decoded;
  task fail(input string reason);
    errors++;
    if (first_error<0) begin
      first_error=$time;
      $display("FIRST_ERROR time_ns=%0d kind=%s frame=%0d",$time,reason,received);
    end
  endtask
  always @(posedge clk) if (!rst && s_axis_tvalid && s_axis_tready) begin
    expected[sent]=s_axis_tdata;
    sent++;
  end
  // Independent serial decoder; does not inspect any DUT counter or state.
  initial forever begin
    @(negedge txd);
    if (!rst) begin
      #(BIT_NS/2);
      if (txd !== 0) fail("start_bit");
      for (integer b=0;b<8;b++) begin
        #BIT_NS;
        decoded[b]=txd;
        if (received < sent && txd !== expected[received][b]) begin
          $display("BIT_MISMATCH time_ns=%0d frame=%0d bit=%0d expected=%b actual=%b",$time,received,b,expected[received][b],txd);
          fail("serial_data_bit");
        end
      end
      #BIT_NS;
      if (txd !== 1) fail("stop_bit");
      if (received >= sent) fail("unexpected_frame");
      received++;
    end
  end
  initial begin
    if ($value$plusargs("SEED=%d",seed)) begin end
    random_state=seed;
    $dumpfile("wave.vcd"); $dumpvars(0,tb);
    repeat(4) @(negedge clk); rst=0;
    for (integer i=0;i<12;i++) begin
      while (busy || !s_axis_tready) @(negedge clk);
      s_axis_tdata=(i==0) ? 8'h35 : $random(random_state);
      s_axis_tvalid=1;
      @(posedge clk);
      while (!s_axis_tready) @(posedge clk);
      @(negedge clk); s_axis_tvalid=0;
      repeat(3+(seed+i)%5) @(negedge clk);
    end
    repeat(200) @(negedge clk);
    if (sent!=12 || received!=12) fail("progress_timeout");
    $display("RESULT seed=%0d errors=%0d sent=%0d received=%0d first_error_ns=%0d",seed,errors,sent,received,first_error);
    $finish;
  end
  initial begin #60000; fail("watchdog"); $display("INCOMPLETE"); $finish; end
endmodule
