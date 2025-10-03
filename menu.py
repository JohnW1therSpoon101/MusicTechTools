#!/usr/bin/env python3
# menu.py — launcher for MusicTechTools (handles yt2aws or link2aws)

import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Tuple

CHECK = "✓"; CROSS = "✗"; DOT = "•"
def bold(s):   return f"\033[1m{s}\033[0m"
def dim(s):    return f"\033[2m{s}\033[0m"
def green(s):  return f"\033[32m{s}\033[0m"
def red(s):    return f"\033[31m{s}\033[0m"
def cyan(s):   return f"\033[36m{s}\033[0m"
def yellow(s): return f"\033[33m{s}\033[0m"

HERE = Path(__file__).resolve().parent  # .../MusicTechTools

def find_dir_named(root: Path, name: str) -> Optional[Path]:
    cand = root / name
    if cand.is_dir(): return cand
    for p in root.rglob(name):
        if p.is_dir() and p.name == name:
            return p
    return None

# --- Accept either yt2aws or link2aws as the main project folder ---
YT2AWS = find_dir_named(HERE, "yt2aws")
LINK2AWS = find_dir_named(HERE, "link2aws")
PROJECT = YT2AWS or LINK2AWS  # whichever exists
PROJECT_NAME = "yt2aws" if YT2AWS else ("link2aws" if LINK2AWS else None)

if PROJECT is None:
    print(red(f"[fatal] Could not find a folder named 'yt2aws' or 'link2aws' under: {HERE}"))
    try:
        kids = sorted([p.name + ("/" if p.is_dir() else "") for p in HERE.iterdir()])
        preview = ", ".join(kids[:25]) + (" ..." if len(kids) > 25 else "")
        print(dim(f"[info] Top-level here contains: {preview}"))
    except Exception:
        pass
    sys.exit(1)

print(dim(f"[info] Using project folder: {PROJECT}"))

COMMANDROUTES = find_dir_named(HERE, "commandroutes")
DETAILS = find_dir_named(PROJECT, "details") or (PROJECT / "details")
METHODS = find_dir_named(PROJECT, "methods") or (PROJECT / "methods")
SPLITS  = find_dir_named(METHODS, "splits") or (METHODS / "splits")

# -------------------------------
# Dependency checks
# -------------------------------
EXEC_DEPS = {"yt-dlp":"yt-dlp","ffmpeg":"ffmpeg","demucs":"demucs"}
PY_DEPS = ["numpy","soundfile","librosa","essentia","torch"]

def which_exe(name: str) -> Optional[str]:
    return shutil.which(name)

def check_python_import(modname: str) -> Tuple[bool, Optional[str]]:
    try:
        mod = __import__(modname)
        ver = getattr(mod, "__version__", None)
        return True, ver
    except Exception:
        return False, None

def show_dependencies():
    print(bold("\nDependency Check"))
    print(dim("Looking for required tools & libraries...\n"))
    print(bold("Executables"))
    for label, exe in EXEC_DEPS.items():
        path = which_exe(exe)
        print(f"  {green('['+CHECK+']')+' ' if path else red('['+CROSS+'] ')}{label:<10} {dim(path) if path else red('not found')}")
    print(bold("\nPython Modules"))
    for mod in PY_DEPS:
        ok, ver = check_python_import(mod)
        v = f" v{ver}" if (ok and ver) else ""
        print(f"  {green('['+CHECK+']') if ok else red('['+CROSS+']')} {mod:<10}{dim(v) if ok else red(' not importable')}")
    print()

# -------------------------------
# Script runners
# -------------------------------
def run_script(pyfile: Path, args=None) -> int:
    if args is None: args = []
    if not pyfile.exists():
        print(red(f"[error] Script not found: {pyfile}"))
        return 1
    cmd = [sys.executable, str(pyfile)] + list(args)
    print(dim(f"\n$ {' '.join(cmd)}\n"))
    try:
        return subprocess.run(cmd).returncode
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(red(f"[error] Failed to launch {pyfile.name}: {e}"))
        return 1

def try_first(*candidates: Path) -> Optional[Path]:
    for p in candidates:
        if p and p.exists():
            return p
    return None

def find_anywhere(filename: str, root: Path) -> Optional[Path]:
    for p in root.rglob(filename):
        if p.name == filename:
            return p
    return None

