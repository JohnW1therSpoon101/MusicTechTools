#!/usr/bin/env python3
"""
getaudiofile1.py

Cross-platform terminal file picker that launches in a NEW terminal window,
starts in the user's Downloads folder, lets you browse folders, and choose
a file or folder with explicit [ Open ] and [ Select ] actions.

Communication back to parent:
  - Always prints:  SELECTED_PATH=/abs/path
  - If env PICKER_OUT=/path/to/tmp.json, writes: {"selected_path": "/abs/path"}

Launcher behavior:
  - If not in child mode, this script re-launches itself in a new terminal window and exits.
  - Child mode runs the picker UI. On selection it exits, allowing the launcher to close the window.

Key bindings (curses UI):
  ↑/k = up, ↓/j = down
  Enter/Right/o = [ Open ] (enter directory if highlighted is a folder)
  s = [ Select ] (select file or folder)
  Backspace/Left/h = go up to parent
  q = quit without selection

Fallback (Windows without curses):
  - Presents a numbered list loop with simple prompts.

Tested on: macOS (Terminal.app), Windows 10/11 (cmd.exe / PowerShell).
"""

import os
import sys
import json
import time
import shutil
import subprocess
from pathlib import Path

IS_CHILD = os.environ.get("PICKER_CHILD") == "1"

def downloads_dir() -> Path:
    home = Path.home()
    candidates = [home / "Downloads", home / "downloads"]
    for c in candidates:
        if c.exists():
            return c
    return home

def write_selection_and_exit(selected: Path):
    abs_path = str(selected.resolve())
    print(f"SELECTED_PATH={abs_path}", flush=True)
    out_file = os.environ.get("PICKER_OUT")
    if out_file:
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump({"selected_path": abs_path}, f)
        except Exception as e:
            print(f"[picker] Warning: failed to write PICKER_OUT file: {e}", file=sys.stderr)
    time.sleep(0.15)
    sys.exit(0)

def relaunch_in_new_terminal():
    this = Path(__file__).resolve()
    env = os.environ.copy()
    env["PICKER_CHILD"] = "1"
    py = sys.executable or "python3"

    if sys.platform.startswith("win"):
        cmdline = f'"{py}" "{this}"'
        full = ['cmd', '/c', 'start', '', 'cmd', '/c', cmdline]
        subprocess.Popen(full, env=env, close_fds=True)
        sys.exit(0)

    elif sys.platform == "darwin":
        osa = f'''
        tell application "Terminal"
            activate
            do script "{py} {this} ; exit"
        end tell
        '''
        subprocess.Popen(["osascript", "-e", osa], env=env, close_fds=True)
        sys.exit(0)

    else:
        for term in ("gnome-terminal", "konsole", "xfce4-terminal", "xterm"):
            if shutil.which(term):
                if term == "gnome-terminal":
                    subprocess.Popen([term, "--", py, str(this)], env=env, close_fds=True)
                elif term == "konsole":
                    subprocess.Popen([term, "-e", py, str(this)], env=env, close_fds=True)
                elif term == "xfce4-terminal":
                    subprocess.Popen([term, "-e", f"{py} {this}"], env=env, close_fds=True)
                else:
                    subprocess.Popen([term, "-e", py, str(this)], env=env, close_fds=True)
                sys.exit(0)
        # Fallback: no terminal found, just continue inline
        pass

def list_dir(path: Path):
    try:
        items = list(path.iterdir())
    except PermissionError:
        return [], []
    dirs = sorted([p for p in items if p.is_dir()], key=lambda p: p.name.lower())
    files = sorted([p for p in items if p.is_file()], key=lambda p: p.name.lower())
    return dirs, files

