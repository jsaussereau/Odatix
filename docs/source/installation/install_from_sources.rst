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

.. tab:: Windows

   .. caution::

      Windows is not an officially supported platform for Odatix yet. However, some functionalities may work.

   Download and install Git from the `git official website <https://git-scm.com/downloads/win>`_ or via winget:

   .. code-block:: powershell

      winget install --id Git.Git -e --source winget 

   Then, clone the repository and navigate to it:

   .. code-block:: powershell

      git clone https://github.com/jsaussereau/Odatix.git
      cd .\Odatix

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

.. tab:: Windows

   Download and install Python the `Microsoft Store <https://apps.microsoft.com/detail/9ncvdn91xzqp>`_, or from `the python official website <https://www.python.org/downloads/windows/>`_, or install it via winget:

   .. code-block:: powershell

      winget install --id Python.Python.3 -e

Step 3: Configure a `virtual environment <https://docs.python.org/3/library/venv.html>`_ [*Optional*]
------------------------------------------------------------------------------------------------------

If you want to use Odatix inside a virtual environment, run:

.. tab:: Ubuntu/Debian

   .. code-block:: bash

      # Create a virtual environment
      python3 -m venv odatix_venv # You only need to do it once

.. tab:: Fedora/CentOS/AlmaLinux

   .. code-block:: bash

      # Create a virtual environment
      python3 -m venv odatix_venv # You only need to do it once

.. tab:: Arch Linux

   .. code-block:: bash

      # Create a virtual environment
      python3 -m venv odatix_venv # You only need to do it once

.. tab:: Windows

   .. code-block:: powershell

      # Create a virtual environment
      python3 -m venv odatix_venv # You only need to do it once

To activate the virtual environment, run:

.. tab:: Ubuntu/Debian

   .. code-block:: bash

      # Activate the virtual environment
      source odatix_venv/bin/activate 

.. tab:: Fedora/CentOS/AlmaLinux

   .. code-block:: bash

      # Activate the virtual environment
      source odatix_venv/bin/activate 

.. tab:: Arch Linux

   .. code-block:: bash

      # Activate the virtual environment
      source odatix_venv/bin/activate 

.. tab:: Windows

   .. code-block:: powershell

      # Activate the virtual environment
      Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
      .\odatix_venv\Scripts\Activate.ps1

.. Note::
   
   You have to run this command at every new shell session.
   Consider creating an alias   

Step 4: Install the package
----------------------------

Depending of if you want to install Odatix in editable mode or not:

.. tab:: Install Odatix (editable mode)

   .. code-block:: bash
      
      python3 -m pip install --upgrade pip setuptools wheel
      python3 -m pip install -e ./sources --use-pep517

.. tab:: Install Odatix (without editable mode)

   .. code-block:: bash

      python3 -m pip install --upgrade pip setuptools wheel
      python3 -m pip install ./sources --use-pep517

Step 5: Enable option auto-completetion [*Optional*]
----------------------------------------------------

If you want to enable autocompletion of odatix command options, you can run:

.. code-block:: bash

   eval "$(register-python-argcomplete odatix)"
   eval "$(register-python-argcomplete odatix-explorer)"

.. Note::
   
   You have to run these commands at every new shell session.   
   Consider adding these to your ``odatix_venv/bin/activate`` (if using a virtual environment) script or your ``.bashrc`` / ``.zshrc``

Step 6: Install one of the supported EDA tools
----------------------------------------------

More information in section :doc:`/installation/install_eda_tools`.
