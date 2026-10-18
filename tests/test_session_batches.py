"""What a daemon session does once a batch it received is over.

The handler a run builds stays in the process of that run: a daemon session
only receives its jobs. Anything the run wants done after the batch (deriving
metrics from the records its jobs export) has to travel with the jobs.
"""

import pytest

import odatix.lib.parallel_job_handler.daemon_control as daemon_control
import odatix.lib.parallel_job_handler.handler_core as handler_core
from odatix.lib.parallel_job_handler.job import ParallelJob


ACTION = {"kind": "derived_metrics", "result_path": "/r", "derived_metrics_file": "/r/derived.yml"}


def _job(name="job"):
    return ParallelJob(
        process=None, command="echo test", directory="work", generate_rtl=False, generate_command="",
        target="target", arch="architecture", display_name=name, status_file="",
        progress_file="", tmp_dir="work", log_size_limit=100, status="idle",
    )


def _session_handler(monkeypatch, ran):
    handler = handler_core.ParallelJobHandler([], nb_jobs=2, format_yaml="")
    monkeypatch.setattr(handler, "_run_post_batch_action", lambda action=None: ran.append(action))
    monkeypatch.setattr(handler, "start_job", lambda job: handler.running_job_list.append(job))
    handler._headless_initialized = True
    return handler


class TestTheActionTravelsWithTheJobs:
    def test_enqueueing_sends_the_post_batch_action(self, monkeypatch):
        sent = {}
        monkeypatch.setattr(daemon_control, "ensure_daemon_running", lambda **kw: {"session_id": "1.s"})
        monkeypatch.setattr(
            daemon_control, "_api_request",
            lambda state, method, path, payload=None, **kw: sent.update(payload=payload) or {},
        )
        handler = handler_core.ParallelJobHandler([_job()], nb_jobs=1, format_yaml="")
        handler.post_batch_action = dict(ACTION)

        daemon_control.enqueue_parallel_jobs(handler, session="s")
        assert sent["payload"]["post_batch_action"] == ACTION

    def test_it_is_sent_even_to_a_session_left_unconfigured(self, monkeypatch):
        # An exploration adding a batch to its own session does not configure
        # it, but its batch still wants its metrics derived.
        sent = {}
        monkeypatch.setattr(daemon_control, "ensure_daemon_running", lambda **kw: {"session_id": "1.s"})
        monkeypatch.setattr(
            daemon_control, "_api_request",
            lambda state, method, path, payload=None, **kw: sent.update(payload=payload) or {},
        )
        handler = handler_core.ParallelJobHandler([_job()], nb_jobs=1, format_yaml="")
        handler.post_batch_action = dict(ACTION)

        daemon_control.enqueue_parallel_jobs(handler, session="s", configure=False)
        assert "options" not in sent["payload"]
        assert sent["payload"]["post_batch_action"] == ACTION

    def test_nothing_is_sent_without_an_action(self, monkeypatch):
        sent = {}
        monkeypatch.setattr(daemon_control, "ensure_daemon_running", lambda **kw: {"session_id": "1.s"})
        monkeypatch.setattr(
            daemon_control, "_api_request",
            lambda state, method, path, payload=None, **kw: sent.update(payload=payload) or {},
        )
        daemon_control.enqueue_parallel_jobs(handler_core.ParallelJobHandler([_job()], format_yaml=""), session="s")
        assert "post_batch_action" not in sent["payload"]

    def test_the_enqueue_endpoint_hands_it_to_the_session(self):
        pytest.importorskip("fastapi")
        from odatix.lib.parallel_job_handler.api import create_parallel_job_app
        from odatix.lib.parallel_job_handler.auth import ApiAuth
        from odatix.lib.parallel_job_handler.serialization import job_to_payload

        handler = handler_core.ParallelJobHandler([], nb_jobs=1, format_yaml="")
        received = []
        handler.add_post_batch_action = received.append
        app = create_parallel_job_app(
            handler, auth=ApiAuth(control_token="c", read_token="r"), start_headless_on_startup=False,
        )
        endpoint = [route.endpoint for route in app.routes if getattr(route, "path", "") == "/jobs/enqueue"][0]
        endpoint({"jobs": [job_to_payload(_job())], "post_batch_action": dict(ACTION)})

        assert received == [ACTION]
        assert len(handler.job_list) == 1


