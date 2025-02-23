###############################################
Generate Parameter Configurations
###############################################

Odatix offers a **highly modular** approach to **automated configuration generation**.  
This system allows users to define **dynamic parameter sets** without manually listing all possible values.  
With a simple YAML-based configuration, Odatix can generate **customized parameter combinations** using a variety of flexible methods.

.. note::

  This functionality requires Odatix 3.4+

**********************************
Configuration Generation Syntax
**********************************

To activate automatic configuration generation, users must define the following fields 
in their main architecture definition file or parameter domain definition file ``_settings.yml``:

.. code-block:: yaml
  :caption: _settings.yml
  :linenos:

  generate_configurations: Yes
  generate_configurations_settings:
    template: "parameter VALUE = $var;"
    name: "config_${var}"
    variables:
      # One or more of the variable definition methods described below

- **generate_configurations: Yes** → Activates the automatic configuration generation.
- **template:** → Defines how generated values will be inserted in the configuration files.
- **name:** → Defines the naming convention for generated configurations.
- **variables:** → Defines how values are generated (ranges, lists, functions, etc.).

For more information about paramter domains see Section :doc:`/userguide/parameter_domains`

***********************************
Variable Definition Methods
***********************************

Odatix supports multiple methods to **dynamically generate values** for configuration parameters.

1️⃣ **Range-based Values**
--------------------------------

Users can define a **range of values** for a parameter with an optional step size.

.. code-block:: yaml
  :caption: _settings.yml
  :linenos:

  generate_configurations: Yes
  generate_configurations_settings:
    template: "parameter VALUE = $var;"
    name: "config_${var}"
    variables:
      var:
        type: range
        settings:
          from: 10
          to: 100
          step: 10

🔹 **var** will generate as `{10, 20, 30, ..., 100}`.

---

2️⃣ **Power-of-Two Values**
--------------------------------

A **power-of-two** range can be defined.

.. code-block:: yaml
  :caption: _settings.yml
  :linenos:

  generate_configurations: Yes
  generate_configurations_settings:
    template: "parameter VALUE = $var;"
    name: "config_${var}"
    variables:
      var:
        type: power_of_two
        settings:
          from_2^: 5
          to_2^: 10

🔹 **var** will generate as `{2^5, 2^6, 2^7, 2^8, 2^9, 2^10}` → `{32, 64, 128, 256, 512, 1024}`.

Alternatively, you can define a range directly:

.. code-block:: yaml
  :caption: _settings.yml
  :linenos:

  generate_configurations: Yes
  generate_configurations_settings:
    template: "parameter VALUE = $var;"
    name: "config_${var}"
    variables:
      var:
        type: power_of_two
        settings:
          from: 32
          to: 1024

🔹 **var** will generate as `{32, 64, 128, 256, 512, 1024}`.

---

3️⃣ **Explicit List of Values**
--------------------------------

If a **fixed set of values** is needed, users can define a list.

.. code-block:: yaml
  :caption: _settings.yml
  :linenos:

  generate_configurations: Yes
  generate_configurations_settings:
    template: "parameter VALUE = $var;"
    name: "config_${var}"
    variables:
      var:
        type: list
        settings:
          list: [100, 225, 412, 803]

🔹 **var** will generate as `{100, 200, 400, 800}`.

.. 🔹 This will generate configurations `{config_100, config_200, config_400, config_800}`.

---

4️⃣ **Multiples of a Base Value**
----------------------------------

Users can define values that are **multiples of a specific number**.

.. code-block:: yaml
  :caption: _settings.yml
  :linenos:

  generate_configurations: Yes
  generate_configurations_settings:
    template: "parameter VALUE = $var;"
    name: "config_${var}"
    variables:
      var:
        type: multiples
        settings:
          base: 8
          from: 8
          to: 64

🔹 **var** will generate as `{8, 16, 24, ..., 64}`.

---

5️⃣ **Computed Values (Function-based)**
----------------------------------------

Odatix allows the use of **mathematical expressions** to compute values dynamically.

.. code-block:: yaml
  :caption: _settings.yml
  :linenos:

  generate_configurations: Yes
  generate_configurations_settings:
    template: "parameter VALUE_START = $var;\n parameter VALUE_END = ${var_func};"
    name: "config_${var}..${var_func}"
    variables:
      var:
        type: multiples
        settings:
          from: 0
          to: 56
          base: 8
      var_func:
        type: function
        settings:
          op: ${var}+7

🔹 **var** will generate as `{0, 8, 16, 24, ..., 56}`.

🔹 **var_func** will be computed as `{7, 15, 23, 31, ..., 63}`.

🔹 This will generate configurations `{config_0..7, config_8..15, config_16..23, config_24..31, ..., config_56..63}`.


***********************************
Operations Between Variables
***********************************

1️⃣ **Union of Variable Sets**
-------------------------------

Users can dynamically **concatenate multiple generated variables**.

.. code-block:: yaml
  :caption: _settings.yml
  :linenos:

  generate_configurations: Yes
  generate_configurations_settings:
    template: "parameter VALUE = ${union_var};"
    name: "config_${union_var}"
    variables:
      var_1:
        type: list
        settings:
          list: [50, 60]
      var_2:
        type: list
        settings:
          list: [10, 100]
      union_var:
        type: union
        settings:
          sources: [var_1, var_2]

