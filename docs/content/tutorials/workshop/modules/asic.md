---
title: "ASIC with open-source tools"
date: 2026-10-19
author: "Jonathan Saussereau"
weight: 4
description: "Module D: take the same design down to a routed sky130 layout with LibreLane, and compare it with the FPGA results."
categories: ["Tutorial", "PNR"]
tags: ["workshop", "asic", "librelane", "sky130", "openroad"]
featured_image: "/images/features/pnr.svg"
next_tutorials: ["/tutorials/workshop/modules/pnr", "/tutorials/workshop/modules/design_space"]
---

{{< toc >}}

| Tools needed | Time | What you leave with |
|---|---|---|
| LibreLane (open source, no license) | 30 min | The same core as cells and wires, on an open PDK |

The design that was LUTs an hour ago becomes standard cells, a floorplan and
routed metal — with no license, no NDA and no vendor account. LibreLane drives
Yosys, OpenROAD, Magic, KLayout and Netgen; Odatix drives LibreLane exactly as
it drives Vivado, with the same commands and the same selection syntax.

> [!IMPORTANT]
> The first LibreLane run downloads its tools through Nix and its PDK through
> ciel — hundreds of megabytes, and not something to do on conference Wi-Fi.
> Have it installed and smoke-tested **before** the session: [Install
> LibreLane](/install/eda_tools/#install-librelane).

## Step 1 — Point Odatix at your LibreLane

{{< code lang=yaml filename="odatix_userconfig/targets/target_librelane.yml" >}}
# A LibreLane checkout, run through its nix-shell. Leave it empty when
# "librelane" is already on your $PATH.
tool_install_path: ~/librelane

targets:
  - sky130_hd
  # - gf180mcu_9t
  # - ihp_sg13g2
{{< /code >}}

The targets are the open PDKs LibreLane supports; keep one for the workshop.
Check that Odatix finds the tool before launching anything long — the **Tools**
page of `odatix-gui` says so for every tool at once.

> [!NOTE]
> Every command runs on `My_Cordic_sv`, the architecture you described in the
> common track. LibreLane synthesizes Verilog and SystemVerilog only, through
> Yosys — its VHDL flow needs a plugin that is not part of a standard install.
> If you described `My_Cordic_vhdl`, describe `My_Cordic_sv` as well first:
> the SystemVerilog tab of [the common track](/tutorials/workshop/common/describe/),
> steps 2 and 3 — five minutes, same core, same parameters, same results.

## Step 2 — Synthesize, and see how fast it goes

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix fmax --tool librelane -a "My_Cordic_sv + ITERATIONS/12 + WIDTH/*" --from 10 --to 150 -y
{{< /code >}}

An fmax search with LibreLane stops at `synthesis` by default: it converges on
the timing of the synthesized netlist, which is fast and optimistic — the
equivalent of what the other ASIC synthesis tools report. `--from 10 --to 150`
frames the search: on sky130 the CORDIC runs around 50 MHz, below the default
lower bound. Four minutes, one configuration per width,
and the results land in `results/results_librelane.yml` with `Fmax`,
`Cell_count` and `Cell_Area` instead of `LUT_count`.

Read the rest of the page while that runs.

## Step 3 — Go down to a layout

An fmax search answers *how fast*; the Classic flow answers *what it looks
like*. Run one configuration at a fixed frequency, through the steps of a real
flow:

{{< code lang=bash filename="Terminal" prompt="true" >}}
$ odatix synth --tool librelane --at 40 -a "My_Cordic_sv + ITERATIONS/12 + WIDTH/8" --until route -y
{{< /code >}}

The job is split into `synthesis`, `floorplan`, `place`, `cts`, `route` and
`signoff`, and each step continues from the state the previous one left, so
nothing is ever run twice:

- `--until place` is the quickest way to see a real floorplan;
- `--until route` ends with the timing of the routed design, parasitics
  included — the number that actually means something;
- `signoff` streams the layout out and runs DRC and LVS. On a design this small
  it takes longer than everything before it put together, so leave it out unless
  you have the time, then ask for it on its own: a later `odatix synth --tool
  librelane --at 40 -a "..."` resumes at the step left to do.

> [!TIP]
> Each step writes its own result record. In Explorer, the **Filters** tab has a
> **Step scope** selector: switch it from `last` to `intermediate` and you can
> watch the area and the slack change from synthesis to routing, for the same
> job.

The run directory holds what the tools produced — the GDSII, the reports, the
OpenROAD database — under `work/`. Open the layout in KLayout or Magic while the
next job runs: two minutes, and the design you simulated this morning is
suddenly a picture of metal.

## Step 4 — FPGA against ASIC, on one chart

If you also did [How fast can it go?](/tutorials/workshop/modules/fmax/), both result
files are now in `results/`, and Explorer reads all of them at once:

1. Chart type **Lines**
2. **Axes** → x: `WIDTH`, y: `Fmax`
3. **Style** → **Color by**: `target`

One line for `xc7a100t-csg324-1`, one for `sky130_hd`: the same RTL, the same
configurations, two completely different implementation technologies, measured
the same way. The cost axes do not compare — LUTs are not cells — but the
**shape** of the two curves does, and that is the interesting part.

> [!NOTE]
> The **Table** page lists the raw records behind the charts, with every metric
> each tool reported. It is the right place to look when two tools do not
> measure the same things.

## If something did not work

| Symptom | What to do |
|---|---|
| `nix-shell` fails on permissions | The Nix daemon is not running: `sudo systemctl enable --now nix-daemon.socket`. See the warning in [Install LibreLane](/install/eda_tools/#install-librelane). |
| `cannot connect to socket at '/nix/var/nix/daemon-socket/socket': Connection refused` | The daemon socket failed to start, typically on a stale socket file (`systemctl status nix-daemon.socket` says *Address already in use*): `sudo rm /nix/var/nix/daemon-socket/socket && sudo systemctl restart nix-daemon.socket`. |
| Nix starts building tools from source | The LibreLane binary cache is not configured in `/etc/nix/nix.conf`. Stop it; it will take hours. |
| The first job spends forever "installing the PDK" | That is ciel downloading sky130. It happens once, and it is why this is prepared in advance. |
| Odatix does not find LibreLane | `tool_install_path` must be the checkout holding its `nix-shell`, or `librelane` must be on your `PATH`. |
| Everything is simply too slow here | Run one configuration, `--until synthesis`, and follow step 4 on the results bundle the organizers provide. |

## Next

- [How fast can it go?](/tutorials/workshop/modules/fmax/) — the same design with a
  commercial synthesizer: Design Compiler or Genus have their own tab there.
- [Accuracy against cost](/tutorials/workshop/modules/accuracy/) — cell area against
  measured accuracy works exactly like LUTs against accuracy.
- [Place and route after synthesis](/tutorials/workshop/modules/pnr/) — the other way to
  a layout: a netlist synthesized by one tool, placed and routed by another.
