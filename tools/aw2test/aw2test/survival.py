"""Dual Strike's Survival (tangoAW2's survival.rs) for the tests: the maps and
runs read straight from the .nds (independently of the Rust conversion), and
driving the mode from Select Mode through its War Room screens.

Dual Strike (USA), overlay 0 at 0x022AD560: map records of 0xA0 bytes at
0x022DBDB0 (DS map id n at index n - 1), the three runs' lists of eleven
u16 ids (Time 0x022F64FC, Money 0x022F652C, Turn 0x022F6514), the text table
0x02306954; arm9: the budgets at 0x02168D04.
"""

import struct

from . import paths
from . import rom as romlib
from .rom import DS_OVERLAY0_BASE, DualStrike, lz10

# The structures' pictures in AW2 (Dual Strike's bmap files are the same bytes).
STRUCTURE_PICTURES = {"0a5": 0x080D2DA8, "0a6": 0x080D38AC}

# survival.rs's RAM
STATE = 0x0203FA00
ON, KIND, STAGE, PHASE = STATE, STATE + 1, STATE + 2, STATE + 3
LEFT, BUDGET, POINTS, FRAMES = STATE + 4, STATE + 8, STATE + 0x0C, STATE + 0x10
CO, MENU_PICKED, BONUS, RANK = STATE + 0x18, STATE + 0x19, STATE + 0x1C, STATE + 0x20
CHOOSING, BETWEEN, PLAYING, CLEARED, LOST = range(5)
PROFILE_RECORDS = 0x0200C435
RECORD_MAGIC = 0xD5

# Kinds in Dual Strike's order (its kind byte), and their list order.
TIME, MONEY, TURN = 0, 1, 2
LIST_ORDER = (MONEY, TURN, TIME)
NAMES = {TIME: "Time Survival", MONEY: "Money Survival", TURN: "Turn Survival"}
ENTRY_IDS = {MONEY: 0xC9, TURN: 0xCA, TIME: 0xCB}
MAPS_FROM = 0xCC

SELECT_MODE_CURSOR = 0x0300591C
SURVIVAL_POSITION = 6
SELECT_MAP_PROC = 0x08616C54
CO_SCREEN_PROC = 0x086165C0
PROCS = (0x0200D610, 0x0200E418)
MAIN_CALLBACK = 0x03000000
MAP_CALLBACK = 0x08022049
DAY = 0x03004080
BIOME = 0x03004493
WEATHER_MODE = 0x03003FED
WEATHER_DEFAULT = 0x03003FEF
LIST_IDS = 0x02027F78
LIST_LAST = 0x02027FAB

MAPS = 0x022DBDB0
TEXT = 0x02306954
LISTS = {TIME: 0x022F64FC, MONEY: 0x022F652C, TURN: 0x022F6514}
BUDGETS = 0x02168D04


def convert_tile(t):
    if t in (0x146, 0x147):
        return 0x022          # Dual Strike's other mountains: AW2's mountain
    if t == 0x1A1:
        return 0x192          # Black Crystal (obelisk.rs)
    if 0x1B9 <= t <= 0x1BD:
        return t - 0x1B9 + 0x1D9  # Com Tower: the Lab tiles (com_tower.rs)
    return t


def convert_unit(t):
    return {25: 26, 26: 27}.get(t, t)


