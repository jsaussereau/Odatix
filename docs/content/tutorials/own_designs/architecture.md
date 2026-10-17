---
title: "Implement your own RTL architectures"
date: 2026-05-15
author: "Jonathan Saussereau"
weight: 1
description: "Add an existing RTL design, configurations and a target to an Odatix workspace."
categories: ["Tutorial", "Design"]
tags: ["synthesis", "own design"]
featured_image: "/images/tutorials/own-rtl.svg"
---

{{< toc >}}

This tutorial takes an RTL design you already have — Verilog, VHDL,
SystemVerilog, or something that *generates* them like Chisel or HLS — and turns
it into an Odatix **architecture**: a design Odatix can synthesize, place &
route and simulate, in as many parameter variants as you want.

Everything here can be done three ways, and they are strictly equivalent because
they all read and write the same files:

| | |
|---|---|
| **Graphical interface** | `odatix-gui`, form by form. The default, and the fastest way to get the first design right. |
| **YAML files** | One directory, one `_settings.yml`, one file per configuration. What the GUI writes. |
| **Python API** | `odatix.workspace`, for a workspace built by a script. |

Each step below has the three versions in tabs. Pick the one you like; you can
switch at any time, even in the middle of a design.

> [!TIP]
> The GUI is the fastest and recommended way to get started. Writing the YAML files directly is useful when you work on a headless server without external ports available to access the GUI from another computer. The API approach is reserved to advanced users wanting to automate their Odatix workspace.

## What an architecture is

An architecture is a **directory** in `odatix_userconfig/architectures/`. It
holds one `_settings.yml` saying where your sources are, what is your top level, what is your clock signal, ...

> [!NOTE] 
> An architecure in Odatix can be **configurable**, meaning that some or all of the parameters of you design can be replaced by specific value. These values can be defined from **rules** or manually in **configuration files**. Each configuration is a variant of the design, and Odatix can run them all in parallel.

{{< code lang=text filename="An architecture directory" >}}
odatix_userconfig/architectures/MyCounter/
├── _settings.yml     # where the sources are, and how parameters are replaced
├── 08bits.txt        # a configuration
├── 16bits.txt        # another one
└── 32bits.txt        # ...
{{< /code >}}

Your RTL itself stays where it is: Odatix never modifies your sources. For each
job, it copies them into a work directory and applies the parameters of one
configuration there.

{{< code lang=text filename="What a job does" >}}
your sources ──copy──► work directory ──replace parameters──► synthesis / P&R / simulation
{{< /code >}}

## Prerequisites

- [Odatix installed](/install/) and available in your `PATH`.
- An Odatix workspace. Create one in the directory of your choice with:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir ~/my_project && cd ~/my_project
$ odatix init
{{< /code >}}

- An RTL design with **one top level module**, a clock and a reset.

No EDA tool is needed to follow this tutorial: the last step checks the setup
without running any synthesis.

Throughout, the example is this small counter, in `~/my_project/rtl/counter.v`:

{{< code lang=verilog filename="rtl/counter.v" linenos="true" >}}
module counter #(
  parameter BITS = 8
)(
  input  wire            clock,
  input  wire            reset,
  input  wire            i_init,
  input  wire            i_inc_dec,
  output wire [BITS-1:0] o_value
);
  reg [BITS-1:0] value;
  always @(posedge clock) begin
    if (reset)       value <= 0;
    else if (i_init) value <= 0;
    else             value <= i_inc_dec ? value + 1 : value - 1;
  end
  assign o_value = value;
endmodule
{{< /code >}}

## Step 1 — Create the architecture

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

Start the GUI from your workspace:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui
{{< /code >}}

Open **RTL Architectures** from the home page, then click the
**Create New Architecture** card. Name it `MyCounter` — this name is how the
design is selected in every run afterwards.

You land on the **Architecture Editor**, the page the next steps fill in.

{{% /tab %}}
{{% tab name="YAML files" %}}

Create the directory and its settings file:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ mkdir -p odatix_userconfig/architectures/MyCounter
$ touch odatix_userconfig/architectures/MyCounter/_settings.yml
{{< /code >}}

