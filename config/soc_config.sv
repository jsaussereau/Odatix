/*
 * A silicon-proven RISC-V based SoC
 *
 * Copyright(C) 2022 by Jonathan Saussereau. All rights reserved.
 * 
 * All source codes and documentation contain proprietary confidential
 * information and are distributed under license. It may be used, copied
 * and/or disclosed only pursuant to the terms of a valid license agreement
 * with Jonathan Saussereau. This copyright must be retained at all times.
 *
 * soc_config.sv
 *
 */
 
 
`ifndef __SOC_CONFIG__
`define __SOC_CONFIG__

/*****************************************************
                Choose the target here                
*****************************************************/

//`define TARGET_ASIC_XFAB
//`define TARGET_ASIC_ST28CMOSFDSOI
//`define TARGET_ASIC_ST130BiCMOS9MW
//`define TARGET_FPGA_XC7K325T
//`define TARGET_FPGA_XC7A100T
//`define TARGET_FPGA_XC7A15T
//`define TARGET_FPGA_XA7S6
`define TARGET_SIM

/*****************************************************
                  Synthesis Settings                  
*****************************************************/

// Keep hierarchy after synthesis?
//`define KEEP_HIERARCHY (* keep_hierarchy = "yes" *) // more accurate utilization reports
`define KEEP_HIERARCHY (* keep_hierarchy = "no" *)  // higher max frequency

// Do synthesis with pads (ASIC)? 
//`define USE_PADS

`endif // __SOC_CONFIG__
