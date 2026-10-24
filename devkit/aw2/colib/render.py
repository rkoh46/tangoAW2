"""Pictures of portraits for the review sheets (docs/dev/co-kit.md)."""
from PIL import Image, ImageDraw, ImageFont
from . import roms

BG = (38, 42, 54)
PANEL = (52, 58, 74)


def font(n=14):
    try:
        return ImageFont.load_default(size=n)
    except TypeError:
        return ImageFont.load_default()


def to_image(px_rows, scale=1, bg=None):
    """px_rows: rows of RGB or None (a compose.Pic's `.px`)."""
    h, w = len(px_rows), len(px_rows[0])
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0) if bg is None else bg + (255,))
    for y, r in enumerate(px_rows):
        for x, c in enumerate(r):
            if c is not None:
                im.putpixel((x, y), c + (255,))
    return im.resize((w * scale, h * scale), Image.NEAREST) if scale != 1 else im


def donor_image(pic, pal, scale=1):
    from .compose import Pic
    return to_image(Pic(pic, pal).px, scale)


def text(im, xy, s, fill=(235, 235, 235), size=14):
    ImageDraw.Draw(im).text(xy, s, fill=fill, font=font(size))


def wrap(s, width):
    out, line = [], ""
    for w in s.split():
        if len(line) + len(w) + 1 > width and line:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    return out + ([line] if line else [])
