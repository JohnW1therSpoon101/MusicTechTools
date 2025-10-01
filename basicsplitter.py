#!/usr/bin/env python3
import os, sys, shutil, subprocess

def log(msg: str):
    print(f"[basicsplitter] {msg}", flush=True)

def run(cmd):
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, check=True)

def split_stems_basic(audio_path: str, out_folder: str) -> bool:
    """
    Minimal Demucs wrapper:
      - Runs demucs CLI with default model
      - Moves resulting stems up into <out_folder>\stems
    Returns True on success, False otherwise.
    """
    if not os.path.isfile(audio_path):
        log(f"audio not found: {audio_path}")
        return False

    # where demucs should write its nested output
    demucs_out = os.path.join(out_folder, "_demucs_out")
    os.makedirs(demucs_out, exist_ok=True)

    # run demucs (uses env venv demucs.exe on Windows)
    try:
        run(["demucs", "--out", demucs_out, audio_path])
    except subprocess.CalledProcessError as e:
        log(f"demucs failed: {e}")
        return False

    base = os.path.splitext(os.path.basename(audio_path))[0]
    # Expected: <demucs_out>\<model>\<base>\*.wav
    candidate_dirs = []
    for model_name in os.listdir(demucs_out):
        p = os.path.join(demucs_out, model_name, base)
        if os.path.isdir(p):
            candidate_dirs.append(p)

    if not candidate_dirs:
        log("couldn't find demucs output directory")
        return False

    stems_src = max(candidate_dirs, key=lambda d: len(os.listdir(d)) if os.path.isdir(d) else 0)
    stems_dst = os.path.join(out_folder, "stems")
    os.makedirs(stems_dst, exist_ok=True)

    moved_any = False
    for name in os.listdir(stems_src):
        if name.lower().endswith(".wav"):
            src = os.path.join(stems_src, name)
            dst = os.path.join(stems_dst, name)
            try:
                shutil.move(src, dst)
                moved_any = True
            except Exception as e:
                log(f"move failed for {name}: {e}")

    if not moved_any:
        log("no .wav stems found to move")
        return False

    # optional: keep demucs_out for debugging; otherwise uncomment to clean
    # shutil.rmtree(demucs_out, ignore_errors=True)

    log(f"done. stems at: {stems_dst}")
    return True

def main():
    if len(sys.argv) < 3:
        print("usage: basicsplitter.py <audio_path> <out_folder>", flush=True)
        sys.exit(2)
    audio_path = sys.argv[1]
    out_folder = sys.argv[2]
    ok = split_stems_basic(audio_path, out_folder)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
