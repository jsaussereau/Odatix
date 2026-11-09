// **********************************************************************
//                                Odatix
// **********************************************************************
//
// Configuration of the adder tree (adder_tree.sv).
//
// The parameters live in this package rather than in the module: the
// parameter domains of the example replace their values here, in a file that
// is not the top level.

package tree_config_pkg;
  parameter int N_INPUTS = 8;          // number of operands, a power of two
  parameter int IN_WIDTH = 8;          // width of each operand
  parameter bit REGISTER_LEVELS = 1;   // register the output of every level of the tree
  localparam int LEVELS    = $clog2(N_INPUTS);
  localparam int OUT_WIDTH = IN_WIDTH + LEVELS;
endpackage
