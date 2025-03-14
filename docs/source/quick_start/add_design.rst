Add your own design
===================


Step 1: Initialize the directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Place yourself in your design's directory, or any other directory.

Run the init command of Odatix to create configuration files. 

.. code-block:: bash

   odatix init


Step 2: Architecture folder
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a folder named after your design in the ``odatix_userconfig/architectures`` folder.

Step 3: Architecture settings file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Add a ``_settings.yml`` file to your newly created folder and fill it with one of the templates below

.. tab:: VHDL/Verilog/SystemVerilog

   .. code-block:: yaml
      :caption: _setting.yml
      :linenos:

      ---
      rtl_path: "examples/alu_sv"

      top_level_file: "alu_top.sv" # The top level path relative to rtl_path
      top_level_module: "alu_top"

      clock_signal: "i_clk"
      reset_signal: "i_rst"

      # copy a file into synthesis directory?
      file_copy_enable: No
      file_copy_source: "/dev/null"
      file_copy_dest: "/dev/null"

      # delimiters for parameter files
      use_parameters: Yes
      start_delimiter: "#("
      stop_delimiter: ")("

      # target-specific options
      xc7s25-csga225-1:
         fmax_synthesis:
            lower_bound: 100
            upper_bound: 450
         custom_freq_synthesis:
            # list definition
            list: [50, 100]
      xc7a100t-csg324-1:
         fmax_synthesis:
            lower_bound: 50
            upper_bound: 800
         custom_freq_synthesis:
            # range definition
            lower_bound: 200
            upper_bound: 1800
            step: 200
      ...

.. tab:: Chisel/HLS

   .. code-block:: yaml
      :caption: _setting.yml
      :linenos:

      ---
      design_path: "examples/alu_chisel"
      design_path_whitelist: [] # path/pattern of what should be copied from design_path
      design_path_blacklist: [] # path/pattern of what should NOT be copied from design_path

      # generate the rtl (from chisel for example)
      generate_rtl: Yes
      generate_command: "sbt 'runMain ALUTop --o=rtl'" # command for rtl generation
      generate_output: "rtl" # path of the generated rtl

      # generated design settings
      top_level_file: "ALUTop.sv" # The top level path relative to generate_output
      top_level_module: "ALUTop"
      clock_signal: "clock"
      reset_signal: "reset"

      # copy a file into synthesis directory?
      file_copy_enable: No
      file_copy_source: "/dev/null"
      file_copy_dest: "/dev/null"

      # delimiters for parameter files
      use_parameters: Yes
      param_target_file: "src/main/scala/ALUTop.scala"
      start_delimiter: "new ALUTop("
      stop_delimiter: ")"

      # target-specific options
      xc7s25-csga225-1:
         fmax_synthesis:
            lower_bound: 100
            upper_bound: 450
         custom_freq_synthesis:
            # list definition
            list: [50, 100]
      xc7a100t-csg324-1:
         fmax_synthesis:
            lower_bound: 50
            upper_bound: 800
         custom_freq_synthesis:
            # range definition
            lower_bound: 200
            upper_bound: 1800
            step: 200
      ...

- Edit the file, so it matches your design source files directory, top level filename, module name, and clock signal name.
- The rtl/design path can be both absolute or relative to the directory from where you start Odatix.
- Set ``start_delimiter`` and ``stop_delimiter``, so it matches the delimiters of the parameter section in your top level source file.
- Add target-specific bounds for the binary search in ``fmax_synthesis``.
- Add a list of frequencies, a range (lower and upper bounds and a step) or a combination of both in ``custom_freq_synthesis`` for custom frequency synthesis.
- A documentation of the keys for ``_settings.yml`` files can be found in section :doc:`/documentation/settings`

Step 4: Parameter files
~~~~~~~~~~~~~~~~~~~~~~~

Add parameter files to the folder.
Parameter files should match the parameter section of your top-level source file with the desired values.

For instance, with the following Verilog module

.. code-block:: verilog
   :caption: alu_top.sv
   :linenos:
   :emphasize-lines: 2

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
   :caption: 16bits.txt
   :linenos:

     parameter BITS = 16

Another parameter file could contain:

.. code-block:: verilog
   :caption: 32bits.txt
   :linenos:

     parameter BITS = 32

You can create as many parameter files as you wish, with different parameter values.
There is no limit to the number of parameters in parameter files.
The only constraint is the strict correspondence between the contents of the parameter files and the parameter section of the top-level in terms of numbers and names.

Step 5: Run your design configurations!
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Follow the same steps as in section :doc:`/quick_start/fmax_synthesis` for Fmax synthesis or :doc:`/quick_start/custom_freq_synthesis` for custom frequency synthesis.:
   - Edit ``odatix_userconfig/fmax_synthesis_settings.yml`` to add your design's configurations
   - Edit ``odatix_userconfig/custom_freq_synthesis_settings.yml`` to add your design's configurations
   - Select the target device or technology in the yaml file corresponding to your EDA tool.
   - Run the selected designs
   - Visualize and explore the results
