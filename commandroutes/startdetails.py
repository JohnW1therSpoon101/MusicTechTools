#!/usr/bin/env python3
"""
startdetails.py

Behavior:
  1) Opens getaudiofile1.py in a NEW TERMINAL WINDOW (picker UI with real TTY)
  2) Waits until the picker finishes and reads the selected path from a temp file
  3) Runs findtemp.py and findkey.py automatically on that path
  4) Works on both macOS and Windows; sets window/tab title to "getaudiofile1.py"

Anti-duplication:
  - Uses a single-launch guard (_picker_launched.flag). If an instance has
    already launched a picker recently and no selection has been produced yet,
    we DO NOT launch another terminal; we just wait for the existing one.
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from typing import Optional, List

# ----------------- Tunables -----------------
PICKER_WAIT_SECONDS = 300         # max 5 minutes waiting for selection
LAUNCH_FLAG_TTL_SECONDS = 300     # flag considered "fresh" for 5 minutes

# ----------------- Logging helpers -----------------
def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg: str) -> None:
    print(f"[{now()}] {msg}")

def hr() -> None:
    print("-" * 72)

# ----------------- Path discovery -----------------
def repo_root_from_here() -> str:
    here = os.path.abspath(__file__)
    return os.path.dirname(os.path.dirname(here))

def first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None

def find_paths(repo_root: str):
    """
    Find picker and details scripts across common repo layouts.
    We search both the repo_root and its parent for resiliency,
    and support details dirs: link2aws, link2stems, youtube2audwstems.
    """
    candidates_roots = [repo_root, os.path.dirname(repo_root)]

    # Picker script (plumming/getaudiofile1.py)
    picker_candidates: List[str] = []
    for root in candidates_roots:
        picker_candidates.append(os.path.join(root, "plumming", "getaudiofile1.py"))
    picker = first_existing(picker_candidates)

    # Details directory: try several known project names under both roots
    details_candidates: List[str] = []
    for root in candidates_roots:
        details_candidates.extend([
            os.path.join(root, "link2aws", "details"),
            os.path.join(root, "link2stems", "details"),
            os.path.join(root, "youtube2audwstems", "details"),
        ])
    details_dir = first_existing(details_candidates)

    findtemp = os.path.join(details_dir, "findtemp.py") if details_dir else None
    findkey  = os.path.join(details_dir, "findkey.py")  if details_dir else None

    return picker, details_dir, findtemp, findkey, picker_candidates, details_candidates

# ----------------- Subprocess helpers -----------------
def stream_subprocess(cmd, timeout=None):
    """Stream live output from a process."""
    proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    start = time.time()
    while True:
        if timeout and (time.time() - start) > timeout:
            proc.kill()
            log(f"Timeout reached for: {' '.join(cmd)}")
            return -1
        out = proc.stdout.readline() if proc.stdout else ""
        err = proc.stderr.readline() if proc.stderr else ""
        if out:
            print(out, end="")
        if err:
            sys.stderr.write(err)
        if out == "" and err == "" and proc.poll() is not None:
            break
    return proc.returncode or 0

# ----------------- Single-launch guard helpers -----------------
def marker_paths() -> tuple[str, str]:
    """Return (tmp_output_path, launch_flag_path) next to this script."""
    base_dir = os.path.dirname(__file__)
    tmp_output = os.path.join(base_dir, "_selected_path.txt")
    launch_flag = os.path.join(base_dir, "_picker_launched.flag")
    return tmp_output, launch_flag

def write_launch_flag(path: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"launched_at={int(time.time())}\n")
    except Exception:
        pass

def clear_launch_flag(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

def fresh_flag_exists(path: str, ttl_seconds: int) -> bool:
    if not os.path.exists(path):
        return False
    try:
        age = time.time() - os.path.getmtime(path)
        return age <= ttl_seconds
    except Exception:
        return False

# ----------------- Picker launcher (external terminal with real TTY) -----------------
def launch_picker_in_new_terminal(picker_path: str, tmp_output: str, launch_flag: str) -> None:
    """
    Launch getaudiofile1.py in an external terminal window with a real TTY.
    The picker writes the selected path into tmp_output (via env PICKER_OUTFILE).
    This function ONLY launches; it does not wait. The caller will poll tmp_output.
    """
    # Prepare: ensure tmp_output is clear; create/refresh the single-launch flag
    try:
        if os.path.exists(tmp_output):
            os.remove(tmp_output)
    except Exception:
        pass
    write_launch_flag(launch_flag)

    if sys.platform.startswith("darwin"):
        # macOS Terminal.app
        title = "getaudiofile1.py"
        picker_esc = picker_path.replace('"', '\\"')
        out_esc = tmp_output.replace('"', '\\"')
        shell_cmd = f'export PICKER_OUTFILE=\\"{out_esc}\\"; python3 \\"{picker_esc}\\"'
        apple_script = (
            'tell application "Terminal"\n'
            f'    set newTab to do script "{shell_cmd}"\n'
            f'    delay 0.1\n'
            f'    set custom title of selected tab of front window to "{title}"\n'
            '    activate\n'
            'end tell'
        )
        log("Launching picker in macOS Terminal (single-launch)…")
        subprocess.Popen(["osascript", "-e", apple_script])

    elif os.name == "nt":
        # Windows PowerShell
        title = "getaudiofile1.py"
        ps_cmd = (
            f"$host.UI.RawUI.WindowTitle = '{title}'; "
            f"$env:PICKER_OUTFILE = '{tmp_output}'; "
            f"python \"{picker_path}\"; "
            "exit"
        )
        log("Launching picker in Windows PowerShell (single-launch)…")
        subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_cmd], shell=True)

    else:
        # Fallback (Linux)
        env = os.environ.copy()
        env["PICKER_OUTFILE"] = tmp_output
        for term in (("gnome-terminal", "--"), ("konsole", "-e"), ("xterm", "-e")):
            if subprocess.call(f"which {term[0]}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                log(f"Launching picker in {term[0]} (single-launch)…")
                subprocess.Popen([term[0], term[1], sys.executable, picker_path], env=env)
                break
        else:
            log("No external terminal detected; running picker inline (TTY required for curses).")
            subprocess.Popen([sys.executable, picker_path], env=env)

def wait_for_picker_result(tmp_output: str, launch_flag: str, max_wait: int) -> Optional[str]:
    """Poll for the output file written by the picker; clear flag on success/timeout."""
    log("Waiting for picker to complete…")
    start = time.time()
    try:
        while True:
            if os.path.exists(tmp_output):
                try:
                    with open(tmp_output, "r", encoding="utf-8") as f:
                        path = f.read().strip()
                except Exception:
                    path = ""
                if path:
                    log(f"Picker selected: {path}")
                    clear_launch_flag(launch_flag)
                    return path
            if (time.time() - start) > max_wait:
                log("Picker timeout or no file selected.")
                clear_launch_flag(launch_flag)
                return None
            time.sleep(1)
    finally:
        # Safety: if something weird happens, don't leave a stale flag around for long
        if fresh_flag_exists(launch_flag, 2):  # if it was just recreated above, keep it
            pass

# ----------------- Main pipeline -----------------
def main():
    repo_root = repo_root_from_here()
    picker, details_dir, findtemp, findkey, picker_tried, details_tried = find_paths(repo_root)
    tmp_output, launch_flag = marker_paths()

    if not picker:
        log("ERROR: getaudiofile1.py not found.")
        log("Paths tried:")
        for p in picker_tried:
            log(f" - {p}")
        sys.exit(1)

    if not details_dir:
        log("ERROR: details folder missing.")
        log("Paths tried (searched repo root and its parent):")
        for p in details_tried:
            log(f" - {p}")
        log('Expected one of: link2aws/details, link2stems/details, youtube2audwstems/details')
        sys.exit(1)

    log(f"[path] Selected DETAILS_DIR: {details_dir}")
    if findtemp and os.path.exists(findtemp):
        log(f"[use] findtemp.py = {findtemp}")
    else:
        log("[use] findtemp.py = missing")
        findtemp = None
    if findkey and os.path.exists(findkey):
        log(f"[use] findkey.py = {findkey}")
    else:
        log("[use] findkey.py = missing")
        findkey = None

    hr()
    # ------- SINGLE-LAUNCH LOGIC -------
    if fresh_flag_exists(launch_flag, LAUNCH_FLAG_TTL_SECONDS):
        # A picker was already launched recently. Don't launch again; just wait.
        log("Detected recent picker launch; NOT opening another terminal.")
        if not os.path.exists(tmp_output):
            log("No selection yet; waiting for the existing picker…")
        selected_path = wait_for_picker_result(tmp_output, launch_flag, PICKER_WAIT_SECONDS)
    else:
        # No recent launch detected, so we launch exactly once.
        log(f"[path] Found getaudiofile1.py: {picker}")
        launch_picker_in_new_terminal(picker, tmp_output, launch_flag)
        selected_path = wait_for_picker_result(tmp_output, launch_flag, PICKER_WAIT_SECONDS)
    # -----------------------------------

    if not selected_path or not os.path.exists(selected_path):
        log("No valid file selected. Exiting.")
        sys.exit(0)

    hr()
    log(f"Selected file: {selected_path}")
    hr()

    # 1) Tempo detection
    if findtemp:
        log("Running findtemp.py (tempo detection)…")
        stream_subprocess([sys.executable, findtemp, selected_path], timeout=300)
    else:
        log("Skipping tempo detection (findtemp.py missing).")

    hr()

    # 2) Key detection
    if findkey:
        log("Running findkey.py (key detection)…")
        stream_subprocess([sys.executable, findkey, selected_path], timeout=600)
    else:
        log("Skipping key detection (findkey.py missing).")

    hr()
    log("Details analysis complete!")

if __name__ == "__main__":
    main()