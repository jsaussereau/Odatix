Quick Start
===========

Step 1: Choose the designs you want to implement
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Uncomment the architectures you want to implement in ``architecture_select.yml``

Step 2: Choose your target device/technology
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Select the target devide or technology in the yaml file corresponding to your EDA tool.

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
