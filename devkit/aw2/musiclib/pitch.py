"""Pitch of a recorded or sampled segment (numpy only)."""
import numpy as np


def f0(x, rate, lo=40.0, hi=2000.0):
    """The fundamental of a short mono segment by autocorrelation: the shortest lag whose peak is within 15% of the best (so a strong second harmonic does not
    read as an octave too high, nor a subharmonic as one too low). Returns (Hz, confidence 0..1) or (0, 0) for silence."""
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    if len(x) < 2048 or np.abs(x).max() < 1e-4:
        return 0.0, 0.0
    n = len(x)
    fft = np.fft.rfft(x, n=2 * n)
    ac = np.fft.irfft(fft * np.conj(fft))[:n]
    ac = ac / ac[0]
    a, b = int(rate / hi), min(int(rate / lo), n - 1)
    seg = ac[a:b]
    best = seg.max()
    # local maxima within 15% of the best, the shortest lag first
    for i in range(1, len(seg) - 1):
        if seg[i] >= 0.85 * best and seg[i] >= seg[i - 1] and seg[i] >= seg[i + 1]:
            lag = a + i
            # parabolic refinement
            y0, y1, y2 = ac[lag - 1], ac[lag], ac[lag + 1]
            d = (y0 - 2 * y1 + y2)
            off = 0.5 * (y0 - y2) / d if d else 0.0
            return rate / (lag + off), float(best)
    return 0.0, 0.0
