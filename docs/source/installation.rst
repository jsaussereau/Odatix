Installation
============

Step 1: Clone the repository
----------------------------

.. tabs::

   .. group-tab:: Ubuntu/Debian

      .. code-block:: console

         sudo apt update
         sudo apt install git

   .. group-tab:: Fedora/CentOS/AlmaLinux

      .. code-block:: console

         sudo dnf update
         sudo dnf install git

   .. group-tab:: Arch Linux

      .. code-block:: console

         sudo pacman -Sy git

.. code-block:: console

   git clone https://github.com/jsaussereau/Asterism.git
   cd Asterism/


Step 2: Install Python 3.6+ and make
------------------------------------

.. tabs::

   .. group-tab:: Ubuntu/Debian

      .. code-block:: console

         sudo apt install python3 make

   .. group-tab:: Fedora/CentOS/AlmaLinux

      .. code-block:: console

         sudo dnf install python3 make

   .. group-tab:: Arch Linux

      .. code-block:: console

         sudo pacman -Sy python3 make

Step 3: Install Python requirements
-----------------------------------

Option #1: Using pipx (recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. tabs::

   .. group-tab:: Ubuntu/Debian

      .. code-block:: console

         sudo apt install pipx
         make pipx_install

   .. group-tab:: Fedora/CentOS/AlmaLinux

      .. code-block:: console

         sudo dnf install pipx
         make pipx_install

   .. group-tab:: Arch Linux

      .. code-block:: console
         
         sudo pacman -Sy python-pipx
         make pipx_install

Option #2: Using pip
~~~~~~~~~~~~~~~~~~~~

.. tabs::

   .. group-tab:: Ubuntu/Debian

      .. code-block:: console

         sudo apt install python3-pip
         pip install -r requirements.txt

   .. group-tab:: Fedora/CentOS/AlmaLinux

      .. code-block:: console

         sudo dnf install python3-pip
         pip install -r requirements.txt

   .. group-tab:: Arch Linux

      .. code-block:: console

         sudo pacman -Sy python-pip
         pip install -r requirements.txt

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
