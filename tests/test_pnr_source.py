"""Tests for PnR source discovery, matching and job enumeration."""

from types import SimpleNamespace

import odatix.lib.hard_settings as hard_settings
import odatix.lib.pnr_handler as pnr_handler
import odatix.lib.pnr_source as pnr_source


def _completed_source(tmp_path, frequency="100MHz"):
    job_dir = tmp_path / "custom_freq_synthesis" / "vivado@timing" / "xc7" / "counter" / "fast" / frequency
    result_dir = job_dir / hard_settings.work_result_path
    log_dir = job_dir / hard_settings.work_log_path
    result_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    (log_dir / hard_settings.synth_status_filename).write_text(hard_settings.valid_status)
    for filename in (hard_settings.pnr_netlist_filename, hard_settings.pnr_sdc_filename, hard_settings.pnr_sdf_filename):
        (result_dir / filename).write_text("handoff")
    return job_dir


def test_discovers_completed_source_with_handoff_and_matches_wildcards(tmp_path):
    _completed_source(tmp_path)

    sources = pnr_source.discover_sources(str(tmp_path))

    assert [source.selector for source in sources] == ["custom_freq_synthesis/vivado@timing/xc7/counter/fast@100MHz"]
    assert sources[0].frequency == 100
    assert pnr_source.match_sources(sources, ["custom_freq_synthesis/*/xc7/*/*@100MHz"], report_unmatched=False) == sources


def test_discovery_excludes_incomplete_handoffs_but_can_list_them_for_the_gui(tmp_path):
    job_dir = _completed_source(tmp_path)
    (job_dir / hard_settings.work_result_path / hard_settings.pnr_sdf_filename).unlink()

    assert pnr_source.discover_sources(str(tmp_path)) == []
    assert len(pnr_source.discover_sources(str(tmp_path), require_handoff=False)) == 1
    assert pnr_source.parse_selector("broken/selector") is None


def test_pnr_handler_turns_a_source_into_a_parameter_free_job(tmp_path, monkeypatch):
    job_dir = _completed_source(tmp_path)
    source = pnr_source.discover_sources(str(tmp_path))[0]
    settings_file = job_dir / hard_settings.yaml_config_filename
    settings_file.write_text("placeholder")
    source_architecture = SimpleNamespace(install_path="synth-install", constraint_filename="synth.sdc")
    monkeypatch.setattr(pnr_handler.Architecture, "read_yaml", staticmethod(lambda _: source_architecture))

    handler = pnr_handler.PnrJobHandler(
        work_path="pnr-work", source_work_root=str(tmp_path), script_path="scripts",
        work_rtl_path="rtl", work_script_path="scripts", work_log_path="logs", work_report_path="reports",
        process_group=True, command="run-pnr", eda_target_filename="targets.yml", overwrite=False,
    )
    monkeypatch.setattr(handler, "classify_job", lambda *args, **kwargs: ("new", None))

    instance = handler._build_instance(source, targets=["xc7"], install_path="pnr-install", constraint_filename="pnr.sdc")

    assert instance is not None
    assert instance.pnr_source is source
    assert instance.use_parameters is False
    assert instance.param_domains == []
    assert instance.install_path == "pnr-install"
    assert instance.tmp_dir.endswith("vivado@timing/xc7/counter/fast/100MHz")