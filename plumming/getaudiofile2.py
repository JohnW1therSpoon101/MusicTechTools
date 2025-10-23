#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
getaudiofile2.py — TTY file picker
Writes the ABSOLUTE selected path to --write-temp or env PICKER_TEMP_PATH
"""

import os
import sys
import argparse

AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg", ".aif", ".aiff", ".wma", ".alac"}

def resolve_temp_path(args_write_temp: str | None) -> str:
    if args_write_temp:
        return os.path.abspath(os.path.expanduser(args_write_temp))
    env = os.environ.get("PICKER_TEMP_PATH")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, os.pardir)) if os.path.basename(here).lower() == "commandroutes" else here
    tmp_dir = os.path.join(root, ".tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    return os.path.join(tmp_dir, "selected_audio_path.txt")

def list_dir(path: str, show_all: bool) -> tuple[list[str], list[str]]:
    try:
        entries = sorted(os.listdir(path), key=lambda s: s.lower())
    except PermissionError:
        print("Permission denied opening directory. Try a different folder.")
        return [], []
    dirs, files = [], []
    for name in entries:
        p = os.path.join(path, name)
        if os.path.isdir(p):
            dirs.append(name + "/")
        elif os.path.isfile(p):
            ext = os.path.splitext(name)[1].lower()
            if show_all or ext in AUDIO_EXTS:
                files.append(name)
    return dirs, files

def clear_screen():
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        pass

def write_selection(temp_path: str, chosen_abs: str) -> int:
    try:
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(chosen_abs)
            f.flush()
            os.fsync(f.fileno())
        print(chosen_abs)
        print("Selection saved.")
        return 0
    except Exception as e:
        print(f"ERROR writing selection: {e}")
        return 2

def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--write-temp", dest="write_temp", default=None)
    ap.add_argument("-h", "--help", action="store_true")
    args, _ = ap.parse_known_args()
    if args.help:
        print(__doc__)
        return 0

    temp_path = resolve_temp_path(args.write_temp)
    start_dir = os.path.expanduser("~/Downloads")
    if not os.path.isdir(start_dir):
        start_dir = os.path.expanduser("~")
    cwd = os.path.abspath(start_dir)
    show_all = False

    while True:
        clear_screen()
        print("=== Select an audio file ===")
        print(f"Current folder: {cwd}")
        print(f"Writing selection to: {temp_path}")
        print(f"Filter: {'ALL files' if show_all else 'Audio files only'}\n")
        dirs, files = list_dir(cwd, show_all=show_all)

        if not dirs and not files:
            print("(No items)")
        else:
            idx = 1
            index: list[str] = []

            if os.path.dirname(cwd) != cwd:
                print(f"{idx}. ..  (up one folder)")
                index.append(".."); idx += 1

            if dirs:
                print("\nFolders:")
                for d in dirs:
                    print(f"  {idx}. {d}")
                    index.append(d); idx += 1

            if files:
                print("\nFiles:")
                for f in files:
                    print(f"  {idx}. {f}")
                    index.append(f); idx += 1

        print("\nCommands:")
        print("  [number]      open item (folder) or select (file)")
        print("  all           toggle show-all files on/off")
        print("  path          type/paste a path manually")
        print("  q             cancel/quit")
        choice = input("\n> ").strip()

        if not choice:
            continue
        if choice.lower() in {"q", "quit", "exit"}:
            print("Canceled. No file selected.")
            return 1
        if choice.lower() == "all":
            show_all = not show_all; continue
        if choice.lower() == "path":
            custom = input("Paste full file path: ").strip().strip('"').strip()
            if not custom:
                continue
            apath = os.path.abspath(os.path.expanduser(custom))
            if os.path.isfile(apath):
                return write_selection(temp_path, apath)
            else:
                print("That path does not point to a file.")
                input("Press Enter to continue...")
                continue

        if choice.isdigit():
            num = int(choice)
            # rebuild current list
            dirs, files = list_dir(cwd, show_all=show_all)
            rebuild: list[str] = []
            if os.path.dirname(cwd) != cwd:
                rebuild.append("..")
            rebuild += [d for d in dirs] + [f for f in files]
            if not (1 <= num <= len(rebuild)):
                continue
            sel = rebuild[num - 1]
            if sel == "..":
                cwd = os.path.dirname(cwd); continue
            sel_path = os.path.join(cwd, sel.rstrip("/"))
            if os.path.isdir(sel_path):
                cwd = os.path.abspath(sel_path); continue
            else:
                apath = os.path.abspath(sel_path)
                return write_selection(temp_path, apath)

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCanceled.")
        raise SystemExit(130)