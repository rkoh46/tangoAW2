"""Dual Strike's attack target cursor: a ring of four quarters with a yellow pointer, drawn instead of AW2's crosshair
(tiles 884..909) on the flat map and on the tilted one (ds_cursor.rs, ds_tilt.rs). The art is bmap/027 (the four
quarters follow the arrow and the dot: rows 68.. of the file read 16 pixels wide, 16 x 16 each: arc, pointer quarter,
three times), palette bmap/028; it runs through three pictures in a turn of 18 frames (7, 2, 8, 1)."""

import os
import struct

from PIL import Image

from aw2test import paths
from aw2test.harness import test
from aw2test.rom import DualStrike

OUT = os.environ.get("AW2TEST_XHAIR", "")
RING = [0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 1]


class Art:
    def __init__(self):
        ds = DualStrike(paths.ds_rom())
        pal = ds.file("bmap/028")
        self.pal = [(((v & 31) * 255) // 31, (((v >> 5) & 31) * 255) // 31, (((v >> 10) & 31) * 255) // 31)
                    for v in (int.from_bytes(pal[2 * i:2 * i + 2], "little") for i in range(16))]
        self.tex = ds.file("bmap/027")

    def quarter(self, k, tip):
        """16 x 16 of RGB or None; frame k's arc or pointer quarter."""
        at = 544 + 256 * k + (128 if tip else 0)
        out = []
        for i in range(256):
            b = self.tex[at + i // 2]
            idx = b & 15 if i % 2 == 0 else b >> 4
            out.append(self.pal[idx] if idx else None)
        return out


def sprites(g):
    """AW2's attack crosshair: the 16 x 16 sprites of tiles 884..909 (palette 1) that show, and the OAM slots."""
    raw = g.e.read(0x07000000, 0x400)
    out = []
    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<3H", raw, 8 * i)
        t = a2 & 0x3FF
        if a0 & 0x300 == 0x200 or not 884 <= t <= 909 or (a2 >> 12) != 1:
            continue
        x, y = a1 & 511, a0 & 255
        x, y = (x - 512 if x >= 240 else x), (y - 256 if y >= 160 else y)
        out.append((i, x, y, t))
    return out


def park(g):
    """Park the crosshair's sprites the way the game hides sprites."""
    n = 0
    for i, _, _, _ in sprites(g):
        a0, a1, a2 = struct.unpack("<3H", g.e.read(0x07000000 + 8 * i, 6))
        g.e.write(0x07000000 + 8 * i, struct.pack("<3H", (a0 & ~0xFF) | 160, a1 & ~0x1FF, a2))
        n += 1
    return n


def scene(ctx, name, tilt, at=(4, 4)):
    env = {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1" if tilt else "0"}
    m = ctx.map()
    m.unit(1, "tank", at[0], at[1]).unit(2, "tank", at[0] + 1, at[1])
    g = ctx.start(m, ["andy", "drake"], env=env)
    g.e.wait(30)
    g.select(*at)
    g.move_to(*at)
    g.choose("Fire", g.ACTION_MENU)
    g.e.wait(20)
    for _ in range(12):
        g.e.shot(os.path.join(ctx.out, "warm"))
    return g


def save_picture(img, name):
    if OUT:
        os.makedirs(OUT, exist_ok=True)
        img.resize((img.width * 3, img.height * 3), Image.NEAREST).save(os.path.join(OUT, name + ".png"))


def close(c, d, tol=70):
    return sum(abs(p - q) for p, q in zip(c, d)) <= tol


def near(px, x, y, c):
    """The pixel, or one beside it, has colour c (the ring is drawn at a fraction of a pixel)."""
    for dy in (0, -1, 1):
        for dx in (0, -1, 1):
            xx, yy = x + dx, y + dy
            if 0 <= xx < 240 and 0 <= yy < 160 and close(px[xx, yy][:3], c):
                return True
    return False


def match(px, quad, x0, y0, n, flip, tolerant=True):
    """(matched, opaque) pixels of the picture `px` over the n x n quad of `art` at (x0, y0), mirrored as told."""
    ok = tot = 0
    for y in range(n):
        v = int((y + 0.5) * 16 / n)
        v = 15 - v if flip[1] else v
        for x in range(n):
            u = int((x + 0.5) * 16 / n)
            u = 15 - u if flip[0] else u
            c = quad[v * 16 + u]
            if c is None:
                continue
            tot += 1
            xx, yy = x0 + x, y0 + y
            if 0 <= xx < 240 and 0 <= yy < 160 and (near(px, xx, yy, c) if tolerant else close(px[xx, yy][:3], c)):
                ok += 1
    return ok, tot


QUARTERS = (("TL", False, (False, False)), ("TR", False, (True, False)), ("BL", False, (False, True)), ("BR", True, (False, False)))


def fit(img, art, centre, ks=(0, 1, 2), sizes=range(11, 22), reach=7):
    """The ring's four quarters in `img` near `centre` (x, y): for each frame k and quarter, the best (size, x0, y0, ratio).
    Returns the frame with the best total and its quarters."""
    px = img.load()
    best = None
    for k in ks:
        total, rows = 0.0, []
        for name, tip, flip in QUARTERS:
            quad = art.quarter(k, tip)
            ox = 0 if name in ("TR", "BR") else -1
            oy = 0 if name in ("BL", "BR") else -1
            top = None
            for n in sizes:
                for y0 in range(int(centre[1] + oy * n) - reach, int(centre[1] + oy * n) + reach + 1):
                    for x0 in range(int(centre[0] + ox * n) - reach, int(centre[0] + ox * n) + reach + 1):
                        ok, tot = match(px, quad, x0, y0, n, flip, tolerant=False)
                        score = ok - 2 * (tot - ok)
                        if top is None or score > top[0]:
                            top = (score, n, x0, y0, 0.0)
            # (the ring is drawn at a fraction of a pixel: the ratio allows a pixel's slack)
            ok, tot = match(px, quad, top[2], top[3], top[1], flip)
            top = top[:4] + (ok / tot,)
            rows.append((name,) + top)
            total += top[0]
        if best is None or total > best[0]:
            best = (total, k, rows)
    # (a neighbouring unit hides part of a quarter: the quarters share the size most of them fit, and are placed again)
    total, k, rows = best
    n = sorted(r[2] for r in rows)[len(rows) // 2]
    again = []
    for (name, tip, flip), r in zip(QUARTERS, rows):
        quad = art.quarter(k, tip)
        top = None
        for y0 in range(r[4] - 3, r[4] + 4):
            for x0 in range(r[3] - 3, r[3] + 4):
                ok, tot = match(px, quad, x0, y0, n, flip, tolerant=False)
                score = ok - 2 * (tot - ok)
                if top is None or score > top[0]:
                    top = (score, n, x0, y0)
        ok, tot = match(px, quad, top[2], top[3], n, flip)
        again.append((name,) + top + (ok / tot,))
    return total, k, again


def box_of(rows):
    xs = [r[3] for r in rows] + [r[3] + r[2] for r in rows]
    ys = [r[4] for r in rows] + [r[4] + r[2] for r in rows]
    return min(xs), min(ys), max(xs), max(ys)


def changed(a, b, tol=24):
    pa, pb = a.load(), b.load()
    return {(x, y) for y in range(160) for x in range(240) if sum(abs(p - q) for p, q in zip(pa[x, y][:3], pb[x, y][:3])) > tol}


def checks_for(ctx, g, name, flat, art):
    """Takes the picture with the crosshair and the same one with its sprites parked (the overlay then has nothing to
    redo: on the tilted map the picture without the ring, on the flat one the console's own with AW2's);
    checks the ring."""
    sp = sprites(g)
    ctx.require(len(sp) == 4, f"{name}: the game shows its crosshair (4 pieces, {len(sp)} found)")
    a = Image.open(ctx.shot(g, name)).convert("RGB")
    save_picture(a, name)
    park(g)
    for _ in range(3):
        g.e.shot(os.path.join(ctx.out, "warm"))
    b = Image.open(ctx.shot(g, name + "_parked")).convert("RGB")
    save_picture(b, name + "_parked")
    diff = changed(a, b)
    ctx.require(len(diff) >= 40, f"{name}: the ring is drawn ({len(diff)} pixels differ from the picture without it)")
    cx = (min(x for x, _ in diff) + max(x for x, _ in diff)) / 2
    cy = (min(y for _, y in diff) + max(y for _, y in diff)) / 2
    total, k, rows = fit(a, art, (cx + 0.5, cy + 0.5))
    ctx.log(f"{name}: diff centre ({cx}, {cy}) frame {k} " + " ".join(f"{r[0]}:{r[2]}px@{r[3]},{r[4]} {r[5]:.2f}" for r in rows))
    for r in rows:
        ctx.check(r[5] >= 0.9, f"{name}: the {r[0]} quarter is Dual Strike's art ({r[5]:.0%} of its pixels, {r[2]} px square)")
    sizes = {r[2] for r in rows}
    ctx.check(max(sizes) - min(sizes) <= 1, f"{name}: the quarters are one size ({sorted(sizes)})")
    # AW2's crosshair is gone. Flat: its four 16-pixel pieces (the same art, in the console's boxes) no longer show.
    # Tilted: the picture differs from the one without the ring by about the ring's own pixels (AW2's would double it;
    # the glow under the target shifts a little between the two, so not exactly).
    mask = set()
    for (qn, tip, flip), r in zip(QUARTERS, rows):
        quad = art.quarter(k, tip)
        n = r[2]
        for y in range(n):
            v = int((y + 0.5) * 16 / n)
            v = 15 - v if flip[1] else v
            for x in range(n):
                u = int((x + 0.5) * 16 / n)
                u = 15 - u if flip[0] else u
                if quad[v * 16 + u] is not None:
                    mask.add((r[3] + x, r[4] + y))
    if flat:
        px = a.load()
        for _, bx, by, _ in sp:
            best = 0.0
            for kk in range(3):
                for t in (False, True):
                    quad = art.quarter(kk, t)
                    for f in ((False, False), (True, False), (False, True), (True, True)):
                        ok, tot = match(px, quad, bx, by, 16, f, tolerant=False)
                        best = max(best, ok / tot)
            ctx.check(best < 0.9, f"{name}: AW2's 16-pixel piece at ({bx}, {by}) is not drawn ({best:.0%} of it)")
    else:
        # no second ring: the ring's white and navy pixels near it all belong to the fitted one
        near_mask = {(x + dx, y + dy) for x, y in mask for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
        px = a.load()
        x0, y0, x1, y1 = box_of(rows)
        extra = [(x, y) for y in range(max(0, y0 - 4), min(160, y1 + 5)) for x in range(max(0, x0 - 4), min(240, x1 + 5))
                 if (x, y) not in near_mask and (min(px[x, y][:3]) >= 238 or close(px[x, y][:3], (49, 98, 148), 40))]
        ctx.log(f"{name}: {len(extra)} ring-coloured pixels beside the ring")
        ctx.check(len(extra) <= 6, f"{name}: one ring, not two ({len(extra)} ring-coloured pixels beside it)")
    return rows, (cx, cy), k


@test(modes=("ds",))
def ds_crosshair_flat(ctx):
    """Flat map: Dual Strike's ring, 30 pixels across and centred on the target's cell."""
    art = Art()
    g = scene(ctx, "flat", False)
    rows, (cx, cy), k = checks_for(ctx, g, "flat", True, art)
    ctx.check({r[2] for r in rows} == {15}, f"the flat ring's quarters are 15 pixels, not AW2's 16 ({[r[2] for r in rows]})")
    x0, y0, x1, y1 = box_of(rows)
    sp = sprites(g)
    # (AW2's crosshair is centred on the cell, so is Dual Strike's)
    ctx.check(abs((x0 + x1) / 2 - 89) <= 2 and abs((y0 + y1) / 2 - 72) <= 2, f"centred on the target's cell, (88, 72): ring ({(x0 + x1) / 2}, {(y0 + y1) / 2})")
    # the yellow pointer is the bottom-right quarter's
    ctx.check(any(r[0] == "BR" and r[5] >= 0.9 for r in rows), "the pointer is the ring's bottom-right quarter")


@test(modes=("ds",))
def ds_crosshair_tilt(ctx):
    """Tilted map: the ring stands on the target's cell, sized with the cell (a cell is 2.07 times smaller than the ring)."""
    art = Art()
    sizes = []
    for at in ((4, 4), (14, 12)):
        g = scene(ctx, f"tilt_{at[0]}", True, at)
        rows, (cx, cy), k = checks_for(ctx, g, f"tilt_{at[0]}", False, art)
        sizes.append(sum(r[2] for r in rows) / 4)
    ctx.log(f"ring quarter sizes {sizes}")
    ctx.check(all(11 <= s <= 18 for s in sizes), f"the tilted ring is 11 to 18 pixels a quarter ({sizes})")
    ctx.check(sizes[1] >= sizes[0], f"lower on the picture, nearer, it is not smaller ({sizes})")


@test(modes=("ds",))
def ds_crosshair_animates(ctx):
    """The ring runs through its three pictures in a turn of 18 frames (7, 2, 8, 1), flat and tilted."""
    art = Art()
    for tilt in (False, True):
        g = scene(ctx, "anim_" + ("t" if tilt else "f"), tilt)
        # (the ring's place from the first picture)
        a = Image.open(ctx.shot(g, "frame")).convert("RGB")
        park(g)
        for _ in range(3):
            g.e.shot(os.path.join(ctx.out, "warm"))
        b = Image.open(ctx.shot(g, "frame_parked")).convert("RGB")
        diff = changed(a, b)
        cx = (min(x for x, _ in diff) + max(x for x, _ in diff)) / 2 + 0.5
        cy = (min(y for _, y in diff) + max(y for _, y in diff)) / 2 + 0.5
        r0 = fit(a, art, (cx, cy))[2]
        n = round(sum(r[2] for r in r0) / 4)
        g2 = scene(ctx, "anim_" + ("t" if tilt else "f"), tilt)
        seq = []
        for i in range(40):
            g2.e.wait(1)
            img = Image.open(ctx.shot(g2, "frame")).convert("RGB")
            seq.append(fit(img, art, (cx, cy), sizes=range(n - 1, n + 2), reach=3)[1])
        ctx.log(f"{'tilt' if tilt else 'flat'} frames: {seq}")
        runs = [seq[0]]
        for k in seq[1:]:
            runs.append(k)
        ok = any(all(seq[i] == RING[(i + s) % 18] for i in range(len(seq))) for s in range(18))
        ctx.check(ok, f"{'tilt' if tilt else 'flat'}: the ring's pictures follow Dual Strike's turn of 18 frames")
        ctx.check(set(seq) == {0, 1, 2}, f"{'tilt' if tilt else 'flat'}: all three pictures show")


@test(modes=("ds",))
def ds_crosshair_off_is_aw2s(ctx):
    """With the map graphics off AW2's own crosshair is untouched."""
    env = {"TANGOAW2_DS_GRAPHICS": "0", "TANGOAW2_TILT": "0"}
    m = ctx.map()
    m.unit(1, "tank", 4, 4).unit(2, "tank", 5, 4)
    g = ctx.start(m, ["andy", "drake"], env=env)
    g.e.wait(30)
    g.select(4, 4)
    g.move_to(4, 4)
    g.choose("Fire", g.ACTION_MENU)
    g.e.wait(20)
    for _ in range(12):
        g.e.shot(os.path.join(ctx.out, "warm"))
    a = Image.open(ctx.shot(g, "off")).convert("RGB")
    save_picture(a, "off")
    n = park(g)
    for _ in range(3):
        g.e.shot(os.path.join(ctx.out, "warm"))
    b = Image.open(ctx.shot(g, "off_parked")).convert("RGB")
    pa, pb = a.load(), b.load()
    diff = sum(1 for y in range(160) for x in range(240) if sum(abs(p - q) for p, q in zip(pa[x, y], pb[x, y])) > 24)
    ctx.log(f"{n} pieces, {diff} pixels differ")
    ctx.check(n == 4 and diff == 0, f"with the graphics off nothing is redone: the picture is the console's own ({n} pieces, {diff} pixels differ)")
