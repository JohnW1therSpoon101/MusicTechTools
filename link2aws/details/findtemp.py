#!/usr/bin/env python3
"""
findtemp.py — Robust tempo (BPM) detector with:
- HPSS percussive emphasis
- Tempogram (autocorrelation) scoring
- Preferred-range prior (e.g., 70–100 BPM)
- Half/double-time normalization toward preferred range
- librosa 0.9/0.10 compatibility (no breaking changes)

Usage examples:
  python findtemp.py "song.wav"
  python findtemp.py "song.wav" --prefer-min 70 --prefer-max 100
  python findtemp.py "song.wav" --start 30 --duration 45
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import librosa
import warnings

# Optional default for quick testing; safe to remove
TEST_FILE = "/Users/jaydenstern/Downloads/Michael Jackson - Butterflies with Lyrics/Michael Jackson - Butterflies with Lyrics.wav"

# ---------- Helpers ----------

def _tempo_candidates_old_api(onset_env, sr: int, hop_length: int) -> np.ndarray:
    """librosa < 0.10 fallback: returns strongest-first tempo candidates."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)
        temps = librosa.beat.tempo(onset_envelope=onset_env, sr=sr, hop_length=hop_length, aggregate=None)
    return np.atleast_1d(temps).astype(float)

def _tempo_candidates_new_api(onset_env, sr: int, hop_length: int) -> Optional[np.ndarray]:
    """librosa >= 0.10 API if available; else None."""
    rhythm = getattr(librosa.feature, "rhythm", None)
    if rhythm is None or not hasattr(rhythm, "tempo"):
        return None
    temps = rhythm.tempo(onset_envelope=onset_env, sr=sr, hop_length=hop_length, aggregate=None)
    return np.atleast_1d(temps).astype(float)

def onset_env_percussive(y: np.ndarray, sr: int, hop_length: int) -> np.ndarray:
    """HPSS to emphasize percussive energy; then onset envelope."""
    y_h, y_p = librosa.effects.hpss(y)
    return librosa.onset.onset_strength(y=y_p, sr=sr, hop_length=hop_length)

