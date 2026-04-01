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

import time

def read_pipe_windows(pipe, job):
    while True:
        try:
            data = pipe.readline()
            if not data:
                break
            job.log_history.append(data)
            if job.log_size_limit != -1 and len(job.log_history) > job.log_size_limit:
                job.log_history = job.log_history[-job.log_size_limit:]
            job.log_changed = True
        except OSError:
            break

def get_elapsed_time_str(job_start_time, job_stop_time):
    if job_start_time is not None:
        if job_stop_time is not None:
            stop_time = job_stop_time
        else:
            stop_time = time.time()
        elapsed_seconds = int(stop_time - job_start_time)
        days = elapsed_seconds // 86400
        hours = (elapsed_seconds % 86400) // 3600
        minutes = (elapsed_seconds % 3600) // 60
        seconds = elapsed_seconds % 60
        if days > 0:
            elapsed_time = f"{days}d+{hours:02}:{minutes:02}" # Format Days+HH:MM
        else:
            elapsed_time = f"{hours:02}:{minutes:02}:{seconds:02}" # Format HH:MM:SS
    else:
        elapsed_time = "00:00:00"
    return elapsed_time
