#!/usr/bin/env python3
# startgetaudio.py — get link -> download audio with yt-dlp -> report file path
# Location: MusicTechTools/commandroutes/startgetaudio.py

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List

# ─── styling ─────────────────────────────────────────────────────────────────
BOLD = "\033[1m"; DIM = "\033[2m"; RED = "\033[31m"; GRN = "\033[32m"; YLW = "\033[33m"; CYN = "\033[36m"; RST = "\033[0m"
def bold(s):   return f"{BOLD}{s}{RST}"
def dim(s):    return f"{DIM}{s}{RST}"
def red(s):    return f"{RED}{s}{RST}"
def green(s):  return f"{GRN}{s}{RST}"
def yellow(s): return f"{YLW}{s}{RST}"
def cyan(s):   return f"{CYN}{s}{RST}"

# ─── paths ───────────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent             # .../MusicTechTools/commandroutes
REPO_ROOT = HERE.parent                            # .../MusicTechTools

# output directory for audio files
OUT_DIR = Path.home() / "Downloads" / "MusicTechTools" / "Audio"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# executables
YTDLP_EXE = shutil.which("yt-dlp") or "/opt/homebrew/bin/yt-dlp"  # you have this
FFMPEG_EXE = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"

# ─── helpers ─────────────────────────────────────────────────────────────────
def run_capture(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def parse_link(stdout: str) -> Optional[str]:
    """
    Accept lines like:
      SELECTED_LINK: https://...
      LINK: https://...
    """
    markers = ("SELECTED_LINK:", "LINK:")
    for line in stdout.splitlines():
        s = line.strip()
        for m in markers:
            if s.startswith(m):
                url = s[len(m):].strip()
                if url:
                    return url
    return None

def ask_link_interactively() -> Optional[str]:
    print(cyan(bold("=INSERTLINK=")))
    try:
        raw = input(bold("> ")).strip()
    except (KeyboardInterrupt, EOFError):
        return None
    return raw if raw else None

def find_anywhere(filename: str, root: Path) -> Optional[Path]:
    try:
        for p in root.rglob(filename):
            if p.is_file():
                return p
    except Exception:
        pass
    return None

def get_link_via_script_or_prompt(log: List[str]) -> Optional[str]:
    # find any getlink.py anywhere under repo
    gl = find_anywhere("getlink.py", REPO_ROOT)
    if gl:
        cmd = [sys.executable, str(gl)]
        log.append(dim(f"$ {' '.join(cmd)}"))
        try:
            proc = run_capture(cmd)
        except Exception as e:
            log.append(yellow(f"[getlink] failed to launch ({e}); asking manually."))
            return ask_link_interactively()
        if proc.stdout:
            log.append(dim("[getlink:stdout]\n" + proc.stdout))
        if proc.stderr:
            log.append(dim("[getlink:stderr]\n" + proc.stderr))
        link = parse_link(proc.stdout)
        if link:
            return link
        log.append(yellow("[getlink] did not print a LINK; asking manually."))
    else:
        log.append(dim("[getlink] not found anywhere; asking manually."))
    return ask_link_interactively()

def yt_dlp_download(link: str, log: List[str]) -> Optional[Path]:
    """
    Use yt-dlp executable directly to extract best audio to WAV.
    We rely on --print after_move:filepath (recent yt-dlp) to get the final path.
    """
    if not YTDLP_EXE:
        log.append(red("[yt-dlp] not found on PATH"))
        return None
    if not FFMPEG_EXE:
        # yt-dlp can still download without ffmpeg, but won't convert to wav
        # We'll still try; result could be .m4a/.webm
        log.append(yellow("[ffmpeg] not found; will keep source audio extension."))

    # output template with absolute path (yt-dlp will create folders)
    # Note: use POSIX-style path; yt-dlp handles it fine on macOS
    out_tpl = str((OUT_DIR / "%(title)s.%(ext)s").resolve())

    cmd = [
        YTDLP_EXE,
        "--no-playlist",
        "--newline",
        "--restrict-filenames",
        "--ignore-errors",
        "--no-overwrites",
        "--add-metadata",
        "--output", out_tpl,
        "--print", "after_move:filepath",
    ]

    # If ffmpeg present, convert to wav
    if FFMPEG_EXE:
        cmd += ["--extract-audio", "--audio-format", "wav", "--audio-quality", "0"]

    cmd.append(link)
    log.append(dim(f"$ {' '.join(cmd)}"))

    try:
        # We *capture* to parse the printed final path, but also mirror lines for user feedback
        proc = run_capture(cmd)
    except Exception as e:
        log.append(red(f"[yt-dlp] failed to launch: {e}"))
        return None

    if proc.stdout:
        log.append(dim("[yt-dlp:stdout]\n" + proc.stdout))
    if proc.stderr:
        log.append(dim("[yt-dlp:stderr]\n" + proc.stderr))

    # Prefer the printed filepath from --print after_move:filepath
    chosen = None
    for line in proc.stdout.splitlines()[::-1]:
        s = line.strip()
        if s and (OUT_DIR.as_posix() in s or str(OUT_DIR) in s):
            p = Path(s).expanduser()
            if p.exists():
                chosen = p
                break

    # Fallback: try to find the newest file created in OUT_DIR
    if not chosen and OUT_DIR.exists():
        try:
            newest = max((f for f in OUT_DIR.rglob("*") if f.is_file()), key=lambda p: p.stat().st_mtime, default=None)
            if newest:
                chosen = newest
        except Exception:
            pass

    if proc.returncode != 0 and not chosen:
        log.append(yellow(f"[yt-dlp] exited code {proc.returncode} and no file detected"))
        return None

    return chosen

def try_legacy_method(name: str, link: str, log: List[str]) -> Optional[Path]:
    """
    If a legacy downloader exists (method2.py / method3.py), try it.
    Expect it to accept the link as the first arg and print:
      DOWNLOADED_FILE: /abs/path
    """
    script = find_anywhere(name, REPO_ROOT)
    if not script:
        log.append(dim(f"[{name}] not present; skipping"))
        return None
    cmd = [sys.executable, str(script), link]
    log.append(dim(f"$ {' '.join(cmd)}"))
    try:
        proc = run_capture(cmd)
    except Exception as e:
        log.append(yellow(f"[{name}] failed to launch: {e}"))
        return None
    if proc.stdout:
        log.append(dim(f"[{name}:stdout]\n" + proc.stdout))
    if proc.stderr:
        log.append(dim(f"[{name}:stderr]\n" + proc.stderr))
    # parse path
    marker = "DOWNLOADED_FILE:"
    for line in proc.stdout.splitlines():
        s = line.strip()
        if s.startswith(marker):
            p = Path(s[len(marker):].strip()).expanduser().resolve()
            if p.exists():
                return p
    return None

# ─── main ────────────────────────────────────────────────────────────────────
def main():
    log: List[str] = []

    # 1) Collect link
    link = get_link_via_script_or_prompt(log)
    if not link:
        print(red("No link provided."))
        print("==ProcessFailed==")
        if log:
            print("\n--- LOG ---")
            for line in log: print(line)
        sys.exit(1)

    # 2) Primary: yt-dlp direct download
    downloaded = yt_dlp_download(link, log)

    # 3) Fallbacks: method2, method3 if they exist anywhere
    if downloaded is None:
        downloaded = try_legacy_method("method2.py", link, log)
    if downloaded is None:
        downloaded = try_legacy_method("method3.py", link, log)

    # 4) Outcome
    if downloaded and downloaded.exists():
        print(green(f"Download complete: {downloaded}"))
        print(f"DOWNLOADED_FILE: {downloaded}")
        sys.exit(0)
    else:
        print(red("Download failed via available methods."))
        print("==ProcessFailed==")
        if log:
            print("\n--- LOG ---")
            for line in log: print(line)
        sys.exit(1)

if __name__ == "__main__":
    main()