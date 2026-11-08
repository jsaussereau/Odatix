// Self-checking testbench: scrambling twice with the same seed gives the data
// back. The descrambler starts one cycle after the scrambler, when the first
// scrambled word reaches it.
module tb_lfsr_scrambler #(
  parameter int LANES  = 8,
  parameter int CYCLES = 1000
);
  logic clk = 0, rst_n = 0, en = 0, en_d = 0;
  logic [LANES-1:0] din = '0, din_d1 = '0, scrambled, descrambled;
  int errors = 0, checked = 0;

  lfsr_scrambler #(.LANES(LANES)) scrambler   (.i_sys_clk(clk), .i_rst_n(rst_n), .i_en(en), .i_data(din),       .o_data(scrambled));
  lfsr_scrambler #(.LANES(LANES)) descrambler (.i_sys_clk(clk), .i_rst_n(rst_n), .i_en(en_d), .i_data(scrambled), .o_data(descrambled));

  always #5 clk = ~clk;
  always @(posedge clk) en_d <= en;

  initial begin
    repeat (3) @(negedge clk);
    rst_n = 1;
    en = 1;
    for (int i = 0; i < CYCLES; i++) begin
      @(negedge clk);
      if (i >= 2) begin
        if (descrambled !== din_d1) errors++;
        checked++;
      end
      din_d1 = din;
      din = LANES'($urandom);
    end
    $display("checked=%0d errors=%0d", checked, errors);
    if (errors == 0) $display("PASS"); else $display("FAIL");
    $finish;
  end
endmodule
