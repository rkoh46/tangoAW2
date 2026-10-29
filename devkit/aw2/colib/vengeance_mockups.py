"""Mock-ups of a Vengeance sign on the battle map (A coloured HP digit, B power shimmer, C status badge, D unit-window line, E = A + D), composed from the game's own frames
(tests/test_aria_vengeance_mockup.py: Aria's Tanks at 10 down to 1 displayed HP) and its own graphics: the HP digits, the power flash, the terrain panel's defence star, AW2's font
(gfxlib.font) in the window's colours. Pictures only: nothing here is in the game. `python3 -m aw2.colib.vengeance_mockups FRAMES_DIR OUT.png` from devkit/."""
import json, os, sys
from PIL import Image, ImageDraw

CAM_X = 0
TANK_Y = 32          # the Tanks' cell top on screen (set from the frame's camera: row * 16 - camera y - 16)
WHITE = (255, 255, 255)


def tanks(cells):
    return [(x, hp) for x, _, hp in cells["tanks"]]


def recolour_digit(im, x, colour):
    """The HP digit (white on black, the cell's lower-right 8x7) of the Tank in column x drawn in `colour`."""
    for yy in range(TANK_Y + 5, TANK_Y + 12):
        for xx in range(16 * x - CAM_X + 8, 16 * x - CAM_X + 16):
            if im.getpixel((xx, yy)) == WHITE:
                im.putpixel((xx, yy), colour)


def option_a(base, cells, colour):
    im = base.copy()
    for x, hp in tanks(cells):
        if hp <= 8:
            recolour_digit(im, x, colour)
    return im


def option_b(base, cells, k=0.45):
    """AW2 has no lasting glow on units while a power is on (it flashes every unit once as the power starts); B would be a new slow pulse on the wounded units, in the
    flash's light: shown here at its brightest (the unit's own colours blended toward white; the HP digit, the icons and the black outline kept)."""
    im = base.copy()
    for x, hp in tanks(cells):
        if hp > 8:
            continue
        for yy in range(TANK_Y - 2, TANK_Y + 12):
            for xx in range(16 * x - CAM_X, 16 * x - CAM_X + 16):
                if xx >= 16 * x - CAM_X + 8 and (yy >= TANK_Y + 4 or yy < TANK_Y + 1):
                    continue
                c = im.getpixel((xx, yy))
                if is_ground(c) or sum(c) < 90:
                    continue
                im.putpixel((xx, yy), tuple(int(v + (255 - v) * k) for v in c))
    return im


def is_ground(c):
    r, g, b = c
    return g > 180 and r > 150 and b < 110


def star(panel):
    """The terrain panel's defence star (its own pixels, the panel's fill left out)."""
    # (found by its light yellow, in the panel's lower right; a 1-pixel margin for its outline)
    pts = [(x, y) for x in range(150, 240) for y in range(90, 160) if panel.getpixel((x, y)) == (255, 255, 106)]
    x0, y0 = min(p[0] for p in pts) - 2, min(p[1] for p in pts) - 2
    box = (x0, y0, x0 + 11, y0 + 11)
    src = panel.crop(box)
    fill = {(139, 156, 32), (156, 156, 16), (197, 230, 49), (222, 238, 32)}
    return [(x, y, src.getpixel((x, y))) for y in range(src.height) for x in range(src.width) if src.getpixel((x, y)) not in fill]


def option_c(base, panel, cells):
    im = base.copy()
    st = star(panel)
    for x, hp in tanks(cells):
        if hp <= 8:
            for sx, sy, c in st:
                if sx < 9 and sy < 9:
                    im.putpixel((16 * x - CAM_X - 2 + sx, TANK_Y - 5 + sy), c)      # (top-left: AW2's ammo and fuel icons have the top-right)
    return im


def text(im, x, y, s, fill=WHITE, edge=(0, 41, 0)):
    from aw2.gfxlib import font
    f = font.load()
    for ch in s:
        if ch not in f:
            x += 4
            continue
        w, ink, anyp = f[ch][0], f[ch][1], f[ch][2]
        for r in range(14):
            for c in range(w):
                if ink[r] >> c & 1:
                    im.putpixel((x + c, y + r), fill)
                elif anyp[r] >> c & 1:
                    im.putpixel((x + c, y + r), edge)
        x += w + 1
    return x


