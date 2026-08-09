---
title: "Install Odatix offline"
date: 2026-05-15
author: "Jonathan Saussereau"
description: "Instructions for installing Odatix offline."
categories: ["Tutorial", "Installation"]
tags: ["install", "offline"]
# featured_image: "/images/blog/modules.svg"
---

{{< toc >}}


> [!WARNING]
> Odatix provides partial support for Windows. For a better experience, it is recommended to use Linux.

## How it works

An offline installation is a regular [PyPI installation](/install/pypi/) split in two: you download Odatix and all of its dependencies once on a machine that has internet access, then you copy the resulting folder to the machine that does not, and install from there.

You therefore need two machines:

- the **online machine**, used only to download the packages,
- the **offline machine**, where Odatix will actually run.

> [!NOTE]
> Both machines should run the same operating system and the same Python version.
> Some of Odatix's dependencies (`numpy`, `pandas`) ship compiled binaries, which are specific to a platform and a Python version. See [Downloading for a different platform](#downloading-for-a-different-platform) if this is not the case.


## Prerequisites

On the **online machine**:

- Python 3.6+
- A way to transfer files to the offline machine (USB drive, internal share, `scp`, …)

On the **offline machine**:

- Python 3.6+
- make
- At least one supported EDA tool for synthesis workflows

Since the offline machine has no internet access, these prerequisites must be installed beforehand, from your distribution's installation media or from an internal package mirror.

{{< tabs >}}

