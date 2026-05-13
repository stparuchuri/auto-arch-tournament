"""subprocess.run replacement that kills the full descendant tree on timeout.

The gpt-5.5 effort sweep produced visible orphan trees: formal/run_all.sh
times out after 30 minutes, subprocess.TimeoutExpired fires, Python kills
the bash, and `make -j10 → sby → yosys-smtbmc → bitwuzla` reparent to
launchd and keep running with nobody waiting on them. Across a multi-hour
bench, the orphans pile up and starve the live evaluators of CPU.

A killpg-only fix is insufficient here: `sby_core.py` calls `os.setpgrp()`
per task, so each leaf bash/yosys-smtbmc/bitwuzla becomes its own
process-group leader and escapes the outer killpg. The PPID chain stays
intact though, so we walk descendants via psutil and SIGKILL each.
"""
import subprocess

import psutil


def _kill_descendant_tree(root_pid: int) -> None:
    """SIGKILL the descendant tree of root_pid (root itself NOT included).

    Snapshots descendants BEFORE killing — once we start sending signals,
    children die and get reaped, which would shrink the tree mid-walk."""
    try:
        root = psutil.Process(root_pid)
    except psutil.NoSuchProcess:
        return
    descendants = root.children(recursive=True)
    for child in descendants:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(descendants, timeout=2)


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
        _kill_descendant_tree(proc.pid)
        proc.kill()
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            out, err = (b"", b"") if not text else ("", "")
        raise subprocess.TimeoutExpired(
            cmd=args, timeout=timeout, output=out, stderr=err,
        ) from None
    rc = proc.returncode
    if check and rc != 0:
        raise subprocess.CalledProcessError(rc, args, output=out, stderr=err)
    return subprocess.CompletedProcess(args, rc, out, err)
