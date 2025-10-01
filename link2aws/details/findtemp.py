#!/usr/bin/env python3
"""
findtemp.py
- Estimate tempo (BPM) from an audio file.
- Prints candidate BPMs and the aggregate (median).
- ASCII-only output for Windows consoles (no Unicode symbols).
- Uses librosa.feature.rhythm.tempo when available (>=0.10), else falls back to librosa.beat.tempo.
"""

import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np

try:
    import librosa
    # Prefer the new API (librosa >= 0.10)
    try:
        from librosa.feature.rhythm import tempo as tempo_fn  # type: ignore
    except Exception:
        # Fallback for older librosa
        tempo_fn = None
except Exception as e:
    print(f"[findtemp] ERROR: Could not import librosa: {e}", flush=True)
    raise

def _tempo(onset_env, sr: int, hop_length: int, aggregate=None):
    """Version-agnostic wrapper around librosa tempo."""
    if tempo_fn is not None:
        # New path (librosa.feature.rhythm.tempo)
        return tempo_fn(onset_envelope=onset_env, sr=sr, hop_length=hop_length, aggregate=aggregate)
    else:
        # Old path (librosa.beat.tempo)
        return librosa.beat.tempo(onset_envelope=onset_env, sr=sr, hop_length=hop_length, aggregate=aggregate)

def analyze_tempo(
    y: np.ndarray,
    sr: int,
    hop_length: int = 512,
    n_candidates: int = 5
) -> Tuple[List[float], float]:
    """
    Compute tempo candidates and an aggregate (median) BPM.
    We gather candidates by running tempo estimation across a few hop_lengths.
    """
    hop_lengths = [256, 384, 512, 768, 1024]

    candidates: List[float] = []
    for hl in hop_lengths:
        try:
            onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hl)
            cand_arr = _tempo(onset_env, sr=sr, hop_length=hl, aggregate=None)
            if cand_arr is not None and len(cand_arr) > 0:
                top = float(cand_arr[0])
                if np.isfinite(top) and top > 0:
                    candidates.append(top)
        except Exception:
            continue
        if len(candidates) >= n_candidates:
            break

    if not candidates:
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
        val = _tempo(onset_env, sr=sr, hop_length=hop_length, aggregate=np.median)
        try:
            bpm = float(val) if np.ndim(val) == 0 else float(val[0])
        except Exception:
            bpm = float(val) if isinstance(val, (int, float)) else 0.0
        if np.isfinite(bpm) and bpm > 0:
            candidates = [bpm] * n_candidates

    clean = [float(f"{c:.2f}") for c in candidates if np.isfinite(c) and c > 0]
    if not clean:
        return [], 0.0

    agg = float(np.median(clean))
    if len(clean) < n_candidates:
        clean = (clean + [agg] * n_candidates)[:n_candidates]
    else:
        clean = clean[:n_candidates]
    return clean, float(f"{agg:.2f}")

def load_audio(path: Path) -> Tuple[np.ndarray, int]:
    y, sr = librosa.load(str(path), sr=None, mono=True)
    if not np.all(np.isfinite(y)):
        y = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0)
    return y, sr

def main(argv: List[str]) -> int:
    if not argv:
        print("usage: findtemp.py <audio_path>", flush=True)
        return 2

    in_path = Path(argv[0]).expanduser().resolve()
    if not in_path.is_file():
        print(f"[findtemp] ERROR: file not found: {in_path}", flush=True)
        return 2

    try:
        y, sr = load_audio(in_path)
    except Exception as e:
        print(f"[findtemp] ERROR: failed to load audio: {e}", flush=True)
        return 1

    display_hl = 512
    frame_rate_hz = sr / float(display_hl)

    candidates, agg = analyze_tempo(y, sr, hop_length=display_hl, n_candidates=5)

    print(f"File     : {in_path}", flush=True)
    print(f"SR/HL    : {sr} / {display_hl}  (frame_rate ~= {frame_rate_hz:.2f} Hz)", flush=True)

    if candidates:
        cand_str = ", ".join(f"{c:.2f}" for c in candidates)
        print(f"Candidates (BPM): [{cand_str}]", flush=True)
        print(f"Aggregate (median): {agg:.2f} BPM", flush=True)
    else:
        print("Candidates (BPM): []", flush=True)
        print("Aggregate (median): 0.00 BPM", flush=True)

    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        raise SystemExit(130)
