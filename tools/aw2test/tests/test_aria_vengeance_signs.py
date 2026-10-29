"""Aria's Vengeance signs, option E (crate::aria_sign, crate::ds_hud::native_sign): the HP number of her wounded units on the map in an orange-to-red ramp, the "Vengeance +NN%" strip on top of the unit
window, and the same strip above the enemy's damage forecast with the DAMAGE box lifted above it. Each is checked against a twin game that differs only in the CO (Andy for Aria: the same units, HP,
cursor and camera), so everything that should not change is compared pixel for pixel, and the strip's lettering against the mock-up's own composer (devkit/aw2/colib/vengeance_mockups.py).

`AW2TEST_VENGEANCE_REVIEW=<dir>` keeps the frames there for `devkit/aw2/colib/vengeance_signs_sheet.py` (the review sheets); `AW2TEST_VENGEANCE_UNIT` / `_ATTACKER` pick the unit shown (tank, megatank) as in
test_aria_vengeance_mockup.py. This is AW2's own battle screen (Dual Strike's map graphics off: with them on the host draws the map, the units and the numbers itself; the strip is the same
there, ds_hud.rs, and was looked at but is not compared pixel for pixel)."""

import os
import shutil
import struct
import sys

from PIL import Image

from aw2test.harness import test
from aw2test import coverify as cv

DEVKIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "devkit")
sys.path.insert(0, DEVKIT)
from aw2.colib import vengeance_mockups as mm  # noqa: E402

HPS = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]
ROW = 7
KIND = os.environ.get("AW2TEST_VENGEANCE_UNIT", "tank")
ATTACKER = os.environ.get("AW2TEST_VENGEANCE_ATTACKER", "tank")
REVIEW = os.environ.get("AW2TEST_VENGEANCE_REVIEW")
# (a Megatank's picture is animated, out of step between two games started apart: only the numbers and the icons' cells are compared for it)
STRICT = KIND == "tank"
ENV = dict(cv.ENV)
CAM = 0x0201_E450 + 4
RAMP = mm.RAMP
WHITE = (255, 255, 255)
OUTLINE = (0, 41, 0)
STRIP_H = 26
BG_PAL = 0x0500_0000
OAM = 0x0700_0000
T_BOX_FRAME = 442


def expand(c5):
    """5 bits to 8 as the console's picture does (31 -> 255, 5 -> 41)."""
    return c5 * 255 // 31


def ramp_rgb(shown):
    """The picture's colour of the ramp for displayed HP `shown`: the game keeps 5 bits a channel (the mock-up's 8-bit value >> 3) and the console shows them expanded."""
    return tuple(expand(c >> 3) for c in RAMP[shown])


def shown(hp):
    return (hp + 9) // 10


def scene(ctx, co, kind="tank", env=None):
    """Her Tanks at 10 down to 1 displayed HP in a row (the 6 HP one low on fuel, the 4 HP one without ammunition), an Oozium of hers at 3 HP, Andy's Tank at 5 HP, spare Recons for the units' redraw."""
    m = ctx.map()
    for k in range(len(HPS)):
        m.unit(1, kind, 2 + k, ROW)
    m.unit(1, "oozium", 13, ROW)
    m.unit(2, "tank", 3, ROW - 3)
    m.unit(1, "recon", 13, ROW + 5)
    m.unit(1, "recon", 14, ROW + 5)
    g = ctx.start(m, [co, "andy"], humans=(1,), env=env or ENV)
    for k, hp in enumerate(HPS):
        ctx.set_hp(g, 2 + k, ROW, hp)
    ctx.set_hp(g, 13, ROW, 30)
    ctx.set_hp(g, 3, ROW - 3, 50)
    from tests.test_crumb import set_unit
    set_unit(g, 6, ROW, fuel=5)
    set_unit(g, 8, ROW, ammo=0)
    g.e.wait(30)
    g.wait_unit(13, ROW + 5)
    g.e.wait(30)
    g.goto(2, ROW + 4)
    g.e.wait(40)
    return g


def cam(g):
    return g.e.u16(CAM), g.e.u16(CAM + 2)


def cell(g, x, y):
    """A map cell's top left on the screen."""
    cx, cy = cam(g)
    return 16 * x - cx, 16 * y - cy


def load(path):
    return Image.open(path).convert("RGB")


def diff(a, b, box=None):
    """The pixels (x, y) where two pictures differ."""
    x0, y0, x1, y1 = box or (0, 0, 240, 160)
    return [(x, y) for y in range(max(0, y0), min(160, y1)) for x in range(max(0, x0), min(240, x1)) if a.getpixel((x, y)) != b.getpixel((x, y))]


