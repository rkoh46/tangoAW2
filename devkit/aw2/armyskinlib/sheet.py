"""Review sheets of a skin (docs/dev/army-packs.md): game pictures from the catalogue's scenarios, one row per unit, the palette against AW2's armies,
and (optionally, in the sheet only, never committed) another project's pictures at the same size for comparison."""
import struct
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from . import Rom, UNIT_PAL, BLD_PAL, UNIT_SHEET, FRAME, SLOT_TABLE, NAMES, sprite, hq as hq_img, emblem as emb_img, foot, scenarios, check
from .. import cfg, harness

BG = (44, 46, 56)


def font(n=14):
    try:
        return ImageFont.load_default(size=n)
    except TypeError:
        return ImageFont.load_default()


def label(im, text, xy, fill=(255, 255, 255), size=14):
    ImageDraw.Draw(im).text(xy, text, fill=fill, font=font(size))


def run_scenarios(names, out, ds=False, ids=None):
    """name -> directory of the shots."""
    dirs = {}
    for n in names:
        sc = scenarios.SCENARIOS[n]
        d = Path(out) / n
        d.mkdir(parents=True, exist_ok=True)
        (d / "script.txt").write_text(scenarios.script(n, (ids or {}).get(n)))
        harness.run_script(d / "script.txt", d, ds=ds or sc["ds"])
        dirs[n] = d
    return dirs


def shot(dirs, scen, name, seat=0):
    p = dirs[scen] / f"{name}_s{seat}.bmp"
    return Image.open(p).convert("RGB") if p.exists() else Image.new("RGB", (240, 160), (90, 0, 0))


