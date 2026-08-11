---
title: Home
description: "Odatix is a free and open-source design automation toolbox for the implementation, validation and design space exploration of configurable digital designs across FPGA and ASIC tools."
---

{{< home-hero
    eyebrow="Free &amp; open source"
    headline="Implement every version of your design,"
    highlight="automatically"
    sub_headline="Odatix generates every configuration of your parametrizable design, runs synthesis, place &amp; route and simulation jobs in parallel on the EDA tools you already use, and gathers every metric in one interactive dashboard."
    primary_button_text="Get started"
    primary_button_url="/install"
    secondary_button_text="View on GitHub"
    secondary_button_url="https://github.com/jsaussereau/odatix"
    image="/images/screenshots/explorer-overview.png"
    image_caption="Odatix Explorer — interactive comparison of implementation metrics"
    tools="Vivado, Design Compiler, Genus, Innovus, IC Compiler II, OpenLane, Verilator, GHDL"
    arrow=true
>}}

{{< section-container class="py-20 bg-gray-50" >}}
    <div class="max-w-4xl mx-auto text-center">
        <h2 class="text-3xl font-bold mb-6">One FOSS* toolbox, from RTL to results</h2>
        <p class="text-lg text-gray-600">
            Digital design means constantly balancing conflicting goals — timing, power, area/resources — across many architectural choices, technology targets and EDA tools.
            Odatix takes care of the repetitive part: it generates every configuration of your designs, runs synthesis and simulation jobs in parallel on the tools of your choice, and gathers all the metrics in one place so you can focus on the decisions that matter.
        </p>
        <p class="text-sm text-gray-400 mt-4">
            *FOSS = Free and Open Source Software
        </p>
    </div>
{{< /section-container >}}


{{< section-container class="pb-20 bg-gray-50" >}}
    <div class="max-w-6xl mx-auto">
        <div class="home-steps">
            <div class="home-step" style="--step-accent:#2563eb">
                <span class="home-step__num">01</span>
                <h3 class="home-step__title">Describe once</h3>
                <p class="home-step__text">Point Odatix at your existing HDL sources and declare the parameters you want to sweep. A handful of YAML rules is enough — scripting is optional, no per-tool project files. Once declared once, it works on all your tools!</p>
                <span class="home-step__meta">VHDL · Verilog · SystemVerilog · Chisel · HLS</span>
            </div>
            <div class="home-step" style="--step-accent:#7c3aed">
                <span class="home-step__num">02</span>
                <h3 class="home-step__title">Run everywhere, in parallel</h3>
                <p class="home-step__text">Odatix expands your parameters into every configuration and drives your FPGA and ASIC tools concurrently — including a binary search on the clock constraint to find each Fmax.</p>
                <span class="home-step__meta">Analysis · Synthesis · Fmax · P&amp;R · Simulation</span>
            </div>
            <div class="home-step" style="--step-accent:#db2777">
                <span class="home-step__num">03</span>
                <h3 class="home-step__title">Compare and decide</h3>
                <p class="home-step__text">Every run lands in the same result files. Odatix Explorer turns them into interactive charts you can filter, correlate and export straight into your papers and slides. No more copying and pasting data into spreadsheets — everything is automated.</p>
                <span class="home-step__meta">Lines · Columns · Scatter · Radar · 3D</span>
            </div>
        </div>
    </div>
{{< /section-container >}}

<!-- 
{{< section-container class="py-20 bg-gray-50" >}}
    <div class="max-w-6xl mx-auto">
        <h2 class="text-3xl font-bold text-center mb-12">Featured projects</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8 items-stretch" style="grid-auto-rows: 1fr;">
            {{< project-card 
                title="AFF3CT"
                icon="/images/logos/aff3ct.png"
                description="A Flexible Forward Error Correction Toolbox"
                buttonLink="https://aff3ct.github.io/"
                openInNewTab="true"
            >}}
            {{< project-card 
                title="Odatix"
                icon="/images/logos/odatix.png"
                description="An open-source design automation toolbox for FPGA/ASIC implementation and Design Space Exploration"
                buttonLink="https://odatix.readthedocs.io/en/latest/"
                openInNewTab="true"
            >}}
            {{< project-card 
                title="AsteRISC"
                icon="/images/logos/asterisc.png"
                description="A configurable multi-cycle RISC-V core designed for design space exploration"
                buttonLink="https://asterisc.readthedocs.io/en/latest/"
                openInNewTab="true"
            >}}
        </div>
    </div>
{{< /section-container >}} -->


