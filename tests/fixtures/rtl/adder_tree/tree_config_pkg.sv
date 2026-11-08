// Configuration of the adder tree
package tree_config_pkg;
  parameter int N_INPUTS  = 8;    // number of operands, a power of two
  parameter int IN_WIDTH  = 12;   // width of each operand
  parameter bit REGISTER_LEVELS = 1;  // register every level of the tree
  localparam int LEVELS    = $clog2(N_INPUTS);
  localparam int OUT_WIDTH = IN_WIDTH + LEVELS;
endpackage