def bg1_entries(e):
    cnt = e.u16(0x0400_000A)
    sb = 0x0600_0000 + ((cnt >> 8) & 31) * 0x800
    return struct.unpack("<1024H", e.read(sb, 0x800))


def ours(e):
    """BG1 entries drawn from our eight digit tiles (BG tiles 0x340..0x347): {tile: [bank, ...]}."""
    out = {}
    for ent in bg1_entries(e):
        if 0x340 <= ent & 0x3FF <= 0x347:
            out.setdefault(ent & 0x3FF, []).append(ent >> 12)
    return out


def digit_box(g, x):
    """The HP number's 8 x 7 box in the cell of column x of the Tanks' row (the cell's lower right)."""
    cx, cy = cell(g, x, ROW)
    return cx + 8, cy + 5, cx + 16, cy + 12


@test(modes=("ds",))
def aria_vengeance_signs_map(ctx):
    """The HP numbers: 8 to 1 HP in the ramp, outline kept; 10 and 9 HP, the Oozium, Andy's Tank and the low fuel / ammunition icons as in the twin game; the game's palette back when nothing needs the ramp."""
    a = scene(ctx, "aria", KIND)
    base = scene(ctx, "andy", KIND)
    ia, ib = load(ctx.shot(a, "aria_map")), load(ctx.shot(base, "andy_map"))
    if REVIEW:
        os.makedirs(REVIEW, exist_ok=True)
        shutil.copy(os.path.join(ctx.out, "aria_map.bmp"), os.path.join(REVIEW, f"{KIND}_map_aria.bmp"))
        shutil.copy(os.path.join(ctx.out, "andy_map.bmp"), os.path.join(REVIEW, f"{KIND}_map_andy.bmp"))
        with open(os.path.join(REVIEW, f"{KIND}_map_box.txt"), "w") as fh:
            fh.write(" ".join(map(str, digit_box(a, 2) + digit_box(a, 11))))
    expect = set()
    for k, hp in enumerate(HPS):
        x, h = 2 + k, shown(hp)
        got = diff(ia, ib, digit_box(a, x))
        if 1 <= h <= 8:
            ctx.check(len(got) >= 6, f"{h} HP (column {x}): the digit changed colour ({len(got)} pixels)")
            bad = [p for p in got if ib.getpixel(p) != WHITE or ia.getpixel(p) != ramp_rgb(h)]
            ctx.check(not bad, f"{h} HP: the pixels that changed are the digit's own white, now {ramp_rgb(h)} (wrong: {[(p, ia.getpixel(p)) for p in bad[:3]]})")
            expect.update(got)
        elif STRICT or h == 9:
            ctx.check(not got, f"{h} HP (column {x}): the number is as it was")
    # the Oozium's number (3 HP, hers) stays white, the same in both (the Oozium itself wobbles, out of step between two games: its cell's picture is left out below)
    ctx.check(not diff(ia, ib, digit_box(a, 13)), "the Oozium's number is as it was")
    ox, oy = cell(a, 13, ROW)
    # everything else of the frame (Andy's 5, the black outline, the icons, the ground) is the twin's
    # (the CO panel and its power meter at the top left are Aria's in one game and Andy's in the other)
    stray = [p for p in diff(ia, ib) if p not in expect and not (p[0] < 80 and p[1] < 37) and not (ox - 4 <= p[0] < ox + 20 and oy - 8 <= p[1] < oy + 16)]
    ctx.check(not stray or not STRICT, f"nothing else of the frame changed ({len(stray)} pixels differ, e.g. {stray[:4]})")
    # the icons are there (AW2's low fuel on the 6 HP Tank, no ammunition on the 4 HP one: the cell's upper right) and untouched
    for x in (6, 8):
        cx, cy = cell(a, x, ROW)
        box = (cx + 8, cy - 3, cx + 16, cy + 5)
        n = sum(1 for yy in range(box[1], box[3]) for xx in range(box[0], box[2]) if not mm.is_ground(ib.getpixel((xx, yy))))
        ctx.check(n >= 12 and not diff(ia, ib, box), f"column {x}: the icon is there ({n} pixels) and as in the twin")
    # the tiles and the palette: our eight tiles, once each, in a bank whose colours 1..8 are the ramp
    used = ours(a.e)
    ctx.eq(sorted(used), list(range(0x340, 0x348)), "BG tiles 0x340..0x347 are in use, once for each HP 1..8")
    banks = {b for v in used.values() for b in v}
    ctx.eq(len(banks), 1, f"one palette bank holds the ramp (banks {banks})")
    bank = banks.pop()
    pal = struct.unpack("<16H", a.e.read(BG_PAL + 32 * bank, 32))
    for h in range(1, 9):
        r, g, b = RAMP[h]
        ctx.eq(pal[h], (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10), f"bank {bank} colour {h} is the ramp's for {h} HP")
    ctx.eq(pal[15], 0, "the outline colour is black")
    for h in (1, 4, 8):
        tile = a.e.read(0x0600_0000 + 32 * (0x340 + h - 1), 32)
        idx = sorted({c for byte in tile for c in (byte & 15, byte >> 4)})
        ctx.eq(idx, [0, h, 15], f"the {h} HP tile's pixels: clear, the digit in colour {h}, the outline in 15")
    # healed, the numbers and the game's own palette go back
    before = {b: base.e.read(BG_PAL + 32 * b, 32) for b in (4, 5, 6, 7, 9)}
    for k in range(len(HPS)):
        ctx.set_hp(a, 2 + k, ROW, 100)
    ctx.set_hp(a, 13, ROW, 100)
    a.select(14, ROW + 5)
    a.move_to(14, ROW + 5)
    a.choose("Wait", a.ACTION_MENU)
    a.wait_for_input()
    a.e.wait(40)
    ctx.eq(ours(a.e), {}, "healed: none of our tiles is left in the map")
    for b, was in before.items():
        ctx.check(a.e.read(BG_PAL + 32 * b, 32) == was, f"healed: palette bank {b} is the game's again")
    a.e.close()
    base.e.close()


