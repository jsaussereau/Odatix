---
title: "Add targets"
date: 2026-05-15
# author: "Jonathan Saussereau"
weight: 3
description: ""
categories: ["Tutorial", "EDA Tools"]
tags: ["tools", "custom", "yaml"]
featured_image: "/images/tutorials/add-tools.svg"
---

{{< toc >}}

# Context 

ASIC EDA tools require the standard cell libaries to be defined. This is usually done through an init script. In Odatix you can select an init script for each target. Thus, users are free to define as many targets as they want for any ASIC technoloy of FPGA circuit.
In this tutorial, you will learn how to ass custom targets to odatix.

## Prerequisites

For this tutorial, you need **at least one** of the following tools installed and available in your `PATH`:
- [Verilator](https://www.veripool.org/verilator/)
- [GHDL](https://github.com/ghdl/ghdl)
- [QuestaSim](https://www.mentor.com/products/fv/questa/) / [ModelSim](https://www.mentor.com/products/fv/modelsim/)
- [Vivado](https://www.xilinx.com/products/design-tools/vivado.html)

Make sure you have [Odatix installed](/install/) and available in your `PATH`. For example, if you installed Odatix in a virtual environment, activate it first:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ source odatix_venv/bin/activate
{{< /code >}}

## Steps

### Step 1 — Initialize an example workspace

Create a new directory for the demonstration and move into it. For example:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir ~/odatix_examples && cd ~/odatix_examples
{{< /code >}}

Create a new Odatix workspace and copy the built-in examples into it:

{{< code lang=bash filename="Terminal" prompt="true" fold="true" ansi="true" >}}
$ odatix init --examples

 ██████╗  ██████╗   █████╗ ████████╗ ██╗ ██╗  ██╗
██╔═══██╗ ██╔══██╗ ██╔══██╗╚══██╔══╝ ██║ ╚██╗██╔╝
██║   ██║ ██║  ██║ ███████║   ██║    ██║  ╚███╔╝ 
██║   ██║ ██║  ██║ ██╔══██║   ██║    ██║  ██╔██╗ 
╚██████╔╝ ██████╔╝ ██║  ██║   ██║    ██║ ██╔╝ ██╗
 ╚═════╝  ╚═════╝  ╚═╝  ╚═╝   ╚═╝    ╚═╝ ╚═╝  ╚═╝

<font color="#555753">[settings.py]</font> <font color="#8AE234">Your directory can now be used by Odatix!</font>
<font color="#555753">[settings.py]</font> Run <b>odatix -h</b> to get a list of useful commands
{{< /code >}}

### Step 2 — Add you target