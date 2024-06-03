Add your own design
===================

Step 1: Architecture folder
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a folder named after your design in the ``architectures`` folder.

Step 2: Setting file
~~~~~~~~~~~~~~~~~~~~

- Add a ``_settings.yml`` in your newly created folder and fill it with the template below

.. code-block:: yaml

   ---
   #rtl path, relative to Asterism root, not this directory
   rtl_path: "examples/alu"

   top_level_file: "alu_top.sv"
   top_level_module: "alu_top"

   clock_signal: "i_clk"

   # copy a file into synthesis directory?
   file_copy_enable: "false"
   file_copy_source: "/dev/null"
   file_copy_dest: "/dev/null"

   # delimiters for parameter files
   use_parameters: "true"
   start_delimiter: "alu_top #("
   stop_delimiter: ")("

   # optionnal target-specific bounds (in MHz) to speed up fmax search
   xc7s25-csga225-1:
      fmax_lower_bound: 100
      fmax_upper_bound: 450
   xc7a100t-csg324-1:
      fmax_lower_bound: 150
      fmax_upper_bound: 450
   xc7k70t-fbg676-2:
      fmax_lower_bound: 100
      fmax_upper_bound: 700
   ...

- Edit the file so it matches your design source files directory, top level filename, module name, and clock signal name.
- Set `start_delimiter` and `stop_delimiter` so it matches the delimiters of the parameter section in your top level source file.
- Add target-specific bounds for the binary search.
- A documentation of the keys for `_settings.yml` files can be found [here](https://github.com/jsaussereau/Asterism/tree/main/documentation#architecture-settings)

Step 3: Parameter files
~~~~~~~~~~~~~~~~~~~~~~~

Add parameter files to the folder.
Parameter files should match the parameter section of your top-level source file with the desired values.

For instance, with the following Verilog module

.. code-block:: verilog

   module alu_top #(
      parameter BITS = 8
   )(
      input  wire            i_clk,
      input  wire            i_rst,
      input  wire      [4:0] i_sel_op,
      input  wire [BITS-1:0] i_op_a,
      input  wire [BITS-1:0] i_op_b,
      output wire [BITS-1:0] o_res
   );


One of the parameter file could contain:

.. code-block:: verilog

     parameter BITS = 16

Another parameter file could contain:

.. code-block:: verilog

     parameter BITS = 32

You can create as many parameter files as you wish, with different parameter values.
There is no limit to the number of parameters in parameter files.
The only constraint is the strict correspondence between the contents of the parameter files and the parameter section of the top-level in terms of numbers and names.
