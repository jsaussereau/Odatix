"""2nd new-user pass, terminal & sessions fixes (SE-*, UX-*, SIM-101, GS-20/21, AP-01/17/19)."""
import types

from odatix.lib import printc
from odatix.lib.parallel_job_handler import curses_ui, daemon_control, daemon_monitor
from odatix.lib.parallel_job_handler.handler_core import ParallelJobHandler
from odatix.lib.parallel_job_handler.job_status import RUNNING_STATUSES


def _layout(width, label="858311.r2_sessions_a", paused=1):
    return curses_ui.header_layout(width, "4.0.0", 2, "on (1 paused)", "on",
                                   curses_ui._job_counts_texts(2, 4, 1, paused), label)


def test_header_never_overlaps_and_keeps_counts_and_guard():
    for width in range(40, 251):
        left, right, title_x = _layout(width)
        assert 1 + len(left) < width - 1 - len(right)
        if title_x is not None:
            assert title_x >= 1 + len(left) + 2 and title_x + 8 <= width - 1 - len(right) - 2
        if width >= 80:
            assert "auto-pause" in left and "paused" in right and "session" in left


def test_exporting_job_is_running_not_over():
    assert "exporting" in RUNNING_STATUSES
    h = ParallelJobHandler([], format_yaml="")
    h.job_list = [types.SimpleNamespace(status=s) for s in ("exporting", "paused", "success")]
    c = h.runtime_counts()
    assert (c["running"], c["paused"], c["retired"]) == (1, 1, 1)


def test_guard_never_pauses_the_last_running_job(monkeypatch):
    import sys
    from odatix.lib.parallel_job_handler import handler_core
    monkeypatch.setattr(handler_core, "_resource_guard_unavailable", [None])
    ps = types.ModuleType("psutil")
    ps.cpu_percent = lambda interval=None: 99.0
    ps.virtual_memory = lambda: types.SimpleNamespace(percent=10.0)
    monkeypatch.setitem(sys.modules, "psutil", ps)
    h = ParallelJobHandler([], resource_guard=True, cpu_limit=90, resource_check_interval=0.0)
    job = types.SimpleNamespace(status="running", takes_a_slot=True, pause=lambda **k: setattr(job, "status", "paused"))
    h.running_job_list = [job]
    for _ in range(5):
        h._resource_guard_last_check = 0
        h._check_resource_guard_unlocked()
    assert job.status == "running"


def test_console_log_has_no_tags_nor_colors():
    h = ParallelJobHandler([], format_yaml="")
    job = types.SimpleNamespace()
    out = h._plain_console_text(job, "<grey>[a]<end> <cy") + h._plain_console_text(job, "an>x\x1b[91my\x1b[0m\n")
    assert out == "[a] xy\n"


def test_prefix_is_odatix_not_a_module(capsys):
    printc.error("x", "run_settings.py")
    assert "[odatix]" in capsys.readouterr().out


def test_gui_sessions_are_named_gui():
    daemon_control.set_session_origin("gui")
    try:
        assert daemon_control._generate_default_session_name("h").startswith("gui.")
    finally:
        daemon_control.set_session_origin(None)


def test_exit_messages_say_how_to_reattach():
    e = daemon_monitor.MonitorExit("detach", {"total": 3, "retired": 1}, "12.s")
    assert 'odatix monitor -S 12.s' in daemon_monitor.exit_messages(e)[0][1]


def test_q_prompt_offers_detach_before_kill():
    parts = curses_ui.exit_prompt_parts(80, True)
    text = "".join(t for t, _ in parts)
    assert len(text) < 80 and text.index("d") < text.index("k")


def test_enqueue_reply_gives_the_run_job_ids():
    assert daemon_control.session_job_ids({"job_ids": [4, 5]}, 2) == [4, 5]
    assert daemon_control.session_job_ids({"total_jobs": 6}, 2) == [4, 5]
