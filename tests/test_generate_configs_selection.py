"""
D-12, D-18: "odatix generate" can be pointed at one architecture, and only says
"Generated" for what it actually changed.
"""

import os
from types import SimpleNamespace

import pytest

from odatix.components import generate_configs
from odatix.components.generate_configs import collect_configs, write_configs

SETTINGS = """\
use_parameters: true
start_delimiter: "#("
stop_delimiter: ")("
configurations:
  name: "${WIDTH}bits"
  template: "parameter WIDTH = $WIDTH"
variables:
  WIDTH:
    type: list
    settings:
      list: [8, 16]
"""


@pytest.fixture
def tree(tmp_path):
    for arch in ("MyAdder", "Other"):
        (tmp_path / "architectures" / arch).mkdir(parents=True)
        (tmp_path / "architectures" / arch / "_settings.yml").write_text(SETTINGS)
    (tmp_path / "workflows").mkdir()
    return tmp_path


def names(paths):
    return sorted(os.path.relpath(path).split(os.sep)[-2] + "/" + os.path.basename(path) for path in paths)


def test_one_architecture_only(tree, monkeypatch):
    monkeypatch.chdir(tree)
    plan = collect_configs("architectures", overwrite=False, entries=["MyAdder"])
    assert names(plan.new) == ["MyAdder/16bits.txt", "MyAdder/8bits.txt"]


def test_a_pattern_of_architectures(tree, monkeypatch):
    monkeypatch.chdir(tree)
    plan = collect_configs("architectures", overwrite=False, entries=["My*"])
    assert all("/MyAdder/" in "/" + path + "/" for path in plan.new)
    assert len(plan.new) == 2


def test_an_up_to_date_file_is_not_said_to_be_generated(tree, monkeypatch, capsys):
    monkeypatch.chdir(tree)
    write_configs(collect_configs("architectures", overwrite=False).valid)
    capsys.readouterr()
    plan = collect_configs("architectures", overwrite=False)
    write_configs(plan.valid, changed=set(plan.new + plan.overwrite))
    assert "Generated" not in capsys.readouterr().out


def test_the_command_takes_an_architecture(tree, monkeypatch):
    monkeypatch.chdir(tree)
    settings = SimpleNamespace(valid=True, arch_path="architectures", workflow_path="workflows")
    args = SimpleNamespace(
        overwrite=False, clean=False, noask=True, debug=False, arch_path=None, workflow_path=None,
        architectures=["MyAdder/*"],
    )
    generate_configs.main(args, settings=settings)
    assert (tree / "architectures" / "MyAdder" / "8bits.txt").exists()
    assert not (tree / "architectures" / "Other" / "8bits.txt").exists()


def test_an_unknown_architecture_is_an_error(tree, monkeypatch):
    monkeypatch.chdir(tree)
    settings = SimpleNamespace(valid=True, arch_path="architectures", workflow_path="workflows")
    args = SimpleNamespace(
        overwrite=False, clean=False, noask=True, debug=False, arch_path=None, workflow_path=None,
        architectures=["Nope"],
    )
    with pytest.raises(SystemExit):
        generate_configs.main(args, settings=settings)
