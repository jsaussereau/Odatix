---
title: "TensorFlow Training"
description: "A classifier trained over a generated range of epochs, with a dependency task that bootstraps a virtualenv once and a fallback when it fails."
weight: 9
---

# `tensorflow` — bootstrapping an environment

Sources: `examples/workflow_tensorflow` — settings in `workflows/tensorflow/`.

{{< code lang=yaml filename="workflow_settings.yml" >}}
workflows:
  - tensorflow + epochs/*
{{< /code >}}

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

