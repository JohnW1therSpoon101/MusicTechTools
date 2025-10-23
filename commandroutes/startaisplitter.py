#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
startaisplitter.py — MusicTechTools

Flow:
  1) Launch getaudiofile2.py in a NEW terminal window (real TTY picker)
  2) Wait for the picker to write a temp file with the chosen path
  3) Ask user for splitter type: "1 = basic, 2 = fullsplitter" (robust TTY prompt)
  4) Ensure input is a .wav (auto-convert with ffmpeg if needed)
  5) Run checkpoint.py with CLI args/env
     • On macOS/Linux: run under a PTY and auto-answer:
         - "Paste absolute path to a .wav"  → send the .wav path once
         - "Type 1 or 2"                    → send "1" or "2" based on your choice

Logging:
  • Per-session log: logs/startaisplitterlog/YYYYMMDD_HHMMSS.log
"""

import os
import sys
import time
import shlex
import shutil
import subprocess
from datetime import datetime
from typing import Optional, List
import re  # cross-platform

# ----------------- logging -----------------
def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _date_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _script_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))

def _project_root_from_here() -> str:
    here = _script_dir()
    parent = os.path.abspath(os.path.join(here, os.pardir))
    return parent if os.path.basename(here).lower() == "commandroutes" else here

PROJECT_ROOT = _project_root_from_here()
LOG_DIR = os.path.join(PROJECT_ROOT, "logs", "startaisplitterlog")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, f"{_date_slug()}.log")

def log(msg: str) -> None:
    line = f"[{_timestamp()}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ----------------- OS helpers -----------------
def is_windows() -> bool:
    return os.name == "nt"

def is_macos() -> bool:
    return sys.platform == "darwin"

def abspath(*parts: str) -> str:
    return os.path.abspath(os.path.join(*parts))

def prompt_tty(prompt: str) -> str:
    """Always wait for input using the controlling TTY when needed."""
    try:
        if sys.stdin and sys.stdin.isatty():
            return input(prompt)
    except Exception:
        pass
    try:
        if is_windows():
            with open("CONIN$", "r") as tty_in:
                print(prompt, end="", flush=True)
                return tty_in.readline().strip()
        else:
            with open("/dev/tty", "r") as tty_in:
                print(prompt, end="", flush=True)
                return tty_in.readline().strip()
    except Exception:
        return ""

# ----------------- Locate files -----------------
def require_picker_path(base_dir: str) -> Optional[str]:
    """Require getaudiofile2.py (no legacy fallbacks)."""
    candidates = [
        abspath(base_dir, "getaudiofile2.py"),
        abspath(base_dir, "commandroutes", "getaudiofile2.py"),
        abspath(base_dir, os.pardir, "plumming", "getaudiofile2.py"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None

def candidate_checkpoint_paths(base_dir: str) -> List[str]:
    candidates = [
        abspath(base_dir, "checkpoint.py"),
        abspath(base_dir, "commandroutes", "checkpoint.py"),
        abspath(base_dir, os.pardir, "commandroutes", "checkpoint.py"),
    ]
    return [p for p in candidates if os.path.isfile(p)]

def candidate_temp_paths(project_root: str) -> List[str]:
    paths = []
    pr_tmp = abspath(project_root, ".tmp")
    os.makedirs(pr_tmp, exist_ok=True)
    paths.append(abspath(pr_tmp, "selected_audio_path.txt"))
    if is_macos():
        mac_tmp_root = abspath(os.path.expanduser("~/Library/Application Support/MusicTechTools/tmp"))
        os.makedirs(mac_tmp_root, exist_ok=True)
        paths.append(abspath(mac_tmp_root, "selected_audio_path.txt"))
    if is_windows():
        la = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        win_tmp_root = abspath(la, "MusicTechTools", "tmp")
        os.makedirs(win_tmp_root, exist_ok=True)
        paths.append(abspath(win_tmp_root, "selected_audio_path.txt"))
    paths.append("/tmp/musictechtools_selected_audio_path.txt")
    return paths

# ----------------- Launch picker in NEW TERMINAL -----------------
def launch_picker_new_terminal(picker_py: str, temp_path: str, working_dir: str) -> None:
    env_export = f'PICKER_TEMP_PATH={shlex.quote(temp_path)}'
    inner = (
        f'cd {shlex.quote(working_dir)}; '
        f'export {env_export}; '
        f'{shlex.quote(sys.executable)} {shlex.quote(picker_py)} --write-temp {shlex.quote(temp_path)}; '
        r'printf "\nDone. You can close this window.\n"; '
        'exec $SHELL'
    )
    log(f"Picker command (inner shell): {inner}")

    if is_macos():
        inner_as = inner.replace("\\", "\\\\").replace('"', '\\"')
        osa_script = (
            f'tell application "Terminal"\n'
            f'  activate\n'
            f'  do script "{inner_as}"\n'
            f'  set custom title of front window to "getaudiofile2.py"\n'
            f'end tell'
        )
        log("Launching macOS Terminal via AppleScript.")
        subprocess.Popen(["osascript", "-e", osa_script])
    elif is_windows():
        ps_inner = inner.replace('"', '\\"')
        ps_command = (
            f'$host.ui.RawUI.WindowTitle = "getaudiofile2.py"; '
            f'{ps_inner}; '
            'Write-Host ""; Write-Host "Done. You can close this window."; '
            'powershell -NoExit'
        )
        log("Launching Windows PowerShell via Start-Process.")
        subprocess.Popen([
            "powershell", "-NoProfile", "-Command",
            f'Start-Process powershell -ArgumentList \'-NoExit\', \'-Command\', "{ps_command}"'
        ])
    else:
        log("Launching picker via shell (no GUI terminal available).")
        subprocess.Popen(inner, shell=True)

# ----------------- WAV ensure/convert -----------------
def ensure_wav(selected_path: str) -> str:
    ext = os.path.splitext(selected_path)[1].lower()
    if ext == ".wav":
        log("Selected file is already a .wav.")
        return selected_path

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        log("WARN: ffmpeg not found; proceeding with original file (checkpoint may reprompt for .wav).")
        return selected_path

    base = os.path.splitext(os.path.basename(selected_path))[0]
    out_dir = abspath(PROJECT_ROOT, ".tmp")
    os.makedirs(out_dir, exist_ok=True)
    wav_out = abspath(out_dir, f"{base}.wav")

    log(f"Converting to WAV via ffmpeg:\n  IN:  {selected_path}\n  OUT: {wav_out}")
    cmd = [
        ffmpeg, "-y",
        "-i", selected_path,
        "-ac", "2",
        "-ar", "44100",
        "-sample_fmt", "s16",
        wav_out
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            log(f"ffmpeg failed (code {proc.returncode}). stderr:\n{proc.stderr.decode(errors='ignore')}")
            return selected_path  # fallback
        log("ffmpeg conversion successful.")
        return wav_out
    except Exception as e:
        log(f"ffmpeg error: {e}")
        return selected_path

# ----------------- PTY runner for checkpoint (POSIX) -----------------
PROMPT_PATTERNS_WAV = [
    re.compile(r"Paste absolute path to a \.wav", re.IGNORECASE),
    re.compile(r"paste.*path.*wav", re.IGNORECASE),
]

PROMPT_PATTERNS_MODE = [
    re.compile(r"CHECKPOINT", re.IGNORECASE),          # banner appears before prompt
    re.compile(r"Type\s+1\s+or\s+2", re.IGNORECASE),   # the actual prompt
]

def run_checkpoint_via_pty(args: List[str], cwd: Optional[str], env: dict, wav_line: str, mode_line: str) -> int:
    """
    Run checkpoint.py under a PTY (macOS/Linux), mirror output,
    and auto-answer two prompts exactly once each.
    """
    # Import POSIX-only modules lazily to avoid Windows import errors
    import pty, select, fcntl

    log("Running checkpoint under PTY (POSIX).")
    master_fd, slave_fd = pty.openpty()

    # Make PTY master non-blocking (smooth read loop)
    try:
        fl = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    except Exception:
        pass

    proc = subprocess.Popen(
        args,
        cwd=cwd or None,
        env=env,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        text=False,  # bytes mode; we'll decode
        close_fds=True
    )
    os.close(slave_fd)

    sent_wav = False
    sent_mode = False

    try:
        while True:
            rlist, _, _ = select.select([master_fd], [], [], 0.2)
            if master_fd in rlist:
                try:
                    chunk = os.read(master_fd, 4096)
                except BlockingIOError:
                    chunk = b""
                if chunk:
                    text = chunk.decode(errors="replace")
                    # echo to console
                    print(text, end="", flush=True)
                    # log to file
                    try:
                        with open(LOG_PATH, "a", encoding="utf-8") as f:
                            f.write(text)
                    except Exception:
                        pass

                    # Detect & answer WAV prompt once
                    if not sent_wav and any(rx.search(text) for rx in PROMPT_PATTERNS_WAV):
                        os.write(master_fd, (wav_line + "\n").encode())
                        log("PTY: answered WAV path prompt.")
                        sent_wav = True

                    # Detect & answer Mode prompt once
                    if not sent_mode and any(rx.search(text) for rx in PROMPT_PATTERNS_MODE):
                        if re.search(r"Type\s+1\s+or\s+2", text, re.IGNORECASE):
                            os.write(master_fd, (mode_line + "\n").encode())
                            log(f"PTY: answered mode prompt with '{mode_line}'.")
                            sent_mode = True

            if proc.poll() is not None:
                return proc.returncode
    finally:
        try:
            os.close(master_fd)
        except Exception:
            pass

# ----------------- Main -----------------
def main() -> int:
    log("== startaisplitter: init ==")
    log(f"Session log: {LOG_PATH}")
    project_root = PROJECT_ROOT

    # Require getaudiofile2.py
    picker_py = require_picker_path(project_root) or require_picker_path(_script_dir())
    log(f"Picker candidates (must be getaudiofile2.py): {picker_py}")
    if not picker_py:
        log("ERROR: getaudiofile2.py not found. Put it in one of:")
        log("  - commandroutes/ (next to this script)")
        log("  - project root")
        log("  - ../plumming/")
        return 2
    log(f"Using picker: {picker_py}")

    # checkpoint
    checkpoints = candidate_checkpoint_paths(project_root) or candidate_checkpoint_paths(_script_dir())
    log(f"Checkpoint candidates: {checkpoints}")
    if not checkpoints:
        log("ERROR: Could not find checkpoint.py in expected locations.")
        return 3
    checkpoint_py = checkpoints[0]
    log(f"Using checkpoint: {checkpoint_py}")

    # temp files
    watch_paths = candidate_temp_paths(project_root)
    temp_path = watch_paths[0]
    for p in watch_paths:
        try:
            if os.path.exists(p):
                os.remove(p)
                log(f"Cleared stale temp file: {p}")
        except Exception as e:
            log(f"WARN: Could not clear {p}: {e}")

    log("Opening picker in a new terminal window...")
    launch_picker_new_terminal(picker_py=picker_py, temp_path=temp_path, working_dir=project_root)

    log("Waiting for selection (getaudiofile2.py)...")
    log("Watching temp paths:\n  • " + "\n  • ".join(watch_paths))

    timeout_s = 60 * 10
    poll_interval = 0.4
    selected_path: Optional[str] = None
    waited = 0.0

    def read_candidate(p: str) -> Optional[str]:
        try:
            if os.path.exists(p) and os.path.getsize(p) > 0:
                with open(p, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
                if raw:
                    return raw.strip().strip('"')
        except Exception as e:
            log(f"WARN: reading {p} failed: {e}")
        return None

    while waited < timeout_s and not selected_path:
        for p in watch_paths:
            text = read_candidate(p)
            if text:
                selected_path = text
                log(f"Detected selection at: {p}")
                break
        if selected_path:
            break
        time.sleep(poll_interval)
        waited += poll_interval

    if not selected_path:
        log("ERROR: No file was selected (timeout waiting for picker).")
        log("Tip: Ensure getaudiofile2.py writes the absolute path to --write-temp or PICKER_TEMP_PATH.")
        return 4

    if not os.path.exists(selected_path):
        log(f"ERROR: Selected path does not exist: {selected_path}")
        return 5

    log(f"Selected file: {selected_path}")

    # Splitter prompt (reliable)
    print()
    print('splittertype')
    print('1 = basic, 2 = fullsplitter')
    choice = prompt_tty('Enter 1 or 2: ').strip()
    if choice not in {"1", "2"}:
        log("Invalid choice or no input. Defaulting to '1 = basic'.")
        choice = "1"
    splitter_type = "basic" if choice == "1" else "fullsplitter"
    log(f"Splitter type: {splitter_type}")
    mode_line = "1" if splitter_type == "basic" else "2"

    # Ensure WAV path
    wav_input = ensure_wav(selected_path)
    if not os.path.exists(wav_input):
        log(f"ERROR: Expected input file not found: {wav_input}")
        return 5

    # Launch checkpoint
    env = os.environ.copy()
    env["SELECTED_AUDIO_FILE"] = wav_input
    env["SPLITTER_TYPE"] = splitter_type

    py = sys.executable
    args = [py, checkpoint_py, "--input", wav_input, "--splitter", splitter_type]
    log("Launching checkpoint.py...")
    log("Command: " + " ".join(shlex.quote(a) for a in args))

    try:
        if is_windows():
            # PTY not available on Windows stdlib; run normally (will still accept --input)
            ret = subprocess.call(args, cwd=os.path.dirname(checkpoint_py) or None, env=env)
        else:
            ret = run_checkpoint_via_pty(
                args,
                cwd=os.path.dirname(checkpoint_py) or None,
                env=env,
                wav_line=wav_input,        # answers the paste-path prompt
                mode_line=mode_line        # answers the "Type 1 or 2" prompt
            )
        log(f"checkpoint.py exited with code {ret}")
        return ret
    except FileNotFoundError:
        log("ERROR: Python interpreter not found or checkpoint.py missing.")
        return 6
    except Exception as e:
        log(f"ERROR running checkpoint.py: {e}")
        return 7

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        log("Interrupted by user.")
        sys.exit(130)