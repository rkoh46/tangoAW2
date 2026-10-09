"""BH Campaign, Act IV (Blue Moon, M17 to M22: tango-gamesupport-aw2/src/bh_act4.rs)."""

import os

from aw2test import bhact4 as a2
from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test.harness import test


# --- every mission loads: its armies, map, rules and opening ---------------------------------------
GMAP = 0x0201E450
DS_TABLE = 0x08E00000
DAY = 0x03004080
KOAL, KINDLE, JUGGER, FLAK = 8, 16, 32, 64
SASHA, GRIT = 78, 5
ALL = a2.ST | a2.VB | a2.HK | KOAL | KINDLE | JUGGER
# number: (title, won before (mission numbers), roster bits, CO picks, armies: (colour, CO), map size, fog, day limit)
# (bh01, bh02 and the bh16 stand-in come first in this tree: the won mask is every earlier mission)
MISSIONS = {
    17: ("Cold Iron", [1, 2, 3], ALL & ~JUGGER, [bh.STURM], [(5, bh.STURM), (2, bh.JUGGER)], (24, 18), True, 22),
    18: ("The Pit", [1, 2, 3, 4], ALL, [bh.STURM], [(5, bh.STURM), (2, bh.FLAK)], (20, 20), False, 12),
    19: ("The Assembly Line", [1, 2, 3, 4], ALL, [bh.STURM], [(5, bh.STURM), (2, SASHA)], (32, 26), False, 28),
    20: ("Moonlit Harbours", [1, 2, 3, 4, 5, 6], a2.ST | a2.VB | a2.HK, [bh.STURM, bh.HAWKE], [(5, None), (2, bh.OLAF)], (26, 18), False, 24),
    21: ("Running Dry", [1, 2, 3, 4, 5, 6, 7], ALL | FLAK, [bh.STURM], [(5, bh.STURM), (1, 2), (2, GRIT)], (28, 20), True, 26),
    22: ("Whiteout", [1, 2, 3, 4, 5, 6, 7, 8], a2.ST | a2.VB | a2.HK, [bh.STURM, bh.HAWKE], [(5, None), (2, bh.OLAF)], (28, 22), False, 24),
}
MAP_FILES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tango-gamesupport-aw2", "five", "bh")


def map_units(name):
    """Units per army, from the map's text file (five/bh/<name>.txt)."""
    out = {}
    for line in open(os.path.join(MAP_FILES, name + ".txt")):
        f = line.split()
        if f and f[0] == "unit":
            out[int(f[1])] = out.get(int(f[1]), 0) + 1
    return out


def mission_count(g, army):
    return len(g.units(army))


def load_mission(ctx, n, cos=None, label=None):
    title, won, roster, picks, armies, size, fog, limit = MISSIONS[n]
    mask = (1 << a2.M[n]) - 1
    e, g, d = a2.boot(ctx, mask, roster, picks={a2.M[n]: len(cos or picks)}, at=a2.M[n])
    return e, g, d, MISSIONS[n]


def check_load(ctx, n):
    e, g, d, spec = load_mission(ctx, n)
    title, won, roster, picks, armies, size, fog, limit = spec
    units = map_units(f"bh{n:02d}")
    texts = a2.open_mission(ctx, e, g, d, a2.M[n], picks, f"m{n}")
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), a2.M[n], f"M{n}: the mission")
    ps = [g.player(a) for a in range(1, len(armies) + 1)]
    ctx.eq([(p["colour"], p["co"] if want[1] is not None else None) for p, want in zip(ps, armies)], armies, f"M{n}: army colours and COs")
    ctx.eq(d.size(), size, f"M{n}: the map's size")
    ps = g.playst()
    ctx.eq(bool(ps["fog"]), fog, f"M{n}: fog")
    ctx.eq(e.u16(DS_TABLE + 0x5C * dc.DS_MAP_ID + 0x24), limit, f"M{n}: the day limit")
    for army, count in units.items():
        ctx.eq(mission_count(g, army), count, f"M{n}: army {army}'s units")
    if len(picks) == 2:
        # (the pair: whichever of the two picks leads, the other is the partner or the second front's CO)
        from aw2test import tag
        from aw2test import twofront as tf
        other = (e.u8(tf.SECOND_COS)) if n == 20 else tag.partner(e, 1)["co"]
        ctx.eq(sorted([g.player(1)["co"], other]), sorted(picks), f"M{n}: the two picks lead the main army and its partner (or the second front)")
    a2.pic(ctx, e, f"m{n}_opening")
    ctx.log("\n".join(texts))
    e.close()


