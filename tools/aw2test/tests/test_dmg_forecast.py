"""The damage forecast box ("Damage xx%") beside the targeting cursor, on maps that carry
tangoAW2's own OBJ art: Crystals, the Obelisk, the north Black Cannon, the Factory and the
Volcano. Each case drives the real menus (select, Fire, the cursor on a target) and looks at
the box: its sprites' tiles and palette must be what the game loaded, not our art's
(AW2TEST_PICS=<dir> keeps the pictures)."""

import os
import struct

from aw2test import bhcampaign as bh
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game, NavError
from aw2test.harness import test

OAM = 0x07000000
VRAM = 0x06010000
PICS = os.environ.get("AW2TEST_PICS")
MAP = 0x0201E450
SIZES = {(0, 0): (1, 1), (0, 1): (2, 2), (0, 2): (4, 4), (0, 3): (8, 8), (1, 0): (2, 1), (1, 1): (4, 1),
         (1, 2): (4, 2), (1, 3): (8, 4), (2, 0): (1, 2), (2, 1): (1, 4), (2, 2): (2, 4), (2, 3): (4, 8)}


def sprites(e):
    """[(tile, tiles wide*high, palette, x, y)] of the visible sprites."""
    oam = e.read(OAM, 0x400)
    out = []
    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<HHH", oam, 8 * i)
        if (a0 >> 8) & 3 == 2:
            continue
        w, h = SIZES.get((a0 >> 14, a1 >> 14), (1, 1))
        y = a0 & 0xFF
        if y >= 160 and y < 240:
            continue
        out.append((a2 & 0x3FF, w * h, a2 >> 12, a1 & 0x1FF, y))
    return out


def tile_set(sp):
    s = set()
    for t, n, _, _, _ in sp:
        s.update(range(t, min(t + n, 1024)))
    return s


def our_ranges():
    """OBJ tiles tangoAW2's art may occupy (crate::obelisk and friends)."""
    return {"obelisk": range(0x176, 0x176 + 36), "crystal": range(0x19A, 0x19A + 8),
            "cannon north 0": range(989, 989 + 16), "cannon north 1": range(1007, 1007 + 8),
            "cannon north 2": range(1015, 1015 + 8), "cannon north 3": range(914, 914 + 4),
            "factory": range(786, 834), "volcano": range(0x130, 0x130 + 64)}


def layer_cell(e, x, y):
    return MAP + 0x12 + e.u16(MAP + 0x417A + 2 * y) + x


def bmp_png(path):
    try:
        from PIL import Image
        im = Image.open(path + ".bmp")
        im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(path + ".png")
    except ImportError:
        pass


def plain_reference(ctx):
    """The forecast box on a plain Versus map without a structure: (box tile data 442..457, palette bank 1)."""
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10)
    g = ctx.start(m, ["andy", "drake"])
    e = g.e
    g.select(10, 10)
    g.move_to(10, 10)
    g.choose("Fire", g.ACTION_MENU)
    e.wait(40)
    ref = (e.read(VRAM + 442 * 32, 16 * 32), e.read(0x05000200 + 32, 32), e.read(VRAM + 458 * 32, 8))
    e.close()
    return ref


