#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complex stem separation (Demucs advanced options) with real-time progress.

Usage:
  python splitter.py /absolute/path/to/file.wav
"""

import os
import sys
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import List, Tuple, Optional

def log(msg: str) -> None:
    print(f"[splitter] {msg}", flush=True)

def _spinner_stop_event():
    # small helper so we don't import threading.Event at top-level twice
    return threading.Event()

def _spinner(title: str, stop_evt: threading.Event, interval: float = 0.1) -> None:
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    i = 0
    while not stop_evt.is_set():
        sys.stdout.write(f"\r[splitter] {title} {frames[i % len(frames)]}")
        sys.stdout.flush()
        time.sleep(interval)
        i += 1
    sys.stdout.write("\r[splitter] " + " " * (len(title) + 2) + "\r")
    sys.stdout.flush()

def run_stream(cmd: List[str], cwd: Optional[Path] = None, env: Optional[dict] = None) -> int:
    """
    Run a command and stream its output in real time. We merge stderr into stdout
    so Demucs/tqdm bars show up as they render.
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

    # start a spinner in case the tool is quiet (some environments hide tqdm)
    stop_evt = _spinner_stop_event()
    spin = threading.Thread(target=_spinner, args=("Running Demucs...", stop_evt), daemon=True)
    spin.start()

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            # if we see progress-y output, clear spinner line first so bars look clean
            if line.strip():
                sys.stdout.write("\r")  # return carriage to overwrite spinner line
                sys.stdout.flush()
                print(line, end="")     # print Demucs/tqdm line as-is
    finally:
        proc.wait()
        stop_evt.set()
        spin.join()

    return proc.returncode

def move_stems_up(out_dir: Path, base_name: str) -> bool:
    """
    Demucs creates: <out>/<model>/<base_name>/*.wav
    Move those .wav files up to <out>/ (which is already <wav_dir>/<base>_stems).
    """
    moved_any = False
    if not out_dir.exists():
        return False
    for model_dir in out_dir.iterdir():
        candidate = model_dir / base_name
        if candidate.is_dir():
            for w in candidate.glob("*.wav"):
                target = out_dir / w.name
                try:
                    if target.exists():
                        target.unlink()
                    shutil.move(str(w), str(target))
                    moved_any = True
                except Exception:
                    pass
    # cleanup nested empty dirs
    for model_dir in list(out_dir.iterdir()):
        if model_dir.is_dir():
            inner = model_dir / base_name
            if inner.is_dir() and not any(inner.iterdir()):
                inner.rmdir()
            if not any(model_dir.iterdir()):
                model_dir.rmdir()
    return moved_any

def main() -> int:
    if len(sys.argv) < 2:
        log("Usage: python splitter.py /absolute/path/to/file.wav")
        return 2

    wav_path = Path(sys.argv[1]).expanduser().resolve()
    if not wav_path.exists() or wav_path.suffix.lower() != ".wav":
        log(f"Invalid wav: {wav_path}")
        return 2

    if shutil.which("demucs") is None:
        log("demucs not found in PATH")
        return 3

    base_name = wav_path.stem
    wav_dir = wav_path.parent
    out_dir = wav_dir / f"{base_name}_stems"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Encourage tqdm to render (even if not in a TTY)
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("FORCE_COLOR", "1")     # nicer progress if supported
    env.setdefault("TQDM_MININTERVAL", "0.1")

    # Complex Demucs settings (tweak as you like)
    cmd = [
        "demucs",
        "-n", "htdemucs_ft",
        "--overlap", "0.5",
        "--segment", "7",
        "--shifts", "2",
        "--clip-mode", "rescale",
        "--float32",
        "--out", str(out_dir),
        str(wav_path),
    ]

    rc = run_stream(cmd, cwd=wav_dir, env=env)
    if rc != 0:
        log(f"Demucs exited with code {rc}")
        return rc

    # Move stems up from nested dirs
    moved = move_stems_up(out_dir, base_name)
    if not moved:
        # Some demucs builds may already export flat; ensure there are wavs
        if not any(out_dir.glob("*.wav")):
            log("No stem .wav files detected in output. Aborting.")
            return 4

    # Write manifest
    manifest = {
        "input_wav": str(wav_path),
        "stems_dir": str(out_dir),
        "stems": sorted([str(p) for p in out_dir.glob("*.wav")]),
        "demucs_cmd": cmd,
    }
    (out_dir / "last_stems.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Best-effort mirror to project stems root (if detectable)
    try:
        stems_root = Path(__file__).resolve().parents[2]  # .../youtube2audwstems
        if (stems_root / "getlink.py").exists():
            (stems_root / "last_stems.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    except Exception:
        pass

    log(f"Stems saved to: {out_dir}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("Interrupted by user.")
        sys.exit(130)