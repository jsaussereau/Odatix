# Welcome to Asterism!

Asterism is a framework designed to facilitate logical synthesis on various FPGA and ASIC tools such as Vivado and Design Compiler. 
It allows to easily find the maximum operating frequency of any digital architecture described with an HDL (VHDL, Verilog, SystemVerilog).

The primary feature of this framework lies in its capability to compare different architectural configurations using parameter files. 
With Asterism, users can effortlessly explore different architectural designs and evaluate their performance based on numerous metrics including Fmax, hardware resource utilization, power consumption, and more.

# Key Features

- Synthesis: Easily conduct logical synthesis on diverse FPGA and ASIC tools for various targets.
- Fmax search: Find the maximum frequency of the design on a specific target.
- Architecture Comparison: Easily compare architectural configurations using parameters.
- Interactive Results Exploration: Explore, visualize and compare architectures implementation results between based on various metrics for each target.

# Supported EDA tools

| EDA Tool                 | Status              |
| :----------------------- | :------------------ |
| AMD Vivado               | ✔️ supported        |
| Synopsys Design Compiler | 🚧 work in progress |
| Intel Quartus Prime      | 📅 planned          |

*Please note that these tools are not included in Asterism and must be obtained separately.*

# Quick start guide

1. Install Python 3.6+
2. Install Python requirements listed in requirements.txt
3. Install one of the supported EDA tools (e.g. Vivado) and make sure it is added to your PATH environment variable
4. Choose the designs you want to implement by uncommenting them in `architecture_select.yml`
5. Choose your target device/technology in the yaml file corresponding to your EDA tool. For Vivado: `target_vivado.yml`
6. Run the selected designs. For Vivado: `make vivado`
7. Visualize and explore the results: `make explore`

# Add your own design

1. Create a folder named after your design in the `architectures` folder.
2. Add a `_settings.yml` in the folder and fill it with the template bellow
```yaml
---
#rtl path, relative to "architectures" parent directory (Asterism root), not this directory
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
```
3. Edit the file so it matches your design source files directory, top level filename, module name, and clock signal name.
4. Set `start_delimiter` and `stop_delimiter` so it matches the delimiters of the parameter section in your top level source file.
5. Add parameter files to the folder containing the parameter section of your top level source file with the desired values.
6. Add target specific bounds for the binary search.

# Contact

For any inquiries or support, feel free to contact me at jonathan.saussereau@ims-bordeaux.fr.

*Note: Asterism is under active development, and we appreciate your feedback and contributions to make it even more powerful and user-friendly.*
