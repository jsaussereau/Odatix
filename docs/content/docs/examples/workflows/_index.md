---
title: "Workflows"
description: "Nine workflow examples — no RTL, no EDA tool — sweeping Python scripts to show command placeholders, paired variables, platform-specific tasks, task dependencies and multi-row metrics."
weight: 2
---

# Workflow Examples

A [workflow](/docs/features/workflows/) is Odatix without the hardware: a directory of sources, a list of commands to run, and a way to read numbers out of whatever those commands produce. Same sweeps, same parallel job monitor, same result files and same [Explorer](/docs/features/explorer/) — but the thing being swept is a script rather than a design.

The nine shipped examples use throwaway Python — a string manipulator, a traffic model, a BER curve, a small neural network — because the interesting part is never the script. Each one isolates **one** workflow mechanism.

{{< details title="What these examples demonstrate" >}}
- **Task graphs** — `dependencies` between named tasks, and a `main` entry point.
- **Platform-specific tasks** — the same task name implemented once for Linux/macOS and once for PowerShell.
- **Command placeholders** — `${name}` in a command, filled from a configuration, a parameter domain, or a variable.
- **[Virtual parameter domains](/docs/configurations/virtual_param_domains/)** — sweeps declared as variables, with no directory behind them.
- **Paired variables** — values zipped together instead of cross-combined, so two parameters move as one.
- **[Metrics](/docs/results/) from JSON, CSV and regex** — and `operation` metrics computed from the others.
- **Multi-row metrics** — one run producing many result records, one per row of a CSV.
- **Environment bootstrapping** — a task that builds a virtualenv, with a fallback if it fails.
{{< /details >}}

{{< toc >}}

## The examples

{{< doc-cards cols="2" >}}
{{< doc-card title="Basic" link="/docs/examples/workflows/basic/" icon="workflow" accent="#ea580c" cta="Read the example" >}}
Task dependencies, progress reported from several steps, substitution into a source file, and regex metrics.
{{< /doc-card >}}

{{< doc-card title="Crossplatform" link="/docs/examples/workflows/crossplatform/" icon="server" accent="#0ea5e9" cta="Read the example" >}}
One task name, two implementations — Linux/macOS and PowerShell — with exactly one selected at run time.
{{< /doc-card >}}

{{< doc-card title="CLI Profile" link="/docs/examples/workflows/cli_profile/" icon="terminal" accent="#7c3aed" cta="Read the example" >}}
A command placeholder filled with the content of the selected configuration file, with nothing written into any source.
{{< /doc-card >}}

{{< doc-card title="Parameter domains on the command line" link="/docs/examples/workflows/param_domains_cli/" icon="domains" accent="#2563eb" cta="Read the example" >}}
Four independent parameter domains, four placeholders in one command, sixteen runs.
{{< /doc-card >}}

{{< doc-card title="Parameter domains as variables" link="/docs/examples/workflows/param_domains_cli_variables/" icon="virtual" accent="#0d9488" cta="Read the example" >}}
The same sweep declared as virtual parameter domains — twenty lines of YAML and not one configuration file.
{{< /doc-card >}}

{{< doc-card title="Paired variables" link="/docs/examples/workflows/param_domains_paired_variables/" icon="variables" accent="#16a34a" cta="Read the example" >}}
Two variables describing the same scenario, zipped together with a `group` label instead of cross-combined.
{{< /doc-card >}}

{{< doc-card title="Parameter domains in a JSON file" link="/docs/examples/workflows/param_domains_json/" icon="code" accent="#f59e0b" cta="Read the example" >}}
A script driven by a configuration file instead of flags — each domain substitutes its value into the JSON.
{{< /doc-card >}}

{{< doc-card title="Metric sweep" link="/docs/examples/workflows/metric_sweep/" icon="chart" accent="#db2777" cta="Read the example" >}}
One run, many result rows: multi-row CSV metrics, `metadata` to tell them apart, and `operation` metrics per row.
{{< /doc-card >}}

{{< doc-card title="TensorFlow training" link="/docs/examples/workflows/tensorflow/" icon="activity" accent="#9333ea" cta="Read the example" >}}
A generated sweep over epochs, a dependency task that bootstraps a virtualenv once, and `on_failure_commands`.
{{< /doc-card >}}
{{< /doc-cards >}}

## At a glance

| Workflow | Isolates | Sources |
|---|---|---|
| [`basic`](/docs/examples/workflows/basic/) | task dependencies, source substitution, regex metrics | `workflow_simple` |
| [`crossplatform`](/docs/examples/workflows/crossplatform/) | platform-specific task implementations | `workflow_simple` |
| [`cli_profile`](/docs/examples/workflows/cli_profile/) | placeholders filled from the workflow configuration | `workflow_cli_profile` |
| [`param_domains_cli`](/docs/examples/workflows/param_domains_cli/) | parameter domains into command placeholders | `workflow_param_domains_cli` |
| [`param_domains_cli_variables`](/docs/examples/workflows/param_domains_cli_variables/) | the same, as virtual domains | `workflow_param_domains_cli` |
| [`param_domains_paired_variables`](/docs/examples/workflows/param_domains_paired_variables/) | paired (grouped) variables | `workflow_param_domains_cli` |
| [`param_domains_json`](/docs/examples/workflows/param_domains_json/) | substitution into a config file instead of a command | `workflow_param_domains_json` |
| [`metric_sweep`](/docs/examples/workflows/metric_sweep/) | multi-row metrics, `operation` metrics, metadata | `workflow_metric_sweep` |
| [`tensorflow`](/docs/examples/workflows/tensorflow/) | environment bootstrapping, `on_failure_commands` | `workflow_tensorflow` |

## Running them

{{< doc-card title="Tutorials" link="/tutorials/run_examples/" icon="tutorial" accent="#0d9488" cta="Browse the tutorials" >}}
Step-by-step instructions to run the examples, and understand how Odatix works.
{{< /doc-card >}}