class Survival:
    """Dual Strike's Survival data, read from the .nds."""

    def __init__(self):
        ds = DualStrike(paths.ds_rom())
        self.ov0, self.arm9 = ds.ov0, ds.arm9

    def u8(self, a):
        return self.ov0[a - DS_OVERLAY0_BASE]

    def u16(self, a):
        return struct.unpack_from("<H", self.ov0, a - DS_OVERLAY0_BASE)[0]

    def u32(self, a):
        return struct.unpack_from("<I", self.ov0, a - DS_OVERLAY0_BASE)[0]

    def text(self, i):
        o = self.u32(TEXT + 4 * i) - DS_OVERLAY0_BASE
        return self.ov0[o:self.ov0.index(b"\0", o)].decode("latin1")

    def run(self, kind):
        return [self.u16(LISTS[kind] + 2 * k) for k in range(11)]

    def budget(self, kind):
        return struct.unpack_from("<I", self.arm9, BUDGETS - 0x02000000 + 4 * kind)[0]

    def all_ids(self):
        return sorted({i for k in (TIME, MONEY, TURN) for i in self.run(k)})

    def map(self, ds_id):
        e = MAPS + 0xA0 * (ds_id - 1)
        tiles_at = self.u32(e + 0x5C) - DS_OVERLAY0_BASE
        raw = lz10(self.ov0[tiles_at:tiles_at + 0x2000])
        w, h = raw[0], raw[1]
        tiles = [convert_tile(struct.unpack_from("<H", raw, 2 + 2 * k)[0]) for k in range(w * h)]
        units, army = [], 0
        p = self.u32(e + 0x64) - DS_OVERLAY0_BASE
        while self.ov0[p] != 0xFF:
            r = self.ov0[p:p + 13]
            if r[0] == 0xFE:
                army = r[1]
            else:
                units.append((army, r[0], r[1], convert_unit(r[2])))
            p += 13
        return {
            "name": self.text(self.u16(e + 0x2C)), "w": w, "h": h, "tiles": tiles, "units": units,
            "armies": self.u8(e + 0x3C), "colours": [self.u8(e + k) for k in range(1, 5)],
            "look": self.u8(e + 0x32), "weather": self.u8(e + 0x33), "fog": self.u8(e + 0x34),
            "cos": (self.u8(e + 0x70), self.u8(e + 0x72)),
            "structure": self.structure_file(e),
        }

    def structure_file(self, e):
        """The bmap file of the map's 4x4 structure's picture (header +0x24)."""
        p = self.u32(e + 0x24)
        if p == 0:
            return None
        o = p - DS_OVERLAY0_BASE
        return self.ov0[o:self.ov0.index(b"\0", o)].decode()

    def map_id(self, kind, stage):
        """tangoAW2's map id of a run's map `stage`."""
        if stage == 0:
            return ENTRY_IDS[kind]
        return MAPS_FROM + self.all_ids().index(self.run(kind)[stage])


def running(e, script):
    lo, hi = PROCS
    b = e.read(lo, hi - lo)
    return any(struct.unpack_from("<I", b, o)[0] == script for o in range(0, len(b), 0x6C))


def state(e):
    b = e.read(STATE, 0x24)
    u = lambda o: struct.unpack_from("<I", b, o)[0]
    return {"on": b[0], "kind": b[1], "stage": b[2], "phase": b[3], "left": u(4), "budget": u(8),
            "points": u(0x0C), "time": u(0x10), "co": b[0x18], "bonus": u(0x1C), "rank": b[0x20]}


def to_select_mode(e):
    e.wait(700)
    e.press("START", 8)
    e.wait(300)
    e.press("A", 8)
    e.wait(150)


def wheel_to(e, position, tries=10):
    for _ in range(tries):
        if e.u8(SELECT_MODE_CURSOR) == position:
            return True
        e.press("UP", 8)
        e.wait(60)
    return e.u8(SELECT_MODE_CURSOR) == position


def open_survival(e):
    """Select Mode -> Survival: its SELECT MAP. True once the list is up."""
    to_select_mode(e)
    if not wheel_to(e, SURVIVAL_POSITION):
        return False
    e.press("A", 8)
    if not e.wait_until(lambda: running(e, SELECT_MAP_PROC), 600, step=10):
        return False
    e.wait(90)  # the list slides in before it takes the pad
    return True


def listed(e):
    """The ids SELECT MAP lists now."""
    n = e.u8(LIST_LAST) + 1
    return list(e.read(LIST_IDS, n))


