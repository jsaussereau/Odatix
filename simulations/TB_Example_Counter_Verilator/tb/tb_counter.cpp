#include <verilated.h>
#include <verilated_vcd_c.h>
#include <getopt.h>
#include <iostream>

#include "Vcounter.h"

#define PERIOD 10

vluint64_t main_time = 0;  // Current simulation time
vluint64_t cycle = 0;      // Current clock cycle

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    std::string vcd_file_path = "./waveform.vcd";

    // Options
    int opt;
    static struct option long_options[] = {
        {"vcd_file", required_argument, 0, 'v'},
        {0, 0, 0, 0}
    };

    int option_index = 0;
    while ((opt = getopt_long(argc, argv, "v:", long_options, &option_index)) != -1) {
        switch (opt) {
            case 'v':
                vcd_file_path = optarg;
                break;
            default:
                std::cerr << "Error: Invalid option '" << (char)opt << "'" << std::endl;
                return 1;
        }
    }

    // Instantiate the design
    Vcounter* top = new Vcounter;

    // Initialize VCD trace dump
    Verilated::traceEverOn(true);
    VerilatedVcdC* tfp = new VerilatedVcdC;
    top->trace(tfp, 99);
    tfp->open(vcd_file_path.c_str());

    // Initial signals
    top->clock = 0;
    top->reset = 1;
    top->i_init = 0;
    top->i_inc_dec = 1;

    // Simulation loop
    while (!Verilated::gotFinish() && cycle < 100) {

        // Toggle clock
        top->clock = !top->clock;

        // Set reset low
        if (main_time == 9) {
            top->reset = 0;
        }

        // Run half a period
        Verilated::timeInc(PERIOD / 2);

        // Evaluate the model
        top->eval();

        // Dump VCD trace
        tfp->dump(main_time);

        // Print the current state (optional)
        if (top->clock) {
            std::cout << "Cycle: " << cycle << ", clk: " << int(top->clock)
                      << ", rst: " << int(top->reset) << ", init: " << int(top->i_init)
                      << ", inc_dec: " << int(top->i_inc_dec) << ", value: " << int(top->o_value)
                      << std::endl;
        }

        main_time++;
        cycle = main_time / 2; // Increment cycle every two main_time increments
    }

    // Finalize simulation
    top->final();
    tfp->close();
    delete top;
    delete tfp;
    return 0;
}
