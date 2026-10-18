---
title: "Add your own flows"
date: 2026-05-15
author: "Jonathan Saussereau"
weight: 1
description: "Add a way of your own to run a tool Odatix already ships — with the GUI or with a ten-line YAML file — and compare it against the standard one."
categories: ["Tutorial", "EDA Tools"]
tags: ["flows", "tools", "vivado"]
featured_image: "/images/tutorials/add-flows.svg"
---

{{< toc >}}

A **flow** is one way of running a tool: a strategy, other options, sometimes
other scripts. Vivado ships five of them (standard, runtime, performance, area,
power). This tutorial adds a sixth, which turns on global retiming during
synthesis, runs a design through both the standard flow and the new one, and
compares them in Odatix Explorer. Then it adds a flow that runs a script of your
own.

Everything can be done three ways, which read and write the same files:

| | |
|---|---|
| **Graphical interface** | `odatix-gui`, in the Tool Editor. |
| **YAML files** | A few lines in `odatix_userconfig/tools/vivado/tool.yml`. |
| **Python API** | `odatix.workspace`, for a workspace built by a script. |

## What a flow is

Flows of a tool are **alternatives meant to be compared**. Each one runs in a
work directory of its own (`work/custom_freq_synthesis/vivado@retiming/…`), and
tags its results with its name (`flow: retiming`), so two flows of the same
design sit side by side in the results.

Most flows are a **strategy**: the same scripts, other options. The scripts of
the built-in Vivado tool read their options from **parameters**, declared at the
top of its `tool.yml`:

| Parameter | Default | Used for |
|-----------|---------|----------|
| `synth_options` | `[-flatten_hierarchy, full]` | `synth_design` |
| `opt_passes` | two `opt_design` passes | after synthesis |
| `power_opt` | `false` | `power_opt_design` |
| `place_options`, `phys_opt_passes`, `route_options`, `post_route_passes` | | implementation |

A flow changes only the parameters it names, and inherits the rest. A new
strategy is therefore a few lines, never a copy of the tool.

The flows of a built-in tool are **read-only**: you add flows of your own next
to them, without touching what Odatix ships. That is what makes a result tagged
`vivado / standard` mean the same thing in every workspace.

## Prerequisites

- A workspace with the examples, created by `odatix init --examples`.
- Vivado on your `PATH`, and the target of `target_vivado.yml` it uses enabled
  (see [Add targets](/tutorials/own_flows/add_targets/)).

## Step 1 — Add a strategy

Add a flow `retiming`: the standard flow, with `-retiming` added to the options
of `synth_design`.

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

Start `odatix-gui`, open **Configure** → **Tools**, and click **Settings** on the
**Vivado** card. The Tool Editor shows the flows of Vivado, locked: they are
Odatix's.

1. Click **Add a flow**. A new flow card opens at the end of the list.
2. Name it `retiming`, with the label `Retiming`.
3. Its **Parameters** panel lists the parameters it inherits from the default
   flow. Click **Override** on `synth_options`, and set its value, one item per
   line:

{{< code lang=text filename="synth_options" >}}
-flatten_hierarchy
full
-retiming
{{< /code >}}

4. Click **Save all**.

{{% /tab %}}
{{% tab name="YAML files" %}}

Create a `tool.yml` for Vivado in the workspace, holding nothing but the new
flow:

{{< code lang=yaml filename="odatix_userconfig/tools/vivado/tool.yml" >}}
flows:
  retiming:
    label: "Retiming"
    description: "Standard, with global retiming during synthesis"
    parameters:
      synth_options: [-flatten_hierarchy, full, -retiming]
{{< /code >}}

This file is merged over the built-in Vivado: the tool keeps its commands, its
scripts, its metrics and its other flows.

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="add_flow.py" >}}
from odatix.workspace import Workspace

ws = Workspace.open()
vivado = ws.tools["vivado"]
flow = vivado.settings.add_flow("retiming", label="Retiming",
                                description="Standard, with global retiming during synthesis")
