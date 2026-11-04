---
weight: 6
title: "Install the OSS CAD Suite"
date: 2026-11-03
author: "Jonathan Saussereau"
description: "One download for the open source tools Odatix runs: Yosys and nextpnr for FPGA synthesis, Verilator, Icarus Verilog and GHDL for simulation. Linux, macOS and Windows, no license."
categories: ["Tutorial", "Installation"]
tags: ["eda", "yosys", "nextpnr", "verilator", "ghdl", "open source", "windows"]
---

{{< toc >}}

The [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build) bundles the
open source tools of digital design into one archive, rebuilt every night. It
needs no administrator rights, no license and no package manager: extract it,
put its `bin` directory on the `PATH`, done.

For Odatix, it is the shortest way to a complete open source setup:

| Odatix tool | What it does | Commands of the suite |
|---|---|---|
| `yosys_fpga` | FPGA synthesis, placement and routing (Lattice ECP5, iCE40), Fmax | `yosys`, `nextpnr-ecp5`, `nextpnr-ice40`, `ghdl` (VHDL) |
| `yosys` | RTL analysis of Verilog and SystemVerilog | `yosys` |
| `verilator`, `icarus`, `ghdl` | Simulation and RTL analysis | `verilator`, `iverilog`, `ghdl` |

It weighs about 2.5 GB once extracted.

## Linux

The same archive runs on any distribution (Ubuntu, Debian, Fedora, Arch...):
everything it needs is inside.

### 1. Download

