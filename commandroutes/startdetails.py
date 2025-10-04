#!/usr/bin/env python3
"""
startdetails.py

Workflow:
1) Check dependencies for details tools (findtemp.py, idgenre.py, findkey.py).
2) Ask user to pick a file (via plumming/getaudiofile.py).
3) Run findtemp.py -> log tempo
4) Run findkey.py  -> log key
5) Run idgenre.py  -> log genre
6) Print summary.

Directory assumptions (relative to this file):
- ../../plumming/getaudiofile.py
- ../yt2aws/details/findtemp.py
- ../yt2aws/details/findkey.py
- ../yt2aws/details/idgenre.py
"""

import os
import re
import sys
import json
import shutil
import subprocess
from pathlib import Path

# ----------------------------
# Paths
# ----------------------------
HERE = Path(__file__).resolve().parent                           # MusicTechTools/commandroutes
ROOT = HERE.parent                                               # MusicTechTools
PLUMMING_DIR = ROOT / "plumming"
GETAUDIOFILE = PLUMMING_DIR / "getaudiofile.py"

YT2AWS_DIR = ROOT / "yt2aws"
DETAILS_DIR = YT2AWS_DIR / "details"
FINDTEMP = DETAILS_DIR / "findtemp.py"
FINDKEY = DETAILS_DIR / "findkey.py"
IDGENRE = DETAILS_DIR / "idgenre.py"

LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)
RUN_LOG = LOGS_DIR / "startdetails.log"

# ----------------------------
# Simple logger
# ----------------------------
def log(msg: str):
    line = msg if msg.endswith("\n") else msg + "\n"
    sys.stdout.write(line)
    sys.stdout.flush()
    try:
        with RUN_LOG.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

# ----------------------------
# Dependency checks
# ----------------------------
REQUIRED_PY_PACKAGES = [
    # Common for tempo/key/genre pipelines (adjust to your actual implementations)
    "numpy",
    "scipy",
    "soundfile",   # pysoundfile
    "librosa",
    "pydub",       # often used to pre-process audio
    # Key detection (if using Essentia)
    # If your findkey.py uses Essentia, include it. Comment out if not.
    "essentia",
    # Genre id (your idgenre.py might use one of these—keep both if unsure)
    "scikit-learn",
    "torch",
]

REQUIRED_BINARIES = [
    "ffmpeg",  # used by librosa/pydub or your scripts
]

def have_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False

def have_binary(name: str) -> bool:
    return shutil.which(name) is not None

