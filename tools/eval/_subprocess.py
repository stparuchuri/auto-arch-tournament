"""subprocess.run replacement that kills the whole process group on timeout.

The gpt-5.5 effort sweep produced visible orphan trees: formal/run_all.sh
times out after 30 minutes, subprocess.TimeoutExpired fires, Python kills
the bash, and `make -j10 → sby → yosys-smtbmc → bitwuzla` reparent to
launchd and keep running with nobody waiting on them. Across a multi-hour
bench, the orphans pile up and starve the live evaluators of CPU.

run_pgroup() places the child in its own session (start_new_session=True)
so the whole tree shares one process-group id, then kills the group on
timeout. Existing TimeoutExpired handlers keep working — they see the
same exception with the same partial output, just a fully reaped tree.
"""
import os
import signal
import subprocess
from typing import Any


def run_pgroup(args, *, timeout=None, capture_output=False, text=False,
               cwd=None, env=None, check=False) -> subprocess.CompletedProcess:
    stdout = subprocess.PIPE if capture_output else None
    stderr = subprocess.PIPE if capture_output else None
    proc = subprocess.Popen(
        args, stdout=stdout, stderr=stderr, text=text,
        cwd=cwd, env=env, start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = (b"", b"") if not text else ("", "")
        raise subprocess.TimeoutExpired(
            cmd=args, timeout=timeout, output=out, stderr=err,
        ) from None
    rc = proc.returncode
    if check and rc != 0:
        raise subprocess.CalledProcessError(rc, args, output=out, stderr=err)
    return subprocess.CompletedProcess(args, rc, out, err)
