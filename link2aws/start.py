#!/usr/bin/env python3
# start.py — cross-platform launcher for yt2aws workflow
# Pipeline:
# 1) Check deps (report only)
# 2) Get URL via getlink.py
# 3) Download via methods/youtube/method1.py
# 4) Locate the MOST RECENT NON-STEMS WAV in ~/Downloads
# 5) Run details/findtemp.py on that WAV
# 6) Checkpoint: Basic or Complex stems (import + call; fallback to subprocess)
# 7) Auto-run details/summarize.py and then complete.py

import os
import sys
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, List, Tuple

LAST_LOG: List[str] = []

def log(msg: str):
    print(msg, flush=True)
    LAST_LOG.append(msg)
    if len(LAST_LOG) > 200:
        del LAST_LOG[:len(LAST_LOG)-200]

def run(cmd: List[str], check=True, capture_output=True, text=True, env=None) -> subprocess.CompletedProcess:
    log(f"$ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=check, capture_output=capture_output, text=text, env=env)

def which(name: str) -> Optional[str]:
    return shutil.which(name)

def which_or_blank(name: str) -> str:
    return which(name) or ""

def detect_os() -> str:
    if sys.platform.startswith("win"):
        return "Windows"
    elif sys.platform == "darwin":
        return "Mac"
    else:
        return sys.platform

def downloads_root() -> Path:
    return Path.home() / "Downloads"

def newest_wav_in_downloads(dl_root: Path, search_window_hours: float = 12.0) -> Optional[Path]:
    """
    Prefer WAVs NOT inside a directory named 'stems'. Fall back to newest-any WAV.
    """
    cutoff = time.time() - search_window_hours * 3600
    best_nonstem: Tuple[float, Optional[Path]] = (0.0, None)
    best_any: Tuple[float, Optional[Path]] = (0.0, None)
    for p in dl_root.rglob("*.wav"):
        try:
            mtime = p.stat().st_mtime
        except Exception:
            continue
        if mtime < cutoff:
            continue
        if mtime > best_any[0]:
            best_any = (mtime, p)
        parts_lower = {x.lower() for x in p.parts}
        if "stems" not in parts_lower and mtime > best_nonstem[0]:
            best_nonstem = (mtime, p)
    return best_nonstem[1] or best_any[1]

def ensure_repo_on_syspath(root: Path):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

def import_path_of(module_name: str) -> str:
    try:
        mod = __import__(module_name)
        return getattr(mod, "__file__", "(built-in)") or "(built-in)"
    except Exception:
        return ""

def main():
    ROOT = Path(__file__).resolve().parent
    ensure_repo_on_syspath(ROOT)

    # ---- 1) OS + deps report
    log(f"[OS] {detect_os()}")
    log("[Dependency Report]")
    log(f"  - yt-dlp   : {which_or_blank('yt-dlp')}")
    log(f"  - ffmpeg   : {which_or_blank('ffmpeg')}")
    log(f"  - demucs   : {which_or_blank('demucs')}")
    log(f"  - librosa : {import_path_of('librosa')}")
    log(f"  - numpy   : {import_path_of('numpy')}")
    try:
        import soundfile  # noqa
        sf_path = getattr(soundfile, '__file__', 'soundfile.py')
    except Exception:
        sf_path = ""
    log(f"  - soundfile: {sf_path}")

    dl_root = downloads_root()
    log(f"[Paths] Downloads root: {dl_root}")

    # ---- 2) Get URL
    py_exe = sys.executable
    getlink_py = ROOT / "getlink.py"
    if not getlink_py.is_file():
        log("[getlink] getlink.py not found. Aborting.")
        sys.exit(1)
    try:
        proc = run([py_exe, str(getlink_py)], check=True, capture_output=True, text=True)
        url_lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        url = url_lines[-1] if url_lines else ""
        print(url)  # to mirror your current stdout style
        log(f"[getlink] URL: {url}")
        if not url:
            log("[getlink] No URL captured. Aborting.")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        log(f"[getlink] failed: {e}")
        sys.exit(1)

    # ---- 3) Download via method1.py
    method1_py = ROOT / "methods" / "youtube" / "method1.py"
    if not method1_py.is_file():
        log("[methods] method1.py not found. Aborting.")
        sys.exit(1)
    try:
        run([py_exe, str(method1_py), url], check=True, capture_output=False, text=True)
        log("[methods] method1.py succeeded.")
    except subprocess.CalledProcessError as e:
        log(f"[methods] method1.py failed: {e}")
        sys.exit(1)

    # ---- 4) Locate the intended WAV (avoid stems/)
    wav_path = newest_wav_in_downloads(dl_root, search_window_hours=24.0)
    if not wav_path:
        log("[findtemp] Could not find a recent .wav in Downloads. Aborting.")
        sys.exit(1)
    log(f"[findtemp] Using WAV: {wav_path}")

    # ---- 5) Run findtemp.py on the full mix (not stem)
    findtemp_py = ROOT / "details" / "findtemp.py"
    if findtemp_py.is_file():
        try:
            run([py_exe, str(findtemp_py), str(wav_path)], check=False)
        except Exception as e:
            log(f"[findtemp] error (continuing): {e}")
    else:
        log("[findtemp] details/findtemp.py not found (continuing).")

    # ---- 6) Checkpoint: split
    print("\n[CHECKPOINT]\nChoose an option:\n  1) Basic Stem Separation\n  2) Complex Stem Separation (splitter.py)")
    choice = input("Enter 1 or 2: ").strip()

    out_dir = str(wav_path.parent)
    success = False

    if choice == "1":
        try:
            from methods.splits.basicsplitter import split_stems_basic
            success = bool(split_stems_basic(str(wav_path), out_dir))
            if success:
                log("[start] Basic stems completed.")
            else:
                log("[start] Basic stems reported failure.")
        except Exception as e:
            log(f"[stems] import/call of basicsplitter failed: {e}")
            basic_py = ROOT / "methods" / "splits" / "basicsplitter.py"
            if basic_py.is_file():
                try:
                    run([py_exe, str(basic_py), str(wav_path), out_dir], check=True, capture_output=False)
                    log("[start] Basic stems (subprocess) completed.")
                    success = True
                except subprocess.CalledProcessError as e2:
                    log(f"[start] Basic stems (subprocess) failed: {e2}")
            else:
                log("[stems] basicsplitter.py not found.")

    elif choice == "2":
        try:
            from methods.splits.splitter import split_stems_with_demucs
            success = bool(split_stems_with_demucs(str(wav_path), out_dir))
            if success:
                log("[start] Complex stems completed.")
            else:
                log("[start] Complex stems reported failure.")
        except Exception as e:
            log(f"[stems] import/call of splitter failed: {e}")
            split_py = ROOT / "methods" / "splits" / "splitter.py"
            if split_py.is_file():
                try:
                    run([py_exe, str(split_py), str(wav_path), out_dir], check=True, capture_output=False)
                    log("[start] Complex stems (subprocess) completed.")
                    success = True
                except subprocess.CalledProcessError as e2:
                    log(f"[start] Complex stems (subprocess) failed: {e2}")
            else:
                log("[stems] splitter.py not found.")
    else:
        log("[start] No valid selection. Skipping stems.")

    # ---- 7) Auto-run summarize.py and complete.py (only after stems success or if skipped)
    summarize_py = ROOT / "details" / "summarize.py"
    if summarize_py.is_file():
        try:
            run([py_exe, str(summarize_py), "--wav", str(wav_path)], check=False, capture_output=False)
        except Exception as e:
            log(f"[start] summarize.py failed (continuing): {e}")

    complete_py = ROOT / "complete.py"
    if complete_py.is_file():
        try:
            run([py_exe, str(complete_py), "--root", str(wav_path.parent)], check=False, capture_output=False)
        except Exception as e:
            log(f"[start] complete.py failed (continuing): {e}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n[start] Interrupted by user.")
        sys.exit(130)
    except Exception as e:
        log(f"[start] Unhandled error: {e}")
        sys.exit(1)
