---
title: "Counter (Verilog, SystemVerilog, VHDL & Chisel)"
description: "The same up/down counter written four times, in four languages, to show that only the delimiters change — plus a fifth variant parameterized on the command line."
weight: 2
---

# Counter (Verilog, SystemVerilog, VHDL & Chisel)

The counter is the **smallest complete example** shipped with Odatix, and the one to read first. It is a single register with an increment/decrement input, described five times: in Verilog, SystemVerilog, VHDL, Chisel, and Chisel again with the width passed on the command line instead of written in the sources.

Nothing about the design is interesting — that is the point. What the example shows is that **the way a design is parameterized is a property of its configuration, not of Odatix**, and that going from one language or one flow to another changes four lines of YAML.

{{< details title="What this example demonstrates" >}}
- **The minimal architecture configuration** — source files, clock, reset, delimiters, frequency bounds, and nothing else.
- **Language independence** — the same sweep on Verilog, SystemVerilog, VHDL and Chisel, differing only by their delimiters.
- **Generated RTL** — the Chisel versions elaborate their own SystemVerilog before synthesis, through `generate_command`.
- **[Configurations](/docs/configurations/) as plain text files** — `04bits.txt`, `08bits.txt`, … each holding the text to substitute, and each becoming one point on the curve.
- **[Virtual parameter domains](/docs/configurations/virtual_param_domains/)** — the CLI variant sweeps a width that never appears in any file, only in a command line.
- **Per-target frequency bounds** — the [fmax search](/docs/features/rtl_fmax_synthesis/) is given a narrower range on the targets where the answer is already roughly known.
- **[Simulations](/docs/features/simulation/) with GHDL and Verilator** — two testbenches that check the counter and write their own `results.yml`.
{{< /details >}}


{{< toc >}}

## What the design does

A `BITS`-wide register, clocked, with a synchronous reset:

- `reset` or `i_init` forces the value back to zero,
- otherwise `i_inc_dec` chooses between `value + 1` and `value - 1`,
- `o_value` exposes the register.

That is all. The whole design is one always block, and its area is `BITS` flip-flops plus an incrementer/decrementer — which is exactly why it makes a readable first sweep: area grows linearly with `BITS`, while the maximum frequency degrades slowly as the carry chain gets longer.

{{< details title="Interface" >}}
| Port | Direction | Width | Role |
|---|---|---|---|
| `clock` | in | 1 | Clock, rising edge |
| `reset` | in | 1 | Synchronous reset, active high |
| `i_init` | in | 1 | Force the counter back to zero |
| `i_inc_dec` | in | 1 | 1 = count up, 0 = count down |
| `o_value` | out | `BITS` | Current value |

The Chisel versions expose the same ports, except that `clock` and `reset` are implicit and emitted by Chisel itself.
{{< /details >}}

### Parameters

| Parameter | Default | Effect |
|---|---|---|
| `BITS` | 8 | Counter width. Sets the number of flip-flops and the length of the carry chain. |

Seven configurations are provided for every version: `04bits`, `08bits`, `16bits`, `24bits`, `32bits`, `48bits`, `64bits`.

## Files

{{< code lang=text filename="workspace" >}}
examples/
├── counter_verilog/counter.v
├── counter_sv/counter.sv
├── counter_vhdl/counter.vhdl
├── counter_chisel/
│   ├── build.sbt
│   └── src/main/scala/counter.scala
└── counter_chisel_cli/            # same Chisel design, --width on the CLI
    ├── build.sbt
    └── src/main/scala/counter.scala

odatix_userconfig/
├── architectures/
│   ├── Example_Counter_verilog/
│   │   ├── _settings.yml
│   │   └── 04bits.txt, 08bits.txt, 16bits.txt, … 64bits.txt
│   ├── Example_Counter_sv/        # same structure
│   ├── Example_Counter_vhdl/      # same structure, VHDL delimiters
│   ├── Example_Counter_chisel/    # same structure, Scala delimiters
│   └── Example_Counter_chisel_cli/
│       └── _settings.yml          # no configuration file at all
└── simulations/
    ├── TB_Example_Counter_GHDL/       # VHDL testbench
    └── TB_Example_Counter_Verilator/  # C++ testbench
{{< /code >}}

## Architecture settings