def word_frames(ctx, out):
    """The unit window's own words (the mock-up's lettering: Recon, Bridge, Tank), from a game with no sign shown."""
    m = ctx.map()
    m.terrain(6, 6, "bridge").terrain(9, 6, "wood")
    m.unit(1, "recon", 6, 6).unit(1, "tank", 3, 6).unit(2, "tank", 20, 12)
    g = ctx.start(m, ["aria", "andy"], humans=(1,), env=ENV)
    os.makedirs(out, exist_ok=True)
    for name, c in (("recon_bridge", (6, 6)), ("wood", (9, 6)), ("tank_plain", (3, 6))):
        g.goto(*c)
        g.e.wait(40)
        g.e.shot(os.path.join(out, f"word_{name}"))
    g.e.close()


def ink(im, box):
    x0, y0, x1, y1 = box
    return {(x, y) for y in range(y0, y1) for x in range(x0, x1) if im.getpixel((x, y)) in (WHITE, OUTLINE)}


def no_strip(ia, ib):
    """No strip in the frame `ia` against its twin `ib`: the window is not lifted, no lettering was added over it (a wounded unit of hers on the map beside it has the ramp in its number, white in the twin: nothing
    else may differ in the window)."""
    wt = mm.window_top(ib)
    x0, x1 = mm.window_x(ib)
    rect = (x0, wt - STRIP_H, x1, wt)
    return mm.window_top(ia) == wt and not (ink(ia, rect) - ink(ib, rect)) and not diff(ia, ib, (x0, wt, x1, 160))


def window_frames(ctx, a, base, frames):
    """The frames of the cursor on each Tank of the row (HP 10 .. 1), on the Oozium and on Andy's Tank, in both games; `panel_hpN` (her window, N displayed HP) for the mock-up's digits."""
    os.makedirs(frames, exist_ok=True)
    stops = [(2 + k, ROW, shown(hp) if hp < 100 else 10) for k, hp in enumerate(HPS)] + [(13, ROW, "oozium"), (3, ROW - 3, "andy")]
    for x, y, tag in stops:
        for name, g in (("a", a), ("b", base)):
            g.goto(x, y)
            g.e.wait(40)
            g.e.shot(os.path.join(frames, f"{name}_{x}_{y}"))
            if name == "a" and isinstance(tag, int):
                g.e.shot(os.path.join(frames, f"panel_hp{tag}"))
    if REVIEW:
        os.makedirs(REVIEW, exist_ok=True)
        for x, y, tag in stops:
            for name in ("a", "b"):
                shutil.copy(os.path.join(frames, f"{name}_{x}_{y}.bmp"), os.path.join(REVIEW, f"{KIND}_win_{'aria' if name == 'a' else 'andy'}_{tag}.bmp"))


