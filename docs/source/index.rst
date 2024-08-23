Odatix
========

.. |License| image:: https://img.shields.io/github/license/jsaussereau/Odatix
  :target:  https://github.com/jsaussereau/Odatix/blob/main/LICENSE

.. |Docs| image:: https://readthedocs.org/projects/odatix/badge/?version=latest
  :target:  https://odatix.readthedocs.io

.. |GitHub| image:: https://img.shields.io/badge/GitHub-Odatix-blue.svg?logo=github
  :target:  https://github.com/jsaussereau/Odatix

.. |PyPi| image:: https://img.shields.io/pypi/v/odatix
  :target:  https://pypi.org/project/odatix/


|GitHub| |PyPi| |License| |Docs|

**Odatix** is a toolbox designed to facilitate logical synthesis of configurable designs on various FPGA and ASIC tools such as Vivado and Design Compiler. 
It allows to easily find the maximum operating frequency of any digital architecture described with an HDL (VHDL, Verilog, SystemVerilog, Chisel).

The primary feature of this toolbox lies in its capability to compare different architectural configurations using parameter files. 
With Odatix, users can effortlessly explore different architectural configurations and evaluate their performance based on numerous metrics including Fmax, hardware resource utilization, power consumption, and more.

Odatix also enables parallel simulations of different configurations of the same design. This is useful both for validation and for comparing configurations, as with benchmarks. 

Key Features
------------

- Synthesis: Easily conduct logical synthesis on diverse FPGA and ASIC tools for various targets.
- Architecture Comparison: Easily compare architectural configurations using parameters.
- Fmax search: Find the maximum frequency of the design on a specific target for each configuration of your design.
- Simulation: Run simulations for each configuration of your design.
- Interactive Results Exploration: Visualize, compare, and explore architecture implementation results based on various metrics for each target.

Supported EDA tools
-------------------

.. note::
  Please note that these tools are not included in Odatix and must be obtained separately.

Synthesis
~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - EDA Tool
     - Status
   * - AMD Vivado
     - ✔️ supported
   * - Synopsys Design Compiler
     - ✔️ supported
   * - `OpenLane 1 <https://github.com/The-OpenROAD-Project/OpenLane>`_
     - ✔️ supported
   * - `F4PGA <https://github.com/chipsalliance/f4pga>`_
     - 📅 planned
   * - Intel Quartus Prime
     - 📅 planned

Simulation
~~~~~~~~~~

Virtually any simulator! Check out the section :doc:`/userguide/add_simulation` for more information.

Odatix includes examples for Verilator and GHDL.

Contents
--------

.. toctree::
  :maxdepth: 2

  installation/index
  
  quick_start/index

  userguide/index

  documentation/commands
  documentation/settings