The directory name — `MyCounter` — is how the design is selected in every run
afterwards.

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="setup.py" >}}
from odatix.workspace import Workspace

ws = Workspace.open()                          # the workspace of the current directory
architecture = ws.architectures.create("MyCounter")
architecture.save()
{{< /code >}}

`Workspace.open()` reads `odatix.yml`, so nothing else in the script takes a
path. `create()` returns the architecture; `save()` writes its `_settings.yml`.

{{% /tab %}}
{{< /tabs >}}

## Step 2 — Describe the sources

Five settings are all Odatix needs to build your design:

| Setting | What it is |
|---------|------------|
| `rtl_path` | The directory holding your sources. It is copied whole into every job. |
| `top_level_file` | The top level source file, **relative to `rtl_path`**. |
| `top_level_module` | The name of the top level module or entity. |
| `clock_signal` | The name of the main clock, used to write the timing constraint. |
| `reset_signal` | The name of the main reset. |

> [!IMPORTANT]
> `rtl_path` is a directory, not a file: put **every** source your design needs
> inside it (packages, submodules, includes). Paths are relative to the root of
> the workspace.

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

In the **Top Level Settings** section of the Architecture Editor, fill in:

| Field | Value |
|-------|-------|
| RTL Path | `rtl` |
| Top Level File | `counter.v` |
| Top Level Module | `counter` |
| Clock Signal | `clock` |
| Reset Signal | `reset` |

Then click **Save** in the header. The save button turns to a warning colour
whenever something is unsaved, so you always know whether what you see is on
disk.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=yaml filename="architectures/MyCounter/_settings.yml" >}}
# Source files
rtl_path: "rtl"
top_level_file: "counter.v"     # relative to rtl_path
top_level_module: "counter"

# Signals
clock_signal: "clock"
reset_signal: "reset"
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="setup.py" >}}
architecture.settings.rtl_path = "rtl"
architecture.settings.top_level_file = "counter.v"
architecture.settings.top_level_module = "counter"
architecture.settings.clock_signal = "clock"
architecture.settings.reset_signal = "reset"
architecture.save()
{{< /code >}}

Settings are typed and are also mappings, so `architecture.settings["rtl_path"]`
says the same thing. Saving keeps the comments, the key order and the unknown
keys of a file that already exists.

{{% /tab %}}
{{< /tabs >}}

At this point the design is complete enough to be synthesized — with one
configuration, the parameter values written in your sources. The next steps make
it parametrizable.

## Step 3 *(optional)* — Generate the RTL first

Skip this step if your sources are already Verilog, VHDL or SystemVerilog.

When the RTL does not exist yet and has to be produced from a higher-level
description — Chisel, HLS, an in-house generator — Odatix copies the
**description**, runs a command to produce the RTL, and only then synthesizes it.

| Setting | What it is |
|---------|------------|
| `design_path` | The directory copied into the work directory. Replaces `rtl_path`. |
| `generate_rtl` | Enables the generation flow. |
| `generate_command` | The command that produces the RTL. |
| `generate_output` | The directory the command writes its RTL to. `top_level_file` is relative to it. |

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

In the Architecture Editor, open the **RTL Generation** section and enable it.
Fill in **Design Path**, **Generation Command** and **Generation Output**; the
**Top Level File** of the previous step then names the file the command
produces.

The optional **Design Path Whitelist** / **Design Path Blacklist** fields
restrict what is copied, which is worth setting on a directory holding build
artefacts.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=yaml filename="architectures/MyALU/_settings.yml" >}}
design_path: "chisel/alu"       # copied instead of rtl_path

generate_rtl: Yes
generate_command: "sbt 'runMain ALUTop --o=rtl'"
generate_output: "rtl"

top_level_file: "ALUTop.sv"     # relative to generate_output
top_level_module: "ALUTop"
clock_signal: "clock"
reset_signal: "reset"
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="setup.py" >}}
architecture.settings.design_path = "chisel/alu"
architecture.settings.generate_rtl = True
architecture.settings.generate_command = "sbt 'runMain ALUTop --o=rtl'"
architecture.settings.generate_output = "rtl"
architecture.settings.top_level_file = "ALUTop.sv"
architecture.save()
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

