import sys, glob, numpy as np
from PIL import Image
fs = sorted(glob.glob(sys.argv[1] + "/f*.bmp")); lo = int(sys.argv[2]) if len(sys.argv) > 2 else 200
p = a = None; out = []
for i, f in enumerate(fs):
    c = np.asarray(Image.open(f).convert("RGB"), dtype=np.int16)
    if p is not None:
        m = (np.abs(a - p).sum(2) > 40) & (np.abs(a - c).sum(2) > 40) & (np.abs(c - p).sum(2) <= 40)
        if m.sum() > lo: out.append((i - 1, int(m.sum())))
    p, a = a, c
print(len(out), out[:40])