def try_curses_ui():
    try:
        import curses
    except Exception:
        return False
    start_path = downloads_dir()
    current = start_path

    def draw(stdscr):
        curses.curs_set(0)
        sel_idx = 0
        while True:
            stdscr.clear()
            height, width = stdscr.getmaxyx()

            title = "File Picker — Downloads"
            stdscr.addstr(0, 0, title[:width-1], curses.A_BOLD)
            stdscr.addstr(1, 0, f"Current: {str(current)}"[:width-1])

            btns = "[ Open ]  [ Select ]  [ Back ]  [ Quit ]"
            stdscr.addstr(2, 0, btns[:width-1], curses.A_REVERSE)

            dirs, files = list_dir(current)
            entries = dirs + files
            if not entries:
                stdscr.addstr(4, 2, "(empty)", curses.A_DIM)
            else:
                top = 4
                visible = height - top - 1
                sel_idx = max(0, min(sel_idx, len(entries)-1))
                start = max(0, sel_idx - visible + 1) if len(entries) > visible else 0
                end = min(len(entries), start + visible)
                for i, p in enumerate(entries[start:end], start=start):
                    label = f"[DIR] {p.name}" if p.is_dir() else f"      {p.name}"
                    attr = curses.A_REVERSE if i == sel_idx else curses.A_NORMAL
                    stdscr.addstr(top + (i - start), 2, label[:width-4], attr)

            stdscr.addstr(height-1, 0, "↑/k ↓/j  Enter/→/o=Open   s=Select   ⌫/←/h=Back   q=Quit "[:width-1], curses.A_DIM)
            stdscr.refresh()

            ch = stdscr.getch()
            if ch in (curses.KEY_UP, ord('k')):
                sel_idx = max(0, sel_idx - 1)
            elif ch in (curses.KEY_DOWN, ord('j')):
                sel_idx = min(len(dirs)+len(files)-1, sel_idx + 1) if (dirs or files) else 0
            elif ch in (curses.KEY_LEFT, curses.KEY_BACKSPACE, 127, ord('h')):
                parent = current.parent
                if parent and parent != current:
                    current = parent
                    sel_idx = 0
            elif ch in (curses.KEY_RIGHT, curses.KEY_ENTER, 10, 13, ord('o')):
                entries = (list_dir(current)[0] + list_dir(current)[1])
                if entries:
                    target = entries[sel_idx]
                    if target.is_dir():
                        current = target
                        sel_idx = 0
            elif ch in (ord('s'),):
                entries = (list_dir(current)[0] + list_dir(current)[1])
                if entries:
                    target = entries[sel_idx]
                    write_selection_and_exit(target)
            elif ch in (ord('q'), 27):
                sys.exit(0)

    import curses
    curses.wrapper(draw)
    return True

def fallback_menu_ui():
    current = downloads_dir()
    while True:
        print("\n=== File Picker — Downloads ===")
        print(f"Current: {current}")
        dirs, files = list_dir(current)

        numbered = []
        idx = 1
        if dirs:
            print("\n[Directories]")
            for d in dirs:
                print(f"  {idx}. {d.name}/")
                numbered.append(d)
                idx += 1
        if files:
            print("\n[Files]")
            for f in files:
                print(f"  {idx}. {f.name}")
                numbered.append(f)
                idx += 1

        print("\nActions: (o) Open folder by number   (s) Select by number   (b) Back   (q) Quit")
        choice = input("Enter action (e.g., 'o 3', 's 7', 'b'): ").strip()

        if not choice:
            continue
        if choice.lower() == 'q':
            sys.exit(0)
        if choice.lower() == 'b':
            parent = current.parent
            if parent and parent != current:
                current = parent
            continue

        parts = choice.split()
        if len(parts) != 2 or parts[0].lower() not in ('o', 's'):
            print("Invalid input. Example: o 3  or  s 7")
            continue

        action, num = parts[0].lower(), parts[1]
        if not num.isdigit():
            print("Please provide a number.")
            continue
        n = int(num)
        if n < 1 or n > len(numbered):
            print("Number out of range.")
            continue

        target = numbered[n-1]
        if action == 'o':
            if target.is_dir():
                current = target
            else:
                print("Open only works on directories. Use 's N' to select files.")
        else:
            write_selection_and_exit(target)

def main():
    if os.environ.get("PICKER_CHILD") != "1":
        relaunch_in_new_terminal()
    used_curses = try_curses_ui()
    if not used_curses:
        fallback_menu_ui()

if __name__ == "__main__":
    main()
