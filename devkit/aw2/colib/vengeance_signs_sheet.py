"""The review sheets of Aria's Vengeance signs as the game draws them (option E, crate::aria_sign): the map row, her unit window at 9 / 8 / 2 / 1 HP and the enemy's damage forecasts at 8 / 5 / 2 / 1 HP, laid out as the
mock-up sheets (vengeance_mockups.py `sheet_e`) from the frames tests/test_aria_vengeance_signs.py keeps with `AW2TEST_VENGEANCE_REVIEW=<dir>` (run it once for each unit:
`AW2TEST_VENGEANCE_UNIT=tank AW2TEST_VENGEANCE_ATTACKER=tank`, then megatank). Pictures only: they come from the player's own ROMs and are never committed.
`python3 -m aw2.colib.vengeance_signs_sheet DIR [OUT_DIR]` from devkit/ (OUT_DIR defaults to DIR)."""
import os
import sys

from PIL import Image, ImageDraw

from . import vengeance_mockups as mm

PCT = mm.VENGEANCE_PCT
BG = (20, 20, 28)
TITLE = (240, 220, 120)
LABEL = (200, 200, 210)
UNITS = ("tank", "megatank")


def img(d, name):
    return Image.open(os.path.join(d, name + ".bmp")).convert("RGB")


def around(twin):
    """A 90 x 120 view round the window (its whole height and the room above it), from the twin game's frame (the same window, no strip)."""
    x0, x1 = mm.window_x(twin)
    cx = max(45, min(240 - 45, (x0 + x1) // 2))
    return (cx - 45, 22, cx + 45, 160)


def map_row(d, kind, sc=6):
    im = img(d, f"{kind}_map_aria")
    box = [int(v) for v in open(os.path.join(d, f"{kind}_map_box.txt")).read().split()]
    d2, d11 = box[:4], box[4:]
    crop = (d2[0] - 12, d2[1] - 14, d11[2] + 4, d2[1] + 11)
    return im.crop(crop).resize(((crop[2] - crop[0]) * sc, (crop[3] - crop[1]) * sc), Image.NEAREST)


def name(kind):
    return kind.capitalize()


def sheet(d, out, kinds=UNITS):
    """One sheet: for each unit the map row, then the windows and the forecasts."""
    sc = 3
    pics = []
    for kind in kinds:
        wins = []
        for hp in (9, 8, 2, 1):
            a, t = img(d, f"{kind}_win_aria_{hp}"), img(d, f"{kind}_win_andy_{hp}")
            c = around(t)
            wins.append((f"{hp} HP" + ("  (no Vengeance)" if hp > 8 else f"  +{PCT[hp]}%"), a.crop(c)))
        fcs = []
        for hp in (8, 5, 2, 1):
            p = os.path.join(d, f"{kind}_fc_aria_{hp}.bmp")
            if os.path.exists(p):
                a = img(d, f"{kind}_fc_aria_{hp}")
                t = img(d, f"{kind}_fc_andy_{hp}")
                fcs.append((f"Andy's {name(kind)} targets her {hp} HP {name(kind)}", a.crop(around(t))))
        pics.append((kind, map_row(d, kind), wins, fcs))
    ww, wh = 90 * sc, 138 * sc
    pad, head = 12, 36
    W = max(max(p[1].width for p in pics), 4 * (ww + pad)) + 2 * pad
    H = pad
    for kind, row, wins, fcs in pics:
        H += head + row.height + pad + head + wh + pad + head + wh + 2 * pad
    sh = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(sh)
    y = pad
    for kind, row, wins, fcs in pics:
        dr.text((pad, y), f"Option E in the game ({name(kind)}). On the map: the HP number goes from orange at 8 HP to dark red at 1 HP; 10 and 9 stay white, an Oozium and other COs' units too.", fill=TITLE)
        sh.paste(row, (pad, y + head))
        y += head + row.height + pad
        dr.text((pad, y), "Her unit window (cursor on the unit): Vengeance and that unit's own bonus, for attack and defence.", fill=TITLE)
        for k, (label, im) in enumerate(wins):
            x = pad + k * (ww + pad)
            dr.text((x, y + 18), label, fill=LABEL)
            sh.paste(im.resize((ww, wh), Image.NEAREST), (x, y + head))
        y += head + wh + pad
        dr.text((pad, y), "The enemy's damage forecast on a Vengeance unit: the same line, the DAMAGE box above it (the % already counts her defence bonus).", fill=TITLE)
        for k, (label, im) in enumerate(fcs):
            x = pad + k * (ww + pad)
            dr.text((x, y + 18), label, fill=LABEL)
            sh.paste(im.resize((ww, wh), Image.NEAREST), (x, y + head))
        y += head + wh + 2 * pad
    sh.save(out)
    return out


def main(d, out_dir=None):
    out_dir = out_dir or d
    os.makedirs(out_dir, exist_ok=True)
    kinds = [k for k in UNITS if os.path.exists(os.path.join(d, f"{k}_map_aria.bmp"))]
    outs = [sheet(d, os.path.join(out_dir, f"option_e_game_{k}.png"), (k,)) for k in kinds]
    if len(kinds) > 1:
        outs.append(sheet(d, os.path.join(out_dir, "option_e_game_both.png"), tuple(kinds)))
    return outs


if __name__ == "__main__":
    for p in main(*sys.argv[1:]):
        print(p)
