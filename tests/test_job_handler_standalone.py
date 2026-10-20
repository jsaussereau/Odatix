"""
The job handler (odatix.lib.parallel_job_handler) depends on nothing of Odatix.

It is meant to leave this repository as a project of its own: everything it
needs from Odatix comes through its plugins (see plugins.py and
odatix/jobs_plugin.py), never through an import. These tests fail on the first
import of Odatix that comes back.
"""

import ast
import os
import subprocess
import sys
import textwrap

import pytest

import odatix.lib.parallel_job_handler as package
from odatix.lib.parallel_job_handler import config, plugins

PACKAGE_DIR = os.path.dirname(os.path.abspath(package.__file__))

#: Imports of Odatix still allowed, as (file relative to the package, module).
#: Empty: keep it that way.
ALLOWED = set()


def _package_files():
    for root, dirs, files in os.walk(PACKAGE_DIR):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in sorted(files):
            if name.endswith(".py"):
                path = os.path.join(root, name)
                yield os.path.relpath(path, PACKAGE_DIR).replace(os.sep, "/"), path


def _absolute_imports(path):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.lineno, node.module


class TestNoOdatixImport:
    def test_the_package_imports_nothing_of_odatix(self):
        found = []
        for relpath, path in _package_files():
            for lineno, module in _absolute_imports(path):
                if (module == "odatix" or module.startswith("odatix.")) and (relpath, module) not in ALLOWED:
                    found.append("{}:{}: {}".format(relpath, lineno, module))
        assert found == [], "\n".join(found)

    def test_it_does_not_name_its_own_location(self):
        """It refers to itself relatively, so that it can move out of odatix.lib."""
        found = []
        for relpath, path in _package_files():
            with open(path, encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    if "odatix.lib.parallel_job_handler" in line:
                        found.append("{}:{}".format(relpath, lineno))
        assert found == [], "\n".join(found)

    def test_it_imports_without_odatix_configuring_it(self, tmp_path):
        """
        Imported alone -- the package copied out of Odatix, as it will be on its
        own -- it starts with its own settings and no plugin.
        """
        target = tmp_path / "jobs"
        _copy_tree(PACKAGE_DIR, str(target))
        script = textwrap.dedent(
            """
            import sys
            import jobs
            from jobs import config, plugins, handler_core, daemon_control, daemon_server, daemon_monitor, api
            assert not any(name == "odatix" or name.startswith("odatix.") for name in sys.modules), sorted(
                name for name in sys.modules if name.startswith("odatix"))
            assert config.CONFIG.state_dirname == ".job_sessions"
            assert plugins.loaded() == []
            print("ok")
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(tmp_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=dict(os.environ, PYTHONPATH=str(tmp_path)),
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "ok"


def _copy_tree(source, destination):
    import shutil

    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__"))


class TestOdatixPlugin:
    def test_odatix_configures_its_sessions(self):
        assert config.CONFIG.state_dirname == ".odatix_sessions"
        assert "odatix.jobs_plugin" in config.CONFIG.plugins
        assert "odatix.jobs_plugin" in plugins.loaded()

    @pytest.mark.parametrize("kind", ["synthesis", "workflow", "simulation", "analysis"])
    def test_every_export_has_a_handler(self, kind):
        assert plugins.post_run_handler(kind) is not None
        assert plugins.post_run_handler(kind.upper()) is not None

    def test_the_batch_action_and_the_fmax_progress_have_handlers(self):
        assert plugins.post_batch_handler("derived_metrics") is not None
        assert plugins.progress_handler("fmax") is not None

    def test_the_services_odatix_provides(self):
        for name in plugins.SERVICES:
            assert plugins.service(name) is not None, name

    def test_an_unknown_name_has_no_handler(self):
        assert plugins.post_run_handler("nothing") is None
        assert plugins.post_batch_handler("") is None


class TestRegistry:
    def test_an_unknown_setting_is_an_error(self):
        with pytest.raises(AttributeError):
            config.configure(no_such_setting=1)

    def test_an_unknown_service_is_an_error(self):
        with pytest.raises(plugins.PluginError):
            plugins.register_service("no_such_service", object())

    def test_a_plugin_that_cannot_be_imported_says_which(self):
        with pytest.raises(plugins.PluginError, match="no_such_plugin_module"):
            plugins.load(["no_such_plugin_module"])
        assert "no_such_plugin_module" not in plugins.loaded()

    def test_a_handler_must_be_callable(self):
        with pytest.raises(plugins.PluginError):
            plugins.register_post_run("broken", "not a function")
