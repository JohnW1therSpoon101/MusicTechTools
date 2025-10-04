#!/usr/bin/env python3
"""
methods/youtube/method1.py

Primary downloader using yt-dlp.
- Accepts URL via argv[1].
- If 'yt-dlp' executable not on PATH, falls back to 'python -m yt_dlp'.

Exit codes:
  0 success
  2 usage / missing URL
  3 downloader failed
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path

def log(s: str):
    print(s, flush=True)

def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        log("[method1] Usage: method1.py <url>")
        log("[method1] No URL passed; expecting start.py to provide it")
        sys.exit(2)

    url = sys.argv[1].strip()

    # Pick output directory: ~/Downloads/<yt_dlp_downloads>
    out_root = Path.home() / "Downloads" / "yt_dlp_downloads"
    out_root.mkdir(parents=True, exist_ok=True)

    # Prefer yt-dlp executable; else fall back to python -m yt_dlp
    ytdlp_exe = shutil.which("yt-dlp")
    if ytdlp_exe:
        cmd = [
            ytdlp_exe,
            "-x", "--audio-format", "wav",
            "--audio-quality", "0",
            "-o", str(out_root / "%(title)s.%(ext)s"),
            url,
        ]
        log("[method1] Using yt-dlp executable")
    else:
        # fallback to python -m yt_dlp (works if yt_dlp module is installed in venv)
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-x", "--audio-format", "wav",
            "--audio-quality", "0",
            "-o", str(out_root / "%(title)s.%(ext)s"),
            url,
        ]
        log("[method1] yt-dlp not found on PATH; using 'python -m yt_dlp' fallback")

    log("[method1] " + " ".join(cmd))
    try:
        cp = subprocess.run(cmd, check=False)
        if cp.returncode != 0:
            log(f"[method1] yt-dlp exited with {cp.returncode}")
            sys.exit(3)
    except KeyboardInterrupt:
        log("[method1] Aborted by user.")
        sys.exit(130)

    log("[method1] Download/extract complete.")
    sys.exit(0)

if __name__ == "__main__":
    main()
