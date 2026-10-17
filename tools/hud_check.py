#!/usr/bin/env python3
"""Fog off: a waiting window's HUD header is its own seat's colour in every frame (the turn-start slide-in included).
Frames from the harness (AW2_DUMP, AW2_SAMPLE=1).

Usage: hud_check.py DUMP_DIR SEAT NOT_COLOUR [FROM_TICK]
NOT_COLOUR (red|blue): the colour the window's header must never have (the OTHER army's). Red is found as a bar of saturated red
(R>200, G,B<110) in the top rows next to the CO's face; blue headers are told from the sea by the same bar being absent of red
and the seat's own colour being red: so check the red window with `blue`: no frame may have a blue header bar of at least
60 pixels at 115,90,255 whose rows are not full-width water (the bar is under 70 pixels wide). Exit 1 on any."""
import glob, re, sys
import numpy as np
from PIL import Image

d, seat, never = sys.argv[1], int(sys.argv[2]), sys.argv[3]
from_tick = int(sys.argv[4]) if len(sys.argv) > 4 else 0
bad = []
n = 0
for f in sorted(glob.glob(f"{d}/t*_s{seat}.bmp")):
    t = int(re.search(r"t0*(\d+)_s", f).group(1))
    if t < from_tick:
        continue
    n += 1
    a = np.asarray(Image.open(f).convert("RGB"), dtype=int)[3:11]
    if never == "red":
        # (the Rules page's map-name plate, red-framed, sits in the middle of the top rows: not the HUD)
        a = a.copy()
        a[:, 76:184] = 0
        hit = ((a[:, :, 0] > 200) & (a[:, :, 1] < 110) & (a[:, :, 2] < 110))
    else:
        hit = ((abs(a[:, :, 0] - 115) < 6) & (abs(a[:, :, 1] - 90) < 6) & (a[:, :, 2] > 240))
        # (the sea is the same blue: the header bar is a block, the sea runs on across the whole row)
        if hit.sum(axis=1).max() > 100 or hit.sum(axis=0).max() < 5:
            hit = hit & False
    if hit.sum() >= 60:
        bad.append(t)
print(f"hud_check seat {seat} (never {never}): {n} frames, {len(bad)} wrong")
if bad:
    print("FAIL ticks", bad[:12], "...")
sys.exit(1 if bad else 0)