def case(ctx, e, g, d, name, att_type, tgt_type, tgt_hp=50, fire=False):
    """Poke an attacker of `att_type` (the first free player unit with a free land neighbour) and a
    `tgt_type` enemy beside it, drive Select, Fire and the cursor onto the target; returns the
    forecast's (sprites, VRAM tiles, palette)."""
    g._units_base = g._players_base = None
    units = g.units()
    taken = {(u["x"], u["y"]) for u in units}
    w, h = d.size()
    # (the player's army as g.units numbers it: five-army records are 51 apart, so Black Hole's fifth is 4)
    me = 4 if g.current_army() == 5 else g.current_army()
    enemies = [u for u in units if u["army"] != me]
    for a in g.units(army=me):
        if a["type"] not in (1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 14, 15):
            continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            x, y = a["x"] + dx, a["y"] + dy
            if not (0 <= x < w and 0 <= y < h) or (x, y) in taken:
                continue
            if g.terrain_class(x, y) & 0x1F not in (1,):   # plains
                continue
            tgt = next(u for u in enemies if u["type"] not in (0,) and (u["x"], u["y"]) != (x, y))
            break
        else:
            continue
        break
    else:
        raise NavError("no attacker with a free plain neighbour")
    ua = g.unit_addr(a["id"])
    e.w8(ua, att_type)
    e.w16(ua + 4, 100 | (9 << 7) if False else (e.u16(ua + 4) & ~0x7F & ~(0xF << 7)) | 100 | (9 << 7))
    d.place_unit(tgt, x, y)
    ut = g.unit_addr(tgt["id"])
    e.w8(ut, tgt_type)
    e.w16(ut + 4, (e.u16(ut + 4) & ~0x7F) | tgt_hp)
    g._units_base = g._players_base = None
    ctx.log(f"{name}: attacker {a['id']} at {(a['x'], a['y'])} type {att_type}, target {tgt['id']} at {(x, y)} type {tgt_type} hp {tgt_hp}")
    g.wait_idle()
    e.wait(20)
    idle = sprites(e)
    g.select(a["x"], a["y"])
    g.move_to(a["x"], a["y"])
    g.choose("Fire", g.ACTION_MENU)
    e.wait(40)
    ctx.log(f"{name}: the cursor is on {g.cursor()} (the target at {(x, y)}; the first of the targets in reach)")
    sp = sprites(e)
    pic = os.path.join(ctx.out, name)
    e.shot(pic)
    bmp_png(pic)
    if PICS:
        os.makedirs(PICS, exist_ok=True)
        e.shot(os.path.join(PICS, name))
        bmp_png(os.path.join(PICS, name))
    vram = e.read(VRAM, 0x8000)
    pal = e.read(0x05000200, 0x200)
    ctx.last_box = (vram[442 * 32:458 * 32], pal[32:64])
    # back out: the targeting, then the move
    if fire:
        e.press("A", 4)
        for _ in range(60):
            e.wait(60)
            if not g.has_proc(0x080228D9) and not g.has_proc(0x08019D0D):
                break
        g.wait_idle(max_frames=6000)
        e.wait(60)
        return idle, sp, vram, pal
    for _ in range(10):
        e.press("B", 4)
        e.wait(30)
        if not g.has_proc(0x080228D9) and not g.has_proc(0x08019D0D):
            break
    g.wait_idle()
    return idle, sp, vram, pal


def boxes(idle, sp):
    """The sprites the forecast added: not in the idle map's list."""
    have = {(t, n, p) for t, n, p, _, _ in idle}
    return [s for s in sp if (s[0], s[1], s[2]) not in have]


CASES = [("tank_vs_mech", 5, 2, 50), ("megatank_vs_tank", 4, 5, 50), ("infantry_vs_mdtank", 1, 3, 100),
         ("mech_vs_infantry_5hp", 2, 1, 50), ("neotank_vs_megatank", 8, 4, 100), ("recon_vs_infantry", 6, 1, 70)]


def run_cases(ctx, e, g, d, prefix, cases=CASES):
    seen = []
    for name, a, t, hp in cases:
        try:
            idle, sp, vram, pal = case(ctx, e, g, d, f"{prefix}_{name}", a, t, hp)
        except NavError as ex:
            ctx.log(f"{prefix}_{name}: skipped ({ex})")
            continue
        new = boxes(idle, sp)
        ours = our_ranges()
        hit = []
        for t0, n, p, x, y in new:
            for k, r in ours.items():
                if set(range(t0, t0 + n)) & set(r):
                    hit.append((k, t0, n))
        ctx.log(f"{prefix}_{name}: forecast sprites {[(t0, n, p) for t0, n, p, _, _ in new]}")
        seen.append((name, new, hit))
    return seen


def start_m1(ctx):
    from tests.test_bh_campaign import boot, first_mission
    e, g, d = boot(ctx)
    first_mission(ctx, e, d)
    g._units_base = g._players_base = None
    e.wait(30)
    return e, g, d


