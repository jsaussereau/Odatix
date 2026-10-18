# Odatix

[![GitHub](https://img.shields.io/badge/GitHub-Odatix-blue.svg?logo=github)](https://github.com/jsaussereau/Odatix)
[![PyPi Package](https://img.shields.io/pypi/v/odatix)](https://pypi.org/project/odatix/)
[![cite](https://img.shields.io/badge/cite-DOI%3A10.1016/j.softx.2024.101970-green)](https://www.sciencedirect.com/science/article/pii/S2352711024003406)
[![GitHub License](https://img.shields.io/github/license/jsaussereau/Odatix)](https://github.com/jsaussereau/Odatix/blob/main/LICENSE)
[![Documentation Status](https://readthedocs.org/projects/odatix/badge/?version=latest)](https://odatix.readthedocs.io/en/latest/docs/)

**Odatix** is a **powerful tool** designed to facilitate **implementation** and **validation** of configurable digital designs across multiple **FPGA** and **ASIC** tools, including **Vivado**, **OpenLane**, and **Design Compiler**.

Odatix enables designers to:

- **Explore different architectural configurations** using parameter definition and generation.
- **Automatically find the maximum operating frequency** (`Fmax`) of any digital design.
- **Run logical synthesis for every desired clock speed** of any digital design.
- **Run simulations** to validate and benchmark your design.
- **Run simulation/synthesis jobs in parallel** to get results faster.
- **Compare architectures based on multiple metrics**, such as Fmax, power consumption, and resource utilization.
- **Visualize results interactively** in a web-based dashboard.

## 🚀 Key Features

✅ **Architecture Exploration**  
   - Easily define and generate multiple design configurations, regardless of the HDL used (**VHDL, Verilog, SystemVerilog**, and even **Chisel or HLS**).

✅ **Automated Synthesis**  
   - Run **synthesis on FPGA and/or ASIC tools** for **each configuration** of a design on various targets.
   - Perform **fixed-frequency synthesis** to analyze design behavior at specific clock speeds.
   - Automatically determine **maximum operating frequency (Fmax)**.

✅ **Efficient Simulation**  
   - Execute simulations for **each configuration** of a design.
   - **Validate** functionality and gather **benchmark** results.

✅ **Job Monitoring**  
   - **Track** parallel synthesis/simulation **jobs progress and logs** in real-time.
   - Start, pause, resume, or kill jobs effortlessly.

✅ **Interactive Results Exploration**  
   - **Analyze results visually** with built-in support for **line, column, scatter, and radar charts**.
   - Export charts in **vector** (SVG) or **raster** (PNG, JPEG, WEBP) **formats**.
   - Customize the appearance of your figures with different **themes**.

✅ **Quick Start**  
   - [Install](https://odatix.readthedocs.io/en/latest/install/pypi/) Odatix **easily** from PyPi with `pip`.
   - Use **built-in examples** and [step-by-step tutorials](https://odatix.readthedocs.io/en/latest/tutorials/) to get started quickly.
   - Need help? [Contact us](mailto:jonathan.saussereau@ims-bordeaux.fr?Subject=[Odatix]) or open an issue on [GitHub](https://github.com/jsaussereau/Odatix/issues).

## 💡 Highlights

### 🖥️ **Job Monitor**
- Track **all running jobs** (synthesis or simulation) in a user-friendly interactive interface.
- **Live updates** of job progress and logs.
- **Full control**: start, pause, resume, or kill jobs at any time.

![Odatix Job Monitor](./sources/images/odatix/odatix.png)

### 📊 **Odatix Explorer**
- **Interactive web interface** for deep result exploration.
- Compare architectures visually using **line, column, scatter, or radar charts**.
- **Export high-quality charts** in both **raster (PNG, JPEG, WEBP)** and **vector (SVG)** formats.

Examples:
- **Line chart** of a metric (Fmax here) for multiple designs and configurations on different targets (FPGA here):
![Fmax comparison for various ALU designs and configurations on two different FPGA targets](./sources/images/odatix-explorer/odatix-explorer-lines.png)

- **Column chart** of a metric (Fmax here) for multiple designs and configurations on different targets (FPGA here):
![Column chart of Fmax for multiple ALU designs and configurations on different FPGA architectures](./sources/images/odatix-explorer/odatix-explorer-columns.png)

- **Radar chart** of a metric (Fmax here) for multiple designs and configurations on different targets (FPGA here):
![Radar chart: Comparative analysis of multiple implementation metrics of multiple ALU configurations across two different FPGA targets](./sources/images/odatix-explorer/odatix-explorer-radar.png)

- Comparison of a metric (power consumption here) **at different operating frequencies** for multiple designs and configurations on different targets (FPGA here):
![Power analysis at different operating frequencies for multiple configurations of a counter](./sources/images/odatix-explorer/odatix-explorer-columns-freq.png)

- **Scatter plot**: Correlation between 2 metrics (power consumption and Fmax here) for multiple designs and configurations on different targets (FPGA here):
![Scatter plot: Correlation between power consumption and Fmax for various ALU designs](./sources/images/odatix-explorer/odatix-explorer-scatter.png)

- **Scatter 3D plot**: Correlation between 3 metrics (LUT count, register counter and Fmax here) for multiple designs and configurations on different targets (FPGA here):
![Scatter 3D plot: Correlation between LUT count, register counter and Fmax for various AsteRISC configurations](./sources/images/odatix-explorer/odatix-explorer-scatter3d.png)

- **Overview**: Comparative analysis of **multiple implementation metrics** for multiple designs and configurations on different targets (FPGA here):
![Overview: Comparative analysis of multiple implementation metrics of multiple ALU configurations across two different FPGA targets](./sources/images/odatix-explorer/odatix-explorer-overview.png)

## 🛠 Supported EDA Tools

> [!NOTE]
> Please note that these tools are not included in Odatix and must be obtained separately.

### **Synthesis**

| EDA Tool                                                         | Status              |
| :--------------------------------------------------------------- | :------------------ |
| AMD Vivado                                                       | ✔️ supported        |
| Intel Quartus Prime                                              | ✔️ supported        |
| Synopsys Design Compiler (and DC NXT)                            | ✔️ supported        |
| Cadence Genus                                                    | ✔️ supported        |
| [LibreLane](https://github.com/librelane/librelane)              | ✔️ supported        |
| [OpenLane 1](https://github.com/The-OpenROAD-Project/OpenLane)   | ✔️ supported        |

### **Place & route**

| EDA Tool                                                         | Status              |
| :--------------------------------------------------------------- | :------------------ |
| Cadence Innovus                                                  | ✔️ supported        |
| Synopsys IC Compiler II                                          | 🧪 experimental     |

See [Install supported EDA tools](https://odatix.readthedocs.io/en/latest/install/eda_tools/) for how to set each one up.

### **Simulation**
Odatix can work with virtually **any simulator**.  
By default, **examples for Verilator and GHDL** are provided.

For more details, check the guide: [Simulate your own RTL](https://odatix.readthedocs.io/en/latest/tutorials/own_designs/simulations/).

## 🏁 Get Started Today!

1️⃣ **Install Odatix and one of the supported EDA Tools**  
   Follow the instructions in the [installation guide](https://odatix.readthedocs.io/en/latest/install/), then [install an EDA tool](https://odatix.readthedocs.io/en/latest/install/eda_tools/).

2️⃣ **Run a Quick Test on Built-in Examples**  
   Run the [built-in examples](https://odatix.readthedocs.io/en/latest/tutorials/run_examples/), or follow [Getting started](https://odatix.readthedocs.io/en/latest/docs/getting-started/).

3️⃣ **Define Your Own Architectures**  
   Follow [Add your own design](https://odatix.readthedocs.io/en/latest/tutorials/own_designs/) to configure and run your own designs.

4️⃣ **Analyze Your Results**  
   Visualize your synthesis and simulation results with [**Odatix Explorer**](https://odatix.readthedocs.io/en/latest/docs/features/explorer/).

## 📰 Citation

**DOI**: [https://doi.org/10.1016/j.softx.2024.101970](https://www.sciencedirect.com/science/article/pii/S2352711024003406)

### **BibTeX**
```bibtex
@article{SAUSSEREAU2025101970,
  title = {Odatix: An open-source design automation toolbox for FPGA/ASIC implementation},
  journal = {SoftwareX},
  volume = {29},
  pages = {101970},
  year = {2025},
  issn = {2352-7110},
  doi = {https://doi.org/10.1016/j.softx.2024.101970},
  url = {https://www.sciencedirect.com/science/article/pii/S2352711024003406},
  author = {Jonathan Saussereau and Christophe Jego and Camille Leroux and Jean-Baptiste Begueret},
  keywords = {Design automation, Design space exploration, Hardware, Computer-aided design, Design flow, FPGA, ASIC}
}
```
---

## 📧 Contact

For any inquiries or support, feel free to contact me at jonathan.saussereau@ims-bordeaux.fr.

*Note: Odatix is under active development, and we appreciate your feedback and contributions to make it even more powerful and user-friendly.*
