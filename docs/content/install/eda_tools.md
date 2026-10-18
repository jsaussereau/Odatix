---
weight: 5
title: "Install supported EDA tools"
date: 2026-05-15
author: "Jonathan Saussereau"
description: "Install and configure the EDA tools supported by Odatix."
categories: ["Tutorial", "Installation"]
tags: ["eda", "vivado", "quartus", "openlane", "verilator", "ghdl"]
---

{{< toc >}}

# Synthesis

## Install LibreLane

LibreLane is the open-source RTL to GDSII flow that succeeds OpenLane 2: Yosys
for synthesis, OpenROAD for floorplan, placement, clock tree, routing and
timing, Magic, KLayout and Netgen for signoff. Its tools come through Nix:

{{< code lang=bash filename="LibreLane through Nix" >}}
git clone https://github.com/librelane/librelane ~/librelane
cd ~/librelane
nix-shell                  # the first run downloads the tools
librelane --smoke-test     # installs the sky130 PDK through ciel and runs a small design
{{< /code >}}

<div class="flex justify-center mt-8">
{{< card
  title="LibreLane installation guide"
  link="https://librelane.readthedocs.io/en/latest/installation/nix_installation/index.html"
  width="50%"
/>}}
</div>

> [!WARNING]
> With a multi-user Nix install, the Nix daemon must be running
> (`sudo systemctl enable --now nix-daemon.socket`), otherwise `nix-shell` fails
> with `creating directory '/nix/store/.links': Permission denied`. Add the
> LibreLane binary cache to `/etc/nix/nix.conf` (see the LibreLane guide), or Nix
> builds every tool from source.

> [!NOTE]
> Odatix runs LibreLane from the checkout given as `tool_install_path` in
> `odatix_userconfig/targets/target_librelane.yml`, through its `nix-shell`.
> Leave it empty when `librelane` is already on your `$PATH` (Odatix started from
> that `nix-shell`). The targets of that file are the open PDKs LibreLane
> supports: `sky130_hd`, `sky130_hs`, `sky130_ms`, `gf180mcu_7t`, `gf180mcu_9t`
> and `ihp_sg13g2`. LibreLane installs a PDK the first time it is used.

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
> Make sure the directory of the tool's executables is in your `PATH`
> environment variable: Odatix runs `vivado` the way you would in a terminal.

{{< tabs >}}

{{% tab name="Linux" %}}

AMD ships a script that sets up the whole environment of Vivado, `PATH`
included. Source it in the terminal you run Odatix from (your installation path
may be different):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ source /opt/Xilinx/Vivado/2024.2/settings64.sh
{{< /code >}}

Or add the directory of the executables yourself:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ export PATH=$PATH:/opt/Xilinx/Vivado/2024.2/bin
{{< /code >}}

Either way, it only lasts for that terminal: add the line to your `~/.bashrc`
(or the start-up file of your shell) to keep it.

{{% /tab %}}

{{% tab name="Windows" %}}

{{< code lang=powershell filename="PowerShell" prompt="true" >}}
$ $env:PATH += ";C:\Xilinx\Vivado\2024.2\bin"
{{< /code >}}

This only lasts for that PowerShell window: to keep it, add the directory to
the `Path` variable of your account in the *Environment Variables* settings.

{{% /tab %}}

{{< /tabs >}}

Check that the tool answers, from the terminal you will run Odatix from:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ vivado -version
{{< /code >}}

The same goes for every tool of this page: replace the path above with the
`bin` directory of your own installation.

## Install Quartus

Quartus Prime is Altera's software suite for its FPGAs. Odatix drives the Pro
Edition (Agilex, Stratix 10, Arria 10…); it is validated with Quartus Prime Pro
26.1.1 on Linux, on Agilex 3, 5 and 7 devices.

<div class="flex justify-center mt-8">
{{< card
  title="Altera download center"
  link="https://www.altera.com/downloads"
  width="50%"
/>}}
</div>

Odatix finds the Quartus executables (`quartus_sh`, `quartus_syn`, `quartus_fit`…)
on your `PATH`:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ PATH=$PATH:/opt/altera/altera_pro/26.1.1/quartus/bin
{{< /code >}}

Or, without touching the `PATH`, set `tool_install_path` in
`odatix_userconfig/targets/target_quartus.yml` to the directory holding
`qinit.sh`:

{{< code lang=yaml filename="odatix_userconfig/targets/target_quartus.yml" >}}
tool_install_path: "/opt/altera/altera_pro/26.1.1"
{{< /code >}}

> [!NOTE]
> Odatix does not source `qinit.sh`: the script finds the installation through
> `BASH_SOURCE`, so sourcing it from another shell (zsh) with an absolute path
> does not work. It adds `quartus/bin` and `qsys/bin` to the `PATH` itself.

## Synopsys and Cadence tools

Design Compiler (and Design Compiler NXT), IC Compiler II, Genus and Innovus
come from their vendors, with a license server, and are usually set up by your
CAD team. Odatix needs nothing more than a terminal where they already work:
their executables (`dc_shell`, `dcnxt_shell`, `icc2_shell`, `genus`, `innovus`)
on the `PATH`, and the license variables of your site set. Check it with:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ dc_shell -version
$ genus -version
{{< /code >}}

These tools also need a technology: the targets their target files list
(`odatix_userconfig/targets/target_design_compiler.yml`,
`target_genus.yml`...) are only examples. See
[Add targets](/tutorials/own_flows/add_targets/).


# Simulations

Any simulator can be used with Odatix. Its [simulation
templates](/docs/reference/simulation/#templates) drive GHDL, Verilator, Icarus
Verilog, Questa/ModelSim and the Vivado simulator, and the provided examples use
GHDL, Verilator, Questa/ModelSim and the Vivado simulator. You only need one of
them: a simulation whose simulator is not in the `PATH` is reported when the run
is checked, and skipped.

GHDL (VHDL), Verilator and Icarus Verilog (Verilog, SystemVerilog) are free and
packaged by most Linux distributions.


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


## Install Icarus Verilog

Icarus Verilog is a free and open-source simulator for Verilog, and part of
SystemVerilog. Its commands are `iverilog` and `vvp`.

{{< tabs >}}

{{% tab name="Ubuntu/Debian" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo apt update
$ sudo apt install -y iverilog
{{< /code >}}

{{% /tab %}}

{{% tab name="Fedora/AlmaLinux/RHEL" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo dnf install -y iverilog
{{< /code >}}

{{% /tab %}}

{{% tab name="Arch Linux" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo pacman -S iverilog --noconfirm
{{< /code >}}

{{% /tab %}}

{{% tab name="Windows" %}}

Install the [Icarus Verilog Windows binaries](https://bleyer.org/icarus/).

{{% /tab %}}

{{< /tabs >}}


## Questa, ModelSim and the Vivado simulator

Questa and ModelSim come from Siemens, with a license, and the Vivado simulator
(`xvlog`, `xvhdl`, `xelab`, `xsim`) with [Vivado](#install-vivado). Odatix only
needs their executables on the `PATH`. Check it with:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ vsim -version
$ xsim -version
{{< /code >}}

The **Simulators** section of the **Tools** page of `odatix-gui` says which
simulators Odatix finds.
