#!/usr/bin/env python3
"""
YouTube audio downloader (method1)

- Given a YouTube URL, downloads and extracts audio to WAV.
- Output path pattern:
    ~/Downloads/<Video Title>/<Video Title>.wav

- Usage (CLI):
    python method1.py <url>

- Usage (import):
    from method1 import download_audio
    out_path = download_audio(url)

Behavior:
- Prints the absolute path to the resulting WAV file on success (single line).
- Returns the absolute path as a string from functions.
"""

import os
import re
import sys
import shutil
import subprocess
from typing import Optional

LAST_OUTPUT_PATH: Optional[str] = None  # populated on success


def _log(msg: str) -> None:
    print(f"[method1] {msg}")


def _find_exe(name: str) -> Optional[str]:
    return shutil.which(name)


def _downloads_dir() -> str:
    # cross-platform "Downloads" (defaults to ~/Downloads)
    home = os.path.expanduser("~")
    dl = os.path.join(home, "Downloads")
    return dl


# sanitize folder name (avoid path separators / very problematic chars)
_INVALID_CHARS = r'[<>:"/\\|?*\x00-\x1F]'
def _sanitize_folder(name: str) -> str:
    # Replace invalid characters with a space; trim extra spaces
    cleaned = re.sub(_INVALID_CHARS, " ", name).strip()
    # Collapse repeated spaces
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned if cleaned else "YouTube_Audio"


def _get_title_with_ytdlp(ytdlp: str, url: str) -> str:
    """
    Ask yt-dlp for the title only (no download).
    """
    # Newer yt-dlp uses -O; older accepts --print as well.
    cmds = [
        [ytdlp, "-O", "%(title)s", url],
        [ytdlp, "--print", "%(title)s", url],
    ]
    for cmd in cmds:
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            title = (res.stdout or "").strip()
            if title:
                return title
        except Exception:
            continue
    # fallback generic
    return "YouTube_Audio"


def _build_output_template(base_dir: str, folder_name_hint: str) -> str:
    """
    We force yt-dlp to create: <base_dir>/<sanitized folder>/<title>.<ext>
    Note: The inner filename still uses yt-dlp's own %(title)s so the file
    matches the video title. The folder name uses our sanitized version.
    """
    folder = _sanitize_folder(folder_name_hint)
    # Important: do NOT quote here; pass as a single string to subprocess list.
    # yt-dlp will create the dirs.
    return os.path.join(base_dir, folder, "%(title)s.%(ext)s")


def _run_ytdlp_to_wav(ytdlp: str, url: str, out_template: str) -> subprocess.CompletedProcess:
    cmd = [
        ytdlp,
        "-x",                       # extract audio
        "--audio-format", "wav",    # convert to wav (requires ffmpeg)
        "--audio-quality", "0",     # best quality
        "-o", out_template,         # output template
        url,
    ]
    _log("Using yt-dlp executable")
    _log(" ".join(cmd))
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


# Regex to capture absolute paths to audio files (including spaces)
_PATH_RE = re.compile(r'(/[^:\n\r\t]*?\.(?:wav|mp3|m4a|aac|flac|ogg|opus))', re.IGNORECASE)

def _extract_path_from_text(s: str) -> Optional[str]:
    if not s:
        return None
    matches = _PATH_RE.findall(s)
    for cand in reversed(matches):
        p = cand.strip().strip('"').strip("'")
        if os.path.isabs(p) and os.path.exists(p):
            return os.path.abspath(p)
    return None


def _expected_wav_path(base_dir: str, folder_name_hint: str, title_for_file: str) -> str:
    """
    Build the expected final WAV path given base_dir and title.
    This mirrors our -o "<base>/<folder>/<title>.%(ext)s"
    """
    folder = _sanitize_folder(folder_name_hint)
    return os.path.join(base_dir, folder, f"{title_for_file}.wav")


def download_audio(url: str) -> str:
    """
    Main programmatic entrypoint.
    Returns absolute path to the .wav file or raises RuntimeError.
    """
    if not url or not isinstance(url, str):
        raise RuntimeError("No URL provided to download_audio().")

    ytdlp = _find_exe("yt-dlp")
    if not ytdlp:
        raise RuntimeError("yt-dlp not found in PATH.")

    ffmpeg = _find_exe("ffmpeg")
    if not ffmpeg:
        _log("Warning: ffmpeg not found; yt-dlp may fail to convert to wav.")

    downloads = _downloads_dir()
    title = _get_title_with_ytdlp(ytdlp, url)
    out_template = _build_output_template(downloads, title)

    # Run yt-dlp
    proc = _run_ytdlp_to_wav(ytdlp, url, out_template)

    # Echo child output for debugging visibility
    if proc.stdout.strip():
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr.strip():
        sys.stderr.write(proc.stderr if proc.stderr.endswith("\n") else proc.stderr + "\n")

    # If yt-dlp succeeded, we can try to compute the expected path immediately.
    # But sometimes the displayed "title" used for the filename may differ (e.g., restricted filenames).
    # First try to detect the path from output text; then fall back to the expected path.
    detected = _extract_path_from_text(proc.stdout) or _extract_path_from_text(proc.stderr)

    if detected and os.path.exists(detected):
        final_out = os.path.abspath(detected)
        globals()["LAST_OUTPUT_PATH"] = final_out
        print(final_out)  # single-line absolute path for caller parsing
        return final_out

    # Fallback: check expected location with the "title" we asked yt-dlp for
    expected = _expected_wav_path(downloads, title, title)
    if os.path.exists(expected):
        final_out = os.path.abspath(expected)
        globals()["LAST_OUTPUT_PATH"] = final_out
        print(final_out)
        return final_out

    # If we cannot find it, try scanning the created folder for a .wav
    folder = os.path.join(downloads, _sanitize_folder(title))
    if os.path.isdir(folder):
        candidates = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".wav")]
        if candidates:
            candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            final_out = os.path.abspath(candidates[0])
            globals()["LAST_OUTPUT_PATH"] = final_out
            print(final_out)
            return final_out

    raise RuntimeError("Download/extract reported success but output .wav was not found.")


def main() -> Optional[str]:
    """
    CLI entry: python method1.py <url>
    Also supports env var YT2AUDIO_URL when no positional arg is given.
    """
    url = None
    if len(sys.argv) >= 2:
        url = sys.argv[1].strip()
    if not url:
        url = os.environ.get("YT2AUDIO_URL", "").strip()

    if not url:
        _log("Usage: method1.py <url>")
        _log("No URL passed; expecting start.py to provide it")
        return None

    try:
        return download_audio(url)
    except Exception as e:
        _log(f"ERROR: {e}")
        return None


if __name__ == "__main__":
    main()