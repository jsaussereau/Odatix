##########################
Define Parameter Domains
##########################

In Odatix, a **parameter domain** defines a set of parameters for a given hardware architecture. 
The goal is to streamline the implementation of parameter combinations. This way, users do not have to manually create a configuration file for each parameter combination.
This is particularly useful when dealing with a large set of parameters.

.. note::

  This functionality requires Odatix 3.4+

.. Important::

Before defining a parameter domain, make sure you have already defined your architecture folder in ``odatix_userconfig/architectures``.

**************
File Structure
**************

To define parameter domains, users must create dedicated sub-folders for each parameter domain inside their architecture directory in ``odatix_userconfig/architectures/``.
Each sub folder must contain a parameter domain definition file ``_settings.yml`` and parameter files. This is similar to how the main paramater domain work (see :doc:`/quick_start/add_design`)

Example of file structure:

.. code-block:: yaml

  odatix_userconfig/architectures/AsteRISC/
  ├── Baseline
  │   ├── _settings.yml             # 'Baseline' parameter domain settings
  │   ├── E.txt                     # 'Baseline' parameter domain architecture configuration
  │   └── I.txt                     # 'Baseline' parameter domain architecture configuration
  ├── DMEM
  │   ├── _settings.yml             # 'DMEM' parameter domain settings
  │   ├── 256.txt                   # 'DMEM' parameter domain architecture configuration
  │   ├── 512.txt                   # 'DMEM' parameter domain architecture configuration
  │   ├── 1024.txt                  # 'DMEM' parameter domain architecture configuration
  │   ├── 2048.txt                  # 'DMEM' parameter domain architecture configuration
  │   └── 4096.txt                  # 'DMEM' parameter domain architecture configuration
  ├── IMEM
  │   ├── _settings.yml             # 'IMEM' parameter domain settings       
  │   ├── 256.txt                   # 'IMEM' parameter domain architecture configuration
  │   ├── 512.txt                   # 'IMEM' parameter domain architecture configuration
  │   ├── 1024.txt                  # 'IMEM' parameter domain architecture configuration
  │   ├── 2048.txt                  # 'IMEM' parameter domain architecture configuration
  │   └── 4096.txt                  # 'IMEM' parameter domain architecture configuration
  ├── Mul
  │   ├── _settings.yml             # 'Mul' parameter domain settings
  │   ├── Basic.txt                 # 'Mul' parameter domain architecture configuration
  │   ├── Fast.txt                  # 'Mul' parameter domain architecture configuration
  │   ├── Off.txt                   # 'Mul' parameter domain architecture configuration
  │   └── Single_cycle.txt          # 'Mul' parameter domain architecture configuration
  ├── _settings.yml                 # Main architecture settings
  ├── M0000.txt                     # Main architecture configuration
  ├── M0001.txt                     # Main architecture configuration
  ├── M0008.txt                     # Main architecture configuration
  ├── M0016.txt                     # Main architecture configuration
  ├── M0024.txt                     # Main architecture configuration
  ├── ...
  └── M0111.txt                     # Main architecture configuration

Each subfolder corresponds to a different **parameter domain** (e.g., ``DMEM``, ``IMEM``, ``Mul``). 
Inside each, different values for that parameter are specified in paramter files (e.g., ``1024.txt``, ``2048.txt``) 
and a parameter domain definition file ``_settings.yml`` defines how the parameter files should be used within the rtl sources files.

***************
YAML Definition
***************

Users must also provide a YAML file that specifies the configuration settings. 
These files contain parameters that control architecture variations, including parameter delimiters, parameter files, and target files.

A basic parameter domain settings file only contains delimiters for replacement in the top-level file. Any delimiter can be used, as long as it complies with the syntax of the HDL in use.

**Example: Verilog Module with Parameters**
   
.. code-block:: verilog
  :caption: top_level.sv
  :linenos:

  module top_level #(
    // <imem>
    parameter p_imem_depth_pw2  = 14,
    // </imem>
    // <dmem>
    parameter p_dmem_depth_pw2  = 13,
    // </dmem>

    // <baseline>
    parameter p_ext_rve         = 0,
    // </baseline>
    
    // <mul>
    parameter p_ext_rvm         = 0,
    parameter p_mul_fast        = 0,
    parameter p_mul_1_cycle     = 0,
    // </mul>

    // <main>
    //...
    // </main>
  ) (

**Example: YAML settings file for a parameter domain**

.. code-block:: yaml
  :caption: baseline/_settings.yml
  :linenos:

  start_delimiter: "  // <baseline>"
  stop_delimiter: "  // </baseline>"

If parameter replacements are needed in a different file from the top-level module, specify it with `param_target_file`:

.. code-block:: yaml
  :caption: other_domain/_settings.yml
  :linenos:

  start_delimiter: "// start"
  stop_delimiter: "// end"
  param_target_file: "top.v"

#### **Dynamic Configuration Generation**
Parameter domains can also **dynamically generate configurations**.  

For example, `DMEM` can generate multiple configurations for different memory sizes:

.. code-block:: yaml
  :caption: DMEM/_settings.yml
  :linenos:

  start_delimiter: "  // <dmem>"
  stop_delimiter: "  // </dmem>"

  generate_configurations: Yes
  generate_configurations_settings:
    template: "\n  parameter p_dmem_depth_pw2  = $mem_depth,\n"
    name: "${mem_depth_pw2}"
    variables:
      mem_depth:
        type: range
        settings:
          from: 8
          to: 12
      mem_depth_pw2:
        type: function
        settings:
          op: 2^$mem_depth

This generates multiple parameter values dynamically, allowing **automated exploration** of different memory configurations.

************************************
Run jobs with your parameter domains
************************************

Once the parameter domains are defined, specify different **architecture configurations** in the YAML configuration file.
Parameter domains are separated by a `+`. 

Example YAML file:

.. code-block:: yaml
  :caption: odatix_userconfig/fmax_synthesis_settings.yml
  :linenos:
   
  architectures: 
    - AsteRISC/M0000 + DMEM/1024 + IMEM/1024 + Baseline/I + Mul/Off
    - AsteRISC/M0001 + DMEM/1024 + IMEM/1024 + Baseline/I + Mul/Off
    - AsteRISC/M0008 + DMEM/1024 + IMEM/1024 + Baseline/I + Mul/Off
    - AsteRISC/M0016 + DMEM/1024 + IMEM/1024 + Baseline/I + Mul/Off
    - AsteRISC/M0024 + DMEM/1024 + IMEM/1024 + Baseline/I + Mul/Off

    - AsteRISC/M0000 + DMEM/1024 + IMEM/1024 + Baseline/I + Mul/Fast
    - AsteRISC/M0001 + DMEM/1024 + IMEM/1024 + Baseline/I + Mul/Fast
    - AsteRISC/M0008 + DMEM/1024 + IMEM/1024 + Baseline/I + Mul/Fast
    - AsteRISC/M0024 + DMEM/1024 + IMEM/1024 + Baseline/I + Mul/Fast

Each line describes a **design variant**, where different **parameter domains** are combined dynamically.

.. Tip:: 

  Parameter domains can be used for **any type of job**, including:
  
  - Fmax synthesis
  - Custom frequency synthesis
  - Simulations

---

**See Also**

- :doc:`/userguide/configuration_generation`

- :doc:`/quick_start/add_design`

- :doc:`/quick_start/fmax_synthesis`

- :doc:`/quick_start/custom_freq_synthesis`

- :doc:`/quick_start/simulations`
