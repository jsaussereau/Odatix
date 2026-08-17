# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

"""
What each kind of run actually does.

Every run goes through the same three steps, but what it hands them differs: a
synthesis selects architectures and needs an eda tool, a simulation selects the
designs it runs on, a place & route starts from results another run produced.
One class per kind says what those differences are; :class:`odatix.run.Run` is
what a caller talks to.
"""

__all__ = ["Flow", "Checked", "flow_for", "FLOWS"]


class Checked(object):
    """
    What checking a run produced: the jobs it would run, and everything
    preparing them needs.
    """

    def __init__(self, instances, prepare_job, job_list, plan, exit_when_done, log_size_limit,
                 nb_jobs, handler=None, tool_settings_file=None):
        self.instances = instances
        self.prepare_job = prepare_job
        self.job_list = job_list
        self.plan = plan
        self.exit_when_done = exit_when_done
        self.log_size_limit = log_size_limit
        self.nb_jobs = nb_jobs
        self.handler = handler
        self.tool_settings_file = tool_settings_file


class Flow(object):
    """One kind of run, and how its three steps are called."""

    #: Name of the run, as :data:`odatix.workspace.JOB_MODES` knows it.
    mode = ""
    #: Path setting holding its run settings file.
    settings_file_setting = ""
    #: Path setting naming its sub-directory of the work directory.
    work_path_setting = ""
    #: Whether it runs jobs with an eda tool, which then has to be named.
    needs_tool = True

    def module(self):
        raise NotImplementedError

    def cancelled_exceptions(self):
        """What the flow raises when it is asked to stop."""
        cancelled = getattr(self.module(), "SynthesisCancelled", None)
        return (cancelled,) if cancelled is not None else ()

    ######################################
    # Where it works
    ######################################

    def settings_file(self, workspace):
        return getattr(workspace.paths, self.settings_file_setting)

    def work_path(self, workspace):
        return workspace.paths.under_work_path(self.work_path_setting)

    ######################################
    # The three steps
    ######################################

    def check(self, run):
        """Read what the run would do, without touching anything."""
        raise NotImplementedError

    def prepare(self, run, checked):
        """Write the work directory of every job, without starting any."""
        raise NotImplementedError

    def start(self, run, parallel_jobs):
        """
        Hand the jobs over to the daemon.

        Through the flow's own entry point when it has one: a flow is allowed to
        do something of its own once its jobs are enqueued.
        """
        start = getattr(self.module(), "start_parallel_jobs", None)
        if start is None:
            from odatix.components.run_common import start_parallel_jobs as start

        start(
            parallel_jobs,
            detach=run.options.detach,
            session=run.options.session,
            configure=run.options.configure_session,
        )

    ######################################
    # Reading what a step returned
    ######################################

    @staticmethod
    def _checked_with_handler(result):
        (instances, prepare_job, job_list, tool_settings_file, handler,
         exit_when_done, log_size_limit, nb_jobs, plan) = result
        return Checked(
            instances=instances, prepare_job=prepare_job, job_list=job_list, plan=plan,
            exit_when_done=exit_when_done, log_size_limit=log_size_limit, nb_jobs=nb_jobs,
            handler=handler, tool_settings_file=tool_settings_file,
        )

    @staticmethod
    def _checked_without_handler(result):
        instances, prepare_job, job_list, exit_when_done, log_size_limit, nb_jobs, plan = result
        return Checked(
            instances=instances, prepare_job=prepare_job, job_list=job_list, plan=plan,
            exit_when_done=exit_when_done, log_size_limit=log_size_limit, nb_jobs=nb_jobs,
        )

    def __repr__(self):
        return "<Flow {0}>".format(self.mode)


######################################
# Synthesis
######################################

class SynthesisFlow(Flow):
    """What an fmax synthesis and a custom frequency synthesis have in common."""

    def check(self, run):
        return Flow._checked_with_handler(self.module().check_settings(**self.check_arguments(run)))

    def check_arguments(self, run):
        options = run.options
        return dict(
            run_config_settings_filename=run.settings_file,
            arch_path=run.path("arch_path"),
            tool=options.tool,
            flow=options.flow,
            until_step=options.until,
            rerun_from_step=options.rerun_from,
            work_path=run.work_path,
            target_path=run.path("target_path"),
            selected_targets=options.targets,
            overwrite=options.overwrite,
            noask=options.noask,
            exit_when_done=options.exit_when_done,
            log_size_limit=options.log_size_limit,
            nb_jobs=options.nb_jobs,
            check_eda_tool=options.check_eda_tool,
            debug=options.debug,
            keep=options.keep,
            cancel_event=run.cancel_event,
            tool_check_sink=run.tool_check_sink,
        )

    def prepare(self, run, checked):
        return self.module().prepare_synthesis(
            architecture_instances=checked.instances,
            prepare_job=checked.prepare_job,
            job_list=checked.job_list,
            tool_settings_file=checked.tool_settings_file,
            arch_handler=checked.handler,
            exit_when_done=checked.exit_when_done,
            log_size_limit=checked.log_size_limit,
            nb_jobs=checked.nb_jobs,
            cancel_event=run.cancel_event,
            export_output_dir=run.result_path,
            export_tool=run.options.tool,
            export_flow=run.options.flow,
            export_work_path=run.work_path,
            use_benchmark=run.use_benchmark,
            benchmark_file=run.benchmark_file,
            custom_metrics_file=run.options.custom_metrics_file,
        )