@test(modes=("ds",))
def aria_vengeance_signs_window(ctx):
    """The unit window: the strip (its fill, "Vengeance", "+NN%" in the window's lettering) on 8, 5, 2 and 1 HP, as wide as the window, exactly the mock-up's; none at 10 and 9 HP, on the Oozium, on Andy's Tank."""
    words = os.path.join(ctx.out, "words")
    word_frames(ctx, words)
    a = scene(ctx, "aria", KIND)
    base = scene(ctx, "andy", KIND)
    frames = os.path.join(ctx.out, "frames")
    window_frames(ctx, a, base, frames)
    for k, hp in enumerate(HPS):
        h = shown(hp) if hp < 100 else 10
        ia, ib = load(os.path.join(frames, f"a_{2 + k}_{ROW}.bmp")), load(os.path.join(frames, f"b_{2 + k}_{ROW}.bmp"))
        wt = mm.window_top(ib)
        x0, x1 = mm.window_x(ib)
        rect = (x0, wt - STRIP_H, x1, wt)
        if h > 8:
            ctx.check(no_strip(ia, ib), f"{h} HP: no strip, the window as in the twin game")
            continue
        pct = mm.VENGEANCE_PCT[h]
        want = mm.option_d(ib, words, pct, frames)
        got_ink, want_ink = ink(ia, rect), ink(want, rect)
        ctx.check(len(got_ink) > 150, f"{h} HP: the strip has its lettering ({len(got_ink)} pixels of ink)")
        ctx.check(got_ink == want_ink, f"{h} HP: the strip reads Vengeance +{pct}% as the mock-up's does ({len(got_ink ^ want_ink)} pixels differ)")
        # as wide as the window: a row through the strip is fill or lettering over the window's columns, and the ground beside them is untouched
        row = wt - 13
        strip_fill = {(139, 156, 32), (156, 156, 16), WHITE, OUTLINE}
        inside = [x for x in range(x0, x1) if ia.getpixel((x, row)) not in strip_fill]
        ctx.check(not inside, f"{h} HP: the strip fills the window's width ({len(inside)} columns of {x0}..{x1} are not its fill)")
        ctx.check(ia.getpixel((x0 - 1, row)) == ib.getpixel((x0 - 1, row)) and ia.getpixel((x1, row)) == ib.getpixel((x1, row)), f"{h} HP: nothing beside the strip changed")
        below = diff(ia, ib, (x0, wt, x1, 160))
        ctx.check(not below, f"{h} HP: the window under the strip is as it was ({len(below)} pixels differ)")
    for who, (x, y) in (("the Oozium", (13, ROW)), ("Andy's Tank", (3, ROW - 3))):
        ia, ib = load(os.path.join(frames, f"a_{x}_{y}.bmp")), load(os.path.join(frames, f"b_{x}_{y}.bmp"))
        wt = mm.window_top(ib)
        x0, x1 = mm.window_x(ib)
        ctx.check(no_strip(ia, ib), f"{who}: no strip, the window as in the twin")
    a.e.close()
    base.e.close()


def box_sprite(e):
    """(y, x) of the DAMAGE box's frame sprite (the 32 x 32 one of tile 442) in OAM."""
    oam = e.read(OAM, 0x400)
    for i in range(128):
        a0, a1, a2 = struct.unpack("<3H", oam[8 * i:8 * i + 6])
        if (a2 & 0x3FF) == T_BOX_FRAME and (a0 >> 8) & 3 != 2:
            return a0 & 0xFF, a1 & 0x1FF
    return None


def forecast_game(ctx, co, kind, attacker, targets):
    """Andy's `attacker`s fire at Aria's `kind`s (HP by column): {hp: (frame path, the box's sprite place, the game's own forecast %)}."""
    m = ctx.map()
    for x, _ in targets:
        m.unit(1, kind, x, ROW).unit(2, attacker, x, ROW + 1)
    g = ctx.start(m, [co, "andy"], humans=(1, 2), env=ENV)
    for x, hp in targets:
        ctx.set_hp(g, x, ROW, hp)
    g.end_turn(human=2)
    res = {}
    for x, hp in targets:
        g.select(x, ROW + 1)
        g.move_to(x, ROW + 1)
        g.choose("Fire", g.ACTION_MENU)
        g.e.wait(40)
        path = g.e.shot(os.path.join(ctx.out, f"{co}_fc_hp{shown(hp)}"))
        res[hp] = (path, box_sprite(g.e), ctx.battle_records(g)[0]["display"])
        for _ in range(3):
            g.e.press("B", 4)
            g.e.wait(10)
        g.wait_for_input()
    g.e.close()
    return res


