---
title: "Workflows"
description: "Nine workflow examples — no RTL, no EDA tool — sweeping Python scripts to show command placeholders, paired variables, platform-specific tasks, task dependencies and multi-row metrics."
weight: 7
---

# Workflows

A [workflow](/docs/features/workflows/) is Odatix without the hardware: a directory of sources, a list of commands to run, and a way to read numbers out of whatever those commands produce. Same sweeps, same parallel job monitor, same result files and same [Explorer](/docs/features/explorer/) — but the thing being swept is a script rather than a design.

The nine shipped examples use throwaway Python — a string manipulator, a traffic model, a BER curve, a small neural network — because the interesting part is never the script. Each one isolates **one** workflow mechanism.

{{< details title="What these examples demonstrate" >}}
- **Task graphs** — `dependencies` between named tasks, and a `main` entry point.
- **Platform-specific tasks** — the same task name implemented once for Linux/macOS and once for PowerShell.
- **Command placeholders** — `${name}` in a command, filled from a configuration, a parameter domain, or a variable.
- **[Virtual parameter domains](/docs/configurations/virtual_param_domains/)** — sweeps declared as variables, with no directory behind them.
- **Paired variables** — values zipped together instead of cross-combined, so two parameters move as one.
- **[Metrics](/docs/metrics/) from JSON, CSV and regex** — and `operation` metrics computed from the others.
- **Multi-row metrics** — one run producing many result records, one per row of a CSV.
- **Environment bootstrapping** — a task that builds a virtualenv, with a fallback if it fails.
{{< /details >}}


{{< toc >}}

## The nine examples at a glance

