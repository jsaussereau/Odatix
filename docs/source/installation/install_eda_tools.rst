**************************************
Install one of the supported EDA tools
**************************************

Synthesis
=========

Install OpenLane
----------------

OpenLane is a free and open-source automated RTL to GDSII flow based on several components including OpenROAD, Yosys, Magic, and Netgen. 


.. card:: OpenLane installation guide
   :margin: auto
   :width: 50%
   :link: https://openlane.readthedocs.io/en/latest/getting_started/installation/index.html
   :text-align: center

.. Warning::
   Once installed, the installation path must be updated in the user target file for OpenLane.
   Update ``tool_install_path`` inside ``odatix_userconfig/target_openlane.yml`` after having initialized your directory.
   
   More information about Initialization in the :doc:`/quick_start/index` section.

Install Vivado
--------------

Vivado is a software suite dedicated to AMD (Xilinx) SoCs and FPGAs. Vivado ML Standard Edition (formerly WebPack Edition) has no-cost for smaller devices.

.. card:: AMD unified installer download page
   :margin: auto
   :width: 50%
   :link: https://www.xilinx.com/support/download.html
   :text-align: center

.. Warning::
   Make sure your EDA tool is added to your PATH environment variable

   .. tab:: Unix

      .. code-block:: bash

         PATH=$PATH:<eda_tool_installation_path>

   .. tab:: Windows

      .. code-block:: powershell

         $env:PATH += "<eda_tool_installation_path>"

   Replace ``<eda_tool_installation_path>`` with your own installation path. 

   Example of adding Vivado to the PATH environment variable (your installation path may be different):

   .. tab:: Unix

      .. code-block:: bash

         PATH=$PATH:/opt/xilinx/Vivado/2024.1/bin

   .. tab:: Windows

      .. code-block:: powershell

         $env:PATH += ";C:\Xilinx\Vivado\2024.2\bin"

      
Simulations
===========

It is possible to use any simulator with Odatix. However, in the examples provided, the simulators used are Verilator and GHDL.

Install Verilator
-----------------

Verilator is a free and open-source simulator for Verilog/SystemVerilog.

.. tab:: Ubuntu/Debian

   .. code-block:: bash

      sudo apt update
      sudo apt install -y verilator

.. tab:: Fedora/CentOS/AlmaLinux

   .. code-block:: bash

      sudo dnf update
      sudo dnf install -y verilator

.. tab:: Arch Linux

   .. code-block:: bash

      sudo pacman -Syu
      sudo pacman -S verilator --noconfirm

Install GHDL
------------

GHDL is a free and open-source simulator for VHDL.

.. tab:: Ubuntu/Debian

   .. code-block:: bash

      sudo apt update
      sudo apt install -y ghdl

.. tab:: Fedora/CentOS/AlmaLinux

   .. code-block:: bash

      sudo dnf update
      sudo dnf install -y ghdl

.. tab:: Arch Linux

   Install the `ghdl-gcc <https://aur.archlinux.org/packages/ghdl-gcc>`_ package from the `AUR <https://wiki.archlinux.org/title/Arch_User_Repository>`_ 

