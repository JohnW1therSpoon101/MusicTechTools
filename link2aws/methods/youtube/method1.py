#!/usr/bin/env python3
"""
YouTube audio downloader (method1) — clean final-path version (no cookies)

Flow:
  1) Try yt-dlp extract ↦ WAV with --print after_move:filepath
     • Client fallback order: web → ios → android (to avoid PO-token noise)
  2) If that fails, download bestaudio and locally convert to WAV (if ffmpeg)
  3) If still nothing, return newest audio file in the target folder.

On success: prints ONE absolute path (single line), exits 0.
On failure: prints error to stderr, exits 3.

Usage:
  method1.py <URL> [outdir]
"""

from __future__ import annotations
import sys, shutil, subprocess, re
from pathlib import Path
from typing import Optional, List, Tuple

# ---------- helpers

def _which(name: str) -> Optional[str]:
    return shutil.which(name)

def _ua() -> str:
    return ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.0.0 Safari/537.36")

INVALID = r'[<>:"/\\|?*\x00-\x1F]'
def _sanitize(s: str) -> str:
    s = re.sub(INVALID, " ", s).strip()
    s = re.sub(r"\s{2,}", " ", s)
    return s or "YouTube_Audio"

def _title(ytdlp: str, url: str) -> str:
    for cmd in ([ytdlp, "-O", "%(title)s", url],
                [ytdlp, "--print", "%(title)s", url]):
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, check=False)
            t = (p.stdout or "").strip()
            if t:
                return t
        except Exception:
            pass
    return "YouTube_Audio"

def _most_recent_audio(folder: Path) -> Optional[Path]:
    if not folder.is_dir(): return None
    exts = {".wav", ".webm", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".mp3"}
    files = [f.resolve() for f in folder.iterdir() if f.is_file() and f.suffix.lower() in exts]
    if not files: return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]

def _run(cmd: List[str]) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout or "", p.stderr or ""

# ---------- yt-dlp runners

def _dl_wav_print_final(ytdlp: str, url: str, outtmpl: str) -> Optional[Path]:
    """Direct to WAV using --print after_move:filepath; client fallback inside."""
    base = [
        ytdlp,
        "-x", "--audio-format", "wav", "--audio-quality", "0",
        "--no-progress", "--force-ipv4",
        "--user-agent", _ua(),
        "--print", "after_move:filepath",
        "-o", outtmpl,
        url,
    ]
    for client in ("web", "ios", "android"):
        cmd = list(base) + ["--extractor-args", f"youtube:player_client={client}"]
        code, out, err = _run(cmd)
        if code == 0:
            # yt-dlp prints the final path as the last non-empty line
            lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
            if not lines:
                continue
            final = Path(lines[-1]).expanduser()
            if final.is_file():
                return final.resolve()
        # clear cache on typical network/throttle/403 hints
        if "HTTP Error 403" in err or "network" in err.lower() or "throttle" in err.lower():
            _run([ytdlp, "--rm-cache-dir"])
    # last try without extractor-args
    code, out, _ = _run(base)
    if code == 0:
        lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
        if lines:
            fp = Path(lines[-1]).expanduser()
            if fp.is_file():
                return fp.resolve()
    return None

def _dl_bestaudio_then_convert(ytdlp: str, ffmpeg: Optional[str], url: str, outtmpl: str) -> Optional[Path]:
    base = [
        ytdlp, "--no-progress", "--force-ipv4",
        "--user-agent", _ua(),
        "-f", "bestaudio/best",
        "-o", outtmpl,
        url,
    ]
    for client in ("web", "ios", "android"):
        cmd = list(base) + ["--extractor-args", f"youtube:player_client={client}"]
        code, out, err = _run(cmd)
        if code == 0:
            folder = Path(outtmpl).parent
            src = _most_recent_audio(folder)
            if not src:
                continue
            if ffmpeg:
                wav = src.with_suffix(".wav")
                _run([ffmpeg, "-y", "-i", str(src), "-vn",
                      "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", str(wav)])
                return (wav if wav.is_file() else src).resolve()
            return src.resolve()
        if "HTTP Error 403" in err or "network" in err.lower() or "throttle" in err.lower():
            _run([ytdlp, "--rm-cache-dir"])
    # last try without extractor-args
    code, _, _ = _run(base)
    if code == 0:
        folder = Path(outtmpl).parent
        src = _most_recent_audio(folder)
        if src:
            if ffmpeg:
                wav = src.with_suffix(".wav")
                _run([ffmpeg, "-y", "-i", str(src), "-vn",
                      "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", str(wav)])
                return (wav if wav.is_file() else src).resolve()
            return src.resolve()
    return None

# ---------- main work

def download_audio(url: str, outdir: Optional[Path] = None) -> Path:
    ytdlp = _which("yt-dlp") or _which("yt_dlp")
    if not ytdlp:
        raise RuntimeError("yt-dlp not found in PATH.")
    ffmpeg = _which("ffmpeg")  # may be None

    base_dir = (outdir or Path.home() / "Downloads")
    base_dir.mkdir(parents=True, exist_ok=True)

    title = _title(ytdlp, url)
    outtmpl = str(base_dir / _sanitize(title) / "%(title)s.%(ext)s")
    Path(outtmpl).parent.mkdir(parents=True, exist_ok=True)

    # Single pass with internal fallbacks
    p = _dl_wav_print_final(ytdlp, url, outtmpl)
    if p and p.is_file():
        return p

    p = _dl_bestaudio_then_convert(ytdlp, ffmpeg, url, outtmpl)
    if p and p.is_file():
        return p

    # last resort: any audio in the target folder
    last = _most_recent_audio(Path(outtmpl).parent)
    if last:
        return last.resolve()

    raise RuntimeError("method1: no file produced.")

def main(argv: List[str]) -> int:
    url = argv[0].strip() if len(argv) >= 1 else ""
    outdir = Path(argv[1]).expanduser() if len(argv) >= 2 else None
    if not url:
        sys.stderr.write("[method1] Usage: method1.py <url> [outdir]\n")
        return 2
    try:
        p = download_audio(url, outdir)
        print(str(p))  # print ONCE
        return 0
    except Exception as e:
        sys.stderr.write(f"[method1] ERROR: {e}\n")
        return 3

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))