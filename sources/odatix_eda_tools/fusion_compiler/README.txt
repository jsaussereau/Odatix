This directory contains the scripts and files required for the Fusion Compiler integration in Odatix.
Please read this file before using the flow.
The current scripts support both logical and physical synthesis.
To choose the synthesis mode, open the tool.yml file and change the synthesis_mode variable as follows:

For logical synthesis:
set synthesis_mode logical;

For physical synthesis:
set synthesis_mode physical;

NOTE:
Currently, the Fusion Compiler flow in Odatix only supports the GF22 technology.
If you want to use another technology, you will need to add the required scripts and technology files manually.
To do this, create a new directory inside the technology directory using the name of your technology, and add the corresponding setup script and required technology files.
Make sure that all library and technology paths are correctly configured before running the synthesis.
