"""Focused regression tests for previously uncovered utility and export paths."""

from types import SimpleNamespace

import pytest

import odatix.components.clean as clean
import odatix.components.export_analysis as export_analysis
import odatix.gui.svg_to_dashsvg as svg_to_dashsvg
import odatix.lib.check_tool as check_tool
import odatix.lib.prepare_work as prepare_work
import odatix.lib.results_schema as results_schema


def test_edit_config_file_replaces_all_synthesis_settings(tmp_path):
    config = tmp_path / "settings.tcl"
    config.write_text(
        "\n".join("set {} old".format(name) for name in (
            "top_level_module", "top_level_file", "clock_signal", "reset_signal", "local_rtl_path",
            "tmp_path", "source_rtl_path", "source_arch_path", "constraints_file", "target_frequency",
            "fmax_lower_bound", "fmax_upper_bound", "lib_name", "continue_on_error", "single_thread",
        ))
    )
    arch = SimpleNamespace(
        tmp_dir=str(tmp_path / "work"), constraint_filename="constraints.sdc", top_level_module="top",
        top_level_filename="top.v", clock_signal="clk", reset_signal=None, local_rtl_path="local-rtl",
        rtl_path="source-rtl", arch_path="architectures", target_frequency=250, fmax_lower_bound=100,
        fmax_upper_bound=500, lib_name="lib", continue_on_error=True, force_single_thread=False,
    )

    prepare_work.edit_config_file(arch, str(config))

    content = config.read_text()
    assert "set top_level_module top" in content
    assert "set reset_signal \n" in content
    assert "set target_frequency 250" in content
    assert "set continue_on_error 1" in content
    assert "set single_thread 0" in content
    assert "constraints.sdc" in content


def test_edit_pnr_config_file_quotes_source_metadata(tmp_path):
    config = tmp_path / "pnr.tcl"
    config.write_text("\n".join("set {} old".format(name) for name in (
        "source_work_path", "source_tool", "source_flow", "source_type", "source_netlist", "source_sdc",
        "source_sdf", "constraints_file",
    )))
    source = SimpleNamespace(
        job_dir=str(tmp_path / "source with space"), tool="tool", flow=None, job_type="fmax_synthesis",
        netlist=str(tmp_path / "netlist.v"), sdc=str(tmp_path / "source.sdc"), sdf=str(tmp_path / "source.sdf"),
    )

    prepare_work.edit_pnr_config_file(None, source, str(config))

    content = config.read_text()
    assert 'set source_flow ""' in content
    assert 'set source_tool "tool"' in content
    assert 'set constraints_file "' in content
    assert "source.sdc\"" in content


def test_clean_removes_requested_files_and_refuses_dangerous_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "remove-me.txt").write_text("temporary")
    settings = tmp_path / "clean.yml"
    settings.write_text("remove_list:\n  - remove-me.txt\n")

    clean.clean(str(settings), quiet=True)
    clean.remove_path(".", force=False, quiet=True)

    assert not (tmp_path / "remove-me.txt").exists()
    assert tmp_path.exists()


def test_clean_rejects_a_malformed_remove_list(tmp_path):
    settings = tmp_path / "clean.yml"
    settings.write_text("remove_list: remove-me.txt\n")

    with pytest.raises(SystemExit):
        clean.clean(str(settings), quiet=True)


def test_tool_check_reports_success_and_the_last_failure_line():
    success = check_tool.ToolCheck("python", '"{}" -c "pass"'.format(check_tool.sys.executable), [], "")
    assert success.result() == (True, "")
    assert success.result() == (True, "")  # Result is cached after the process ends.

    failure = check_tool.ToolCheck(
        "python", '"{}" -c "import sys; print(\'first\', file=sys.stderr); print(\'last\', file=sys.stderr); sys.exit(2)"'.format(check_tool.sys.executable), [], "",
    )
    assert failure.result() == (False, "first\nlast")
    assert failure.failure_message().endswith(": last")


def test_svg_converter_normalizes_style_namespaces_and_classes(tmp_path):
    source = tmp_path / "icon.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" style="fill: #111; stroke-width: 2">'
        '<path class="icon" clip-rule="evenodd" data-id="x" style="stroke: #fff" d="M0 0"/>'
        "</svg>"
    )

    component = svg_to_dashsvg.svg_to_dashsvg(str(source)).to_plotly_json()
    child = component["props"]["children"][0].to_plotly_json()

    assert component["props"]["style"] == {"fill": "#111", "strokeWidth": "2"}
    assert child["props"]["className"] == "icon"
    assert child["props"]["clipRule"] == "evenodd"
    assert child["props"]["data-id"] == "x"


def test_analysis_export_upserts_records_and_tags_jobs(tmp_path):
    summary = {
        "results": [{
            "architecture": "counter/fast", "status": "WARNING", "errors": ["lint"],
            "blackbox_warnings": ["blackbox"], "error_count": 1, "warning_count": 2,
            "standard_warning_count": 1,
        }]
    }
    output = export_analysis.export_analysis_results(summary, str(tmp_path), "dummy", flow="standard")
    assert output is not None

    updated_summary = {"results": [{**summary["results"][0], "status": "PASSED", "error_count": 0}]}
    export_analysis.export_analysis_results(updated_summary, str(tmp_path), "dummy", flow="standard")
    records = results_schema.load_results_file(output).records
    assert len(records) == 1
    assert records[0]["meta"]["_status"] == "PASSED"
    assert records[0]["metrics"]["critical_warning_count"] == 1

    job = SimpleNamespace(tmp_dir=str(tmp_path / "work" / "dummy@standard" / "target" / "counter" / "fast"))
    handler = SimpleNamespace(job_list=[job, SimpleNamespace(tmp_dir=str(tmp_path / "outside"))])
    assert export_analysis.configure_analysis_job_exports(handler, analysis_work_root=tmp_path / "work", output_dir=tmp_path) == 1
    assert job.post_run_export["architecture"] == "counter/fast"
    assert job.post_run_export["flow"] == "standard"