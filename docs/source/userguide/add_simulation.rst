Add your own simulation
=======================

Step 1: Simulation folder
~~~~~~~~~~~~~~~~~~~~~~~~~

Create a folder named after your simulation in the ``simulations`` folder.

Step 2: Makefile
~~~~~~~~~~~~~~~~

- Add a ``Makefile`` file to your newly created folder. 
- Add a rule named ``sim`` than runs the simulation. Any simulator installed on your system can be used.

.. tip::
    Check out the examples for Verilator and GHDL Makefiles in the ``simulations`` directory.

Step 3: Optional setting file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Add a ``_settings.yml`` file to your newly created folder and fill it with one of the templates below

.. code-block:: yaml
    :caption: _setting.yml
    :linenos:

    ---
    # delimiters for parameter files
    use_parameters: "true"
    param_target_file: "tb/tb_counter.vhdl"
    start_delimiter: "generic ("
    stop_delimiter: ");"
    ...

- If you want the tool to edit the parameters for each configuration in a different file than the one specified in your architecture's ``_settings.yml`` (like a testbench for example) set ``use_parameters`` to ``true`` and edit the other keys. Otherwise, set it to ``false``.
- Edit the ``param_target_file``, so it matches your design/simulation top top-level.
- Set ``start_delimiter`` and ``stop_delimiter``, so it matches the delimiters of the parameter section in ``param_target_file``.
- A documentation of the keys for ``_settings.yml`` files can be found in section :doc:`/documentation/settings`

.. note::
    If your testbench does not need to have its parameters modified for each configuration (as could a c++ verilator testbench for example), a ``_settings.yml`` is not mandatory

Step 4: Run your design configurations!
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Follow the same steps as in section :doc:`/userguide/quick_start` :
   - Edit ``_run_simulations_settings.yml`` to add your simulations, linked to the corresponding design configurations
   - Run the selected simulations