{{< features-section 
    title="Main features"
    description="Odatix covers the whole implementation and validation loop of configurable digital designs."
>}}

{{< feature
  title="Architecture exploration"
  description="Define a parametrizable design once, then let Odatix generate and implement every configuration you want to compare. Parameter domains and configuration generation turn a handful of YAML rules into hundreds of design variants — regardless of the HDL you use (VHDL, Verilog, SystemVerilog, and even Chisel, HLS, HDL Coder or any other HDL generation or conversion method)."
  badgeColor="#2563eb"
  image="/images/features/architecture-exploration.svg"
  features="Parameter domains, Automatic configuration generation, VHDL\, Verilog\, SystemVerilog\, Chisel\, HLS"
  imagePosition="left"
  buttonText="Learn more"
  buttonLink="/docs/features/architecture-exploration/"
>}}

{{< feature
  title="RTL analysis"
  description="Elaborate every configuration of your designs with several EDA tools at once, and catch missing sources, black boxes and lint issues in seconds instead of hours — before committing a whole campaign to synthesis."
  badgeColor="#f59e0b"
  image="/images/features/analysis.svg"
  features="Elaboration only, Parallel runs, Vivado\, Genus\, Design Compiler\, Verilator, Errors\, black boxes and critical warnings flagged"
  imagePosition="right"
  buttonText="Learn more"
  buttonLink="/docs/features/analysis/"
>}}

{{< feature
  title="Automated RTL synthesis"
  description="Run synthesis for every configuration of your design, on every target you care about, across FPGA and ASIC tools. Odatix drives Vivado, Design Compiler, Genus and OpenLane for you and collects area, resource, timing and power metrics automatically."
  badgeColor="#7c3aed"
  image="/images/features/rtl-synthesis.svg"
  features="FPGA and ASIC targets, Vivado\, Design Compiler\, Genus\, OpenLane, Parallel runs, Custom flows and scripts, Step-by-step or one-shot (synthesis\, PNR\, bitstream generation)"
  imagePosition="left"
  buttonText="Learn more"
  buttonLink="/docs/features/rtl_synthesis/"
>}}

{{< feature
  title="Maximum frequency search"
  description="Automatically find the maximum operating frequency (Fmax) of any digital design through a parallel binary search on the clock constraint — for each configuration and each target."
  badgeColor="#0ea5e9"
  image="/images/features/fmax-synthesis.svg"
  features="Binary search on Fmax, Per-configuration bounds, Parallel runs, Custom flows and scripts"
  imagePosition="right"
  buttonText="Learn more"
  buttonLink="/docs/features/rtl_fmax_synthesis/"
>}}

{{< feature
  title="Place & route"
  description="Chain two EDA tools: place & route a netlist another tool synthesized: Design Compiler + IC Compiler II, Genus + Innovus, Design Compiler + Innovus, Genus + IC Compiler II, or a pair of your own — and get post-route numbers next to the synthesis figures in the same results files."
  badgeColor="#0d9488"
  image="/images/features/pnr.svg"
  features="Synthesize with one tool\, place and route with another, Parallel runs, Step-by-step or one-shot (init\, place\, cts\, route\, signoff)"
  imagePosition="left"
  buttonText="Learn more"
  buttonLink="/docs/features/pnr/"
>}}

{{< feature
  title="Simulation & validation"
  description="Validate and benchmark every configuration of your design with the simulator of your choice. Odatix ships with ready-to-use examples for various simulators, and can drive virtually any simulator."
  badgeColor="#16a34a"
  image="/images/features/simulation.svg"
  features="Flow driven: works with any simulator, Verilator\, GHDL\, QuestaSim/ModelSim and Vivado (xsim) examples, Parallel runs"
  imagePosition="right"
  buttonText="Learn more"
  buttonLink="/docs/features/simulation/"
>}}