@test(modes=("ds",))
def aria_vengeance_signs_forecast(ctx):
    """The enemy's forecast on her unit: the strip above the target's window (the mock-up's, that HP's number) and the DAMAGE box lifted by its height; 9 HP has neither; the forecast's % is the game's own, higher
    than the twin's where Vengeance applies."""
    words = os.path.join(ctx.out, "words")
    word_frames(ctx, words)
    targets = [(3, 80), (7, 50), (11, 20), (15, 10), (19, 90)]
    aria = forecast_game(ctx, "aria", KIND, ATTACKER, targets)
    andy = forecast_game(ctx, "andy", KIND, ATTACKER, targets)
    # (the digits of the mock-up's "+NN%": the window's own numbers, from a window frame of each HP)
    frames = os.path.join(ctx.out, "frames")
    os.makedirs(frames, exist_ok=True)
    w = scene(ctx, "aria", KIND)
    for k, hp in enumerate(HPS):
        w.goto(2 + k, ROW)
        w.e.wait(40)
        w.e.shot(os.path.join(frames, f"panel_hp{shown(hp) if hp < 100 else 10}"))
    w.e.close()
    for x, hp in targets:
        h = shown(hp)
        pa, ba, da = aria[hp]
        pb, bb, db = andy[hp]
        ia, ib = load(pa), load(pb)
        ctx.check(ba is not None and bb is not None, f"{h} HP: the DAMAGE box is up")
        wt = mm.window_top(ib)
        x0, x1 = mm.window_x(ib)
        rect = (x0, wt - STRIP_H, x1, wt)
        if h > 8:
            ctx.check(ba[1] == bb[1] and abs(ba[0] - bb[0]) <= 2, f"{h} HP: the DAMAGE box is where it always is ({ba} against the twin's {bb}: it bobs a pixel or two)")
            ctx.eq(mm.window_top(ia), wt, f"{h} HP: the window is not lifted by a strip")
            ctx.check(da < db, f"{h} HP: the game's forecast is {da}%: her flat 5% defence (the twin's Andy: {db}%)")
            continue
        pct = mm.VENGEANCE_PCT[h]
        want = mm.option_d(ib, words, pct, frames)
        got_ink, want_ink = ink(ia, rect), ink(want, rect)
        ctx.check(got_ink == want_ink and len(got_ink) > 150, f"{h} HP: the strip over the window reads Vengeance +{pct}% as the mock-up's ({len(got_ink ^ want_ink)} pixels differ)")
        ctx.check(abs((bb[0] - ba[0]) - STRIP_H) <= 2, f"{h} HP: the DAMAGE box is {STRIP_H} pixels higher than in the twin ({ba[0]} against {bb[0]}; it bobs a pixel or two)")
        ctx.eq(ba[1], bb[1], f"{h} HP: and in the same column")
        ctx.eq(mm.window_top(ia), wt - STRIP_H, f"{h} HP: the window is lifted by the strip's {STRIP_H} pixels")
        ctx.check(0 < da < db, f"{h} HP: the game's own forecast is {da}% against the twin Andy's {db}%: her defence counts")
        ctx.log(f"forecast on her {h} HP {KIND}: {da}% (twin {db}%)")
    if REVIEW:
        os.makedirs(REVIEW, exist_ok=True)
        for tag, res in (("aria", aria), ("andy", andy)):
            for hp, (p, _, _) in res.items():
                shutil.copy(p, os.path.join(REVIEW, f"{KIND}_fc_{tag}_{shown(hp)}.bmp"))


def components(pix, w, h, ok):
    """8-connected clusters of the pixels (x, y) with ok(colour) in a dict {(x, y): colour}: list of sets."""
    seen, out = set(), []
    for p in pix:
        if p in seen or not ok(pix[p]):
            continue
        stack, comp = [p], {p}
        seen.add(p)
        while stack:
            x, y = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in pix and q not in seen and ok(pix[q]):
                        seen.add(q)
                        comp.add(q)
                        stack.append(q)
        out.append(comp)
    return out


def tilt_lut(c5):
    """The tilt's 3D colour expansion of a 5-bit channel (ds_tilt rgba_lut_3d: 2c + 1 of 63, black 4)."""
    return (2 * c5 + 1) * 255 // 63 if c5 else 4


