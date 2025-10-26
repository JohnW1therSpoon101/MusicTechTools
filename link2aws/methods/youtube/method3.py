#!/usr/bin/env python3
"""
method3.py — Selenium-assisted fallback downloader (no cookies)

• Optionally grabs a stable title via Selenium (headless) for nicer filenames.
• Then runs the same clean yt-dlp flow as method1:
    - Direct WAV with --print after_move:filepath (client fallback: web→ios→android)
    - If that fails: bestaudio then local convert (if ffmpeg)
• Accepts positional URL or --url URL.

Prints ONE absolute path on success; exits 0.
"""

from __future__ import annotations
import argparse, sys, shutil, subprocess, re
from pathlib import Path
from typing import Optional, List, Tuple
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ---------- shared helpers (same as method1)

def which(n: str) -> Optional[str]: return shutil.which(n)

def ua() -> str:
    return ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.0.0 Safari/537.36")

INVALID = r'[<>:"/\\|?*\x00-\x1F]'
def sanitize(s: str) -> str:
    s = re.sub(INVALID, " ", s).strip()
    s = re.sub(r"\s{2,}", " ", s)
    return s or "YouTube_Audio"

def run(cmd: List[str]) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout or "", p.stderr or ""

def most_recent_audio(folder: Path) -> Optional[Path]:
    if not folder.is_dir(): return None
    exts = {".wav", ".webm", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".mp3"}
    files = [f.resolve() for f in folder.iterdir() if f.is_file() and f.suffix.lower() in exts]
    if not files: return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]

# ---------- selenium

def make_driver(headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,720")
    opts.add_argument("--autoplay-policy=no-user-gesture-required")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

def get_title(url: str, headless: bool = True) -> Optional[str]:
    try:
        d = make_driver(headless=headless)
    except Exception:
        return None
    try:
        d.get(url)
        t = (d.title or "").replace(" - YouTube","").strip()
        return t or None
    finally:
        try: d.quit()
        except Exception: pass

# ---------- yt-dlp pieces

def dl_wav_print_final(ytdlp: str, url: str, outtmpl: str) -> Optional[Path]:
    base = [
        ytdlp,
        "-x", "--audio-format", "wav", "--audio-quality", "0",
        "--no-progress", "--force-ipv4",
        "--user-agent", ua(),
        "--print", "after_move:filepath",
        "-o", outtmpl,
        url,
    ]
    for client in ("web", "ios", "android"):
        cmd = list(base) + ["--extractor-args", f"youtube:player_client={client}"]
        code, out, err = run(cmd)
        if code == 0:
            lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
            if lines:
                fp = Path(lines[-1]).expanduser()
                if fp.is_file():
                    return fp.resolve()
        if "HTTP Error 403" in err or "network" in err.lower() or "throttle" in err.lower():
            run([ytdlp, "--rm-cache-dir"])
    code, out, _ = run(base)
    if code == 0:
        lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
        if lines:
            fp = Path(lines[-1]).expanduser()
            if fp.is_file():
                return fp.resolve()
    return None

def dl_bestaudio_then_convert(ytdlp: str, ffmpeg: Optional[str], url: str, outtmpl: str) -> Optional[Path]:
    base = [ytdlp, "--no-progress", "--force-ipv4", "--user-agent", ua(), "-o", outtmpl, "-f", "bestaudio/best", url]
    for client in ("web", "ios", "android"):
        cmd = list(base) + ["--extractor-args", f"youtube:player_client={client}"]
        code, out, err = run(cmd)
        if code == 0:
            folder = Path(outtmpl).parent
            src = most_recent_audio(folder)
            if not src: continue
            if ffmpeg:
                wav = src.with_suffix(".wav")
                run([ffmpeg, "-y", "-i", str(src), "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", str(wav)])
                return (wav if wav.is_file() else src).resolve()
            return src.resolve()
        if "HTTP Error 403" in err or "network" in err.lower() or "throttle" in err.lower():
            run([ytdlp, "--rm-cache-dir"])
    code, _, _ = run(base)
    if code == 0:
        folder = Path(outtmpl).parent
        src = most_recent_audio(folder)
        if src:
            if ffmpeg:
                wav = src.with_suffix(".wav")
                run([ffmpeg, "-y", "-i", str(src), "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", str(wav)])
                return (wav if wav.is_file() else src).resolve()
            return src.resolve()
    return None

# ---------- orchestration

def record_youtube_to_audio(url: str, outdir: Path, headless: bool = True, basename: Optional[str] = None) -> Path:
    ytdlp = which("yt-dlp") or which("yt_dlp")
    if not ytdlp:
        raise RuntimeError("yt-dlp not found in PATH.")
    ffmpeg = which("ffmpeg")

    if not basename:
        t = get_title(url, headless=headless)
        if t:
            basename = sanitize(t)

    outtmpl = str(outdir / (f"{basename}.%(ext)s" if basename else "%(title)s.%(ext)s"))
    outdir.mkdir(parents=True, exist_ok=True)

    p = dl_wav_print_final(ytdlp, url, outtmpl)
    if p and p.is_file():
        return p
    p = dl_bestaudio_then_convert(ytdlp, ffmpeg, url, outtmpl)
    if p and p.is_file():
        return p
    mr = most_recent_audio(Path(outtmpl).parent)
    if mr:
        return mr.resolve()
    raise RuntimeError("method3: no file produced.")

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Selenium-assisted fallback downloader (method3)")
    p.add_argument("positional_url", nargs="?", help="(legacy) URL as positional arg")
    p.add_argument("--url", help="YouTube URL")
    p.add_argument("--outdir", default=str(Path.home() / "Downloads"))
    p.add_argument("--basename", default=None)
    p.add_argument("--headless", dest="headless", action="store_true", default=True)
    p.add_argument("--no-headless", dest="headless", action="store_false")
    a = p.parse_args(argv)
    if not (a.url or a.positional_url):
        p.error("URL is required (use --url URL or positional URL).")
    a.url = a.url or a.positional_url
    return a

def main(argv: List[str]) -> int:
    a = parse_args(argv)
    try:
        outdir = Path(a.outdir).expanduser().resolve()
        p = record_youtube_to_audio(a.url, outdir, headless=a.headless, basename=a.basename)
        print(str(p))
        return 0
    except Exception as e:
        sys.stderr.write(f"[method3] ERROR: {e}\n")
        return 3

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))