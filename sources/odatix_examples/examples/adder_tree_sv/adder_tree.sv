// **********************************************************************
//                                Odatix
// **********************************************************************
//
// Adder tree: sums N_INPUTS unsigned operands of IN_WIDTH bits each.
//
// The operands are registered, then added two by two over LEVELS =
// log2(N_INPUTS) levels, and the sum is registered. Its parameters are those
// of the package tree_config_pkg (tree_config_pkg.sv):
//   - N_INPUTS:        number of operands, a power of two
//   - IN_WIDTH:        width of each operand
//   - REGISTER_LEVELS: 1 registers every level of the tree (latency LEVELS + 2
//                      cycles, short critical path); 0 leaves the tree
//                      combinational (latency 2 cycles, the critical path
//                      crosses every level)
//
// The ports and constants name the package explicitly (tree_config_pkg::...)
// rather than importing it, which every synthesis tool accepts.

module adder_tree (
  input  logic                                                            clock,
  input  logic                                                            reset,
  input  logic [tree_config_pkg::N_INPUTS*tree_config_pkg::IN_WIDTH-1:0] i_operands,
  output logic [tree_config_pkg::OUT_WIDTH-1:0]                          o_sum
);
  localparam int N_INPUTS        = tree_config_pkg::N_INPUTS;
  localparam int IN_WIDTH        = tree_config_pkg::IN_WIDTH;
  localparam bit REGISTER_LEVELS = tree_config_pkg::REGISTER_LEVELS;
  localparam int LEVELS          = tree_config_pkg::LEVELS;
  localparam int OUT_WIDTH       = tree_config_pkg::OUT_WIDTH;

  logic [N_INPUTS*IN_WIDTH-1:0] operands;
  logic [OUT_WIDTH-1:0]         level [0:LEVELS][0:N_INPUTS-1];

  // Input registers: every path of the tree starts at a register
  always_ff @(posedge clock)
    if (reset) operands <= '0;
    else       operands <= i_operands;

  always_comb
    for (int i = 0; i < N_INPUTS; i++)
      level[0][i] = OUT_WIDTH'(operands[i*IN_WIDTH +: IN_WIDTH]);

  for (genvar l = 0; l < LEVELS; l++) begin : g_level
    for (genvar i = 0; i < (N_INPUTS >> (l + 1)); i++) begin : g_add
      if (REGISTER_LEVELS) begin : g_reg
        always_ff @(posedge clock)
          if (reset) level[l+1][i] <= '0;
          else       level[l+1][i] <= level[l][2*i] + level[l][2*i+1];
      end else begin : g_comb
        assign level[l+1][i] = level[l][2*i] + level[l][2*i+1];
      end
    end
  end

  // Output register
  always_ff @(posedge clock)
    if (reset) o_sum <= '0;
    else       o_sum <= level[LEVELS][0];
endmodule