class TestTheSessionRunsIt:
    def test_once_the_batch_is_over(self, monkeypatch):
        ran = []
        handler = _session_handler(monkeypatch, ran)
        job = _job()
        handler.add_job(job)
        handler.add_post_batch_action(dict(ACTION))
        assert ran == []  # the batch is running

        handler.running_job_list.remove(job)
        handler._run_post_batch_action_if_drained()
        assert ran == [ACTION]

        # Once per batch: draining again does not run it again.
        handler._run_post_batch_action_if_drained()
        assert ran == [ACTION]

    def test_a_batch_already_over_runs_it_right_away(self, monkeypatch):
        ran = []
        handler = _session_handler(monkeypatch, ran)
        handler.add_post_batch_action(dict(ACTION))
        assert ran == [ACTION]

    def test_the_same_action_twice_runs_once(self, monkeypatch):
        ran = []
        handler = _session_handler(monkeypatch, ran)
        handler.add_job(_job())
        handler.add_post_batch_action(dict(ACTION))
        handler.add_post_batch_action(dict(ACTION))
        handler.running_job_list[:] = []
        handler._run_post_batch_action_if_drained()
        assert ran == [ACTION]

    def test_each_run_sharing_a_session_gets_its_own(self, monkeypatch):
        ran = []
        handler = _session_handler(monkeypatch, ran)
        other = dict(ACTION, result_path="/other")
        handler.add_job(_job("a"))
        handler.add_post_batch_action(dict(ACTION))
        handler.add_job(_job("b"))
        handler.add_post_batch_action(other)
        handler.running_job_list[:] = []
        handler._run_post_batch_action_if_drained()
        assert ran == [ACTION, other]

    def test_the_derivation_itself_is_applied(self, monkeypatch, tmp_path):
        import odatix.components.export_derived_metrics as exp_derived

        derived = tmp_path / "derived.yml"
        derived.write_text("{}")
        applied = []
        monkeypatch.setattr(exp_derived, "apply_derived_metrics", lambda *args: applied.append(args))
        handler = handler_core.ParallelJobHandler([], nb_jobs=1, format_yaml="")
        handler._headless_initialized = True
        handler.add_post_batch_action(
            {"kind": "derived_metrics", "result_path": str(tmp_path), "derived_metrics_file": str(derived)}
        )
        assert applied == [(str(tmp_path), str(derived))]


class TestLeavingJobsToSessions:
    """A simulation or a workflow already running in a session is not run twice."""

    def _plan(self, *names):
        from odatix.lib.run_report import JobPlan

        plan = JobPlan()
        for name in names:
            plan.add(name, "incomplete")
        return plan

    def _sessions(self, monkeypatch, jobs):
        import odatix.run.planner as planner

        monkeypatch.setattr(planner, "list_daemon_jobs", lambda workspace_root=None: list(jobs))

    def test_a_job_running_in_a_session_is_left_to_it(self, monkeypatch, tmp_path):
        from odatix.run.planner import leave_jobs_to_sessions

        running = str(tmp_path / "work" / "a")
        self._sessions(monkeypatch, [{"tmp_dir": running, "status": "running", "session_id": "1.alpha"}])
        plan = self._plan("slow/a", "slow/b")
        instances = [("slow/a", running), ("slow/b", str(tmp_path / "work" / "b"))]

        kept = leave_jobs_to_sessions(instances, plan, tmp_dir=lambda i: i[1], name=lambda i: i[0])

        assert kept == [instances[1]]
        assert plan.counts()["daemon"] == 1
        assert plan.run_count() == 1
        assert "1.alpha" in plan.names("daemon", colored=False)[0]

    def test_a_job_a_session_failed_is_run_again(self, monkeypatch, tmp_path):
        from odatix.run.planner import leave_jobs_to_sessions

        failed = str(tmp_path / "work" / "a")
        self._sessions(monkeypatch, [{"tmp_dir": failed, "status": "failed", "session_id": "1.alpha"}])
        plan = self._plan("slow/a")
        kept = leave_jobs_to_sessions([("slow/a", failed)], plan, tmp_dir=lambda i: i[1], name=lambda i: i[0])
        assert len(kept) == 1 and plan.run_count() == 1

    def test_without_sessions_everything_runs(self, monkeypatch, tmp_path):
        from odatix.run.planner import leave_jobs_to_sessions

        self._sessions(monkeypatch, [])
        plan = self._plan("slow/a")
        kept = leave_jobs_to_sessions([("slow/a", str(tmp_path))], plan, tmp_dir=lambda i: i[1], name=lambda i: i[0])
        assert len(kept) == 1
