Quick start
===========

Fmax synthesis
--------------

Step 1: Choose the designs you want to implement
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Uncomment the architectures you want to implement in ``_run_fmax_synthesis_settings.yml``

Change the value of ``nb_jobs`` in ``_run_fmax_synthesis_settings.yml`` depending on the number of logical cores available on your CPU. 

.. tip::
   75% of your number of logical cores is usually a good balance for ``nb_jobs``.

Example:

.. code-block:: yaml
   :caption: _run_fmax_synthesis_settings.yml
   :linenos:
   :emphasize-lines: 4

   overwrite:        No  # overwrite existing results?
   ask_continue:     Yes # prompt 'continue? (y/n)' after settings checks?
   show_log_if_one:  Yes # show synthesis log if there is only one architecture selected?
   nb_jobs:          12  # maximum number of parallel synthesis

   architectures: 
      - Example_Counter_vhdl/04bits
      - Example_Counter_vhdl/08bits
      - Example_Counter_vhdl/16bits
      - Example_Counter_vhdl/24bits
      - Example_Counter_vhdl/32bits
      - Example_Counter_vhdl/48bits
      - Example_Counter_vhdl/64bits

Step 2: Choose your target device/technology
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Select the target device or technology in the yaml file corresponding to your EDA tool.

.. list-table::
   :header-rows: 1

   * - EDA Tool
     - Target File
   * - AMD Vivado
     - ``target_vivado.yml``
   * - Synopsys Design Compiler
     - ``target_design_compiler.yml``


Step 3: Run the selected designs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. tabs::

   .. group-tab:: Vivado

      .. code-block:: console

         make vivado

   .. group-tab:: Design Compiler

      .. code-block:: console

         make dc


Step 4: Visualize and explore the results
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: console

   make explore


Simulations
-----------

Step 1: Choose the designs you want to simulate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Uncomment the architectures you want to implement in ``_run_simulations_settings.yml``

Change the value of ``nb_jobs`` in ``_run_simulations_settings.yml`` depending on the number of logical cores available on your CPU. 

.. tip::
   75% of your number of logical cores is usually a good balance for ``nb_jobs``.

Example:

.. code-block:: yaml
   :caption: _run_simulations_settings.yml
   :linenos:
   :emphasize-lines: 4

   overwrite:        No  # overwrite existing results?
   ask_continue:     Yes # prompt 'continue? (y/n)' after settings checks?
   show_log_if_one:  Yes # show synthesis log if there is only one architecture selected?
   nb_jobs:          12  # maximum number of parallel synthesis

   simulations: 
      - TB_Example_Counter_Verilator:
        - Example_Counter_sv/04bits
        - Example_Counter_sv/08bits
        - Example_Counter_sv/16bits
        - Example_Counter_sv/24bits
        - Example_Counter_sv/32bits
        - Example_Counter_sv/48bits
        - Example_Counter_sv/64bits

Step 2: Run the selected designs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: console

   make sim
