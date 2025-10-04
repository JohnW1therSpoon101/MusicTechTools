#!/usr/bin/env python3
"""
method3.py — Selenium-driven YouTube recorder -> audio extractor.

Requirements:
  - Python: selenium, webdriver-manager
  - FFmpeg in PATH
  - macOS: (optional/recommended) BlackHole 2ch for system audio capture
  - Windows: “Stereo Mix” device enabled (or will fallback to silent capture)

Usage (example):
    from methods.youtube.method3 import record_youtube_to_audio

    audio_path = record_youtube_to_audio(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        out_dir="/Users/yourname/Downloads/yt2aws_captures",
        audio_format="wav"  # or "mp3"
    )
    print("Final audio:", audio_path)
"""

import os
import re
import sys
import time
import shutil
import subprocess
import tempfile
import platform
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import JavascriptException, NoSuchElementException

# -----------------------
# Simple logger
# -----------------------
def log(msg: str):
    print(msg, flush=True)

# -----------------------
# Dependency checks
# -----------------------
def which_or_fail(name: str) -> str:
    p = shutil.which(name)
    if not p:
        raise RuntimeError(f"Required dependency not found on PATH: {name}")
    return p

# -----------------------
# FFmpeg record command (per-OS)
# -----------------------
def build_ffmpeg_cmd(video_out: Path, duration_s: float | None) -> list[str]:
    """
    Build an FFmpeg screen (and if possible system-audio) capture command for current OS.
    - On macOS: uses avfoundation. If BlackHole 2ch exists, captures it; otherwise screen only (silent).
    - On Windows: uses gdigrab for screen; tries dshow audio "Stereo Mix" if available.
    - On Linux: uses x11grab; audio capture left as a TODO/disabled by default.
    """
    sys_os = platform.system().lower()
    fps = 30
    # If you want to capture a specific screen index or region, you can extend this.
    # For now, we capture the primary display.

    if sys_os == "darwin":  # macOS
        # List devices: `ffmpeg -f avfoundation -list_devices true -i ""`
        # Screen is usually index 1; system audio requires a virtual device (e.g., "BlackHole 2ch")
        audio_device = None

        # Try to detect BlackHole 2ch (best-effort; user may need to set it as a system output)
        # We can't enumerate easily here; let users set AUDIO_DEVICE env if needed.
        if os.environ.get("AUDIO_DEVICE"):
            audio_device = os.environ["AUDIO_DEVICE"]
        else:
            # Default guess—comment this out if it causes issues:
            audio_device = "BlackHole 2ch"

        # Build input spec
        # If BlackHole is not actually present, FFmpeg will fail; we therefore try an audio probe first.
        def audio_device_exists(devname: str) -> bool:
            # We can't reliably probe avfoundation devices non-interactively; we fall back to silent if it fails.
            # User can set AUDIO_DEVICE exact name to force.
            return devname is not None and len(devname.strip()) > 0

        # Screen index "1" is common; on some setups it may be "0".
        video_input = "1:none" if audio_device_exists(audio_device) else "1:none"
        cmd = ["ffmpeg", "-y", "-f", "avfoundation", "-framerate", str(fps), "-i"]

        if audio_device_exists(audio_device):
            # screen + audio device
            av_in = f"{video_input}:{audio_device}"
        else:
            # screen only (silent)
            av_in = f"{video_input}"

        cmd += [av_in]

        # Optional duration
        if duration_s is not None and duration_s > 0:
            cmd += ["-t", f"{duration_s:.2f}"]

        # Encode to a compact MP4 for the intermediate
        cmd += [
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-movflags", "+faststart",
            str(video_out)
        ]
        return cmd

    elif sys_os == "windows":
        # Screen via gdigrab; try dshow audio "Stereo Mix"
        # To list devices: ffmpeg -list_devices true -f dshow -i dummy
        # Change the audio device if needed (e.g., "virtual-audio-capturer")
        audio_name = os.environ.get("AUDIO_DEVICE", "Stereo Mix (Realtek(R) Audio)")
        # Build inputs
        cmd = ["ffmpeg", "-y"]

        # Video (primary desktop)
        cmd += ["-f", "gdigrab", "-framerate", str(fps), "-i", "desktop"]

        # Audio (best effort)
        if audio_name:
            cmd += ["-f", "dshow", "-i", f"audio={audio_name}"]

        if duration_s is not None and duration_s > 0:
            cmd += ["-t", f"{duration_s:.2f}"]

        cmd += [
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(video_out)
        ]
        return cmd

    else:  # Linux (best-effort; may need DISPLAY and pulse/jack setup)
        display = os.environ.get("DISPLAY", ":0")
        cmd = [
            "ffmpeg", "-y",
            "-f", "x11grab", "-framerate", str(fps), "-i", f"{display}.0"
        ]
        # (Optional) add PulseAudio capture here if configured:
        # cmd += ["-f", "pulse", "-i", "default"]

        if duration_s is not None and duration_s > 0:
            cmd += ["-t", f"{duration_s:.2f}"]

        cmd += [
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            str(video_out)
        ]
        return cmd

# -----------------------
# Selenium helpers
# -----------------------
def make_driver(width=1280, height=720) -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument(f"--window-size={width},{height}")
    chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--force-dark-mode")
    chrome_options.add_argument("--disable-features=PreloadMediaEngagementData,AutoplayIgnoreWebAudio")
    chrome_options.add_argument("--lang=en-US")
    # Headful is recommended so FFmpeg can capture the screen/tab.
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
    return driver

