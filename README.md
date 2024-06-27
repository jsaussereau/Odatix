# Asterism

[![GitHub](https://img.shields.io/badge/GitHub-Asterism-blue.svg?logo=github)](https://github.com/jsaussereau/Asterism)
[![GitHub License](https://img.shields.io/github/license/jsaussereau/Asterism)](https://github.com/jsaussereau/Asterism/blob/main/LICENSE)
[![Documentation Status](https://readthedocs.org/projects/asterism/badge/?version=latest)](https://asterism.readthedocs.io)

**Asterism** is a toolbox designed to facilitate logical synthesis of configurable designs on various FPGA and ASIC tools such as Vivado and Design Compiler. 
It allows to easily find the maximum operating frequency of any digital architecture described with an HDL (VHDL, Verilog, SystemVerilog, Chisel).

The primary feature of this toolbox lies in its capability to compare different architectural configurations using parameter files. 
With Asterism, users can effortlessly explore different architectural configurations and evaluate their performance based on numerous metrics including Fmax, hardware resource utilization, power consumption, and more.

Asterism also enables parallel simulations of different configurations of the same design. This is useful both for validation and for comparing configurations, as with benchmarks. 

## Key Features

- Synthesis: Easily conduct logical synthesis on diverse FPGA and ASIC tools for various targets.
- Architecture Comparison: Easily compare architectural configurations using parameters.
- Fmax search: Find the maximum frequency of the design on a specific target.
- Simulation: Run simulations for each configuration of your design.
- Interactive Results Exploration: Visualize, compare, and explore architecture implementation results based on various metrics for each target.

## Supported EDA tools

> [!NOTE]
> Please note that these tools are not included in Asterism and must be obtained separately.

### Synthesis

| EDA Tool                 | Status              |
| :----------------------- | :------------------ |
| AMD Vivado               | ✔️ supported        |
| Synopsys Design Compiler | ✔️ supported        |
| Intel Quartus Prime      | 📅 planned          |

### Simulation

Virtually any simulator! Check out the section [Add your own simulation](https://asterism.readthedocs.io/en/latest/userguide/add_simulation.html) for more information.

Asterism includes examples for Verilator and GHDL.

## Contents

- [Installation](https://asterism.readthedocs.io/en/latest/userguide/installation.html)
- [Quick start](https://asterism.readthedocs.io/en/latest/userguide/quick_start.html)
- [Add your own design](https://asterism.readthedocs.io/en/latest/userguide/add_design.html)
- [Add your own simulation](https://asterism.readthedocs.io/en/latest/userguide/add_simulation.html)
- [Useful commands](https://asterism.readthedocs.io/en/latest/documentation/commands.html)
- [Settings documentation](https://asterism.readthedocs.io/en/latest/documentation/settings.html)

  
## Contact

For any inquiries or support, feel free to contact me at jonathan.saussereau@ims-bordeaux.fr.

*Note: Asterism is under active development, and we appreciate your feedback and contributions to make it even more powerful and user-friendly.*
