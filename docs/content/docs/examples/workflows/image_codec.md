---
title: "Image codec"
description: "Four variables handed to a script on its command line describe 3150 encoders that trade bitrate for quality: too many to run them all, which is what a design space exploration is for."
weight: 10
---

# `image_codec` — a design space too large to run in full

Sources: `examples/workflow_image_codec` — settings in `workflows/image_codec/`. This one is **not listed** in the shipped `workflow_settings.yml`, on purpose: its four variables describe 3150 configurations.

A small image codec, run once per setting. Nothing is substituted into a file: the four knobs reach the script as placeholders in its command.

{{< code lang=yaml filename="workflows/image_codec/_settings.yml" >}}
use_parameters: No

tasks:
  - name: main
    commands:
      - python3 encode_image.py --block_size ${block_size} --quality ${quality} --downsample ${downsample} --dead_zone ${dead_zone}

variables:
  quality:            # 1, 3, ... 99: 50 values
    type: range
    settings: {from: 1, to: 99, step: 2}
  block_size:         # 4, 8, 16
    type: power_of_two
    settings: {from: 4, to: 16}
  downsample:         # full resolution, half, quarter
    type: list
    settings: {list: [1, 2, 4]}
  dead_zone:          # 0, 10, ... 60 (percent)
    type: range
    settings: {from: 0, to: 60, step: 10}
{{< /code >}}

The script writes `workflow_results.json`, from which four metrics are read: `bitrate_bpp` (bpp), `psnr_db` (dB), `encode_time_ms` (ms) and `compressed_bytes` (B).

Every knob buys quality with bitrate, or bitrate with quality: no setting is best at both. Rather than running all 3150 encoders, search for the ones nothing beats with the shipped campaign `dse_campaigns/image_codec_rate_quality.yml`:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix dse
{{< /code >}}

To run one configuration directly, name a value for each variable on the command line:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix workflow -W "image_codec + quality/51 + block_size/8 + downsample/2 + dead_zone/0"
{{< /code >}}

## Where to go next

<div class="not-prose docs-links">
  <a class="docs-link" href="/docs/reference/dse/#exploring-a-workflow">
    <span class="docs-link__title">Exploring a workflow</span>
    <span class="docs-link__text">How a design space exploration searches this workflow.</span>
  </a>
  <a class="docs-link" href="/docs/examples/workflows/">
    <span class="docs-link__title">All workflow examples</span>
    <span class="docs-link__text">The ten examples and what each one isolates.</span>
  </a>
</div>