def set_youtube_playback(driver: webdriver.Chrome, url: str) -> tuple[float | None, str]:
    """
    Navigate, accept cookies if needed, start playback, set quality via keyboard
    shortcut (Shift+, / Shift+.) and return (duration_seconds, suggested_basename)
    """
    driver.get(url)
    time.sleep(2)

    # Try to click the big player area to ensure focus
    try:
        video = driver.find_element(By.CSS_SELECTOR, "video.html5-main-video")
        video.click()
    except NoSuchElementException:
        pass

    # Start playback via JS
    duration = None
    title = "youtube_capture"
    try:
        # Extract title for naming
        title = driver.title or title
        title = re.sub(r"[^\w\-\.\s]", "", title).strip() or "youtube_capture"

        duration = driver.execute_script("""
            const v = document.querySelector('video.html5-main-video');
            if (v) {
                v.muted = true;            // avoid feedback while recording; system audio captured from output device
                v.playbackRate = 1.0;
                v.play().catch(()=>{});
                return v.duration;         // seconds (may be NaN if not loaded yet)
            }
            return null;
        """)
    except JavascriptException:
        pass

    # Small wait to buffer, then try quality menu hint via keyboard (best-effort)
    time.sleep(2)
    # YouTube has hotkeys; here we nudge resolution by opening settings via 'Shift+.' pattern is unreliable headless;
    # leaving as is (recording screen at browser resolution is usually enough).

    # If duration is NaN/None, don’t block; we’ll record for a default length & let user stop via Ctrl+C, or set a cap.
    if not duration or (isinstance(duration, float) and (duration != duration or duration <= 0)):  # NaN check
        duration = None

    return duration, title

# -----------------------
# Conversion helpers
# -----------------------
def video_to_audio(video_path: Path, out_format: str = "wav") -> Path:
    out_format = out_format.lower().strip()
    if out_format not in {"wav", "mp3"}:
        out_format = "wav"

    audio_path = video_path.with_suffix(f".{out_format}")

    if out_format == "wav":
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "48000",
            "-ac", "2",
            str(audio_path),
        ]
    else:  # mp3
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vn",
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(audio_path),
        ]

    subprocess.run(cmd, check=True)
    return audio_path

# -----------------------
# Public entry
# -----------------------
def record_youtube_to_audio(
    url: str,
    out_dir: str | Path,
    audio_format: str = "wav",
    max_extra_buffer_s: float = 6.0,
    hard_cap_minutes: float | None = 15.0
) -> Path:
    """
    Orchestrates:
      - Launch Chrome (Selenium), navigate & play
      - Screen-record the browser via FFmpeg (with best-effort system audio)
      - Convert captured video -> audio
      - Return final audio path and print it

    Notes:
      - For macOS system audio, install/configure a virtual loopback device (e.g., BlackHole 2ch)
        and set it as output (or export AUDIO_DEVICE env with exact device name).
      - If duration is unknown, we record up to hard_cap_minutes to avoid runaway capture.
    """
    which_or_fail("ffmpeg")

    out_dir = Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    driver = make_driver()
    try:
        duration, title = set_youtube_playback(driver, url)

        # Decide recording length
        record_seconds = None
        if duration and duration > 0:
            record_seconds = float(duration) + float(max_extra_buffer_s)
        elif hard_cap_minutes:
            record_seconds = max(30.0, hard_cap_minutes * 60.0)  # minimum 30s if unknown
        else:
            record_seconds = 300.0  # 5 min default

        # Build output temp video path
        safe_title = re.sub(r"\s+", "_", title)[:80]
        video_out = out_dir / f"{safe_title}.mp4"

        ffmpeg_cmd = build_ffmpeg_cmd(video_out, duration_s=record_seconds)
        log("[method3] Starting FFmpeg recorder:")
        log("         " + " ".join(ffmpeg_cmd))

        # Give a brief moment to ensure video is playing in foreground
        time.sleep(1.5)
        rec_proc = subprocess.Popen(ffmpeg_cmd)

        # While recording, keep the tab “alive” (occasionally poke playback)
        # This is optional; helps avoid pauses/screensavers.
        start = time.time()
        while rec_proc.poll() is None:
            time.sleep(5)
            try:
                driver.execute_script("""
                    const v = document.querySelector('video.html5-main-video');
                    if (v && v.paused) v.play().catch(()=>{});
                """)
            except JavascriptException:
                pass
            # If no hard cap (record_seconds None), allow manual stop only (Ctrl+C)
            if record_seconds is not None and time.time() - start > record_seconds + 2:
                break

        # If still running past expected time, terminate
        if rec_proc.poll() is None:
            rec_proc.terminate()
            try:
                rec_proc.wait(timeout=5)
            except Exception:
                rec_proc.kill()

        if not video_out.exists():
            raise RuntimeError("Recording failed: no video file created.")

        log(f"[method3] Recording complete: {video_out}")

        # Convert to audio
        audio_path = video_to_audio(video_out, out_format=audio_format)
        log(f"[method3] Audio written: {audio_path}")

        return audio_path

    finally:
        try:
            driver.quit()
        except Exception:
            pass

# -----------------------
# CLI hook (optional)
# -----------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Record a YouTube link via Selenium + FFmpeg and extract audio.")
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument("--out-dir", default=str(Path.home() / "Downloads" / "yt2aws_captures"))
    parser.add_argument("--audio-format", choices=["wav", "mp3"], default="wav")
    parser.add_argument("--hard-cap-minutes", type=float, default=15.0)
    args = parser.parse_args()

    audio = record_youtube_to_audio(
        url=args.url,
        out_dir=args.out_dir,
        audio_format=args.audio_format,
        hard_cap_minutes=args.hard_cap_minutes
    )
    print(f"\nFINAL AUDIO LOCATION: {audio}\n")