The Verilog version is as short as an architecture gets:

{{< code lang=yaml filename="architectures/Example_Counter_verilog/_settings.yml" >}}
# Source files
rtl_path: "examples/counter_verilog"
top_level_file: "counter.v"
top_level_module: "counter"

# Signals
clock_signal: "clock"
reset_signal: "reset"

# Delimiters for parameter files
use_parameters: Yes
start_delimiter: "counter #("
stop_delimiter: ")("

# Default frequencies (in MHz)
fmax_synthesis:
  lower_bound: 50
  upper_bound: 1500
custom_freq_synthesis:
  list: [50, 100]
{{< /code >}}

The delimiters are the module header itself — nothing is inserted in the RTL:

{{< code lang=verilog filename="examples/counter_verilog/counter.v" >}}
module counter #(
  parameter BITS = 8
)(
  input  wire            clock,
{{< /code >}}

Everything between `counter #(` and `)(` is replaced by the content of the selected configuration file, which holds exactly the text to write:

{{< code lang=text filename="architectures/Example_Counter_verilog/16bits.txt" >}}

  parameter BITS = 16
{{< /code >}}

> [!TIP]
> The configuration file holds a **fragment of source code**, not just a value. That is what lets one file set several parameters at once, and what makes the mechanism work identically in Verilog, VHDL or Scala.

### Per-target frequency bounds

Below the defaults, each architecture may narrow the [fmax search](/docs/features/rtl_fmax_synthesis/) range per [target](/docs/reference/targets/). The binary search converges faster when it starts from a range that actually contains the answer:

{{< code lang=yaml filename="architectures/Example_Counter_verilog/_settings.yml" >}}
xc7a100t-csg324-1:
  fmax_synthesis:
    lower_bound: 250
    upper_bound: 900
  custom_freq_synthesis:
    list: [50, 100]
AMS350CMOS:
  fmax_synthesis:
    lower_bound: 60
    upper_bound: 160
  custom_freq_synthesis:
    list: [50, 100]
{{< /code >}}

A 350 nm ASIC process and a 28 nm FPGA do not live in the same decade of frequencies, so a single global range would waste most of its iterations on either one.

## The same design, four languages

Only the source paths and the delimiters change from one version to the next.

{{< tabs groupId="counter-lang" >}}
{{< tab name="Verilog" >}}
```verilog
module counter #(
  parameter BITS = 8
)(
```
```yaml
rtl_path: "examples/counter_verilog"
top_level_file: "counter.v"
start_delimiter: "counter #("
stop_delimiter: ")("
```
{{< /tab >}}
{{< tab name="SystemVerilog" >}}
```systemverilog
module counter #(
  parameter BITS = 8
)(
```
```yaml
rtl_path: "examples/counter_sv"
top_level_file: "counter.sv"
start_delimiter: "counter #("
stop_delimiter: ")("
```
{{< /tab >}}
{{< tab name="VHDL" >}}
```vhdl
entity counter is
  generic (
    BITS : integer := 8
  );
```
```yaml
rtl_path: "examples/counter_vhdl"
top_level_file: "counter.vhdl"
start_delimiter: "generic ("
stop_delimiter: "  );"
```
{{< /tab >}}
{{< tab name="Chisel" >}}
```scala
object Counter extends App {
  ChiselStage.emitSystemVerilog(
    new Counter(8),
```
```yaml
design_path: "examples/counter_chisel"
param_target_file: "src/main/scala/counter.scala"
start_delimiter: "new Counter("
stop_delimiter: ")"
```
{{< /tab >}}
{{< /tabs >}}

The VHDL and Chisel configuration files hold the fragment their own syntax expects — `BITS : integer := 16` and `BITS = 16` respectively — and the SystemVerilog one is byte-for-byte the Verilog one.

> [!INFO]
> `Example_Counter_verilog` is the version enabled by default in the run settings, because plain Verilog is the only language every supported EDA tool accepts. The VHDL, SystemVerilog and Chisel versions are present but commented out.

### The Chisel versions: generating the RTL first

A Chisel design is not RTL yet, so the architecture declares **how to produce it**. Odatix copies the design directory, patches the Scala source, runs the generation command, and synthesizes what comes out:

{{< code lang=yaml filename="architectures/Example_Counter_chisel/_settings.yml" >}}
# Source files
design_path: "examples/counter_chisel"
design_path_whitelist: ['project', 'src', 'build.sbt']
design_path_blacklist: []

# Generate the rtl (from chisel for example)
generate_rtl: Yes
generate_command: "sbt 'runMain example.Counter --o=rtl'"  # requires sbt and firtool
generate_output: "rtl"  # path of the generated rtl

# Generated design settings
top_level_file: "counter.sv"
top_level_module: "counter"
clock_signal: "clock"
reset_signal: "reset"

# Delimiters for parameter files
use_parameters: Yes
param_target_file: "src/main/scala/counter.scala"
start_delimiter: "new Counter("
stop_delimiter: ")"
{{< /code >}}

Three settings carry the whole difference with an RTL architecture:

- `design_path` instead of `rtl_path`, with a whitelist so that `target/`, `project/target/` and other sbt build artifacts are not copied into every job directory.
- `generate_rtl` / `generate_command` / `generate_output` — what to run, and where the RTL lands afterwards.
- `param_target_file` — the substitution happens in the **Scala** source, not in the generated SystemVerilog, so the width is baked in before elaboration.

The design also overrides its emitted module name so that the generated file matches `top_level_file`, whatever the Scala class is called:

{{< code lang=scala filename="examples/counter_chisel/src/main/scala/counter.scala" >}}
class Counter(BITS: Int) extends Module {
  override val desiredName = s"counter"
{{< /code >}}

> [!WARNING]
> The Chisel examples need **sbt** and **firtool** on the machine. They are the only examples with a toolchain requirement beyond the EDA tool itself.

## Command-line parameterization: `Example_Counter_chisel_cli`

`Example_Counter_chisel_cli` synthesizes the **same counter** across the **same seven widths**, but has no configuration directory at all — not one `.txt` file, and nothing replaced in the sources.

Instead, the generation command carries a placeholder, and the architecture declares the variable that fills it:

{{< code lang=yaml filename="architectures/Example_Counter_chisel_cli/_settings.yml" >}}
generate_rtl: Yes
generate_command: "sbt 'runMain example.Counter --width ${width} --o=rtl'"
generate_output: "rtl"

# No parameter file: nothing is replaced in the sources
use_parameters: No

variables:
  width:
    type: list
    unit: bits  # only annotates the name of the run (width/16bits)
    settings:
      list: [4, 8, 16, 24, 32, 48, 64]
{{< /code >}}

`width` behaves exactly like a [parameter domain](/docs/configurations/param_domains/): the design is synthesized once per value, and results are labelled `width/04bits`, `width/08bits`, and so on — but the domain is **virtual**, with no directory and no file behind it.

The Scala side simply reads the flag, and forwards everything else to firtool:

{{< code lang=scala filename="examples/counter_chisel_cli/src/main/scala/counter.scala" >}}
val widthIndex = args.indexOf("--width")
val bits =
  if (widthIndex >= 0 && widthIndex + 1 < args.length) args(widthIndex + 1).toInt
  else DEFAULT_BITS

// Everything else is passed on to firtool, "--width <n>" excluded.
val firtoolArgs =
  if (widthIndex >= 0) args.patch(widthIndex, Nil, 2)
  else args
{{< /code >}}

A single line in the run settings covers the seven widths:

{{< code lang=yaml filename="fmax_synthesis_settings.yml" >}}
architectures:
  - Example_Counter_Chisel_CLI
{{< /code >}}

and one of them is selected with a `+`, on the command line or in the file:

{{< code lang=shell prompt=true >}}
$ odatix fmax -a Example_Counter_Chisel_CLI+width/16bits
{{< /code >}}

> [!TIP]
> Prefer this form whenever the design already accepts the parameter on its command line — a generator flag, a `make` variable, an environment variable. It removes the configuration directory entirely, and the sweep is declared where the sweep belongs.

## Running the sweep

The counter is what the shipped run settings enable out of the box:

{{< code lang=yaml filename="fmax_synthesis_settings.yml" >}}
architectures:
  - Example_Counter_verilog/04bits
  - Example_Counter_verilog/08bits
  - Example_Counter_verilog/16bits
  - Example_Counter_verilog/24bits
  - Example_Counter_verilog/32bits
  - Example_Counter_verilog/48bits
  - Example_Counter_verilog/64bits
{{< /code >}}

{{< code lang=shell prompt=true >}}
$ odatix fmax -t vivado
{{< /code >}}

The same list appears in `custom_freq_synthesis_settings.yml`, where each configuration is synthesized at 50 MHz and 100 MHz instead of being searched for its maximum frequency.

> [!INFO]
> `Example_Counter_verilog/04bits` is commented as failing with **OpenLane**: a 4-bit counter is small enough that the flow trips over a design with almost nothing in it. It is a genuine tool limitation, kept in the file as a warning rather than removed.

## Simulation

Two testbenches check the counter, and both **write their own `results.yml`** rather than printing numbers for Odatix to scrape out of a log.

| Testbench | Tool | Testbench language | Runs on |
|---|---|---|---|
| `TB_Example_Counter_GHDL` | GHDL | VHDL | `Example_Counter_vhdl` |
| `TB_Example_Counter_Verilator` | Verilator | C++ | `Example_Counter_verilog`, `Example_Counter_sv`, `Example_Counter_chisel` |

{{< code lang=yaml filename="simulations/TB_Example_Counter_Verilator/_settings.yml" >}}
# What to do for this simulation. The "main" task is the entry point
tasks:
- name: main
  commands:
  - make sim --no-print-directory

# Where Odatix should look for progress information, and how to parse it
progress:
  file: "log/progress.log"
  regex: "(.*): ([0-9]+)%(.*)"

# Architectures this testbench is meant to run on. Only an indication: running
# it on another one works, and only prints a warning.
architectures:
- Example_Counter_verilog
{{< /code >}}

The GHDL testbench additionally declares delimiters of its own, because the width has to be propagated into the **testbench entity** as well as into the design:

{{< code lang=yaml filename="simulations/TB_Example_Counter_GHDL/_settings.yml" >}}
use_parameters: Yes
param_target_file: "tb/tb_counter.vhdl"
start_delimiter: "generic ("
stop_delimiter: "  );"
{{< /code >}}

### Metrics

Both testbenches run the same four checks — reset, increment, decrement, init — and write a flat YAML file that `_metrics.yml` maps key by key:

{{< code lang=yaml filename="simulations/TB_Example_Counter_Verilator/_metrics.yml" >}}
metrics:
  cycles:
    type: yaml
    settings:
      file: results.yml
      key: cycles
    unit: "cycles"
    format: "%.0f"

  checks_passed:
    type: yaml
    settings:
      file: results.yml
      key: checks_passed
    format: "%.0f"

  status:
    type: yaml
    settings:
      file: results.yml
      key: status
{{< /code >}}

The reported metrics are `cycles`, the check counters `checks_total` / `checks_passed` / `checks_failed`, the per-check verdicts `reset`, `increment`, `decrement`, and the overall `status` (`OK` / `KO`).

Writing the file from the testbench, in both C++ and VHDL, is a deliberate choice: the testbench is the only place that knows what is worth reporting, and a structured file survives changes in log formatting.

{{< code lang=cpp filename="simulations/TB_Example_Counter_Verilator/tb/tb_counter.cpp" >}}
yaml << "cycles: " << cycles << std::endl;
yaml << "checks_total: " << checks.size() << std::endl;
yaml << "checks_passed: " << passed << std::endl;
yaml << "checks_failed: " << (int(checks.size()) - passed) << std::endl;
yaml << "status: " << (passed == int(checks.size()) ? "OK" : "KO") << std::endl;
{{< /code >}}

The simulation entries are present but commented out in `simulations_settings.yml`; uncomment them and run:

{{< code lang=shell prompt=true >}}
$ odatix sim
{{< /code >}}

## Where to go next

- [Cordic](/docs/examples/architectures/cordic/) — the same ideas, with two independent parameter domains and four simulators.
- [Multiplier & Shift Register](/docs/examples/architectures/mult_shift_register/) — two more one-parameter designs, whose curves are worth comparing against the counter's.
- [Virtual parameter domains](/docs/configurations/virtual_param_domains/) — the mechanism behind `Example_Counter_chisel_cli`.
- [All architecture examples](/docs/examples/architectures/) — the six designs and what each one adds.
