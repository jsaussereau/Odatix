---
title: "Crossplatform"
description: "The same task name declared twice, once for Linux/macOS and once for PowerShell, with exactly one implementation selected at run time."
weight: 2
---

# `crossplatform` — one task name, two implementations

Sources: `examples/workflow_simple` — settings in `workflows/crossplatform/`.

{{< code lang=yaml filename="workflow_settings.yml" >}}
workflows:
  - crossplatform
{{< /code >}}

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

