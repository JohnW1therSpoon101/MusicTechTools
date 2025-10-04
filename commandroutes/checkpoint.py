#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MusicTechTools/commandroutes/checkpoint.py

CHECKPOINT flow:
- Choose stem separation:
  1) Basic -> methods/splits/basicsplitter.py
  2) Complex -> methods/splits/splitter.py

Args:
  --wav  /path/to/file.wav  (optional; if omitted we auto-discover)
  --mode 1|2|basic|complex (optional; if omitted we prompt)

WAV resolution order:
1) --wav argument
2) last_download.json / last_download.txt (stems root)
3) newest .wav in ~/Downloads (24h)
4) Prompt

Exit codes:
 0 success
 2 cannot locate stems root / scripts
 3 no valid wav selected
 4 splitter script error

This version streams Demucs/splitter output in real time (no buffering).
"""

import os
import sys
import json
import platform
import argparse
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime

# ---------- logging ----------
def log(msg: str) -> None:
    print(f"[checkpoint] {msg}", flush=True)

def section(title: str) -> None:
    print("\n" + "-" * 72)
    print(f"[checkpoint] {title}")
    print("-" * 72, flush=True)

# ---------- streaming runner (REAL-TIME OUTPUT) ----------
def _spinner_stop_event():
    return threading.Event()

def _spinner(title: str, stop_evt, interval: float = 0.1) -> None:
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    i = 0
    while not stop_evt.is_set():
        sys.stdout.write(f"\r[checkpoint] {title} {frames[i % len(frames)]}")
        sys.stdout.flush()
        time.sleep(interval)
        i += 1
    sys.stdout.write("\r" + " " * (len(title) + 20) + "\r")
    sys.stdout.flush()

def run_stream(cmd: List[str], cwd: Optional[Path] = None, env: Optional[dict] = None) -> int:
    """
    Run a command and stream its output in real time.
    We merge stderr into stdout so tqdm progress bars are visible.
    """
    log("$ " + " ".join(str(c) for c in cmd))
    proc = subprocess.Popen(
        [str(c) for c in cmd],
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        env=env
    )

    stop_evt = _spinner_stop_event()
    spin = threading.Thread(target=_spinner, args=("Running splitter...", stop_evt), daemon=True)
    spin.start()

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if line.strip():
                # clear spinner line so tqdm lines print cleanly
                sys.stdout.write("\r")
                sys.stdout.flush()
                print(line, end="")
    finally:
        proc.wait()
        stop_evt.set()
        spin.join()

    return proc.returncode

# ---------- locate repo roots ----------
STEMS_DIR_CANDIDATE_NAMES = [
    "youtube2audwithstems",
    "youtube2audwstems",
    "yt2aws",
]

def looks_like_stems_dir(p: Path) -> bool:
    return (p / "getlink.py").exists() and (p / "methods" / "youtube").exists()

def find_musictechtools_root(start: Path) -> Path:
    start = start.resolve()
    if start.name.lower() == "commandroutes" and start.parent.exists():
        return start.parent
    for parent in [start] + list(start.parents):
        if (parent / "commandroutes").exists():
            return parent
    return start

def find_stems_root(musictech_root: Path) -> Optional[Path]:
    for name in STEMS_DIR_CANDIDATE_NAMES:
        p = musictech_root / name
        if p.is_dir() and looks_like_stems_dir(p):
            return p
    for child in musictech_root.iterdir():
        if child.is_dir():
            nm = child.name.lower()
            if "youtube2aud" in nm and "stem" in nm and looks_like_stems_dir(child):
                return child
    for child in musictech_root.iterdir():
        if child.is_dir() and (child / "getlink.py").exists():
            return child
    return None

# ---------- wav discovery ----------
def get_downloads_dir() -> Path:
    home = Path.home()
    candidate = home / "Downloads"
    return candidate if candidate.exists() else home

def newest_wav_under(root: Path, within_hours: int = 24) -> Optional[Path]:
    if not root.exists():
        return None
    newest = None
    newest_mtime = 0.0
    cutoff = datetime.now().timestamp() - within_hours * 3600
    for p in root.rglob("*.wav"):
        try:
            t = p.stat().st_mtime
        except Exception:
            continue
        if t >= cutoff and t > newest_mtime:
            newest, newest_mtime = p, t
    return newest

def read_manifest_for_wav(stems_root: Path) -> Optional[Path]:
    j = stems_root / "last_download.json"
    if j.exists():
        try:
            data = json.loads(j.read_text(encoding="utf-8"))
            wav = data.get("wav")
            if wav and Path(wav).exists():
                return Path(wav)
            folder = data.get("folder")
            if folder and Path(folder).is_dir():
                f = newest_wav_under(Path(folder), within_hours=72)
                if f:
                    return f
        except Exception:
            pass
    t = stems_root / "last_download.txt"
    if t.exists():
        try:
            txt = t.read_text(encoding="utf-8").strip()
            if txt and txt.lower().endswith(".wav") and Path(txt).exists():
                return Path(txt)
        except Exception:
            pass
    return None

def prompt_for_wav() -> Optional[Path]:
    try:
        sys.stdout.write("\n[checkpoint] Paste absolute path to a .wav (or leave blank to cancel): ")
        sys.stdout.flush()
        s = sys.stdin.readline().strip()
        if not s:
            return None
        p = Path(s).expanduser().resolve()
        return p if p.exists() and p.suffix.lower() == ".wav" else None
    except KeyboardInterrupt:
        return None

def choose_mode_interactive() -> str:
    print(
        "\nCHECKPOINT\n"
        "  1) Basic Stem Separation\n"
        "  2) Complex Stem Separation\n"
        "Type 1 or 2, then press Enter.\n",
        flush=True,
    )
    while True:
        sys.stdout.write("> ")
        sys.stdout.flush()
        val = sys.stdin.readline().strip()
        if val in ("1", "2"):
            return val
        print("Please enter 1 or 2.", flush=True)

# ---------- main ----------
def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--wav", dest="wav", default=None)
    parser.add_argument("--mode", dest="mode", default=None)  # 1|2|basic|complex
    args, _ = parser.parse_known_args()

    section("CHECKPOINT")
    log(f"OS: {platform.system()}")

    this_file = Path(__file__).resolve()
    commandroutes_dir = this_file.parent
    musictech_root = find_musictechtools_root(commandroutes_dir)
    stems_root = find_stems_root(musictech_root)

    log(f"MusicTechTools root: {musictech_root}")
    if not stems_root:
        log("Could not locate stems project root.")
        return 2
    log(f"Stems project root: {stems_root}")

    # WAV resolution
    wav_path: Optional[Path] = None
    if args.wav:
        p = Path(args.wav).expanduser().resolve()
        if p.exists() and p.suffix.lower() == ".wav":
            wav_path = p
            log(f"Using WAV from --wav: {wav_path}")
        else:
            log(f"--wav path invalid: {p}")

    if not wav_path:
        wav_path = read_manifest_for_wav(stems_root)
        if wav_path:
            log(f"Using WAV from manifest: {wav_path}")
        else:
            downloads = get_downloads_dir()
            log(f"Searching for recent .wav under: {downloads}")
            wav_path = newest_wav_under(downloads, within_hours=24)
            if wav_path:
                log(f"Using newest .wav: {wav_path}")

    if not wav_path:
        log("Could not determine .wav automatically.")
        wav_path = prompt_for_wav()

    if not wav_path:
        log("No valid .wav provided. Exiting.")
        return 3

    # Mode resolution (non-interactive if provided)
    mode_arg = None
    if args.mode:
        m = args.mode.strip().lower()
        if m in ("1", "basic"):
            mode_arg = "1"
        elif m in ("2", "complex"):
            mode_arg = "2"
    if not mode_arg:
        mode_arg = choose_mode_interactive()

    # Resolve splitter scripts
    splits_dir = stems_root / "methods" / "splits"
    basic_path = splits_dir / "basicsplitter.py"
    complex_path = splits_dir / "splitter.py"

    if mode_arg == "1" and not basic_path.exists():
        log(f"Missing script: {basic_path}")
        return 2
    if mode_arg == "2" and not complex_path.exists():
        log(f"Missing script: {complex_path}")
        return 2

    section("RUN SPLITTER (real-time)")
    target = basic_path if mode_arg == "1" else complex_path
    log(f"Mode : {'Basic' if mode_arg == '1' else 'Complex'}")
    log(f"Script: {target}")
    log(f"WAV  : {wav_path}")

    # boost chances that tqdm renders even if no TTY
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("FORCE_COLOR", "1")
    env.setdefault("TQDM_MININTERVAL", "0.1")

    # NOTE: We stream the splitter script itself. The splitter scripts already
    # run Demucs with streaming as well, so you'll get continuous progress.
    rc = run_stream([sys.executable, str(target), str(wav_path)], cwd=target.parent, env=env)
    if rc != 0:
        log(f"Splitter exited with code {rc}")
        return 4

    log("Stem separation completed successfully.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("Interrupted by user.")
        sys.exit(130)