def option_d(panel):
    """The unit window with one more strip on top: "Vengeance" (the window's fill and corner kept)."""
    im = panel.copy()
    x0, x1, y1 = 173, 236, 99
    strip = im.crop((x0, y1 + 2, x1, y1 + 4))          # the window's fill pattern, two rows
    for yy in range(y1 - 16, y1 + 2):
        for xx in range(x0, x1):
            im.putpixel((xx, yy), strip.getpixel((xx - x0, (yy - y1) % 2)))
    text(im, x0 + 5, y1 - 16, "Vengeance")
    return im


def row_top(im, x):
    """The Tanks' cell top on screen, found in the picture: the first row where the HP digit box of the Tank in column x (the cell's right half) is all black."""
    for y in range(4, 150):
        if all(sum(im.getpixel((xx, y))) < 60 for xx in range(16 * x - CAM_X + 8, 16 * x - CAM_X + 16)):
            return y - 5
    raise SystemExit("no HP digit box found")


def main(frames, out):
    global TANK_Y, CAM_X
    cells = json.load(open(os.path.join(frames, "cells.json")))
    base = Image.open(os.path.join(frames, "base.bmp")).convert("RGB")
    panel = Image.open(os.path.join(frames, "panel_8hp.bmp")).convert("RGB")
    row = cells.get("row", 6)
    ty_base = 16 * row - cells["cam_base"][1] - 16
    ty_panel = 16 * row - cells["cam"][1] - 16
    CAM_X = cells["cam_base"][0]
    ty_base = row_top(base, 3)
    CAM_X = cells["cam"][0]
    ty_panel = row_top(panel, 3)
    TANK_Y, CAM_X = ty_base, cells["cam_base"][0]
    a_orange = option_a(base, cells, (255, 156, 0))
    a_red = option_a(base, cells, (255, 40, 24))
    b = option_b(base, cells)
    TANK_Y = ty_panel
    star_src = base          # (only the terrain panel is up there: its star is the one light yellow)
    TANK_Y, CAM_X = ty_base, cells["cam_base"][0]
    c = option_c(base, star_src, cells)
    TANK_Y, CAM_X = ty_panel, cells["cam"][0]
    d = option_d(panel)
    e = option_d(option_a(panel, cells, (255, 40, 24)))
    TANK_Y, CAM_X = ty_base, cells["cam_base"][0]
    box = (16 * 2 - CAM_X - 4, TANK_Y - 9, 16 * 12 - CAM_X + 4, TANK_Y + 16)
    rows = [("Today, no sign. Tanks at 10 down to 1 HP: Vengeance is on from 8 down. The 6 HP one is low on fuel, the 4 HP one out of ammo (AW2's icons, top-right)", base),
            ("A1  HP number in orange, 8 and below", a_orange),
            ("A2  HP number in red, 8 and below", a_red),
            ("B   a slow pulse on the wounded units (a new effect: AW2 only flashes units once, when a power starts); shown at its brightest", b),
            ("C   a badge: the terrain panel's defence star, top-left of the unit (the ammo and fuel icons keep the top-right)", c)]
    sc, pad, head = 5, 12, 20
    cw, ch = (box[2] - box[0]) * sc, (box[3] - box[1]) * sc
    full_w, full_h = 240 * 3, 160 * 3
    W = max(cw, 2 * full_w + pad) + 2 * pad
    H = pad + len(rows) * (ch + head + pad) + head + full_h + 2 * pad
    sheet = Image.new("RGB", (W, H), (20, 20, 28))
    dr = ImageDraw.Draw(sheet)
    y = pad
    for label, im in rows:
        dr.text((pad, y + 4), label, fill=(240, 220, 120))
        sheet.paste(im.crop(box).resize((cw, ch), Image.NEAREST), (pad, y + head))
        y += ch + head + pad
    for k, (label, im) in enumerate([("D   the unit window gets a Vengeance line (cursor on the 8 HP Tank)", d), ("E   A + D: red number on the map, and the line in the window", e)]):
        x = pad + k * (full_w + pad)
        dr.text((x, y + 4), label, fill=(240, 220, 120))
        sheet.paste(im.resize((full_w, full_h), Image.NEAREST), (x, y + head))
    sheet.save(out)
    return out


if __name__ == "__main__":
    print(main(sys.argv[1], sys.argv[2]))
