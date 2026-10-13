`timescale 1ns/1ps
module tb;
  reg clk=0,rst=1;
  always #5 clk=~clk;
  reg [3:0] request=0;
  wire [3:0] grant;
  wire grant_valid;
  wire [1:0] grant_encoded;
  arbiter #(.PORTS(4),.ARB_TYPE_ROUND_ROBIN(1),.ARB_BLOCK(0),.ARB_LSB_HIGH_PRIORITY(1)) dut(
    .clk(clk),.rst(rst),.request(request),.acknowledge(4'b0),
    .grant(grant),.grant_valid(grant_valid),.grant_encoded(grant_encoded));
  integer errors=0,first_error=-1,seed=1,random_state=1,checked=0,last=3,chosen;
  reg [3:0] expected;
  task fail(input string reason);
    errors++;
    if(first_error<0) begin
      first_error=$time;
      $display("FIRST_ERROR time_ns=%0d kind=%s request=%b expected=%b actual=%b",$time,reason,request,expected,grant);
    end
  endtask
  // Behavioral scheduling model: scan cyclically after the last expected winner.
  // Does not inspect or duplicate the DUT's mask implementation.
  always @(posedge clk) begin
    if(rst) last=3;
    else begin
      chosen=-1;
      for(integer offset=1;offset<=4;offset++)
        if(chosen<0 && request[(last+offset)%4]) chosen=(last+offset)%4;
      expected=chosen<0 ? 0 : (1<<chosen);
      #1;
      if(grant !== expected || grant_valid !== (chosen>=0)) fail("round_robin_order");
      if(chosen>=0 && grant_encoded !== chosen[1:0]) fail("encoded_grant");
      if(chosen>=0) last=chosen;
      checked++;
    end
  end
  initial begin
    if($value$plusargs("SEED=%d",seed)) begin end
    random_state=seed;
    $dumpfile("wave.vcd"); $dumpvars(0,tb);
    repeat(4) @(negedge clk); rst=0;
    for(integer i=0;i<100;i++) begin
      request=i<16 ? 4'b1111 : ($random(random_state)&15);
      @(negedge clk);
    end
    if(checked!=100) fail("incomplete_schedule");
    $display("RESULT seed=%0d errors=%0d sent=%0d received=%0d first_error_ns=%0d",seed,errors,checked,checked,first_error);
    $finish;
  end
endmodule
