"""Every army's units, looked for black silhouettes (the owner's 0.9.2 reports: Silver Nova's picked-up Battle Copter, moved Landers and the
capture box's soldier drew nearly black). For each army colour (Orange Star .. Black Hole, and Silver Nova on the colour it sits on), each
unit (the 24 of AW2 and Dual Strike's new ones) and each state the map draws (idle, picked up, moved), in AW2's look and with the Dual
Strike map graphics, the share of the sprite's pixels that are near black is measured from the console's own sheets and palette rows.
An army whose sprite is far darker than the darkest of AW2's own armies' for the same unit, or mostly black, fails. The table is written
to audit.txt beside the shots."""

import os
import struct

from aw2test import gauntlet as ga
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test
from aw2test.rom import UNIT_NAMES

CAULDER = 0x58
UNIT_ROWS, MOVED_ROWS, MOVING_ROWS = 0x0810_E6E0, 0x0810_E780, 0x0810_EA60
AW2_IDLE, DS_IDLE = 0x0810_BE60, 0x09EB_0000
AW2_SLOTS = 0x0849_9608
AW2_MOVES = 0x0849_CD88
DS_MOVES = 0x09EC_0000
NEW_IDLE, NEW_MOVES = 0x0868_8000, 0x0868_9000
NEW_UNITS = 7
COLOURS = ["Orange Star", "Blue Moon", "Green Earth", "Yellow Comet", "Black Hole"]
DARK = 0.18
# An army's sprite fails when this much more of it is near black than the darkest of Orange Star's, Blue Moon's, Green Earth's and Yellow Comet's (or mostly black and darker than theirs).
MARGIN, MOSTLY = 0.15, 0.55


def lz77(e, at):
    """GBA LZ77 (type 0x10) at `at` in the console's ROM."""
    head = struct.unpack("<I", e.read(at, 4))[0]
    if head & 0xFF != 0x10:
        return None
    size = head >> 8
    src = e.read(at + 4, min(0x2000, size * 2 + 64))
    out = bytearray()
    i = 0
    while len(out) < size and i < len(src):
        flags = src[i]
        i += 1
        for b in range(8):
            if len(out) >= size or i >= len(src):
                break
            if flags & (0x80 >> b):
                n = (src[i] >> 4) + 3
                d = ((src[i] & 15) << 8 | src[i + 1]) + 1
                i += 2
                for _ in range(n):
                    out.append(out[-d])
            else:
                out.append(src[i])
                i += 1
    return bytes(out)


def rows(e, base):
    return [struct.unpack("<16H", e.read(base + 32 * c, 32)) for c in range(5)]


def lum(c):
    r, g, b = (c & 31) * 255 / 31, (c >> 5 & 31) * 255 / 31, (c >> 10 & 31) * 255 / 31
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def hist(tiles):
    h = [0] * 16
    for b in tiles:
        h[b & 15] += 1
        h[b >> 4] += 1
    return h


def dark_share(h, row):
    total = sum(h[1:])
    return sum(h[i] for i in range(1, 16) if lum(row[i]) < DARK) / total if total else 0.0


def sheets(e, ds):
    """{unit: {"idle": index histogram, "moving": index histogram}} for colour 1's sheets (the art is the same in every colour's but Infantry and Mech)."""
    out = {}
    idle_base = DS_IDLE if ds else AW2_IDLE
    for t in range(1, 25):
        slot = struct.unpack("<H", e.read(AW2_SLOTS + 2 * t, 2))[0]
        if slot >= 0x6C // 4 or (slot == 0 and t != 3):
            continue
        idle = e.read(idle_base + 128 * slot, 128)
        mv = lz77(e, DS_MOVES + 0x1000 * (t - 1)) if ds else lz77(e, struct.unpack("<I", e.read(AW2_MOVES + 36 * t, 4))[0])
        out[t] = {"idle": hist(idle), "moving": hist(mv) if mv else None}
    for k in range(NEW_UNITS):
        out[25 + k] = {"idle": hist(e.read(NEW_IDLE + 384 * k, 128)), "moving": (lambda m: hist(m) if m else None)(lz77(e, NEW_MOVES + 0x1000 * k))}
    return out


def game(ctx, look, skin):
    env = {"TANGOAW2_DS_GRAPHICS": "1" if look == "ds" else "0"}
    e = Emu(save=paths.base_save(), ds=ctx.ds, env=env)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    if skin:
        ga.Gauntlet(g).start(CAULDER, colour=6)
    else:
        m = ctx.map()
        m.unit(1, "tank", 10, 6).unit(2, "tank", 20, 6)
        g = ctx.start(m, ["andy", "olaf"], env=env)
    return g.e


@test(modes=("ds",))
def unit_audit_all_armies(ctx):
    lines, bad = [], []
    for look in ("aw2", "ds"):
        plain = game(ctx, look, False)
        art = sheets(plain, look == "ds")
        tables = {"idle": rows(plain, UNIT_ROWS), "moving": rows(plain, MOVING_ROWS), "moved": rows(plain, MOVED_ROWS)}
        sn = game(ctx, look, True)
        host = sn.u8(0x0203_C500)
        ctx.log(f"{look} moved rows: OS " + " ".join("%04x" % c for c in rows(plain, MOVED_ROWS)[0]) + " | SN " + " ".join("%04x" % c for c in rows(sn, MOVED_ROWS)[host - 1]))
        sn_tables = {"idle": rows(sn, UNIT_ROWS)[host - 1], "moving": rows(sn, MOVING_ROWS)[host - 1], "moved": rows(sn, MOVED_ROWS)[host - 1]}
        for t, a in sorted(art.items()):
            name = UNIT_NAMES.get(t, f"unit {t}")
            for state in ("idle", "moving", "moved"):
                h = a["moving"] if state == "moving" else a["idle"]
                if h is None or sum(h[1:]) == 0:
                    continue
                own = [dark_share(h, tables[state][c]) for c in range(5)]
                sk = dark_share(h, sn_tables[state])
                ref = max(own[:4])
                row = f"{look:3} {state:6} {name:12} " + " ".join(f"{COLOURS[c][:2]} {own[c]:.2f}" for c in range(5)) + f"  SN {sk:.2f}"
                lines.append(row)
                for who, v in [(COLOURS[c], own[c]) for c in range(5)] + [("Silver Nova", sk)]:
                    # (a unit Dual Strike draws dark in every army, the Carrier or the Missiles, is its art: only darker than AW2's own armies' counts)
                    if v > ref + MARGIN or (v > MOSTLY and v > ref + 0.05):
                        bad.append(f"{look} {state} {name}: {who} {v:.2f} near-black (AW2's other armies at most {ref:.2f})")
    with open(os.path.join(ctx.out, "audit.txt"), "w") as f:
        f.write("\n".join(lines + ["", "FAILURES:"] + bad) + "\n")
    for b in bad:
        ctx.log("bad   " + b)
    ctx.check(not bad, f"no army's unit is a black silhouette ({len(bad)} failures, table in audit.txt)")