def battle_up(e):
    return e.u32(MAIN_CALLBACK) == MAP_CALLBACK and e.u8(PHASE) == PLAYING


def pick(e, row, co_steps=0):
    """Pick list row `row` (from the top), then (on a run's first map) the CO
    screen's CO, `co_steps` down its list: the battle starts. True once the
    battle map is up. From the second map on the screen offers the run's CO
    only."""
    for _ in range(row):
        e.press("DOWN", 8)
        e.wait(30)
    e.press("A", 8)
    for _ in range(60):
        if battle_up(e):
            return True
        if running(e, CO_SCREEN_PROC):
            e.wait(60)
            for _ in range(co_steps):
                e.press("DOWN", 8)
                e.wait(30)
            e.press("A", 8)
            e.wait(100)
            e.press("A", 8)
            break
        e.wait(10)
    return e.wait_until(lambda: battle_up(e), 1500, step=20)


def to_select_map(e, max_steps=80):
    """Press A through the results, the War Room's saving and back to SELECT
    MAP."""
    for _ in range(max_steps):
        if running(e, SELECT_MAP_PROC):
            e.wait(60)
            return True
        e.press("A", 8)
        e.wait(30)
    return False


def records(e):
    """The three kinds' records in the profile: {kind: (rank, co, left)}."""
    b = e.read(PROFILE_RECORDS, 10)
    if b[0] != RECORD_MAGIC:
        return {}
    unit = {TIME: 60, MONEY: 100, TURN: 1}
    out = {}
    for k in (TIME, MONEY, TURN):
        v = b[1 + 3 * k] | b[2 + 3 * k] << 8 | b[3 + 3 * k] << 16
        if v & 7:
            out[k] = (v & 7, (v >> 3) & 0x7F, (v >> 10) * unit[k])
    return out


# --- SELECT MAP in Dual Strike's look (survival_ui.rs) ---------------------------------

UI = STATE + 0x26
SHOWN, BROWSE, RECORDS = UI, UI + 1, UI + 2
SELECT_MAP_IDLE = 0x08085F91
BG0CNT = 0x04000008
PAL_RAM = 0x05000000
FONT_GLYPHS, FONT_WIDTHS = 0x084C32E4, 0x084C36E4
# Where survival_ui.rs puts things (screen pixels).
PANEL_ROW1, PANEL_ROW2 = 52, 65
VALUE_RIGHT = 224
LABEL_X = 108
BANNER = (56, 34)

_aw2 = None


def aw2_image():
    global _aw2
    if _aw2 is None:
        _aw2 = romlib.Image.load()
    return _aw2


