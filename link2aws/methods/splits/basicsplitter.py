#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basic stem separation (Demucs default/lean settings) with real-time progress.

Usage:
  python basicsplitter.py /absolute/path/to/file.wav
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
    print(f"[basicsplitter] {msg}", flush=True)

def _spinner_stop_event():
    import threading
    return threading.Event()

def _spinner(title: str, stop_evt, interval: float = 0.1) -> None:
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    i = 0
    while not stop_evt.is_set():
        sys.stdout.write(f"\r[basicsplitter] {title} {frames[i % len(frames)]}")
        sys.stdout.flush()
        time.sleep(interval)
        i += 1
    sys.stdout.write("\r[basicsplitter] " + " " * (len(title) + 2) + "\r")
    sys.stdout.flush()

def run_stream(cmd: List[str], cwd: Optional[Path] = None, env: Optional[dict] = None) -> int:
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
    spin = threading.Thread(target=_spinner, args=("Running Demucs...", stop_evt), daemon=True)
    spin.start()

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if line.strip():
                sys.stdout.write("\r")
                sys.stdout.flush()
                print(line, end="")
    finally:
        proc.wait()
        stop_evt.set()
        spin.join()

    return proc.returncode

def move_stems_up(out_dir: Path, base_name: str) -> bool:
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
    # cleanup
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
        log("Usage: python basicsplitter.py /absolute/path/to/file.wav")
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

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("FORCE_COLOR", "1")
    env.setdefault("TQDM_MININTERVAL", "0.1")

    cmd = [
        "demucs",
        "--out", str(out_dir),
        str(wav_path),
    ]

    rc = run_stream(cmd, cwd=wav_dir, env=env)
    if rc != 0:
        log(f"Demucs exited with code {rc}")
        return rc

    moved = move_stems_up(out_dir, base_name)
    if not moved and not any(out_dir.glob("*.wav")):
        log("No stem .wav files found after Demucs run.")
        return 4

    manifest = {
        "input_wav": str(wav_path),
        "stems_dir": str(out_dir),
        "stems": sorted([str(p) for p in out_dir.glob("*.wav")]),
        "demucs_cmd": cmd,
    }
    (out_dir / "last_stems.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    try:
        stems_root = Path(__file__).resolve().parents[2]
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