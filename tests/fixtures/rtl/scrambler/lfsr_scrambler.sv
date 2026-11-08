// Parallel additive scrambler: an LFSR of LFSR_LEN bits, LANES bits per cycle
module lfsr_scrambler #(
  parameter int LANES    = 8,
  parameter int LFSR_LEN = 23,
  parameter logic [LFSR_LEN-1:0] SEED = '1
)(
  input  logic             i_sys_clk,
  input  logic             i_rst_n,
  input  logic             i_en,
  input  logic [LANES-1:0] i_data,
  output logic [LANES-1:0] o_data
);
  logic [LFSR_LEN-1:0] state, next_state;
  logic [LANES-1:0]    keystream;

  always_comb begin
    next_state = state;
    for (int k = 0; k < LANES; k++) begin
      keystream[k] = next_state[LFSR_LEN-1];
      next_state   = {next_state[LFSR_LEN-2:0], next_state[LFSR_LEN-1] ^ next_state[LFSR_LEN-6]};
    end
  end

  always_ff @(posedge i_sys_clk or negedge i_rst_n) begin
    if (!i_rst_n) begin
      state  <= SEED;
      o_data <= '0;
    end else if (i_en) begin
      state  <= next_state;
      o_data <= i_data ^ keystream;
    end
  end
endmodule
