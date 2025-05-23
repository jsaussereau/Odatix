**************
Fmax synthesis
**************

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

Uncomment the architectures you want to implement in ``odatix_userconfig/fmax_synthesis_settings.yml``.
Those architectures are defined in ``odatix_userconfig/architectures``.

Change the value of ``nb_jobs`` in ``odatix_userconfig/fmax_synthesis_settings.yml`` depending on the number of logical cores available on your CPU. 

.. tip::
   75% of your number of logical cores is usually a good balance for ``nb_jobs``.

Example:

.. code-block:: yaml
   :caption: odatix_userconfig/fmax_synthesis_settings.yml
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

Step 3: Choose your target device/technology
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


Step 4: Run the selected designs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


.. tab:: Vivado

   .. code-block:: bash

      odatix fmax --tool vivado

.. tab:: Design Compiler

   .. code-block:: bash

      odatix fmax --tool design_compiler

.. tab:: Openlane

   .. code-block:: bash

      odatix fmax --tool openlane


Step 5: Visualize and explore the results
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   odatix-explorer

Step 6: Try with your own design
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Check out section :doc:`/quick_start/add_design`
