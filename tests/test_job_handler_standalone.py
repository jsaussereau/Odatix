"""
Odatix runs its jobs with jobtender, which knows nothing of Odatix: what
Odatix plugs into it (odatix/jobs_plugin.py), and the former package name
(odatix.lib.parallel_job_handler), which is jobtender under another name.
"""

import pytest

import jobtender
from jobtender import config, plugins


class TestFormerName:
    def test_each_module_is_the_jobtender_one(self):
        import odatix.lib.parallel_job_handler.handler_core as former_core
        from odatix.lib.parallel_job_handler import daemon_control as former_control
        import jobtender.daemon_control
        import jobtender.handler_core

        assert former_core is jobtender.handler_core
        assert former_control is jobtender.daemon_control

    def test_the_package_exports_what_it_did(self):
        from odatix.lib.parallel_job_handler import ParallelJob, ParallelJobHandler, Theme

        assert ParallelJob is jobtender.ParallelJob
        assert ParallelJobHandler is jobtender.ParallelJobHandler
        assert Theme is jobtender.Theme

    def test_the_utilities_are_shared(self):
        import odatix.lib.printc as printc
        import jobtender._vendor.printc

        assert printc is jobtender._vendor.printc

    def test_a_missing_module_is_still_an_import_error(self):
        with pytest.raises(ImportError):
            import odatix.lib.parallel_job_handler.no_such_module  # noqa: F401


class TestOdatixPlugin:
    def test_odatix_configures_its_sessions(self):
        assert config.CONFIG.state_dirname == ".odatix_sessions"
        assert config.CONFIG.workspace_marker == "odatix.yml"
        assert config.CONFIG.env_var("DAEMON_TOKEN") == "ODATIX_DAEMON_TOKEN"
        assert "odatix.jobs_plugin" in config.CONFIG.plugins
        assert "odatix.jobs_plugin" in plugins.loaded()

    def test_the_hints_name_the_odatix_commands(self):
        from jobtender import daemon_control

        assert config.command("list") == "odatix ps"
        assert config.command("start", "--expose") == "odatix daemon --expose"
        assert daemon_control.follow_hint("x") == (
            'follow the jobs with "odatix monitor -S x" from a full terminal, "odatix ps", '
            "or the Monitor page of odatix-gui"
        )

    def test_sessions_started_under_the_former_name_are_found(self):
        from jobtender import daemon_control

        assert daemon_control._is_daemon_server_process(
            ["python", "-m", "odatix.lib.parallel_job_handler.daemon_server", "--state-file", "x"])
        assert daemon_control._is_daemon_server_process(["python", "-m", "jobtender.daemon_server"])

    @pytest.mark.parametrize("kind", ["synthesis", "workflow", "simulation", "analysis"])
    def test_every_export_has_a_handler(self, kind):
        assert plugins.post_run_handler(kind) is not None
        assert plugins.post_run_handler(kind.upper()) is not None

    def test_the_batch_action_and_the_fmax_progress_have_handlers(self):
        assert plugins.post_batch_handler("derived_metrics") is not None
        assert plugins.progress_handler("fmax") is not None

    def test_the_services_odatix_provides(self):
        for name in ("export_buffer", "step_store", "version", "resource_guard_defaults", "daemon_pythonpath"):
            assert plugins.service(name) is not None, name

    def test_an_unknown_name_has_no_handler(self):
        assert plugins.post_run_handler("nothing") is None
        assert plugins.post_batch_handler("") is None
