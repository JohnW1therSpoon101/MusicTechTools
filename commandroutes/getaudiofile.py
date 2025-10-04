#!/usr/bin/env python3
# getaudiofile.py — interactive audio file picker (controls at the bottom)
# Prints: SELECTED_FILE: /absolute/path/to/file.ext
# Also writes the same path to env MUSICTECH_PICK_OUT (if set).

import os, sys
from pathlib import Path
from typing import List, Tuple

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".aiff", ".aif", ".m4a", ".ogg", ".wma", ".aac"}
PAGE_SIZE = 20

BOLD = "\033[1m"; DIM = "\033[2m"; RESET = "\033[0m"; CYAN = "\033[36m"; YELLOW = "\033[33m"
def bold(s): return f"{BOLD}{s}{RESET}"
def dim(s): return f"{DIM}{s}{RESET}"
def cyan(s): return f"{CYAN}{s}{RESET}"
def yellow(s): return f"{YELLOW}{s}{RESET}"

def human_path(p: Path) -> str:
    return str(p).replace(str(Path.home()), "~")

def list_dir(cur: Path, audio_only: bool) -> Tuple[List[Path], List[Path]]:
    try:
        items = list(cur.iterdir())
    except Exception:
        items = []
    dirs = sorted([x for x in items if x.is_dir()])
    files = sorted([x for x in items if x.is_file() and (not audio_only or x.suffix.lower() in AUDIO_EXTS)])
    return dirs, files

def print_page(dirs: List[Path], files: List[Path], page: int):
    start = page * PAGE_SIZE
    rows: List[Path] = dirs + files
    if not rows:
        print(yellow("(empty folder)"))
        return 0
    for i, entry in enumerate(rows[start:start+PAGE_SIZE], start=1+start):
        tag = "[DIR] " if entry.is_dir() else "[FILE]"
        print(f"{i:>3}  {tag} {entry.name}")
    return len(rows)

def default_start_dir() -> Path:
    dl = Path.home() / "Downloads"
    return dl if dl.exists() else Path.cwd()

def controls_line():
    # single compact line of controls — shown at the BOTTOM
    return dim("Commands: number=open/select • u=up • n/p=next/prev • a=toggle audio/all • dl=Downloads • home=~ • q=quit")

def pick():
    cur = default_start_dir()
    audio_only = True
    page = 0
    while True:
        dirs, files = list_dir(cur, audio_only)
        total = len(dirs) + len(files)
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE or 1
        if page >= pages:
            page = max(pages - 1, 0)

        # header (short) — then LIST — then CONTROLS at the bottom
        print()
        print(cyan(bold("Locate your file..")))
        print(f"{bold('Current:')} {human_path(cur)}   {bold('Filter:')} {'Audio only' if audio_only else 'All files'}   {bold('Page:')} {page+1}/{pages}")
        total_rows = print_page(dirs, files, page)

        # bottom controls
        print(controls_line())
        try:
            choice = input(bold("> ")).strip()
        except (KeyboardInterrupt, EOFError):
            return None

        if not choice:
            continue
        c = choice.lower()

        if c in ("q","quit","exit"):
            return None
        if c in ("u","up",".."):
            if cur.parent != cur:
                cur = cur.parent; page = 0
            continue
        if c in ("n","next"):
            if page + 1 < pages: page += 1
            continue
        if c in ("p","prev","previous"):
            if page > 0: page -= 1
            continue
        if c in ("a","all","audio"):
            audio_only = not audio_only; page = 0
            continue
        if c in ("dl","downloads"):
            dl = Path.home() / "Downloads"
            if dl.exists():
                cur = dl; page = 0
            else:
                print(yellow("Downloads folder not found."))
            continue
        if c in ("home","~"):
            cur = Path.home(); page = 0
            continue

        # direct path paste
        p = Path(choice).expanduser()
        if p.exists():
            if p.is_file():
                return p.resolve()
            if p.is_dir():
                cur = p.resolve(); page = 0
                continue

        # numeric selection
        if c.isdigit():
            idx = int(c)
            if 1 <= idx <= total_rows:
                target = (dirs + files)[idx - 1]
                if target.is_dir():
                    cur = target; page = 0
                    continue
                if target.is_file():
                    return target.resolve()

        print(yellow("Unrecognized command."))

def main():
    sel = pick()
    if sel is None:
        sys.exit(1)

    # Tell the caller
    print(f"SELECTED_FILE: {sel}")

    # Also write to a temp file if provided
    out_path = os.environ.get("MUSICTECH_PICK_OUT")
    if out_path:
        try:
            Path(out_path).write_text(str(sel), encoding="utf-8")
        except Exception:
            pass

    sys.exit(0)

if __name__ == "__main__":
    main()