def bg0(e):
    """The picture on BG0 as game_rgb[y][x] (240x160), from VRAM and palette RAM
    as the PPU reads them (tile 0 clear is never used by the picture)."""
    cnt = e.u16(BG0CNT)
    chars = 0x06000000 + 0x4000 * ((cnt >> 2) & 3)
    screen = 0x06000000 + 0x800 * ((cnt >> 8) & 31)
    tiles = e.read(chars, 0x4000)
    smap = e.read(screen, 0x800)
    pal = e.read(PAL_RAM, 0x40)
    colours = []
    for k in range(32):
        c = struct.unpack_from("<H", pal, 2 * k)[0]
        colours.append((((c & 31) << 3) | ((c & 31) >> 2), (((c >> 5) & 31) << 3) | (((c >> 5) & 31) >> 2),
                        (((c >> 10) & 31) << 3) | (((c >> 10) & 31) >> 2)))
    img = [[None] * 240 for _ in range(160)]
    for ty in range(20):
        for tx in range(30):
            ent = struct.unpack_from("<H", smap, 2 * (32 * ty + tx))[0]
            t, bank = ent & 0x3FF, ent >> 12
            for y in range(8):
                for x in range(8):
                    v = (tiles[32 * t + 4 * y + x // 2] >> (4 * (x & 1))) & 15
                    img[8 * ty + y][8 * tx + x] = colours[16 * bank + v]
    return img


def dark(px):
    """AW2's text ink (and the title's black outline) on the picture."""
    return sum(px) < 150


def font_ink(s, x, y):
    """The pixels AW2's proportional font inks for `s` at (x, y) (value 0xA of
    its 4bpp glyphs, 11 rows from the glyph's third): survival_ui's Canvas::text."""
    img = aw2_image()
    px = set()
    for ch in s.encode():
        w = img.u8(FONT_WIDTHS + ch)
        at = img.u32(FONT_GLYPHS + 4 * ch)
        stride = (w + 1) // 2
        for r in range(11):
            for cx in range(w):
                b = img.data[at - 0x08000000 + stride * (3 + r) + cx // 2]
                if (b >> (4 * (cx & 1))) & 15 == 0xA:
                    px.add((x + cx, y + r))
        x += w + 1
    return px


def text_width(s):
    img = aw2_image()
    return sum(img.u8(FONT_WIDTHS + c) + 1 for c in s.encode()) - 1


def text_on(shot, s, x, y, need=0.97):
    """Whether `s` is on the picture at (x, y): every inked pixel dark."""
    ink = font_ink(s, x, y)
    if not ink:
        return False
    got = sum(1 for (px, py) in ink if 0 <= px < 240 and 0 <= py < 160 and dark(shot[py][px]))
    return got >= need * len(ink)


def text_right(shot, s, right, y, need=0.97):
    return text_on(shot, s, right - text_width(s), y, need)


def words(ds=None):
    """Dual Strike's survival wording: the strings at 0x0230E718 in overlay 0."""
    ds = ds or DualStrike(paths.ds_rom())
    o = 0x0230E718 - DS_OVERLAY0_BASE
    chunk = ds.ov0[o:o + 0xA0]
    out = []
    for part in chunk.split(b"\0"):
        t = bytes(c for c in part if 0x20 <= c < 0x7F).decode()
        if len(t) >= 2:
            out.append(t)
    return out


def title_font(ds=None):
    """res_modefont: 28 glyphs of 16x32 (A..Z, the star, the dash) as
    {(x, y): colour index} of the non-clear pixels."""
    ds = ds or DualStrike(paths.ds_rom())
    d = ds.file("ohashi/res_modefont")
    out = []
    for g in range(28):
        px = {}
        for t in range(8):
            for y in range(8):
                for x in range(8):
                    v = (d[(8 * g + t) * 32 + 4 * y + x // 2] >> (4 * (x & 1))) & 15
                    if v:
                        px[(8 * (t % 2) + x, 8 * (t // 2) + y)] = v
        out.append(px)
    return out


def title_pixels(text, glyphs, top=1):
    """Where the title `text` ('MONEY*SURVIVAL') draws its pixels: {(x, y): the
    font's colour index}, a later glyph over an earlier one, centred, its first
    row at `top`; glyphs share one column each with the next, the rows trimmed to
    the font's extent (survival_ui.rs's Art::title)."""
    gl = [glyphs[26 if c in "* " else 27 if c == "-" else ord(c) - 65] for c in text]
    rows = [y for g in glyphs for (_, y) in g]
    y0 = min(rows)
    spans = [(min(x for x, _ in g), max(x for x, _ in g)) for g in gl]
    total = sum(r - l for l, r in spans) + 1
    x = (240 - total) // 2
    out = {}
    for g, (l, r) in zip(gl, spans):
        for (gx, gy), v in g.items():
            out[(x + gx - l, top + gy - y0)] = v
        x += r - l
    return out


def title_blue(text, glyphs, ds=None):
    """The pixels of the title that are blue (not the white outline): the
    font's colours whose blue exceeds their red by 60 or more."""
    ds = ds or DualStrike(paths.ds_rom())
    raw = ds.files["ohashi/res_modefont"]
    pal = []
    for k in range(16):
        c = struct.unpack_from("<H", raw, len(raw) - 64 + 2 * k)[0]
        pal.append((((c & 31) << 3), ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3))
    return {xy for xy, v in title_pixels(text, glyphs).items() if pal[v][2] - pal[v][0] >= 60}


def blue_pixels(shot, rows=range(0, 32)):
    return {(x, y) for y in rows for x in range(240) if shot[y][x][2] - shot[y][x][0] >= 60}


def banner_dark(ds=None):
    """The 'BASIC COURSE' banner's dark pixels (128x16) from res_survival's
    first stream and its palette: pixels whose colour is dark."""
    ds = ds or DualStrike(paths.ds_rom())
    d = ds.file("ohashi/res_survival")
    raw = ds.files["ohashi/res_survival"]
    pal = []
    for k in range(16):
        c = struct.unpack_from("<H", raw, len(raw) - 770 + 2 * k)[0]
        pal.append((((c & 31) << 3), ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3))
    out = set()
    for blk in range(4):
        for t in range(8):
            for y in range(8):
                for x in range(8):
                    v = (d[(blk * 8 + t) * 32 + 4 * y + x // 2] >> (4 * (x & 1))) & 15
                    if v and sum(pal[v]) < 200:
                        out.add((32 * blk + 8 * (t % 4) + x, 8 * (t // 4) + y))
    return out


def course_text(kind, budget_text, ds=None):
    """The three strings of a course's panel rows: (budget label, best label) in Dual Strike's words."""
    w = words(ds)
    return {MONEY: ("Funds", "Spent"), TURN: ("Turn total", "Turns used"), TIME: ("Total time", "Time used")}[kind]


# The budget on the battle map (survival_ui.rs's hud, as two_front's text is drawn):
HUD_TILES = [(0x1F9, 17), (0x2D2, 9), (0x2E4, 4), (0x2EC, 4), (0x2F4, 4), (0x2FC, 4), (0x309, 9)]
HUD_WHITE = 6
FONT_TOP, FONT_ROWS = 2, 14


def hud_white(e):
    """The white pixels of the budget's lines on the screen: {line top y: {(x, y)}}."""
    oam = e.read(0x07000000, 0x400)
    lines = {}
    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<HHH", oam, 8 * i)
        if (a0 >> 8) & 3 == 2 or (a0 >> 14) != 2:
            continue
        tile = a2 & 0x3FF
        if not any(lo <= tile < lo + n for lo, n in HUD_TILES):
            continue
        y, x = a0 & 0xFF, a1 & 0x1FF
        if y >= 32:
            continue
        data = e.read(0x06010000 + 32 * tile, 64)
        for row in range(16):
            for col in range(8):
                v = (data[32 * (row // 8) + 4 * (row % 8) + col // 2] >> (4 * (col & 1))) & 15
                if v == HUD_WHITE:
                    lines.setdefault(y, set()).add((x + col, y + row))
    return lines


def hud_expected(s, y):
    """The white pixels of `s` as the budget line at top `y` draws them: AW2's
    font rows FONT_TOP.. of each glyph, one blank column before and after,
    centred on x = 120 (two_front::outlined)."""
    img = aw2_image()
    cols = 1 + sum(img.u8(FONT_WIDTHS + c) + 1 for c in s.encode()) + 1
    x0 = 120 - cols // 2
    px = set()
    cx = 1
    for ch in s.encode():
        w = img.u8(FONT_WIDTHS + ch)
        at = img.u32(FONT_GLYPHS + 4 * ch)
        stride = (w + 1) // 2
        for c in range(w):
            for r in range(FONT_ROWS):
                b = img.data[at - 0x08000000 + stride * (FONT_TOP + r) + c // 2]
                if (b >> (4 * (c & 1))) & 15:
                    px.add((x0 + cx + c, y + r + 1))
        cx += w + 1
    return px


def clock(frames):
    s = frames // 60
    return f"{s // 60}:{s % 60:02d}"
