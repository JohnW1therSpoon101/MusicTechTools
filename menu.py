#!/usr/bin/env python3
# menu.py — entry launcher for MusicTechTools (this file lives INSIDE MusicTechTools)

import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Tuple

# -------------------------------
# Paths / Layout
# -------------------------------
HERE = Path(__file__).resolve().parent                    # .../MusicTechTools
MTT_ROOT = HERE
YT2AWS = MTT_ROOT / "yt2aws"
COMMANDROUTES = MTT_ROOT / "commandroutes"
DETAILS = YT2AWS / "details"
METHODS = YT2AWS / "methods"
SPLITS = METHODS / "splits"

# -------------------------------
# Pretty printing helpers
# -------------------------------
CHECK = "✓"
CROSS = "✗"
DOT = "•"

def bold(s: str) -> str:   return f"\033[1m{s}\033[0m"
def dim(s: str) -> str:    return f"\033[2m{s}\033[0m"
def green(s: str) -> str:  return f"\033[32m{s}\033[0m"
def red(s: str) -> str:    return f"\033[31m{s}\033[0m"
def cyan(s: str) -> str:   return f"\033[36m{s}\033[0m"
def yellow(s: str) -> str: return f"\033[33m{s}\033[0m"

# -------------------------------
# Dependency checks
# -------------------------------
EXEC_DEPS = {
    "yt-dlp": "yt-dlp",
    "ffmpeg": "ffmpeg",
    "demucs": "demucs",
}

PY_DEPS = [
    "numpy",
    "soundfile",    # backend for librosa I/O
    "librosa",
    "essentia",     # key/tempo/genre (if you use it)
    "torch",        # demucs commonly relies on this
]

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
        if path:
            print(f"  {green('['+CHECK+']')} {label:<10} {dim(path)}")
        else:
            print(f"  {red('['+CROSS+']')} {label:<10} {red('not found')}")

    print(bold("\nPython Modules"))
    for mod in PY_DEPS:
        ok, ver = check_python_import(mod)
        if ok:
            v = f" v{ver}" if ver else ""
            print(f"  {green('['+CHECK+']')} {mod:<10}{dim(v)}")
        else:
            print(f"  {red('['+CROSS+']')} {mod:<10}{red('not importable')}")
    print()

# -------------------------------
# Script runners
# -------------------------------
def run_script(pyfile: Path, args=None) -> int:
    """Run a Python script with the current interpreter. Returns exit code."""
    if args is None:
        args = []
    if not pyfile.exists():
        print(red(f"[error] Script not found: {pyfile}"))
        return 1
    cmd = [sys.executable, str(pyfile)] + list(args)
    print(dim(f"\n$ {' '.join(cmd)}\n"))
    try:
        proc = subprocess.run(cmd)
        return proc.returncode
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

    # Core (download flow)
    ro["link2stems"] = try_first(
        YT2AWS / "start.py",
        COMMANDROUTES / "start.py",
        find_anywhere("start.py", MTT_ROOT)  # last resort
    )

    # Optional commandroutes wrappers (disregard if missing)
    ro["getaudio"] = try_first(
        COMMANDROUTES / "startgetaudio.py",
        find_anywhere("startgetaudio.py", MTT_ROOT)
    )
    ro["getdetails"] = try_first(
        COMMANDROUTES / "startdetails.py",
        find_anywhere("startdetails.py", MTT_ROOT)
    )

    # Music details
    ro["gettempo"] = try_first(
        DETAILS / "findtemp.py",
        find_anywhere("findtemp.py", MTT_ROOT)
    )
    ro["getkey"] = try_first(
        DETAILS / "findkey.py",
        find_anywhere("findkey.py", MTT_ROOT)
    )
    ro["getgenre"] = try_first(
        DETAILS / "idgenre.py",
        find_anywhere("idgenre.py", MTT_ROOT)
    )

    # Splitter
    ro["aisplitter"] = try_first(
        YT2AWS / "checkpoint.py",          # if you add a checkpoint menu later
        SPLITS / "splitter.py",
        find_anywhere("checkpoint.py", MTT_ROOT),
        find_anywhere("splitter.py", MTT_ROOT)
    )

    # Bonus: DrumKit builder if present anywhere
    ro["DrumKitBuilder"] = try_first(find_anywhere("rundk.py", MTT_ROOT))

    return ro

# -------------------------------
# Intro / Menu
# -------------------------------
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
    f'{DOT} "link2stems"   → run yt2aws/start.py',
    f'{DOT} "getaudio"     → run commandroutes/startgetaudio.py',
    f'{DOT} "getdetails"   → run commandroutes/startdetails.py',
    f'{DOT} "gettempo"     → run yt2aws/details/findtemp.py',
    f'{DOT} "getkey"       → run yt2aws/details/findkey.py',
    f'{DOT} "getgenre"     → run yt2aws/details/idgenre.py',
    f'{DOT} "aisplitter"   → run yt2aws/checkpoint.py (or methods/splits/splitter.py)',
    f'{DOT} "DrumKitBuilder" → run rundk.py (if present)',
    f'{DOT} "done" / "quit" to exit',
]

def print_intro():
    print()
    for line in INTRO:
        print(cyan(line))
    print()
    print(bold("PREOPTIONS"))
    for k, v in PREOPTIONS.items():
        print(f"  {yellow(k)}  → {', '.join(v)}")
    print()
    print(bold("OPTIONS"))
    for line in OPTIONS_HELP:
        print(" ", line)
    print()

# -------------------------------
# Main loop
# -------------------------------
def main():
    # Sanity checks for top-level folders
    if not YT2AWS.exists():
        print(red(f"[fatal] Expected folder not found: {YT2AWS}"))
        sys.exit(1)

    print_intro()
    show_dependencies()

    routes = resolve_routes()

    # Show which routes are resolved
    print(bold("Route Resolution"))
    for key in ["link2stems","getaudio","getdetails","gettempo","getkey","getgenre","aisplitter","DrumKitBuilder"]:
        p = routes.get(key)
        if p:
            print(f"  {green('['+CHECK+']')} {key:<13} {dim(str(p))}")
        else:
            print(f"  {red('['+CROSS+']')} {key:<13} {red('no script found')}")
    print("\nType a " + bold("PREOPTION") + " (download / split / music details) or a direct " + bold("OPTION") + " keyword.")
    print("Example: link2stems\n")

    while True:
        try:
            choice = input(bold("> ")).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nbye.\n")
            break

        if choice in ("done", "quit", "exit", "q"):
            print("bye.\n")
            break

        # Expand preoptions to show submenu suggestions
        if choice in PREOPTIONS:
            sub = PREOPTIONS[choice]
            print(bold(f"\n{choice.upper()} options: ") + ", ".join(sub))
            continue

        # Direct option
        if choice in routes and routes[choice] is not None:
            code = run_script(routes[choice])
            print()  # spacer
            if code == 130:
                print(red("Interrupted by user.\n"))
        else:
            print(red("Unknown option or script not found."))
            avail = [k for k in routes if routes[k] is not None]
            if avail:
                print("Try one of: " + ", ".join(avail))
            print()

if __name__ == "__main__":
    main()