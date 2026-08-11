---
title: "FAQ"
description: "Answers to the most frequently asked questions about Odatix."
layout: "faq"
---

{{< faq >}}
{
    "eyebrow": "Support",
    "title": "Frequently Asked Questions",
    "description": "Everything people usually ask before running their first jobs with Odatix, from EDA licences to parallelism and result analysis.",
    "categories": [
        {
            "name": "Getting started",
            "icon": "🚀",
            "questions": [
                {
                    "question": "Are EDA tools like Vivado or Design Compiler included ?",
                    "answer": "No, Odatix facilitates the use of FPGA and ASIC tools, but it does not include any EDA tools. Users need to have their own licenses for the EDA tools they wish to use with Odatix."
                },
                {
                    "question": "Can I try Odatix without an EDA licence ?",
                    "answer": "Yes! Some examples rely on free and open-source tools."
                },
                {
                    "question": "Does Odatix work on Windows, Linux and MacOS ?",
                    "answer": "Odatix targets Linux. However, most features may work on Windows and MacOS. Please note some EDA tools may have specific platform requirements, so users should check the compatibility of their EDA tools with their operating system."
                }
            ]
        },
        {
            "name": "Running jobs",
            "icon": "⚙️",
            "questions": [
                {
                    "question": "How many parallel jobs should I run ?",
                    "answer": "Set `nb_jobs` according to available CPU, memory and EDA licences. The value `auto` uses the available CPUs minus one, but a smaller value is often safer for memory-heavy implementation flows."
                },
                {
                    "question": "Do I need to run odatix generate ?",
                    "answer": "Only when a design or workflow enables `generate_configurations` in its settings. Hand-written configuration files and ordinary parameter-domain files can be run directly."
                },
                {
                    "question": "Where do I find a failed job's logs ?",
                    "answer": "Each job keeps its working directory under `work/`, including `log/` and `report/` subdirectories. Unexpected application errors are also recorded in `odatix_error.log` in the workspace root."
                },
                {
                    "question": "Can I run Odatix on a remote server ?",
                    "answer": "Yes. Start a detached session over SSH, reconnect later to monitor it, and access Odatix Explorer through an SSH tunnel. The server and SSH tutorials explain the recommended setup."
                }
            ]
        },
        {
            "name": "Results & analysis",
            "icon": "📊",
            "questions": [
                {
                    "question": "How do I join simulation and synthesis results ?",
                    "answer": "Export the source result files, define entries in `odatix_userconfig/derived_metrics.yml`, then run `odatix res_derived`. Derived metrics can compute values such as runtime or energy from matching records."
                }
            ]
        }
    ]
}
{{< /faq >}}
