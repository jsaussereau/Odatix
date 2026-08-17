---
weight: 1
title: "Install Odatix from PyPi"
date: 2026-05-15
author: "Jonathan Saussereau"
description: "Recommended installation method for Odatix using the Python package manager (pip)."
categories: ["Tutorial", "Installation"]
tags: ["install", "pypi"]
# featured_image: "/images/blog/modules.svg"
next_tutorials:
  - /install/eda_tools/
  - /tutorials/run_examples
---

{{< toc >}}


> [!WARNING]
> Odatix provides partial support for Windows. For a better experience, it is recommended to use Linux.

## Prerequisites

- Python 3.6+
- make
- At least one supported EDA tool for synthesis workflows

### Install dependencies

{{< tabs >}}

{{% tab name="Ubuntu/Debian" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo apt update
$ sudo apt install -y python3 python3-pip python3-venv make
{{< /code >}}
{{% /tab %}}

{{% tab name="Fedora/AlmaLinux/RHEL" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo dnf update
$ sudo dnf install -y python3 make
{{< /code >}}
{{% /tab %}}

{{% tab name="ArchLinux" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo pacman -Syu
$ sudo pacman -S python3 make --noconfirm
{{< /code >}}
{{% /tab %}}

{{% tab name="macOS" %}}
- Check if Homebrew is already installed.
In a terminal, run:
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ brew --version
{{< /code >}}
- If a version is displayed, it is already installed. Otherwise, install Homebrew with the following command:
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ curl -o- https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh | bash
{{< /code >}}
- Then, in a terminal, run:
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ brew update
$ brew install python make
{{< /code >}}
{{% /tab %}}

{{% tab name="Windows" %}}
- Check if winget is already installed.
In a PowerShell terminal:

{{< code lang=bash filename="Terminal Powershell" prompt="true" >}}
$ winget --version
{{< /code >}}
- If a version is displayed, it is already installed.
Otherwise, install or update the [App Installer](https://apps.microsoft.com/detail/9nblggh4nns1) from the Microsoft Store.
- Then, in a PowerShell terminal (in administrator mode) :
{{< code lang=bash filename="Terminal Powershell" prompt="true" >}}
$ winget install -e --id Python.Python.3
$ winget install -e --id GnuWin32.Make
{{< /code >}}
{{% /tab %}}

{{< /tabs >}}

## Installation steps

### Step 1: Configure a [virtual environment](https://docs.python.org/3/library/venv.html) *(optional)*

If you want to use Odatix inside a virtual environment (recommended), run:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m venv odatix_venv
{{< /code >}}

Activate the virtual environment:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ source odatix_venv/bin/activate
{{< /code >}}

> [!NOTE]
> You have to run this command at every new shell session.  
> Consider creating an alias.


### Step 2: Install Odatix

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m pip install odatix
{{< /code >}}


## Enable autocompletion *(optional)*

To enable autocompletion of Odatix command options:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ eval "$(register-python-argcomplete odatix)"
$ eval "$(register-python-argcomplete odatix-gui)"
$ eval "$(register-python-argcomplete odatix-explorer)"
{{< /code >}}

> [!NOTE]
> You have to run these commands at every new shell session.  
> Consider adding them to `odatix_venv/bin/activate` (if using a virtual environment) or your `.bashrc` / `.zshrc`.

## Update

To get updates, run:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m pip install --upgrade odatix
{{< /code >}}