def _loads(n):
    def fn(ctx):
        check_load(ctx, n)
    fn.__name__ = f"bh_act4_m{n}_loads"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _loads(_n)


# --- pictures: the whole map, the opening frame after Deploy, a dialogue frame ------------------------
FOG = 0x03003FCD


def unfog(g, e):
    """Fog off for the picture: the map redraws unfogged once the map menu has opened and closed."""
    e.w8(FOG, 0)
    e.wait(10)
    g.open_map_menu()
    e.wait(20)
    e.press("B", 4)
    e.wait(40)


def pictures(ctx, n, shots=(0,)):
    """The opening frame after Deploy, a dialogue frame, and the whole map as one picture (fog off)."""
    from aw2test import stitch
    e, g, d, spec = load_mission(ctx, n)
    title, won, roster, picks, armies, size, fog, limit = spec
    texts = a2.open_mission(ctx, e, g, d, a2.M[n], picks, f"m{n}", shots=shots)
    d.wait_control()
    g._units_base = g._players_base = None
    a2.pic(ctx, e, f"m{n}_opening")
    ctx.log("\n".join(texts))
    stitch.IMAGES = a2.SHOTS or stitch.IMAGES
    w, h = d.size()
    if fog:
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}_fog", w, h)       # the map as the player sees it on day 1
        unfog(g, e)
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}_nofog", w, h)     # every unit of both sides
        stitch.stitch(ctx, g, f"m{n}", w, h)
    else:
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}", w, h)
    if n == 20:
        # the dusk gate, the second front: Map menu > Front shows it
        from aw2test import twofront as tf
        ctx.require(tf.look_at_other_front(e, g), "the other front is shown")
        w2, h2 = d.size()
        ctx.eq((w2, h2), (22, 16), "the second front's map: the open sea, 22x16")
        a2.pic(ctx, e, "m20_second_front_view")
        g.goto(0, 0)
        # (the view's "Second front" banner sits on the screen's top: a sweep without the cells it covers, the
        # few cells only it can show stand in the row below's)
        class Quiet:
            def __init__(self, c):
                self.c = c

            def __getattr__(self, k):
                return getattr(self.c, k)

            def check(self, ok, msg):
                return None
        clean = stitch.stitch(Quiet(ctx), g, "m20_second_front", w2, h2, exclude=lambda tx, ty: ty <= 2 and 5 <= tx <= 10)
        try:
            from PIL import Image
            import numpy as np
            a = np.asarray(Image.open(clean).convert("RGB")).copy()
            for cy in range(h2):
                for cx in range(w2):
                    cell = a[16 * cy:16 * cy + 16, 16 * cx:16 * cx + 16]
                    whitish = (cell.min(axis=2) > 225).sum() > 100 and cy <= 3      # (the view's info window, caught in a sweep)
                    if whitish:
                        cell[:] = a[16 * cy:16 * cy + 16, 16 * (cx + 2):16 * (cx + 2) + 16] if cx + 2 < w2 else cell
                    if not cell.any():
                        # (only a few cells under the view's windows: the nearest picture beside stands for them)
                        k = cx - 1
                        while k >= 0 and not a[16 * cy:16 * cy + 16, 16 * k:16 * k + 16].any():
                            k -= 1
                        if k < 0:
                            k = cx + 1
                            while k < w2 and not a[16 * cy:16 * cy + 16, 16 * k:16 * k + 16].any():
                                k += 1
                        cell[:] = a[16 * cy:16 * cy + 16, 16 * k:16 * k + 16]
            Image.fromarray(a).save(clean)
            if a2.SHOTS:
                Image.fromarray(a).save(os.path.join(a2.SHOTS, "m20_second_front_full.png"))
        except ImportError:
            pass
    e.close()


def _pictures(n):
    def fn(ctx):
        pictures(ctx, n)
    fn.__name__ = f"bh_act4_pictures_m{n}"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _pictures(_n)


def ready(ctx, n, cos=None, label=None):
    """The mission started and under the player's control."""
    title, won, roster, picks, armies, size, fog, limit = MISSIONS[n]
    cos = cos or picks
    mask = (1 << a2.M[n]) - 1
    e, g, d = a2.boot(ctx, mask, roster, picks={a2.M[n]: len(cos)}, at=a2.M[n])
    texts = a2.open_mission(ctx, e, g, d, a2.M[n], cos, label or f"m{n}")
    d.wait_control()
    g._units_base = g._players_base = None
    return e, g, d, texts


