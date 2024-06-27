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

    bool reset_ok = true;
    bool increment_ok = true;
    bool decrement_ok = true;
    bool init_ok = true;

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

        // Apply stimulus based on cycle
        if (top->clock) {
            if (cycle == 4) {
                if (top->o_value != 0) {
                    reset_ok = false;
                    std::cout << "Reset KO: Expected = 0, Received = " << int(top->o_value) << std::endl;
                } else {
                    std::cout << "Reset OK" << std::endl;
                }
            } else if (cycle == 5) {
                if (top->o_value != 1) {
                    increment_ok = false;
                    std::cout << "Increment KO: Expected = 1, Received = " << int(top->o_value) << std::endl;
                }
            } else if (cycle == 6) {
                if (top->o_value != 2) {
                    increment_ok = false;
                    std::cout << "Increment KO: Expected = 2, Received = " << int(top->o_value) << std::endl;
                }
            } else if (cycle == 7) {
                if (top->o_value != 3) {
                    increment_ok = false;
                    std::cout << "Increment KO: Expected = 3, Received = " << int(top->o_value) << std::endl;
                }
                if (increment_ok) {
                    std::cout << "Increment OK" << std::endl;
                }
                top->i_inc_dec = 0; // Start decrementing
            } else if (cycle == 8) {
                if (top->o_value != 2) {
                    decrement_ok = false;
                    std::cout << "Decrement KO: Expected = 2, Received = " << int(top->o_value) << std::endl;
                }
            } else if (cycle == 9) {
                if (top->o_value != 1) {
                    decrement_ok = false;
                    std::cout << "Decrement KO: Expected = 1, Received = " << int(top->o_value) << std::endl;
                }
            } else if (cycle == 10) {
                if (top->o_value != 0) {
                    decrement_ok = false;
                    std::cout << "Decrement KO: Expected = 0, Received = " << int(top->o_value) << std::endl;
                }
                if (decrement_ok) {
                    std::cout << "Decrement OK" << std::endl;
                }
                top->i_inc_dec = 1; // Stop decrementing
                top->i_init = 1;    // Start initialization
            } else if (cycle == 13) {
                if (top->o_value != 0) {
                    init_ok = false;
                    std::cout << "Initialization KO: Expected = 0, Received = " << int(top->o_value) << std::endl;
                }
            } else if (cycle == 14) {
                if (top->o_value != 0) {
                    init_ok = false;
                    std::cout << "Initialization KO: Expected = 0, Received = " << int(top->o_value) << std::endl;
                }
            } else if (cycle == 15) {
                if (top->o_value != 0) {
                    init_ok = false;
                    std::cout << "Initialization KO: Expected = 0, Received = " << int(top->o_value) << std::endl;
                }
                if (init_ok) {
                    std::cout << "Initialization OK" << std::endl;
                }
                top->i_init = 0;    // Stop initialization
            }
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