Take the latest `oss-cad-suite-linux-x64-<date>.tgz` from the
[releases page](https://github.com/YosysHQ/oss-cad-suite-build/releases/latest)
(`linux-arm64` on an ARM machine), or from a terminal:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ cd ~/Downloads
$ curl -s https://api.github.com/repos/YosysHQ/oss-cad-suite-build/releases/latest \
    | grep -o 'https://[^"]*linux-x64[^"]*\.tgz' \
    | xargs curl -L -o oss-cad-suite.tgz
{{< /code >}}

### 2. Extract

Anywhere you can write to, for instance `~/tools`:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p ~/tools
$ tar xzf oss-cad-suite.tgz -C ~/tools
$ ls ~/tools/oss-cad-suite
bin  environment  environment.fish  etc  examples  include  lib  libexec  license  py3bin  README  share  ...
{{< /code >}}

### 3. Put it on the PATH

Add its `bin` directory, **with an absolute path**, at the end of your shell's
startup file (`~/.bashrc`, or `~/.zshrc` for zsh):

{{< code lang=bash filename="~/.bashrc" >}}
export PATH="$HOME/tools/oss-cad-suite/bin:$PATH"
{{< /code >}}

With fish: `fish_add_path ~/tools/oss-cad-suite/bin`. Then open a new
terminal. The commands of `bin` are small scripts that set up
their own environment: nothing else is needed.

> [!WARNING] Do not source `environment` for Odatix
> The suite also ships an `environment` script (`source
> ~/tools/oss-cad-suite/environment`) that puts its own Python first on the
> `PATH` and sets `PYTHONHOME`. A shell set up that way runs `python` and `pip`
> from the suite, not the Python Odatix is installed in. Keep to the `PATH`
> line above.

> [!TIP] Without touching the PATH
> Leave the `PATH` alone and give the directory of the suite to Odatix instead,
> as `tool_install_path` in the target file of the tool
> (`odatix_userconfig/targets/target_yosys_fpga.yml`): Odatix puts its `bin`
> first on the `PATH` of the jobs of that tool only.
>
> ```yaml
> tool_install_path: ~/tools/oss-cad-suite
> ```

### 4. Check

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ yosys -V
Yosys 0.70+145 (git sha1 a31d95ea0, Release, Clang ...)
$ nextpnr-ecp5 --version
"nextpnr-ecp5" -- Next Generation Place and Route (Version nextpnr-0.11.1-...)
{{< /code >}}

`command not found`: the `PATH` line is in another startup file than the one
your shell reads, or it names a relative path (`.local/...` instead of
`$HOME/.local/...`), which only works from your home directory.

## Windows

The Windows build runs natively: no WSL needed for `yosys_fpga`, `yosys`
analyses or GHDL simulations.

### 1. Download

Take the latest `oss-cad-suite-windows-x64-<date>.exe` from the
[releases page](https://github.com/YosysHQ/oss-cad-suite-build/releases/latest).
It is a self-extracting archive, not an installer.

### 2. Extract

Run it and choose a directory **without spaces** in its path, such as
`C:\tools`. It creates `C:\tools\oss-cad-suite`.

> [!NOTE] SmartScreen
> Windows may warn about an unrecognized application: **More info**, then
> **Run anyway**. Your organization may also forbid running downloaded
> executables; ask for the archive to be allowed, or use
> [WSL](/install/eda_tools/#tools-of-linux-on-windows-wsl) and the Linux
> archive.

### 3. Put it on the PATH

Unlike on Linux, the programs of `bin` need the libraries of `lib`: **both**
directories go on the `PATH`.

{{< tabs >}}

{{% tab name="Settings window" %}}

1. Press <kbd>Win</kbd>, type *environment variables*, open **Edit environment
   variables for your account**.
2. Select **Path**, then **Edit**.
3. **New**: `C:\tools\oss-cad-suite\bin`. **New** again:
   `C:\tools\oss-cad-suite\lib`.
4. **OK** in both windows, then open a new terminal: a terminal opened before
   keeps the old `PATH`.

{{% /tab %}}

{{% tab name="PowerShell" %}}

{{< code lang=powershell filename="PowerShell" >}}
$suite = "C:\tools\oss-cad-suite"
$path = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", "$suite\bin;$suite\lib;$path", "User")
{{< /code >}}

Then open a new terminal.

{{% /tab %}}

{{% tab name="For one terminal only" %}}

The suite's `start.bat` opens a command prompt set up for it, and
`environment.bat` sets up the one you are in:

{{< code lang=bat filename="Command prompt" >}}
C:\> C:\tools\oss-cad-suite\environment.bat
{{< /code >}}

Start Odatix (`odatix`, `odatix-gui`) from that prompt. Like on Linux, this
script puts the suite's Python first: run Odatix through the full path of
your own Python if `odatix` is then not found.

{{% /tab %}}

{{< /tabs >}}

### 4. Check

{{< code lang=powershell filename="PowerShell" >}}
PS> yosys -V
PS> nextpnr-ecp5 --version
{{< /code >}}

A missing DLL error means `lib` is not on the `PATH`.

## macOS

Take `oss-cad-suite-darwin-arm64-<date>.tgz` (Apple silicon) or `darwin-x64`
(Intel), and follow the [Linux](#linux) steps. macOS blocks the programs of a
downloaded archive: run `./activate` once, from the extracted `oss-cad-suite`
directory, to allow them.

## Check with Odatix

From a workspace with the examples (`odatix init --examples`):

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax -t yosys_fpga -a "Example_Counter_verilog/08bits" -y
{{< /code >}}

The **Tools** page of `odatix-gui` shows the tool as installed, and the run
ends with the maximum frequency of the counter on an ECP5 (the target of
`target_yosys_fpga.yml`).

## Update

The suite is one directory: download a newer archive, extract it in place of
the old one, nothing else changes. Keeping one version for a whole class or
project is as simple: keep the archive.

## Troubleshooting

| Symptom | Cause, fix |
|---|---|
| `yosys: command not found` | The `PATH` names a relative path, another directory than `bin`, or was changed after the terminal opened. |
| `odatix` now runs another Python, or no longer starts | `environment` (or `environment.bat`) was sourced: it puts the suite's Python first. Put `bin` on the `PATH` instead. |
| Windows: *The code execution cannot proceed because ... .dll was not found* | `lib` is missing from the `PATH`. |
| `Can't load module './ghdl'` in a Yosys log | The GHDL plugin of this build does not match its Yosys. `yosys_fpga` does not use it (it runs `ghdl` itself), only scripts of your own calling `plugin -i ghdl` are affected. |
| `yosys_fpga` reports a package with too few I/Os | nextpnr places every port of the design on a pin: take a larger package in `target_yosys_fpga.yml`. |