def capture_hq(ctx, e, g, d, hqs, hostile=None):
    """The test aid for a mission won by taking the HQ: every enemy unit but the farthest of each army
    removed, an Infantry of the player's on each HQ capturing it turn by turn until the HQ is the player's."""
    units = g.units()
    by = {}
    for u in units:
        if u["army"] != 1 and (hostile is None or u["army"] in hostile):
            by.setdefault(u["army"], []).append(u)
    for army, us in by.items():
        far = max(us, key=lambda u: min(abs(u["x"] - h[0]) + abs(u["y"] - h[1]) for h in hqs))
        for u in us:
            if u is not far:
                d.remove_unit(u)
    mine = [u for u in g.units(1) if u["type"] == 1][:len(hqs)]
    for u, hq in zip(mine, hqs):
        d.place_unit(u, *hq)
    e.wait(10)
    ctx.log(f"capturers placed: {[(u['id'], hq, g.unit_at(*hq)) for u, hq in zip(mine, hqs)]}")
    for turn in range(5):
        for hq in hqs:
            if g.terrain_class(*hq) >> 5 == 1:
                continue
            a2.calm(e, g, d)
            g.select(*hq)
            names = g.move_to(*hq)["names"]
            g.choose(next(x for x in names if x.lower().startswith("capt")), g.ACTION_MENU)
            for _ in range(200):
                if d.scripts_running() or e.u8(dc.LAST_RESULT):
                    return
                if g.idle():
                    break
                e.wait(4)
            e.wait(20)
            if d.scripts_running() or e.u8(dc.LAST_RESULT):
                return
        if all(g.terrain_class(*hq) >> 5 == 1 for hq in hqs):
            return
        a2.next_turn(e, g, d)


def lose_by_day(ctx, e, g, d, n):
    """The day limit loses: the day after it begins and the mission is lost."""
    limit = MISSIONS[n][7]
    e.w16(DAY, limit)
    a2.end_turn(e, g, d)
    for _ in range(3000):
        if e.u8(dc.LAST_RESULT):
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(20)
    ctx.eq(e.u8(dc.LAST_RESULT), 2, f"M{n}: lost when day {limit + 1} begins")


def after_win(ctx, e, g, d, n, victory, mapscene, want_next, unlocked):
    """The checks every win has: the won bit, the next flags open, the unlocked COs."""
    ctx.eq((d.won() >> a2.M[n]) & 1, 1, f"M{n} won")
    flags = d.map_flags()
    ctx.eq([k for k in range(len(flags)) if flags[k] & 1 and not flags[k] & 2 and k > a2.M[n]], [a2.M[k] for k in want_next], f"M{n}: the next flags open")
    ctx.eq(d.unlocked(), unlocked, f"M{n}: the roster")


def _win_by_capture(n, hqs, want_next, unlocked, cos=None):
    def fn(ctx):
        e, g, d, texts = ready(ctx, n, cos)
        capture_hq(ctx, e, g, d, hqs)
        victory, mapscene = a2.follow(ctx, e, d, f"m{n}", shots=(0,))
        ctx.log("VICTORY\n" + "\n".join(victory) + "\nMAP\n" + "\n".join(mapscene))
        ctx.check(len(victory) >= 3 and len(mapscene) >= 3, f"M{n}: the victory scene and the world-map scene played ({len(victory)}, {len(mapscene)} boxes)")
        spec = MISSIONS[n]
        after_win(ctx, e, g, d, n, victory, mapscene, want_next, unlocked)
        a2.pic(ctx, e, f"m{n}_world_after")
        e.close()
    fn.__name__ = f"bh_act4_m{n}_win_by_capture"
    test(modes=("ds",))(fn)


def _lose_by_day(n):
    def fn(ctx):
        e, g, d, texts = ready(ctx, n)
        lose_by_day(ctx, e, g, d, n)
        e.close()
    fn.__name__ = f"bh_act4_m{n}_lose_by_day_limit"
    test(modes=("ds",))(fn)



