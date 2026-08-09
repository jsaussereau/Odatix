---
title: "Install Odatix from sources"
date: 2026-05-15
author: "Jonathan Saussereau"
description: "Installation method for Odatix from sources, allowing for more customization and control over the execution."
categories: ["Tutorial", "Installation"]
tags: ["install", "sources"]
# featured_image: "/images/blog/modules.svg"
---

{{< toc >}}


> [!WARNING]
> Odatix provides partial support for Windows. For a better experience, it is recommended to use Linux.

## Prerequisites

- Python 3.6+
- git
- make
- At least one supported EDA tool for synthesis workflows

### Install dependencies

{{< tabs >}}

{{% tab name="Ubuntu/Debian" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo apt update
$ sudo apt install -y python3 python3-pip python3-venv make git
{{< /code >}}
{{% /tab %}}

{{% tab name="Fedora/AlmaLinux/RHEL" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo dnf update
$ sudo dnf install -y python3 make git
{{< /code >}}
{{% /tab %}}

{{% tab name="ArchLinux" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ sudo pacman -Syu
$ sudo pacman -S python3 make --noconfirm
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
$ winget install -e --id Git.Git
{{< /code >}}
{{% /tab %}}

{{< /tabs >}}

## Step 1: Clone the Odatix repository


{{< tabs >}}

{{% tab name="Ubuntu/Debian" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ git clone https://github.com/jsaussereau/Odatix.git
$ cd Odatix/
{{< /code >}}
{{% /tab %}}

{{% tab name="Fedora/AlmaLinux/RHEL" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ git clone https://github.com/jsaussereau/Odatix.git
$ cd Odatix/
{{< /code >}}
{{% /tab %}}

{{% tab name="ArchLinux" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ git clone https://github.com/jsaussereau/Odatix.git
$ cd Odatix/
{{< /code >}}
{{% /tab %}}

{{% tab name="Windows" %}}
{{< code lang=bash filename="Terminal Powershell" prompt="true" >}}
$ git clone https://github.com/jsaussereau/Odatix.git
$ cd Odatix/
{{< /code >}}
{{% /tab %}}

{{< /tabs >}}

## Step 2: Configure a [virtual environment](https://docs.python.org/3/library/venv.html) *(optional)*

If you want to use Odatix inside a virtual environment (recommended), run:



{{< tabs >}}

{{% tab name="Ubuntu/Debian" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
# Create a virtual environment
$ python3 -m venv odatix_venv
{{< /code >}}
{{% /tab %}}

{{% tab name="Fedora/AlmaLinux/RHEL" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
# Create a virtual environment
$ python3 -m venv odatix_venv
{{< /code >}}
{{% /tab %}}

{{% tab name="ArchLinux" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
# Create a virtual environment
$ python3 -m venv odatix_venv
{{< /code >}}
{{% /tab %}}

{{% tab name="Windows" %}}
{{< code lang=bash filename="Terminal Powershell" prompt="true" >}}
# Create a virtual environment
$ python -m venv odatix_venv
{{< /code >}}
{{% /tab %}}

{{< /tabs >}}

Activate the virtual environment:


{{< tabs >}}

{{% tab name="Ubuntu/Debian" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
# Activate the virtual environment
$ source odatix_venv/bin/activate
{{< /code >}}
{{% /tab %}}

{{% tab name="Fedora/AlmaLinux/RHEL" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
# Activate the virtual environment
$ source odatix_venv/bin/activate
{{< /code >}}
{{% /tab %}}

{{% tab name="ArchLinux" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
# Activate the virtual environment
$ source odatix_venv/bin/activate
{{< /code >}}
{{% /tab %}}

{{% tab name="Windows" %}}
{{< code lang=bash filename="Terminal Powershell" prompt="true" >}}
# Activate the virtual environment
$ Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$ .\odatix_venv\Scripts\Activate.ps1
{{< /code >}}
{{% /tab %}}

{{< /tabs >}}


> [!NOTE]
> You have to run this command at every new shell session.  
> Consider creating an alias.


## Step 3: Install Odatix

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ python3 -m pip install odatix
{{< /code >}}


## Step 3: Enable option autocompletion *(optional)*

To enable autocompletion of Odatix command options:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ eval "$(register-python-argcomplete odatix)"
$ eval "$(register-python-argcomplete odatix-gui)"
$ eval "$(register-python-argcomplete odatix-explorer)"
{{< /code >}}

> [!NOTE]
> You have to run these commands at every new shell session.  
> Consider adding them to `odatix_venv/bin/activate` (if using a virtual environment) or your `.bashrc` / `.zshrc`.


## Step 4: Install a supported EDA tool

More information is available in the [EDA tools installation section](/install/eda_tools).
