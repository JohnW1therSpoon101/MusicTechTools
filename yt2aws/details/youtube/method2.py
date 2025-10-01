#!/usr/bin/env python3
"""
method2.py — Primary: pytube audio-only + ffmpeg -> WAV
Fallback: yt-dlp audio-only -> WAV
Emits: WAV_PATH: /abs/path/to.wav
"""

import sys, shutil, subprocess, time, json
from pathlib import Path

def log(msg): print(msg, flush=True)
def run(cmd, capture=False):
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, text=True, capture_output=capture)

def convert_to_wav(input_path: Path, wav_path: Path) -> bool:
    r = run(["ffmpeg", "-y", "-i", str(input_path), "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", str(wav_path)])
    return r.returncode == 0 and wav_path.exists()

def pytube_path(url: str, downloads: Path) -> Path | None:
    try:
        from pytube import YouTube
    except Exception as e:
        log(f"[method2] pytube not available: {e}")
        return None
    try:
        yt = YouTube(url)
        title = yt.title.strip() if yt.title else "YouTube_Audio"
        out_dir = downloads / title
        out_dir.mkdir(parents=True, exist_ok=True)
        stream = yt.streams.filter(only_audio=True).order_by("abr").desc().first()
        if stream is None:
            log("[method2] No audio-only stream found via pytube.")
            return None
        temp_media = Path(stream.download(output_path=str(out_dir), filename=title))
        if not temp_media.exists():
            log("[method2] pytube download produced no file.")
            return None
        wav_path = out_dir / f"{title}.wav"
        if convert_to_wav(temp_media, wav_path):
            return wav_path
        else:
            log("[method2] ffmpeg conversion failed on pytube file.")
            return None
    except Exception as e:
        log(f"[method2] pytube error: {e}")
        return None

def ytdlp_fallback_path(url: str, downloads: Path) -> Path | None:
    if not shutil.which("yt-dlp"):
        log("[method2] yt-dlp not on PATH for fallback.")
        return None
    # Get title
    meta = run(["yt-dlp", "-J", "--no-playlist", url], capture=True)
    if meta.returncode != 0 or not meta.stdout.strip():
        log("[method2] yt-dlp -J failed for fallback.")
        return None
    try:
        info = json.loads(meta.stdout)
        title = info.get("title") or "YouTube_Audio"
    except Exception as e:
        log(f"[method2] fallback: cannot parse metadata JSON: {e}")
        return None
    out_dir = downloads / title
    out_dir.mkdir(parents=True, exist_ok=True)
    out_tmpl_wav = str(out_dir / f"{title}.%(ext)s")
    r = run([
        "yt-dlp",
        "-x", "--audio-format", "wav", "--audio-quality", "0",
        "-o", out_tmpl_wav,
        "--no-playlist",
        url,
    ])
    if r.returncode != 0:
        log("[method2] yt-dlp fallback extraction failed.")
        return None
    wav_path = out_dir / f"{title}.wav"
    if wav_path.exists():
        return wav_path
    # fallback to newest in out_dir
    cands = list(out_dir.rglob("*.wav"))
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None

def main(argv):
    if not shutil.which("ffmpeg"):
        log("[method2] ffmpeg not found on PATH")
        return 2
    if not argv:
        log("[method2] No URL passed; expecting start.py to provide it")
        return 2

    url = argv[0]
    downloads = Path.home() / "Downloads"
    t0 = time.time()

    # Try pytube path first
    wav = pytube_path(url, downloads)
    if wav is None:
        log("[method2] Falling back to yt-dlp audio-only path...")
        wav = ytdlp_fallback_path(url, downloads)

    if wav and wav.exists():
        print(f"WAV_PATH: {wav}")
        log("[method2] Success")
        return 0

    log("[method2] Failed to obtain WAV via pytube and fallback.")
    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
