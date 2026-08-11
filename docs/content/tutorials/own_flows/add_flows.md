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

Your team has a Tcl script that turns on retiming before synthesis, and you want
to know what it actually buys you across a whole design space. You do **not**
want a new tool: Vivado already works, its metrics are already defined, its
targets are already set up. You want another **flow** — another way of running
it, so Odatix runs both and lets you compare them.

That is a ten-minute job. Here it is, twice: with the GUI, and by hand.

> [!NOTE]
> You need Odatix installed ([installation guide](/install/)) and a working
> workspace (`odatix init --examples` is enough). This tutorial uses Vivado, but
> any built-in tool works the same — including `dummy`, which needs no licence.

## Step 1 — Write the script your flow will run

A flow is only useful if it runs something different. Put your script in the
workspace tool directory of Vivado, in a `tcl/` sub-directory:

{{< code lang=tcl filename="odatix_userconfig/tools/vivado/tcl/flow_retiming.tcl" >}}
# Enable global retiming for this run
set_property STEPS.SYNTH_DESIGN.ARGS.RETIMING true [get_runs synth_1]
puts "<green>retiming enabled<end>"
{{< /code >}}

Odatix copies **both** the built-in Vivado scripts and yours into every job
directory, yours last. So your script sits right next to Odatix's own ones and
can `source` them.

## Step 2 — Declare the flow

{{< tabs >}}
{{% tab name="With the GUI" %}}
{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-gui
{{< /code >}}

1. Open **EDA Tools**. Vivado is in the **Built-in tools** row.
2. Click **Settings** on its card. The flows Odatix ships are shown, locked —
   they belong to Odatix and cannot be changed.
3. Click **Add a flow**. Name it `retiming`, give it the label
   *"Retiming"* and a one-line description; both are what you will see on the
   tool's card when launching a run.
4. In the flow's **Unix / Linux** section, find **Custom frequency synthesis**
   and pick **Steps**. The steps of the standard flow are inherited: keep
   `pnr` and `bitstream` as they are, and edit only the `synthesis` step to
   insert your script:

   {{< code lang=text filename="synthesis step — one argument per line" >}}
export LC_ALL=C; unset LANGUAGE;
vivado -mode tcl -notrace
-log $log_path/synthesis.log
-source $script_path/init_script.tcl
-source $script_path/flow_retiming.tcl
-source $script_path/analyze_script.tcl
-source $script_path/step_synthesis.tcl
-source $script_path/exit.tcl
   {{< /code >}}

5. **Save**. The save button turns orange whenever there is something unsaved.

Vivado's card now reads **built-in + your changes**, and lists two flows.
{{% /tab %}}
{{% tab name="By hand" %}}
Create a `tool.yml` under Vivado's *workspace* directory. It holds nothing but
your flow — it is merged over the built-in definition, so everything else still
comes from Odatix:

{{< code lang=yaml filename="odatix_userconfig/tools/vivado/tool.yml" >}}
flows:
  retiming:
    label: "Retiming"
    description: "Timing oriented synthesis with global retiming enabled"
    unix:
      custom_freq_synthesis_steps:
        - name: synthesis          # "pnr" and "bitstream" are inherited
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

Two things are worth noticing:

- you redefine **one step**, not the whole flow. Steps are merged by name, so
  place & route and bitstream generation are inherited unchanged — which is
  correct, since they continue from the checkpoint the synthesis wrote;
- you declare nothing about `fmax_synthesis`, so `odatix fmax -f retiming` runs
  Vivado's standard fmax search. Add a `fmax_synthesis_steps` entry when you
  want the search itself to use retiming.
{{% /tab %}}
{{< /tabs >}}

> [!WARNING]
> You cannot redefine a **built-in** flow — Odatix drops those keys and warns
> you, so that `vivado / standard` means the same thing in every workspace. Give
> your flow a new name (as above), or duplicate the whole tool from the GUI to
> own all of it.

## Step 3 — Check that Odatix sees it

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth --tool vivado --flow nope
{{< /code >}}

The error lists the flows able to run the job — `standard`, `power_opt`,
`retiming`. That is the quickest way to confirm your YAML parsed and your flow
name is valid.

## Step 4 — Run both

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth --tool vivado                      # the standard flow
$ odatix synth --tool vivado --flow retiming      # yours
{{< /code >}}

From the GUI, both are buttons on Vivado's card on the **Select an EDA Tool**
page, and a run starts in one click.

Each flow runs in its own work directory — `work/custom_freq_synthesis/vivado/`
and `work/custom_freq_synthesis/vivado@retiming/` — so nothing overwrites
anything, and the two can run in the same session.

## Step 5 — Stop where it is worth stopping

Your flow inherited Vivado's steps, so it is stoppable and resumable like any
other:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth -t vivado -f retiming --until synthesis   # post-synthesis estimates only
$ odatix synth -t vivado -f retiming --until pnr         # implement the ones worth it
$ odatix synth -t vivado -f retiming                     # bitstreams, at last
{{< /code >}}

A later run picks up at the first step left to do instead of redoing everything.
Screen the whole design space cheaply, then carry only the interesting part
further.

## Step 6 — Compare them

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix-explorer
{{< /code >}}

Both flows exported into Vivado's single results file, told apart by the `flow`
key. Use it as a color or a series in any chart and you are looking at exactly
what your script changed, on every configuration at once.

## Next steps

- The full reference: [Run your own flows and scripts](/docs/custom_tools/add_flows/)
- No tool to attach a flow to? [Add an unsupported tool](/tutorials/own_flows/add_tools/)
- [Commands](/docs/commands/#selecting-a-flow) · [Configuration reference](/docs/reference/tools/)
