---
title: "Install supported EDA tools"
date: 2026-05-15
author: "Jonathan Saussereau"
description: "Install and configure the EDA tools supported by Odatix."
categories: ["Tutorial", "Installation"]
tags: ["eda", "vivado", "openlane", "verilator", "ghdl"]
---

{{< toc >}}

# Synthesis

## Install OpenLane

OpenLane is a free and open-source automated RTL to GDSII flow based on several components including OpenROAD, Yosys, Magic, and Netgen.

<div class="flex justify-center mt-8">
{{< card
  title="OpenLane installation guide"
  link="https://openlane.readthedocs.io/en/latest/getting_started/installation/index.html"
  width="50%"
/>}}
</div>

> [!WARNING]
> Once installed, the installation path must be updated in the user target file for OpenLane.  
> Update `tool_install_path` inside `odatix_userconfig/targets/target_openlane.yml` after having initialized your directory.
>
> More information about initialization is available in the [Getting Started](/docs/getting-started/) section.


## Install Vivado

Vivado is a software suite dedicated to AMD (Xilinx) SoCs and FPGAs. Vivado ML Standard Edition (formerly WebPack Edition) has no cost for smaller devices.

<div class="flex justify-center mt-8">
{{< card
  title="AMD unified installer download page"
  link="https://www.xilinx.com/support/download.html"
  width="50%"
/>}}
</div>

> [!WARNING]
> Make sure your EDA tool is added to your `PATH` environment variable.

{{< tabs >}}

{{% tab name="Ubuntu/Debian" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ PATH=$PATH:<eda_tool_installation_path>
{{< /code >}}

{{% /tab %}}

{{% tab name="Fedora/AlmaLinux/RHEL" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ PATH=$PATH:<eda_tool_installation_path>
{{< /code >}}

{{% /tab %}}

{{% tab name="Arch Linux" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ PATH=$PATH:<eda_tool_installation_path>
{{< /code >}}

{{% /tab %}}

{{% tab name="Windows" %}}

{{< code lang=powershell filename="PowerShell" prompt="true" >}}
$ $env:PATH += "<eda_tool_installation_path>"
{{< /code >}}

{{% /tab %}}

{{< /tabs >}}

Replace `<eda_tool_installation_path>` with your own installation path.

Example of adding Vivado to the `PATH` environment variable (your installation path may be different):

{{< tabs >}}

{{% tab name="Ubuntu/Debian" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ PATH=$PATH:/opt/xilinx/Vivado/2024.1/bin
{{< /code >}}

{{% /tab %}}

{{% tab name="Fedora/AlmaLinux/RHEL" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ PATH=$PATH:/opt/xilinx/Vivado/2024.1/bin
{{< /code >}}

{{% /tab %}}

{{% tab name="Arch Linux" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ PATH=$PATH:/opt/xilinx/Vivado/2024.1/bin
{{< /code >}}

{{% /tab %}}

{{% tab name="Windows" %}}

{{< code lang=powershell filename="PowerShell" prompt="true" >}}
$ $env:PATH += ";C:\Xilinx\Vivado\2024.2\bin"
{{< /code >}}

{{% /tab %}}

{{< /tabs >}}


# Simulations

It is possible to use any simulator with Odatix. However, in the provided examples, the simulators used are Verilator and GHDL.


## Install Verilator

Verilator is a free and open-source simulator for Verilog/SystemVerilog.

{{< tabs >}}

{{% tab name="Ubuntu/Debian" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo apt update
$ sudo apt install -y verilator
{{< /code >}}

{{% /tab %}}

{{% tab name="Fedora/AlmaLinux/RHEL" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo dnf update
$ sudo dnf install -y verilator
{{< /code >}}

{{% /tab %}}

{{% tab name="Arch Linux" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo pacman -Syu
$ sudo pacman -S verilator --noconfirm
{{< /code >}}

{{% /tab %}}

{{% tab name="Windows" %}}

Verilator is not natively supported on Windows.
Consider using [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) to install Verilator.

{{% /tab %}}

{{< /tabs >}}


## Install GHDL

GHDL is a free and open-source simulator for VHDL.

{{< tabs >}}

{{% tab name="Ubuntu/Debian" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo apt update
$ sudo apt install -y ghdl
{{< /code >}}

{{% /tab %}}

{{% tab name="Fedora/AlmaLinux/RHEL" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo dnf update
$ sudo dnf install -y ghdl
{{< /code >}}

{{% /tab %}}

{{% tab name="Arch Linux" %}}

Install the [`ghdl-gcc`](https://aur.archlinux.org/packages/ghdl-gcc) package from the [AUR](https://wiki.archlinux.org/title/Arch_User_Repository).

{{% /tab %}}

{{% tab name="Windows" %}}

Install the [GHDL Windows binaries](http://ghdl.free.fr/download.html).

{{% /tab %}}


{{< /tabs >}}
