#!/usr/bin/env python3
import sys, shutil, subprocess, json, time
from pathlib import Path

def log(msg): print(msg, flush=True)

def run(cmd, capture=False):
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, text=True, capture_output=capture)

def main(argv):
    if not shutil.which("yt-dlp"):
        log("[method1] yt-dlp not found on PATH")
        return 2
    if not shutil.which("ffmpeg"):
        log("[method1] ffmpeg not found on PATH")
        return 2
    if not argv:
        log("[method1] No URL passed; expecting start.py to provide it")
        return 2

    url = argv[0]
    downloads = Path.home() / "Downloads"

    # 0) Get title deterministically
    meta = run(["yt-dlp", "-J", "--no-playlist", url], capture=True)
    if meta.returncode != 0 or not meta.stdout.strip():
        log("[method1] Failed to read metadata (-J).")
        if meta.stderr: log(meta.stderr.strip())
        return 3
    try:
        info = json.loads(meta.stdout)
        title = info.get("title") or "YouTube_Audio"
    except Exception as e:
        log(f"[method1] Could not parse metadata JSON: {e}")
        return 3

    out_dir = downloads / title
    out_dir.mkdir(parents=True, exist_ok=True)
    wav_path = out_dir / f"{title}.wav"

    t0 = time.time()

    # 1) Download video (keep original)
    out_tmpl_video = str(out_dir / f"{title}.%(ext)s")
    r1 = run([
        "yt-dlp",
        "-f", "bv*+ba/best",
        "-o", out_tmpl_video,
        "--no-playlist",
        "--merge-output-format", "mp4",
        url,
    ])
    if r1.returncode != 0:
        log("[method1] Video download failed")
        return r1.returncode

    # 2) Extract WAV
    out_tmpl_wav = str(out_dir / f"{title}.%(ext)s")
    r2 = run([
        "yt-dlp",
        "-x", "--audio-format", "wav", "--audio-quality", "0",
        "-o", out_tmpl_wav,
        "--no-playlist",
        url,
    ])
    if r2.returncode != 0:
        log("[method1] WAV extraction failed")
        return r2.returncode

    # 3) Verify expected path; fallback to newest after t0 if needed
    if not wav_path.exists():
        cands = [p for p in out_dir.rglob("*.wav") if p.stat().st_mtime >= (t0 - 5)]
        if cands:
            wav_path = max(cands, key=lambda p: p.stat().st_mtime)
        else:
            # As last resort, check Downloads recursively after t0
            all_cands = [p for p in downloads.rglob("*.wav") if p.stat().st_mtime >= (t0 - 5)]
            if all_cands:
                wav_path = max(all_cands, key=lambda p: p.stat().st_mtime)
            else:
                log("[method1] Could not find WAV after extraction.")
                return 3

    print(f"WAV_PATH: {wav_path}")
    log("[method1] Success")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
