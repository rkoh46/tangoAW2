"""The silhouette check (the owner's rule: BH2 maps must not all be the same oval): each map's land/sea mask is compared with every other map's, and the generic "rounded blob in the sea" is flagged.

- Pairwise: the *obstacle* mask (water, shoal, reef, lava and mountains) of each map on a 24 x 16 grid; two maps whose masks overlap by more than SIMILAR (intersection over union) look alike. Edge-to-edge land maps compare by their ranges.
- Blob: sea along all four edges (the biggest landmass is inset from every edge), one landmass that is 90% of the land, and a shape that fits its bounding ellipse (IoU >= 0.78) with high solidity (>= 0.88): an island that is an oval.
Maps the owner has approved (APPROVED) are grandfathered: they are measured and listed, never failed (Act I's M1, M2, M4 and the whole of Act II). `aw2dev bh2 silhouettes` prints the numbers; `aw2dev bh2 check` fails on a new map that is too like another or is a blob."""
import glob
import os

import numpy as np

SIMILAR = 0.62
APPROVED = {"bh2_01", "bh2_02", "bh2_03", "bh2_04", "bh2_05", "bh2_06", "bh2_07", "bh2_08", "bh2_09", "bh2_10", "bh2_10b"}
SKIP = {"bh2_04b"}                      # the sky front has no land


def _rows(path):
    return [l.rstrip("\n") for l in open(path) if l.strip() and not l.startswith(("#", "unit", "map", "armies", "team", "objective", "blackhole", "nohq", "owners", "split", "zone"))]


def _grid(rows, chars, gw=24, gh=16):
    h, w = len(rows), len(rows[0])
    a = np.array([[1 if c in chars else 0 for c in r] for r in rows], float)
    out = np.zeros((gh, gw))
    for j in range(gh):
        for i in range(gw):
            y0 = int(j * h / gh); y1 = max(int((j + 1) * h / gh), y0 + 1)
            x0 = int(i * w / gw); x1 = max(int((i + 1) * w / gw), x0 + 1)
            out[j, i] = a[y0:y1, x0:x1].mean()
    return out


def _hull_area(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return len(pts)
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    h = lo[:-1] + up[:-1]
    return abs(sum(h[i][0] * h[(i + 1) % len(h)][1] - h[(i + 1) % len(h)][0] * h[i][1] for i in range(len(h)))) / 2


def _components(land):
    h, w = land.shape
    seen = np.zeros_like(land, bool)
    out = []
    for y in range(h):
        for x in range(w):
            if land[y, x] and not seen[y, x]:
                st, c = [(x, y)], []
                seen[y, x] = True
                while st:
                    a, b = st.pop()
                    c.append((a, b))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        X, Y = a + dx, b + dy
                        if 0 <= X < w and 0 <= Y < h and land[Y, X] and not seen[Y, X]:
                            seen[Y, X] = True
                            st.append((X, Y))
                out.append(c)
    return sorted(out, key=len, reverse=True)


def blob_metrics(rows):
    """{inset, main (share of the land in the biggest landmass), ellipse (IoU with the bounding ellipse), solidity} of one map's land."""
    h, w = len(rows), len(rows[0])
    land = np.array([[c not in "~,r" for c in r] for r in rows])
    comps = _components(land)
    c = comps[0]
    xs, ys = [p[0] for p in c], [p[1] for p in c]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    L = np.zeros_like(land)
    for x, y in c:
        L[y, x] = True
    E = np.zeros_like(land)
    for y in range(h):
        for x in range(w):
            E[y, x] = ((x - (x0 + x1) / 2) / (bw / 2)) ** 2 + ((y - (y0 + y1) / 2) / (bh / 2)) ** 2 <= 1
    pts = [(x + a, y + b) for x, y in c for a in (0, 1) for b in (0, 1)]
    return {"inset": min(x0, w - 1 - x1, y0, h - 1 - y1), "main": len(c) / land.sum(), "ellipse": float((L & E).sum() / (L | E).sum()), "solidity": len(c) / _hull_area(pts)}


def is_blob(m):
    return m["inset"] >= 1 and m["main"] >= 0.9 and m["ellipse"] >= 0.78 and m["solidity"] >= 0.88


def analyse(five_dir):
    """(masks, metrics, pairs): per map the obstacle mask and blob metrics; every pair's IoU, highest first."""
    names = [os.path.basename(p)[:-4] for p in sorted(glob.glob(os.path.join(five_dir, "bh2_*.txt"))) if os.path.basename(p)[:-4] not in SKIP]
    rows = {n: _rows(os.path.join(five_dir, n + ".txt")) for n in names}
    masks = {n: _grid(rows[n], "~,r^") > 0.4 for n in names}
    metrics = {n: blob_metrics(rows[n]) for n in names}
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            A, B = masks[a], masks[b]
            pairs.append((float((A & B).sum() / max(1, (A | B).sum())), a, b))
    return masks, metrics, sorted(pairs, reverse=True)


def check(five_dir):
    """Problems (strings): a new map too like another map, or a blob. Approved maps are never failed. Returns (problems, report lines)."""
    masks, metrics, pairs = analyse(five_dir)
    problems, lines = [], []
    for iou, a, b in pairs:
        if iou >= SIMILAR:
            both = a in APPROVED and b in APPROVED
            lines.append(f"{a} and {b} overlap {iou:.2f}" + (" (both approved)" if both else ""))
            if not both:
                problems.append(f"{a} and {b} look alike: their land/water/ranges overlap {iou:.2f} (limit {SIMILAR})")
    for n, m in metrics.items():
        if is_blob(m):
            lines.append(f"{n} is a blob (ellipse {m['ellipse']:.2f}, solidity {m['solidity']:.2f})" + (" (approved)" if n in APPROVED else ""))
            if n not in APPROVED:
                problems.append(f"{n} is a rounded blob in the sea (sea on all four sides, ellipse fit {m['ellipse']:.2f}, solidity {m['solidity']:.2f})")
    return problems, lines