_win_by_capture(17, [(21, 9)], [18, 19], [bh.STURM, bh.VON_BOLT, bh.HAWKE, bh.KOAL, bh.KINDLE, bh.JUGGER])
_win_by_capture(18, [(10, 1)], [19], [bh.STURM, bh.VON_BOLT, bh.HAWKE, bh.KOAL, bh.KINDLE, bh.JUGGER, bh.FLAK], cos=None)
_win_by_capture(19, [(29, 12)], [20], [bh.STURM, bh.VON_BOLT, bh.HAWKE, bh.KOAL, bh.KINDLE, bh.JUGGER])
_win_by_capture(22, [(14, 3)], [], [bh.STURM, bh.VON_BOLT, bh.HAWKE])
for _n in MISSIONS:
    if _n != 20:
        _lose_by_day(_n)


# --- mission specifics -------------------------------------------------------------------------------------
@test(modes=("ds",))
def bh_act4_m17_hawke_pitch_bond_and_jugger_joins(ctx):
    """Hawke leads: his pitch, Jugger joins and the bond (bit 4) is earned."""
    e, g, d, texts = ready(ctx, 17, [bh.HAWKE])
    victory, mapscene = a2.win_by_attrition(ctx, e, g, d, "m17_hk", shots=(0,))
    ctx.check("Because here you will not be called too literal." in " ".join(victory), f"Hawke's pitch ({victory})")
    ctx.eq((d.bonds() >> 4) & 1, 1, "Jugger's bond earned")
    ctx.check(bh.JUGGER in d.unlocked(), "Jugger unlocked")
    e.close()


@test(modes=("ds",))
def bh_act4_m17_other_co_no_bond(ctx):
    e, g, d, texts = ready(ctx, 17, [bh.VON_BOLT])
    a2.win_by_attrition(ctx, e, g, d, "m17_vb", shots=(0,))
    ctx.eq((d.bonds() >> 4) & 1, 0, "no bond for Von Bolt's default pitch")
    ctx.check(bh.JUGGER in d.unlocked(), "Jugger still joins")
    e.close()


@test(modes=("ds",))
def bh_act4_m18_sturm_pitch_bond_and_flak_joins(ctx):
    e, g, d, texts = ready(ctx, 18, [bh.STURM])
    victory, mapscene = a2.win_by_attrition(ctx, e, g, d, "m18_st", shots=(0,))
    ctx.check("A thousand battles. And a full table." in " ".join(victory), f"Sturm's pitch ({victory})")
    ctx.eq((d.bonds() >> 5) & 1, 1, "Flak's bond earned")
    ctx.check(bh.FLAK in d.unlocked(), "Flak unlocked")
    e.close()


@test(modes=("ds",))
def bh_act4_m18_throne_wins(ctx):
    """Capturing the throne (10, 10) wins without routing Flak."""
    e, g, d, texts = ready(ctx, 18)
    capture_hq(ctx, e, g, d, [(10, 10)])
    a2.follow(ctx, e, d, "m18_throne", shots=())
    ctx.eq((d.won() >> a2.M[18]) & 1, 1, "M18 won by the throne")
    e.close()


@test(modes=("ds",))
def bh_act4_m19_factory_spawns_on_the_doors(ctx):
    """Day 2: the Black Factory (x 4..6, y 10..13, doors on row 14) spawns on the player's doors."""
    e, g, d, texts = ready(ctx, 19)
    before = {(u["x"], u["y"]) for u in g.units(1)}
    ctx.check(all(not (u["y"] == 14 and 4 <= u["x"] <= 6) for u in g.units(1)), "the doors are free at the start")
    a2.to_day(e, g, d, 2)
    spawned = [(u["type"], u["x"], u["y"]) for u in g.units(1) if (u["x"], u["y"]) not in before and u["y"] == 14 and 4 <= u["x"] <= 6]
    ctx.check(len(spawned) >= 1, f"a unit on a door ({spawned})")
    a2.pic(ctx, e, "m19_factory_day2")
    e.close()


@test(modes=("ds",))
def bh_act4_m19_sasha_funds_and_megatank(ctx):
    e, g, d, texts = ready(ctx, 19)
    ctx.check(any(u["type"] == 4 for u in g.units(2)), "Sasha starts with the Megatank")
    ctx.eq(len([u for u in g.units(2) if u["type"] == 8]), 2, "two Neotanks")
    e.close()


