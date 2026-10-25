"""`aw2dev art repal`: put pictures onto a fixed palette, keeping the palette's slot order (docs/dev/art-repal.md).

Every opaque pixel goes to the palette entry with the smallest weighted absolute RGB difference, sum of w_c * |p_c - q_c| with the luma weights
30 / 59 / 11 by default (`rgb` = 1 / 1 / 1); ties go to the lower slot; no dithering. Transparent pixels go to the transparent slot (index 0, or the
last with `alpha_last`, the Mugen convention), which is never used for an opaque pixel. The method follows PalReplacer by Hendrik Iben (2012, MIT;
CREDITS.md); this is our own code, nothing of it is copied.

Palette sources (`load_palette`): a GIMP `.gpl`; a `.pal` (raw 16-bit GBA BGR555 entries, little-endian; JASC-PAL and RIFF PAL text/binary are read
too); a PNG (an indexed PNG's palette in its order, or an RGB picture's unique colours in the order they first appear); `co:<id>` (a custom CO's
committed art palette, art/cos/<id>/large.png); `skin:<id>` (an army skin's unit palette as `Skin::unit_row` builds it, read on the player's AW2 ROM);
`army:os|bm|ge|yc|bh` (AW2's own map-unit palette row of that army, read from the ROM). The ROM is only read."""
import struct
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

WEIGHTS = {"luma": (30, 59, 11), "rgb": (1, 1, 1)}
ARMIES = {"os": 1, "bm": 2, "ge": 3, "yc": 4, "bh": 5}


def weights(spec):
    """'luma' | 'rgb' | 'a,b,c' -> (wr, wg, wb)."""
    if isinstance(spec, (tuple, list)):
        return tuple(int(v) for v in spec)
    if spec in WEIGHTS:
        return WEIGHTS[spec]
    parts = [int(v) for v in str(spec).split(",")]
    if len(parts) != 3 or min(parts) < 0 or sum(parts) == 0:
        raise ValueError(f"weights must be luma, rgb or three non-negative integers a,b,c (got {spec!r})")
    return tuple(parts)


