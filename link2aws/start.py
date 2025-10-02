#!/usr/bin/env python3
# start.py — cross-platform launcher for link2aws workflow
# Spec:
# [CHECKS] OS + dependency log (mark missing)
# [Adapt]  Cross-platform paths via pathlib
# Prompt:  "===ENTERLINK===: " then run getlink.py
# Methods: Progress log while running; parse WAV_PATH; fallback to newest WAV
# findtemp: run with the downloaded WAV
# [CHECKPOINT] loop: 1) Basic stems  2) Complex stems (splitter.py)
# Finish:   run complete.py

import sys
import os
import shutil
import subprocess
import time
import re
from pathlib import Path
from typing import Optional, List, Tuple

LAST_LOG: List[str] = []

# -------------------------
# Logging & helpers
# -------------------------
def log(msg: str):
    print(msg, flush=True)
    LAST_LOG.append(msg)
    if len(LAST_LOG) > 300:
        del LAST_LOG[:len(LAST_LOG)-300]

def run(cmd: List[str], check=True, capture_output=True, text=True, env=None) -> subprocess.CompletedProcess:
    """Run a subprocess and (optionally) capture output. Always logs the command."""
    log(f"$ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=check, capture_output=capture_output, text=text, env=env)

def which(name: str) -> Optional[str]:
    return shutil.which(name)

def which_or_blank(name: str) -> str:
    return which(name) or ""

def detect_os_name() -> str:
    if sys.platform.startswith("win"):
        return "Windows"
    elif sys.platform == "darwin":
        return "Mac"
    else:
        # Linux or other
        return sys.platform

def ensure_repo_on_syspath(root: Path):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

def import_path_of(module_name: str) -> str:
    try:
        mod = __import__(module_name)
        return getattr(mod, "__file__", "(built-in)") or "(built-in)"
    except Exception:
        return ""

def downloads_root() -> Path:
    # Cross-platform: default to user Downloads
    return Path.home() / "Downloads"

def newest_wav_in_downloads(dl_root: Path, search_window_hours: float = 24.0) -> Optional[Path]:
    """Prefer WAVs NOT inside 'stems' directory. Fallback to newest-any WAV within window."""
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

def parse_wav_path_from_text(text: str) -> Optional[str]:
    """
    Extracts a line like:
      WAV_PATH: /abs/path/to/file.wav
    from the stdout of method1.py
    """
    m = re.search(r"^\s*WAV_PATH:\s*(.+?)\s*$", text, re.MULTILINE)
    return m.group(1) if m else None

def dependency_report():
    log("[CHECKS] Detecting OS...")
    os_name = detect_os_name()
    # Display "Windows" or "Mac" per spec
    if os_name == "Windows":
        print("Windows")
    elif os_name == "Mac":
        print("Mac")
    else:
        print(os_name)

    log("[CHECKS] Locating dependencies...")
    found_missing = []

    def mark(name: str, path: str):
        if path:
            log(f"  - {name:<9}: {path}")
        else:
            log(f"  - {name:<9}: NOT FOUND")
            found_missing.append(name)

    mark("yt-dlp", which_or_blank("yt-dlp"))
    mark("ffmpeg", which_or_blank("ffmpeg"))
    mark("demucs", which_or_blank("demucs"))

    # Python libs
    librosa_path = import_path_of("librosa")
    numpy_path = import_path_of("numpy")
    try:
        import soundfile  # noqa
        sf_path = getattr(soundfile, "__file__", "soundfile.py")
    except Exception:
        sf_path = ""
    mark("librosa", librosa_path)
    mark("numpy", numpy_path)
    mark("soundfile", sf_path)

    if found_missing:
        log(f"[CHECKS] Missing dependencies detected: {', '.join(found_missing)}")
    else:
        log("[CHECKS] All listed dependencies appear present.")

# -------------------------
# Main flow
# -------------------------
def main():
    ROOT = Path(__file__).resolve().parent
    ensure_repo_on_syspath(ROOT)

    # [CHECKS] OS + dependency log
    dependency_report()

    # Paths
    dl_root = downloads_root()
    log(f"[Paths] Downloads root: {dl_root}")

    py_exe = sys.executable

    # --- Prompt and run getlink.py ---
    # Spec wants this exact display text before running:
    print("===ENTERLINK===: ", flush=True)
    getlink_py = ROOT / "getlink.py"
    if not getlink_py.is_file():
        log("[getlink] getlink.py not found. Aborting.")
        sys.exit(1)

    try:
        # getlink.py is assumed to handle input/prompt; we still pre-printed required text
        proc = run([py_exe, str(getlink_py)], check=True, capture_output=True, text=True)
        # we treat last non-empty line as the URL
        url_lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        url = url_lines[-1] if url_lines else ""
        log(f"[getlink] URL captured: {url if url else '(empty)'}")
        if not url:
            log("[getlink] No URL captured. Aborting.")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        log(f"[getlink] failed: {e}")
        sys.exit(1)

    # --- Run Methods (progress log) ---
    log("[methods] Starting YouTube download method (method1.py)...")
    method1_py = ROOT / "methods" / "youtube" / "method1.py"
    if not method1_py.is_file():
        log("[methods] method1.py not found. Aborting.")
        sys.exit(1)

    try:
        log("[methods] Invoking yt-dlp wrapper (this may take a while)...")
        # Capture output so we can parse WAV_PATH; also echo it for visibility
        proc_dl = run([py_exe, str(method1_py), url], check=True, capture_output=True, text=True)
        if proc_dl.stdout:
            print(proc_dl.stdout, end="")
        if proc_dl.stderr:
            print(proc_dl.stderr, end="", file=sys.stderr)
        log("[methods] method1.py completed successfully.")
    except subprocess.CalledProcessError as e:
        # Echo whatever we got, then abort
        if e.stdout:
            print(e.stdout, end="")
        if e.stderr:
            print(e.stderr, end="", file=sys.stderr)
        log(f"[methods] method1.py failed: {e}")
        sys.exit(1)

    # Parse WAV_PATH from method1 output (Option B), fallback to scan
    wav_path_str = parse_wav_path_from_text(proc_dl.stdout or "")
    if wav_path_str:
        wav_path = Path(wav_path_str).expanduser().resolve()
        log(f"[methods] WAV_PATH (parsed): {wav_path}")
        if not wav_path.exists():
            log("[methods] Parsed WAV_PATH does not exist. Falling back to Downloads scan.")
            wav_path = None
    else:
        log("[methods] Could not parse WAV_PATH from method1 output. Falling back to Downloads scan.")
        wav_path = None

    if wav_path is None:
        wav_path = newest_wav_in_downloads(dl_root, search_window_hours=24.0)
        if not wav_path:
            log("[methods] Could not locate a recent .wav in Downloads. Aborting.")
            sys.exit(1)
        log(f"[methods] Using WAV (fallback): {wav_path}")

    # --- findtemp.py (use the downloaded WAV as input) ---
    log("[findtemp] Running tempo/key analysis...")
    findtemp_py = ROOT / "details" / "findtemp.py"
    if findtemp_py.is_file():
        try:
            # Prefer the --path API if your findtemp.py supports it; otherwise pass the path positionally.
            # We'll try --path first; if it errors quickly, fall back to positional.
            try:
                run([py_exe, str(findtemp_py), "--path", str(wav_path)], check=True, capture_output=False)
            except subprocess.CalledProcessError:
                log("[findtemp] --path not supported? Retrying with positional arg.")
                run([py_exe, str(findtemp_py), str(wav_path)], check=True, capture_output=False)
            log("[findtemp] Completed.")
        except subprocess.CalledProcessError as e:
            log(f"[findtemp] failed (continuing to checkpoint): {e}")
    else:
        log("[findtemp] details/findtemp.py not found (skipping).")

    # --- [CHECKPOINT] strict input loop ---
    print("\n[CHECKPOINT]")
    print("Choose an option:")
    print("  1) Basic Stem Separation")
    print("  2) Complex Stem Separation (splitter.py)")

    choice = None
    while True:
        choice = input("Enter 1 or 2: ").strip()
        if choice in ("1", "2"):
            break
        print("This is not valid, try again")

    out_dir = str(wav_path.parent)
    stems_success = False

    if choice == "1":
        log("[stems] Running Basic Stem Separation...")
        try:
            # Prefer direct import; fallback to subprocess if import fails
            try:
                from methods.splits.basicsplitter import split_stems_basic
                stems_success = bool(split_stems_basic(str(wav_path), out_dir))
            except Exception as e:
                log(f"[stems] basicsplitter import failed: {e} — trying subprocess.")
                basic_py = ROOT / "methods" / "splits" / "basicsplitter.py"
                if basic_py.is_file():
                    run([py_exe, str(basic_py), str(wav_path), out_dir], check=True, capture_output=False)
                    stems_success = True
                else:
                    log("[stems] basicsplitter.py not found.")
                    stems_success = False
        except subprocess.CalledProcessError as e:
            log(f"[stems] Basic stems failed: {e}")
            stems_success = False

    else:
        log("[stems] Running Complex Stem Separation (Demucs)...")
        try:
            try:
                from methods.splits.splitter import split_stems_with_demucs
                stems_success = bool(split_stems_with_demucs(str(wav_path), out_dir))
            except Exception as e:
                log(f"[stems] splitter import failed: {e} — trying subprocess.")
                split_py = ROOT / "methods" / "splits" / "splitter.py"
                if split_py.is_file():
                    run([py_exe, str(split_py), str(wav_path), out_dir], check=True, capture_output=False)
                    stems_success = True
                else:
                    log("[stems] splitter.py not found.")
                    stems_success = False
        except subprocess.CalledProcessError as e:
            log(f"[stems] Complex stems failed: {e}")
            stems_success = False

    if stems_success:
        log("[stems] Stem separation completed.")
    else:
        log("[stems] Stem separation did not complete successfully.")

    # --- If everything runs properly, run complete.py ---
    complete_py = ROOT / "complete.py"
    if complete_py.is_file():
        try:
            log("[complete] Running complete.py...")
            run([py_exe, str(complete_py), "--root", str(wav_path.parent)], check=True, capture_output=False)
        except subprocess.CalledProcessError as e:
            log(f"[complete] failed: {e}")
    else:
        log("[complete] complete.py not found (skipping).")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n[start] Interrupted by user.")
        sys.exit(130)
    except Exception as e:
        log(f"[start] Unhandled error: {e}")
        sys.exit(1)