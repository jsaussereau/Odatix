***************************
Install Odatix from sources
***************************

Step 1: Clone the repository
----------------------------


.. tab:: Ubuntu/Debian

   .. code-block:: bash

      sudo apt update
      sudo apt install -y git
      git clone https://github.com/jsaussereau/Odatix.git
      cd Odatix/

.. tab:: Fedora/CentOS/AlmaLinux

   .. code-block:: bash

      sudo dnf update
      sudo dnf install -y git
      git clone https://github.com/jsaussereau/Odatix.git
      cd Odatix/

.. tab:: Arch Linux

   .. code-block:: bash

      sudo pacman -Syu
      sudo pacman -S git --noconfirm
      git clone https://github.com/jsaussereau/Odatix.git
      cd Odatix/


Step 2: Install Python 3.6+ and make
------------------------------------

.. tab:: Ubuntu/Debian

   .. code-block:: bash

      sudo apt update
      sudo apt install -y python3 python3-pip python3-venv make

.. tab:: Fedora/CentOS/AlmaLinux

   .. code-block:: bash

      sudo dnf update
      sudo dnf install -y python3 make

.. tab:: Arch Linux

   .. code-block:: bash

      sudo pacman -Syu
      sudo pacman -S python3 make --noconfirm

Step 3: Configure a virtual environment [*Optional*]
----------------------------------------------------

.. code-block:: bash

   # Create a virtual environment
   python3 -m venv odatix_venv
   # Activate the virtual environment
   source odatix_venv/bin/activate # You have to run this command at every new shell session

   
Step 4: Install the package
----------------------------

Depending of if you want to install Odatix in editable mode or not:

.. tab:: Install Odatix (editable mode)

   .. code-block:: bash
      
      python3 -m pip install --upgrade pip setuptools wheel
      python3 -m pip install -e ./sources

.. tab:: Install Odatix (without editable mode)

   .. code-block:: bash

      python3 -m pip install --upgrade pip setuptools wheel
      python3 -m pip install ./sources

Step 5: Install one of the supported EDA tools
----------------------------------------------

More information in section :doc:`/installation/install_eda_tools`.
