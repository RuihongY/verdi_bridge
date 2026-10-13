`timescale 1ns/1ps
module tb;
  reg clk=0, rst=1;
  always #5 clk=~clk;
  reg [7:0] s_axis_tdata=0;
  reg s_axis_tvalid=0, m_axis_tready=0;
  wire s_axis_tready, m_axis_tvalid;
  wire [7:0] m_axis_tdata;
  axis_fifo #(.DEPTH(8), .DATA_WIDTH(8), .KEEP_ENABLE(0), .LAST_ENABLE(0),
    .ID_ENABLE(0), .DEST_ENABLE(0), .USER_ENABLE(0), .RAM_PIPELINE(1)) dut (
    .clk(clk), .rst(rst), .s_axis_tdata(s_axis_tdata), .s_axis_tkeep(1'b1),
    .s_axis_tvalid(s_axis_tvalid), .s_axis_tready(s_axis_tready),
    .s_axis_tlast(1'b0), .s_axis_tid(8'b0), .s_axis_tdest(8'b0), .s_axis_tuser(1'b0),
    .m_axis_tdata(m_axis_tdata), .m_axis_tvalid(m_axis_tvalid),
    .m_axis_tready(m_axis_tready), .pause_req(1'b0)
  );
  reg [7:0] scoreboard [0:255];
  integer sent=0, received=0, errors=0, cycles=0, seed=1, random_state=1;
  integer first_error=-1;
  reg [7:0] held_data;
  reg held=0;
  task fail(input string reason);
    begin
      errors++;
      if (first_error < 0) begin
        first_error=$time;
        $display("FIRST_ERROR time_ns=%0d kind=%s sent=%0d received=%0d actual=%h", $time,reason,sent,received,m_axis_tdata);
      end
    end
  endtask
  // Independent interface scoreboard. No internal DUT pointers used in checker.
  always @(posedge clk) begin
    if (!rst) begin
      if (held && (!m_axis_tvalid || m_axis_tdata !== held_data)) fail("output_changed_while_stalled");
      held = m_axis_tvalid && !m_axis_tready;
      held_data = m_axis_tdata;
      if (s_axis_tvalid && s_axis_tready) begin
        scoreboard[sent]=s_axis_tdata;
        sent++;
      end
      if (m_axis_tvalid && m_axis_tready) begin
        if (received >= sent) fail("unexpected_output");
        else if (m_axis_tdata !== scoreboard[received]) fail("data_mismatch");
        received++;
      end
    end
  end
  initial begin
    if ($value$plusargs("SEED=%d", seed)) begin end
    random_state=seed;
    $dumpfile("wave.vcd"); $dumpvars(0,tb);
    repeat (4) @(negedge clk);
    rst=0;
    // Fill and stall first, then vary backpressure while sending 64 unique bytes.
    for (cycles=0; cycles<300; cycles++) begin
      s_axis_tvalid=(sent<64);
      s_axis_tdata=(sent*3+17) & 255;
      m_axis_tready=(cycles>=35) && (($random(random_state)&3)!=0);
      @(negedge clk);
    end
    s_axis_tvalid=0; m_axis_tready=1;
    repeat (30) @(negedge clk);
    if (sent != 64 || received != 64) fail("progress_timeout");
    $display("RESULT seed=%0d errors=%0d sent=%0d received=%0d first_error_ns=%0d",seed,errors,sent,received,first_error);
    $finish;
  end
endmodule
