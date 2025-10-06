#!/usr/bin/env python3
"""
instamethod1.py

Takes an Instagram Reels/shorts link, downloads the video with yt-dlp,
extracts WAV audio via ffmpeg, and writes both video + audio to the user's
Downloads folder.

Usage (interactive):
    python instamethod1.py
    # then paste the Instagram link when prompted

Usage (CLI):
    python instamethod1.py "https://www.instagram.com/reel/XXXXXXXXX/"

Notes:
- Requires ffmpeg on PATH.
- If yt-dlp is missing, this script will attempt to install it.
- If your Instagram links require login (private accounts), place a
  Netscape-format cookies file named 'cookies.txt' next to this script
  or in the repository root; it will be detected automatically.

Outputs:
- <Downloads>/<Title> [<id>].mp4
- <Downloads>/<Title> [<id>].wav
"""

from __future__ import annotations
import sys
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# ---------------------------
# Helpers
# ---------------------------

def _print_header() -> None:
    print("\n[insta] Instagram → Video → Audio (WAV)")
    print("[insta] Built for MusicTechTools / youtube2audaisplitter")
    print("---------------------------------------------------------")

def find_downloads_folder() -> Path:
    """
    Resolve a sensible Downloads folder on macOS/Windows/Linux.
    Prefers ~/Downloads; falls back to OneDrive/Downloads on Windows if present.
    """
    home = Path.home()

    # Primary guess
    downloads = home / "Downloads"
    if downloads.exists():
        return downloads

    # Windows OneDrive fallback
    one_drive = home / "OneDrive" / "Downloads"
    if one_drive.exists():
        return one_drive

    # As a last resort, create ~/Downloads
    downloads.mkdir(parents=True, exist_ok=True)
    return downloads

