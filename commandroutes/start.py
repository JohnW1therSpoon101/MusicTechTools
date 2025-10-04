#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MusicTechTools/commandroutes/start.py

Workflow:
1) CHECKS (OS + deps)
2) ADAPT (OS-safe paths)
3) Run getlink.py (or prompt), then method1.py to download WAV
4) Run details/findtemp.py on the WAV
5) PROMPT user to choose split mode (1=Basic, 2=Complex)
6) Run checkpoint.py with --wav and --mode per selection
7) Run complete.py
"""

import os
import sys
import re
import json
import platform
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List, Tuple, Union
from datetime import datetime

# ----------------------------------------
# Logging helpers
# ----------------------------------------
def log(msg: str) -> None:
    print(f"[start] {msg}", flush=True)

def section(title: str) -> None:
    print("\n" + "-" * 72)
    print(f"[start] {title}")
    print("-" * 72, flush=True)

def run_cmd(cmd: List[Union[str, Path]], cwd: Optional[Path] = None, check: bool = False) -> Tuple[int, str, str]:
    """Run a command and capture stdout/stderr (text mode)."""
    cmd_str = " ".join(str(c) for c in cmd)
    log(f"$ {cmd_str}")
    proc = subprocess.Popen(
        [str(c) for c in cmd],
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, err = proc.communicate()
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, out, err)
    return proc.returncode, out or "", err or ""

def which_all(names: List[str]) -> dict:
    return {name: shutil.which(name) for name in names}

# ----------------------------------------
# Directory discovery
# ----------------------------------------
STEMS_DIR_CANDIDATE_NAMES = [
    "youtube2audwithstems",
    "youtube2audwstems",
    "yt2aws",   # legacy alias
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

# ----------------------------------------
# URL helpers
# ----------------------------------------
YT_URL_RE = re.compile(
    r"(https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=[\w\-]+[^\s]*|shorts/[\w\-]+[^\s]*)|youtu\.be/[\w\-]+[^\s]*))",
    re.IGNORECASE
)

def extract_url(text: str) -> Optional[str]:
    if not text:
        return None
    m = YT_URL_RE.search(text.strip())
    return m.group(1) if m else None

def prompt_for_url() -> Optional[str]:
    sys.stdout.write("===ENTERLINK===: ")
    sys.stdout.flush()
    try:
        entered = sys.stdin.readline().strip()
    except KeyboardInterrupt:
        return None
    if not entered:
        return None
    return extract_url(entered)

# ----------------------------------------
# WAV discovery
# ----------------------------------------
def get_downloads_dir() -> Path:
    home = Path.home()
    candidate = home / "Downloads"
    if candidate.exists():
        return candidate
    env = os.environ.get("USERPROFILE")
    if env:
        p = Path(env) / "Downloads"
        if p.exists():
            return p
    return home

def newest_wav_under(root: Path, within_hours: int = 12) -> Optional[Path]:
    if not root.exists():
        return None
    newest: Optional[Path] = None
    newest_mtime = 0.0
    cutoff = datetime.now().timestamp() - within_hours * 3600
    for p in root.rglob("*.wav"):
        try:
            mtime = p.stat().st_mtime
        except Exception:
            continue
        if mtime >= cutoff and mtime > newest_mtime:
            newest, newest_mtime = p, mtime
    return newest

def read_manifest_for_wav(stems_root: Path) -> Optional[Path]:
    t = stems_root / "last_download.txt"
    if t.exists():
        try:
            txt = t.read_text(encoding="utf-8").strip()
            if txt and txt.lower().endswith(".wav") and Path(txt).exists():
                return Path(txt)
        except Exception:
            pass
    j = stems_root / "last_download.json"
    if j.exists():
        try:
            data = json.loads(j.read_text(encoding="utf-8"))
            wav = data.get("wav")
            if wav and Path(wav).exists():
                return Path(wav)
            folder = data.get("folder")
            if folder and Path(folder).is_dir():
                found = newest_wav_under(Path(folder), within_hours=48)
                if found:
                    return found
        except Exception:
            pass
    return None

# ----------------------------------------
# Prompt for split mode
# ----------------------------------------
def prompt_split_mode() -> str:
    print(
        "\nSPLIT MODE\n"
        "  1) Basic (basicsplitter.py)\n"
        "  2) Complex (splitter.py)\n"
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

# ----------------------------------------
# Main
# ----------------------------------------
def main() -> int:
    # CHECKS
    section("CHECKS")
    os_name = platform.system()
    if os_name == "Windows":
        log("Windows")
    elif os_name == "Darwin":
        log("Mac")
    else:
        log(os_name)

    this_file = Path(__file__).resolve()
    commandroutes_dir = this_file.parent
    musictech_root = find_musictechtools_root(commandroutes_dir)
    stems_root = find_stems_root(musictech_root)

    log(f"MusicTechTools root: {musictech_root}")
    if not stems_root:
        log("Could not locate the youtube2audwithstems folder relative to MusicTechTools.")
        return 2
    log(f"Stems project root: {stems_root}")

    section("Dependency Check")
    log("Looking for required tools & libraries...")

    # Executables
    exe_hits = which_all(["yt-dlp", "ffmpeg", "demucs"])
    print("\nExecutables")
    for name, path_val in exe_hits.items():
        mark = "✓" if path_val else "✗"
        log(f"  [{mark}] {name:<6} {path_val or '(not found)'}")

    # Python modules
    modules = ["numpy", "soundfile", "librosa", "essentia", "torch"]
    print("\nPython Modules")
    for m in modules:
        try:
            __import__(m)
            log(f"  [✓] {m} importable")
        except Exception:
            log(f"  [✗] {m} not importable")

    # ADAPT
    section("ADAPT")
    log("Using OS-appropriate paths and sys.executable for Python calls.")

    # Run getlink.py
    section("Run getlink.py")
    getlink = stems_root / "getlink.py"
    url: Optional[str] = None

    if getlink.exists():
        log(f"Executing: {getlink}")
        rc, out, err = run_cmd([sys.executable, getlink], cwd=stems_root)
        url = extract_url(out) or extract_url(err)
    else:
        log("getlink.py not found.")

    if not url:
        url = prompt_for_url()

    if not url:
        log("No valid URL provided. Exiting.")
        return 3

    log(f"URL captured: {url}")

    # Send link to method1.py
    section("Run Methods")
    method1 = stems_root / "methods" / "youtube" / "method1.py"
    if not method1.exists():
        log(f"Downloader not found: {method1}")
        return 4

    log("Starting download/extract via method1.py ...")
    rc, _, _ = run_cmd([sys.executable, method1, url], cwd=method1.parent)
    if rc != 0:
        log(f"method1.py exited with code {rc}")
        return rc
    log("method1.py completed successfully.")

    # Find the output WAV
    section("Locate Downloaded WAV")
    wav_path: Optional[Path] = read_manifest_for_wav(stems_root)
    if not wav_path:
        downloads = get_downloads_dir()
        log(f"Searching for fresh .wav under: {downloads}")
        wav_path = newest_wav_under(downloads, within_hours=24)

    if not wav_path:
        log("Could not find a recently-downloaded .wav. If your pipeline writes a manifest, consider last_download.json.")
        return 5

    log(f"Using WAV: {wav_path}")

    # Run details/findtemp.py with the wav path
    section("Run findtemp.py")
    findtemp = stems_root / "details" / "findtemp.py"
    if not findtemp.exists():
        log(f"findtemp.py not found at {findtemp}")
        return 6

    rc, _, _ = run_cmd([sys.executable, findtemp, str(wav_path)], cwd=findtemp.parent)
    if rc != 0:
        log(f"findtemp.py exited with code {rc}")
        return rc
    log("findtemp.py completed successfully.")

    # === Prompt user for split mode ===
    section("Choose split mode")
    mode_arg = prompt_split_mode()  # "1" or "2"

    # Run checkpoint (aisplitter) non-interactively with chosen mode
    section("Run checkpoint.py")
    checkpoint = musictech_root / "commandroutes" / "checkpoint.py"
    if not checkpoint.exists():
        log(f"checkpoint.py not found at {checkpoint}")
        return 7

    rc, _, _ = run_cmd([sys.executable, checkpoint, "--wav", str(wav_path), "--mode", mode_arg], cwd=checkpoint.parent)
    if rc != 0:
        log(f"checkpoint.py exited with code {rc}")
        return rc
    log("checkpoint.py completed successfully.")

    # Run complete.py
    section("Run complete.py")
    complete = stems_root / "complete.py"
    if not complete.exists():
        complete = musictech_root / "complete.py"

    if complete.exists():
        rc, _, _ = run_cmd([sys.executable, complete], cwd=complete.parent)
        if rc != 0:
            log(f"complete.py exited with code {rc}")
            return rc
        log("complete.py completed successfully.")
    else:
        log("complete.py not found; skipping finalization step.")

    section("DONE")
    log("Pipeline finished successfully.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("Interrupted by user.")
        sys.exit(130)