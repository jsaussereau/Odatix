************
Installation
************

Install Asterism
================

Step 1: Clone the repository
----------------------------

.. tabs::

   .. group-tab:: Ubuntu/Debian

      .. code-block:: console

         sudo apt update
         sudo apt install -y git
         git clone https://github.com/jsaussereau/Asterism.git
         cd Asterism/

   .. group-tab:: Fedora/CentOS/AlmaLinux

      .. code-block:: console

         sudo dnf update
         sudo dnf install -y git
         git clone https://github.com/jsaussereau/Asterism.git
         cd Asterism/

   .. group-tab:: Arch Linux

      .. code-block:: console

         sudo pacman -Syu
         sudo pacman -S git --noconfirm
         git clone https://github.com/jsaussereau/Asterism.git
         cd Asterism/


Step 2: Install Python 3.6+ and make
------------------------------------

.. tabs::

   .. group-tab:: Ubuntu/Debian

      .. code-block:: console

         sudo apt install -y python3 make

   .. group-tab:: Fedora/CentOS/AlmaLinux

      .. code-block:: console

         sudo dnf install -y python3 make

   .. group-tab:: Arch Linux

      .. code-block:: console

         sudo pacman -S python3 make --noconfirm

Step 3: Install Python requirements
-----------------------------------

Option #1: Using pipx (recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. tabs::

   .. group-tab:: Ubuntu/Debian

      .. code-block:: console

         sudo apt install -y pipx
         make pipx_install
         pipx ensurepath

   .. group-tab:: Fedora/CentOS/AlmaLinux

      .. code-block:: console

         sudo dnf install -y pipx
         make pipx_install
         pipx ensurepath

   .. group-tab:: Arch Linux

      .. code-block:: console
         
         sudo pacman -S python-pipx --noconfirm
         make pipx_install
         pipx ensurepath

.. warning::
   If the directory where pipx stores apps was not already in your PATH environment variable, you have to start a new shell session before running Asterism

Option #2: Using pip
~~~~~~~~~~~~~~~~~~~~

.. tabs::

   .. group-tab:: Ubuntu/Debian

      .. code-block:: console

         sudo apt install python3-pip
         pip3 install -r requirements.txt

   .. group-tab:: Fedora/CentOS/AlmaLinux

      .. code-block:: console

         sudo dnf install python3-pip
         pip3 install -r requirements.txt

   .. group-tab:: Arch Linux

      .. code-block:: console

         sudo pacman -Sy python-pip
         pip3 install -r requirements.txt

.. Option #3: Using system package manager
.. ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. .. tabs::

..    .. group-tab:: Ubuntu/Debian

..       Unsupported

..    .. group-tab:: Fedora/CentOS/AlmaLinux
      
..       Unsupported

..    .. group-tab:: Arch Linux

..       .. code-block:: console

..          sudo pacman -Sy - < requirements-archlinux.txt

..       .. warning::

..          Includes packages from the AUR

Step 4: Install one of the supported EDA tools
----------------------------------------------

Make sure your EDA tool is added to your PATH environment variable

.. code-block:: console

   PATH=$PATH:<eda_tool_installation_path>

Replace ``<eda_tool_installation_path>`` with your own installation path. 

Example of adding Vivado to the PATH environment variable (your installation path may be different):

.. code-block:: console

   PATH=$PATH:/opt/xilinx/2022/Vivado/2022.2/bin