def grid(images, cols, scale, pad=6, caption=None, width=None):
    """Tile the (title, image) pairs."""
    w, h = images[0][1].size
    W, H = w * scale, h * scale
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (W + pad) + pad, rows * (H + pad + 18) + pad + (22 if caption else 0)), BG)
    if caption:
        label(sheet, caption, (pad, 4), size=16)
    for i, (t, im) in enumerate(images):
        x, y = pad + (i % cols) * (W + pad), pad + (22 if caption else 0) + (i // cols) * (H + pad + 18)
        sheet.paste(im.resize((W, H), Image.NEAREST), (x, y + 16))
        label(sheet, t, (x, y), size=13)
    return sheet


def unit_rows(host, skin_path=None):
    """One row per AW2 unit: its idle picture in each army's colours and in the skin's (live, done, moving)."""
    base, sk = Rom(), Rom(host, skin_path)
    cols = [(c, base.pal(UNIT_PAL + 32 * (c - 1)), base) for c in (1, 2, 3, 4, 5)]
    names = {1: "Infantry", 2: "Mech", 3: "Recon", 4: "(DS)", 5: "Tank", 6: "Md Tank", 7: "Neotank", 8: "APC", 9: "(DS)", 10: "Artillery", 11: "Rockets",
             12: "(DS)", 13: "(DS)", 14: "Anti-Air", 15: "Missiles", 16: "Fighter", 17: "Bomber", 18: "(DS)", 19: "B Copter", 20: "T Copter", 21: "Battleship",
             22: "Cruiser", 23: "Lander", 24: "Sub"}
    units = [t for t in range(1, 25) if not names[t].startswith("(")]
    S, cell = 4, 16 * 4 + 6
    W = 150 + cell * 9
    sheet = Image.new("RGB", (W, 32 + len(units) * (16 * S + 4)), BG)
    heads = ["Orange Star", "Blue Moon", "Green Earth", "Yellow Comet", "Black Hole", "Emerald Sun", "ES done", "ES moving"]
    for i, hname in enumerate(heads):
        label(sheet, hname, (150 + i * cell, 8), size=10)
    for r, t in enumerate(units):
        y = 28 + r * (16 * S + 4)
        label(sheet, f"{t:2d} {names[t]}", (6, y + 20), size=14)
        x = 150
        for c, pal, rom in cols:
            g = foot(rom, c, t, 0, pal, S) if t in (1, 2) else _unit(rom, c, t, pal, S)
            sheet.paste(g, (x, y), g)
            x += cell
        skpal = sk.pal(UNIT_PAL + 32 * (host - 1))
        g = foot(sk, host, t, 0, skpal, S, skin=True) if t in (1, 2) else _unit(sk, host, t, skpal, S)
        sheet.paste(g, (x, y), g)
        x += cell
        done = sk.pal(UNIT_PAL + 0xA0 + 32 * (host - 1))
        g = foot(sk, host, t, 0, done, S, skin=True) if t in (1, 2) else _unit(sk, host, t, done, S)
        sheet.paste(g, (x, y), g)
        x += cell
        g = _moving(sk, host, t, S)
        if g:
            sheet.paste(g, (x, y), g)
    return sheet


def _unit(rom, colour, t, pal, S):
    slot = rom.u16(SLOT_TABLE + 2 * (25 * (colour - 1) + t))
    return sprite(rom.raw(UNIT_SHEET + 128 * slot, 128), 2, 2, pal, S)


MOVE_TABLE = 0x0849CD88


def _moving(sk, host, t, S):
    """The unit's moving picture, side view first frame, in the skin's moving palette (the sheet LZ77; foot units from the skin's own)."""
    from .. import cfg as _c
    if t in (1, 2) and getattr(sk, "blobs", None) is not None:
        data = sk.blobs.get(("Infantry" if t == 1 else "Mech") + " moving sheet", [None])[0]
        sheet = lz77(data, 0) if data else None
    else:
        ptr = sk.u32(MOVE_TABLE + 0x24 * t + 4 * (host - 1))
        sheet = lz77(sk.b, ptr & 0x01FFFFFF)
    if not sheet:
        return None
    pal = sk.pal(0x0810EA60 + 32 * (host - 1))
    im = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    for k in range(9):
        cx, cy = 2 - k % 3, 2 - k // 3
        tile = sheet[k * 32:(k + 1) * 32]
        for y in range(8):
            for x in range(8):
                b = tile[y * 4 + x // 2]
                v = (b >> (4 * (x & 1))) & 15
                if v:
                    im.putpixel((cx * 8 + x, cy * 8 + y), pal[v] + (255,))
    return im.resize((24 * S * 2 // 3, 24 * S * 2 // 3), Image.NEAREST)


def lz77(buf, off):
    hdr = struct.unpack_from("<I", buf, off)[0]
    n = hdr >> 8
    out, p = bytearray(), off + 4
    while len(out) < n:
        flags = buf[p]
        p += 1
        for i in range(8):
            if len(out) >= n:
                break
            if flags & (0x80 >> i):
                b1, b2 = buf[p], buf[p + 1]
                p += 2
                ln, disp = (b1 >> 4) + 3, ((b1 & 15) << 8 | b2) + 1
                for _ in range(ln):
                    out.append(out[-disp])
            else:
                out.append(buf[p])
                p += 1
    return bytes(out[:n])


def compare_strip(host, awbw_dir=None, S=4):
    """The skin's Infantry, Mech, HQ, emblem at 4x; with `awbw_dir` (reference pictures kept outside the repository) the same of the project it was inspired by,
    beside them, for review only."""
    sk, base = Rom(host), Rom()
    items = []
    pal = sk.pal(UNIT_PAL + 32 * (host - 1))
    bpal = sk.pal(BLD_PAL + 32 * (host - 1))
    mine = {
        "infantry": foot(sk, host, 1, 0, pal, S, skin=True),
        "mech": foot(sk, host, 2, 0, pal, S, skin=True),
        "HQ": hq_img(sk, host, bpal, S, skin=True),
        "emblem": emb_img(sk, host, S * 2),
    }
    sheet = Image.new("RGB", (16 * S * 10 + 40, 44 + 2 * (32 * S + 40)), BG)
    label(sheet, "Emerald Sun (drawn for tangoAW2, original)", (8, 6), size=16)
    x = 8
    for k, im in mine.items():
        sheet.paste(im, (x, 40), im)
        label(sheet, k, (x, 40 + im.height + 2), size=12)
        x += im.width + 24
    if awbw_dir:
        label(sheet, "For comparison only: AWBW's Jade Sun, fetched to the scratchpad, never committed", (8, 40 + 32 * S + 44), size=16)
        x = 8
        for n, key in (("jsinfantry", "infantry"), ("jsmech", "mech"), ("jadesunhq", "HQ"), ("jslogo", "emblem"), ("jadesuncity", "city"), ("jadesunbase", "base")):
            p = Path(awbw_dir) / f"{n}.gif"
            if p.exists():
                im = Image.open(p).convert("RGBA")
                im = im.resize((im.width * S * (2 if key == "emblem" else 1), im.height * S * (2 if key == "emblem" else 1)), Image.NEAREST)
                sheet.paste(im, (x, 40 + 32 * S + 80), im)
                label(sheet, key, (x, 40 + 32 * S + 80 + im.height + 2), size=12)
                x += im.width + 24
    return sheet


def swatches(host):
    """The skin's ramp, trim and done grey next to Green Earth's, Black Hole's and the fog terrain's colours."""
    base, sk = Rom(), Rom(host)
    rows = [("Emerald Sun ramp", sk.pal(UNIT_PAL + 32 * (host - 1))[2:8]), ("ES trim", sk.pal(UNIT_PAL + 32 * (host - 1))[11:14]),
            ("ES done unit", sk.pal(UNIT_PAL + 0xA0 + 32 * (host - 1))[2:8]), ("Green Earth", base.pal(UNIT_PAL + 64)[2:8]), ("Black Hole", base.pal(UNIT_PAL + 128)[2:8]),
            ("Blue Moon", base.pal(UNIT_PAL + 32)[2:8]), ("Orange Star", base.pal(UNIT_PAL)[2:8]), ("Yellow Comet", base.pal(UNIT_PAL + 96)[2:8]),
            ("done greys (GE)", base.pal(UNIT_PAL + 0xA0 + 64)[2:8]), ("done greys (BH)", base.pal(UNIT_PAL + 0xA0 + 128)[2:8]), ("fog terrain", check.FOG_TERRAIN[:6])]
    sheet = Image.new("RGB", (560, 20 + len(rows) * 30), BG)
    for i, (n, cols) in enumerate(rows):
        y = 10 + i * 30
        label(sheet, n, (8, y + 4), size=14)
        for j, c in enumerate(cols):
            ImageDraw.Draw(sheet).rectangle([160 + j * 56, y, 160 + j * 56 + 52, y + 24], fill=tuple(c))
    return sheet
