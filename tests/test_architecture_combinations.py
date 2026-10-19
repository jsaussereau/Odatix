"""
What the Architecture API says about the sweep of an architecture: the same
combinations a run would make of "<arch>/* + <domain>/*" (D-03, D-06, D-09).
"""

import yaml

from odatix.workspace.architectures import ArchitectureCollection


def make(tmp_path, exclusions=None):
    root = tmp_path / "architectures"
    arch = root / "adder"
    (arch / "Regs").mkdir(parents=True)
    settings = {
        "rtl_path": "rtl",
        "use_parameters": True,
        "start_delimiter": "// <w>",
        "stop_delimiter": "// </w>",
        "configurations": {"name": "${width}bits", "template": "\n  localparam WIDTH = ${width};\n"},
        "variables": {"width": {"type": "list", "settings": {"list": [8, 16, 32]}}},
    }
    if exclusions:
        settings["exclusions"] = exclusions
    (arch / "_settings.yml").write_text(yaml.safe_dump(settings), encoding="utf-8")
    (arch / "Regs" / "_settings.yml").write_text(yaml.safe_dump({
        "use_parameters": True, "start_delimiter": "// <r>", "stop_delimiter": "// </r>",
    }))
    (arch / "Regs" / "On.txt").write_text("\n  localparam R = 1;\n", encoding="utf-8")
    (arch / "Regs" / "Off.txt").write_text("\n  localparam R = 0;\n", encoding="utf-8")
    return ArchitectureCollection(None, str(root))["adder"]


def test_the_full_sweep_crosses_every_domain(tmp_path):
    arch = make(tmp_path)
    assert arch.count_combinations() == 6
    assert ["adder/8bits", "Regs/Off"] in arch.combinations()


def test_exclusions_leave_combinations_out_as_a_run_does(tmp_path):
    arch = make(tmp_path, exclusions=[{"id": "no-regs-32", "when": "$Regs == 'Off' and $config == '32bits'"}])
    combinations = arch.combinations()
    assert ["adder/32bits", "Regs/Off"] not in combinations
    assert arch.count_combinations() == 5 == len(combinations)
    # Asked for, the whole cross product is still there.
    assert arch.count_combinations(exclusions=False) == 6
    assert len(arch.combinations(exclusions=False)) == 6


def test_the_architecture_previews_its_main_domain(tmp_path):
    arch = make(tmp_path)
    preview = arch.preview_configurations()
    assert preview == arch.domains.main.preview_configurations()
    assert preview["16bits"] == "\n  localparam WIDTH = 16;\n"


def test_the_domains_say_what_their_rules_describe(tmp_path):
    arch = make(tmp_path)
    # No file was written for the main domain: its configurations are its rules.
    assert arch.domains.configs()["__main__"] == []
    names = arch.domains.configuration_names()
    assert names["__main__"] == ["8bits", "16bits", "32bits"]
    assert names["Regs"] == ["Off", "On"]


def test_a_negative_frequency_step_is_refused(tmp_path):
    arch = make(tmp_path)
    arch.settings.update({"fixed_freq_synthesis": {"lower_bound": 50, "upper_bound": 100, "step": -10}})
    resolved = arch.frequencies(mode="custom_freq")
    assert [message.level for message in resolved.messages] == ["error"]
    assert "strictly positive" in resolved.messages[0].text


def test_a_zero_frequency_step_means_no_range(tmp_path):
    arch = make(tmp_path)
    arch.settings.update({"fixed_freq_synthesis": {"list": [75], "lower_bound": 50, "upper_bound": 100, "step": 0}})
    resolved = arch.frequencies(mode="custom_freq")
    assert resolved.frequencies == [75]
    assert not resolved.messages
