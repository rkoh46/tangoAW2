"""python3 fx/blink.py FRAMEDIR [min_pixels]: frames where pixels change for exactly one frame and revert (A!=B by >80, A==C within 10): real blinks, not slow movers."""
import sys, glob, numpy as np
from PIL import Image
fs = sorted(glob.glob(sys.argv[1] + "/*.bmp")); lo = int(sys.argv[2]) if len(sys.argv) > 2 else 12
p = a = None; out = []
for i, f in enumerate(fs):
    c = np.asarray(Image.open(f).convert("RGB"), dtype=np.int16)
    if p is not None:
        m = (np.abs(a - p).sum(2) > 80) & (np.abs(a - c).sum(2) > 80) & (np.abs(c - p).sum(2) <= 10)
        n = int(m.sum())
        if n >= lo:
            ys, xs = np.nonzero(m); out.append((i - 1, n, int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))
    p, a = a, c
print(len(out), out[:int(sys.argv[3]) if len(sys.argv) > 3 else 40])
