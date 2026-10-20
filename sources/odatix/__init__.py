# Odatix runs its jobs with odatix.lib.parallel_job_handler, which knows nothing
# of Odatix: this registers what Odatix plugs into it, for every odatix process.
import odatix.jobs_plugin  # noqa: F401