def pip_install(pkg: str) -> bool:
    log(f"[deps] Installing Python package: {pkg} ...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)
        log(f"[deps] Installed: {pkg}")
        return True
    except subprocess.CalledProcessError as e:
        log(f"[deps] FAILED to install {pkg}: {e}")
        return False

def check_and_fix_dependencies(auto_install=True):
    log("Dependency Check")
    log("Looking for required tools & libraries...\n")

    # Binaries
    log("Executables")
    for binname in REQUIRED_BINARIES:
        path = shutil.which(binname)
        if path:
            log(f"  [✓] {binname:<8} {path}")
        else:
            log(f"  [✗] {binname} not found in PATH")

    # Python packages
    log("\nPython Packages")
    for pkg in REQUIRED_PY_PACKAGES:
        ok = have_module(pkg)
        if ok:
            log(f"  [✓] {pkg}")
        else:
            log(f"  [✗] {pkg} (missing)")
            if auto_install:
                pip_install(pkg)

    # Final status
    missing_bins = [b for b in REQUIRED_BINARIES if not have_binary(b)]
    missing_pkgs = [p for p in REQUIRED_PY_PACKAGES if not have_module(p)]
    if missing_bins or missing_pkgs:
        log("\n[deps] Summary:")
        if missing_bins:
            log("  Missing executables: " + ", ".join(missing_bins))
        if missing_pkgs:
            log("  Missing Python packages: " + ", ".join(missing_pkgs))
        log("  Some functionality may not work until these are installed.\n")
    else:
        log("\n[deps] All dependencies satisfied.\n")

# ----------------------------
# Helpers
# ----------------------------
def run_python_script(script_path: Path, args=None) -> subprocess.CompletedProcess:
    """Run a Python script and capture output."""
    if args is None:
        args = []
    cmd = [sys.executable, str(script_path)] + list(args)
    log(f"[run] {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True)

def extract_first(pattern: str, text: str, default: str = "Unknown") -> str:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else default

def ensure_paths():
    problems = []
    if not GETAUDIOFILE.exists():
        problems.append(f"Missing: {GETAUDIOFILE}")
    if not FINDTEMP.exists():
        problems.append(f"Missing: {FINDTEMP}")
    if not FINDKEY.exists():
        problems.append(f"Missing: {FINDKEY}")
    if not IDGENRE.exists():
        problems.append(f"Missing: {IDGENRE}")

    if problems:
        log("Path verification failed:")
        for p in problems:
            log(f"  - {p}")
        log("\nFix the paths above before running.")
        sys.exit(1)

# ----------------------------
# Main flow
# ----------------------------
def main():
    ensure_paths()
    check_and_fix_dependencies(auto_install=True)

    print("\nHow do you plan to proceed?")
    print("UserChoices =")
    print("  - Option 1 = pick file  => use getaudiofile.py\n")

    # For now, we only have Option 1, so proceed directly to picker
    input("Press ENTER to open the file picker...")

    # Run the audio file selector
    sel = run_python_script(GETAUDIOFILE)
    if sel.returncode != 0:
        log("[select] getaudiofile.py failed.")
        log(sel.stderr.strip())
        sys.exit(1)

    # Try to detect a file path from the selector's stdout
    stdout = sel.stdout.strip()
    log("[select] getaudiofile.py output:")
    log(stdout + "\n")

    # Preferred: the selector prints a JSON line or a clear 'SELECTED_FILE:' marker.
    selected_file = None

    # 1) JSON mode: {"selected_file": "/path/to/file.wav"}
    try:
        maybe_json = json.loads(stdout)
        if isinstance(maybe_json, dict) and "selected_file" in maybe_json:
            selected_file = maybe_json["selected_file"]
    except Exception:
        pass

    # 2) Marker mode: SELECTED_FILE: /path/to/file.wav
    if not selected_file:
        m = re.search(r"SELECTED_FILE:\s*(.+)", stdout)
        if m:
            selected_file = m.group(1).strip()

    # 3) Fallback: last non-empty line that looks like a path
    if not selected_file:
        lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
        if lines:
            last = lines[-1]
            # crude heuristic: treat it as a path if it exists
            if Path(last).expanduser().exists():
                selected_file = Path(last).expanduser().as_posix()

    if not selected_file:
        log("[select] Could not determine selected file path from picker output.")
        sys.exit(1)

    selected_path = Path(selected_file).expanduser().resolve()
    if not selected_path.exists():
        log(f"[select] Selected path doesn't exist: {selected_path}")
        sys.exit(1)

    log(f"[select] Using file: {selected_path}\n")

    # ---------------- Run analyzers ----------------
    tempo = "Unknown"
    key = "Unknown"
    genre = "Unknown"

    # 1) Tempo
    log("Running: findtemp.py ...")
    r1 = run_python_script(FINDTEMP, [str(selected_path)])
    if r1.stdout:
        log(r1.stdout)
        # Try to parse common patterns:
        # e.g., "tempo = 120.0", "TEMPO: 120", "Aggregate: 120 BPM"
        tempo = extract_first(r"(?:tempo\s*=|TEMPO\s*:|Aggregate.*?:)\s*([0-9]+(?:\.[0-9]+)?)", r1.stdout, tempo)
    if r1.stderr:
        log("[findtemp stderr]")
        log(r1.stderr)

    # 2) Key
    log("\nRunning: findkey.py ...")
    r2 = run_python_script(FINDKEY, [str(selected_path)])
    if r2.stdout:
        log(r2.stdout)
        # Try to parse common patterns:
        # e.g., "Key = G minor", "KEY: C# Major"
        key = extract_first(r"(?:Key\s*=|KEY\s*:)\s*([A-G][b#]?\s*(?:major|minor)?)", r2.stdout, key)
    if r2.stderr:
        log("[findkey stderr]")
        log(r2.stderr)

    # 3) Genre
    log("\nRunning: idgenre.py ...")
    r3 = run_python_script(IDGENRE, [str(selected_path)])
    if r3.stdout:
        log(r3.stdout)
        # e.g., "Genre = R&B" or "GENRE: Hip-Hop"
        genre = extract_first(r"(?:Genre\s*=|GENRE\s*:)\s*([^\r\n]+)", r3.stdout, genre)
    if r3.stderr:
        log("[idgenre stderr]")
        log(r3.stderr)

    # ---------------- Output summary ----------------
    print("\nYou're audio has been analyzed")
    print("Results:")
    print(f"  genre = {genre}")
    print(f"  tempo = {tempo}")
    print(f"  key   = {key}")

    log("\n=== SUMMARY ===")
    log(f"genre = {genre}")
    log(f"tempo = {tempo}")
    log(f"key   = {key}")
    log("================\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.")
