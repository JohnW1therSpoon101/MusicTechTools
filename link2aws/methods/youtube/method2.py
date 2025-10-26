#!/usr/bin/env python3
"""
methods/youtube/method2.py — alternate downloader (no cookies)

Strategy:
  • If pytube is installed, use it to fetch audio-only.
  • Else, use yt-dlp to fetch bestaudio (no conversion),
    then convert to WAV with ffmpeg if available.

Prints ONE absolute path on success; exits 0.
"""

from __future__ import annotations
import sys, os, shutil, subprocess
from pathlib import Path
from typing import Optional

def which(n: str) -> Optional[str]: return shutil.which(n)
def downloads_dir() -> Path: return Path.home() / "Downloads"

def most_recent_audio(folder: Path) -> Optional[Path]:
    if not folder.is_dir(): return None
    exts = {".webm", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".mp3", ".wav"}
    files = [p.resolve() for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts]
    if not files: return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]

def pytube_download(url: str, outdir: Path) -> Optional[Path]:
    try:
        from pytube import YouTube
    except Exception:
        return None
    yt = YouTube(url)
    stream = yt.streams.filter(only_audio=True).order_by("abr").desc().first()
    if not stream: return None
    outdir.mkdir(parents=True, exist_ok=True)
    p = Path(stream.download(output_path=str(outdir)))
    return p.resolve() if p.is_file() else None

def ytdlp_bestaudio(url: str, outdir: Path) -> Optional[Path]:
    ytdlp = which("yt-dlp") or which("yt_dlp")
    if not ytdlp: return None
    cmd = [ytdlp, "--no-progress", "--force-ipv4",
           "-o", str(outdir / "%(title)s.%(ext)s"),
           "-f", "bestaudio/best", url]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout or "")
        return None
    return most_recent_audio(outdir)

def convert_to_wav(src: Path) -> Path:
    ffmpeg = which("ffmpeg")
    if not ffmpeg: return src.resolve()
    wav = src.with_suffix(".wav")
    subprocess.run([ffmpeg, "-y", "-i", str(src), "-vn",
                    "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", str(wav)],
                   check=False)
    return wav.resolve() if wav.is_file() else src.resolve()

def main() -> int:
    url = sys.argv[1].strip() if len(sys.argv) >= 2 and sys.argv[1].strip() else os.environ.get("START_URL","").strip()
    if not url:
        print("[method2] No URL passed; expecting start.py to provide it", flush=True)
        return 2
    outdir = downloads_dir() / "method2"
    try:
        p = pytube_download(url, outdir) or ytdlp_bestaudio(url, outdir)
        if not p: raise RuntimeError("method2: no file produced.")
        p = convert_to_wav(p)
        print(str(p))
        return 0
    except Exception as e:
        sys.stderr.write(f"[method2] ERROR: {e}\n")
        return 3

if __name__ == "__main__":
    sys.exit(main())