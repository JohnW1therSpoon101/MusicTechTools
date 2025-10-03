#!/usr/bin/env python3
"""
getaudiofile.py

A simple, cross-platform terminal browser that:
- Starts in your Downloads folder (override with --start).
- Shows a visual layout (folders first), with pagination.
- Lets you navigate into folders and back out.
- Lets you filter to audio files or search by substring.
- Prints the final chosen audio file path to stdout and logs it.

Controls:
  [number]  Open folder / select file
  ..        Go up one folder
  n / p     Next / previous page
  f         Toggle "audio only" filter
  /text     Filter by substring (case-insensitive). Use just "/" to clear.
  r         Refresh (clear filters)
  q         Quit without selecting

Examples:
  python getaudiofile.py
  python getaudiofile.py --start "C:/Users/You/Downloads" --audio-only
"""

import argparse
import os
import sys
import textwrap
from pathlib import Path
from datetime import datetime

AUDIO_EXTS = {
    ".wav", ".mp3", ".m4a", ".flac", ".aiff", ".aif", ".aac",
    ".ogg", ".oga", ".opus", ".wma"
}

LOG_FILE = Path.cwd() / "getaudiofile.log"
PAGE_SIZE_DEFAULT = 20


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def is_audio(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTS


def human_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for u in units:
        if size < 1024.0:
            return f"{size:.1f} {u}"
        size /= 1024.0
    return f"{size:.1f} PB"


def list_dir(
    folder: Path,
    audio_only: bool = False,
    name_filter: str | None = None,
    show_hidden: bool = False
) -> list[Path]:
    entries: list[Path] = []
    try:
        for p in folder.iterdir():
            if not show_hidden and p.name.startswith("."):
                continue
            if name_filter and name_filter.lower() not in p.name.lower():
                continue
            if audio_only and p.is_file() and not is_audio(p):
                continue
            entries.append(p)
    except PermissionError:
        print("⚠️  Permission denied for this folder.")
        return []
    # Folders first, then files; both alphabetical
    entries.sort(key=lambda p: (0 if p.is_dir() else 1, p.name.lower()))
    return entries


def print_header(path: Path, page_idx: int, page_size: int, total: int, audio_only: bool, name_filter: str | None):
    os.system("cls" if os.name == "nt" else "clear")
    title = f"📁 {str(path)}"
    print("═" * len(title))
    print(title)
    print("═" * len(title))
    filter_bits = []
    if audio_only:
        filter_bits.append("AudioOnly=ON")
    if name_filter:
        filter_bits.append(f'Filter="{name_filter}"')
    if filter_bits:
        print(" • " + " | ".join(filter_bits))
    if total == 0:
        print("\n(No items match.)\n")
    else:
        start = page_idx * page_size + 1
        end = min((page_idx + 1) * page_size, total)
        print(f"\nShowing {start}-{end} of {total} items\n")


def print_entries(entries: list[Path], page_idx: int, page_size: int):
    start = page_idx * page_size
    end = min(start + page_size, len(entries))
    for i, p in enumerate(entries[start:end], start=1):
        idx = start + i  # 1-based across all pages for stable numbering
        if p.is_dir():
            marker = "📂"
            info = ""
        else:
            marker = "🎵" if is_audio(p) else "📄"
            try:
                sz = human_size(p.stat().st_size)
            except OSError:
                sz = "?"
            info = f"  ({sz})"
        name = p.name
        # Truncate very long names nicely
        if len(name) > 90:
            name = name[:87] + "..."
        print(f"{idx:>4}. {marker} {name}{info}")
    print()


def get_downloads_path() -> Path:
    # Cross-platform best guess for Downloads folder
    home = Path.home()
    candidates = [
        home / "Downloads",
        home / "downloads",
    ]
    for c in candidates:
        if c.exists():
            return c
    return home  # Fallback to home if no Downloads


def select_loop(start_path: Path, page_size: int):
    current = start_path.resolve()
    audio_only = False
    name_filter: str | None = None
    page_idx = 0

    while True:
        items = list_dir(current, audio_only=audio_only, name_filter=name_filter, show_hidden=False)
        total = len(items)

        # Clamp page index
        max_page = max((total - 1) // page_size, 0) if total > 0 else 0
        page_idx = max(0, min(page_idx, max_page))

        print_header(current, page_idx, page_size, total, audio_only, name_filter)
        # Always show the "up" shortcut when not at root
        if current.parent != current:
            print("   ..   ⬅️  Go up\n")
        print_entries(items, page_idx, page_size)

        print(textwrap.dedent("""\
            Commands:
              [number]  Open folder / select file
              ..        Go up one folder
              n / p     Next / previous page
              f         Toggle audio-only filter
              /text     Filter by name (use "/" alone to clear)
              r         Refresh (clear filters)
              q         Quit
        """))

        choice = input("> ").strip()

        if choice == "":
            continue
        if choice.lower() == "q":
            print("No file selected.")
            return None
        if choice == "..":
            parent = current.parent
            if parent != current:
                current = parent
                page_idx = 0
            continue
        if choice.lower() == "n":
            if page_idx < max_page:
                page_idx += 1
            continue
        if choice.lower() == "p":
            if page_idx > 0:
                page_idx -= 1
            continue
        if choice.lower() == "f":
            audio_only = not audio_only
            page_idx = 0
            continue
        if choice.lower() == "r":
            audio_only = False
            name_filter = None
            page_idx = 0
            continue
        if choice.startswith("/"):
            name_filter = choice[1:] or None
            page_idx = 0
            continue

        # Numeric selection (global index across all pages)
        try:
            k = int(choice)
        except ValueError:
            print("Invalid input. Enter a number, '..', 'n', 'p', 'f', '/', 'r', or 'q'.")
            input("Press Enter to continue...")
            continue

        if total == 0:
            input("No items to select. Press Enter to continue...")
            continue

        # Convert 1-based global index back to list index
        idx0 = k - 1
        if idx0 < 0 or idx0 >= total:
            input("Index out of range. Press Enter to continue...")
            continue

        target = items[idx0]
        if target.is_dir():
            current = target
            page_idx = 0
            continue
        else:
            if not is_audio(target):
                confirm = input("Selected file is not a known audio type. Select anyway? [y/N]: ").strip().lower()
                if confirm != "y":
                    continue
            return target.resolve()


def main():
    parser = argparse.ArgumentParser(description="Browse and select an audio file from your Downloads (or a custom start folder).")
    parser.add_argument("--start", type=str, default=None, help="Start folder (default: your Downloads)")
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE_DEFAULT, help=f"Items per page (default: {PAGE_SIZE_DEFAULT})")
    parser.add_argument("--audio-only", action="store_true", help="Show only audio files")
    args = parser.parse_args()

    start = Path(args.start).expanduser().resolve() if args.start else get_downloads_path()
    if not start.exists():
        print(f"Start path does not exist: {start}")
        sys.exit(2)

    # Initial screen note
    print(f"Starting in: {start}")
    print("Loading...")

    selected = select_loop(start, page_size=args.page_size)
    if selected is None:
        sys.exit(1)

    # Output and log
    print(str(selected))
    log(f"Selected audio file: {selected}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")