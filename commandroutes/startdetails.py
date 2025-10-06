#!/usr/bin/env python3
# commandroutes/startdetails.py

import os
import sys
import re
import json
import time
import uuid
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
CANDIDATE_ROOTS = [HERE.parent, HERE, HERE.parent.parent]
LOG_SUBDIR = Path("logs") / "startgetaudiologs"
PICKER_TIMEOUT = 10 * 60
POLL_INTERVAL = 0.4

def ts() -> str: return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
def ensure_dir(p: Path): p.mkdir(parents=True, exist_ok=True)
def py_exe() -> str: return sys.executable or "python"

def append_log(p: Path, text: str, also_print: bool=False):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f: f.write(text.rstrip()+"\n")
    if also_print: print(text, flush=True)

def read_text(p: Path) -> str:
    if not p.exists(): return ""
    try: return p.read_text(encoding="utf-8", errors="ignore")
    except Exception: return ""

def run_py(script: Path, args: list[str], out_file: Path, err_file: Path) -> int:
    cmd = [py_exe(), str(script)] + args
    with open(out_file, "w", encoding="utf-8") as out, open(err_file, "w", encoding="utf-8") as err:
        proc = subprocess.run(cmd, stdout=out, stderr=err, text=True)
    return proc.returncode

def find_project_root() -> Path:
    for root in CANDIDATE_ROOTS:
        if (root / "logs").exists() or (root / "plumming").exists() or (root / "plpumming").exists():
            return root
    return HERE.parent

def resolve_picker(project_root: Path, meta_log: Path) -> Optional[Path]:
    env_picker = os.environ.get("PICKER_PATH")
    if env_picker:
        p = Path(env_picker).expanduser().resolve()
        if p.exists():
            append_log(meta_log, f"[path] Using getaudiofile1.py from env: {p}", True)
            return p
        append_log(meta_log, f"[warn] PICKER_PATH set but not found: {p}", True)

    candidates = []
    for root in [project_root, project_root.parent, project_root.parent / "MusicTechTools"]:
        for folder in ("plumming", "plpumming"):
            candidates.append((root / folder / "getaudiofile1.py").resolve())
    for c in candidates:
        if c.exists():
            append_log(meta_log, f"[path] Found getaudiofile1.py: {c}", True)
            return c
    return None

def resolve_details_dir(project_root: Path, meta_log: Path) -> Optional[Path]:
    env_dir = os.environ.get("DETAILS_DIR")
    if env_dir:
        p = Path(env_dir).expanduser().resolve()
        if p.exists():
            append_log(meta_log, f"[path] Using DETAILS_DIR from env: {p}", True)
            return p
        append_log(meta_log, f"[warn] DETAILS_DIR set but not found: {p}", True)

    candidates = []
    for base in [project_root, project_root.parent, project_root.parent / "MusicTechTools"]:
        for proj in ("youtube2audwstems", "link2audwstems", "youtube2audwithstems/link2aws"):
            if "/" in proj:
                project_dir = (base / proj).resolve()
                candidates.append((project_dir / "details").resolve())
            else:
                candidates.append((base / proj / "details").resolve())

    for c in candidates:
        if (c / "findkey.py").exists() and ((c / "findtemp.py").exists() or (c / "findtempo.py").exists()):
            append_log(meta_log, f"[path] Selected DETAILS_DIR: {c}", True)
            return c
    return None

def resolve_scripts(details_dir: Path, meta_log: Path):
    ft_env = os.environ.get("FINDTEMP_PATH")
    fk_env = os.environ.get("FINDKEY_PATH")
    findtemp = Path(ft_env).expanduser().resolve() if ft_env else None
    findkey  = Path(fk_env).expanduser().resolve() if fk_env else None
    if not (findtemp and findtemp.exists()):
        findtemp = (details_dir / "findtemp.py").resolve()
        if not findtemp.exists():
            alt = (details_dir / "findtempo.py").resolve()
            if alt.exists(): findtemp = alt
    if not (findkey and findkey.exists()):
        findkey = (details_dir / "findkey.py").resolve()
    append_log(meta_log, f"[use] findtemp(o).py = {findtemp}", True)
    append_log(meta_log, f"[use] findkey.py    = {findkey}", True)
    return findtemp if findtemp.exists() else None, findkey if findkey.exists() else None

