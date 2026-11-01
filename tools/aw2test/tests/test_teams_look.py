"""The Normal Battle TEAMS screen's look with the new COs and the Emerald Sun skin.

* The CO cards (`teams_cards_show_the_committed_faces`): each custom CO's 48 x 48 face on the card, in the 1P and the CP column, is the committed
  `art/cos/<id>/face_normal.png` pixel for pixel (the screen's colours, 5 bits a channel). Until 0.9.1 Silver Nova's COs' faces were
  cut from the picture at twice the size (`mug_scale` missing in their framing files), so the card showed eyes and nose only.
* The windows (`teams_windows_stay_aw2s_with_the_skin`): AW2's own screen paints its help box in Orange Star's window colours whichever armies
  are chosen (checked with each of AW2's five); the Emerald Sun skin on a seat's army must not change them (it used to turn the box olive when it
  took Orange Star's colour: `army_skin::refresh_palettes` rewrote the windows' palette bank too)."""

import os

from PIL import Image

from aw2test.harness import test
from tests.test_tag import read_bmp
from tests.test_teams_faces import OAM
import struct

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tango-gamesupport-aw2", "art", "cos")
COS = {"tabitha": 86, "lili": 87, "caulder": 88, "asuka": 92, "aria": 93}
HELP_BOX = (12, 150)          # inside the help box at the bottom
HELP_BOX_EDGE = (4, 138)      # its border


def card_origin(e, col):
    """Top-left of column `col`'s face (left to right) from its sprites: the 32x8 and 16x8 pieces of the 6 rows."""
    oam = e.read(OAM, 0x400)
    groups = {}
    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<HHH", oam, 8 * i)
        if (a0 >> 8) & 3 == 2 or (a2 >> 10) & 3 != 3 or a0 >> 14 != 1 or a1 >> 14 not in (0, 1):
            continue
        groups.setdefault(a2 >> 12, []).append((a0 & 0xFF, a1 & 0x1FF))
    cols = sorted((min(x for _, x in v), min(y for y, _ in v)) for v in groups.values())
    return cols[col]


def q(c):
    return tuple(v >> 3 for v in c)


@test(modes=("ds",))
def teams_cards_show_the_committed_faces(ctx):
    m = ctx.map()
    bad = 0
    for name, co in COS.items():
        face = Image.open(os.path.join(ART, name, "face_normal.png")).convert("RGBA")
        # a face framed to show the whole head leaves the picture's background around it (Aria's 231 pixels is the least of the six; the zoomed
        # Emerald Sun faces had 0 to 404 and filled the square with eyes and nose)
        clear = sum(1 for y in range(48) for x in range(48) if face.getpixel((x, y))[3] == 0)
        bad += not ctx.check(clear >= 150, f"{name}: the face shows the whole head, not a zoomed crop ({clear} background pixels in the 48 x 48 square)")
        for col in (0, 1):
            g = ctx.boot_teams(m)
            cos = ["andy", "andy"]
            cos[col] = co
            g.set_teams(cos, {1})
            g.e.wait(80)
            path = ctx.shot(g, f"card_{name}_{'1P' if col == 0 else 'CP'}")
            x0, y0 = card_origin(g.e, col)
            rows = read_bmp(path)
            diff = 0
            seen = 0
            for y in range(48):
                for x in range(48):
                    r, gg, b, a = face.getpixel((x, y))
                    if min(x, y, 47 - x, 47 - y) < 3:      # (the card's frame)
                        continue
                    if (x < 18 and y >= 30) or (x >= 24 and y < 14):    # (the army's emblem and the 1P / CP tag lie over the face's corners)
                        continue
                    if a == 0 or not (0 <= y0 + y < 160 and 0 <= x0 + x < 240):
                        continue
                    seen += 1
                    diff += q(rows[y0 + y][x0 + x]) != q((r, gg, b))
            ctx.log(f"{name} {'1P' if col == 0 else 'CP'}: card at ({x0},{y0}), {diff} of {seen} pixels differ")
            ok = ctx.check(seen > 400 and diff <= seen // 100, f"{name}: the {'1P' if col == 0 else 'CP'} card shows the committed face ({diff} of {seen} pixels differ)")
            bad += not ok
            g.e.close()
    ctx.eq(bad, 0, "cards with a wrong face")


@test(modes=("ds",))
def teams_windows_stay_aw2s_with_the_skin(ctx):
    m = ctx.map()
    g = ctx.boot_teams(m)
    e = g.e
    g.set_teams(["andy", "andy"], {1})
    e.press("LEFT", 6); e.wait(14); e.press("LEFT", 6); e.wait(40)   # the cursor on the 1P column
    seen = []
    for k in range(7):         # 1P's army through Orange Star, Yellow Comet, Green Earth, Black Hole, then Emerald Sun, and on
        e.wait(60)
        rows = read_bmp(ctx.shot(g, f"win1p_{k}"))
        seen.append((rows[HELP_BOX[1]][HELP_BOX[0]], rows[HELP_BOX_EDGE[1]][HELP_BOX_EDGE[0]]))
        e.press("R", 6)
        e.wait(30)
    ctx.log(f"help box colours by army: {seen}")
    ctx.eq(len(set(seen)), 1, "the help box's colours with every army (AW2's five and Emerald Sun) on 1P")
    e.close()
