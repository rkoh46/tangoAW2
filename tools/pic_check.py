#!/usr/bin/env python3
"""Checks what a waiting window DRAWS, not the camera registers: successive frames of one seat (the harness' AW2_DUMP with
AW2_SAMPLE=1: NAME_tTICK_sSEAT.bmp) are compared by image offset on the map area. While the picture scrolls, every
step must be at most MAX_STEP pixels on each axis and the scroll may not reverse direction within GAP ticks of the
last step (no up-and-down).

Usage: pic_check.py DUMP_DIR SEATS [MAX_STEP=32] [GAP=24] [--live]   (SEATS: 1 or 1,2,3; the waiting seats)
--live: DUMP_DIR is a driver run (s<k>_NNNN.png window screenshots and shots_s<k>.jsonl, the ticks from the sidecar): steps up to 8 cells between frames, GAP in ticks
Frames that are not a plain scroll of the previous one (banners, animations, a unit moving, other screens) have a large
residual and are skipped. With several seats, a step all of them make on the same tick is the console's own (the DAY
banner dropping, a screen change) and is not scored. Exit 1 on a violation."""
import glob, re, sys
import numpy as np
from PIL import Image

import json
args = [a for a in sys.argv[1:] if not a.startswith("--")]
live = "--live" in sys.argv
d = args[0]
seats = [int(x) for x in args[1].split(",")]
max_step = int(args[2]) if len(args) > 2 else (64 if live else 32)
gap = int(args[3]) if len(args) > 3 else 24


def load(f):
    return np.asarray(Image.open(f).convert("L"), dtype=np.int16)


def offset(a, b, span=64 if '--live' in sys.argv else 32):
    """The (dx, dy) such that b's map area shifted by it matches a's best (both axes searched together, so a diagonal
    scroll is not taken for two repeats of the map's tile pattern), the residual, and the runner-up's residual."""
    A = a[30:150:2, 28:150:2].astype(np.float32)
    res = []
    for dy in range(-span, span + 1, 2):
        for dx in range(-span, span + 1, 2):
            B = b[30 + dy:150 + dy:2, 28 + dx:150 + dx:2].astype(np.float32)
            if B.shape != A.shape:
                continue
            res.append((float(np.abs(A - B).mean()), dx, dy))
    res.sort()
    return res[0][0], res[0][1], res[0][2], res[1][0]


def load_live(f):
    """A window screenshot of the app (the game's 240x160 picture scaled up, with bars) as 240x160 grey."""
    im = Image.open(f).convert("L")
    w = im.size[0]
    sc = w // 240
    arr = np.asarray(im, dtype=np.int16)
    # (the game's rows: the picture is centred; find them by the first and last rows that are not the black bar)
    rows = np.where(arr[:, w // 2 - 8 * sc:w // 2 + 8 * sc].max(axis=1) > 16)[0]
    top = int(rows[0]) if len(rows) else 0
    top = max(0, min(top, arr.shape[0] - 160 * sc))
    return arr[top + sc // 2:top + 160 * sc:sc, sc // 2:240 * sc:sc][:160, :240]


def steps_of(seat):
    if live:
        recs = [json.loads(l) for l in open(f"{d}/shots_s{seat}.jsonl")]
        files = [(r["tick"], f"{d}/{r['file']}") for r in recs]
    else:
        files = sorted(
            ((int(re.search(r"t0*(\d+)_s", f).group(1)), f) for f in glob.glob(f"{d}/t*_s{seat}.bmp")),
        )
    out = []  # (tick, dx, dy)
    spikes = []  # (tick, dx, dy): one frame jumped away and the next is back where the one before was
    hist = []
    prev = None
    for t, f in files:
        try:
            cur = load_live(f) if live else load(f)
        except Exception:
            continue
        if prev is not None:
            pa = prev
            e0 = np.abs(cur[30:150, 8:150] - pa[30:150, 8:150]).mean()
            if e0 > 0.5:
                e, dx, dy, e2 = offset(pa, cur)
                # (a plain scroll: a small residual at the offset, much smaller than with none and than any other)
                if e < 5 and e0 > 2 * e and e2 > 1.3 * e and (abs(dx) >= 8 or abs(dy) >= 8):
                    out.append((t, dx, dy))
        hist.append((t, cur))
        if len(hist) >= 5 and hist[-1][0] - hist[-5][0] == 4:
            # (the window is made every second tick, so a jump shows as two equal frames: look two ticks either side)
            (t0, a), (t1, b), (t2, c) = hist[-5], hist[-3], hist[-1]
            if np.abs(a[30:150, 28:150] - c[30:150, 28:150]).mean() < 1.5 and np.abs(a[30:150, 28:150] - b[30:150, 28:150]).mean() > 6:
                e, dx, dy, e2 = offset(a, b)
                if e < 5 and e2 > 1.3 * e and (abs(dx) >= 8 or abs(dy) >= 8):
                    spikes.append((t1, dx, dy))
        prev = cur
    return len(files), out, spikes


per = {s: steps_of(s)[:2] for s in seats}
spk = {s: steps_of(s)[2] for s in seats}
common = set()
if len(seats) > 1:
    ticks = [set(t for t, _, _ in per[s][1]) for s in seats]
    common = set.intersection(*ticks)
bad = []
for s in seats:
    last = {0: None, 1: None}
    n = 0
    for t, dx, dy in per[s][1]:
        if t in common:
            continue
        n += 1
        for axis, v in ((0, dx), (1, dy)):
            if v == 0:
                continue
            if abs(v) > max_step:
                bad.append(f"seat {s} tick {t}: step {v} px on axis {axis} (more than {max_step})")
            sg = 1 if v > 0 else -1
            if last[axis] and last[axis][1] != sg and t - last[axis][0] <= gap:
                bad.append(f"seat {s} tick {t}: scroll reversed on axis {axis} ({last[axis][1]:+d} -> {sg:+d}) {t - last[axis][0]} ticks after the last step")
            last[axis] = (t, sg)
    print(f"pic_check seat {s}: {per[s][0]} frames, {n} scroll steps ({len([1 for t, _, _ in per[s][1] if t in common])} common to all seats, not scored)")
for s_, sp in spk.items():
    for t, dx, dy in sp:
        if t not in common:
            bad.append(f"seat {s_} tick {t}: one frame is shifted by ({dx},{dy}) px and the next is back (a jump up and down)")
for b in bad[:20]:
    print("FAIL", b)
sys.exit(1 if bad else 0)
