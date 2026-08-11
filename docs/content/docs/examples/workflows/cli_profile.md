---
title: "CLI Profile"
description: "A command placeholder filled with the content of the selected configuration file — parameterization with nothing written into any source."
weight: 3
---

# `cli_profile` — a placeholder filled by the configuration itself

Sources: `examples/workflow_cli_profile` — settings in `workflows/cli_profile/`.

{{< code lang=yaml filename="workflow_settings.yml" >}}
workflows:
  - cli_profile/default
  - cli_profile/aggressive
{{< /code >}}

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

