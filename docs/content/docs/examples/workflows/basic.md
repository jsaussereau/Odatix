---
title: "Basic"
description: "The smallest workflow: two tasks with a dependency, progress reported from both, a value substituted into a Python source file, and metrics read back with regexes."
weight: 1
---

# `basic` — tasks, dependencies and source substitution

Sources: `examples/workflow_simple` — settings in `workflows/basic/`. This one is **not listed** in the shipped `workflow_settings.yml` — add it to the `workflows:` list to run it:

{{< code lang=yaml filename="workflow_settings.yml" >}}
workflows:
  - basic/*
{{< /code >}}

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

## Where to go next

<div class="not-prose docs-links">
  <a class="docs-link" href="/docs/examples/workflows/">
    <span class="docs-link__title">All workflow examples</span>
    <span class="docs-link__text">The nine examples and what each one isolates.</span>
  </a>
  <a class="docs-link" href="/docs/features/workflows/">
    <span class="docs-link__title">Workflows</span>
    <span class="docs-link__text">The feature reference.</span>
  </a>
  <a class="docs-link" href="/docs/reference/workflow/">
    <span class="docs-link__title">Workflow settings</span>
    <span class="docs-link__text">Every setting these examples use, and the ones they do not.</span>
  </a>
  <a class="docs-link" href="/docs/results/">
    <span class="docs-link__title">Metrics</span>
    <span class="docs-link__text">The extractor types, and what <code>multiple</code> and <code>metadata</code> do.</span>
  </a>
</div>

