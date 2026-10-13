`timescale 1ns/1ps
module tb;
  reg clk=0,rst=1;
  always #5 clk=~clk;
  reg [15:0] s_axil_awaddr=0;
  reg s_axil_awvalid=0, s_axil_wvalid=0, s_axil_bready=0;
  reg [31:0] s_axil_wdata=0;
  reg [3:0] s_axil_wstrb=0;
  wire s_axil_awready,s_axil_wready,s_axil_bvalid;
  wire [1:0] s_axil_bresp;
  wire [15:0] reg_wr_addr;
  wire [31:0] reg_wr_data;
  wire [3:0] reg_wr_strb;
  wire reg_wr_en;
  axil_reg_if_wr #(.ADDR_WIDTH(16)) dut(.clk(clk),.rst(rst),
    .s_axil_awaddr(s_axil_awaddr),.s_axil_awprot(3'b0),.s_axil_awvalid(s_axil_awvalid),.s_axil_awready(s_axil_awready),
    .s_axil_wdata(s_axil_wdata),.s_axil_wstrb(s_axil_wstrb),.s_axil_wvalid(s_axil_wvalid),.s_axil_wready(s_axil_wready),
    .s_axil_bresp(s_axil_bresp),.s_axil_bvalid(s_axil_bvalid),.s_axil_bready(s_axil_bready),
    .reg_wr_addr(reg_wr_addr),.reg_wr_data(reg_wr_data),.reg_wr_strb(reg_wr_strb),.reg_wr_en(reg_wr_en),
    .reg_wr_wait(1'b0),.reg_wr_ack(reg_wr_en));
  integer seed=1,errors=0,first_error=-1,sent=0,received=0,aw_count=0,w_count=0;
  reg held=0;
  reg [1:0] held_resp;
  reg [15:0] address_queue[0:31];
  reg [31:0] data_queue[0:31];
  reg [3:0] strobe_queue[0:31];
  task fail(input string reason);
    errors++;
    if(first_error<0) begin
      first_error=$time;
      $display("FIRST_ERROR time_ns=%0d kind=%s",$time,reason);
    end
  endtask
  always @(posedge clk) if (!rst) begin
    // Capture independent AW/W handshakes and compare register-side effects.
    if (s_axil_awvalid && s_axil_awready) begin address_queue[aw_count]=s_axil_awaddr; aw_count++; end
    if (s_axil_wvalid && s_axil_wready) begin data_queue[w_count]=s_axil_wdata; strobe_queue[w_count]=s_axil_wstrb; w_count++; end
    if (reg_wr_en) begin
      if (sent>=aw_count || sent>=w_count) fail("write_without_request");
      else if (reg_wr_addr !== address_queue[sent] || reg_wr_data !== data_queue[sent] || reg_wr_strb !== strobe_queue[sent]) fail("register_payload");
      sent++;
    end
    if (held && (!s_axil_bvalid || s_axil_bresp !== held_resp)) fail("response_not_held");
    held=s_axil_bvalid && !s_axil_bready;
    held_resp=s_axil_bresp;
    if (s_axil_bvalid && s_axil_bready) begin
      if (s_axil_bresp !== 0 || received>=sent) fail("invalid_response");
      received++;
    end
  end
  task send_aw(input integer n);
    repeat((n+seed)%4) @(negedge clk);
    s_axil_awaddr=n*4; s_axil_awvalid=1;
    @(posedge clk); while(!s_axil_awready) @(posedge clk);
    @(negedge clk); s_axil_awvalid=0;
  endtask
  task send_w(input integer n);
    repeat((n+seed+2)%5) @(negedge clk);
    s_axil_wdata=32'hac000000+n*13+seed; s_axil_wstrb=1+(n%15); s_axil_wvalid=1;
    @(posedge clk); while(!s_axil_wready) @(posedge clk);
    @(negedge clk); s_axil_wvalid=0;
  endtask
  initial begin
    if ($value$plusargs("SEED=%d",seed)) begin end
    $dumpfile("wave.vcd"); $dumpvars(0,tb);
    repeat(4) @(negedge clk); rst=0;
    for(integer i=0;i<12;i++) begin
      fork send_aw(i); send_w(i); join
      repeat(8+(seed+i)%3) @(negedge clk);
      s_axil_bready=1;
      for(integer timeout=0; timeout<40 && received<i+1; timeout++) @(negedge clk);
      if(received!=i+1) fail("response_timeout");
      s_axil_bready=0;
      repeat(2) @(negedge clk);
    end
    if(sent!=12 || received!=12 || aw_count!=12 || w_count!=12) fail("progress_timeout");
    $display("RESULT seed=%0d errors=%0d sent=%0d received=%0d first_error_ns=%0d",seed,errors,sent,received,first_error);
    $finish;
  end
  initial begin #30000; fail("watchdog"); $display("INCOMPLETE"); $finish; end
endmodule
