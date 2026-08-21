---
title: "Parameter Domains"
description: "Split independent parameters into domains and combine them automatically to cover a full design space."
weight: 1
---


# Parameter Domains

> [!IMPORTANT] Requires Odatix 3.4+

A **parameter domain** is a set of parameters for a design, defined independently of the others. Domains let you combine parameters automatically instead of writing a configuration file for every combination by hand — invaluable when the design space is large.

{{< toc >}}


> [!WARNING]
> Define your [architecture folder](/docs/configurations/) in `odatix_userconfig/architectures/` before adding parameter domains.

## File structure

Each parameter domain is a sub-folder of your architecture directory, containing a `_settings.yml` and its parameter files — exactly like the main design, but scoped to one group of parameters.

{{< code lang=text filename="architectures/AsteRISC/" >}}
architectures/AsteRISC/
├── Baseline/            # 'Baseline' parameter domain
│   ├── _settings.yml
│   ├── E.txt
│   └── I.txt
├── DMEM/                # 'DMEM' parameter domain
│   ├── _settings.yml
│   ├── 256.txt
│   ├── 512.txt
│   └── 1024.txt
├── Mul/                 # 'Mul' parameter domain
│   ├── _settings.yml
│   ├── Basic.txt
│   ├── Fast.txt
│   └── Off.txt
├── _settings.yml        # main architecture settings
├── M0000.txt            # main architecture configurations
└── M0001.txt
{{< /code >}}

## Marking domains in the top level

Each domain replaces a different delimited block of your top level. Give every block a distinct delimiter:

{{< code lang=verilog filename="top_level.sv" >}}
module top_level #(
  // <dmem>
  parameter p_dmem_depth_pw2 = 13,
  // </dmem>

  // <baseline>
  parameter p_ext_rve        = 0,
  // </baseline>

  // <mul>
  parameter p_ext_rvm        = 0,
  parameter p_mul_fast       = 0,
  // </mul>
) ( /* ... */ );
{{< /code >}}

A domain's `_settings.yml` only needs its delimiters:

{{< code lang=yaml filename="Baseline/_settings.yml" >}}
start_delimiter: "  // <baseline>"
stop_delimiter: "  // </baseline>"
{{< /code >}}

> [!IMPORTANT]
> If a domain replaces parameters in a file other than the top level, point to it with `param_target_file`. With generated RTL (Chisel, HLS), `param_target_file` is mandatory.

{{< code lang=yaml filename="other_domain/_settings.yml" >}}
start_delimiter: "// start"
stop_delimiter: "// end"
param_target_file: "src/main/scala/counter.scala"
{{< /code >}}

## Domains can generate configurations too

A domain can use [configuration generation](/docs/configurations/config_generation/) to produce its values dynamically:

{{< code lang=yaml filename="DMEM/_settings.yml" >}}
start_delimiter: "  // <dmem>"
stop_delimiter: "  // </dmem>"
param_target_file: "top.v"

configurations:
  name: "${mem_depth_pw2}"
  template: "\n  parameter p_dmem_depth_pw2 = $mem_depth,\n"

variables:
  mem_depth:
    type: range
    settings: { from: 8, to: 12 }
  mem_depth_pw2:
    type: function
    settings: { op: 2^$mem_depth }
{{< /code >}}

## Running jobs with parameter domains

In your run settings, combine domains with `+`. Each line is one design variant:

{{< code lang=yaml filename="fmax_synthesis_settings.yml" >}}
architectures:
  - AsteRISC/M0000 + DMEM/1024 + IMEM/1024 + Baseline/I + Mul/Off
  - AsteRISC/M0001 + DMEM/1024 + IMEM/1024 + Baseline/I + Mul/Fast
{{< /code >}}

Use the `*` wildcard to expand every matching configuration automatically:

{{< code lang=yaml filename="fmax_synthesis_settings.yml" >}}
architectures:
  # every combination of every domain
  - AsteRISC/* + DMEM/* + IMEM/* + Baseline/* + Mul/*
{{< /code >}}

> [!TIP]
> Parameter domains work for **any** job type — Fmax synthesis, custom-frequency synthesis, simulation and [workflows](/docs/features/workflows/).

## See also

- [Configuration generation](/docs/configurations/config_generation/)
- [Virtual parameter domains](/docs/configurations/virtual_param_domains/) (for workflows)
- [Configuration reference](/docs/reference/)
