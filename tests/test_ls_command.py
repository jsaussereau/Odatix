"""
"odatix ls": what the workspace holds, filtered by kind and by name.
"""

import json

from odatix import odatix_main


def run_ls(capsys, *argv):
    args = odatix_main.ArgParser.parse_arguments(["ls"] + list(argv))
    assert odatix_main.ls_command.main(args)
    return capsys.readouterr().out


def test_lists_the_three_kinds_by_default(example_workspace, capsys):
    listing = json.loads(run_ls(capsys, "--json"))
    assert set(listing) == {"architectures", "simulations", "workflows"}
    assert listing["architectures"] and "configurations" not in listing["architectures"][0]


def test_kind_options_and_patterns_filter(example_workspace, capsys):
    listing = json.loads(run_ls(capsys, "--json", "--arch", "Example_Counter*"))
    assert list(listing) == ["architectures"]
    names = [item["name"] for item in listing["architectures"]]
    assert names and all(name.startswith("Example_Counter") for name in names)


def test_all_adds_the_configurations(example_workspace, capsys):
    listing = json.loads(run_ls(capsys, "--json", "-a", "--arch"))
    with_configs = [item for item in listing["architectures"] if item["configurations"]]
    assert with_configs
    item = with_configs[0]
    assert item["name"] in item["configurations"] or item["configurations"]
    out = run_ls(capsys, "-a", "--arch", item["name"])
    first_config = next(iter(item["configurations"].values()))[0]
    assert first_config in out


def test_outside_a_workspace_is_a_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    args = odatix_main.ArgParser.parse_arguments(["ls"])
    assert not odatix_main.ls_command.main(args)
