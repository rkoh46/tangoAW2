"""python3 fx/sheet.py OUTDIR SCENE OUT.png [N] [first,last]: flat | tilt at the N frames (spread over the busiest stretch) of an effect."""
import os, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from PIL import Image
import oam
d, scene, out = sys.argv[1], sys.argv[2], sys.argv[3]
n = int(sys.argv[4]) if len(sys.argv) > 4 else 8
fr = oam.load(f"{d}/{scene}_flat.oam")
have = {int(os.path.basename(f)[1:6]) for f in glob.glob(f"{d}/{scene}_flat/f*.bmp")} & {int(os.path.basename(f)[1:6]) for f in glob.glob(f"{d}/{scene}_tilt/f*.bmp")}
if len(sys.argv) > 5:
    a, b = map(int, sys.argv[5].split(","))
    cand = sorted(f for f in have if a <= f <= b)
else:
    eff = {f: sum(1 for s in v if s[7] in (3, 4, 5)) for f, v in fr.items() if f in have}
    cand = sorted(f for f, c in eff.items() if c >= 3)
if not cand:
    cand = sorted(have)
step = max(1, len(cand) // n)
pick = cand[::step][:n]
w, h = 480, 320
S = Image.new("RGB", (2 * w, h * len(pick)))
for k, f in enumerate(pick):
    for j, m in enumerate(("flat", "tilt")):
        S.paste(Image.open(f"{d}/{scene}_{m}/f{f:05d}.bmp").convert("RGB").resize((w, h), Image.NEAREST), (j * w, k * h))
S.save(out)
print(pick)
