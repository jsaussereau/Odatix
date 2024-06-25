Useful Commands
===============

Makefile Rules
--------------

+-------------------+---------------------------+----------------------------------------------------+
| 🏷️ Category       | ⌨️ Command                | 💡 Role                                            |
+===================+===========================+====================================================+
| Simulation        | ``make sim``              | Run simulations                                    |
+-------------------+---------------------------+----------------------------------------------------+
| Synthesis         | ``make vivado``           | Run synthesis + place&route in *Vivado*            |
|                   +---------------------------+----------------------------------------------------+
|                   | ``make dc``               | Run synthesis in *Design Compiler*                 |
+-------------------+---------------------------+----------------------------------------------------+
| Data Export       | ``make results``          | Export synthesis results                           |
|                   +---------------------------+----------------------------------------------------+
|                   | ``make results_vivado``   | Export *Vivado* synthesis results only             |
+                   +---------------------------+----------------------------------------------------+
|                   | ``make results_dc``       | Export *Design Compiler* synthesis results only    |
+-------------------+---------------------------+----------------------------------------------------+
| Data Exploration  | ``make explore``          | Explore results in a web app (localhost only)      |
|                   +---------------------------+----------------------------------------------------+
|                   | ``make explore_network``  | Explore results in a web app (network-accessible)  |
+-------------------+---------------------------+----------------------------------------------------+
| Others            | ``make help``             | Display a list of useful commands                  |
+-------------------+---------------------------+----------------------------------------------------+

Options can be passed to the underlying scripts through the variable ``OPTIONS``. 
Example:

.. code-block:: console

    make vivado OPTIONS="--noask --overwrite"