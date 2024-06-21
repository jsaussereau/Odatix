.. _arch_settings:

Architecture Settings
=====================

+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| 🔑 key name        | 💡 Role                                               | 💬 Comment                                                 | ➕ Optional                               |
+====================+=======================================================+============================================================+===========================================+
| rtl_path           | Path of the RTL files                                 | The path is relative to Asterism root directory            | Mandatory                                 |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| design_path        | Path of the design files                              | The path is relative to Asterism root directory            | Optional unless $param_target_file or     |
|                    |                                                       |                                                            | $generate_command are used                |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| generate_rtl       | Enable RTL generation, using HLS or Chisel for example| Make sure all tools used within this command are installed | Optional                                  |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| generate_command   | Command to generate the RTL                           | The command will be launched from the work copy of         | Optional unless $generate_rtl is true     |
|                    |                                                       | $design_path                                               |                                           |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| top_level_file     | Filename of top level file                            | The path is relative to $rtl_path                          | Mandatory                                 |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| top_level_module   | Module name of the top level                          | Entity name in vhdl                                        | Mandatory                                 |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| clock_signal       | Main clock signal                                     | With chisel, the default clock name is 'clock'             | Mandatory                                 |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| reset_signal       | Main reset signal                                     | With chisel, the default clock name is 'reset'             | Mandatory                                 |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| file_copy_enable   | Enable the copy of a source file to the work copy of  | This is done after the copy of the copy of $rtl_path       | Mandatory                                 |
|                    | $rtl_path                                             |                                                            |                                           |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| file_copy_source   | Path of the source file to copy                       | The path is relative to Asterism root directory            | Mandatory                                 |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| file_copy_dest     | Destination path of the copied file                   | The path is relative to $rtl_path                          | Mandatory                                 |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| use_parameters     | Enable the replacement of parameters                  | Architecture parameter files are useless if                | Mandatory                                 |
|                    |                                                       | $use_parameters is false                                   |                                           |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| param_target_file  | Path of the file in which the parameters will be      | The path is relative to $design_path                       | Optional unless $design_path is used      |
|                    | replaced                                              |                                                            | Default value is $rtl_path/$top_level_file|
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| start_delimiter    | Start delimiter for the parameter replacement         | This mainly depends on the source language                 | Mandatory                                 |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| stop_delimiter     | Stop delimiter for the parameter replacement          | This mainly depends on the source language                 | Mandatory                                 |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| fmax_lower_bound   | Lower bound for fmax binary search (in MHz)           | This must be linked to a target                            | Optional                                  |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+
| fmax_upper_bound   | Upper bound for fmax binary search (in MHz)           | This must be linked to a target                            | Optional                                  |
+--------------------+-------------------------------------------------------+------------------------------------------------------------+-------------------------------------------+

