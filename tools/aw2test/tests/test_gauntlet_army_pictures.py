"""The Gauntlet's army screen in the three looks (AW2 graphics, the Dual Strike map graphics with the tilt, and without it) on four maps: Dustwind Basin (two enemies), Harvest Run (all Orange Star,
four enemies), Chrome Meridian (Silver Nova enemies) and Iron Crown (five lines, Asuka's stage not shown). Per map and look three pictures: the screen as it opens, after UP / DOWN changed the CO, after R
changed the colour. Versus' own Teams screen in the same looks (two and four armies) for comparison. `-k gauntlet_army_pictures`; `AW2TEST_ARMY_PICS` is where the pictures and the two sheets
(`army_screen_sheet.png`, `versus_teams_sheet.png`) go (default: the test's folder). Looked at by a person: the checks only count what the screens must hold."""

import os

from PIL import Image, ImageDraw

from aw2test import gauntlet as ga
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

LOOKS = (
    ("aw2", {}),
    ("ds_tilt", {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1"}),
    ("ds_flat", {"TANGOAW2_DS_GRAPHICS": "1"}),
)
# (title, mission, the CO the second picture changes to: its face is nobody else's on the screen)
MAPS = (("Dustwind Basin", 2, ga.ARIA), ("Harvest Run", 5, ga.ASUKA), ("Chrome Meridian", 6, ga.TABITHA), ("Iron Crown", 1, ga.JAVIER))
STATES = ("default", "co_changed", "colour_changed")


def grab(ctx, e, out, name):
    path = os.path.join(ctx.out, name)
    e.shot(path)
    im = Image.open(path + ".bmp").convert("RGB")
    dest = os.path.join(out, name + ".png")
    im.save(dest)
    return im


def sheet_of(rows, cols, labels_left, labels_top, path, gap=4, head=14, left=150):
    w, h = 240, 160
    sheet = Image.new("RGB", (left + len(cols) * (w + gap), head + len(rows) * (h + gap)), (20, 20, 28))
    dr = ImageDraw.Draw(sheet)
    for j, t in enumerate(labels_top):
        dr.text((left + j * (w + gap), 2), t, fill=(255, 220, 120))
    for i, row in enumerate(rows):
        dr.text((2, head + i * (h + gap) + 4), labels_left[i], fill=(255, 255, 255))
        for j, im in enumerate(row):
            sheet.paste(im, (left + j * (w + gap), head + i * (h + gap)))
    sheet.save(path)


@test(modes=("ds",))
def gauntlet_army_pictures(ctx):
    out = os.environ.get("AW2TEST_ARMY_PICS") or ctx.out
    os.makedirs(out, exist_ok=True)
    rows, names = [], []
    for title, mission, co in MAPS:
        for look, env in LOOKS:
            e = Emu(save=paths.base_save(), ds=ctx.ds, env=env)
            g = Game(e, ctx.image)
            ctx.games.append(g)
            d = ga.Gauntlet(g)
            d.open(map=mission)
            d.wait_army()
            e.wait(20)
            key = title.lower().replace(" ", "_")
            row = [grab(ctx, e, out, f"{key}_{look}_default")]
            enemies = ga.shown(e)[1]
            ctx.check(len(enemies) >= 2, f"{title} {look}: the map has its enemies ({len(enemies)})")
            ctx.eq(d.pick_co(co), co, f"{title} {look}: UP / DOWN reach CO {co}")
            e.wait(20)
            row.append(grab(ctx, e, out, f"{key}_{look}_co_changed"))
            free = ga.shown(e)[2]
            before = e.u8(ga.UI_COLOUR_CURSOR)
            e.press("R", 4)
            e.wait(20)
            ctx.eq(e.u8(ga.UI_COLOUR_CURSOR), (before + 1) % len(free), f"{title} {look}: R moves to the next free colour ({free})")
            row.append(grab(ctx, e, out, f"{key}_{look}_colour_changed"))
            ctx.check(row[0].tobytes() != row[1].tobytes(), f"{title} {look}: the CO change shows")
            if len(free) > 1:
                ctx.check(row[1].tobytes() != row[2].tobytes(), f"{title} {look}: the colour change shows")
            rows.append(row)
            names.append(f"{title} / {look}")
            e.close()
    sheet_of(rows, STATES, names, STATES, os.path.join(out, "army_screen_sheet.png"))
    # Versus' own Teams screen, two and four armies, in the same looks
    vrows = []
    for look, env in LOOKS:
        row = []
        for n in (2, 4):
            m = ctx.map(hq=tuple((a, 0 if a % 2 else 29, 0 if a < 3 else 19) for a in range(1, n + 1)))
            g = ctx.boot_teams(m, env=env)
            g.set_teams(["andy", "drake", "sami", "grit"][:n], {1})
            g.e.wait(80)
            row.append(grab(ctx, g.e, out, f"versus_{n}p_{look}"))
            g.e.close()
        vrows.append(row)
    sheet_of(vrows, ("2 armies", "4 armies"), [l for l, _ in LOOKS], ("2 armies", "4 armies"), os.path.join(out, "versus_teams_sheet.png"))
