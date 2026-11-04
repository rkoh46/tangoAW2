"""The audit's detectors. Each takes a `Shot` (the picture, the video-state dump when there is one, the scene's tags) and returns findings:
{"detector", "severity": "fail"|"warn", "msg", "box": [x, y, w, h] (optional)}. `DETECTORS` lists them; `judge(shot)` runs those that apply.

What each one catches (docs/dev/graphics.md, "The audit"):
  blank      a frame of one plain colour (black or white screen, a window that never drew)
  stripes    black / white (or any two far colours) stripes in a small window: a BG map cell drawn from the wrong tiles or palette (past bug: Silver Nova's striped Infantry cells)
  dark       a 16 x 16 block of pure black on a map: a black building or unit (a palette that never loaded)
  sprites    OAM: an uninitialised entry drawn at the top-left corner, an unseen sprite budget overflow (a scanline over the GBA's 1210 cycles drops sprites), a sprite that draws only black
  palette    video state: a palette bank the screen draws with that is grey where it must not be (past bug: the moved-unit grey written over the dialogue faces' bank 9), or that is all one colour
  text       dialogue box text: every glyph must be one of the game's own (a glyph cell that matches none is two strings drawn into the same tiles, past bug: the garbled first box)
  leftover   a 16 x 16 block of detail identical to the previous picture while the screen around it changed completely (tiles of the previous screen left on a new one)
  seams      tilt: thin dark or bright lines running across the picture where the tilted plane's tiles do not meet
  facts      the scene's own checks from the game's memory (which HQ the terrain panel draws, ...)
"""
import numpy as np
from PIL import Image

from .. import ocr

# ---- tuning: calibrated on the first full sweep (docs/dev/graphics.md); every number has the corpus it was set against in the audit report's `calibration` table
STRIPE_WINDOW_FLIPS = 100      # sn_looks' striped Infantry/Mech cells measured over 100 flips in a 16 x 16 window, healthy AW2 art about 50
GREY_CHROMA = 14               # a palette entry is grey when max-min of its channels (0..255) is below this
GREY_BANK_ENTRIES = 10         # a bank is grey when this many of entries 1..15 are grey and all are within GREY_CHROMA
WASHED_HUE_SPREAD = 8          # degrees; faces measured 11..24 over the first sweep
CYCLES_PER_LINE = 1210         # GBA OBJ budget per scanline in a non-HBlank-free mode (a sprite w wide costs w cycles, rotated 2 w + 10)


class Shot:
    def __init__(self, mode, scene, look, name, png, vram, tags, meta, prev=None, facts=None):
        self.mode, self.scene, self.look, self.name, self.png, self.vram_path = mode, scene, look, name, png, vram
        self.tags, self.meta, self.prev, self._img, self._dump = set(tags), meta, prev, None, None

    @property
    def img(self):
        if self._img is None:
            self._img = Image.open(self.png).convert("RGB")
        return self._img

    @property
    def arr(self):
        return np.asarray(self.img, dtype=np.int32)

    @property
    def dump(self):
        if self._dump is None and self.vram_path:
            from ..vram import Dump
            self._dump = Dump.load(self.vram_path)
        return self._dump

    @property
    def tilted(self):
        return self.look == "ds_tilt"

    @property
    def label(self):
        return f"{self.mode}/{self.scene}/{self.look}/{self.name}"


def F(detector, msg, severity="fail", box=None):
    d = {"detector": detector, "severity": severity, "msg": msg}
    if box:
        d["box"] = [int(v) for v in box]
    return d


# ---------------------------------------------------------------------------------------------------------------- blank
def blank(s):
    if s.tags & {"fade", "blank_ok", "burst"}:      # (an animation's frames: a black one between two scenes is a cut, not a dead screen)
        return []
    a = s.arr
    flat = a.reshape(-1, 3)
    vals, counts = np.unique(flat[:, 0] * 65536 + flat[:, 1] * 256 + flat[:, 2], return_counts=True)
    top = counts.max() / len(flat)
    if top >= 0.995:
        c = vals[counts.argmax()]
        return [F("blank", f"{top:.1%} of the picture is one colour ({c >> 16 & 255},{c >> 8 & 255},{c & 255})")]
    return []


