---
title: "FIR filter (C++ / Vitis HLS)"
description: "A FIR filter written in C++ and turned into RTL by Vitis HLS, swept over an HLS pragma and a generation parameter before being synthesized like any other design."
weight: 7
---

# FIR filter (C++ / Vitis HLS)

The HLS example synthesizes a design that **does not exist as RTL** until Odatix asks for it: a direct-form FIR filter written in C++, handed to **Vitis HLS**, and only then implemented by Vivado (or any other supported eda tool).

What is swept is not a Verilog parameter but the way the high-level synthesis is run: two **HLS pragmas** — the initiation interval the MAC loop is pipelined at, and how the tap delay line is partitioned — and one **generation parameter**, the number of taps, passed to the C++ front end as a preprocessor define. All three are variables of the architecture, so one point of the design space is one high-level synthesis followed by one logic synthesis, and the C++ is never modified.

{{< details title="What this example demonstrates" >}}
- **RTL generated from C/C++** — `generate_rtl` with a high-level synthesis instead of a hardware description language compiler, the same mechanism the [Chisel examples](/docs/examples/architectures/counter/) use.
- **[Virtual parameter domains](/docs/configurations/virtual_param_domains/)** — every knob is a `${...}` placeholder in the generation command, so there is no configuration directory, no `.txt` file and no delimiter anywhere.
- **Pragmas explored without touching the source** — every directive is applied from the Tcl script with `set_directive_*`, so the same unmodified C++ is synthesized at every point.
- **The two ways a pragma can be explored** — sweeping the *value* of a directive (`ii`), and sweeping *which directive is applied at all* (`partition`, including a "no pragma" case).
- **The real cost of an HLS pragma** — the numbers come from the actual place & route, not from the HLS estimate.
- **A three-dimensional trade-off worth mapping** — throughput against area, with a filter length that changes which pragma dominates.
{{< /details >}}

{{< toc >}}

## What the design does

`fir` is a **direct-form FIR filter**. One call consumes one sample and produces one output: the tap delay line is shifted, every tap is multiplied by its coefficient, and the products are accumulated.

{{< code lang=cpp filename="examples/fir_hls/src/fir.cpp" >}}
void fir(data_t sample, const coef_t coeffs[TAPS], data_t *out) {
  static data_t shift_reg[TAPS];
  acc_t acc = 0;

mac_loop:
  for (int i = TAPS - 1; i >= 0; i--) {
    if (i == 0) {
      shift_reg[0] = sample;
    } else {
      shift_reg[i] = shift_reg[i - 1];
    }
    acc += (acc_t)shift_reg[i] * (acc_t)coeffs[i];
  }

  // Coefficients are Q1.15: bring the accumulator back to the input format.
  *out = (data_t)(acc >> 15);
}
{{< /code >}}

Coefficients are an **input port**, not a constant table, so the filter is programmable and the generated RTL needs no memory initialization file — which keeps the design a plain set of `.v` files any tool can read.

{{< details title="Interface" >}}
Vitis HLS gives the function the default `ap_ctrl_hs` block-level protocol, so the generated module has more ports than the C++ has arguments:

| Port | Direction | Width | Role |
|---|---|---|---|
| `ap_clk` | in | 1 | Clock, rising edge |
| `ap_rst` | in | 1 | Synchronous reset, active high |
| `ap_start` / `ap_done` / `ap_idle` / `ap_ready` | in/out | 1 | Block-level handshake |
| `sample` | in | 16 | Input sample |
| `coeffs_address0` / `coeffs_ce0` / `coeffs_q0` | out/out/in | — | `ap_memory` interface to the coefficient table |
| `out_r` / `out_r_ap_vld` | out | 16 / 1 | Filter output and its valid flag |

This is why the architecture declares `clock_signal: "ap_clk"` and `reset_signal: "ap_rst"` rather than the `clock`/`reset` the other examples use.
{{< /details >}}

### Parameters

| Knob | Kind | Swept values | How it is applied | Effect |
|---|---|---|---|---|
| `taps` | generation parameter | 8, 16, 32 | `-DTAPS=<n>` on the C++ front end | Filter length. Sets how many multiply-accumulates one sample costs, so it scales both the arithmetic and the delay line. |
| `ii` | pragma value | 1, 2, 4 | `set_directive_pipeline -II <n>` | Initiation interval of the MAC loop. II=1 issues one sample per cycle and needs the most operators; larger IIs let HLS share them. |
| `partition` | pragma choice | `none`, `cyclic`, `complete` | `set_directive_array_partition`, or nothing at all | How the tap delay line is stored. `none` leaves it in a bram — two accesses per cycle at most — `cyclic` splits it into four banks, `complete` turns it into registers readable in parallel. |