{{< feature
  title="Custom workflows"
  description="Go beyond synthesis and simulation. Workflows let you describe arbitrary task pipelines — with dependencies, progress tracking and custom metric extraction — and sweep them across parameters. From HLS flows to machine-learning training runs, if it runs on a command line, Odatix can orchestrate and compare it."
  badgeColor="#ea580c"
  image="/images/features/workflows.svg"
  features="Arbitrary task pipelines, Parallel runs, Custom metrics (regex\, JSON), Parameter sweeping"
  imagePosition="left"
  buttonText="Learn more"
  buttonLink="/docs/features/workflows/"
>}}

{{< feature
  title="Interactive results exploration"
  description="Odatix Explorer turns your synthesis, simulation, analysis and workflow results into an interactive web dashboard. Compare architectures with line, column, scatter, radar and 3D charts, correlate metrics against each other, and export publication-ready figures in vector or raster formats."
  badgeColor="#db2777"
  image="/images/features/explorer.svg"
  features="Line, Column, Scatter 2D & 3D, Radar, Tables, SVG\, PNG\, JPEG\, WEBP export, Hostable interface on your own server"
  imagePosition="right"
  buttonText="Learn more"
  buttonLink="/docs/features/explorer/"
>}}

{{< /features-section >}}

{{< citation-section
    title="Cite Odatix in your work"
    description="Odatix is described in a peer-reviewed article. If it helped your research, please cite it."
    paper="Odatix: An open-source design automation toolbox for FPGA/ASIC implementation"
    authors="Jonathan Saussereau, Christophe Jego, Camille Leroux, Jean-Baptiste Begueret"
    journal="SoftwareX"
    meta="Volume 29, 2025, Article 101970, ISSN 2352-7110"
    doi="10.1016/j.softx.2024.101970"
    url="https://www.sciencedirect.com/science/article/pii/S2352711024003406"
>}}

{{< tabs >}}

{{% tab name="Text" %}}
{{< code lang=txt filename="Raw Text Citation" >}}
Jonathan Saussereau, Christophe Jego, Camille Leroux, Jean-Baptiste Begueret,
Odatix: An open-source design automation toolbox for FPGA/ASIC implementation,
SoftwareX,
Volume 29,
2025,
101970,
ISSN 2352-7110,
https://doi.org/10.1016/j.softx.2024.101970.
(https://www.sciencedirect.com/science/article/pii/S2352711024003406)
{{< /code >}}
{{% /tab %}}

{{% tab name="BibTeX" %}}
{{< code lang=latex filename="BibTeX Citation" >}}
@article{SAUSSEREAU2025101970,
  title = {Odatix: An open-source design automation toolbox for FPGA/ASIC implementation},
  journal = {SoftwareX},
  volume = {29},
  pages = {101970},
  year = {2025},
  issn = {2352-7110},
  doi = {https://doi.org/10.1016/j.softx.2024.101970},
  url = {https://www.sciencedirect.com/science/article/pii/S2352711024003406},
  author = {Jonathan Saussereau and Christophe Jego and Camille Leroux and Jean-Baptiste Begueret},
  keywords = {Design automation, Design space exploration, Hardware, Computer-aided design, Design flow, FPGA, ASIC}
}
{{< /code >}}
{{% /tab %}}

{{% tab name="RIS" %}}
{{< code lang=latex filename="RIS Citation" >}}
TY  - JOUR
T1  - Odatix: An open-source design automation toolbox for FPGA/ASIC implementation
AU  - Saussereau, Jonathan
AU  - Jego, Christophe
AU  - Leroux, Camille
AU  - Begueret, Jean-Baptiste
JO  - SoftwareX
VL  - 29
SP  - 101970
PY  - 2025
DA  - 2025/02/01/
SN  - 2352-7110
DO  - https://doi.org/10.1016/j.softx.2024.101970
UR  - https://www.sciencedirect.com/science/article/pii/S2352711024003406
KW  - Design automation
KW  - Design space exploration
KW  - Hardware
KW  - Computer-aided design
KW  - Design flow
KW  - FPGA
KW  - ASIC
ER  -
{{< /code >}}
{{% /tab %}}

{{< /tabs >}}
{{< /citation-section >}}

{{< cta >}}