def ensure_yt_dlp() -> None:
    """
    Ensure yt-dlp is importable; if not, try to install.
    """
    try:
        import yt_dlp  # noqa: F401
    except Exception:
        print("[insta] yt-dlp not found. Installing via pip...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], check=True)
        # Validate import after install
        import yt_dlp  # noqa: F401
        print("[insta] yt-dlp installed.")

def ensure_ffmpeg() -> None:
    """
    Ensure ffmpeg is available on PATH.
    """
    if shutil.which("ffmpeg") is None:
        # Give explicit hints per OS
        print("\n[insta] ERROR: ffmpeg not found on PATH.")
        if os.name == "nt":
            print("        Windows tips:")
            print("        • Install ffmpeg (e.g., https://www.gyan.dev/ffmpeg/builds/ )")
            print("        • Or use winget: winget install Gyan.FFmpeg")
            print("        • After install, restart terminal and try again.")
        else:
            print("        macOS tips:")
            print("        • brew install ffmpeg   (Homebrew)")
            print("        Linux tips:")
            print("        • sudo apt-get install ffmpeg   (Debian/Ubuntu)")
        sys.exit(1)

def locate_cookies_file(search_from: Path) -> Optional[Path]:
    """
    Look for a cookies.txt file to help with private/login-gated Instagram.
    Search order:
      1) same directory as this script
      2) repository root two levels up (…/youtube2audwithstems/)
    """
    here = Path(__file__).resolve().parent
    candidate1 = here / "cookies.txt"
    if candidate1.exists():
        return candidate1

    # repo root guess: .../youtube2audwithstems/link2aws/methods/instagram/
    # go up three parents to reach .../youtube2audwithstems/
    repo_root = here.parent.parent.parent
    candidate2 = repo_root / "cookies.txt"
    if candidate2.exists():
        return candidate2

    # Also check the caller-provided path
    candidate3 = search_from / "cookies.txt"
    if candidate3.exists():
        return candidate3

    return None

def sanitize_ig_url(url: str) -> str:
    """
    Normalize common Instagram Reel/short patterns.
    """
    url = url.strip().strip('"').strip("'")
    # Accept reels, p/, tv/, short links, etc. yt-dlp handles most.
    return url

# ---------------------------
# Core logic
# ---------------------------

def _progress_hook(d: Dict[str, Any]) -> None:
    if d.get('status') == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
        downloaded = d.get('downloaded_bytes', 0)
        if total:
            pct = (downloaded / total) * 100
            print(f"[insta] Downloading… {pct:5.1f}%  ({downloaded}/{total} bytes)", end='\r')
    elif d.get('status') == 'finished':
        print("\n[insta] Download complete. Post-processing…")

def download_instagram_to_audio(url: str, downloads_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Download Instagram video and extract WAV audio.
    Returns (video_path, audio_path). Any missing item will be None.
    """
    ensure_yt_dlp()
    ensure_ffmpeg()

    # Late import to allow auto-install to happen first
    import yt_dlp

    url = sanitize_ig_url(url)
    downloads_dir.mkdir(parents=True, exist_ok=True)

    cookies = locate_cookies_file(downloads_dir)
    if cookies:
        print(f"[insta] Using cookies file: {cookies}")

    # Output template: Keep title and ID for uniqueness; limit title length to 200 chars.
    outtmpl = str(downloads_dir / "%(title).200s [%(id)s].%(ext)s")

    ydl_opts: Dict[str, Any] = {
        "outtmpl": outtmpl,
        "quiet": False,
        "noplaylist": True,
        "nocheckcertificate": True,
        "merge_output_format": "mp4",
        "format": "mp4+bestaudio/best/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",  # best
            }
        ],
        # Keep original video after extracting audio (default is to delete it)
        "keepvideo": True,
        "progress_hooks": [_progress_hook],
    }

    if cookies:
        ydl_opts["cookiefile"] = str(cookies)

    print(f"[insta] Saving to: {downloads_dir}")

    video_path: Optional[Path] = None
    audio_path: Optional[Path] = None

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Resolve final filenames based on given info dict
            # The video container will be mp4 (merge_output_format)
            title = info.get("title") or "instagram_video"
            vid = info.get("id") or "unknown"
            video_filename = downloads_dir / f"{title} [{vid}].mp4"
            audio_filename = downloads_dir / f"{title} [{vid}].wav"

            # Sometimes Instagram returns a different extension; fallbacks:
            if not video_filename.exists():
                # Probe for any video with same stem
                stem = f"{title} [{vid}]"
                # Common alt containers: .mkv, .mov
                for ext in (".mp4", ".mkv", ".mov", ".webm"):
                    candidate = downloads_dir / f"{stem}{ext}"
                    if candidate.exists():
                        video_filename = candidate
                        break

            if video_filename.exists():
                video_path = video_filename

            if audio_filename.exists():
                audio_path = audio_filename
            else:
                # As a fallback, try to extract audio now if postprocessor failed
                # (rare, but can happen if metadata was odd)
                if video_path and video_path.exists():
                    print("[insta] Forcing audio extraction fallback…")
                    audio_path = force_extract_audio_with_ffmpeg(video_path, downloads_dir)

    except yt_dlp.utils.DownloadError as e:
        print(f"[insta] DownloadError: {e}")
    except Exception as e:
        print(f"[insta] Unexpected error: {e}")

    return video_path, audio_path

def force_extract_audio_with_ffmpeg(video_path: Path, downloads_dir: Path) -> Optional[Path]:
    """
    Fallback audio extraction using ffmpeg directly.
    """
    wav_out = downloads_dir / (video_path.stem + ".wav")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        "-ac", "2",
        str(wav_out),
    ]
    print("[insta] Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
        if wav_out.exists():
            print(f"[insta] Fallback audio saved: {wav_out}")
            return wav_out
    except subprocess.CalledProcessError as e:
        print(f"[insta] ffmpeg failed: {e}")
    return None

# ---------------------------
# CLI Entrypoint
# ---------------------------

def main(argv: list[str]) -> int:
    _print_header()

    # Determine Downloads folder
    downloads = find_downloads_folder()

    # Get URL
    if len(argv) >= 2:
        ig_url = argv[1]
    else:
        print("Paste the Instagram link below (e.g., https://www.instagram.com/reel/XXXXXXXXX/)")
        ig_url = input("=INSTAGRAM_LINK= > ").strip()

    if not ig_url:
        print("[insta] No URL provided. Exiting.")
        return 2

    print("[insta] Starting download & audio extraction…")
    video_path, audio_path = download_instagram_to_audio(ig_url, downloads)

    print("\n[insta] ---- RESULT ----")
    if video_path:
        print(f"[insta] Video : {video_path}")
    else:
        print("[insta] Video : (not created)")

    if audio_path:
        print(f"[insta] Audio : {audio_path}")
    else:
        print("[insta] Audio : (not created)")

    if audio_path:
        print("\n[insta] Success. Files saved to your Downloads folder.")
        return 0
    else:
        print("\n[insta] Completed with issues. See messages above.")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
