
module counter #(
  parameter BITS = 8
)(
  input  wire            clock,
  input  wire            reset,
  input  wire            i_init,
  input  wire            i_inc_dec,
  output wire [BITS-1:0] o_value
);

  reg [BITS-1:0] value;

  always @(posedge clock) begin
    if (reset) begin
      value <= 0;
    end else begin
      if (i_init) begin
        value <= 0;
      end else begin
        if (i_inc_dec) begin
          value <= value + 1;
        end else begin
          value <= value - 1;
        end
      end
    end
  end

  assign o_value = value;

endmodule
