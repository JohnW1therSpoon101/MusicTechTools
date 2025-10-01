#!/usr/bin/env python3
"""
summarize.py
- Takes results and puts properties into a text file.
- Gathers output from:
  - findtemp.py
  - (findkey.py - disregard for now)
- Creates summary text:
  OUTPUT = [
      - DISPLAY : "findtemp.py output"
  ]
Usage:
  python details/summarize.py --wav "<path to wav>" [--out "<summary.txt path>"] [--findtemp-log "<existing log path>"]
"""

import argparse
import subprocess
import sys
from pathlib import Path
import re
import datetime

def run_findtemp(wav_path: Path, repo_root: Path) -> str:
    findtemp_py = repo_root / "details" / "findtemp.py"
    if not findtemp_py.is_file():
        return "[summarize] findtemp.py not found; skipping tempo run."

    try:
        proc = subprocess.run(
            [sys.executable, str(findtemp_py), str(wav_path)],
            check=False, capture_output=True, text=True
        )
        # Return stdout + stderr for completeness
        out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return out.strip()
    except Exception as e:
        return f"[summarize] Error running findtemp.py: {e}"

def parse_aggregate_bpm(text: str) -> str:
    # Looks for a line like: "Aggregate (median): 130.81 BPM"
    m = re.search(r"Aggregate\s*\(median\)\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*BPM", text, re.IGNORECASE)
    return m.group(1) if m else ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True, help="Path to the main WAV file.")
    ap.add_argument("--out", help="Path to write summary.txt (default: <wav parent>/summary.txt).")
    ap.add_argument("--findtemp-log", help="If provided, use this text instead of invoking findtemp.py.")
    args = ap.parse_args()

    wav_path = Path(args.wav).expanduser().resolve()
    if not wav_path.is_file():
        print(f"[summarize] WAV not found: {wav_path}", flush=True)
        sys.exit(2)

    out_path = Path(args.out).expanduser().resolve() if args.out else wav_path.parent / "summary.txt"
    repo_root = Path(__file__).resolve().parents[1]

    # Get findtemp output
    if args.findtemp_log:
        ft_text = Path(args.findtemp_log).read_text(encoding="utf-8", errors="ignore")
    else:
        ft_text = run_findtemp(wav_path, repo_root)

    bpm = parse_aggregate_bpm(ft_text)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build the summary
    lines = []
    lines.append(f"SUMMARY GENERATED: {now}")
    lines.append(f"WAV FILE: {wav_path}")
    if bpm:
        lines.append(f"TEMPO (Aggregate/Median): {bpm} BPM")
    lines.append("")
    lines.append('DISPLAY : "findtemp.py output"')
    lines.append("-" * 72)
    lines.append(ft_text.strip())
    lines.append("-" * 72)
    lines.append("")
    lines.append("(findkey.py results omitted by design)")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[summarize] Wrote summary: {out_path}", flush=True)

if __name__ == "__main__":
    main()
