Welcome to Asterism's documentation!
====================================

**Asterism** is a toolbox designed to facilitate logical synthesis on various FPGA and ASIC tools such as Vivado and Design Compiler. 
It allows to easily find the maximum operating frequency of any digital architecture described with an HDL (VHDL, Verilog, SystemVerilog). RTL generation is also supported, using Chisel for example.

The primary feature of this framework lies in its capability to compare different architectural configurations using parameter files. 
With Asterism, users can effortlessly explore different architectural designs and evaluate their performance based on numerous metrics including Fmax, hardware resource utilization, power consumption, and more.

Asterism repository can be found at https://github.com/jsaussereau/Asterism

Key Features
------------

- Synthesis: Easily conduct logical synthesis on diverse FPGA and ASIC tools for various targets.
- Fmax search: Find the maximum frequency of the design on a specific target.
- Architecture Comparison: Easily compare architectural configurations using parameters.
- Interactive Results Exploration: Visualize, compare, and explore architecture implementation results based on various metrics for each target.

.. note::
  Please note that these tools are not included in Asterism and must be obtained separately.

Supported EDA tools
-------------------

.. list-table::
   :header-rows: 1

   * - EDA Tool
     - Status
   * - AMD Vivado
     - ✔️ supported
   * - Synopsys Design Compiler
     - ✔️ supported
   * - Intel Quartus Prime
     - 📅 planned


Contents
--------

.. toctree::

   installation
   quick_start
   add_design
