"""Pictures of maps for the linter and the before/after sheets: one coloured cell per tile (our own colours, not the game's art, so
nothing from the games is in them), units as lettered discs, problems boxed with their rule ids and listed beside the map."""
from PIL import Image, ImageDraw, ImageFont
from .terrain import terrain, PROP_KIND

COL = {".": (150, 196, 96), "f": (50, 120, 60), "^": (140, 120, 100), "R": (214, 190, 140), "-": (80, 150, 230), "=": (150, 100, 50),
       "~": (30, 70, 150), ",": (236, 224, 150), "r": (60, 130, 140), "I": (140, 140, 150), "Z": (90, 90, 100), "M": (200, 60, 60),
       "#": (40, 30, 50), "?": (255, 0, 255), "T": (200, 200, 200)}
ARMY = {0: (170, 170, 170), 1: (240, 130, 30), 2: (60, 110, 240), 3: (50, 170, 70), 4: (240, 210, 40), 5: (130, 50, 170)}
UNIT_INITIAL = {1: "i", 2: "m", 3: "M", 4: "G", 5: "T", 6: "R", 7: "A", 8: "N", 9: "p", 10: "a", 11: "k", 12: "S", 13: "B", 14: "Z", 15: "s", 16: "F",
                17: "b", 18: "y", 19: "c", 20: "t", 21: "W", 22: "C", 23: "L", 24: "U", 26: "V", 27: "O"}


def font(size):
    for p in ("/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf", "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_map(m, problems=(), cell=16, legend=True, title=None):
    T = terrain()
    h, w = len(m.tiles), len(m.tiles[0])
    lines = [f"{p.rule} ({p.x},{p.y}) {p.msg}" for p in problems][:60]
    lw = 520 if legend else 0
    head = 22
    H = max(h * cell + head, head + 14 * (len(lines) + 1) + 8) if legend else h * cell + head
    img = Image.new("RGB", (w * cell + lw, H), (24, 24, 30))
    d = ImageDraw.Draw(img)
    f, fs = font(max(8, cell - 4)), font(11)
    d.text((4, 4), title or f"{m.name} ({m.source}) {w}x{h}", fill=(240, 240, 240), font=fs)
    for y in range(h):
        for x in range(w):
            t = m.tiles[y][x]
            c = T.ch(t)
            col = COL.get(c, (255, 255, 255))
            lab = ""
            if c in "HBCAP":
                own = PROP_KIND[t][1]
                col = ARMY[own]
                lab = c
            elif c == "T":
                lab = "T"
            x0, y0 = x * cell, y * cell + head
            d.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=col)
            if lab:
                d.text((x0 + 3, y0 + 1), lab, fill=(0, 0, 0), font=f)
            elif c == "=":
                d.line([x0, y0 + cell // 2, x0 + cell, y0 + cell // 2], fill=(220, 180, 100), width=2)
    for u in getattr(m, "units", []) or []:
        x0, y0 = u["x"] * cell, u["y"] * cell + head
        d.ellipse([x0 + 1, y0 + 1, x0 + cell - 2, y0 + cell - 2], fill=ARMY.get(u["army"], (255, 255, 255)), outline=(0, 0, 0))
        d.text((x0 + 4, y0 + 1), UNIT_INITIAL.get(u["kind"], "?"), fill=(0, 0, 0), font=f)
    for p in problems:
        if p.x < 0:
            continue
        col = (255, 40, 40) if p.level == "error" else (255, 170, 0)
        x0, y0 = p.x * cell, p.y * cell + head
        d.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], outline=col, width=2)
    if legend:
        d.text((w * cell + 8, head), "problems" if problems else "no problems", fill=(240, 240, 240), font=fs)
        for i, ln in enumerate(lines):
            lv = problems[i].level
            d.text((w * cell + 8, head + 14 * (i + 1)), ln[:84], fill=(255, 110, 110) if lv == "error" else (255, 190, 80), font=fs)
    return img
