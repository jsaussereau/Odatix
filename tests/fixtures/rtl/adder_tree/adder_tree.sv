// Pipelined adder tree summing N_INPUTS operands
module adder_tree (
  input  logic                         clk_core,
  input  logic                         sync_rst,
  input  logic [tree_config_pkg::N_INPUTS*tree_config_pkg::IN_WIDTH-1:0] operands,
  output logic [tree_config_pkg::OUT_WIDTH-1:0]                          sum
);
  localparam int N_INPUTS        = tree_config_pkg::N_INPUTS;
  localparam int IN_WIDTH        = tree_config_pkg::IN_WIDTH;
  localparam bit REGISTER_LEVELS = tree_config_pkg::REGISTER_LEVELS;
  localparam int LEVELS          = tree_config_pkg::LEVELS;
  localparam int OUT_WIDTH       = tree_config_pkg::OUT_WIDTH;
  logic [OUT_WIDTH-1:0] level [0:LEVELS][0:N_INPUTS-1];

  always_comb
    for (int i = 0; i < N_INPUTS; i++)
      level[0][i] = OUT_WIDTH'(operands[i*IN_WIDTH +: IN_WIDTH]);

  for (genvar l = 0; l < LEVELS; l++) begin : g_level
    for (genvar i = 0; i < (N_INPUTS >> (l + 1)); i++) begin : g_add
      if (REGISTER_LEVELS) begin : g_reg
        always_ff @(posedge clk_core)
          if (sync_rst) level[l+1][i] <= '0;
          else          level[l+1][i] <= level[l][2*i] + level[l][2*i+1];
      end else begin : g_comb
        assign level[l+1][i] = level[l][2*i] + level[l][2*i+1];
      end
    end
  end

  always_ff @(posedge clk_core)
    sum <= sync_rst ? '0 : level[LEVELS][0];
endmodule