The three interact, and the interaction is the point. `ii` asks for a throughput, but **`partition` decides whether that throughput is reachable**: with the delay line in a bram, the memory ports cap the loop long before the operators do, so a demanding `ii` is silently not met. At 32 taps and II=1, the three partitions give three different micro-architectures:

| `partition` | II=1 met? | Delay line | Estimated fmax |
|---|---|---|---|
| `none` | no | 2 brams | 265.8 MHz |
| `cyclic` | no | 2 brams + multiplexers | 261.3 MHz |
| `complete` | **yes** | registers + multiplexers | 215.3 MHz |

Only `complete` honours the pipeline directive, and it pays about 20% of the clock for it. Whether that is a good trade depends on the filter length — which is exactly the question a multi-dimensional sweep answers, and exactly what an HLS estimate alone cannot tell you.

## Files

{{< code lang=text filename="workspace" >}}
examples/
└── fir_hls/
    ├── run_hls.tcl                # the high-level synthesis script
    └── src/
        ├── fir.h                  # types and the TAPS default
        └── fir.cpp                # the filter — no "#pragma HLS" in it

odatix_userconfig/
└── architectures/
    └── Example_FIR_hls/
        └── _settings.yml          # the only file: no configuration directory
{{< /code >}}

There is **one** settings file and no configuration at all — the twenty-seven points of the sweep are described by the three variables it declares.

## Architecture settings

{{< code lang=yaml filename="architectures/Example_FIR_hls/_settings.yml" >}}
# Source files
design_path: "examples/fir_hls"
design_path_whitelist: ['src', 'run_hls.tcl']
design_path_blacklist: []

# Generate the rtl (from C/C++ with Vitis HLS here)
generate_rtl: Yes
generate_command: "vitis_hls -f run_hls.tcl -tclargs ${taps} ${ii} ${partition}"
generate_output: "rtl"

# Generated design settings
top_level_file: "fir.v"
top_level_module: "fir"
clock_signal: "ap_clk"
reset_signal: "ap_rst"

# No parameter file: nothing is replaced in the sources
use_parameters: No

variables:
  taps:
    type: list
    unit: taps
    settings:
      list: [8, 16, 32]

  ii:
    type: list
    settings:
      list: [1, 2, 4]

  partition:
    type: list
    settings:
      list: ["none", "cyclic", "complete"]
{{< /code >}}

Three things are worth pointing out.

### The high-level synthesis *is* the generation command

`generate_command` is run in the job's work directory before the eda tool is started, exactly as `sbt runMain` is for the [Chisel examples](/docs/examples/architectures/counter/). Nothing about it is HLS-specific: any command that writes RTL into `rtl/` will do.

That directory is not a convention of the example — Odatix always reads the design from `rtl/`, which is why the last thing `run_hls.tcl` does is copy the generated Verilog there:

