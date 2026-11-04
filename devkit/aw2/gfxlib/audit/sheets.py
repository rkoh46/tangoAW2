"""Contact sheets of the audit's pictures: one set per (mode, look), 3 columns at 2x, nine to a sheet, each cell captioned with scene/shot; cells with findings are framed red."""
from pathlib import Path
from PIL import Image, ImageDraw

COLS, ROWS, SCALE, GAP, CAP = 3, 3, 2, 8, 14   # (defaults; make() takes others)


def _cell(path, caption, bad, scale=SCALE):
    im = Image.open(path).convert("RGB").resize((240 * scale, 160 * scale), Image.NEAREST)
    c = Image.new("RGB", (im.width, im.height + CAP), (30, 30, 30))
    c.paste(im, (0, CAP))
    d = ImageDraw.Draw(c)
    d.text((3, 1), caption[:80], fill=(255, 120, 120) if bad else (230, 230, 230))
    if bad:
        d.rectangle((0, 0, c.width - 1, c.height - 1), outline=(255, 0, 0), width=3)
    return c


def make(items, out_dir, stem, cols=COLS, rows=ROWS, scale=SCALE):
    """items: [(png path, caption, bad)]; returns the sheets' paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    per = cols * rows
    for s in range(0, len(items), per):
        chunk = items[s:s + per]
        cells = [_cell(*it, scale=scale) for it in chunk]
        w, h = cells[0].size
        nrows = (len(cells) + cols - 1) // cols
        im = Image.new("RGB", (cols * w + (cols + 1) * GAP, nrows * h + (nrows + 1) * GAP), (60, 60, 60))
        for k, c in enumerate(cells):
            im.paste(c, (GAP + (k % cols) * (w + GAP), GAP + (k // cols) * (h + GAP)))
        p = out_dir / f"{stem}_{s // per + 1:02d}.png"
        im.save(p)
        paths.append(str(p))
    return paths
