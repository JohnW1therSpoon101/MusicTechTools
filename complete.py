#!/usr/bin/env python3
"""
complete.py
- Prints final banner and file locations.
- Includes METHOD 1 BREAKDOWN and METHOD 2 BREAKDOWN (if logs exist).
- Writes the same report to <root>/PROCESS_COMPLETE.txt

NO "SUMMARY" SECTION CONTENT IS PRINTED (per your instruction). We only list the path.
"""

import argparse
import sys
from pathlib import Path
import time

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}
STEM_HINTS = {"vocals", "drums", "bass", "other", "piano", "guitar", "strings"}

def downloads_root() -> Path:
    return Path.home() / "Downloads"

def find_latest_work_root(dl_root: Path, hours: float = 24.0) -> Path | None:
    cutoff = time.time() - hours * 3600
    candidates = []
    for d in dl_root.iterdir():
        if not d.is_dir():
            continue
        try:
            mtime = d.stat().st_mtime
        except Exception:
            continue
        if mtime < cutoff:
            continue
        has_wav = any(p.suffix.lower() == ".wav" for p in d.rglob("*"))
        if has_wav:
            candidates.append((mtime, d))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]

def short_list(path: Path, max_items: int = 12) -> list[str]:
    items = []
    if path.is_dir():
        for p in sorted(path.iterdir()):
            items.append(p.name)
            if len(items) >= max_items:
                break
    return items

def read_text_if_exists(p: Path, max_chars: int = 4000) -> str | None:
    if p and p.is_file():
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            if len(txt) > max_chars:
                return txt[:max_chars] + "\n... (truncated)"
            return txt
        except Exception:
            return None
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", help="Work folder (<Title> folder). If omitted, auto-detect in Downloads.")
    ap.add_argument("--method1-log", help="Path to Method 1 (yt-dlp) log.")
    ap.add_argument("--method2-log", help="Path to Method 2 (splitter) log.")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve() if args.root else None
    if not root:
        root = find_latest_work_root(downloads_root())
        if not root:
            print(":( no bueno :(  — Could not auto-detect work folder in Downloads.", flush=True)
            sys.exit(2)

    wavs = sorted(root.rglob("*.wav"))
    videos = [p for p in root.rglob("*") if p.suffix.lower() in VIDEO_EXTS]

    stems_dir = None
    direct_stems = root / "stems"
    if direct_stems.is_dir():
        stems_dir = direct_stems
    else:
        for d in root.iterdir():
            if d.is_dir() and any((d / f"{name}.wav").exists() for name in STEM_HINTS):
                stems_dir = d
                break

    summary_txt = root / "summary.txt"

    m1_log = Path(args.method1_log).expanduser().resolve() if args.method1_log else (root / "_logs" / "method1.log")
    m2_log = Path(args.method2_log).expanduser().resolve() if args.method2_log else (root / "_logs" / "method2.log")

    lines = []
    lines.append("================================================================")
    lines.append("PROCESS COMPLETE !")
    lines.append("(FILE LOCATIONS OF EVERYTHING BELOW)")
    lines.append("================================================================")
    lines.append("")
    lines.append(f"WORK FOLDER: {root}")
    lines.append("")

    if wavs:
        lines.append("WAV FILES:")
        for w in wavs[:12]:
            lines.append(f" - {w}")
        if len(wavs) > 12:
            lines.append(f" - ... plus {len(wavs) - 12} more")
        lines.append("")
    else:
        lines.append("WAV FILES: (none found)")
        lines.append("")

    if videos:
        lines.append("VIDEO FILES:")
        for v in videos[:12]:
            lines.append(f" - {v}")
        if len(videos) > 12:
            lines.append(f" - ... plus {len(videos) - 12} more")
        lines.append("")
    else:
        lines.append("VIDEO FILES: (none found)")
        lines.append("")

    if stems_dir and stems_dir.is_dir():
        lines.append(f"STEMS FOLDER: {stems_dir}")
        listing = short_list(stems_dir, max_items=12)
        if listing:
            lines.append("  contents (up to 12):")
            for name in listing:
                lines.append(f"   - {name}")
        lines.append("")
    else:
        lines.append("STEMS FOLDER: (none found)")
        lines.append("")

    if summary_txt.exists():
        lines.append(f"SUMMARY FILE: {summary_txt}")
        lines.append("")
    else:
        lines.append("SUMMARY FILE: (summary.txt not found)")
        lines.append("")

    # ---- METHOD BREAKDOWNS
    lines.append("METHOD 1 BREAKDOWN:")
    txt1 = read_text_if_exists(m1_log) if m1_log.exists() else None
    if txt1:
        lines.append("----------------------------------------------------------------")
        lines.append(txt1.strip())
        lines.append("----------------------------------------------------------------")
    else:
        lines.append("(no method 1 log found)")
    lines.append("")

    lines.append("METHOD 2 BREAKDOWN:")
    txt2 = read_text_if_exists(m2_log) if m2_log.exists() else None
    if txt2:
        lines.append("----------------------------------------------------------------")
        lines.append(txt2.strip())
        lines.append("----------------------------------------------------------------")
    else:
        lines.append("(no method 2 log found)")
    lines.append("")

    report = "\n".join(lines)
    print(report, flush=True)

    out_txt = root / "PROCESS_COMPLETE.txt"
    try:
        out_txt.write_text(report, encoding="utf-8")
        print(f"[complete] Wrote: {out_txt}", flush=True)
    except Exception as e:
        print(f"[complete] Could not write PROCESS_COMPLETE.txt: {e}", flush=True)

if __name__ == "__main__":
    main()
