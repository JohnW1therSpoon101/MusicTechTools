#!/usr/bin/env python3
"""
startdetails.py

Behavior:
  1) Opens getaudiofile1.py in a NEW TERMINAL WINDOW (picker UI with real TTY)
  2) Waits until the picker finishes and reads the selected path from a temp file
  3) Runs findtemp.py and findkey.py automatically on that path
  4) Works on both macOS and Windows; sets window/tab title to "getaudiofile1.py"
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from typing import Optional, List

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
    picker = first_existing([os.path.join(repo_root, "plumming", "getaudiofile1.py")])
    details_dir = first_existing([
        os.path.join(repo_root, "youtube2audwstems", "details"),
        os.path.join(repo_root, "link2stems", "details"),
    ])
    findtemp = os.path.join(details_dir, "findtemp.py") if details_dir else None
    findkey  = os.path.join(details_dir, "findkey.py")  if details_dir else None
    return picker, details_dir, findtemp, findkey

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

# ----------------- Picker launcher (external terminal with real TTY) -----------------
def launch_picker_in_new_terminal(picker_path: str) -> Optional[str]:
    """
    Launch getaudiofile1.py in an external terminal window with a real TTY.
    The picker writes the selected path into a temp file specified by
    the env var PICKER_OUTFILE. We poll that file from here.
    """
    log(f"[path] Found getaudiofile1.py: {picker_path}")

    tmp_output = os.path.join(os.path.dirname(__file__), "_selected_path.txt")
    try:
        if os.path.exists(tmp_output):
            os.remove(tmp_output)
    except Exception:
        pass

    if sys.platform.startswith("darwin"):
        # macOS Terminal.app: open a new tab/window, set the tab title via AppleScript,
        # export PICKER_OUTFILE, then run picker interactively with a real TTY.
        title = "getaudiofile1.py"
        picker_esc = picker_path.replace('"', '\\"')
        out_esc = tmp_output.replace('"', '\\"')

        # AppleScript avoids ANSI escapes; it directly sets the tab's custom title.
        # We run a simple bash command that exports the env var and runs the picker.
        # Note: use semicolons, not '&&', to keep it simple for AppleScript parsing.
        shell_cmd = f'export PICKER_OUTFILE=\\"{out_esc}\\"; python3 \\"{picker_esc}\\"'

        apple_script = (
            'tell application "Terminal"\n'
            f'    set newTab to do script "{shell_cmd}"\n'
            f'    delay 0.1\n'
            f'    set custom title of selected tab of front window to "{title}"\n'
            'end tell'
        )

        log("Launching picker in macOS Terminal (with title)…")
        subprocess.Popen(["osascript", "-e", apple_script])

    elif os.name == "nt":
        # Windows PowerShell: set title and env var, then run picker interactively in a new window
        title = "getaudiofile1.py"
        ps_cmd = (
            f"$host.UI.RawUI.WindowTitle = '{title}'; "
            f"$env:PICKER_OUTFILE = '{tmp_output}'; "
            f"python \"{picker_path}\"; "
            "exit"
        )
        log("Launching picker in Windows PowerShell (with title)…")
        subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_cmd], shell=True)

    else:
        # Fallback (Linux): try gnome-terminal/konsole/xterm; if none, run inline
        env = os.environ.copy()
        env["PICKER_OUTFILE"] = tmp_output
        for term in (("gnome-terminal", "--"), ("konsole", "-e"), ("xterm", "-e")):
            if subprocess.call(f"which {term[0]}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                log(f"Launching picker in {term[0]}…")
                subprocess.Popen([term[0], term[1], sys.executable, picker_path], env=env)
                break
        else:
            log("No external terminal detected; running picker inline (TTY required for curses).")
            subprocess.Popen([sys.executable, picker_path], env=env)

    # Poll for the output file written by the picker
    log("Waiting for picker to complete…")
    for _ in range(180):  # up to 3 minutes
        if os.path.exists(tmp_output):
            try:
                with open(tmp_output, "r", encoding="utf-8") as f:
                    path = f.read().strip()
            except Exception:
                path = ""
            if path:
                log(f"Picker selected: {path}")
                return path
        time.sleep(1)

    log("Picker timeout or no file selected.")
    return None

# ----------------- Main pipeline -----------------
def main():
    repo_root = repo_root_from_here()
    picker, details_dir, findtemp, findkey = find_paths(repo_root)

    if not picker:
        log("ERROR: getaudiofile1.py not found.")
        sys.exit(1)
    if not details_dir:
        log("ERROR: details folder missing (expected youtube2audwstems/details or link2stems/details).")
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
    selected_path = launch_picker_in_new_terminal(picker)
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