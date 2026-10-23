"""Battle-scene figures and portraits of a skin (docs/dev/army-packs.md "Battle figures and portraits"): the skin's patched sheets as the game's console holds them (decoded from the
engine's own output), beside AW2's Green Earth ones the skin starts from, for the review sheet and a parity check against the data file's rules."""
import struct
from PIL import Image, ImageDraw
from . import Rom, NAMES, toml_art
from .sheet import lz77, label, BG

FIG_TABLE, PORTRAIT_TABLE, BASE_COUNTRY = 0x085D64A8, 0x0849DC18 + 0x14, 2


def frames(data):
    return [data[i * 512:(i + 1) * 512] for i in range(len(data) // 512)]


def grid(f):
    g = [[0] * 32 for _ in range(32)]
    for k in range(16):
        for y in range(8):
            for x in range(4):
                b = f[k * 32 + y * 4 + x]
                g[(k // 4) * 8 + y][(k % 4) * 8 + 2 * x] = b & 15
                g[(k // 4) * 8 + y][(k % 4) * 8 + 2 * x + 1] = b >> 4
    return g


def dome(g, size):
    """Python twin of `army_skin::dome_of`: the top-left of the 12 x 9 block of army-coloured pixels above the face."""
    top = next((y for y in range(32) if any(g[y])), None)
    face = next((y for y in range(32) if any(v in (8, 9, 10) for v in g[y])), None)
    if top is None or face is None or face < top + 7:
        return None
    pts = [(x, y) for y in range(top, face) for x in range(32) if 2 <= g[y][x] <= 5]
    if not pts:
        return None
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    return (x0, y0) if x1 - x0 + 1 == size[0] and size[1] - 1 <= y1 - y0 + 1 <= size[1] else None


def patched(g, at, patch):
    out = [r[:] for r in g]
    for dy, row in enumerate(patch["rows"]):
        for dx, c in enumerate(row):
            x, y = at[0] + patch.get("x", 0) + dx, at[1] + patch.get("y", 0) + dy
            if c != "." and 0 <= x < 32 and 0 <= y < 32:
                out[y][x] = 0 if c == "_" else int(c, 16)
    return out


def sheets_of(base, sk):
    """{(unit, which): (original frames of Green Earth's sheet, the skin's frames)} from the engine's patched blobs; which 0, 1 the two sheets, 2 the portrait."""
    table = struct.unpack("<6I", sk.blobs["battle figures: table"][0][:24])
    heads = [p for p in sk.info["blobs"] if p["what"] == "battle figures: table"]
    at0 = heads[0]["addr"]
    data = sk.blobs["battle figures and portraits"][0]
    rec = base.u32(FIG_TABLE + 4 * (5 + BASE_COUNTRY))
    out = {}
    for unit in (1, 2):
        for which in range(3):
            addr = table[3 * (unit - 1) + which]
            if not addr:
                continue
            src = base.u32(rec + 16 * which) if which < 2 else base.u32(PORTRAIT_TABLE + 4 * (15 * unit + BASE_COUNTRY))
            orig = lz77(bytes(base.b), src & 0x01FFFFFF)
            mine = lz77(data, addr - (at0 + 0x20))
            out[(unit, which)] = (frames(orig), frames(mine))
    return out


def palette(sk, host, bank_row=0):
    """The figures' palette on colour `host` in the skin's ROM image (entries 0..15, row 0 of the power-colours table)."""
    return sk.pal(0x084F2BC8 + 32 * (2 * (host - 1) + bank_row))


def draw_frame(f, pal, scale):
    g = grid(f)
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for y in range(32):
        for x in range(32):
            if g[y][x]:
                im.putpixel((x, y), tuple(pal[g[y][x]]) + (255,))
    return im.resize((32 * scale, 32 * scale), Image.NEAREST)


def check_parity(base, sk, skin_data):
    """The engine's patched frames equal the data file's rules applied here (Python twin): [failure text]."""
    fails = []
    for (unit, which), (orig, mine) in sheets_of(base, sk).items():
        sect = skin_data["portrait" if which == 2 else "battle"]["infantry" if unit == 1 else "mech"]
        for i, (o, m) in enumerate(zip(orig, mine)):
            g = grid(o)
            at = dome(g, sect["dome"])
            want = patched(g, at, sect) if at else g
            if want != grid(m):
                fails.append(f"battle figures: unit {unit} {'portrait' if which == 2 else 'sheet %d' % which} frame {i} differs from the data file's rules")
    return fails


def battle_sheet(host=1, skin_path=None):
    """Sheet 10: the soldiers' battle frames (both sheets: the rifle's and the bazooka's) at 2x and 4x, Green Earth's above the skin's, and the portraits at 4x."""
    base, sk = Rom(), Rom(host, skin_path)
    pal_skin = palette(sk, host)
    pal_ge = palette(base, 3)
    sh = sheets_of(base, sk)
    W = 1500
    im = Image.new("RGB", (W, 2200), BG)
    d = ImageDraw.Draw(im)
    label(im, "Battle-scene soldiers and portraits: Green Earth's (AW2's own, which the skin starts from) above, the skin's below; frames of the two sheets the Infantry and the Mech use", (8, 6), size=16)
    y = 34
    for which, title in ((1, "rifle sheet (Infantry; the Mech's machine gun): walking in, kneeling to fire, hit and falling"), (0, "bazooka sheet (the Mech against vehicles): the same, with the launcher")):
        orig, mine = sh[(1, which)]
        label(im, f"{title} at 2x  (the falling frames have no helmet block and keep AW2's)", (8, y), size=14)
        y += 22
        for row, (frs, pal) in enumerate(((orig, pal_ge), (mine, pal_skin))):
            for i, f in enumerate(frs):
                g = draw_frame(f, pal, 2)
                im.paste(g, (8 + i * 66, y), g)
            y += 68
        y += 6
    label(im, "at 4x: standing, walking, kneeling to fire (Green Earth's, then the skin's), rifle sheet frames 0, 3, 12, 14 and bazooka sheet frames 0, 12", (8, y), size=14)
    y += 22
    picks = [(1, 1, 0), (1, 1, 3), (1, 1, 12), (1, 1, 14), (1, 0, 0), (1, 0, 12)]
    for row, which_set in enumerate((0, 1)):
        x = 8
        for unit, which, k in picks:
            f = sh[(unit, which)][which_set][k]
            g = draw_frame(f, pal_ge if which_set == 0 else pal_skin, 4)
            im.paste(g, (x, y), g)
            x += 136
        y += 136
    label(im, "portraits on the unit panel at 4x: Infantry and Mech, Green Earth's then the skin's", (8, y), size=14)
    y += 22
    x = 8
    for unit in (1, 2):
        if (unit, 2) not in sh:
            continue
        for which_set, pal in ((0, pal_ge), (1, pal_skin)):
            g = draw_frame(sh[(unit, 2)][which_set][0], pal, 4)
            im.paste(g, (x, y), g)
            x += 150
    y += 140
    return im.crop((0, 0, W, y + 8))
