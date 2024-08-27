**************************************
Install one of the supported EDA tools
**************************************

Install OpenLane
----------------

OpenLane is a free and open-source automated RTL to GDSII flow based on several components including OpenROAD, Yosys, Magic, and Netgen. 


.. card:: OpenLane installation guide
   :margin: auto
   :width: 50%
   :link: https://openlane.readthedocs.io/en/latest/getting_started/installation/index.html
   :text-align: center
        
Install Vivado
--------------

Vivado is a software suite dedicated to AMD (Xilinx) SoCs and FPGAs. Vivado ML Standard Edition (formerly WebPack Edition) has no-cost for smaller devices.

.. card:: AMD unified installer download page
   :margin: auto
   :width: 50%
   :link: https://www.xilinx.com/support/download.html
   :text-align: center
      
Make sure your EDA tool is added to your PATH environment variable
------------------------------------------------------------------

.. code-block:: bash

   PATH=$PATH:<eda_tool_installation_path>

Replace ``<eda_tool_installation_path>`` with your own installation path. 

Example of adding Vivado to the PATH environment variable (your installation path may be different):

.. code-block:: bash

   PATH=$PATH:/opt/xilinx/Vivado/2022.2/bin
