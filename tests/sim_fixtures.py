"""
Fixtures of the simulation tests.
"""

import os

import pytest

# The programs the simulation templates run, as their "test_command" names them
SIMULATOR_PROGRAMS = ("ghdl", "verilator", "vsim", "xelab", "iverilog")


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
        path = directory / name
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ.get("PATH", ""))
    return directory
