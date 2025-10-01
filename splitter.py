#!/usr/bin/env python3
"""
Split stems using Demucs and move the produced WAVs up into out_folder.

API:
    ok = split_stems_with_demucs(audio_path: str, out_folder: str) -> bool
"""

import os
import shutil
import subprocess
from pathlib import Path

# Use a simple local logger to avoid cross-module coupling.
def log(msg: str) -> None:
    print(msg, flush=True)

def split_stems_with_demucs(audio_path: str, out_folder: str) -> bool:
    """
    Run demucs and move stems up into out_folder.
    Returns True on success, False otherwise.
    """
    if shutil.which("demucs") is None:
        log("[stems] demucs not found; skipping.")
        return False

    audio_path = str(audio_path)
    out_folder = str(out_folder)

    # Ensure output directory exists
    Path(out_folder).mkdir(parents=True, exist_ok=True)

    try:
        cmd = ["demucs", "--out", out_folder, audio_path]
        log("[stems] " + " ".join(cmd))
        # Let Demucs print its own progress to the console
        subprocess.run(cmd, check=True)

        # Expected demucs layout: <out>/<model>/<basename>/*.wav
        base = os.path.splitext(os.path.basename(audio_path))[0]
        candidate_dirs = []
        # Common models include htdemucs, htdemucs_ft, mdx_extra, etc.
        for name in os.listdir(out_folder):
            d = os.path.join(out_folder, name, base)
            if os.path.isdir(d):
                candidate_dirs.append(d)

        moved_any = False
        for d in candidate_dirs:
            for fn in os.listdir(d):
                if fn.lower().endswith(".wav"):
                    src = os.path.join(d, fn)
                    dst = os.path.join(out_folder, fn)
                    try:
                        os.replace(src, dst)
                        log(f"[stems] -> {dst}")
                        moved_any = True
                    except Exception:
                        # If a file is locked or identical, just continue
                        pass
            # Try to cleanup empty leaf dir
            try:
                os.rmdir(d)
            except OSError:
                pass

        return moved_any
    except subprocess.CalledProcessError as e:
        log(f"[stems] demucs failed: {e}")
        return False
