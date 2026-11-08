// Transposed-form FIR filter, fixed triangular coefficients
module fir_filter #(
  parameter DATA_WIDTH = 16,
  parameter COEF_WIDTH = 12,
  parameter TAPS = 8
)(
  input  wire                         clk,
  input  wire                         rst,
  input  wire                         in_valid,
  input  wire signed [DATA_WIDTH-1:0] in_data,
  output wire signed [DATA_WIDTH+COEF_WIDTH+3:0] out_data,
  output reg                          out_valid
);
  localparam ACC_WIDTH = DATA_WIDTH + COEF_WIDTH + 4;

  wire signed [ACC_WIDTH-1:0] chain [0:TAPS];
  reg  signed [DATA_WIDTH-1:0] sample;
  assign chain[TAPS] = {ACC_WIDTH{1'b0}};

  always @(posedge clk) begin
    if (rst) begin
      sample    <= 0;
      out_valid <= 1'b0;
    end else begin
      sample    <= in_valid ? in_data : sample;
      out_valid <= in_valid;
    end
  end

  genvar i;
  generate
    for (i = 0; i < TAPS; i = i + 1) begin : taps
      localparam signed [COEF_WIDTH-1:0] COEF = (i < TAPS/2) ? i + 1 : TAPS - i;
      mac #(.A_WIDTH(DATA_WIDTH), .B_WIDTH(COEF_WIDTH), .ACC_WIDTH(ACC_WIDTH)) u_mac (
        .clk(clk), .a(sample), .b(COEF), .acc_in(chain[i+1]), .acc_out(chain[i])
      );
    end
  endgenerate

  assign out_data = chain[0];
endmodule
