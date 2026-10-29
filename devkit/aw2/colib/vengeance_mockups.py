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


def components(im, box):
    """The white letters of a window word (8-connected white pixels in `box`: a lowercase letter's strokes touch at corners; letters are two columns apart), left to right, each a set of (x, y) relative to the box."""
    x0, y0, x1, y1 = box
    white = {(x, y) for x in range(x0, x1) for y in range(y0, y1) if im.getpixel((x, y)) == WHITE}
    out = []
    while white:
        stack = [white.pop()]
        comp = set(stack)
        while stack:
            x, y = stack.pop()
            for n in ((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy):
                if n in white:
                    white.remove(n)
                    comp.add(n)
                    stack.append(n)
        out.append(comp)
    out.sort(key=lambda c: min(p[0] for p in c))
    return [{(x - x0, y - y0) for x, y in c} for c in out]


# The window's capital V, drawn in its letters' style (2-pixel strokes, the capitals' height: rows 5..13 of the 16-row word box), since no window word of AW2 has a V.
V_ROWS = ["##...##", "##...##", "##...##", ".##.##.", ".##.##.", ".##.##.", "..###..", "..###..", "...#..."]


def lettering(frames):
    """ "Vengeance" in the unit window's own lettering: e, n, c from "Recon", g from "Brdg", a from "Tank" (the game's words, cut letter by letter), V drawn to match; one column between letters, and the
    dark outline round the white as the window draws it."""
    rb = Image.open(os.path.join(frames, "word_recon_bridge.bmp")).convert("RGB")
    tp = Image.open(os.path.join(frames, "word_tank_plain.bmp")).convert("RGB")
    recon = components(rb, (172, 100, 210, 116))          # R e c o n
    brdg = components(rb, (210, 100, 240, 116))           # B r d g
    tank = components(tp, (172, 100, 205, 116))           # T a n k
    v = {(x, 5 + y) for y, row in enumerate(V_ROWS) for x, c in enumerate(row) if c == "#"}
    letters = {"V": v, "e": recon[1], "c": recon[2], "n": recon[4], "g": brdg[3], "a": tank[1]}
    fill = set()
    x = 1
    for ch in "Vengeance":
        g = letters[ch]
        gx0 = min(p[0] for p in g)
        for px, py in g:
            fill.add((x + px - gx0, py))
        x += max(p[0] for p in g) - gx0 + 2
    edge = {(px + dx, py + dy) for px, py in fill for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - fill
    return fill, edge, x


# "+" and "%" in the window digits' style (2-pixel strokes, the digits' 6 rows), drawn: the window has neither
PLUS_ROWS = ["..##..", "..##..", "######", "######", "..##..", "..##.."]
PERCENT_ROWS = ["##...#", "##..#.", "...#..", "..#...", ".#..##", "#...##"]
VENGEANCE_PCT = {8: 32, 7: 38, 6: 44, 5: 50, 4: 56, 3: 62, 2: 68, 1: 92}      # (in all: the flat 7% and Vengeance)


def digits(frames):
    """The window's own digits, cut from its HP number (the unit windows of the Tanks at 1..9 HP) and the 0 of its "70" (ammo): {char: set of (x, y), rows 0..5}."""
    out = {}
    for d in range(1, 10):
        im = Image.open(os.path.join(frames, f"panel_hp{d}.bmp")).convert("RGB")
        c = components(im, (190, 128, 204, 136))
        if c:
            g = max(c, key=len)
            y0 = min(p[1] for p in g)
            out[str(d)] = {(x, y - y0) for x, y in g}
    im = Image.open(os.path.join(frames, "panel_hp9.bmp")).convert("RGB")
    c = components(im, (180, 136, 204, 144))
    if len(c) >= 2:
        g = c[-1]
        y0 = min(p[1] for p in g)
        out["0"] = {(x, y - y0) for x, y in g}
    out["+"] = {(x, y) for y, row in enumerate(PLUS_ROWS) for x, ch in enumerate(row) if ch == "#"}
    out["%"] = {(x, y) for y, row in enumerate(PERCENT_ROWS) for x, ch in enumerate(row) if ch == "#"}
    return out


def set_line(glyphs, text, y_off=0):
    fill, x = set(), 1
    for ch in text:
        g = glyphs[ch]
        gx0 = min(p[0] for p in g)
        for px, py in g:
            fill.add((x + px - gx0, py + y_off))
        x += max(p[0] for p in g) - gx0 + 2
    return fill, x


def window_top(im):
    fill_cols = {(139, 156, 32), (156, 156, 16)}
    return min(y for y in range(40, 160) for x in range(0, 240, 3) if im.getpixel((x, y)) in fill_cols)


def window_x(im):
    """The window's left and right edges (a row inside it: its fill colours)."""
    fill_cols = {(139, 156, 32), (156, 156, 16)}
    y = window_top(im) + 6
    xs = [x for x in range(0, 240) if im.getpixel((x, y)) in fill_cols]
    return min(xs), max(xs) + 1


def option_d(panel, frames=None, bonus=None, mock=None):
    """The unit window with one more strip on top: "Vengeance" (the window's fill and corner kept)."""
    im = panel.copy()
    y1 = window_top(im)
    # (the window's own left and right edges, measured on a row inside it: its fill colours)
    x0, x1 = window_x(im)
    strip = im.crop((x0, y1 + 2, x1, y1 + 4))          # the window's fill pattern, two rows
    extra = 10 if bonus else 0
    for yy in range(y1 - 16 - extra, y1 + 2):
        for xx in range(x0, x1):
            im.putpixel((xx, yy), strip.getpixel((xx - x0, (yy - y1) % 2)))
    if frames and os.path.exists(os.path.join(frames, "word_recon_bridge.bmp")):
        fill, edge, w = lettering(frames)
        ox, oy = x0 + (x1 - x0 - w) // 2, y1 - 18 - extra
        for px, py in edge:
            im.putpixel((ox + px, oy + py), (0, 41, 0))
        for px, py in fill:
            im.putpixel((ox + px, oy + py), WHITE)
        if bonus:
            f2, w2 = set_line(digits(mock), f"+{bonus}%")
            e2 = {(px + dx, py + dy) for px, py in f2 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - f2
            ox2, oy2 = x0 + (x1 - x0 - w2) // 2, y1 - 9
            for px, py in e2:
                im.putpixel((ox2 + px, oy2 + py), (0, 41, 0))
            for px, py in f2:
                im.putpixel((ox2 + px, oy2 + py), WHITE)
    else:
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
    words = os.path.join(os.path.dirname(frames.rstrip("/")), "aria_vengeance_mockup_words")
    d = option_d(panel, words)
    e = option_d(option_a(panel, cells, (255, 40, 24)), words)
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


RAMP = {8: (248, 168, 0), 7: (248, 136, 0), 6: (248, 104, 0), 5: (248, 72, 0), 4: (240, 40, 0), 3: (224, 16, 0), 2: (200, 0, 0), 1: (168, 0, 0)}


def forecast(fc, words, frames, bonus):
    """The enemy's forecast on a Vengeance unit: the DAMAGE box lifted by the header's height and the window's "Vengeance +N%" header under it (the same header as the player's own window)."""
    im = fc.copy()
    wt = window_top(im)
    ground = lambda c: is_ground(c)
    wx0, wx1 = window_x(im)
    # (the DAMAGE box alone: its light frame's extent above the window, then everything inside that rectangle down to the window: the box and its pointer, no unit beside it)
    light = [(x, y) for y in range(max(0, wt - 34), wt) for x in range(max(0, wx0 - 8), min(240, wx1 + 8)) if sum(im.getpixel((x, y))) > 600 and not ground(im.getpixel((x, y)))]
    pts = light
    if pts:
        bx0, by0 = min(p[0] for p in pts) - 1, min(p[1] for p in pts) - 1
        bx1, by1 = max(p[0] for p in pts) + 2, wt
        box = im.crop((bx0, by0, bx1, by1))
        clean = fc.crop((bx0, by0 - 40, bx1, by0 - 40 + (by1 - by0))) if by0 >= 40 else None
        if clean is not None:
            im.paste(clean, (bx0, by0))
        im.paste(box, (bx0, by0 - 26))
    return option_d(im, words, bonus, frames)


def around(im):
    """A 90 x 120 view round the window (its whole height and what sits above it)."""
    x0, x1 = window_x(im)
    cx = max(45, min(240 - 45, (x0 + x1) // 2))
    return (cx - 45, 40, cx + 45, 160)


def sheet_e(frames, words, fcdir, out):
    cells = json.load(open(os.path.join(frames, "cells.json")))
    global TANK_Y, CAM_X
    base = Image.open(os.path.join(frames, "base.bmp")).convert("RGB")
    CAM_X = cells["cam_base"][0]
    TANK_Y = row_top(base, 3)
    row = base.copy()
    for x, hp in tanks(cells):
        if hp <= 8:
            recolour_digit(row, x, RAMP[hp])
    box = (16 * 2 - CAM_X - 4, TANK_Y - 9, 16 * 12 - CAM_X + 4, TANK_Y + 16)
    wins = []
    for hp in (9, 8, 2, 1):
        im = Image.open(os.path.join(frames, f"panel_hp{hp}.bmp")).convert("RGB")
        wins.append((f"{hp} HP" + ("  (no Vengeance)" if hp > 8 else f"  +{VENGEANCE_PCT[hp]}%"), im if hp > 8 else option_d(im, words, VENGEANCE_PCT[hp], frames)))
    fcs = []
    unit = os.environ.get("AW2TEST_VENGEANCE_UNIT", "tank").capitalize()
    for hp in (8, 5, 2, 1):
        if os.path.exists(os.path.join(fcdir, f"fc_hp{hp}.bmp")):
            im = Image.open(os.path.join(fcdir, f"fc_hp{hp}.bmp")).convert("RGB")
            fcs.append((f"Andy's {unit} targets her {hp} HP {unit}", forecast(im, words, frames, VENGEANCE_PCT[hp])))
    sc = 6
    cw, ch = (box[2] - box[0]) * sc, (box[3] - box[1]) * sc
    crop = (150, 40, 240, 160)
    ww, wh = (crop[2] - crop[0]) * 3, (crop[3] - crop[1]) * 3
    pad, head = 12, 36
    W = max(cw, 4 * (ww + pad)) + 2 * pad
    H = pad + head + ch + 2 * pad + head + wh + 2 * pad + head + wh + 2 * pad
    sh = Image.new("RGB", (W, H), (20, 20, 28))
    dr = ImageDraw.Draw(sh)
    y = pad
    dr.text((pad, y), "Option E (mock-up). On the map: the HP number goes from orange at 8 HP to dark red at 1 HP; 10 and 9 stay white.", fill=(240, 220, 120))
    sh.paste(row.crop(box).resize((cw, ch), Image.NEAREST), (pad, y + head))
    y += head + ch + 2 * pad
    dr.text((pad, y), "Her unit window (cursor on the unit): Vengeance and that unit's own bonus, for attack and defence.", fill=(240, 220, 120))
    for k, (label, im) in enumerate(wins):
        x = pad + k * (ww + pad)
        dr.text((x, y + 18), label, fill=(200, 200, 210))
        sh.paste(im.crop(around(im)).resize((ww, wh), Image.NEAREST), (x, y + head))
    y += head + wh + 2 * pad
    dr.text((pad, y), "The enemy's damage forecast on a Vengeance unit: the same line, the DAMAGE box above it (the % already counts her defence bonus).", fill=(240, 220, 120))
    for k, (label, im) in enumerate(fcs):
        x = pad + k * (ww + pad)
        dr.text((x, y + 18), label, fill=(200, 200, 210))
        sh.paste(im.crop(around(im)).resize((ww, wh), Image.NEAREST), (x, y + head))
    sh.save(out)
    return out
