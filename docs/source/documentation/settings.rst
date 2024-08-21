.. _arch_settings:

Settings
========

Architecture Settings
---------------------

These are the YAML key for architecture settings files ``_settings.yml``

+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| 🔑 Key name            | 💡 Role                                               | 💬 Comment                                                 | ➕ Status                                 |
+========================+=======================================================+============================================================+===========================================+
| ``rtl_path``           | Path of the RTL files                                 | The path is relative to the current directory              | Mandatory                                 |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``design_path``        | Path of the design files                              | The path is relative to the current directory              | Optional unless ``param_target_file`` or  |
|                        |                                                       |                                                            | ``generate_command`` are used             |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``generate_rtl``       | Enable RTL generation, using HLS or Chisel for example| Make sure all tools used within this command are installed | Optional                                  |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``generate_command``   | Command to generate the RTL                           | The command will be launched from the work copy of         | Optional unless ``generate_rtl`` is true  |
|                        |                                                       | ``design_path``                                            |                                           |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``top_level_file``     | Filename of top level file                            | The path is relative to ``rtl_path``                       | Mandatory                                 |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``top_level_module``   | Module name of the top level                          | Entity name in vhdl                                        | Mandatory                                 |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``clock_signal``       | Main clock signal                                     | With chisel, the default clock name is 'clock'             | Mandatory                                 |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``reset_signal``       | Main reset signal                                     | With chisel, the default clock name is 'reset'             | Mandatory                                 |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``file_copy_enable``   | Enable the copy of a source file to the work copy of  | This is done after the copy of the copy of ``rtl_path``    | Mandatory                                 |
|                        | $rtl_path                                             |                                                            |                                           |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``file_copy_source``   | Path of the source file to copy                       | The path is relative to the current directory              | Mandatory                                 |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``file_copy_dest``     | Destination path of the copied file                   | The path is relative to ``rtl_path``                       | Mandatory                                 |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``use_parameters``     | Enable the replacement of parameters                  | Architecture parameter files are not used if               | Mandatory                                 |
|                        |                                                       | ``use_parameters`` is false                                |                                           |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``param_target_file``  | Path of the file in which the parameters will be      | The path is relative to ``design_path``                    | Optional unless ``design_path`` is used.  |
|                        | replaced                                              |                                                            | Default value is                          |
|                        |                                                       |                                                            | ``rtl_path``/``top_level_file``           |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``start_delimiter``    | Start delimiter for the parameter replacement         | This mainly depends on the source language                 | Mandatory                                 |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``stop_delimiter``     | Stop delimiter for the parameter replacement          | This mainly depends on the source language                 | Mandatory                                 |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``fmax_lower_bound``   | Lower bound for fmax binary search (in MHz)           | This must be linked to a target                            | Optional                                  |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``fmax_upper_bound``   | Upper bound for fmax binary search (in MHz)           | This must be linked to a target                            | Optional                                  |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+

Simualtion Settings
--------------------

These are the YAML key for the optional simulation settings files ``_settings.yml``

+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| 🔑 Key name            | 💡 Role                                               | 💬 Comment                                                 | ➕ Status                                 |
+========================+=======================================================+============================================================+===========================================+
| ``use_parameters``     | Enable the replacement of parameters                  | Architecture parameter files are not used if               | Mandatory                                 |
|                        |                                                       | ``use_parameters`` is false                                |                                           |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``param_target_file``  | Path of the file in which the parameters will be      | The path is relative to the simulation path. It can        | Optional unless ``use_parameters``        |
|                        | replaced                                              | lead to a file from either the rtl or simulation folder    | is true.                                  |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``start_delimiter``    | Start delimiter for the parameter replacement         | This mainly depends on the source language                 | Optional unless ``use_parameters``        |
|                        |                                                       |                                                            | is true.                                  |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| ``stop_delimiter``     | Stop delimiter for the parameter replacement          | This mainly depends on the source language                 | Optional unless ``use_parameters``        |
|                        |                                                       |                                                            | is true.                                  |
+------------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+


Synthesis Settings
------------------

These are the YAML key for the fmax synthesis settings file ``_run_fmax_synthesis_settings.yml``

+------------------------+----------------------------------------+-------------------------------------------+--------------+
| 🔑 Key name            | 💡 Role                                | 💬 Comment                                | ➕ Status    |
+========================+========================================+===========================================+==============+
| ``overwrite``          | Overwrite existing results             | ``--overwrite`` option overrides this key | Mandatory    |
+------------------------+----------------------------------------+-------------------------------------------+--------------+
| ``ask_continue``       | Do not ask to continue                 | ``--noask`` option overrides this key     | Mandatory    |
+------------------------+----------------------------------------+-------------------------------------------+--------------+
| ``show_log_if_one``    | Show simulation log if there is        |                                           | Mandatory    |
|                        | only one architecture selected         |                                           |              |
+------------------------+----------------------------------------+-------------------------------------------+--------------+
| ``nb_jobs``            | Maximum number of parallel synthesis   |                                           | Mandatory    |
+------------------------+----------------------------------------+-------------------------------------------+--------------+
| ``architectures``      | List of architectures to run           |                                           | Mandatory    |
+------------------------+----------------------------------------+-------------------------------------------+--------------+

Simulation Settings
-------------------

These are the YAML key for the simulation settings file ``_run_simulations_settings.yml``

+------------------------+----------------------------------------+-------------------------------------------+--------------+
| 🔑 Key name            | 💡 Role                                | 💬 Comment                                | ➕ Status    |
+========================+========================================+===========================================+==============+
| ``overwrite``          | Overwrite existing results             | ``--overwrite`` option overrides this key | Mandatory    |
+------------------------+----------------------------------------+-------------------------------------------+--------------+
| ``ask_continue``       | Do not ask to continue                 | ``--noask`` option overrides this key     | Mandatory    |
+------------------------+----------------------------------------+-------------------------------------------+--------------+
| ``show_log_if_one``    | Show simulation log if there is        |                                           | Mandatory    |
|                        | only one architecture selected         |                                           |              |
+------------------------+----------------------------------------+-------------------------------------------+--------------+
| ``nb_jobs``            | Maximum number of parallel synthesis   |                                           | Mandatory    |
+------------------------+----------------------------------------+-------------------------------------------+--------------+
| ``simulations``        | List of simulations to run             |                                           | Mandatory    |
+------------------------+----------------------------------------+-------------------------------------------+--------------+