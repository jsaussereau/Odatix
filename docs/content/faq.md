---
title: "FAQ"
description: "Answers to the most frequently asked questions about Odatix."
layout: "faq"
---

{{< faq >}}
{
    "eyebrow": "Support",
    "title": "Frequently asked questions",
    "description": "Everything people usually ask before running their first jobs with Odatix, from EDA licences to parallelism and result analysis.",
    "categories": [
        {
            "name": "Getting started",
            "icon": "🚀",
            "questions": [
                {
                    "question": "Are EDA tools like Vivado or Design Compiler included?",
                    "answer": "No, Odatix facilitates the use of FPGA and ASIC tools, but it does not include any EDA tools. Users need to have their own licenses for the EDA tools they wish to use with Odatix."
                },
                {
                    "question": "Can I try Odatix without an EDA licence?",
                    "answer": "Yes! Some examples rely on free and open-source tools."
                },
                {
                    "question": "Odatix does not find my EDA tool. What should I check?",
                    "answer": "Run the tool's own version command (`vivado -version`...) in the terminal where you start Odatix: if it fails, the tool is not on your `PATH`, or its environment script was not sourced. Otherwise, set `tool_install_path` in the target file of the tool, in `odatix_userconfig/targets/`, to its installation directory: Odatix puts it first on the `PATH` of the tool's commands. See [Install supported EDA tools](/install/eda_tools/)."
                },
                {
                    "question": "The tool fails with a licence error. Is it Odatix?",
                    "answer": "No. Odatix runs the tool in the environment of the terminal (or session) that started it, so the licence variables (`LM_LICENSE_FILE`, or the one of your vendor) and the licence server must be reachable from there. Check that the tool starts on its own in that same terminal. Also keep `nb_jobs` within the number of licences you have: each parallel job takes one."
                },
                {
                    "question": "Does Odatix work on Windows, Linux and macOS?",
                    "answer": "Odatix targets Linux. However, most features may work on Windows and macOS. Please note some EDA tools may have specific platform requirements, so users should check the compatibility of their EDA tools with their operating system."
                }
            ]
        },
        {
            "name": "Running jobs",
            "icon": "⚙️",
            "questions": [
                {
                    "question": "How many parallel jobs should I run?",
                    "answer": "Set `nb_jobs` according to available CPU, memory and EDA licences. The value `auto` uses the available CPUs minus one, but a smaller value is often safer for memory-heavy implementation flows."
                },
                {
                    "question": "Where do I find a failed job's logs?",
                    "answer": "Each job keeps its working directory under `work/`, including `log/` and `report/` subdirectories. The [Job Monitor](/docs/sessions/gui_monitor/) also streams the log of each job live: select a job to follow it, and use **Open task directory** to open its work directory in your file browser."
                },
                {
                    "question": "Odatix crashed with an internal error. What should I do?",
                    "answer": "Odatix writes the full details of an unexpected error (date, system, Odatix and Python versions, command line and traceback) to a log file in the directory it was started from: `odatix_error.log` for `odatix`, `odatix-gui_error.log` for `odatix-gui` and `odatix-explorer_error.log` for `odatix-explorer`. Each crash overwrites the previous one. Please [open an issue on GitHub](https://github.com/jsaussereau/Odatix/issues) with that file attached."
                },
                {
                    "question": "Can I run Odatix on a remote server?",
                    "answer": "Yes. Start a detached session over SSH, reconnect later to monitor it, and access Odatix Explorer through an SSH tunnel. The server and SSH tutorials explain the recommended setup."
                },
                {
                    "question": "What is the difference between odatix fmax and odatix synth?",
                    "answer": "`odatix fmax` searches the maximum operating frequency of each configuration: it runs synthesis repeatedly between the bounds of the `fmax_synthesis` block, narrowing them down until it converges. `odatix synth` runs synthesis once per frequency you ask for (`fixed_freq_synthesis` block), to see how area or power behave at given clock speeds, for example the one of your system."
                },
                {
                    "question": "My machine saturates or swaps. What can I do?",
                    "answer": "Lower `nb_jobs` in the run settings: implementation flows can take several GB each. Keep the resource guard on in `odatix.yml` (`resource_guard`, `cpu_limit`, `mem_limit`): it pauses jobs while the machine is overloaded and resumes them afterwards. On a shared machine, `force_single_thread: Yes` keeps each job on one thread, whatever its tool."
                },
                {
                    "question": "My settings files from Odatix 3.7 (or earlier) no longer work. What should I do?",
                    "answer": "Run `odatix migrate` in the workspace (`odatix migrate -n` first to see what would change). It rewrites settings files written in a former format, keeping their comments and layout, and keeps each former version as `<file>.bak`. Result files from before 4.0 need nothing: they are still read and converted on the fly, and re-exporting writes them in the current format."
                }
            ]
        },
        {
            "name": "Results & analysis",
            "icon": "📊",
            "questions": [
                {
                    "question": "How do I join simulation and synthesis results?",
                    "answer": "Export the source result files, define entries in `odatix_userconfig/derived_metrics.yml`, then run `odatix results derived`. Derived metrics can compute values such as runtime or energy from matching records."
                },
                {
                    "question": "How do I regenerate results without running the jobs again?",
                    "answer": "Use `odatix results synth`, `odatix results sim`, `odatix results workflow`, `odatix results analysis` or `odatix results derived`. They read the job directories under `work/` again and rewrite the result files. Metrics are extracted at export, so after fixing a pattern in a metrics file, re-exporting is enough."
                },
                {
                    "question": "How do I open Odatix Explorer running on a remote server?",
                    "answer": "On the server, run `odatix-explorer --nobrowser --port 8052` (inside `tmux` to keep it running). On your workstation, open a tunnel with `ssh -N -L 8052:127.0.0.1:8052 user@server`, then browse to `http://127.0.0.1:8052`. On a trusted local network where the port is open, you can skip the tunnel: run `odatix-explorer -nB --port 8052` (`-nB` =  `--network --nobrowser`) and browse to `http://<server-address>:8052`. Anyone who reaches that port can read your results, so add `--read-only` to keep visitors from changing anything. See the [SSH tutorial](/tutorials/ssh/)."
                }
            ]
        },
        {
            "name": "RTL analysis",
            "icon": "🔍",
            "questions": [
                {
                    "question": "My analysis found errors, but the job is marked as succeeded. Why?",
                    "answer": "That is intended. The job status says whether the tool ran; the verdict on the design is the analysis status (*Passed*, *Warnings*, *Failed*...), shown on the RTL Analysis page of Odatix Explorer and in the report of `odatix results analysis`. Tools do not agree on the exit code an RTL error gives, so it is not used to judge the design."
                },
                {
                    "question": "How do I declare that a warning is expected?",
                    "answer": "Add an entry to the `expected` section of `odatix_userconfig/analyze_settings.yml`, matching the finding by `category`, `subject` (wildcards allowed), and optionally `architectures` or `tools`, with the `reason` it is normal. Matching findings no longer count against the design. See the [analysis reference](/docs/reference/analysis/)."
                }
            ]
        },
        {
            "name": "Design space exploration",
            "icon": "🧭",
            "questions": [
                {
                    "question": "How do I explore a design space without running every configuration?",
                    "answer": "Use `odatix dse`. It evaluates a batch of configurations, reads their results, and picks the next batch from there until the budget is spent, returning the Pareto front of the best trade-offs. Choose the strategy with `-s` (e.g. `nsga2` or `bayesian`) and the budget with `-b`. See [Design space exploration](/docs/reference/dse/)."
                },
                {
                    "question": "How do I exclude invalid combinations of parameters?",
                    "answer": "Declare them once in an `exclusions` list: each rule says `when` a combination is invalid (an expression over the parameters, such as `\"$Overlap == 'On' and $p_rf_sp == 1\"`), its `kind` (`illegal`, `duplicate`, `dominated`) and an optional `message`. Every sweep and every search then skips them. See [Exclusions](/docs/configurations/exclusions/)."
                }
            ]
        }
    ]
}
{{< /faq >}}
