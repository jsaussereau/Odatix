"""
Fixtures of the simulation tests.
"""

import os

import pytest

# The programs the simulation templates run, as their "test_command" names them
SIMULATOR_PROGRAMS = ("ghdl", "verilator", "vsim", "xelab", "iverilog")


def fake_program(directory, name):
    """
    The file of a fake program: Windows only finds one with an extension of
    PATHEXT, and runs a batch file rather than a shell script.
    """
    return directory / (name + ".cmd" if os.name == "nt" else name)


def write_fake_program(directory, name, exit_code=0):
    """A program doing nothing but exiting with `exit_code`."""
    path = fake_program(directory, name)
    if os.name == "nt":
        path.write_text("@exit /b {0}\r\n".format(exit_code), encoding="utf-8")
    else:
        path.write_text("#!/bin/sh\nexit {0}\n".format(exit_code), encoding="utf-8")
        path.chmod(0o755)
    return path


@pytest.fixture
def fake_simulators(tmp_path_factory, monkeypatch):
    """
    Every simulator a template runs, as a program doing nothing at the head of
    the PATH: checking a run refuses a simulator that is not installed, and
    what is tested here is the check, not the simulators. Not for a test that
    runs a simulation.
    """
    directory = tmp_path_factory.mktemp("fake_simulators")
    for name in SIMULATOR_PROGRAMS:
        write_fake_program(directory, name)
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ.get("PATH", ""))
    return directory