@test(modes=("ds",))
def aria_vengeance_signs_tilt(ctx):
    """Dual Strike's tilted map (host drawn, 4x): the HP numbers of her 8..1 HP Tanks are in exactly the ramp colours (the tilt's colour expansion of mm.RAMP), one cluster each; the twin game (Andy) has none of those
    colours; the white numbers (9 HP, the Oozium, Andy's Tank, 10 HP has none) stay white: the twin has exactly eight white numbers more."""
    env = {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1", "TANGOAW2_TILT_SCALE": "4", "TANGOAW2_TILT_TIME": "0"}
    shots = {}
    for co in ("aria", "andy"):
        g = scene(ctx, co, KIND, dict(ENV, **env))
        for _ in range(12):
            g.e.shot(os.path.join(ctx.out, "warm"))
        shots[co] = load(ctx.shot(g, f"{co}_tilt"))
        g.e.close()
    ia, ib = shots["aria"], shots["andy"]
    ctx.eq(ia.size, (960, 640), "the tilted picture is 4x")
    px = lambda im: {(x, y): im.getpixel((x, y)) for y in range(im.height) for x in range(im.width)}
    pa, pb = px(ia), px(ib)
    ramp = {tuple(tilt_lut(c >> 3) for c in RAMP[h]): h for h in range(1, 9)}
    for col, h in ramp.items():
        na, nb = sum(1 for c in pa.values() if c == col), sum(1 for c in pb.values() if c == col)
        ctx.check(na >= 100 and nb == 0, f"{h} HP: the tilted number is in {col} ({na} pixels; the twin has {nb})")
    clusters = components({p: c for p, c in pa.items() if c in ramp}, 960, 640, lambda c: True)
    big = [c for c in clusters if len(c) >= 100]
    ctx.eq(len(big), 8, "eight numbers in the ramp, one cluster each")
    ctx.eq(sorted(ramp[pa[next(iter(c))]] for c in big), list(range(1, 9)), "one for each HP 1..8")
    # the white numbers: in the band of the Tanks' row (where the ramp clusters are), the twin has eight more white clusters
    y0 = min(y for c in big for _, y in c) - 40
    y1 = max(y for c in big for _, y in c) + 40
    def whites(p):
        return [c for c in components({q: v for q, v in p.items() if y0 <= q[1] <= y1 and q[0] > 100}, 960, 640, lambda v: v == WHITE) if len(c) >= 40]
    wa, wb = whites(pa), whites(pb)
    ctx.eq(len(wb) - len(wa), 8, f"the white numbers left in her row: {len(wa)} (9 HP, Oozium, Andy's Tank) against the twin's {len(wb)}")
    ctx.check(len(wa) >= 3, "9 HP, the Oozium and Andy's Tank keep white numbers")
    if REVIEW:
        os.makedirs(REVIEW, exist_ok=True)
        ia.crop((0, y0, 960, y1)).save(os.path.join(REVIEW, f"{KIND}_tilt_aria.png"))
        ib.crop((0, y0, 960, y1)).save(os.path.join(REVIEW, f"{KIND}_tilt_andy.png"))


def oam_entries(e):
    """Every shown sprite of OAM: (index, y, x, w, h, first tile, palette)."""
    sizes = {(0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64), (1, 0): (16, 8), (1, 1): (32, 8), (1, 2): (32, 16), (1, 3): (64, 32),
             (2, 0): (8, 16), (2, 1): (8, 32), (2, 2): (16, 32), (2, 3): (32, 64)}
    oam = e.read(OAM, 0x400)
    out = []
    for i in range(128):
        a0, a1, a2 = struct.unpack("<3H", oam[8 * i:8 * i + 6])
        if (a0 >> 8) & 3 == 2 or (a0 >> 14) == 3:
            continue
        w, h = sizes[(a0 >> 14, a1 >> 14)]
        out.append((i, a0 & 0xFF, a1 & 0x1FF, w, h, a2 & 0x3FF, a2 >> 12))
    return out


def strip_sprites(e):
    """The strip's own sprites in OAM: its 'Vengeance' pair of 32 x 16 sprites and the number's 32 x 8 (found by their tile order: base, base + 8, base + 16 in palette 1), or []."""
    ents = [x for x in oam_entries(e) if x[6] == 1 and (x[3], x[4]) in ((32, 16), (32, 8))]
    for a in ents:
        b = [x for x in ents if (x[3], x[4]) == (32, 16) and x[5] == a[5] + 8 and x[1] == a[1] and x[2] == a[2] + 32]
        c = [x for x in ents if (x[3], x[4]) == (32, 8) and x[5] == a[5] + 16]
        if (a[3], a[4]) == (32, 16) and b and c and c[0][1] == a[1] + 17:
            return [a, b[0], c[0]]
    return []


def cursor_on_sign(g):
    """Whether the cursor is on a unit of hers with 8 HP or less (a strip is then due)."""
    u = g.unit_at(*g.cursor())
    return bool(u and u["army"] == 1 and u["type"] != 27 and 1 <= (u["hp"] + 9) // 10 <= 8)


def check_strip_oam(ctx, e, label, want, box):
    """The strip's OAM entries are there exactly when `want`, inside `box` (x0, y0, x1, y1), and no other sprite of the frame uses its tiles: nothing of the strip can show on another sprite, nor another's picture in it."""
    st = strip_sprites(e)
    ctx.eq(bool(st), want, f"{label}: strip sprites in OAM when expected")
    if not st:
        return
    base = st[0][5]
    for (_, y, x, w, h, t, pal) in st:
        # (the lettering is 53 pixels in a 64 pixel sprite: the clear rest may reach a few pixels past the window)
        ctx.check(box[0] <= x and x + w <= box[2] + 12 and box[1] - 2 <= y and y + h <= box[3] + 1, f"{label}: a strip sprite at {(x, y)} {w}x{h} is inside the strip's box {box}")
    shown_on_screen = lambda x: x[1] < 160 and x[1] + x[4] > 0 and x[2] < 240 and x[2] + x[3] > 0
    others = [x for x in oam_entries(e) if x not in st and shown_on_screen(x) and not (x[5] + max(1, x[3] * x[4] // 64) <= base or x[5] >= base + 20)]
    ctx.check(not others, f"{label}: no other sprite uses the strip's tiles {base}..{base + 19} ({others[:2]})")
    # and no sprite of the game shows a tile that holds the strip's lettering (the game's own pictures are intact)
    vram = e.read(0x0601_0000, 1024 * 32)
    mine = {vram[32 * t:32 * t + 32] for t in range(base, base + 16)} - {bytes(32)}
    leaked = [x for x in oam_entries(e) if x not in st and shown_on_screen(x) and any(vram[32 * t:32 * t + 32] in mine for t in range(x[5], x[5] + max(1, x[3] * x[4] // 64)))]
    ctx.check(not leaked, f"{label}: no sprite of the game shows a tile of the lettering ({leaked[:2]})")


@test(modes=("ds",))
def aria_vengeance_signs_no_leak(ctx):
    """Her Infantry on several rows, Andy's Mech below each: for each, the forecast opens (select the Mech, Fire), B three times, then the attack, and the next. Every frame has the strip's three sprites inside the strip's own box
    while a forecast of a wounded unit is open and none otherwise, no sprite of the game uses the tiles the strip's sprites do, and the Mechs' pictures are the twin game's."""
    rows = [(4, 80), (7, 50), (10, 20), (13, 10)]
    shots = {}
    for co in ("aria", "andy"):
        m = ctx.map()
        for r, _ in rows:
            m.unit(1, "infantry", 5, r).unit(2, "mech", 5, r + 1)
        g = ctx.start(m, [co, "andy"], humans=(1, 2), env=ENV)
        for r, hp in rows:
            ctx.set_hp(g, 5, r, hp)
        g.end_turn(human=2)
        for r, hp in rows:
            g.select(5, r + 1)
            g.move_to(5, r + 1)
            g.choose("Fire", g.ACTION_MENU)
            g.e.wait(40)
            shots[(co, r)] = g.e.shot(os.path.join(ctx.out, f"{co}_{r}"))
            if co == "aria":
                ia = load(shots[(co, r)])
                wt = mm.window_top(ia)
                x0, x1 = mm.window_x(ia)
                check_strip_oam(ctx, g.e, f"forecast on her {shown(hp)} HP Infantry", True, (x0, wt, x1, wt + STRIP_H))
            for _ in range(3):
                g.e.press("B", 4)
                g.e.wait(10)
            if co == "aria":
                check_strip_oam(ctx, g.e, "after the forecast closed", cursor_on_sign(g), (0, 0, 240, 160))
            g.select(5, r + 1)
            g.move_to(5, r + 1)
            g.choose("Fire", g.ACTION_MENU)
            g.pick_target(5, r)
            g.wait_for_input()
            g.e.wait(30)
            if co == "aria":
                check_strip_oam(ctx, g.e, "after the attack", cursor_on_sign(g), (0, 0, 240, 160))
        g.e.close()
    # (the games part after the first attack, the damage differing: the frames are looked at, not compared; what the sprites use is checked above, frame by frame)


def faded(c8, y):
    """A colour after the GBA's brightness increase by y / 16 (5-bit channels)."""
    out = []
    for c in c8:
        c5 = c >> 3
        out.append(expand(c5 + (((31 - c5) * y) >> 4)))
    return tuple(out)


@test(modes=("ds",))
def aria_vengeance_signs_fade(ctx):
    """The game's fades are the GBA's brightness effect (BLDCNT mode 2 / 3 on every layer, BLDY stepping 0..16), not a change of palettes: so a number in the ramp fades with the map exactly as a white one does, the
    hardware applying it to whatever colour the layer holds. Her Super Power's fade to white is stepped through, frame by frame: at every step the unit palettes (BG 11..15) and the ramp's bank hold the same colours
    as before the fade (nothing of ours is rewritten to a faded or unfaded value), and the ramp's bank is ours while a tile map of the map screen refers to it."""
    g = scene(ctx, "aria", KIND)
    e = g.e
    banks = {b: e.read(BG_PAL + 32 * b, 32) for b in (11, 12, 13, 14, 15)}
    g.charge_power(1, "super")
    g.open_map_menu()
    g.choose("Super", g.MAP_MENU)
    steps = set()
    for _ in range(400):
        e.wait(1)
        y = e.u16(0x0400_0054) & 0x1F
        if e.u16(0x0400_0050) & 0x3F == 0x3F and y:
            steps.add(y)
            for b in (11, 13, 14, 15):
                ctx.check(e.read(BG_PAL + 32 * b, 32) == banks[b], f"fade step {y}/16: unit palette {b} is not changed by the fade")
    ctx.check(len(steps) >= 8, f"the fade was stepped through ({sorted(steps)})")
    e.close()


def five_scene(ctx, env=None, co="aria"):
    """A five-army game with fog: her Tanks at 8..1 HP (army 1) in a row, every army's units, a wide mix of terrain (the fog's banks 4..7 and the others), moved units of the other armies (BG palette 9)."""
    m = ctx.map(hq=((1, 0, 0), (2, 29, 19), (3, 29, 0), (4, 0, 19)))
    m.terrain(15, 15, 0x1B4)
    m.colours = [5, 1, 2, 3, 4]
    for a in range(2, 6):
        m.unit(a, "tank", 1 + a, 3).unit(a, "infantry", 1 + a, 4)
    for k, t in enumerate(("wood", "mountain", "road", "river", "sea", "city", "bridge", "shoal", "reef", "pipe")):
        m.terrain(3 + k, 9, t)
    for k in range(8):
        m.unit(1, "tank", 2 + k, ROW)
    g = ctx.start(m, [co, "andy", "max", "olaf", "sami"], humans=(1,), fog=True, env=env or ENV)
    for k in range(8):
        ctx.set_hp(g, 2 + k, ROW, 80 - 10 * k)
    g.e.wait(30)
    g.goto(2, ROW + 4)
    g.e.wait(40)
    return g


def bg_banks_referenced(e):
    refs = set()
    for i in range(4):
        c = e.u16(0x0400_0008 + 2 * i)
        for ent in struct.unpack("<1024H", e.read(0x0600_0000 + ((c >> 8) & 31) * 0x800, 0x800)):
            if ent & 0x3FF and not 0x340 <= ent & 0x3FF <= 0x347:
                refs.add(ent >> 12)
    return refs


@test(modes=("ds",))
def aria_vengeance_signs_worst_case_banks(ctx):
    """Fog and five armies (the fog's terrain banks, five unit banks, a moved unit's bank 9) and then, by drawing tiles of them on BG0 (a menu's layer), every bank the ramp prefers (4, 5, 6, 7, 1, 3, 2, 11, 9, 10) referenced
    as well: her 8..1 HP numbers are still in exactly the ramp colours, in the one bank left (8 and 0 are not used for it), and the game's own palettes are as they were in every bank we do not use."""
    g = five_scene(ctx)
    e = g.e
    g.wait_for_input()
    g.select(7, ROW)
    g.move_to(7, ROW)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_for_input()
    g.goto(2, ROW + 4)
    e.wait(40)
    cnt = e.u16(0x0400_0008)
    sb = 0x0600_0000 + ((cnt >> 8) & 31) * 0x800
    natural = bg_banks_referenced(e)
    ctx.log(f"banks referenced by the game: {sorted(natural)}")
    # (the same game with Andy for Aria: the game's own palettes at this point)
    t = five_scene(ctx, co="andy")
    t.wait_for_input()
    t.select(7, ROW)
    t.move_to(7, ROW)
    t.choose("Wait", t.ACTION_MENU)
    t.wait_for_input()
    t.goto(2, ROW + 4)
    t.e.wait(40)
    before = {b: t.e.read(BG_PAL + 32 * b, 32) for b in range(16)}
    t.e.close()
    for b in (4, 5, 6, 7, 1, 3, 2, 11, 9, 10):
        # (BG0's empty screen block: a clear tile of the font run 0x3BF in each bank; the game writes BG0 only for menus)
        e.w16(sb + 2 * (31 * 32 + b), 0x3BF | (b << 12))
    e.wait(6)
    ctx.eq(sorted(bg_banks_referenced(e) & set(range(16)) - {8, 0}), sorted((set((4, 5, 6, 7, 1, 3, 2, 11, 9, 10)) | natural) - {8, 0}), "the worst case: every preferred bank is referenced")
    path = ctx.shot(g, "worst")
    im = load(path)
    for h in range(1, 9):
        n = sum(1 for p in im.getdata() if p == ramp_rgb(h))
        ctx.check(n >= 8, f"{h} HP: the number is in {ramp_rgb(h)} ({n} pixels)")
    used = {b for v in ours(e).values() for b in v}
    ctx.eq(len(used), 1, f"one bank holds the ramp ({used})")
    ctx.check(used <= {8}, f"it is the one bank left, 8 ({used})")
    for b in range(16):
        if b not in used:
            ctx.check(e.read(BG_PAL + 32 * b, 32) == before[b], f"bank {b} is the game's as it was")
    e.close()
