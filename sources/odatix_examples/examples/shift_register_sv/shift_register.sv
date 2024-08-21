
module shift_register #(
  parameter BITS = 8
)(
  input  wire            i_clk,
  input  wire            i_rst,
  input  wire            i_bit_in,
  input  wire            i_right_nleft,
  output wire [BITS-1:0] o_value
);

  logic [BITS-1:0] shift_reg;

  always_ff @(posedge i_clk) begin
    if (i_rst) begin
      shift_reg <= 0;
    end else begin
      if (i_right_nleft) begin
        shift_reg <= {i_bit_in, shift_reg[BITS-1:1]};
      end else begin
        shift_reg <= {shift_reg[BITS-2:0], i_bit_in};
      end
    end
  end

  assign o_value = shift_reg;

endmodule