{{% tab name="Ubuntu/Debian" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo apt install -y python3 python3-pip python3-venv make
{{< /code >}}
{{% /tab %}}

{{% tab name="Fedora/AlmaLinux/RHEL" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo dnf install -y python3 make
{{< /code >}}
{{% /tab %}}

{{% tab name="ArchLinux" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo pacman -S python3 make --noconfirm
{{< /code >}}
{{% /tab %}}

{{% tab name="macOS" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ brew install python make
{{< /code >}}
{{% /tab %}}

{{% tab name="Windows" %}}
{{< code lang=bash filename="Terminal Powershell" prompt="true" >}}
$ winget install -e --id Python.Python.3
$ winget install -e --id GnuWin32.Make
{{< /code >}}
{{% /tab %}}

{{< /tabs >}}

Check the Python version on **both** machines, and make sure they match:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 --version
{{< /code >}}

> [!IMPORTANT]
> If the versions do not match, don't worry: you can still download the packages for a different platform. See [Downloading for a different platform](#downloading-for-a-different-platform).

## Step 1: Download Odatix on the online machine

Download Odatix and every package it depends on into a local folder:

{{< tabs >}}

{{% tab name="Ubuntu/Debian" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m pip download odatix -d odatix_offline
{{< /code >}}
{{% /tab %}}

{{% tab name="Fedora/AlmaLinux/RHEL" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m pip download odatix -d odatix_offline
{{< /code >}}
{{% /tab %}}

{{% tab name="ArchLinux" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m pip download odatix -d odatix_offline
{{< /code >}}
{{% /tab %}}

{{% tab name="macOS" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m pip download odatix -d odatix_offline
{{< /code >}}
{{% /tab %}}

{{% tab name="Windows" %}}
{{< code lang=bash filename="Terminal Powershell" prompt="true" >}}
$ python -m pip download odatix -d odatix_offline
{{< /code >}}
{{% /tab %}}

{{< /tabs >}}

The `odatix_offline` folder now contains the Odatix package and all of its dependencies (`dash`, `pandas`, `plotly`, `PyYAML`, …), as `.whl` files.

> [!TIP]
> To install a specific version rather than the latest one, pin it:
> 
> {{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m pip download odatix==4.0.0 -d odatix_offline
{{< /code >}}

### Downloading for a different platform

If the online machine does not run the same OS or Python version as the offline one, tell `pip` what to target. This requires downloading prebuilt wheels only, so that nothing is built for the wrong platform:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m pip download odatix -d odatix_offline \
    --only-binary=:all: \
    --python-version 3.11 \
    --platform manylinux2014_x86_64
{{< /code >}}

Common values for `--platform`:

| Target machine | `--platform` value |
| --- | --- |
| Linux x86-64 | `manylinux2014_x86_64` |
| Linux ARM64 | `manylinux2014_aarch64` |
| macOS (Apple Silicon) | `macosx_11_0_arm64` |
| macOS (Intel) | `macosx_10_9_x86_64` |
| Windows x86-64 | `win_amd64` |

> [!WARNING]
> `--only-binary=:all:` makes `pip` fail if one of the dependencies is not available as a wheel for the requested target. In that case, download the packages from a machine matching the offline one.


## Step 2: Transfer the packages

Copy the whole `odatix_offline` folder to the offline machine, using any medium you have available:

{{< code lang=bash filename="Terminal" prompt="true" >}}
# For instance, over an internal network
$ scp -r odatix_offline user@offline-machine:/home/user/
{{< /code >}}


## Step 3: Configure a [virtual environment](https://docs.python.org/3/library/venv.html) *(optional)*

The remaining steps take place **on the offline machine**.

If you want to use Odatix inside a virtual environment (recommended), run:

{{< tabs >}}

{{% tab name="Ubuntu/Debian" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m venv odatix_venv
$ source odatix_venv/bin/activate
{{< /code >}}
{{% /tab %}}

{{% tab name="Fedora/AlmaLinux/RHEL" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m venv odatix_venv
$ source odatix_venv/bin/activate
{{< /code >}}
{{% /tab %}}

{{% tab name="ArchLinux" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m venv odatix_venv
$ source odatix_venv/bin/activate
{{< /code >}}
{{% /tab %}}

{{% tab name="macOS" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m venv odatix_venv
$ source odatix_venv/bin/activate
{{< /code >}}
{{% /tab %}}

{{% tab name="Windows" %}}
{{< code lang=bash filename="Terminal Powershell" prompt="true" >}}
$ python -m venv odatix_venv
$ Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$ .\odatix_venv\Scripts\Activate.ps1
{{< /code >}}
{{% /tab %}}

{{< /tabs >}}

Creating a virtual environment does not require an internet connection: `pip` is bootstrapped from the copy bundled with Python itself.

> [!NOTE]
> You have to activate the virtual environment at every new shell session.  
> Consider creating an alias.


## Step 4: Install Odatix

Install from the transferred folder, and tell `pip` not to contact PyPI:

{{< tabs >}}

{{% tab name="Ubuntu/Debian" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m pip install --no-index --find-links=odatix_offline odatix
{{< /code >}}
{{% /tab %}}

{{% tab name="Fedora/AlmaLinux/RHEL" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m pip install --no-index --find-links=odatix_offline odatix
{{< /code >}}
{{% /tab %}}

{{% tab name="ArchLinux" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m pip install --no-index --find-links=odatix_offline odatix
{{< /code >}}
{{% /tab %}}

{{% tab name="macOS" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m pip install --no-index --find-links=odatix_offline odatix
{{< /code >}}
{{% /tab %}}

{{% tab name="Windows" %}}
{{< code lang=bash filename="Terminal Powershell" prompt="true" >}}
$ python -m pip install --no-index --find-links=odatix_offline odatix
{{< /code >}}
{{% /tab %}}

{{< /tabs >}}

- `--no-index` disables the PyPI index, so the installation never tries to reach the network.
- `--find-links` points `pip` at the folder holding the downloaded packages.

Check that the installation succeeded:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix --version
{{< /code >}}


## Step 5: Enable option autocompletion *(optional)*

To enable autocompletion of Odatix command options:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ eval "$(register-python-argcomplete odatix)"
$ eval "$(register-python-argcomplete odatix-gui)"
$ eval "$(register-python-argcomplete odatix-explorer)"
{{< /code >}}

> [!NOTE]
> You have to run these commands at every new shell session.  
> Consider adding them to `odatix_venv/bin/activate` (if using a virtual environment) or your `.bashrc` / `.zshrc`.


## Step 6: Install a supported EDA tool

More information is available in the [EDA tools installation section](/install/eda_tools).


## Updating an offline installation

Repeat [step 1](#step-1-download-odatix-on-the-online-machine) and [step 2](#step-2-transfer-the-packages) with the newer version, then, on the offline machine:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m pip install --no-index --find-links=odatix_offline --upgrade odatix
{{< /code >}}


## Troubleshooting

> [!ERROR] `ERROR: Could not find a version that satisfies the requirement ...` 

One of the dependencies is missing from the folder, or its wheel does not match the offline machine. Check that the Python version and the platform of both machines match, and download again with the appropriate `--python-version` and `--platform` options.

> [!ERROR] `ERROR: Network is unreachable`, or the installation hangs

`pip` is still trying to reach PyPI. Make sure `--no-index` is present, and that no local `pip.conf` / `pip.ini` defines an unreachable `index-url` or `extra-index-url`.

> [!ERROR] A package is built from source and the build fails  

Add `--only-binary=:all:` when downloading, so that only prebuilt wheels are collected.
