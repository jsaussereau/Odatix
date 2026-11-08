"""
Finding the running sessions by scanning processes, with and without /proc
(macOS has none: psutil reads the processes there).
"""

import os
import subprocess
import sys
import time

import pytest

import odatix.lib.parallel_job_handler.daemon_control as daemon_control

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="sessions are not found by scanning on Windows")


@pytest.fixture(params=["proc", "psutil"])
def scan(request, monkeypatch):
    if request.param == "proc":
        if not os.path.isdir("/proc"):
            pytest.skip("no /proc here")
    else:
        pytest.importorskip("psutil")
        real_isdir = os.path.isdir
        monkeypatch.setattr(daemon_control.os.path, "isdir", lambda path: path != "/proc" and real_isdir(path))
    return daemon_control._iter_system_daemon_candidates


def test_a_session_process_is_found(tmp_path, scan):
    state_file = tmp_path / ".odatix_sessions" / "s.json"
    # A stand-in with the command line of a session server: the scan only
    # reads command lines, so nothing needs to listen.
    script = tmp_path / "daemon_server.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    process = subprocess.Popen([sys.executable, str(script), "--state-file", str(state_file),
                                "--session-name", "s", "--port", "1234"], cwd=str(tmp_path))
    try:
        # Popen returns once exec has started, but the kernel fills the new
        # command line a moment later: until then it reads empty and the
        # process is (rightly) skipped. A real session has long been running.
        deadline = time.time() + 10
        found = []
        while not found and time.time() < deadline:
            found = [c for c in scan() if c["pid"] == process.pid]
            if not found:
                time.sleep(0.05)
    finally:
        process.kill()
        process.wait()

    assert len(found) == 1
    candidate = found[0]
    assert candidate["session_name"] == "s"
    assert candidate["port"] == 1234
    assert candidate["uid"] == os.getuid()
    assert candidate["workspace_root"] == os.path.realpath(str(tmp_path))
