# Asterism - Documentation

## Makefile Rules

<table class="tg"><thead>
  <tr>
    <th class="tg-0pky">🏷️ Category</th>
    <th class="tg-c3ow">⌨️ Command</th>
    <th class="tg-0pky">💡 Role</th>
  </tr></thead>
<tbody>
  <tr>
    <td class="tg-0pky" rowspan="2">Synthesis</td>
    <td class="tg-0pky">make vivado</td>
    <td class="tg-0pky">Run synthesis + place&amp;route in Vivado</td>
  </tr>
  <tr>
    <td class="tg-0pky">make dc</td>
    <td class="tg-0pky">Run synthesis + place&amp;route in Design Compiler</td>
  </tr>
  <tr>
    <td class="tg-0pky" rowspan="3">Data Export</td>
    <td class="tg-0pky">make results</td>
    <td class="tg-0pky">Export synthesis results</td>
  </tr>
  <tr>
    <td class="tg-0lax">make results_vivado</td>
    <td class="tg-0lax">Export vivado synthesis results only</td>
  </tr>
  <tr>
    <td class="tg-0lax">make results_dc</td>
    <td class="tg-0lax">Export Design Compiler synthesis results only</td>
  </tr>
  <tr>
    <td class="tg-0pky" rowspan="2">Data Exploration</td>
    <td class="tg-0pky">make explore<br></td>
    <td class="tg-0pky">Explore results in a web app (localhost only)</td>
  </tr>
  <tr>
    <td class="tg-0pky">make explore_network</td>
    <td class="tg-0pky">Explore results in a web app (network-accessible)</td>
  </tr>
  <tr>
    <td class="tg-0pky">Others</td>
    <td class="tg-0pky">make help</td>
    <td class="tg-0pky">Display a list of useful commands</td>
  </tr>
</tbody></table>

## Architecture Settings

<table class="tg"><thead>
  <tr>
    <th class="tg-0pky">🔑 key name</th>
    <th class="tg-0pky">💡 Role</th>
    <th class="tg-0pky">💬 Comment</th>
    <th class="tg-0pky">➕ Optional</th>
  </tr></thead>
<tbody>
  <tr>
    <td class="tg-0pky">rtl_path</td>
    <td class="tg-0pky">Path of the RTL files</td>
    <td class="tg-0pky">The path is relative to Asterism root directory</td>
    <td class="tg-0pky">Mandatory</td>
  </tr>
  <tr>
    <td class="tg-0pky">design_path</td>
    <td class="tg-0pky">Path of the design files</td>
    <td class="tg-0pky">The path is relative to Asterism root directory</td>
    <td class="tg-0pky">Optional <br>Unless $param_target_file or $generate_command are used<br></td>
  </tr>
  <tr>
    <td class="tg-0pky">generate_rtl</td>
    <td class="tg-0pky">Enable RTL generation, using HLS or Chisel for example</td>
    <td class="tg-0pky">Make sure all tools used within this command are installed</td>
    <td class="tg-0pky">Optional</td>
  </tr>
  <tr>
    <td class="tg-0pky">generate_command</td>
    <td class="tg-0pky">Command to generate the RTL</td>
    <td class="tg-0pky">The command will be launched from the work copy of $design_path</td>
    <td class="tg-0pky">Optional <br>Unless $generate_rtl is true</td>
  </tr>
  <tr>
    <td class="tg-0pky">top_level_file</td>
    <td class="tg-0pky">Filename of top level file</td>
    <td class="tg-0pky">The path is relative to $rtl_path</td>
    <td class="tg-0pky">Mandatory</td>
  </tr>
  <tr>
    <td class="tg-0pky">top_level_module</td>
    <td class="tg-0pky">Module name of the top level</td>
    <td class="tg-0pky">Entity name in vhdl</td>
    <td class="tg-0pky">Mandatory</td>
  </tr>
  <tr>
    <td class="tg-0pky">clock_signal</td>
    <td class="tg-0pky">Main clock signal</td>
    <td class="tg-0pky">With chisel, the default clock name is 'clock'</td>
    <td class="tg-0pky">Mandatory</td>
  </tr>
  <tr>
    <td class="tg-0pky">reset_signal</td>
    <td class="tg-0pky">Main reset signal</td>
    <td class="tg-0pky">With chisel, the default clock name is 'reset'</td>
    <td class="tg-0pky">Mandatory</td>
  </tr>
  <tr>
    <td class="tg-0pky">file_copy_enable</td>
    <td class="tg-0pky">Enable the copy of a source file to the work copy of $rtl_path</td>
    <td class="tg-0pky">This is done after the copy of the copy of $rtl_path</td>
    <td class="tg-0pky">Mandatory</td>
  </tr>
  <tr>
    <td class="tg-0lax">file_copy_source</td>
    <td class="tg-0lax">Path of the source file to copy</td>
    <td class="tg-0lax">The path is relative to Asterism root directory</td>
    <td class="tg-0lax">Mandatory</td>
  </tr>
  <tr>
    <td class="tg-0lax">file_copy_dest</td>
    <td class="tg-0lax">Destination path of the copied file</td>
    <td class="tg-0lax">The path is relative to $rtl_path</td>
    <td class="tg-0lax">Mandatory</td>
  </tr>
  <tr>
    <td class="tg-0lax">use_parameters</td>
    <td class="tg-0lax">Enable the replacement of parameters</td>
    <td class="tg-0lax">Architecture parameter files are useless if $use_parameters is false</td>
    <td class="tg-0lax">Mandatory</td>
  </tr>
  <tr>
    <td class="tg-0lax">param_target_file</td>
    <td class="tg-0lax">Path of the file in which the parameters will be replaced</td>
    <td class="tg-0lax">The path is relative to $design_path</td>
    <td class="tg-0lax">Optional <br>Unless $design_path is used <br>Default value is <br>$rtl_path/$top_level_file</td>
  </tr>
  <tr>
    <td class="tg-0lax">start_delimiter</td>
    <td class="tg-0lax">Start delimiter for the parameter replacement</td>
    <td class="tg-0lax">This mainly depends on the source language</td>
    <td class="tg-0lax">Mandatory</td>
  </tr>
  <tr>
    <td class="tg-0lax">stop_delimiter</td>
    <td class="tg-0lax">Stop delimiter for the parameter replacement</td>
    <td class="tg-0lax">This mainly depends on the source language</td>
    <td class="tg-0lax">Mandatory</td>
  </tr>
  <tr>
    <td class="tg-0lax">fmax_lower_bound</td>
    <td class="tg-0lax">Lower bound for fmax binary search (in MHz)</td>
    <td class="tg-0lax">This must be linked to a target</td>
    <td class="tg-0lax">Optional</td>
  </tr>
  <tr>
    <td class="tg-0lax">fmax_upper_bound</td>
    <td class="tg-0lax">Upper bound for fmax binary search (in MHz)</td>
    <td class="tg-0lax">This must be linked to a target</td>
    <td class="tg-0lax">Optional</td>
  </tr>
</tbody></table>