> [!IMPORTANT]
> With `generate_rtl`, the parameters of the next step cannot be replaced in the
> top level: it does not exist yet when the replacement happens. They must
> target the **source** that produces it, with `param_target_file` — see the note
> at the end of Step 4.

## Step 4 — Mark the parameter section

This is the heart of Odatix, and it is deliberately simple. You mark a section
of a source file with two pieces of text — a **start delimiter** and a **stop
delimiter** — and each configuration provides the text that goes between them.
The delimiters themselves are kept.

For the counter, the section to vary is the parameter list, between
`counter #(` and `)(`:

{{< code lang=verilog filename="rtl/counter.v" >}}
module counter #(
  parameter BITS = 8      // <-- this line is what a configuration replaces
)(
{{< /code >}}

so the delimiters are:

| Setting | Value |
|---------|-------|
| `start_delimiter` | `counter #(` |
| `stop_delimiter` | `)(` |

and a configuration file holds nothing but the replacement text:

{{< code lang=verilog filename="architectures/MyCounter/16bits.txt" >}}
  parameter BITS = 16
{{< /code >}}

> [!TIP]
> Pick delimiters that appear **once** in the file. `#(` alone would match every
> instantiation; `counter #(` matches only the top level's own parameter list.
> When nothing convenient exists, add a comment of your own around the section
> — `// <params>` / `// </params>` — which works in every language and can never
> be ambiguous.

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

On the **RTL Architectures** page, click **Edit Configs** on the `MyCounter`
card. The **Configuration Editor** opens on the **Main parameter domain**.

In the **Configuration Parameters** panel:

1. Tick **Enable parameter replacement**.
2. Leave **Param Target File** empty — the top level file is used by default.
3. Set **Start Delimiter** to `counter #(` and **Stop Delimiter** to `)(`.
4. Click **Save**.

The **Preview Pane** on the right shows the target file with the selected
configuration spliced in, so a wrong delimiter is visible immediately instead of
at the end of a synthesis.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=yaml filename="architectures/MyCounter/_settings.yml" >}}
# Delimiters for parameter files
use_parameters: Yes
start_delimiter: "counter #("
stop_delimiter: ")("
{{< /code >}}

| Key | What it is |
|-----|------------|
| `use_parameters` | Enables the replacement. Set it to `No` for a design with a single, fixed configuration. |
| `start_delimiter` | Text marking the start of the replaced block. |
| `stop_delimiter` | Text marking its end. |
| `param_target_file` | The file the replacement is applied to. Defaults to the top level. |

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="setup.py" >}}
architecture.settings.use_parameters = True
architecture.settings.start_delimiter = "counter #("
architecture.settings.stop_delimiter = ")("
architecture.save()
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

> [!NOTE]
> **Generated RTL (Step 3):** set `param_target_file` to the source the command
> reads — for instance `src/main/scala/ALUTop.scala` — with delimiters taken
> from *that* file (`new ALUTop(` / `)`). It is mandatory there.

## Step 5 — Describe the configurations

There are three ways to say which variants of the design exist. They are not
alternatives to choose once and for all: start with the first, move to the
others when the list gets long.

### A. One file per configuration

The direct way: one file, one variant, holding the exact replacement text. The
file name — without `.txt` — is the configuration name.

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

In the Configuration Editor, click the **add** card of the main parameter
domain, name the configuration `08bits`, and type its content:

{{< code lang=verilog filename="08bits" >}}
  parameter BITS = 8
{{< /code >}}

Repeat for `16bits` and `32bits`, then **Save**. Selecting a configuration
updates the Preview Pane with the file as the job would see it.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ cd odatix_userconfig/architectures/MyCounter
$ echo "  parameter BITS = 8"  > 08bits.txt
$ echo "  parameter BITS = 16" > 16bits.txt
$ echo "  parameter BITS = 32" > 32bits.txt
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="setup.py" >}}
for bits in (8, 16, 32):
    architecture.configs.write(f"{bits:02}bits", f"  parameter BITS = {bits}\n")

architecture.configs.names()          # ['08bits', '16bits', '32bits']
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

### B. A rule that describes them all