@test(modes=("ds",))
def forecast_box_clear_of_our_art_m1(ctx):
    """BH Campaign mission 1 (Crystals, Obelisk, Factory, a Black Cannon): no sprite of the
    damage forecast box draws from a tile our art occupies, in six matchups."""
    e, g, d = start_m1(ctx)
    ref = plain_reference(ctx)
    seen = run_cases(ctx, e, g, d, "m1")
    box, pal1 = ctx.last_box
    ctx.check(box == ref[0], "the box's frame tiles (442..457) are the game's own, as on a plain map")
    # (colour 4 is the box's fill, which the game tints by the damage it forecasts)
    used = sorted(({b & 15 for b in box} | {b >> 4 for b in box}) - {4})
    cols = lambda pal: [pal[2 * i:2 * i + 2] for i in used]
    ctx.log(f"box colour indexes {used}; map {[c.hex() for c in cols(pal1)]}; plain {[c.hex() for c in cols(ref[1])]}")
    ctx.check(cols(pal1) == cols(ref[1]), "the colours the box draws with (palette bank 1) are the plain map's")
    ctx.require(len(seen) >= 3, f"the matchups ran ({len(seen)})")
    for name, new, hit in seen:
        ctx.check(not hit, f"{name}: the forecast's sprites avoid our art's tiles ({hit})")
    after_a_battle_scene(ctx, e, g, d, "m1")


def start_features(ctx, mission, five):
    """A feature mission of the BH Campaign's test set (bh.FEATURES): `mission` is its 0-based index."""
    from tests.test_bh_nofactory import boot_features
    e, g, d = boot_features(ctx)
    d.picks = {mission: 0}
    d.start_at(won_mask=((1 << mission) - 1) & ~(1 << 5), unlocked_mask=1)
    d.pick_mission()
    d.wait_map()
    g._units_base = g._players_base = None
    e.wait(60)
    if five:
        # (the allies' four turns come first)
        stable = 0
        for _ in range(3000):
            stable = stable + 1 if g.current_army() == 5 and not d.scripts_running() else 0
            if stable >= 5:
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(20)
    d.wait_control()
    return e, g, d


@test(modes=("ds",))
def north_cannon_and_forecast_m19(ctx):
    """The five-army test mission with a Black Cannon facing north, a Volcano, a Laser and a
    Deathray: the cannon is drawn from the tiles chosen for it (989, 1007, 1015, 914), each holding
    art, and the forecast box beside a target avoids every tile of our art."""
    e, g, d = start_features(ctx, 18, True)
    drawn = set()
    for cell in ((8, 12), (8, 13), (12, 4)):
        g.goto(*cell)
        e.wait(40)
        drawn |= {t for t, _, _, _, _ in sprites(e)}
        pic = os.path.join(ctx.out, f"cannon_{cell[0]}_{cell[1]}")
        e.shot(pic)
        bmp_png(pic)
    ctx.check({989, 1007, 1015, 914} <= drawn, f"the north cannon's four sprites are on screen ({sorted(t for t in drawn if t > 900)})")
    for t, n in ((989, 16), (1007, 8), (1015, 8), (914, 4)):
        ctx.check(any(e.read(VRAM + t * 32, n * 32)), f"tiles {t}..{t + n - 1} hold art")
    seen = run_cases(ctx, e, g, d, "m19", CASES[:3])
    ctx.require(seen, "a matchup ran")
    for name, new, hit in seen:
        ctx.check(not hit, f"{name}: the forecast's sprites avoid our art's tiles ({hit})")
    after_a_battle_scene(ctx, e, g, d, "m19")


ART_TILES = ((0x176, 36), (0x19A, 8), (989, 16), (1007, 8), (1015, 8), (914, 4))


def art_snapshot(e):
    return {t: e.read(VRAM + t * 32, n * 32) for t, n in ART_TILES}


def after_a_battle_scene(ctx, e, g, d, prefix):
    """With the battle animations on, a real attack plays Dual Strike's scene (which rewrites most of OBJ
    VRAM); back on the map every picture of ours is as before and the forecast box is clean again."""
    before = art_snapshot(e)
    e.w8(0x03003FC0 + 9, 1)            # gPlaySt animations: on
    frames0 = e.frame
    case(ctx, e, g, d, f"{prefix}_scene", 5, 5, 100, fire=True)
    ctx.check(e.frame - frames0 > 300, f"{prefix}: the battle scene played ({e.frame - frames0} frames)")
    e.w8(0x03003FC0 + 9, 0)
    after = art_snapshot(e)
    for (t, n) in ART_TILES:
        if any(before[t]):
            ctx.check(after[t] == before[t], f"{prefix}: tiles {t}..{t + n - 1} hold the same art after the scene")
    seen = run_cases(ctx, e, g, d, f"{prefix}_after", [("tank_vs_mech", 5, 2, 50)])
    for name, new, hit in seen:
        ctx.check(not hit, f"{prefix} after a scene, {name}: the forecast's sprites avoid our art's tiles ({hit})")
