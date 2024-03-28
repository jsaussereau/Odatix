# Welcome to Asterism!

Asterism is a framework designed to facilitate logical synthesis on various FPGA and ASIC tools such as Vivado and Design Compiler. 
It allows to easily find the maximum operating frequency of any digital architecture described with an HDL (VHDL, Verilog, SystemVerilog).

The primary feature of this framework lies in its capability to compare different architectural configurations using parameter files. 
With Asterism, users can effortlessly explore different architectural designs and evaluate their performance based on numerous metrics including Fmax, hardware resource utilization, power consumption, and more.

# Key Features:

- Synthesis: Easily conduct logical synthesis on diverse FPGA and ASIC tools for various targets.
- Fmax search: Find the maximum frequency of the design on a specific target.
- Architecture Comparison: Easily compare architectural configurations using parameters.
- Interactive Results Exploration: Explore, visualize and compare architectures implementation results between based on various metrics for each target.

# Quick start guide

1. Install Python 3.6+
2. Install Python requirements listed in requirements.txt
3. Run the example design : `make all`
4. Explore the results : `make explore`

# Supported EDA tools

The following EDA tools are currently supported:
- AMD Vivado
- Synopsys Design Compiler

Please note that these tools are not included in Asterism and must be obtained separately.

*Support for other tools such as Intel Quartus Prime is planned.*

# Contributing

Contributions are welcome! Please refer to the contribution guidelines before making any pull requests.

# Contact

For any inquiries or support, feel free to contact me at jonathan.saussereau@ims-bordeaux.fr.

*Note: Asterism is under active development, and we appreciate your feedback and contributions to make it even more powerful and user-friendly.*