{{< code lang=tcl filename="examples/fir_hls/run_hls.tcl" >}}
file mkdir rtl
foreach rtl_file [glob -nocomplain hls_proj/solution/syn/verilog/*.v] {
  file copy -force $rtl_file rtl
}
{{< /code >}}

### The pragmas live in the Tcl script, not in the C++

`fir.cpp` contains no `#pragma HLS` at all. Everything being explored is applied as a **directive** instead — which is what makes the pragmas swept from the command line:

{{< code lang=tcl filename="examples/fir_hls/run_hls.tcl" >}}
set_directive_pipeline -II $ii "fir/mac_loop"

switch -exact -- $partition {
  none     { }
  cyclic   { set_directive_array_partition -type cyclic -factor 4 -dim 1 "fir" shift_reg }
  complete { set_directive_array_partition -type complete -dim 1 "fir" shift_reg }
}
{{< /code >}}

The two are explored differently on purpose:

- **`ii` sweeps the value of a directive.** The pragma is always applied; only its argument changes.
- **`partition` sweeps which directive is applied.** A branch of the `switch` applies **no directive at all**, so "the pragma is absent" is a point of the design space like any other — the baseline the other two are read against. Any pragma can be explored this way, including ones that take no argument (`dataflow`, `inline`, `unroll`).

This is what makes the sweep possible without any parameter substitution: the source is identical for all twenty-seven runs, and only the arguments of the script change. It also keeps the C++ readable and reusable outside Odatix — the same property the [delimiter-based examples](/docs/examples/architectures/cordic/) preserve for RTL.

> [!NOTE]
> Directives can only be swept this way because they are a Tcl API. If a pragma you need has no `set_directive_*` equivalent, it has to stay in the source — and then it is explored with [delimiter-based substitution](/docs/configurations/param_files/), exactly like a Verilog parameter, with the `#pragma HLS` line as its delimiter.

### All three knobs are virtual parameter domains

`${taps}`, `${ii}` and `${partition}` are filled from the `variables` block, so they behave like [parameter domains](/docs/configurations/param_domains/) — combined automatically, selectable one by one — with no directory and no `.txt` file to write. `taps` declares `unit: taps` so the runs are named `taps/16taps`; the other two declare none, so they are named `ii/2` and `partition/complete`.

> [!TIP]
> The knobs are deliberately of two different kinds: `taps` is a **generation parameter** (it changes the C++ that is compiled) while `ii` and `partition` are **pragmas** (they change how that C++ is scheduled and mapped). To Odatix they are the same thing — a value substituted into a command — which is what makes a design space mixing the two easy to describe.

## Running the sweep

Add the architecture to the job settings file and run the synthesis:

{{< code lang=yaml filename="odatix_userconfig/fmax_synthesis_settings.yml" >}}
architectures:
  - Example_FIR_hls
{{< /code >}}

{{< code lang=shell prompt=true >}}
$ odatix fmax -t vivado
{{< /code >}}

That single entry is 3 filter lengths × 3 initiation intervals × 3 partitions = **27 points**, each one a high-level synthesis followed by a full fmax search. That is a long run — a slice, or a single point, is selected the same way a parameter domain is:

{{< code lang=yaml filename="odatix_userconfig/fmax_synthesis_settings.yml" >}}
architectures:
  - Example_FIR_hls+taps/16taps+ii/1+partition/complete  # one point
  - Example_FIR_hls+taps/32taps+ii/1+partition/*         # the pragma comparison above
  - Example_FIR_hls+taps/*+ii/*+partition/complete       # the throughput/area curve
{{< /code >}}

> [!WARNING]
> This example needs **Vitis HLS** installed and in your `PATH`, in addition to the synthesis tool. It is the only example shipped with Odatix that requires it, which is why it is listed separately in the job settings files.

> [!INFO]
> `run_hls.tcl` sets the part Vitis HLS estimates against (`xc7a100tcsg324-1`) and the clock it schedules for. Those only drive the HLS scheduling — the numbers Odatix reports come from the real synthesis that follows, on the target declared in `targets/target_vivado.yml`. If you change the target, change the part in the script too, or the scheduling will be estimated for the wrong device.

## What to look for in the results

The interesting comparison is not the HLS report but what the implementation actually costs:

- **Fmax against II.** Larger initiation intervals shorten the critical path far less than they cut the operator count — the pipeline is already registered.
- **DSP count against II.** This is where the pragma pays off, and where the effect of `taps` is clearest: the number of multipliers a given II needs scales with the filter length.
- **BRAM count against `partition`.** The clearest reading of what a pragma actually did: `none` and `cyclic` spend brams and keep a single MAC, `complete` spends registers and multiplexers to feed several. The fmax and area difference between them is the price of meeting the requested II.
- **Throughput, not frequency.** A design at II=2 processes one sample every two cycles, so its useful sample rate is `fmax / 2`. Comparing frequencies alone across initiation intervals is misleading; that is a good candidate for a [derived metric](/docs/results/).

## Where to go next

- [Virtual parameter domains](/docs/configurations/virtual_param_domains/) — the mechanism behind `${taps}` and `${ii}`.
- [Counter](/docs/examples/architectures/counter/) — the same generation mechanism with Chisel, and the simplest example of it.
- [Workflows](/docs/examples/workflows/) — if what you want to measure is the HLS report itself rather than the implemented design, a workflow is the job type to reach for.
- [All architecture examples](/docs/examples/architectures/) — the designs and what each one adds.
