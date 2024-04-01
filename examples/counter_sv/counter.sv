
module counter #(
  parameter BITS = 8
)(
  input  wire            i_clk,
  input  wire            i_rst,
  input  wire            i_init,
  input  wire            i_inc_dec,
  output wire [BITS-1:0] o_value
);

  logic [BITS-1:0] counter;

  always_ff @(posedge i_clk) begin
    if (i_rst) begin
      counter <= 0;
    end else begin
      if (i_init) begin
        counter <= 0;
      end else begin
        if (i_inc_dec) begin
          counter <= counter + 1;
        end else begin
          counter <= counter - 1;
        end
      end
    end
  end

  assign o_value = counter;

endmodule
