#!/usr/bin/env python3
"""
getaudiofile1.py
Interactive file picker focused on audio files (Windows + macOS/Linux).

- Tries to use curses TUI if available; falls back to simple menu otherwise.
- Starts in ~/Downloads; you can navigate anywhere.
- Prints ONE absolute file path to stdout, then exits 0 (exit 1 if canceled).
- NEW: If env var PICKER_OUTFILE is set, also writes the same path to that file
  so callers (e.g., startdetails.py) can read it when running in another terminal.
"""

import os
import sys
import traceback
from pathlib import Path
from typing import List, Tuple

# ---------- Optional curses import (Windows-safe) ----------
HAS_CURSES = True
try:
    import curses  # type: ignore
except Exception:
    curses = None  # type: ignore
    HAS_CURSES = False

AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus"}

def downloads_dir() -> Path:
    home = Path.home()
    d = home / "Downloads"
    return d if d.exists() else home

def list_dir(path: Path) -> Tuple[List[Path], List[Path]]:
    try:
        items = list(path.iterdir())
    except (PermissionError, FileNotFoundError):
        items = []
    dirs = sorted([p for p in items if p.is_dir()], key=lambda p: p.name.lower())
    files = sorted([p for p in items if p.is_file()], key=lambda p: p.name.lower())
    return dirs, files

def is_audio(p: Path) -> bool:
    return p.suffix.lower() in AUDIO_EXTS

# -----------------------------
# Curses UI (only if available)
# -----------------------------
def curses_picker() -> Path | None:
    if not HAS_CURSES:
        return None

    current_path = downloads_dir().resolve()
    selected_idx = 0
    selected_file: Path | None = None

    def build_entries(path: Path) -> List[Path]:
        dirs, files = list_dir(path)
        entries = []
        if path.parent != path:
            entries.append(path.parent)  # ".."
        entries.extend(dirs)
        entries.extend(files)
        return entries

    entries = build_entries(current_path)

    def draw(stdscr):
        nonlocal current_path, selected_idx, selected_file, entries

        try:
            curses.curs_set(0)
        except Exception:
            pass
        stdscr.nodelay(False)
        stdscr.keypad(True)

        while True:
            stdscr.clear()
            height, width = stdscr.getmaxyx()

            title = " Audio File Picker "
            try:
                stdscr.addstr(0, max(0, (width - len(title)) // 2), title, curses.A_BOLD)
            except Exception:
                stdscr.addstr(0, 0, title)

            path_line = f"Current: {str(current_path)}"
            stdscr.addstr(1, 0, path_line[: max(0, width - 1)])

            help_line = "↑/↓ or j/k = move • Enter = open/select • Backspace = up • q = quit"
            try:
                stdscr.addstr(2, 0, help_line[: max(0, width - 1)], curses.A_DIM)
            except Exception:
                stdscr.addstr(2, 0, help_line[: max(0, width - 1)])

            start_row = 4
            visible_rows = max(1, height - start_row - 1)

            if not entries:
                selected_idx = 0
            else:
                selected_idx = max(0, min(selected_idx, len(entries) - 1))

            top = 0
            if selected_idx >= visible_rows:
                top = selected_idx - visible_rows + 1
            window_entries = entries[top : top + visible_rows]

            for i, p in enumerate(window_entries):
                row = start_row + i
                is_selected = (top + i) == selected_idx

                if p.is_dir():
                    label = f"[DIR] {p.name}" if p != current_path.parent else "[UP] .."
                else:
                    label = f"{p.name}"
                    if is_audio(p):
                        label = f"[AUDIO] {label}"

                label = label[: max(0, width - 2)]
                try:
                    if is_selected:
                        stdscr.addstr(row, 0, label, curses.A_REVERSE)
                    else:
                        stdscr.addstr(row, 0, label)
                except Exception:
                    pass

            info = f"{len(entries)} items" if entries else "Empty directory"
            try:
                stdscr.addstr(height - 1, 0, info[: max(0, width - 1)], curses.A_DIM)
            except Exception:
                stdscr.addstr(height - 1, 0, info[: max(0, width - 1)])

            key = stdscr.getch()

            if key in (curses.KEY_UP, ord('k')):
                if entries:
                    selected_idx = max(0, selected_idx - 1)
            elif key in (curses.KEY_DOWN, ord('j')):
                if entries:
                    selected_idx = min(len(entries) - 1, selected_idx + 1)
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                if current_path.parent != current_path:
                    current_path = current_path.parent
                    entries = build_entries(current_path)
                    selected_idx = 0
            elif key in (curses.KEY_ENTER, 10, 13):
                if not entries:
                    continue
                target = entries[selected_idx]
                if target.is_dir():
                    current_path = target.resolve()
                    entries = build_entries(current_path)
                    selected_idx = 0
                else:
                    selected_file = target.resolve()
                    return
            elif key in (ord('q'), ord('Q')):
                selected_file = None
                return
            else:
                pass

    try:
        curses.wrapper(draw)
    except Exception:
        sys.stderr.write("[getaudiofile1] Curses UI failed, falling back to basic menu.\n")
        sys.stderr.write(traceback.format_exc() + "\n")
        return None

    return selected_file

# -----------------------------
# Fallback (non-curses) UI
# -----------------------------
def fallback_picker() -> Path | None:
    current_path = downloads_dir().resolve()
    while True:
        print("\n== Audio File Picker (fallback) ==")
        print(f"Current: {current_path}")
        dirs, files = list_dir(current_path)

        menu: list[tuple[str, Path]] = []
        if current_path.parent != current_path:
            menu.append((".. (Up)", current_path.parent))
        for d in dirs:
            menu.append((f"[DIR] {d.name}", d))
        for f in files:
            tag = "[AUDIO]" if is_audio(f) else "       "
            menu.append((f"{tag} {f.name}", f))

        for i, (label, _) in enumerate(menu, start=1):
            print(f"{i:2d}. {label}")
        print(" q. Quit")

        choice = input("Select number (Enter to refresh): ").strip()
        if choice.lower() == "q":
            return None
        if not choice:
            continue
        if not choice.isdigit():
            print("Enter a valid number.")
            continue

        idx = int(choice) - 1
        if idx < 0 or idx >= len(menu):
            print("Out of range.")
            continue

        target = menu[idx][1]
        if target.is_dir():
            current_path = target.resolve()
            continue
        else:
            return target.resolve()

# -----------------------------
# Main
# -----------------------------
def main() -> None:
    prefer_curses = HAS_CURSES and sys.stdin.isatty() and sys.stdout.isatty()

    selected: Path | None = None
    if prefer_curses:
        selected = curses_picker() or None

    if selected is None:
        selected = fallback_picker()

    if selected is None:
        sys.exit(1)

    # Print absolute path
    path_str = str(selected)
    print(path_str)

    # ALSO write to outfile if requested (for external-terminal orchestration)
    outfile = os.environ.get("PICKER_OUTFILE", "").strip()
    if outfile:
        try:
            with open(outfile, "w", encoding="utf-8") as f:
                f.write(path_str)
        except Exception as e:
            sys.stderr.write(f"[getaudiofile1] WARN: Could not write PICKER_OUTFILE: {e}\n")

    sys.exit(0)

if __name__ == "__main__":
    main()