# ---------------------------------------------------------------------------------------------------------------- stripes
def _flip_window_max(img):
    """The most black/white-ish neighbour flips in any 16 x 16 window (sn_looks.stripes, vectorised): (flips, x, y)."""
    a = np.asarray(img, dtype=np.int32)
    lum = a.sum(axis=2)
    cls = np.where(lum < 120, 0, np.where(lum > 600, 2, 1))
    f = ((cls[:, :-1] != cls[:, 1:]) & (cls[:, :-1] != 1) & (cls[:, 1:] != 1)).astype(np.int32)
    H, W = f.shape
    # integral image of the flip map: window sums
    ii = np.zeros((H + 1, W + 1), dtype=np.int32)
    ii[1:, 1:] = f.cumsum(0).cumsum(1)
    best, at = 0, (0, 0)
    ws, hs = 15, 16
    sums = ii[hs:, ws:] - ii[:-hs, ws:] - ii[hs:, :-ws] + ii[:-hs, :-ws]
    if sums.size:
        k = int(sums.argmax())
        best = int(sums.flat[k])
        at = (k % sums.shape[1], k // sums.shape[1])
    return best, at


def stripes(s):
    # (text boxes and menus are black on white by design and flip as often: the detector is for the map layers, where a cell drawn from the wrong tiles shows as stripes)
    if not (s.tags & {"map", "battle"}) or s.tags & {"fade", "blank_ok", "title", "dialogue", "dialogue_box", "copage", "menu", "scene", "power", "capture"}:
        return []
    img = s.img
    if s.tilted:
        img = img.resize((240, 160), Image.NEAREST) if img.size != (240, 160) else img
    best, (x, y) = _flip_window_max(img)
    limit = s.meta.get("stripe_limit", STRIPE_WINDOW_FLIPS)
    if best >= limit:
        return [F("stripes", f"a 16 x 16 window at ({x},{y}) flips black/white {best} times (limit {limit})", box=(x, y, 16, 16))]
    return []


# ---------------------------------------------------------------------------------------------------------------- dark
def dark(s):
    """Pure black 16 x 16 blocks where a map is drawn: black buildings and units (a palette that never loaded)."""
    if "map" not in s.tags or s.tags & {"fade", "blank_ok", "setup"}:
        return []
    a = s.arr
    H, W = a.shape[:2]
    lum = a.sum(axis=2)
    blk = (lum < 36)
    gw, gh = W // 16, H // 16
    grid = np.zeros((gh, gw), dtype=bool)
    for gy in range(gh):
        for gx in range(gw):
            grid[gy, gx] = blk[gy * 16:gy * 16 + 16, gx * 16:gx * 16 + 16].mean() >= 0.97
    # (the letterbox round a small map, a menu's black corners and the tilt's edge touch the border of the picture: only a black patch with picture all round it counts,
    # and a patch of more than 12 blocks is a dark scene, not a building)
    seen = np.zeros_like(grid)
    found = []
    for gy in range(gh):
        for gx in range(gw):
            if not grid[gy, gx] or seen[gy, gx]:
                continue
            stack, comp = [(gx, gy)], []
            seen[gy, gx] = True
            while stack:
                x, y = stack.pop()
                comp.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < gw and 0 <= ny < gh and grid[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((nx, ny))
            touches = any(x in (0, gw - 1) or y in (0, gh - 1) for x, y in comp)
            if not touches and len(comp) <= 12:
                found.append(comp)
    if found:
        x, y = found[0][0]
        return [F("dark", f"{len(found)} patch(es) of pure black inside the map, the first of {len(found[0])} block(s) at ({x * 16},{y * 16})", box=(x * 16, y * 16, 16, 16))]
    return []


# ---------------------------------------------------------------------------------------------------------------- sprites
SIZES = {0: [(8, 8), (16, 16), (32, 32), (64, 64)], 1: [(16, 8), (32, 8), (32, 16), (64, 32)], 2: [(8, 16), (8, 32), (16, 32), (32, 64)]}


def _oam(d):
    import struct
    out = []
    for k in range(128):
        a0, a1, a2 = struct.unpack_from("<HHH", d.oam, 8 * k)
        mode = a0 >> 8 & 3
        if mode == 2:
            continue
        shape, size = a0 >> 14 & 3, a1 >> 14 & 3
        w, h = SIZES.get(shape, SIZES[0])[size]
        x = a1 & 0x1FF
        x -= 512 if x >= 256 else 0
        y = a0 & 0xFF
        y -= 256 if y >= 160 else 0
        out.append({"i": k, "x": x, "y": y, "w": w, "h": h, "tile": a2 & 0x3FF, "pal": a2 >> 12, "prio": a2 >> 10 & 3, "rot": mode in (1, 3), "dbl": mode == 3,
                    "bpp8": bool(a0 >> 13 & 1), "gfx": a0 >> 10 & 3, "a0": a0, "a1": a1, "a2": a2})
    return out


def _sprite_pixels(d, sp):
    """The sprite's w x h colour indices (1D or 2D mapping per DISPCNT; flips ignored) as an array."""
    dc = d.dispcnt()
    tiles_w, tiles_h = sp["w"] // 8, sp["h"] // 8
    out = np.zeros((sp["h"], sp["w"]), dtype=np.int16)
    base = 0x10000
    for ty in range(tiles_h):
        for tx in range(tiles_w):
            t = sp["tile"] + (ty * tiles_w + tx if dc["obj_1d"] else ty * 32 + tx)
            off = base + 32 * (t & 0x3FF)
            b = d.vram[off:off + 32] if off + 32 <= len(d.vram) else bytes(32)
            if len(b) < 32:
                continue
            for y in range(8):
                for x in range(4):
                    v = b[4 * y + x]
                    out[ty * 8 + y, tx * 8 + 2 * x] = v & 15
                    out[ty * 8 + y, tx * 8 + 2 * x + 1] = v >> 4
    return out


def sprites(s):
    d = s.dump
    if d is None or not d.dispcnt()["obj_on"]:
        return []
    out = []
    sp = _oam(d)
    # an uninitialised entry: attr0..2 all zero draws tile 0 (8 x 8, palette 0) in the top-left corner
    zero = [e for e in sp if e["a0"] == 0 and e["a1"] == 0 and e["a2"] == 0]
    if zero and not (s.tags & {"fade"}):
        px = _sprite_pixels(d, zero[0])
        if px.any():
            out.append(F("sprites", f"{len(zero)} all-zero OAM entr{'y' if len(zero) == 1 else 'ies'} drawing tile 0 at the top-left corner", box=(0, 0, 8, 8)))
    # scanline budget: 1210 cycles; a w-wide sprite costs w, rotated 2 w + 10; a line over budget drops the later sprites
    cyc = np.zeros(160, dtype=int)
    for e in sp:
        w, h = e["w"] * (2 if e["dbl"] else 1), e["h"] * (2 if e["dbl"] else 1)
        cost = (2 * e["w"] + 10) if e["rot"] else e["w"]
        if e["x"] + w <= 0 or e["x"] >= 240:
            continue
        for y in range(max(0, e["y"]), min(160, e["y"] + h)):
            cyc[y] += cost
    if cyc.max() > CYCLES_PER_LINE:
        y = int(cyc.argmax())
        out.append(F("sprites", f"scanline {y} needs {cyc.max()} OBJ cycles (budget {CYCLES_PER_LINE}): sprites are dropped there", box=(0, y, 240, 1)))
    return out


# ---------------------------------------------------------------------------------------------------------------- palette
def _bank_chroma(d, bank, obj):
    cols = [d.colour(16 * bank + i, obj) for i in range(1, 16)]
    return [max(c) - min(c) for c in cols], cols


def used_banks(d):
    """(BG banks drawn with, OBJ banks drawn with) from the visible tile maps and sprites: {bank: first (what, where)}."""
    dc = d.dispcnt()
    bg, ob = {}, {}
    if dc["mode"] == 0:
        for i in range(4):
            if not dc["bg_on"][i]:
                continue
            c = d.bgcnt(i)
            if c["bpp8"]:
                continue
            cells = d.bg_cells(i)
            for py in range(0, 160, 8):
                for px in range(0, 240, 8):
                    x, y = (px + c["hofs"]) & 255, (py + c["vofs"]) & 255
                    t, hf, vf, pb = cells[(y // 8) * 32 + x // 8]
                    if t == 0 and pb == 0:
                        continue
                    # a cell whose tile is all transparent draws nothing
                    base = c["char_base"] + 32 * t
                    if not any(d.vram[base:base + 32]):
                        continue
                    bg.setdefault(pb, (f"BG{i}", (px, py)))
    if dc["obj_on"]:
        for e in _oam(d):
            if e["bpp8"] or e["x"] + e["w"] <= 0 or e["x"] >= 240 or e["y"] + e["h"] <= 0 or e["y"] >= 160 or e["gfx"] == 2:
                continue
            ob.setdefault(e["pal"], (f"OAM{e['i']}", (e["x"], e["y"])))
    return bg, ob


def _rect_banks(d, rect, bgs=(0, 1, 2, 3)):
    """Palette banks of the non-blank BG cells and OBJ sprites touching `rect` = (x, y, w, h): {("BG"|"OBJ", bank): (what, (x, y))}."""
    x0, y0, w, h = rect
    out = {}
    dc = d.dispcnt()
    for i in bgs:
        if not dc["bg_on"][i] or d.bgcnt(i)["bpp8"]:
            continue
        c = d.bgcnt(i)
        cells = d.bg_cells(i)
        for py in range(y0, y0 + h, 8):
            for px in range(x0, x0 + w, 8):
                x, y = (px + c["hofs"]) & 255, (py + c["vofs"]) & 255
                t, hf, vf, pb = cells[(y // 8) * 32 + x // 8]
                base = c["char_base"] + 32 * t
                if any(d.vram[base:base + 32]):
                    out.setdefault(("BG", pb), (f"BG{i}", (px, py)))
    if dc["obj_on"]:
        for e in _oam(d):
            if e["bpp8"] or e["gfx"] == 2 or e["x"] + e["w"] <= x0 or e["x"] >= x0 + w or e["y"] + e["h"] <= y0 or e["y"] >= y0 + h:
                continue
            out.setdefault(("OBJ", e["pal"]), (f"OAM{e['i']}", (e["x"], e["y"])))
    return out


def _grey(d, bank, obj):
    """A palette bank that is a plain grey ramp: at least GREY_BANK_ENTRIES of its 15 colours grey, four or more of them not black (an all-black bank is a faded or
    not yet loaded bank, not a washed-out picture)."""
    chroma, cols = _bank_chroma(d, bank, obj)
    bright = sum(1 for c in cols if sum(c) > 120)
    grey = sum(1 for c in chroma if c < GREY_CHROMA)
    return grey >= GREY_BANK_ENTRIES and bright >= 4 and max(chroma) < 2 * GREY_CHROMA


def _washed(d, bank, obj):
    """A bank that has lost its colours: a grey ramp, or a one-hue ramp (six or more tinted entries within 8 degrees of one hue: the moved-unit grey of an army is bluish, greenish or yellowish).
    Real faces measured 11 to 24 degrees apart (skin, hair, eyes, clothes)."""
    import colorsys
    import math
    if _grey(d, bank, obj):
        return "a grey ramp"
    hs = []
    for r, g, b in (d.colour(16 * bank + i, obj) for i in range(1, 16)):
        h, sat, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if sat > 0.15 and v > 0.2:
            hs.append(math.radians(h * 360))
    if len(hs) >= 6:
        c, sn = sum(math.cos(h) for h in hs) / len(hs), sum(math.sin(h) for h in hs) / len(hs)
        R = max(math.hypot(c, sn), 1e-9)
        if math.degrees(math.sqrt(-2 * math.log(R))) < WASHED_HUE_SPREAD:
            return "a one-hue ramp"
    return None


def palette(s):
    """Washed-out palettes where colour must be: the faces of a dialogue box (the box's left end) and the map's unit layer (BG1, banks 8..15)."""
    d = s.dump
    if d is None or s.tags & {"fade", "blank_ok"}:
        return []
    out = []
    if s.tags & {"dialogue", "dialogue_box", "story"}:
        for (y0, y1) in _boxes(s.arr):
            for (kind, b), (what, at) in _rect_banks(d, (0, y0, 48, y1 - y0)).items():
                why = _washed(d, b, kind == "OBJ")
                if why and not (kind, b) in s.meta.get("grey_ok", ()):
                    out.append(F("palette", f"{kind} palette bank {b} drawing the face in the dialogue box is {why} ({what} at {at}): a washed-out face", box=(0, y0, 48, y1 - y0)))
    if "map" in s.tags and not s.tags & {"moved", "setup"}:
        dc = d.dispcnt()
        if dc["bg_on"][1]:
            for (kind, b), (what, at) in _rect_banks(d, (0, 0, 240, 160), bgs=(1,)).items():
                if kind == "BG" and 8 <= b <= 15 and _grey(d, b, False):
                    out.append(F("palette", f"unit layer palette bank {b} is a grey ramp where units show ({at}): units drawn in the moved-unit grey", box=(at[0], at[1], 16, 16)))
    return out


# banks that are grey on purpose, by screen kind (set from the first sweep; the report lists every grey bank it saw with where, so a new one is a decision not a guess)
GREY_OK_BG = set()
GREY_OK_OBJ = set()


# ---------------------------------------------------------------------------------------------------------------- text
def _boxes(arr):
    """Dialogue / message boxes: horizontal bands where most pixels are near-white (a box's inside), the box's own frame lines (up to 4 rows) allowed inside: [(y0, y1)] of 24 rows or more."""
    near = (arr.min(axis=2) >= 225)
    frac = near.mean(axis=1)
    bands, y, H = [], 0, len(frac)
    while y < H:
        if frac[y] >= 0.45:
            y0, last, gap = y, y, 0
            while y < H and gap <= 4:
                if frac[y] >= 0.30:
                    last, gap = y, 0
                else:
                    gap += 1
                y += 1
            if last + 1 - y0 >= 24:
                bands.append((y0, last + 1))
        else:
            y += 1
    return bands


def _read_cells(m):
    """Glyph cells of a binary ink mask: [(x0, x1, y0, y1)] of connected column runs per text line, and which match a glyph of the game's font."""
    ocr_t = ocr._T
    if ocr_t is None:
        ocr._T = ocr._templates()
        ocr_t = ocr._T
    H, W = m.shape
    rows = m.any(axis=1)
    lines, y = [], 0
    while y < H:
        if not rows[y]:
            y += 1
            continue
        y0 = y
        while y < H and rows[y]:
            y += 1
        if 4 <= y - y0 <= 17:
            lines.append((y0, y))
    res = []
    for y0, y1 in lines:
        band = m[y0:min(H, y1 + 1)]
        cols = band.any(axis=0)
        x = 0
        text = ""
        unknown = []
        last = None
        while x < W:
            if not cols[x]:
                x += 1
                continue
            x0 = x
            while x < W and cols[x]:
                x += 1
            if last is not None and x0 - last >= 4:
                text += " "
            last = x
            cell = band[:, x0:x]
            ys = np.where(cell.any(axis=1))[0]
            cell = cell[ys.min():ys.max() + 1]
            best, bs = "?", 1.0
            for ch, tm, _t in ocr_t:
                if tm.shape != cell.shape:
                    continue
                dd = float((tm != cell).mean())
                if dd < bs:
                    best, bs = ch, dd
            if bs > 0.12:
                best = "?"
                rows_n = cell.sum(axis=1)
                arrow = 5 <= x - x0 <= 10 and len(rows_n) <= 8 and rows_n[0] > rows_n[-1] and all(rows_n[k] >= rows_n[k + 1] for k in range(len(rows_n) - 1))
                typing = (x - x0) <= 2 and x >= W - 1 or (x - x0) <= 2 and not cols[x:x + 12].any()      # (a glyph still being typed in: its first columns, at the end of the line)
                if arrow or typing:
                    best = "~"
                else:
                    unknown.append((x0, y0, x - x0))
            text += best
        res.append((y0, text, unknown))
    return res


def text(s):
    """Dialogue box text: glyph cells that match none of the game's glyphs."""
    # (the screens whose boxes are dialogue and message boxes; menus, lists and pages lay their text out in bands of their own, black on white too)
    if not (s.tags & {"dialogue", "dialogue_box", "story", "capture", "battle", "scene", "power", "first_box"}) or s.tags & {"fade", "title", "worldmap_art", "copage", "menu", "worldmap", "online", "map"}:       # ("map": the plain map, whose HUD panel is a pale box too)
        return []
    a = s.arr
    out = []
    for (y0, y1) in _boxes(a):
        if y0 > 12 and y1 < 150:          # a dialogue box stands at the top or the bottom of the screen
            continue
        x0 = 8
        # a face fills the box's left end: skip it
        left = a[y0 + 4:y1 - 4, 4:46]
        if (left.min(axis=2) < 200).mean() > 0.18:
            x0 = 50
        sub = a[y0 + 3:y1 - 3, x0:232]
        ink = (np.abs(sub - np.array([0, 0, 0])).max(axis=2) < 36)
        for ly, line, unk in _read_cells(ink):
            if unk:
                ux, uy, uw = unk[0]
                out.append(F("text", f"{len(unk)} garbled glyph cell(s) in the box text {line.strip()!r} (first at ({x0 + ux},{y0 + 3 + uy}), {uw} px wide)", box=(x0 + ux - 1, y0 + 3 + uy - 2, uw + 2, 13)))
                break
    return out


# ---------------------------------------------------------------------------------------------------------------- leftover
def leftover(s):
    """Detail blocks kept from the previous picture when the screen changed completely."""
    p = s.prev
    if p is None or s.tags & {"fade", "blank_ok", "scene", "power", "capture", "map", "battle"} or not (s.tags & {"menu", "worldmap"}) or p.img.size != s.img.size:
        return []
    a, b = s.arr, p.arr
    H, W = a.shape[:2]
    diff = (np.abs(a - b).max(axis=2) > 24)
    if diff.mean() < 0.55:
        return []
    keep = []
    for by in range(0, H - 15, 16):
        for bx in range(0, W - 15, 16):
            blk = a[by:by + 16, bx:bx + 16]
            if diff[by:by + 16, bx:bx + 16].mean() > 0.01:
                continue
            if len(np.unique(blk.reshape(-1, 3), axis=0)) >= 6:
                keep.append((bx, by))
    # a cluster of three or more touching blocks
    ks = set(keep)
    for bx, by in keep:
        n = sum(1 for dx, dy in ((16, 0), (0, 16), (16, 16), (-16, 0), (0, -16)) if (bx + dx, by + dy) in ks)
        if n >= 2:
            return [F("leftover", f"{len(keep)} detailed 16 x 16 blocks are identical to the previous picture ({s.prev.name}) while {diff.mean():.0%} of the rest changed, first at ({bx},{by})", "warn", box=(bx, by, 16, 16))]
    return []


# ---------------------------------------------------------------------------------------------------------------- seams (tilt)
def seams(s):
    """Thin lines across the tilted picture: a row or column whose pixels all differ strongly from BOTH neighbours by one dark or bright line."""
    if not s.tilted or s.tags & {"fade", "blank_ok", "menu", "dialogue", "dialogue_box", "copage", "scene", "power", "title", "story"}:
        return []
    a = s.arr.sum(axis=2) / 3.0
    H, W = a.shape
    out = []
    # horizontal 1 px seams inside the map plane (rows 24..120), measured against the rows above and below
    for y in range(24, min(H - 2, 120)):
        d1, d2 = a[y] - a[y - 1], a[y] - a[y + 1]
        same = np.abs(a[y - 1] - a[y + 1]) < 24            # (a line, not an edge or a band: the rows either side agree)
        dark = ((d1 < -60) & (d2 < -60) & same).mean()
        bright = ((d1 > 60) & (d2 > 60) & same).mean()
        if dark > 0.55 or bright > 0.55:
            out.append(F("seams", f"a 1 px {'dark' if dark > bright else 'bright'} line across {max(dark, bright):.0%} of row {y}", box=(0, y, W, 1)))
            break
    return out


# ---------------------------------------------------------------------------------------------------------------- facts (from the scene)
def facts(s):
    return []


DETECTORS = {"blank": blank, "stripes": stripes, "dark": dark, "sprites": sprites, "palette": palette, "text": text, "leftover": leftover, "seams": seams}


def judge(shot, only=None):
    out = []
    for name, fn in DETECTORS.items():
        if only and name not in only:
            continue
        try:
            out += fn(shot)
        except Exception as ex:      # noqa: BLE001 - a detector that crashes is itself a finding, never a silent pass
            out.append(F(name, f"the detector crashed: {type(ex).__name__}: {ex}", "warn"))
    return out
