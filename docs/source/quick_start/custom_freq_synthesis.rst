**************************
Custom Frequency synthesis
**************************

.. note::
   This functionality requires Odatix 3.2+


Step 1: Initialize a directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Place yourself in an empty directory, for example:

.. code-block:: bash

   mkdir ~/odatix_example
   cd ~/odatix_example

Run the init command of Odatix to create configuration files. 

.. code-block:: bash

   odatix init --examples

Step 2: Choose the designs you want to implement
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Uncomment the architectures you want to implement in ``odatix_userconfig/custom_freq_synthesis_settings.yml``.
Those architectures are defined in ``odatix_userconfig/architectures``.

Change the value of ``nb_jobs`` in ``odatix_userconfig/custom_freq_synthesis_settings.yml`` depending on the number of logical cores available on your CPU. 

.. tip::
   75% of your number of logical cores is usually a good balance for ``nb_jobs``.

Example:

.. code-block:: yaml
   :caption: odatix_userconfig/custom_freq_synthesis_settings.yml
   :linenos:
   :emphasize-lines: 5

   overwrite:        No  # overwrite existing results?
   ask_continue:     Yes # prompt 'continue? (y/n)' after settings checks?
   exit_when_done:   Yes # exit monitor when all jobs are done
   log_size_limit:   300 # size of the log history per job in the monitor
   nb_jobs:          12  # maximum number of parallel synthesis

   architectures: 
      - Example_Counter_vhdl/04bits
      - Example_Counter_vhdl/08bits
      - Example_Counter_vhdl/16bits
      - Example_Counter_vhdl/24bits
      - Example_Counter_vhdl/32bits
      - Example_Counter_vhdl/48bits
      - Example_Counter_vhdl/64bits

Step 3: Choose synthesis frequencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Inside the directory ``odatix_userconfig/architectures``, each architecture is defined in a ``_settings.yml`` yaml file. 
You can change the synthesis frequencies in these files. You can define a list of frequencies, a range (lower and upper bounds and a step) or a combination of both.

The frequencies must be defined for each target.

Example:

.. code-block:: yaml
   :caption: odatix_userconfig/architectures/Example_Counter_verilog/_settings.yml
   :linenos:
   :lineno-start: 33

   xc7a100t-csg324-1:
      fmax_synthesis:
         lower_bound: 250
         upper_bound: 900
      custom_freq_synthesis:
         # list definition
         list: [50, 100]
   xc7k70t-fbg676-2:
      fmax_synthesis:
         lower_bound: 200
         upper_bound: 1800
      custom_freq_synthesis:
         # range definition
         lower_bound: 200
         upper_bound: 1800
         step: 200

Step 4: Choose your target device/technology
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Select the target device or technology in the yaml file corresponding to your EDA tool.

.. list-table::
   :header-rows: 1

   * - EDA Tool
     - Target File
   * - AMD Vivado
     - ``odatix_userconfig/target_vivado.yml``
   * - Synopsys Design Compiler
     - ``odatix_userconfig/target_design_compiler.yml``
   * - OpenLane
     - ``odatix_userconfig/target_openlane.yml``


Step 5: Run the selected designs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


.. tab:: Vivado

   .. code-block:: bash

      odatix freq --tool vivado

.. tab:: Design Compiler

   .. code-block:: bash

      odatix freq --tool design_compiler

.. tab:: Openlane

   .. code-block:: bash

      odatix freq --tool openlane


Step 6: Visualize and explore the results
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   odatix-explorer

Step 7: Try with your own design
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Check out section :doc:`/quick_start/add_design`