When the values follow a pattern — a range, powers of two, a list — describe the
**rule** instead of writing the files. Odatix resolves it when a run starts;
nothing has to be written to disk.

A rule is made of a **variable** (the values), a **configuration name** (how each
variant is named) and a **content template** (what it writes between the
delimiters):

{{< code lang=text filename="From a rule to configurations" >}}
variable width = 8, 16, 32       name: "${width}bits"      08bits, 16bits, 32bits
                            ──►  template:              ──►  "parameter BITS = 8"
                                 "  parameter BITS = ${width}"   ...
{{< /code >}}

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

In the Configuration Editor, in the **Variables** panel of the main parameter
domain:

1. Click the **add variable** card, name it `width`, choose the type
   **power_of_two**, and set `from` to 8 and `to` to 32.
2. Open **Advanced**, next to the delimiters, and set:
   - **Configuration name**: `${width}bits`
   - **Content template**: `  parameter BITS = ${width}`
3. Click **Save rules**.

The configurations the rule describes appear straight away among the
configurations of the domain, with a counter next to the panel title saying how
many there are. Each can be previewed like a hand-written one, and excluded with
its card button — which blacklists it rather than deleting anything.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=yaml filename="architectures/MyCounter/_settings.yml" >}}
configurations:
  name: "${width}bits"
  template: "  parameter BITS = ${width}"

variables:
  width:
    type: power_of_two
    settings:
      from: 8
      to: 32
{{< /code >}}

This describes `8bits`, `16bits` and `32bits`. Describing configurations is what
asks for them: there is no flag to turn on, and the files do not have to exist.

Other variable types — `range`, `list`, `bool`, `multiples`, `function`,
`conversion`, `format` — are on the [Variables](/docs/configurations/variables/)
page. `configurations.constraints` rejects combinations that make no sense, and
`configurations.blacklist` excludes a generated name.

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="setup.py" >}}
architecture.settings.configurations.name = "${width}bits"
architecture.settings.configurations.template = "  parameter BITS = ${width}"
architecture.settings.set_variable("width", "power_of_two", {"from": 8, "to": 32})
architecture.save()

architecture.preview_configurations()   # {name: content}, writes nothing
architecture.generate_configurations()  # optional: write them out as files
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

### C. Several independent parameters

When parameters are **independent** — a data width *and* a multiplier type *and*
a memory depth — do not write one file per combination. Give each parameter its
own **parameter domain**: a sub-directory of the architecture with its own
delimiters, replacing its own block of the file. Odatix then runs every
combination, named `A+B`.

{{< code lang=text filename="An architecture with two domains" >}}
architectures/MyCPU/
├── _settings.yml
├── 32bits.txt          ◄── main domain: the parameter list
├── 64bits.txt
└── Mul/                ◄── a parameter domain: the multiplier
    ├── _settings.yml
    ├── Fast.txt
    └── Off.txt
                        ──►  32bits+Fast, 32bits+Off, 64bits+Fast, 64bits+Off
{{< /code >}}

Each domain must replace a **distinct** block of the target file:

{{< code lang=verilog filename="rtl/cpu.sv" >}}
  // <mul>
  parameter MUL = "fast",
  // </mul>
{{< /code >}}

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

In the Configuration Editor, click the **add parameter domain** card, name it
`Mul`, and fill in its delimiters (`  // <mul>` and `  // </mul>`) exactly as
for the main domain. Add its configurations, or give it a rule — a domain
sweeping a single variable needs no name or template at all: its configurations
are named after the values.

Each domain of the architecture is one section of the page, so the whole design
space is readable at a glance.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=yaml filename="architectures/MyCPU/Mul/_settings.yml" >}}
start_delimiter: "  // <mul>"
stop_delimiter: "  // </mul>"
{{< /code >}}

Everything else — sources, top level, clock — is inherited from the
architecture. Then add `Mul/Fast.txt` and `Mul/Off.txt`, or a `configurations`
rule scoped to the domain.

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="setup.py" >}}
mul = architecture.domains.create("Mul")
mul.settings.start_delimiter = "  // <mul>"
mul.settings.stop_delimiter = "  // </mul>"
mul.save()