def tempogram_strengths(onset_env: np.ndarray, sr: int, hop_length: int,
                        bpm_min: float = 30.0, bpm_max: float = 240.0) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute global tempogram (autocorrelation) strengths across BPM.
    Returns (bpms, strengths), both 1-D arrays filtered to [bpm_min, bpm_max].
    """
    tg = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr, hop_length=hop_length)
    strength = np.mean(tg, axis=1)  # lags
    lags = np.arange(len(strength))
    valid = lags > 0
    lags = lags[valid]
    strength = strength[valid]
    bpms = 60.0 * sr / (hop_length * lags)
    mask = (bpms >= bpm_min) & (bpms <= bpm_max)
    return bpms[mask], strength[mask]

def apply_gaussian_prior(bpms: np.ndarray, strengths: np.ndarray,
                         prefer_min: Optional[float], prefer_max: Optional[float]) -> np.ndarray:
    """Weight strengths by a smooth prior centered in the preferred range."""
    if prefer_min is None or prefer_max is None or prefer_max <= prefer_min:
        return strengths
    center = 0.5 * (prefer_min + prefer_max)
    sigma = max((prefer_max - prefer_min) / 2.0, 1.0)
    prior = np.exp(-0.5 * ((bpms - center) / sigma) ** 2)
    return strengths * prior

def half_double_normalize(bpm: float, prefer_min: Optional[float], prefer_max: Optional[float]) -> float:
    """Pull BPM toward preferred window via half/double steps if it gets closer."""
    if prefer_min is None or prefer_max is None:
        return bpm
    candidates = {bpm}
    for _ in range(3):
        candidates |= {c / 2 for c in list(candidates)}
        candidates |= {c * 2 for c in list(candidates)}
    in_range = [c for c in candidates if prefer_min <= c <= prefer_max]
    if in_range:
        center = 0.5 * (prefer_min + prefer_max)
        return min(in_range, key=lambda c: abs(c - center))
    return bpm

# ---------- Core ----------

def detect_tempo(
    path: str,
    topn: int = 5,
    sr: Optional[int] = None,
    hop_length: int = 512,
    aggregate: str = "median",
    start: Optional[float] = None,
    duration: Optional[float] = None,
    mono: bool = True,
    trim_silence: bool = True,
    prefer_min: Optional[float] = None,
    prefer_max: Optional[float] = None,
    normalize_half_double: bool = True,
) -> dict:
    y, sr_loaded = librosa.load(path, sr=sr, mono=mono, offset=start or 0.0, duration=duration)
    if trim_silence:
        y, _ = librosa.effects.trim(y, top_db=30)

    onset_env = onset_env_percussive(y, sr_loaded, hop_length)

    temps = _tempo_candidates_new_api(onset_env, sr_loaded, hop_length)
    if temps is None:
        temps = _tempo_candidates_old_api(onset_env, sr_loaded, hop_length)
    candidates = np.atleast_1d(temps).astype(float)[: max(1, topn)].tolist()

    bpms, strengths = tempogram_strengths(onset_env, sr_loaded, hop_length)
    weighted = apply_gaussian_prior(bpms, strengths, prefer_min, prefer_max)
    pick_bpm = float(bpms[np.argmax(weighted)]) if len(bpms) else float(candidates[0])

    if normalize_half_double:
        pick_bpm = half_double_normalize(pick_bpm, prefer_min, prefer_max)

    if aggregate == "median":
        agg_value = float(np.median(candidates))
    elif aggregate == "mean":
        agg_value = float(np.mean(candidates))
    else:
        agg_value = None

    return {
        "picked_bpm": pick_bpm,
        "candidates": candidates,
        "aggregate": agg_value,
        "sr": sr_loaded,
        "hop_length": hop_length,
        "frame_rate_hz": sr_loaded / hop_length,
        "prefer_min": prefer_min,
        "prefer_max": prefer_max,
    }

# ---------- CLI ----------

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Robust tempo (BPM) detector with preferred-range prior and half/double normalization")
    p.add_argument("audio", nargs="?", default=TEST_FILE, help="Path to audio file")
    p.add_argument("--topn", type=int, default=5, help="Show top-N raw tempo candidates (strongest-first)")
    p.add_argument("--sr", type=int, default=None, help="Resample rate (None=native)")
    p.add_argument("--hop-length", type=int, default=512, help="Hop length")
    p.add_argument("--aggregate", choices=["median", "mean", "none"], default="median")
    p.add_argument("--start", type=float, default=None, help="Start time (s)")
    p.add_argument("--duration", type=float, default=None, help="Duration (s)")
    p.add_argument("--mono", action="store_true", help="Force mono downmix (default True)")
    p.add_argument("--stereo", dest="mono", action="store_false", help="Keep stereo")
    p.set_defaults(mono=True)
    p.add_argument("--prefer-min", type=float, default=None, help="Preferred BPM lower bound")
    p.add_argument("--prefer-max", type=float, default=None, help="Preferred BPM upper bound")
    p.add_argument("--no-normalize", dest="normalize", action="store_false",
                   help="Disable half/double-time normalization toward preferred range")
    p.set_defaults(normalize=True)
    return p.parse_args(argv)

def main(argv: List[str]) -> int:
    args = parse_args(argv)
    audio_path = Path(args.audio).expanduser()
    if not audio_path.exists():
        print(f"[error] File not found: {audio_path}", file=sys.stderr)
        return 2

    try:
        result = detect_tempo(
            path=str(audio_path),
            topn=args.topn,
            sr=args.sr,
            hop_length=args.hop_length,
            aggregate=args.aggregate,
            start=args.start,
            duration=args.duration,
            mono=args.mono,
            trim_silence=True,
            prefer_min=args.prefer_min,
            prefer_max=args.prefer_max,
            normalize_half_double=args.normalize,
        )
    except Exception as e:
        print(f"[error] Failed to analyze tempo: {e}", file=sys.stderr)
        return 1

    cands = ", ".join(f"{bpm:.2f}" for bpm in result["candidates"])
    print(f"File     : {audio_path}")
    print(f"SR/HL    : {result['sr']} / {result['hop_length']}  (frame_rate ≈ {result['frame_rate_hz']:.2f} Hz)")
    if result["prefer_min"] is not None and result["prefer_max"] is not None:
        print(f"Prefers  : [{result['prefer_min']:.2f} … {result['prefer_max']:.2f}] BPM (normalization={'on' if args.normalize else 'off'})")
    print(f"Candidates (BPM): [{cands}]")
    if result["aggregate"] is not None:
        print(f"Aggregate ({args.aggregate}): {result['aggregate']:.2f} BPM")
    print(f"Picked   : {result['picked_bpm']:.2f} BPM")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))