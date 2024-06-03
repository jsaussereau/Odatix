Installation
============

Step 1: Clone the repository
----------------------------

.. code-block:: console

   git clone https://github.com/jsaussereau/Asterism.git
   cd Asterism/


Step 2: Install Python 3.6+ and make
------------------------------------

.. tabs::

   .. group-tab:: Ubuntu/Debian

      .. code-block:: console

         sudo apt update
         sudo apt install python3 python3-pip make

   .. group-tab:: Fedora/CentOS/AlmaLinux

      .. code-block:: console

         sudo dnf update
         sudo dnf install python3 python3-pip make

   .. group-tab:: Arch Linux

      .. code-block:: console

         sudo pacman -Sy python3 make

Step 3: Install Python requirements listed in requirements.txt
--------------------------------------------------------------

.. tabs::

   .. group-tab:: Ubuntu/Debian

      .. code-block:: console

        pip install -r requirements.txt

   .. group-tab:: Fedora/CentOS/AlmaLinux

      .. code-block:: console

        pip install -r requirements.txt

   .. group-tab:: Arch Linux

      .. code-block:: console

        sudo pacman -Sy - < requirements-archlinux.txt

Step 4: Install one of the supported EDA tools
----------------------------------------------

Make sure your EDA tool is added to your PATH environment variable

.. code-block:: console

   PATH=$PATH:<eda_tool_installation_path>

Replace ``<eda_tool_installation_path>`` with your own installation path. 

Example of adding Vivado to the PATH environment variable (your installation path may be different):

.. code-block:: console

   PATH=$PATH:/opt/xilinx/2022/Vivado/2022.2/bin