flow.parameters = {"synth_options": ["-flatten_hierarchy", "full", "-retiming"]}
vivado.save()
{{< /code >}}

`save()` writes only what the workspace adds to the built-in tool. Changing one
of the built-in flows is refused with a `ValueError`: they are read-only.

{{% /tab %}}
{{< /tabs >}}

The new flow appears on the Vivado card of the run pages, with a **custom**
badge. On the command line, a flow Vivado does not have is refused, with the
list of those it has:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t vivado -f retimin
[odatix synth] error: The EDA tool "vivado" has no flow named "retimin"
[odatix synth] note: Flows of "vivado" able to run fixed-frequency synthesis: standard, runtime, performance, area, power_opt, retiming
{{< /code >}}

## Step 2 — Run both flows

Run the same design through the standard flow and the new one. Vivado runs a
fixed-frequency synthesis in steps (`elaboration`, `synthesis`, `pnr`,
`bitstream`): stopping after `synthesis` is enough to compare what the strategy
changes there.

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

Open **Run** → **Fixed-frequency synthesis**. The Vivado card lists its flows:
pick **Standard** and stop at **synthesis**. Then select `Example_Counter_verilog` and, in its **Preview**, untick every configuration
but `08bits`. Turn on **Override frequencies**, type `100` in **Target
frequencies (MHz)**, click **Run jobs**, then **Start** in the popup once the
check is done. Then do the same with **Retiming**.

Hovering a flow of the card shows its steps: clicking one runs up to it.

{{% /tab %}}
{{% tab name="YAML files" %}}

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t vivado -a Example_Counter_verilog/08bits --at 100 --until synthesis
$ odatix synth -t vivado -f retiming -a Example_Counter_verilog/08bits --at 100 --until synthesis
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="run_flows.py" >}}
from odatix.run import Run

for flow in ("standard", "retiming"):
    run = Run(ws, "custom_freq_synthesis", tool="vivado", flow=flow, until="synthesis",
              architectures=["Example_Counter_verilog/08bits"], frequencies=[100])
    run.start()
    for job in run.wait():
        print(flow, job["name"], job["status"])
    run.session.stop()  # each run has its session, which stays open otherwise
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

The log of the retiming job shows the option the flow added:

{{< code lang=text filename="work/custom_freq_synthesis/vivado@retiming/.../log/console.log" >}}
[step_synthesis.tcl] synth_design -part xc7a100t-csg324-1 -top counter -verilog_define VIVADO -flatten_hierarchy full -retiming
{{< /code >}}

## Step 3 — Compare them

Both jobs export into `results/results_vivado.yml`, one record per step, told
apart by `flow`:

{{< code lang=yaml filename="results/results_vivado.yml" >}}
- meta:
    tool: vivado
    flow: retiming
    step: synthesis
    ...
{{< /code >}}

Start `odatix-explorer`. **Flow** is a dimension like **Target** or
**Configuration**: color a chart by flow, or filter the table on it, and the two
strategies of the same design are side by side. On a design as small as the
example counter, the two flows give the same numbers: compare them on a design
whose critical path retiming can shorten.

To implement the two of them, run again without `--until`: each job picks up
after `synthesis`, and stops at `pnr`, the default step of Vivado.

## Step 4 — A flow running a script of your own

When options are not enough, a flow runs scripts of your own. Here, a flow
`retiming_script` replaces the `synthesis` step of Vivado: it sources a script
of yours, then the step script of Odatix. The other steps are inherited.

{{< tabs groupId="how" >}}
{{% tab name="Graphical interface" %}}

In the Tool Editor of Vivado, **Add a flow** named `retiming_script`. Under
**Unix / Linux** → **Fixed-frequency synthesis**, choose **Steps** and add a
step `synthesis` whose command is the one of the YAML tab, one fragment per
line. **Save all**.

