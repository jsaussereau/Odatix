************************
Install Odatix from PyPi
************************

Step 1: Install Python 3.6+ and make
------------------------------------

.. tab:: Ubuntu/Debian

   .. code-block:: bash

      sudo apt update
      sudo apt install -y python3 make

.. tab:: Fedora/CentOS/AlmaLinux

   .. code-block:: bash

      sudo dnf update
      sudo dnf install -y python3 make

.. tab:: Arch Linux

   .. code-block:: bash

      sudo pacman -Syu
      sudo pacman -S python3 make --noconfirm

Step 2: Configure a virtual environment [*Optional*]
----------------------------------------------------

.. code-block:: bash

   # Create a virtual environment
   python3 -m venv odatix_venv
   # Activate the virtual environment
   source odatix_venv/bin/activate # You have to run this command at every new shell session

Step 3: Install the package
----------------------------

.. code-block:: bash

   python3 -m pip install odatix

Step 4: Install one of the supported EDA tools
----------------------------------------------

More information in section :doc:`/installation/install_eda_tools`.