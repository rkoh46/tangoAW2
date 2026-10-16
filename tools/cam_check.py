#!/usr/bin/env python3
"""Checks the waiting windows' cameras in a harness log made with AW2_CAM_LOG=1 (and AW2_SAMPLE=N so views are made).

Usage: cam_check.py LOG [MAX_STEP]

- `camend seat S mine (x,y)` lines: each waiting window's camera (pixels) after each view. A view may move it by at most
  MAX_STEP (default 16: the game's scroll is four pixels a tick, eight over a long way, a view every second tick) on each axis, and the camera may not
  reverse direction on an axis while it is moving (no up-and-down): a reversal needs a view at rest in between.
- `concam tick T px (x, y)` lines: the console's own camera (what a window shows with Fog off): at most 8 pixels a tick,
  same reversal rule.
Exit 1 and the offending lines when a rule fails. Prints the number of views and moves checked."""
import re, sys


def check(series, max_step, what, bad, ticked=False):
    views = moves = 0
    for key, pts in series.items():
        last = None
        last_t = None
        dirs = [0, 0]
        for t, (x, y) in pts:
            gap = 1
            if ticked and last_t is not None:
                # (the console log has only the ticks the camera moved on: a gap is a rest)
                gap = t - last_t
                if gap > 1:
                    dirs = [0, 0]
            last_t = t
            if last is not None:
                for axis, (a, b) in enumerate(((last[0], x), (last[1], y))):
                    d = b - a
                    if abs(d) > max_step * gap:
                        bad.append(f"{what} {key} step {d} on axis {axis} at {t}: {last} -> {(x, y)}")
                    s = (d > 0) - (d < 0)
                    if s != 0:
                        if dirs[axis] != 0 and s != dirs[axis]:
                            bad.append(f"{what} {key} reversed on axis {axis} while moving at {t}: {last} -> {(x, y)}")
                        if dirs[axis] == 0:
                            moves += 1
                        dirs[axis] = s
                    else:
                        dirs[axis] = 0
                views += 1
            last = (x, y)
    return views, moves


def main():
    log = sys.argv[1]
    step = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    cams, con = {}, {"console": []}
    targets = {}
    bad = []
    n = 0
    for line in open(log, errors="ignore"):
        n += 1
        m = re.match(r"camend seat (\d+) mine \((-?\d+),(-?\d+)\)", line)
        if m:
            cams.setdefault(int(m.group(1)), []).append((n, (int(m.group(2)), int(m.group(3)))))
            continue
        m = re.match(r"cam seat (\d+) phase \w+ cam \((-?\d+),(-?\d+)\) -> \((-?\d+),(-?\d+)\) target \((\d+),(\d+)\) .* reason (\w+)", line)
        if m:
            seat, tg, why = int(m.group(1)), (int(m.group(6)), int(m.group(7))), m.group(8)
            prev = targets.get(seat)
            # the camera's target changes only when a cell of the mover's is seen (or, once, when the window sees nothing)
            if prev is not None and prev != tg and why == "none":
                bad.append(f"seat {seat} camera target changed {prev} -> {tg} at line {n} without a seen cell of the mover's")
            targets[seat] = tg
            continue
        m = re.match(r"concam tick (\d+) px \((-?\d+), (-?\d+)\)", line)
        if m:
            con["console"].append((int(m.group(1)), (int(m.group(2)), int(m.group(3)))))
    v1, m1 = check(cams, step, "waiting camera seat", bad)
    v2, m2 = check(con, 8, "console camera", bad, True)
    print(f"cam_check: {v1} views ({m1} moves) of the waiting windows, {v2} console camera steps ({m2} moves)")
    for b in bad[:20]:
        print("FAIL", b)
    sys.exit(1 if bad else 0)


main()
