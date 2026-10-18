"""
Build the virtual environment every job of the example shares, with the
python given on the command line, unless a job already built it.

The jobs of a run start together: the first one to take the lock builds the
environment while the others wait, then find it ready and do nothing.
"""

import fcntl
import os
import subprocess
import sys

ENV = "/tmp/odatix_tensorflow_example_env"
READY = os.path.join(ENV, "ready")  # the file the task is named after

python = sys.argv[1] if len(sys.argv) > 1 else "python3"

with open(ENV + ".lock", "w") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    if os.path.isfile(READY):
        print("Virtual environment already built.")
        sys.exit(0)

    env_python = os.path.join(ENV, "bin", "python3")
    subprocess.check_call([python, "-m", "venv", "--clear", ENV])
    subprocess.check_call([env_python, "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([env_python, "-m", "pip", "install", "tensorflow"])
    open(READY, "w").close()
    print("Virtual environment built with " + python + ".")