def parse_tempo(text: str) -> str:
    m = re.search(r"tempo\s*=\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if m: return m.group(1)
    m = re.search(r"\b([0-9]+(?:\.[0-9]+)?)\s*BPM\b", text, re.IGNORECASE)
    if m: return m.group(1)
    m = re.search(r"\bBPM\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if m: return m.group(1)
    return "Unknown"

def parse_key(text: str) -> str:
    m = re.search(r"(?:key|detected\s*key)\s*[:=]\s*([A-G][#b]?\s*(?:major|minor|maj|min|ionian|aeolian)?)", text, re.IGNORECASE)
    if m: return m.group(1).strip()
    m = re.search(r"\bKey\b\s*[:=]\s*([A-G][#b]?(?:m|M|maj|minor|major)?)", text)
    if m: return m.group(1).strip()
    return "Unknown"

def parse_genre(text: str) -> str:
    m = re.search(r"(?:genre|detected\s*genre)\s*[:=]\s*([A-Za-z0-9\-\s_/&+]+)", text, re.IGNORECASE)
    if m: return m.group(1).strip()
    return "Unknown"

def main():
    project_root = find_project_root()
    session_id = f"{ts()}__{uuid.uuid4().hex[:8]}"
    session_dir = (project_root / LOG_SUBDIR / session_id).resolve()
    ensure_dir(session_dir)
    meta_log = session_dir / "session.log"

    append_log(meta_log, f"[{ts()}] startdetails session: {session_id}")
    append_log(meta_log, f"[root] project_root = {project_root}")

    picker = resolve_picker(project_root, meta_log)
    if not picker:
        append_log(meta_log, "[ERROR] Could not locate getaudiofile1.py in plumming/ or plpumming/.", True)
        print("Aborting due to missing components. See logs.", flush=True)
        sys.exit(1)

    details_dir = resolve_details_dir(project_root, meta_log)
    if not details_dir:
        append_log(meta_log, "[ERROR] Could not locate details dir with findtemp(o).py and findkey.py.", True)
        print("Aborting due to missing components. See logs.", flush=True)
        sys.exit(1)

    findtemp, findkey = resolve_scripts(details_dir, meta_log)
    if not findtemp:
        append_log(meta_log, f"[ERROR] Missing findtemp.py/findtempo.py in: {details_dir}", True)
        print("Aborting due to missing components. See logs.", flush=True)
        sys.exit(1)
    if not findkey:
        append_log(meta_log, f"[ERROR] Missing findkey.py in: {details_dir}", True)
        print("Aborting due to missing components. See logs.", flush=True)
        sys.exit(1)

    # Launch picker: on Windows, force a NEW console and run as CHILD directly.
    picker_out = session_dir / "selected.json"
    env = os.environ.copy()
    env["PICKER_OUT"] = str(picker_out)
    env["PICKER_CHILD"] = "1"  # skip self-relaunch; we'll create the console

    try:
        if sys.platform.startswith("win"):
            CREATE_NEW_CONSOLE = 0x00000010
            subprocess.Popen([py_exe(), str(picker)], env=env, creationflags=CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([py_exe(), str(picker)], env=env)
        append_log(meta_log, "Launched getaudiofile1.py (new terminal window should open).", True)
    except Exception as e:
        append_log(meta_log, f"[ERROR] Failed to launch picker: {e}", True)
        sys.exit(1)

    # Wait for selection (or manual fallback)
    selected_path: Optional[str] = None
    start = time.time()
    while time.time() - start < PICKER_TIMEOUT:
        if picker_out.exists():
            try:
                data = json.loads(picker_out.read_text(encoding="utf-8"))
                sp = data.get("selected_path")
                if sp and Path(sp).exists():
                    selected_path = str(Path(sp).resolve())
                    break
            except Exception:
                pass
        time.sleep(POLL_INTERVAL)

    if not selected_path:
        append_log(meta_log, f"[warn] Picker timed out (>{PICKER_TIMEOUT}s). Prompting for manual path…", True)
        user_in = input("Paste full file path to analyze (or press Enter to quit): ").strip().strip('"')
        if user_in and Path(user_in).exists():
            selected_path = str(Path(user_in).resolve())
            append_log(meta_log, f"[fallback] Using manual path: {selected_path}", True)
        else:
            append_log(meta_log, "No valid path provided. Exiting.", True)
            sys.exit(1)

    append_log(meta_log, f"[selected] {selected_path}", True)

    # Progress cues
    print("gettingtempo", flush=True)
    print("gettinggenre", flush=True)

    # Run findtemp(o).py
    ft_out = session_dir / "findtemp_stdout.txt"
    ft_err = session_dir / "findtemp_stderr.txt"
    rc_t = run_py(findtemp, [selected_path], ft_out, ft_err)

    # Run findkey.py
    print("gettingkey", flush=True)
    fk_out = session_dir / "findkey_stdout.txt"
    fk_err = session_dir / "findkey_stderr.txt"
    rc_k = run_py(findkey, [selected_path], fk_out, fk_err)

    # Parse results
    tempo_text = read_text(ft_out) + "\n" + read_text(ft_err)
    key_text   = read_text(fk_out) + "\n" + read_text(fk_err)
    tempo_val = parse_tempo(tempo_text)
    key_val   = parse_key(key_text)
    genre_val = parse_genre(tempo_text) or parse_genre(key_text) or "Unknown"

    # Summary JSON
    summary = {
        "selected_path": selected_path,
        "tempo": tempo_val,
        "key": key_val,
        "genre": genre_val,
        "resolved_paths": {
            "project_root": str(project_root),
            "picker": str(picker),
            "details_dir": str(details_dir),
            "findtempo_or_findtemp": str(findtemp),
            "findkey": str(findkey),
        },
        "returncodes": {"findtemp_or_findtempo": rc_t, "findkey": rc_k},
        "timestamps": {"started": session_id.split("__")[0], "completed": ts()}
    }
    (session_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Final required output
    print("You're audio has been analyzed")
    print(f"genre = {genre_val}")
    print(f"tempo = {tempo_val}")
    print(f"key = {key_val}")

    append_log(meta_log, "FINAL OUTPUT:")
    append_log(meta_log, "You're audio has been analyzed")
    append_log(meta_log, f"genre = {genre_val}")
    append_log(meta_log, f"tempo = {tempo_val}")
    append_log(meta_log, f"key = {key_val}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(130)
    except Exception as e:
        try:
            crash_dir = (find_project_root() / LOG_SUBDIR / f"fatal_{ts()}").resolve()
            ensure_dir(crash_dir)
            (crash_dir / "fatal_error.txt").write_text(repr(e), encoding="utf-8")
        except Exception:
            pass
        print(f"[FATAL] {e}", file=sys.stderr)
        sys.exit(1)