🔹 **var** will generate as `{10, 50, 60, 100}`.

🔹 This will generate configurations `{config_10, config_50, config_60, config_100}`.

---

2️⃣ **Disjonctive Union of Variable Sets**
-------------------------------------------

It is also possible to perform a symmetric difference (disjunctive union) of two variable. 
This consists in concatenating the elements which are in either of the sets, but not in both.

.. code-block:: yaml
  :caption: _settings.yml
  :linenos:

  generate_configurations: Yes
  generate_configurations_settings:
    template: "parameter VALUE = ${union_var};"
    name: "config_${union_var}"
    variables:
      var_1:
        type: list
        settings:
          list: [50, 60]
      var_2:
        type: list
        settings:
          list: [10, 50, 100]
      union_var:
        type: disjunctive_union
        settings:
          sources: [var_1, var_2]

🔹 **var** will generate as `{10, 60, 100}`. Note that `50` is missing because it is defined in both var_1 and var_2.

🔹 This will generate configurations `{config_10, config_60, config_100}`.

---

3️⃣ **Intersection of Variable Sets**
--------------------------------------

Users can dynamically get exclusiveley the values that are in all given variables.

.. code-block:: yaml
  :caption: _settings.yml
  :linenos:

  generate_configurations: Yes
  generate_configurations_settings:
    template: "parameter VALUE = ${inter_var};"
    name: "config_${inter_var}"
    variables:
      mult_3:
        type: multiples
        settings:
          base: 3
          from: 1
          to: 50
      mult_4:
        type: multiples
        settings:
          base: 4
          from: 1
          to: 50
      inter_var:
        type: intersection
        settings:
          sources: [mult_3, mult_4]

🔹 **mult_3** will generate as the list of all multiples of 3 in [1:50]: 
{3, 6, 9, **12**, 15, 18, 21, **24**, 27, 30, 33, **36**, 39, 42, 45, **48**}.

🔹 **mult_4** will generate as the list of all multiples of 4 in [1:50]: 
{4, 8, **12**, 16, 20, **24**, 28, 32, **36**, 40, 44, **48**}.

🔹 **inter_var** will generate as the list of all multiples of both 3 and 4 in [1:50]: 
{12, 24, 36, 48}.

🔹 This will generate configurations `{config_12, config_24, config_36, config_48}`.

---

4️⃣ **Difference of Variable Sets**
--------------------------------------

Users can dynamically get exclusiveley the values that are in all given variables.

.. code-block:: yaml
  :caption: _settings.yml
  :linenos:

  generate_configurations: Yes
  generate_configurations_settings:
    template: "parameter VALUE = ${diff_var};"
    name: "config_${diff_var}"
    variables:
      mult_3:
        type: multiples
        settings:
          base: 3
          from: 1
          to: 50
      mult_4:
        type: multiples
        settings:
          base: 4
          from: 1
          to: 50
      diff_var:
        type: difference
        settings:
          sources: [mult_4, mult_3]

🔹 **mult_3** will generate as the list of all multiples of 3 in [1:50]: 
{3, 6, 9, **12**, 15, 18, 21, **24**, 27, 30, 33, **36**, 39, 42, 45, **48**}.

🔹 **mult_4** will generate as the list of all multiples of 4 in [1:50]: 
{4, 8, **12**, 16, 20, **24**, 28, 32, **36**, 40, 44, **48**}.

🔹 **diff_var** will generate as the list of all multiples of 4 in [1:50] that are not a multiple of 3: 
{4, 8, 16, 20, 28, 32, 40, 44}.


***********************************
Combining Multiple Parameters
***********************************

Odatix allows multiple parameters to be generated **together**, enabling **complex configurations**.

**Example: Dual Memory Depth Configuration**

In this example, both instruction memory (`IMEM`) and data memory (`DMEM`) depths are generated dynamically.

.. code-block:: yaml
  :caption: _settings.yml
  :linenos:

  start_delimiter: "  // <mem>"
  stop_delimiter: "  // </mem>"

  generate_configurations: Yes
  generate_configurations_settings:
    template: "\n  parameter p_dmem_depth_pw2  = $dmem_depth,\n  parameter p_imem_depth_pw2  = $imem_depth,\n"
    name: "DMEM_${dmem_depth_pw2}-IMEM_${imem_depth_pw2}"
    variables:
      dmem_depth:
        type: range
        settings:
          from: 8
          to: 10
      dmem_depth_pw2:
        type: function
        settings:
          op: 2^$dmem_depth
      imem_depth:
        type: range
        settings:
          from: 8
          to: 10
      imem_depth_pw2:
        type: function
        settings:
          op: 2^$imem_depth

🔹 This generates configurations such as:

- `DMEM_256-IMEM_256`
- `DMEM_256-IMEM_512`
- `DMEM_512-IMEM_512`
- `DMEM_1024-IMEM_2048`
- etc.

Each configuration automatically computes both `p_dmem_depth_pw2` and `p_imem_depth_pw2` using the power-of-two function.

---

**See Also**

- :doc:`/userguide/parameter_domains`