def nearest(rgb, pal, w=(30, 59, 11), allowed=None):
    """rgb: (..., 3) colours; pal: (n, 3). -> (...) the index of the entry with the smallest sum w_c |rgb_c - pal_c| (ties: the lowest index).
    `allowed`: the indexes that may be chosen (default all)."""
    rgb = np.asarray(rgb, dtype=np.int64)
    pal = np.asarray(pal, dtype=np.int64).reshape(-1, 3)
    shape = rgb.shape[:-1]
    flat = rgb.reshape(-1, 3)
    cand = np.arange(len(pal)) if allowed is None else np.asarray(sorted(allowed), dtype=np.int64)
    if len(cand) == 0:
        raise ValueError("the palette has no slot an opaque pixel may use")
    sub = pal[cand]
    wv = np.asarray(w, dtype=np.int64)
    out = np.empty(len(flat), dtype=np.int64)
    step = max(1, (1 << 22) // max(1, len(sub) * 3))
    for s in range(0, len(flat), step):
        d = (np.abs(flat[s:s + step, None, :] - sub[None]) * wv).sum(2)
        out[s:s + step] = cand[d.argmin(1)]          # argmin returns the first minimum: the lower slot wins a tie
    return out.reshape(shape)


# --- palette files ------------------------------------------------------------------------------------------------------------------------------------------------

def to555(c):
    r, g, b = (int(round(v * 31 / 255)) for v in c)
    return r | g << 5 | b << 10


def from555(v):
    return ((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31)


def read_gpl(path):
    pal = []
    for line in Path(path).read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("GIMP") or ":" in s.split()[0]:
            continue
        parts = s.split()
        try:
            pal.append(tuple(int(v) for v in parts[:3]))
        except ValueError:
            continue
    return pal


def write_gpl(pal, path, name=None):
    name = name or Path(path).stem
    lines = ["GIMP Palette", f"Name: {name}", f"Columns: {min(16, max(1, len(pal)))}", "#"]
    lines += [f"{r:3d} {g:3d} {b:3d}\tslot {i}" for i, (r, g, b) in enumerate(pal)]
    Path(path).write_text("\n".join(lines) + "\n")


def read_pal(path):
    b = Path(path).read_bytes()
    if b.startswith(b"JASC-PAL"):
        rows = b.decode().splitlines()
        n = int(rows[2])
        return [tuple(int(v) for v in r.split()[:3]) for r in rows[3:3 + n]]
    if b.startswith(b"RIFF") and b[8:12] == b"PAL ":
        n = struct.unpack_from("<H", b, 22)[0]
        return [tuple(b[24 + 4 * i: 27 + 4 * i]) for i in range(n)]
    if len(b) % 2:
        raise ValueError(f"{path}: a raw .pal is 16-bit entries (odd size {len(b)})")
    return [from555(v) for v in struct.unpack(f"<{len(b) // 2}H", b)]


def write_pal(pal, path):
    Path(path).write_bytes(struct.pack(f"<{len(pal)}H", *(to555(c) for c in pal)))


def write_palette(pal, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".gpl":
        write_gpl(pal, path)
    elif path.suffix.lower() == ".pal":
        write_pal(pal, path)
    else:
        raise ValueError(f"{path}: write a .gpl or a .pal")
    return path


def palette_of_image(path):
    """An indexed PNG's palette in slot order (trailing unused black entries trimmed), or an RGB(A) picture's unique opaque colours in raster order."""
    im = Image.open(path)
    if im.mode == "P":
        flat = im.getpalette() or []
        pal = [tuple(flat[3 * i: 3 * i + 3]) for i in range(len(flat) // 3)]
        used = int(np.array(im).max()) + 1
        while len(pal) > used and pal[-1] == (0, 0, 0):
            pal.pop()
        return pal
    a = np.array(im.convert("RGBA")).reshape(-1, 4)
    a = a[a[:, 3] >= 128, :3]
    _, first = np.unique(a, axis=0, return_index=True)
    pal = [tuple(int(v) for v in a[i]) for i in sorted(first)]
    if len(pal) > 256:
        raise ValueError(f"{path}: {len(pal)} colours, a palette has at most 256")
    return pal


def load_palette(src):
    """-> list of (r, g, b) in slot order, from any palette source (module doc)."""
    s = str(src)
    if s.startswith("co:"):
        from .. import cfg
        p = cfg.REPO / "tango-gamesupport-aw2" / "art" / "cos" / s[3:] / "large.png"
        if not p.exists():
            raise ValueError(f"{s}: no committed art at {p.relative_to(cfg.REPO)} (a recolour-based CO wears its donor's palette: cos/<id>.toml)")
        im = Image.open(p)
        flat = im.getpalette()[:48]
        return [tuple(flat[3 * i: 3 * i + 3]) for i in range(16)]
    if s.startswith("skin:"):
        from ..armyskinlib import Rom, SKIN_DIR, toml_art
        from ..armyskinlib.options import unit_palette
        f = SKIN_DIR / f"{s[5:]}.toml"
        if not f.exists():
            raise ValueError(f"{s}: no skin file {f.name} in tango-gamesupport-aw2/skins/")
        return list(unit_palette(Rom(), toml_art(f), {}))
    if s.startswith("army:"):
        from ..armyskinlib import Rom, UNIT_PAL
        c = ARMIES.get(s[5:].lower())
        if not c:
            raise ValueError(f"{s}: army is one of {', '.join(ARMIES)}")
        return list(Rom().pal(UNIT_PAL + 32 * (c - 1)))
    p = Path(s)
    ext = p.suffix.lower()
    if ext == ".gpl":
        return read_gpl(p)
    if ext == ".pal":
        return read_pal(p)
    return palette_of_image(p)


# --- applying ------------------------------------------------------------------------------------------------------------------------------------------------------

def transparent_slot(n, alpha_last=False, opaque=False):
    return None if opaque else (n - 1 if alpha_last else 0)


def apply(img, pal, w=(30, 59, 11), alpha_last=False, opaque=False, keep_index=False):
    """img: a PIL image. -> (h x w) uint8 indexes into `pal`. Opaque pixels take the nearest slot other than the transparent one; pixels with alpha < 128
    take the transparent slot. `keep_index`: an indexed picture keeps its indexes (a pure palette swap)."""
    n = len(pal)
    if n == 0 or n > 256:
        raise ValueError(f"a palette has 1 to 256 entries (got {n})")
    t = transparent_slot(n, alpha_last, opaque)
    if keep_index:
        if img.mode != "P":
            raise ValueError("--keep-index needs an indexed picture")
        idx = np.array(img).astype(np.int64)
        if idx.max() >= n:
            raise ValueError(f"the picture uses index {int(idx.max())}, the palette has {n} entries")
        return idx.astype(np.uint8)
    a = np.array(img.convert("RGBA"))
    clear = a[..., 3] < 128
    allowed = [i for i in range(n) if i != t]
    idx = nearest(a[..., :3], pal, w, allowed)
    if clear.any():
        if t is None:
            raise ValueError("the picture has transparent pixels but --opaque leaves no transparent slot")
        idx[clear] = t
    return idx.astype(np.uint8)


def indexed_png(idx, pal, tslot=0):
    """An indexed image whose palette is exactly `pal` in slot order (`tslot` marked transparent; None: none)."""
    im = Image.fromarray(np.asarray(idx, np.uint8), mode="P")
    flat = [v for c in pal for v in c]
    im.putpalette(flat, rawmode="RGB")
    if tslot is not None:
        im.info["transparency"] = tslot
    return im


def save_png(idx, pal, path, tslot=0):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    im = indexed_png(idx, pal, tslot)
    kw = {"bits": 4} if len(pal) <= 16 else {}
    if tslot is not None:
        kw["transparency"] = tslot
    im.save(path, optimize=False, **kw)          # optimize would drop and reorder unused entries: the slot order is the point
    return path


def render(idx, pal, tslot=0):
    """Indexes -> RGBA picture."""
    p = np.array([list(c) + [255] for c in pal], np.uint8)
    if tslot is not None:
        p[tslot, 3] = 0
    return Image.fromarray(p[np.asarray(idx, np.int64)], mode="RGBA")


def _checker(w, h, s=8):
    yy, xx = np.mgrid[:h, :w]
    v = np.where(((yy // s) + (xx // s)) % 2 == 0, 70, 90).astype(np.uint8)
    return Image.fromarray(np.stack([v, v, v + 10, np.full_like(v, 255)], -1), mode="RGBA")


def preview(img, idx, pal, tslot=0, title=""):
    """Before | after, scaled by whole pixels to at least 256 rows, on a checkerboard; the palette's slots numbered underneath. -> RGBA picture."""
    before = img.convert("RGBA")
    after = render(idx, pal, tslot)
    k = max(1, -(-256 // before.height))
    if before.width * k > 900:
        k = max(1, 900 // before.width)
    big = lambda im: im.resize((im.width * k, im.height * k), Image.NEAREST)
    b, a = big(before), big(after)
    gap, sw = 12, 22
    cols = min(16, len(pal))
    rows = -(-len(pal) // cols)
    W = max(b.width * 2 + gap * 3, cols * sw + gap * 2)
    H = 20 + b.height + gap * 2 + rows * (sw + 12) + 4
    out = Image.new("RGBA", (W, H), (40, 40, 48, 255))
    d = ImageDraw.Draw(out)
    d.text((gap, 4), (title + "  " if title else "") + "before | after", fill=(230, 230, 230, 255))
    for i, im in enumerate((b, a)):
        x = gap + i * (b.width + gap)
        bg = _checker(im.width, im.height)
        bg.alpha_composite(im)
        out.paste(bg, (x, 20))
    y0 = 20 + b.height + gap
    for i, c in enumerate(pal):
        x, y = gap + (i % cols) * sw, y0 + (i // cols) * (sw + 12)
        d.rectangle((x, y, x + sw - 3, y + sw - 3), fill=tuple(c) + (255,), outline=(255, 80, 80, 255) if i == tslot else (0, 0, 0, 255))
        d.text((x + 2, y + sw - 2), str(i), fill=(200, 200, 200, 255))
    return out