mul.configs.write("Fast", '  parameter MUL = "fast",\n')
mul.configs.write("Off",  '  parameter MUL = "off",\n')

architecture.combinations()          # what a run would sweep
architecture.count_combinations()
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

## Step 6 — Check the replacement before running anything

A wrong delimiter is the one mistake worth catching early, because it only shows
up as a syntax error at the end of an expensive synthesis.

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

The **Preview Pane** of the Configuration Editor already did it: it shows the
target file with the selected configuration spliced in. Click through the
configurations and confirm that each one produces valid code, and that only the
intended block changed.

{{% /tab %}}
{{% tab name="YAML files" %}}

`odatix replace` applies exactly the same replacement as a job, outside of any
job:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix replace -s "counter #(" -S ")(" \
    -i rtl/counter.v \
    -r odatix_userconfig/architectures/MyCounter/16bits.txt \
    -o /tmp/counter_16bits.v
$ cat /tmp/counter_16bits.v
{{< /code >}}

If the configurations come from a rule, write them out to look at them:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix generate
{{< /code >}}

This is optional — a run resolves the rules on its own.

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="check.py" >}}
print(architecture.count_combinations())      # how many jobs a full sweep is
for name, content in architecture.preview_configurations().items():
    print(name, "->", content)
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

## Step 7 — Run it

Your design is now an architecture like any other, selected by
`<design>/<configuration>`, or with a `*` wildcard for all of its
configurations.

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

Go to **Run jobs**, pick a job type, a tool and a target, then select
`MyCounter/*` in the job settings, and run. You land on the **Monitor**.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=yaml filename="odatix_userconfig/fmax_settings.yml" >}}
architectures:
  - MyCounter/*
{{< /code >}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool vivado
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="run.py" >}}
from odatix.run import Run

ws.jobs.fmax_synthesis.settings.architectures = ["MyCounter/*"]
ws.jobs.fmax_synthesis.save()

run = Run(ws, "fmax_synthesis", tool="vivado")
plan = run.check()          # what would be run, having touched nothing
print(plan.counts())
run.start()
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

> [!IMPORTANT]
> Start with **one configuration and one target**. Confirm that it passes before
> enabling a large sweep or many parallel jobs.

Frequency bounds are worth setting once the design runs: `fmax_synthesis` for
the binary search, `fixed_freq_synthesis` for explicit frequency points, and
`overrides` for the targets that need different ones. See
[Architecture settings](/docs/reference/architecture/#frequency-settings).

## Common mistakes

| Symptom | Cause |
|---------|-------|
| A source file is missing at synthesis | It lives outside `rtl_path`. Everything the design needs must be inside that directory. |
| The replacement produced invalid code | The delimiters match somewhere else in the file, or the configuration text does not fit the block (a trailing comma, a missing one). Check it with the Preview Pane or `odatix replace`. |
| The top level file is not found | `top_level_file` is relative to `rtl_path` — or to `generate_output` in a generation flow — not to the workspace. |
| Nothing is replaced | `use_parameters` is off, or the configuration files are in the architecture directory but the delimiters are empty. |
| Two domains fight over the same lines | Each parameter domain must replace a **distinct** block of the target file. |
| Timing constraints look wrong | `clock_signal` does not name the actual top level clock port. |

## Next steps

- [Simulate your own RTL](/tutorials/own_designs/simulations/) — connect a
  testbench to the design you just added.
- [Create your own workflow](/tutorials/own_designs/workflows/) — turn an
  existing script into parallel, monitored, parameter-swept jobs.
- [Add tools](/tutorials/own_flows/add_tools/) and
  [add targets](/tutorials/own_flows/add_targets/) — run it on your own
  technology.

## Related resources

- **Reference** — [Architecture settings](/docs/reference/architecture/) — every key of `_settings.yml`.
- **Reference** — [Configurations](/docs/configurations/) — parameter files, domains, generation.
- **Reference** — [Variables](/docs/configurations/variables/) — every variable type.
- **Reference** — [Exclusions](/docs/configurations/exclusions/) — combinations that are not part of the design space.
- **Guide** — [The Odatix GUI](/docs/gui/app/) and [Python API](/docs/python_api/).