class FmaxSynthesisFlow(SynthesisFlow):
    mode = "fmax_synthesis"
    settings_file_setting = "fmax_synthesis_settings_file"
    work_path_setting = "fmax_synthesis_work_path"

    def module(self):
        import odatix.components.run_fmax_synthesis as module

        return module

    def check_arguments(self, run):
        arguments = super(FmaxSynthesisFlow, self).check_arguments(run)
        arguments["continue_on_error"] = run.options.continue_on_error
        arguments["forced_fmax_lower_bound"] = run.options.lower_bound
        arguments["forced_fmax_upper_bound"] = run.options.upper_bound
        return arguments


class CustomFreqSynthesisFlow(SynthesisFlow):
    mode = "custom_freq_synthesis"
    settings_file_setting = "custom_freq_synthesis_settings_file"
    work_path_setting = "custom_freq_synthesis_work_path"

    def module(self):
        import odatix.components.run_custom_synthesis as module

        return module

    def check_arguments(self, run):
        arguments = super(CustomFreqSynthesisFlow, self).check_arguments(run)
        arguments["custom_freq_list"] = list(run.options.frequencies)
        return arguments


######################################
# Place & route
######################################

class PnrFlow(Flow):
    mode = "pnr"
    settings_file_setting = "pnr_settings_file"
    work_path_setting = "pnr_work_path"

    def module(self):
        import odatix.components.run_pnr as module

        return module

    def cancelled_exceptions(self):
        return (self.module().PnrCancelled,)

    def check(self, run):
        options = run.options
        return Flow._checked_with_handler(self.module().check_settings(
            run_config_settings_filename=run.settings_file,
            # A place & route starts from what other runs left in the work
            # directory, so it is handed the whole of it, not its own part.
            source_work_root=options.source_work_root or run.workspace.paths.work_path,
            tool=options.tool,
            flow=options.flow,
            until_step=options.until,
            rerun_from_step=options.rerun_from,
            work_path=run.work_path,
            target_path=run.path("target_path"),
            overwrite=options.overwrite,
            noask=options.noask,
            exit_when_done=options.exit_when_done,
            log_size_limit=options.log_size_limit,
            nb_jobs=options.nb_jobs,
            check_eda_tool=options.check_eda_tool,
            source_result_types=options.source_result_types,
            from_type=options.from_type,
            from_tool=options.from_tool,
            from_flow=options.from_flow,
            debug=options.debug,
            cancel_event=run.cancel_event,
            tool_check_sink=run.tool_check_sink,
        ))

    def prepare(self, run, checked):
        return self.module().prepare_pnr(
            architecture_instances=checked.instances,
            prepare_job=checked.prepare_job,
            job_list=checked.job_list,
            tool_settings_file=checked.tool_settings_file,
            arch_handler=checked.handler,
            exit_when_done=checked.exit_when_done,
            log_size_limit=checked.log_size_limit,
            nb_jobs=checked.nb_jobs,
            cancel_event=run.cancel_event,
            export_output_dir=run.result_path,
            export_tool=run.options.tool,
            export_flow=run.options.flow,
            export_work_path=run.work_path,
            use_benchmark=run.use_benchmark,
            benchmark_file=run.benchmark_file,
            custom_metrics_file=run.options.custom_metrics_file,
        )


######################################
# RTL analysis
######################################

