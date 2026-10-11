#!/usr/bin/env python3
"""Development aid: before/after sheet of the five HQs next to Dual Strike's own
(hq_sheet.py OUT_DIR; reads the pictures hq_probe.py / hq_bh.py made in OUT_DIR)."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PIL import Image, ImageDraw
from aw2test.rom import DualStrike

out = sys.argv[1]
ds = DualStrike()
sprites, pals = ds.file("bmap/015"), ds.file("bmap/00e")
CELLS = [10, 11, 12, 13, 9]
NAMES = ["Orange Star", "Blue Moon", "Green Earth", "Yellow Comet", "Black Hole"]
PAL = [7, 8, 9, 10, 11]
Z = 4


def rgb(c):
    return ((c & 31) * 255 // 31, ((c >> 5) & 31) * 255 // 31, ((c >> 10) & 31) * 255 // 31)


def cell_picture(n):
    pal = [rgb(c) for c in struct.unpack_from("<16H", pals, 32 * PAL[n])]
    im = Image.new("RGBA", (16, 32), (0, 0, 0, 0))
    for i in range(512):
        b = sprites[256 * CELLS[n] + i // 2]
        v = b >> 4 if i & 1 else b & 15
        if v:
            im.putpixel((i % 16, i // 16), pal[v] + (255,))
    return im


def grass(im):
    bg = Image.new("RGB", im.size, (214, 235, 104))
    bg.paste(im, (0, 0), im)
    return bg


def crop(path, box):
    return Image.open(path).convert("RGB").crop(box)


W, H = 32, 44
rows = []
real = Image.open(os.path.join(out, "hq", "real_ds_editor.png")).convert("RGB")
# (the Design Room map has the HQs placed as Orange Star, Yellow Comet, Green Earth, Blue Moon)
real_row = [real.crop((cx - 20, 192 + 75, cx + 20, 192 + 123)) for cx in (77, 209, 165, 121)] + [None]
data_row = [grass(cell_picture(n)) for n in range(5)]
rows.append(("Dual Strike, real screen (melonDS, Design Room)", real_row))
rows.append(("Dual Strike's cell with its own palette (data, 1:1)", data_row))
for label, tag in (("before, flat", "before/hq_g1t0c.bmp"), ("after, flat", "after_hq_g1t0c.bmp")):
    p = os.path.join(out, "hq", tag)
    r = [crop(p, (cx - 20, 56, cx + 20, 104)) for cx in (24, 56, 88, 120)]
    bh = os.path.join(out, "hq", tag.replace("hq_g1t0c", "bh_hq_g1t0") if "before" in tag else "after_bh_hq_g1t0.bmp")
    r.append(crop(bh, (20, 92, 60, 140)))
    rows.append((label + " (Black Hole: BH Campaign mission 1, units on it)", r))
for label, tag in (("before, tilted", "before/hq_g1t1c.bmp"), ("after, tilted", "after_hq_g1t1c.bmp")):
    p = os.path.join(out, "hq", tag)
    rows.append((label, [crop(p, (cx - 20, 56, cx + 20, 104)) for cx in (35, 64, 92, 120)] + [None]))
cw, ch = 40 * Z, 48 * Z
sheet = Image.new("RGB", (5 * cw + 10, len(rows) * (ch + 22) + 22), (30, 30, 36))
d = ImageDraw.Draw(sheet)
for n, name in enumerate(NAMES):
    d.text((5 + n * cw + 8, 4), name, fill=(255, 255, 255))
for r, (label, ims) in enumerate(rows):
    y = 22 + r * (ch + 22)
    d.text((5, y), label, fill=(190, 220, 255))
    for n, im in enumerate(ims):
        if im is None:
            d.text((5 + n * cw + 8, y + 40), "no real capture", fill=(200, 120, 120))
            continue
        big = im.resize((im.width * Z, im.height * Z), Image.NEAREST)
        sheet.paste(big, (5 + n * cw, y + 14))
sheet.save(os.path.join(out, "hq", "sheet.png"))
real_only = Image.new("RGB", (4 * 40 * 6 + 10, 48 * 6 + 10), (30, 30, 36))
for n, im in enumerate(real_row[:4]):
    real_only.paste(im.resize((40 * 6, 48 * 6), Image.NEAREST), (5 + n * 40 * 6, 5))
real_only.save(os.path.join(out, "hq", "real_hqs.png"))
print(os.path.join(out, "hq", "sheet.png"))