Scripts are not edited in the GUI: create `tcl/flow_retiming.tcl` in
`odatix_userconfig/tools/vivado/`, the directory the Tool Editor saves to.

{{% /tab %}}
{{% tab name="YAML files" %}}

Add the flow next to the first one:

{{< code lang=yaml filename="odatix_userconfig/tools/vivado/tool.yml" >}}
flows:
  retiming_script:
    label: "Retiming (script)"
    unix:
      custom_freq_synthesis_steps:
        - name: synthesis
          command:
            - export LC_ALL=C; unset LANGUAGE;
            - vivado -mode tcl -notrace
            - -log $log_path/synthesis.log
            - -source $script_path/init_script.tcl
            - -source $script_path/flow_retiming.tcl
            - -source $script_path/analyze_script.tcl
            - -source $script_path/step_synthesis.tcl
            - -source $script_path/exit.tcl
{{< /code >}}

{{% /tab %}}
{{% tab name="Python API" %}}

{{< code lang=python filename="add_flow.py" >}}
flow = vivado.settings.add_flow("retiming_script", label="Retiming (script)")
flow.set_steps("custom_freq_synthesis", [{
    "name": "synthesis",
    "command": [
        "export LC_ALL=C; unset LANGUAGE;",
        "vivado -mode tcl -notrace",
        "-log $log_path/synthesis.log",
        "-source $script_path/init_script.tcl",
        "-source $script_path/flow_retiming.tcl",
        "-source $script_path/analyze_script.tcl",
        "-source $script_path/step_synthesis.tcl",
        "-source $script_path/exit.tcl",
    ],
}])
vivado.save()
{{< /code >}}

{{% /tab %}}
{{< /tabs >}}

And the script, in the `tcl/` directory of the workspace Vivado:

{{< code lang=tcl filename="odatix_userconfig/tools/vivado/tcl/flow_retiming.tcl" >}}
# Sourced before step_synthesis.tcl: options added to synth_design
puts "flow_retiming.tcl: synthesis with global retiming"
set ::odatix_synth_options [list -retiming]
{{< /code >}}

Both `tcl/` directories, Odatix's and yours, are copied into the `scripts/`
directory of every job, yours last: `flow_retiming.tcl` sits next to Odatix's
scripts and can source them.

Steps are merged **by name**: this flow redefines `synthesis`, and inherits
`elaboration`, `pnr` and `bitstream` as they are. Run it like the others:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t vivado -f retiming_script -a Example_Counter_verilog/08bits --at 100 --until synthesis
{{< /code >}}

## Common mistakes

| Symptom | Cause |
|---------|-------|
| `Ignoring what '.../tools/vivado/tool.yml' says about the built-in flow "standard"` | The workspace file redefines a flow Odatix ships. Give yours another name. |
| `The EDA tool "vivado" has no flow named ...` | A typo in `-f`, or the flow is in a file Odatix does not read (`tools_path` of `odatix.yml`). |
| The new flow gives the same results | The strategy changes nothing on this design, or the parameter is not one the scripts read: see the top of the built-in `tool.yml`. |
| A script of the flow is not found | It is not in `odatix_userconfig/tools/vivado/tcl/`. |
| `ValueError` from `save()` | The script changed a built-in flow: add a flow of your own instead. |

To own all of a built-in tool, its flows included, duplicate it under another
name (**Duplicate** on its card, or `ws.tools.import_builtin("vivado", "my_vivado")`):
the copy is a tool of its own, with nothing read-only left.

## Next steps

- [Add unsupported tools](/tutorials/own_flows/add_tools/) — flows work the same
  on a tool of your own.
- [Design space exploration](/docs/reference/dse/) — let a search choose between
  flows, targets and configurations.

## Related resources

- **Reference** — [Run your own flows and scripts](/docs/tools/add_flows/): flows,
  steps, sessions, parameters, one record per step.
- **Reference** — [Tool definitions](/docs/reference/tools/).