# -------------------------------
# Route map (what each keyword launches)
# -------------------------------
def resolve_routes() -> Dict[str, Path]:
    ro: Dict[str, Path] = {}

    # Core (download flow) -> start.py under whichever project folder exists
    ro["link2stems"] = try_first(
        PROJECT / "start.py",
        COMMANDROUTES / "start.py" if COMMANDROUTES else None,
        find_anywhere("start.py", HERE)  # last resort
    )

    # Optional commandroutes wrappers (ignored if missing)
    ro["getaudio"] = try_first(
        (COMMANDROUTES / "startgetaudio.py") if COMMANDROUTES else None,
        find_anywhere("startgetaudio.py", HERE)
    )
    ro["getdetails"] = try_first(
        (COMMANDROUTES / "startdetails.py") if COMMANDROUTES else None,
        find_anywhere("startdetails.py", HERE)
    )

    # Music details
    ro["gettempo"] = try_first(
        DETAILS / "findtemp.py",
        find_anywhere("findtemp.py", HERE)
    )
    ro["getkey"] = try_first(
        DETAILS / "findkey.py",
        find_anywhere("findkey.py", HERE)
    )
    ro["getgenre"] = try_first(
        DETAILS / "idgenre.py",
        find_anywhere("idgenre.py", HERE)
    )

    # Splitter
    ro["aisplitter"] = try_first(
        PROJECT / "checkpoint.py",
        SPLITS / "splitter.py",
        find_anywhere("checkpoint.py", HERE),
        find_anywhere("splitter.py", HERE)
    )

    # Bonus: DrumKit builder if present anywhere
    ro["DrumKitBuilder"] = try_first(find_anywhere("rundk.py", HERE))

    return ro

INTRO = [
    bold("Welcome to my MusicTechTools!"),
    "Built by Stxrn",
    "Choose what you want to do",
    "You can pick... download, split, or music details",
]

PREOPTIONS = {
    "download": ["link2stems", "getaudio"],
    "split":    ["aisplitter"],
    "music details": ["gettempo", "getdetails", "getkey", "getgenre"],
}

OPTIONS_HELP = [
    f'{DOT} "link2stems"   → run {PROJECT_NAME}/start.py',
    f'{DOT} "getaudio"     → run commandroutes/startgetaudio.py',
    f'{DOT} "getdetails"   → run commandroutes/startdetails.py',
    f'{DOT} "gettempo"     → run {PROJECT_NAME}/details/findtemp.py',
    f'{DOT} "getkey"       → run {PROJECT_NAME}/details/findkey.py',
    f'{DOT} "getgenre"     → run {PROJECT_NAME}/details/idgenre.py',
    f'{DOT} "aisplitter"   → run {PROJECT_NAME}/checkpoint.py (or methods/splits/splitter.py)',
    f'{DOT} "DrumKitBuilder" → run rundk.py (if present)',
    f'{DOT} "done" / "quit" to exit',
]

def print_intro():
    print()
    for line in INTRO: print(cyan(line))
    print()
    print(bold("PREOPTIONS"))
    for k, v in PREOPTIONS.items(): print(f"  {yellow(k)}  → {', '.join(v)}")
    print()
    print(bold("OPTIONS"))
    for line in OPTIONS_HELP: print(" ", line)
    print()

def main():
    print_intro()
    show_dependencies()

    routes = resolve_routes()

    print(bold("Route Resolution"))
    for key in ["link2stems","getaudio","getdetails","gettempo","getkey","getgenre","aisplitter","DrumKitBuilder"]:
        p = routes.get(key)
        if p: print(f"  {green('['+CHECK+']')} {key:<13} {dim(str(p))}")
        else: print(f"  {red('['+CROSS+']')} {key:<13} {red('no script found')}")
    print("\nType a " + bold("PREOPTION") + " (download / split / music details) or a direct " + bold("OPTION") + " keyword.")
    print("Example: link2stems\n")

    while True:
        try:
            choice = input(bold("> ")).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nbye.\n"); break

        if choice in ("done","quit","exit","q"):
            print("bye.\n"); break

        if choice in PREOPTIONS:
            print(bold(f"\n{choice.upper()} options: ") + ", ".join(PREOPTIONS[choice]))
            continue

        if choice in routes and routes[choice] is not None:
            code = run_script(routes[choice])
            print()
            if code == 130: print(red("Interrupted by user.\n"))
        else:
            print(red("Unknown option or script not found."))
            avail = [k for k in routes if routes[k] is not None]
            if avail: print("Try one of: " + ", ".join(avail))
            print()

if __name__ == "__main__":
    main()