| Workflow | Isolates | Sources |
|---|---|---|
| [`basic`](#basic--tasks-dependencies-and-source-substitution) | task dependencies, source substitution, regex metrics | `workflow_simple` |
| [`crossplatform`](#crossplatform--one-task-name-two-implementations) | platform-specific task implementations | `workflow_simple` |
| [`cli_profile`](#cli_profile--a-placeholder-filled-by-the-configuration-itself) | placeholders filled from the workflow configuration | `workflow_cli_profile` |
| [`param_domains_cli`](#param_domains_cli--four-parameter-domains-into-four-placeholders) | parameter domains into command placeholders | `workflow_param_domains_cli` |
| [`param_domains_cli_variables`](#param_domains_cli_variables--the-same-sweep-with-no-directories) | the same, as virtual domains | `workflow_param_domains_cli` |
| [`param_domains_paired_variables`](#param_domains_paired_variables--zipping-two-variables-together) | paired (grouped) variables | `workflow_param_domains_cli` |
| [`param_domains_json`](#param_domains_json--substituting-into-a-parameter-file) | substitution into a config file instead of a command | `workflow_param_domains_json` |
| [`metric_sweep`](#metric_sweep--one-run-many-result-rows) | multi-row metrics, `operation` metrics, metadata | `workflow_metric_sweep` |
| [`tensorflow`](#tensorflow--bootstrapping-an-environment) | environment bootstrapping, `on_failure_commands` | `workflow_tensorflow` |

All of them are declared in a single settings file:

{{< code lang=yaml filename="workflow_settings.yml" >}}
workflows:
  # Platform-specific task implementation example
  - crossplatform

  # Command placeholder example (main workflow config value)
  - cli_profile/default
  - cli_profile/aggressive

  # Multiple virtual parameter domains (variables) replaced in command placeholders
  - param_domains_cli_variables + max_speed/* + num_vehicles/* + signal_timing/* + road_length/*

  # Paired ("grouped") variables
  - param_domains_paired_variables + max_speed/* + road_length/* + num_vehicles/* + signal_timing/*

  # Multiple parameter domains replaced in command placeholders
  - param_domains_cli + max_speed/* + num_vehicles/* + signal_timing/* + road_length/*

  # Multiple parameter domains replaced in a json
  - param_domains_json + max_speed/* + num_vehicles/* + signal_timing/* + road_length/*

  # TensorFlow training workflow example
  - tensorflow + epochs/*
{{< /code >}}

and run with:

{{< code lang=shell prompt=true >}}
$ odatix workflow
{{< /code >}}

or one at a time, without editing the file:

{{< code lang=shell prompt=true >}}
$ odatix workflow -w "cli_profile/*"
{{< /code >}}

## The anatomy of a workflow

Every workflow settings file has the same four blocks:

{{< code lang=yaml filename="workflows/<name>/_settings.yml" >}}
# Design sources (that will be copied into each work directory)
sources:
  path: examples/workflow_param_domains_cli
  blacklist:
    - "*.log"

# Progress tracking
progress:
  file: progress.txt
  regex: "Progress: ([0-9]+)"

# Generated design settings
use_parameters: No

# Design workflow settings
tasks:
  - name: main
    commands:
      - python3 simulate_traffic.py --max_speed ${max_speed} ...
{{< /code >}}

- **`sources`** — the directory copied into each job's work directory, optionally filtered by `whitelist` / `blacklist`. Every job gets its own copy, so runs never interfere.
- **`progress`** — a file and a regex. Whatever the script writes there drives the percentage in the job monitor.
- **`use_parameters`** — whether a value is substituted into a source file, exactly as for an [architecture](/docs/reference/architecture/).
- **`tasks`** — named lists of commands. `main` is the entry point; other tasks run because something depends on them.

Metrics live next door, in `_metrics.yml`.

> [!TIP]
> `blacklist: ["*.log"]` appears in three of the examples, and the source directories contain a `should_not_be_copied.log` to prove it works. Worth remembering for real projects, where the source directory usually accumulates build output that has no business being copied per job.

## `basic` — tasks, dependencies and source substitution

The smallest workflow. `main` depends on `generate_config`, so the two run in order, and both report progress along the way:

{{< code lang=yaml filename="workflows/basic/_settings.yml" >}}
tasks:
  - name: main
    dependencies:
      - "generate_config"
    commands:
      - echo 'Generating string...'
      - sleep 1
      - "echo 'Progress: 60' > progress.txt"
      - ...
      - "echo 'Progress: 100' > progress.txt"

  - name: "generate_config"
    commands:
      - echo 'Generating config.txt...'
      - "echo 'Progress: 20' > progress.txt"
      - ...
      - touch config.txt
{{< /code >}}

The dependency task takes progress from 20% to 40%, `main` from 60% to 100% — which is how the monitor shows a single coherent bar for a job made of several steps.

It is also the only workflow that **substitutes into a source file**, exactly like an RTL architecture:

{{< code lang=yaml filename="workflows/basic/_settings.yml" >}}
use_parameters: Yes
param_target_file: "main.py"
start_delimiter: 'AWESOME_STRING = "'
stop_delimiter: '"'
{{< /code >}}

{{< code lang=python filename="examples/workflow_simple/main.py" >}}
AWESOME_STRING = "default string"

print(AWESOME_STRING)

with open("output.txt", "w") as f:
    f.write("text: " + AWESOME_STRING + "\n")
    f.write("letters: " + str(len(AWESOME_STRING)) + "\n")
{{< /code >}}

Two configurations are provided, `default.txt` and `hehe.txt`, each holding the string to write between the quotes. And the metrics are read back with regexes over the output file:

{{< code lang=yaml filename="workflows/basic/_metrics.yml" >}}
metrics:
  word:
    type: regex
    settings:
      file: output.txt
      pattern: "text: (.*)"
      group_id: 1

  letters:
    type: regex
    settings:
      file: output.txt
      pattern: "letters: ([0-9]+)"
      group_id: 1
    format: "%.0f"
{{< /code >}}

> [!INFO]
> `word` has no `format`, so it stays a string; `letters` is formatted as an integer. A metric that is not numeric is perfectly valid — it becomes a label rather than an axis.

## `crossplatform` — one task name, two implementations

The same task is declared **twice**, each declaration listing the platforms it applies to. Exactly one is selected, according to `sys.platform`:

{{< code lang=yaml filename="workflows/crossplatform/_settings.yml" >}}
tasks:
  - name: main
    platforms: [linux, darwin]
    commands:
      - echo 'Linux/MacOS Task...'
      - sleep 1
      - "echo 'Progress: 60' > progress.txt"
      - ...

  - name: main
    platforms: win32  # powershell
    commands:
      - Write-Host "Windows Task..."
      - Start-Sleep -Seconds 1
      - '"Progress: 60" | Set-Content progress.txt'
      - ...
{{< /code >}}

`platforms` accepts a single value or a list. The Windows implementation is PowerShell, not `cmd`, which is why it uses `Write-Host` and `Set-Content` rather than shell redirection.

Its `_metrics.yml` reads a `platform` metric out of `platform_info.txt`, so the result records show which branch actually ran.

> [!TIP]
> This is the mechanism to reach for whenever a step is genuinely OS-dependent — invoking a tool that is installed differently, or cleaning up files. Everything else should stay in a single task.

## `cli_profile` — a placeholder filled by the configuration itself

The workflow does not touch its sources at all. Instead, the **command** carries a placeholder named after the workflow:

{{< code lang=yaml filename="workflows/cli_profile/_settings.yml" >}}
# This workflow intentionally does not replace source files; it demonstrates
# command placeholder substitution from the workflow config file itself.
use_parameters: No

tasks:
  - name: main
    commands:
      - python3 run_profile.py --profile "${workflow_cli_profile}" --tag "config-placeholder-demo"
{{< /code >}}

`${workflow_cli_profile}` is filled with the content of the selected configuration file — `default.txt` holds `balanced profile`, `aggressive.txt` holds `aggressive profile` — so `cli_profile/default` and `cli_profile/aggressive` run the same script with different arguments.

This is the simplest form of parameterization there is: **one value, chosen by configuration, passed on the command line**, with nothing written into any file.

The metrics mix a string and two numbers, one of them derived from the profile name by the script itself:

{{< code lang=yaml filename="workflows/cli_profile/_metrics.yml" >}}
metrics:
  profile:
    type: regex
    settings:
      file: output.txt
      pattern: "profile: (.*)"
      group_id: 1

  complexity_score:
    type: regex
    settings:
      file: output.txt
      pattern: "complexity_score: ([0-9.]+)"
      group_id: 1
    format: "%.3f"
{{< /code >}}

## `param_domains_cli` — four parameter domains into four placeholders

A traffic simulation with four independent knobs — speed limit, vehicle count, signal timing, road length — each its own [parameter domain](/docs/configurations/param_domains/):

{{< code lang=yaml filename="workflows/param_domains_cli/_settings.yml" >}}
tasks:
  - name: main
    commands:
      - python3 simulate_traffic.py --max_speed ${max_speed} --num_vehicles ${num_vehicles} --signal_timing ${signal_timing} --road_length ${road_length}
{{< /code >}}

Each domain is a directory of configuration files, and its `_settings.yml` says only that nothing is substituted into a source:

{{< code lang=yaml filename="workflows/param_domains_cli/max_speed/_settings.yml" >}}
# This parameter domain is used for command placeholder substitution.
# Placeholders are injected in task commands through ${max_speed}.
use_parameters: No
{{< /code >}}

{{< code lang=text filename="workflows/param_domains_cli/" >}}
max_speed/       30kmh.txt (30)   70kmh.txt (70)
num_vehicles/    100.txt (100)    300.txt (300)
signal_timing/   15s.txt (15)     45s.txt (45)
road_length/     1km.txt (1)      5km.txt (5)
{{< /code >}}

Note the split between the **file name** and the **file content**: `30kmh.txt` is what the run is called, `30` is what the command receives. Units belong in the name, where they make results readable, and never in the value.

Four domains of two values each, combined with `+`:

{{< code lang=yaml filename="workflow_settings.yml" >}}
  - param_domains_cli + max_speed/* + num_vehicles/* + signal_timing/* + road_length/*
{{< /code >}}

give 2 × 2 × 2 × 2 = **16 runs**. Results are read back from the JSON the script writes:

{{< code lang=yaml filename="workflows/param_domains_cli/_metrics.yml" >}}
metrics:
  average_travel_time:
    type: json
    settings:
      file: workflow_results.json
      key: average_travel_time

  co2_emissions:
    type: json
    settings:
      file: workflow_results.json
      key: co2_emissions

  congestion_level:
    type: json
    settings:
      file: workflow_results.json
      key: congestion_level
{{< /code >}}

## `param_domains_cli_variables` — the same sweep, with no directories

Identical sources, identical command, identical metrics — and **no domain directories at all**. The four sweeps are declared as variables instead:

{{< code lang=yaml filename="workflows/param_domains_cli_variables/_settings.yml" >}}
tasks:
  - name: main
    commands:
      - python3 simulate_traffic.py --max_speed ${max_speed} --num_vehicles ${num_vehicles} --signal_timing ${signal_timing} --road_length ${road_length}

generate_configurations_settings:
  variables:
    max_speed:
      type: list
      unit: kmh
      settings:
        list: [35, 45, 55]

    num_vehicles:
      type: list
      settings:
        list: [100, 300]

    signal_timing:
      type: list
      unit: s
      settings:
        list: [15, 45]

    road_length:
      type: list
      unit: km
      settings:
        list: [1, 5]
{{< /code >}}

Selected the same way, with `+ max_speed/*`, and named the same way — `unit: kmh` produces `max_speed/35kmh`, reproducing by declaration what the directory version encoded in its file names. This is the [virtual parameter domain](/docs/configurations/virtual_param_domains/) mechanism, and reading the two workflows side by side is the fastest way to understand it.

3 × 2 × 2 × 2 = **24 runs**, from twenty lines of YAML and not one file.

> [!TIP]
> Prefer variables whenever the values are just values. Keep directories when a configuration is a **fragment of source code** rather than a scalar — which is the usual case for RTL, and the unusual case for workflows.

## `param_domains_paired_variables` — zipping two variables together

Cross-combining every variable is not always what you want. Here, `max_speed` and `road_length` describe **the same thing** — a road profile — and combining them freely would produce a 35 km/h motorway and a 90 km/h city street, neither of which is worth simulating.

Giving them the same `group` label zips them instead:

{{< code lang=yaml filename="workflows/param_domains_paired_variables/_settings.yml" >}}
generate_configurations_settings:
  variables:
    max_speed:
      type: list
      unit: kmh
      group: road_profile
      settings:
        list: [35, 90]

    road_length:
      type: list
      unit: km
      group: road_profile
      settings:
        list: [1, 10]

    num_vehicles:
      type: list
      settings:
        list: [100, 300]

    signal_timing:
      type: list
      unit: s
      settings:
        list: [15, 45]
{{< /code >}}

`35 kmh` pairs with `1 km` and `90 kmh` with `10 km`, position by position — two coherent road profiles, urban and highway. The ungrouped variables still cross-combine normally with them:

| | Without pairing | With pairing |
|---|---|---|
| Combinations | 2 × 2 × 2 × 2 = **16** | 2 × 2 × 2 = **8** |
| Nonsensical points | 8 of them | none |

> [!TIP]
> Pairing is the answer whenever several parameters describe one physical scenario — a technology node and its supply voltage, a cache size and its associativity, a memory depth and the address width that indexes it. It halves the sweep and removes the combinations that would need explaining away in the results.

## `param_domains_json` — substituting into a parameter file

The same traffic simulation, but the script takes no arguments at all: it reads a JSON file that sits in its sources.

{{< code lang=yaml filename="workflows/param_domains_json/_settings.yml" >}}
tasks:
  - name: main
    commands:
      - python3 simulate_traffic.py
{{< /code >}}

{{< code lang=json filename="examples/workflow_param_domains_json/workflow_params.json" >}}
{
    "num_vehicles": 150,
    "signal_timing": 45,
    "max_speed": 60,
    "road_length": 1,
    "other": ""
}
{{< /code >}}

{{< code lang=python filename="examples/workflow_param_domains_json/simulate_traffic.py" >}}
if __name__ == "__main__":
    # Load parameters from JSON file
    with open("workflow_params.json", "r") as f:
        params = json.load(f)
{{< /code >}}

Each domain therefore **writes its value into that file**, which is ordinary delimiter substitution with the JSON key as the start delimiter:

{{< code lang=yaml filename="workflows/param_domains_json/max_speed/_settings.yml" >}}
use_parameters: Yes
param_target_file: "workflow_params.json"
start_delimiter: '"max_speed": '
stop_delimiter: ','
{{< /code >}}

The other three domains are identical, with their own key. `param_target_file` is relative to the **root of the work directory**, which is where a workflow's `sources` are copied — a workflow has no `rtl/` subfolder, unlike an [architecture](/docs/reference/architecture/).

This is the pattern for any tool driven by a configuration file rather than by flags — and there are many: simulators, synthesis scripts, training configs, benchmark harnesses. The JSON stays valid and runnable on its own, exactly as the RTL examples keep their sources synthesizable outside Odatix.

> [!TIP]
> Using the key as the start delimiter and `,` as the stop delimiter works for any flat JSON, and leaves the formatting of the file untouched. Only the value between them is rewritten — the key order, the indentation and the unrelated entries (`"other": ""` here) survive.

## `metric_sweep` — one run, many result rows

Some tools do not produce a result, they produce a **curve**. A BER simulation sweeps its own Eb/N0 axis internally and writes one CSV row per point:

{{< code lang=yaml filename="workflows/metric_sweep/_settings.yml" >}}
tasks:
  - name: main
    commands:
      - python3 simulate_ber.py --channel_gain ${channel_gain} --ebno_from 1 --ebno_to 3 --ebno_step 0.5

generate_configurations_settings:
  variables:
    channel_gain:
      type: list
      settings:
        list: [0.5, 1.0]
{{< /code >}}

Two configurations, five Eb/N0 points each. Taking the first row of the CSV and discarding the rest would throw away most of the run, so `multiple: true` extracts **every** row, and a `metadata` block tags each one with the value it belongs to:

{{< code lang=yaml filename="workflows/metric_sweep/_metrics.yml" >}}
metrics:
  FER:
    type: csv
    multiple: true
    settings:
      file: results.csv
      key: FER

  BER:
    type: csv
    multiple: true
    settings:
      file: results.csv
      key: BER

  # "operation" metrics are evaluated once per expanded row, using that row's
  # own FER/BER values.
  fer_over_ber:
    type: operation
    settings:
      op: "FER / BER"

metadata:
  EBNO:
    type: csv
    multiple: true
    settings:
      file: results.csv
      key: EBNO
{{< /code >}}

The two runs expand into **ten result records**, each carrying its own `EBNO` — as if each point had been run as a separate configuration, without paying the cost of ten separate jobs.

Two mechanisms worth separating:

- **`multiple: true`** turns one job into several records. `metadata` is what makes them distinguishable; without it, ten records would share the same identity.
- **`type: operation`** computes a metric from other metrics of the same record. Here it is evaluated per row, with that row's own values — not once for the job.

> [!TIP]
> This is the right shape for any tool with an internal sweep — a simulator stepping through SNR points, a benchmark suite reporting per-test numbers, a profiler with per-function results. Let the tool do the inner loop, and let Odatix do the outer one.

## `tensorflow` — bootstrapping an environment

The last example trains a small classifier for a swept number of epochs. It is the only one with an external dependency, and it handles it inside the workflow rather than requiring a pre-installed environment:

{{< code lang=yaml filename="workflows/tensorflow/_settings.yml" >}}
tasks:
  - name: main
    dependencies:
      - /tmp/odatix_tensorflow_example_env/bin/python3
    commands:
      - /tmp/odatix_tensorflow_example_env/bin/python3 train.py

  - name: /tmp/odatix_tensorflow_example_env/bin/python3
    commands:
      - python3.10 -m venv /tmp/odatix_tensorflow_example_env
      - /tmp/odatix_tensorflow_example_env/bin/python3 -m pip install --upgrade pip
      - /tmp/odatix_tensorflow_example_env/bin/python3 -m pip install tensorflow
    on_failure_commands:
      - python3.10 -m venv /tmp/odatix_tensorflow_example_env
      - ...
{{< /code >}}

Three things are going on:

- The dependency task is **named after the file it produces**, so the virtualenv is built once and reused by every subsequent job instead of being rebuilt ten times.
- **`on_failure_commands`** gives a fallback path when the primary one does not work — a different interpreter version, here.
- The training script reports progress from inside a Keras callback, so the job monitor tracks epochs:

{{< code lang=python filename="examples/workflow_tensorflow/train.py" >}}
class ProgressCallback(tf.keras.callbacks.Callback):
    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        progress = int(((epoch + 1) / EPOCHS) * 90 + 5)
        report_progress(progress)
{{< /code >}}

The `epochs` domain generates its ten configurations rather than listing them, and writes the value straight into the script:

{{< code lang=yaml filename="workflows/tensorflow/epochs/_settings.yml" >}}
start_delimiter: 'EPOCHS = '
stop_delimiter: "\n"
param_target_file: "train.py"

generate_configurations: Yes
generate_configurations_settings:
  template: "${epochs}"
  name: "${epochs}"
  variables:
    epochs:
      type: range
      settings:
        from: 5
        to: 50
        step: 5
{{< /code >}}

The metrics end on an `operation` that answers the actual question of the sweep — is the model overfitting?

{{< code lang=yaml filename="workflows/tensorflow/_metrics.yml" >}}
metrics:
  final_loss:
    type: json
    settings: { file: workflow_results.json, key: final_loss }
    format: "%.6f"

  final_val_loss:
    type: json
    settings: { file: workflow_results.json, key: final_val_loss }
    format: "%.6f"

  generalization_gap:
    type: operation
    settings:
      op: "final_val_loss - final_loss"
    format: "%.6f"
{{< /code >}}

Plotting `generalization_gap` against `epochs` in the [Explorer](/docs/features/explorer/) shows the training loss and the validation loss parting company — the same kind of curve, read the same way, as an area-versus-frequency trade-off.

> [!WARNING]
> This example needs a Python interpreter TensorFlow supports, available as `python3.10` on the machine. It is the one workflow that will not run out of the box everywhere.

## Where to go next

- [Workflows](/docs/features/workflows/) — the feature reference.
- [Workflow settings](/docs/reference/workflow/) — every setting these examples use, and the ones they do not.
- [Metrics](/docs/metrics/) — the extractor types (`regex`, `json`, `csv`, `yaml`, `operation`) and what `multiple` and `metadata` do.
- [Virtual parameter domains](/docs/configurations/virtual_param_domains/) — variables, units, and grouping.