class AnalysisFlow(Flow):
    mode = "analysis"
    settings_file_setting = "analysis_settings_file"
    work_path_setting = "analysis_work_path"

    def module(self):
        import odatix.components.run_analysis as module

        return module

    def cancelled_exceptions(self):
        return (self.module().AnalysisCancelled,)

    def tools(self, run):
        """An analysis runs one or several tools, and reports one summary each."""
        tool = run.options.tool
        return list(tool) if isinstance(tool, (list, tuple)) else [tool]

    def check(self, run):
        options = run.options
        self._flows = self.module().parse_flow_selection(options.flow, self.tools(run))
        return Flow._checked_with_handler(self.module().check_settings(
            run_config_settings_filename=run.settings_file,
            arch_path=run.path("arch_path"),
            tool=self.tools(run),
            work_path=run.work_path,
            target_path=run.path("target_path"),
            overwrite=options.overwrite,
            noask=options.noask,
            exit_when_done=options.exit_when_done,
            log_size_limit=options.log_size_limit,
            nb_jobs=options.nb_jobs,
            check_eda_tool=options.check_eda_tool,
            debug=options.debug,
            keep=options.keep,
            cancel_event=run.cancel_event,
            tool_check_sink=run.tool_check_sink,
            flows=self._flows,
        ))

    def prepare(self, run, checked):
        return self.module().prepare_synthesis(
            architecture_instances=checked.instances,
            prepare_job=checked.prepare_job,
            job_list=checked.job_list,
            tool_settings_file=checked.tool_settings_file,
            arch_handler=checked.handler,
            exit_when_done=checked.exit_when_done,
            log_size_limit=checked.log_size_limit,
            nb_jobs=checked.nb_jobs,
            cancel_event=run.cancel_event,
            export_output_dir=run.result_path,
            analysis_work_root=run.work_path,
            flows=getattr(self, "_flows", None),
        )


######################################
# Simulations and workflows
######################################

class SimulationFlow(Flow):
    mode = "simulation"
    settings_file_setting = "simulation_settings_file"
    work_path_setting = "simulation_work_path"
    needs_tool = False

    def module(self):
        import odatix.components.run_simulations as module

        return module

    def cancelled_exceptions(self):
        return ()

    def check(self, run):
        options = run.options
        return Flow._checked_without_handler(self.module().check_settings(
            run_config_settings_filename=run.settings_file,
            arch_path=run.path("arch_path"),
            sim_path=run.path("sim_path"),
            work_path=run.work_path,
            overwrite=options.overwrite,
            noask=options.noask,
            exit_when_done=options.exit_when_done,
            log_size_limit=options.log_size_limit,
            nb_jobs=options.nb_jobs,
            debug=options.debug,
            keep=options.keep,
        ))

    def prepare(self, run, checked):
        arguments = dict(
            simulation_instances=checked.instances,
            prepare_job=checked.prepare_job,
            job_list=checked.job_list,
            exit_when_done=checked.exit_when_done,
            log_size_limit=checked.log_size_limit,
            nb_jobs=checked.nb_jobs,
            resume=run.options.resume,
            export_output_dir=run.result_path,
            export_work_root=run.work_path,
            export_sim_path=run.path("sim_path"),
        )
        if run.options.output_filename:
            arguments["export_output_filename"] = run.options.output_filename
        return self.module().prepare_simulations(**arguments)


class WorkflowFlow(Flow):
    mode = "workflow"
    settings_file_setting = "workflow_settings_file"
    work_path_setting = "workflow_work_path"
    needs_tool = False

    def module(self):
        import odatix.components.run_workflow as module

        return module

    def cancelled_exceptions(self):
        return ()

    def check(self, run):
        options = run.options
        return Flow._checked_without_handler(self.module().check_settings(
            run_config_settings_filename=run.settings_file,
            workflow_path=run.path("workflow_path"),
            work_path=run.work_path,
            overwrite=options.overwrite,
            noask=options.noask,
            exit_when_done=options.exit_when_done,
            log_size_limit=options.log_size_limit,
            nb_jobs=options.nb_jobs,
            debug=options.debug,
            keep=options.keep,
        ))

    def prepare(self, run, checked):
        arguments = dict(
            workflow_instances=checked.instances,
            prepare_job=checked.prepare_job,
            job_list=checked.job_list,
            exit_when_done=checked.exit_when_done,
            log_size_limit=checked.log_size_limit,
            nb_jobs=checked.nb_jobs,
            resume=run.options.resume,
            export_output_dir=run.result_path,
            export_work_root=run.work_path,
            export_workflow_path=run.path("workflow_path"),
        )
        if run.options.output_filename:
            arguments["export_output_filename"] = run.options.output_filename
        return self.module().prepare_workflows(**arguments)


#: Every kind of run, by the name :data:`odatix.workspace.JOB_MODES` gives it.
FLOWS = {
    "fmax_synthesis": FmaxSynthesisFlow,
    "custom_freq_synthesis": CustomFreqSynthesisFlow,
    "pnr": PnrFlow,
    "analysis": AnalysisFlow,
    "simulation": SimulationFlow,
    "workflow": WorkflowFlow,
}


def flow_for(mode):
    """The flow of a run mode, whichever of its names is used."""
    from odatix.workspace.jobs import resolve_mode

    return FLOWS[resolve_mode(mode)]()