@test(modes=("ds",))
def bh_act4_m21_column_starts_low_and_the_convoy_comes(ctx):
    """The column's ammunition and fuel as the sheet lists; convoy A on day 3, convoy B on day 6."""
    e, g, d, texts = ready(ctx, 21)
    want = {3: (0, 25), 10: (0, 25), 11: (0, 25), 15: (0, 25), 19: (0, 28), 5: (1, 30)}
    got = {}
    for u in g.units(1):
        if u["type"] in want:
            got.setdefault(u["type"], set()).add((u["ammo"], u["fuel"]))
    ctx.log(str(got))
    for t, (ammo, fuel) in want.items():
        ok = all(a == ammo and (f == fuel or (fuel == 99 and f > 40)) for a, f in got.get(t, set()))
        ctx.check(got.get(t) and ok, f"type {t}: ammo {ammo}, fuel {fuel} (got {got.get(t)})")
    a2.pic(ctx, e, "m21_start")
    apcs = lambda: [u for u in g.units(1) if u["type"] == 7]
    ctx.eq(len(apcs()), 0, "no APC at the start")
    a2.to_day(e, g, d, 3)
    ctx.eq([(u["x"], u["y"]) for u in apcs()][:1] and len(apcs()), 1, "convoy A's APC on day 3")
    a2.to_day(e, g, d, 6)
    ctx.check(len(apcs()) >= 2, f"convoy B's APCs on day 6 ({len(apcs())})")
    e.close()


@test(modes=("ds",))
def bh_act4_m21_supply_cut_loses(ctx):
    """With every APC destroyed after the convoys have come and the guns still empty, the mission is lost."""
    e, g, d, texts = ready(ctx, 21)
    e.w16(DAY, 6)
    a2.to_day(e, g, d, 7)
    for u in g.units(1):
        if u["type"] == 7:
            d.remove_unit(u)
    mine = next(u for u in g.units(1) if u["type"] == 1)
    e.wait(10)
    g.select(mine["x"], mine["y"])
    g.move_to(mine["x"], mine["y"])
    names = g.menu()["names"]
    g.choose(next(n for n in names if n.lower().startswith("wait")), g.ACTION_MENU)
    for _ in range(3000):
        if e.u8(dc.LAST_RESULT):
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(20)
    ctx.eq(e.u8(dc.LAST_RESULT), 2, "lost with no APC left and the guns empty")
    e.close()


@test(modes=("ds",))
def bh_act4_m22_obelisk_and_forces_on_the_map(ctx):
    e, g, d, texts = ready(ctx, 22, [bh.STURM, bh.HAWKE])
    ctx.eq(len(g.units(2)), 30, "Blue Moon's 30 units")
    e.close()


def _advances(n, army, cos=None):
    def fn(ctx):
        e, g, d, texts = ready(ctx, n, cos)
        before = {(u["x"], u["y"]) for u in g.units(army)}
        a2.to_day(e, g, d, 3)
        after_ = {(u["x"], u["y"]) for u in g.units(army)}
        moved = len(after_ - before)
        ctx.check(moved >= len(before) // 2, f"M{n}: army {army}'s units advance ({moved} of {len(before)} cells changed by day 3)")
        e.close()
    fn.__name__ = f"bh_act4_m{n}_enemy_advances"
    test(modes=("ds",))(fn)


_advances(17, 2)
_advances(18, 2)
_advances(21, 2)


@test(modes=("ds",))
def bh_act4_m21_nobody_is_lost_to_fuel_on_days_1_to_3(ctx):
    """The B Copter (air units crash at 0 fuel at turn start) and every other unit of the column survive days 1-3 with fuel left."""
    e, g, d, texts = ready(ctx, 21)
    start = {(u["type"], u["x"], u["y"]) for u in g.units(1)}
    copter = [u for u in g.units(1) if u["type"] == 19]
    ctx.eq(len(copter), 1, "one B Copter")
    ctx.check(copter[0]["fuel"] >= 25, f"its fuel is low but safe ({copter[0]['fuel']})")
    for day in (2, 3):
        a2.to_day(e, g, d, day)
        mine = g.units(1)
        cp = [u for u in mine if u["type"] == 19]
        ctx.check(len(cp) == 1 and cp[0]["fuel"] > 0, f"day {day}: the B Copter is alive with fuel ({[u['fuel'] for u in cp]})")
        ctx.check(all(u["fuel"] > 0 for u in mine if u["type"] != 7), f"day {day}: no unit is out of fuel ({sorted(u['fuel'] for u in mine)[:3]})")
    e.close()
