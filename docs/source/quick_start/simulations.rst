***********
Simulations
***********

Step 1: Initialize a directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Place yourself in an empty directory, for example:

.. code-block:: bash

   mkdir ~/odatix_example
   cd ~/odatix_example

Run the init command of Odatix to create configuration files. 

.. code-block:: bash

   odatix init --examples

Step 2: Choose the designs you want to simulate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Uncomment the simulations you want to simulate in ``odatix_userconfig/simulations_settings.yml``.
Those simulations are defined in ``odatix_userconfig/simulations``.
Architectures are defined in ``odatix_userconfig/architectures``.

Change the value of ``nb_jobs`` in ``odatix_userconfig/simulations_settings.yml`` depending on the number of logical cores available on your CPU. 

.. tip::
   75% of your number of logical cores is usually a good balance for ``nb_jobs``.

Example:

.. code-block:: yaml
   :caption: odatix_userconfig/simulations_settings.yml
   :linenos:
   :emphasize-lines: 5

   overwrite:        No  # overwrite existing results?
   ask_continue:     Yes # prompt 'continue? (y/n)' after settings checks?
   exit_when_done:   No  # exit monitor when all jobs are done
   log_size_limit:   300 # size of the log history per job in the monitor
   nb_jobs:          12  # maximum number of parallel synthesis

   simulations: 
      - TB_Example_Counter_Verilator:
        - Example_Counter_sv/04bits
        - Example_Counter_sv/08bits
        - Example_Counter_sv/16bits
        - Example_Counter_sv/24bits
        - Example_Counter_sv/32bits
        - Example_Counter_sv/48bits
        - Example_Counter_sv/64bits

Step 3: Run the selected designs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   odatix sim

Step 4: Try with your own design
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Check out sections :doc:`/quick_start/add_design` and  :doc:`/quick_start/add_simulation`