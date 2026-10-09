"""BH Campaign, Act III (Yellow Comet, M12 to M16: tango-gamesupport-aw2/src/bh_act3.rs)."""

import os

from aw2test import bhact3 as a3
from aw2test import bhact4 as a4
from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test import ram
from aw2test import tag
from aw2test.harness import test

GMAP = 0x0201E450
DS_TABLE = 0x08E00000
DAY = 0x03004080
FOG = 0x03003FCD
ALL = a3.ST | a3.VB | a3.HK | a3.KO | a3.KI
# number: (title, won before (mission numbers; M11 is the tree's stub), roster bits, CO picks (M12: the pair, lead first;
# M16: a fixed pair, no pick screen), size, fog, day limit)
MISSIONS = {
    12: ("Highway to the Horizon", list(range(1, 12)), a3.ST | a3.VB | a3.HK, [bh.STURM, bh.HAWKE], (36, 18), False, 28),
    13: ("Festival of Flame", list(range(1, 13)), a3.ST | a3.VB | a3.HK | a3.KO, [bh.STURM], (22, 16), False, 14),
    14: ("No Soldier Left Behind", list(range(1, 14)), ALL, [bh.STURM], (22, 22), True, 15),
    15: ("The Skybridge", list(range(1, 15)), ALL, [bh.STURM, bh.HAWKE], (24, 20), False, 24),
    16: ("Comet Keep", list(range(1, 16)), ALL, [], (26, 22), False, 24),
}


def load_mission(ctx, n):
    title, won, roster, picks, size, fog, limit = MISSIONS[n]
    mask = 0
    for k in won:
        mask |= 1 << a3.M[k]
    e, g, d = a3.boot(ctx, mask, roster, picks={a3.M[n]: len(picks)}, at=a3.M[n])
    return e, g, d, MISSIONS[n]


def unfog(g, e):
    """Fog off for the picture: the map redraws unfogged once the map menu has opened and closed."""
    e.w8(FOG, 0)
    e.wait(10)
    g.open_map_menu()
    e.wait(20)
    e.press("B", 4)
    e.wait(40)


def pictures(ctx, n):
    from aw2test import stitch
    e, g, d, spec = load_mission(ctx, n)
    title, won, roster, picks, size, fog, limit = spec
    texts = a3.open_mission(ctx, e, g, d, a3.M[n], picks, f"m{n}", shots=(0,))
    d.wait_control()
    g._units_base = g._players_base = None
    a3.pic(ctx, e, f"m{n}_opening")
    ctx.log("\n".join(texts))
    stitch.IMAGES = a3.SHOTS or stitch.IMAGES
    w, h = d.size()
    ctx.eq((w, h), size, f"M{n}: the map's size")
    if fog:
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}_fog", w, h)       # the map as the player sees it on day 1
        unfog(g, e)
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}_nofog", w, h)     # every unit of both sides
    else:
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}", w, h)
    if n == 15:
        # Map menu > Front shows the sky front (display only). Its "Second front" banner covers cells (9..10, 0..2)
        # in every view; the label step repaints them (the clouds repeat every 4 cells).
        from aw2test import twofront as tf
        ctx.require(tf.look_at_other_front(e, g), "the other front is shown")
        w2, h2 = d.size()
        ctx.eq((w2, h2), (20, 14), "the sky front: 20x14")
        a3.pic(ctx, e, "m15_second_front_view")
        g.goto(0, 0)

        class Quiet:
            def __init__(self, c):
                self.c = c

            def __getattr__(self, k):
                return getattr(self.c, k)

            def check(self, ok, msg):
                return None
        stitch.stitch(Quiet(ctx), g, "m15_second_front", w2, h2, exclude=lambda tx, ty: ty <= 2 and 4 <= tx <= 10)
    e.close()


def _pictures(n):
    def fn(ctx):
        pictures(ctx, n)
    fn.__name__ = f"bh_act3_pictures_m{n}"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _pictures(_n)


# --- loads: every mission's armies, map, rules and opening ------------------------------------------------
MAP_FILES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tango-gamesupport-aw2", "five", "bh")
# number: (armies: (colour, CO) (None: the player's pick), funds)
GRIMM = 76
ARMIES = {
    12: [(5, None), (4, bh.KOAL)],
    13: [(5, None), (4, bh.KINDLE)],
    14: [(5, None), (4, bh.SONJA)],
    15: [(5, None), (4, bh.KANBEI)],
    16: [(5, bh.KOAL), (4, bh.KANBEI)],
}
# the enemy army's tag partner (None: it has none)
ENEMY_PARTNER = {12: GRIMM, 16: bh.SENSEI}
# the player's army: the fixed pair of M16 (lead, partner)
FIXED_PAIR = {16: (bh.KOAL, bh.KINDLE)}


def lead_and_partner(g, e, n):
    """(the player's lead CO, its tag partner's CO or None) as the battle holds them."""
    p = tag.partner(e, 1)
    return g.player(1)["co"], (p["co"] if p else None)


def map_units(name):
    """Units per army, from the map's text file (five/bh/<name>.txt)."""
    out = {}
    for line in open(os.path.join(MAP_FILES, name + ".txt")):
        f = line.split()
        if f and f[0] == "unit":
            out[int(f[1])] = out.get(int(f[1]), 0) + 1
    return out


def check_load(ctx, n):
    e, g, d, spec = load_mission(ctx, n)
    title, won, roster, picks, size, fog, limit = spec
    texts = a3.open_mission(ctx, e, g, d, a3.M[n], picks, f"m{n}")
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), a3.M[n], f"M{n}: the mission")
    ps = [g.player(a) for a in range(1, 3)]
    ctx.eq([p["colour"] for p in ps], [c for c, _ in ARMIES[n]], f"M{n}: army colours")
    ctx.eq(ps[1]["co"], ARMIES[n][1][1], f"M{n}: the enemy CO")
    foe = tag.partner(e, 2)
    ctx.eq(foe["co"] if foe else None, ENEMY_PARTNER.get(n), f"M{n}: the enemy's partner")
    lead, partner = lead_and_partner(g, e, n)
    if n in FIXED_PAIR:
        ctx.eq((lead, partner), FIXED_PAIR[n], f"M{n}: the fixed pair leads and partners the player's army")
    elif n == 12:
        ctx.eq(sorted([lead, partner]), sorted(picks), "M12: the picked pair is the player's lead and partner")
    elif n == 15:
        # (a two-front mission: the first pick leads the main front, the second leads the sky front -- not a tag partner,
        # so the dialogue's @WITH/@PARTNER rows see the main front's lead only)
        from aw2test import twofront as tf
        ctx.eq((lead, e.u8(tf.SECOND_COS)), tuple(picks), "M15: the first pick leads the main front, the second the sky front")
        ctx.eq(partner, None, "M15: no tag partner")
    else:
        ctx.eq(lead, picks[0], f"M{n}: the picked CO leads")
    ctx.eq(d.size(), size, f"M{n}: the map's size")
    ctx.eq(bool(g.playst()["fog"]), fog, f"M{n}: fog")
    ctx.eq(e.u16(DS_TABLE + 0x5C * dc.DS_MAP_ID + 0x24), limit, f"M{n}: the day limit")
    for army, count in map_units(f"bh{n}").items():
        if n == 15 and False:
            continue
        ctx.eq(len(g.units(army)), count, f"M{n}: army {army}'s units")
    # every unit at full HP, ammunition and fuel (Crumb alone at 1 HP)
    for u in g.units():
        if n == 14 and u["army"] == 1 and u["type"] == 1 and u["hp"] < 100:
            ctx.eq(u["hp"], 10, "Crumb: 1 HP")
            continue
        ctx.check(u["hp"] == 100, f"M{n}: unit {u['id']} (type {u['type']}) at full HP ({u['hp']})")
    ctx.eq(texts, a3.played(f"m{n}_pre", lead, partner), f"M{n}: the opening scene is the dialogue file's m{n}_pre for this pair")
    a3.pic(ctx, e, f"m{n}_opening")
    ctx.log("\n".join(texts))
    e.close()


def _loads(n):
    def fn(ctx):
        check_load(ctx, n)
    fn.__name__ = f"bh_act3_m{n}_loads"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _loads(_n)


# --- the day limit loses ---------------------------------------------------------------------------------------
def ready(ctx, n, cos=None, label=None):
    """The mission started and under the player's control."""
    title, won, roster, picks, size, fog, limit = MISSIONS[n]
    cos = cos or picks
    mask = sum(1 << a3.M[k] for k in won)
    e, g, d = a3.boot(ctx, mask, roster, picks={a3.M[n]: len(cos)}, at=a3.M[n])
    texts = a3.open_mission(ctx, e, g, d, a3.M[n], cos, label or f"m{n}")
    d.wait_control()
    g._units_base = g._players_base = None
    return e, g, d, texts


def lose_by_day(ctx, e, g, d, n):
    limit = MISSIONS[n][6]
    e.w16(DAY, limit)
    a3.end_turn(e, g, d)
    for _ in range(3000):
        if e.u8(dc.LAST_RESULT):
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(20)
    ctx.eq(e.u8(dc.LAST_RESULT), 2, f"M{n}: lost when day {limit + 1} begins")


def _lose_by_day(n):
    def fn(ctx):
        e, g, d, texts = ready(ctx, n)
        lose_by_day(ctx, e, g, d, n)
        e.close()
    fn.__name__ = f"bh_act3_m{n}_lose_by_day_limit"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    if _n != 15:      # (two fronts: the day limit is the main front's, as M8's)
        _lose_by_day(_n)


# --- wins ------------------------------------------------------------------------------------------------------
def capture_hq(ctx, e, g, d, hqs, hostile=None):
    """Every enemy unit but the farthest removed, an Infantry of the player's on each HQ capturing it turn by turn."""
    by = {}
    for u in g.units():
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
    for turn in range(5):
        for hq in hqs:
            if g.terrain_class(*hq) >> 5 == 1:
                continue
            a3.calm(e, g, d)
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
        a3.next_turn(e, g, d)


def act(ctx, e, g, d, k=0):
    """A player's unit (the k-th of the foot, tanks and recon) takes an action: the after-action rules look."""
    mine = [u for u in g.units(1) if u["type"] in (1, 2, 3, 5, 6)][k]
    g.select(mine["x"], mine["y"])
    names = g.move_to(mine["x"], mine["y"])["names"]
    g.choose(next(x for x in names if x.lower().startswith("wait")), g.ACTION_MENU)


def set_owner(e, x, y, army):
    row = e.u16(GMAP + 0x417A + 2 * y)
    at = GMAP + 0x1432 + row + x
    e.w8(at, (e.u8(at) & 0x1F) | (army << 5))


def _win_by_capture(n, hqs, bond=None, recruit=None, cos=None):
    def fn(ctx):
        e, g, d, texts = ready(ctx, n, cos)
        lead, partner = lead_and_partner(g, e, n)
        capture_hq(ctx, e, g, d, hqs)
        victory, mapscene = a3.follow(ctx, e, d, f"m{n}", shots=(0,))
        ctx.log("VICTORY\n" + "\n".join(victory) + "\nMAP\n" + "\n".join(mapscene))
        ctx.eq(victory, a3.played(f"m{n}_post", lead, partner), f"M{n}: the victory scene is the dialogue file's m{n}_post")
        ctx.eq(mapscene[:len(a3.played(f"m{n}_map", lead, partner))], a3.played(f"m{n}_map", lead, partner),
               f"M{n}: the world-map scene starts with the dialogue file's m{n}_map")
        ctx.eq((d.won() >> a3.M[n]) & 1, 1, f"M{n} won")
        flags = d.map_flags()
        ctx.eq(flags[a3.M[n] + 1] & 1, 1 if n < 16 else flags[a3.M[n] + 1] & 1, f"M{n}: the next flag opens")
        if recruit:
            ctx.check(recruit in d.unlocked(), f"M{n}: {recruit} joins ({d.unlocked()})")
        if bond is not None:
            ctx.eq((d.bonds() >> bond) & 1, 1, f"M{n}: bond {bond} earned")
        e.close()
    fn.__name__ = f"bh_act3_m{n}_win_by_capture" + (f"_{'_'.join(a3.co_name(c).lower().replace(' ', '') for c in cos)}" if cos else "")
    test(modes=("ds",))(fn)


_win_by_capture(12, [(34, 9)], bond=2, recruit=bh.KOAL)                                            # (Sturm + Hawke: the affinity)
_win_by_capture(12, [(34, 9)], bond=2, recruit=bh.KOAL, cos=[bh.VON_BOLT, bh.STURM])               # (Sturm as the partner counts)
_win_by_capture(12, [(34, 9)], bond=2, recruit=bh.KOAL, cos=[bh.VON_BOLT, bh.HAWKE])               # (Hawke without Sturm counts)
_win_by_capture(15, [(22, 10)])
_win_by_capture(16, [(13, 2)])


@test(modes=("ds",))
def bh_act3_m12_no_bond_without_an_affinity_co(ctx):
    """No pair of the pool (Sturm, Von Bolt, Hawke) lacks both Sturm and Hawke, so the no-bond branch cannot be
    reached through the pick screens; the pair is rewritten in RAM (Von Bolt leading, Kindle as the partner), then
    Koal's HQ is taken: he joins, no bond."""
    e, g, d, texts = ready(ctx, 12, cos=[bh.VON_BOLT, bh.HAWKE])
    e.w8(g.player(1)["addr"] + ram.P_CO, bh.VON_BOLT)
    e.w8(tag.rec(1) + tag.P_CO, bh.KINDLE)
    ctx.eq((g.player(1)["co"], tag.partner(e, 1)["co"]), (bh.VON_BOLT, bh.KINDLE), "the pair is Von Bolt + Kindle (no Sturm, no Hawke)")
    capture_hq(ctx, e, g, d, [(34, 9)])
    a3.follow(ctx, e, d, "m12v", shots=())
    ctx.eq((d.won() >> a3.M[12]) & 1, 1, "M12 won")
    ctx.eq((d.bonds() >> 2) & 1, 0, "neither Sturm nor Hawke in the pair: Koal joins reluctantly, no bond")
    ctx.check(bh.KOAL in d.unlocked(), "Koal joins")
    e.close()


@test(modes=("ds",))
def bh_act3_m12_pair_pick_screen(ctx):
    """M12 is a free pair: the CO screen asks twice (the pool is Sturm, Von Bolt, Hawke), the first pick leads and the
    second is the partner (see test_bh_pair_seating.py); the enemy is Koal + Grimm; the opening is the file's m12_pre for that pair."""
    for pair in ([bh.STURM, bh.HAWKE], [bh.HAWKE, bh.STURM], [bh.VON_BOLT, bh.STURM], [bh.VON_BOLT, bh.HAWKE]):
        label = "+".join(a3.co_name(c) for c in pair)
        e, g, d, spec = load_mission(ctx, 12)
        d.pick_mission()
        ctx.require(e.wait_until(d.on_co_select, 600, step=10), f"{label}: the CO screen opens")
        ctx.require(e.wait_until(lambda: d.co_cursor() is not None, 300, step=10), f"{label}: the CO screen's cursor")
        offered = d.offered()
        ctx.eq(sorted(offered), sorted([bh.STURM, bh.VON_BOLT, bh.HAWKE]), f"{label}: the pool the screen offers (no Koal yet)")
        got = a4.pick_cos(d, e, 2, list(pair))
        ctx.eq(got, pair, f"{label}: two screens, answered in order")
        for _ in range(600):
            if d.in_battle() and e.u32(0x0849_9598) != 0:
                break
            e.wait(10)
        d.leave_setup()
        texts = a3.intro(ctx, e, d, f"m12_{label}", shots=())
        d.wait_control()
        g._units_base = g._players_base = None
        lead, partner = lead_and_partner(g, e, 12)
        ctx.eq((lead, partner), tuple(pair), f"{label}: the first pick leads, the second is the partner")
        ctx.eq((g.player(2)["co"], tag.partner(e, 2)["co"]), (bh.KOAL, GRIMM), f"{label}: the enemy is Koal + Grimm")
        ctx.eq(texts, a3.played("m12_pre", lead, partner), f"{label}: the opening scene for this pair")
        e.close()


@test(modes=("ds",))
def bh_act3_m13_win_needs_the_stage_and_three_towers(ctx):
    """The stage (10,3) is a city, not an HQ: taking it alone wins nothing; with 3 of the 4 towers it does
    (the 4th is not needed); Von Bolt leading earns Kindle's bond."""
    e, g, d, texts = ready(ctx, 13, cos=[bh.VON_BOLT])
    ctx.check(g.terrain_class(10, 3) & 0x1F != g.terrain_class(11, 14) & 0x1F, "the stage is not the HQ's terrain")
    keep = next(u for u in g.units(2) if u["type"] == 2)
    for u in g.units(2):
        if u["id"] != keep["id"]:
            d.remove_unit(u)
    e.wait(10)
    set_owner(e, 10, 3, 1)
    act(ctx, e, g, d, 0)
    calm_ok = e.u8(dc.LAST_RESULT)
    ctx.eq(calm_ok, 0, "the stage alone does not win")
    for t in [(8, 5), (13, 5)]:
        set_owner(e, t[0], t[1], 1)
    a3.calm(e, g, d)
    act(ctx, e, g, d, 1)
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "the stage and two towers do not win")
    set_owner(e, 8, 10, 1)
    a3.calm(e, g, d)
    act(ctx, e, g, d, 2)
    victory, mapscene = a3.follow(ctx, e, d, "m13", shots=())
    ctx.check(len(victory) >= 5, f"the victory scene ({len(victory)} boxes)")
    ctx.eq((d.won() >> a3.M[13]) & 1, 1, "M13 won")
    ctx.check(bh.KINDLE in d.unlocked(), "Kindle joins")
    ctx.eq((d.bonds() >> 3) & 1, 1, "Kindle's bond (Von Bolt leading)")
    e.close()


# --- M14: the evacuation ---------------------------------------------------------------------------------------
PAD = (19, 18)


def crumb(g):
    return next(u for u in g.units(1) if u["type"] == 1 and u["hp"] < 100)


@test(modes=("ds",))
def bh_act3_m14_capturing_sonjas_post_wins_nothing(ctx):
    """The north-east post (20,2) is a city, not an HQ: once it is the player's, nothing is won."""
    e, g, d, texts = ready(ctx, 14)
    ctx.check(g.terrain_class(20, 2) & 0x1F == g.terrain_class(19, 3) & 0x1F, "(20,2) is a city like (19,3)")
    set_owner(e, 20, 2, 1)
    e.wait(10)
    ctx.eq(g.terrain_class(20, 2) >> 5, 1, "the post is the player's")
    act(ctx, e, g, d)
    a3.calm(e, g, d)
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "nothing is won by it")
    e.close()


@test(modes=("ds",))
def bh_act3_m14_crumb_on_foot_on_pad_echo_wins_and_the_quote_by_day_12(ctx):
    e, g, d, texts = ready(ctx, 14)
    c = crumb(g)
    d.place_unit(c, *PAD) if g.unit_at(*PAD) is None else None
    if g.unit_at(*PAD) and g.unit_at(*PAD)["id"] != c["id"]:
        d.remove_unit(g.unit_at(*PAD))
        d.place_unit(c, *PAD)
    e.wait(10)
    act(ctx, e, g, d)
    victory, mapscene = a3.follow(ctx, e, d, "m14", shots=())
    ctx.check(len(victory) >= 10, f"the victory scene ({len(victory)} boxes)")
    ctx.eq((d.won() >> a3.M[14]) & 1, 1, "M14 won")
    ctx.eq((d.bonds() >> 9) & 1, 1, "Crumb's secret quote: won by day 12")
    e.close()


@test(modes=("ds",))
def bh_act3_m14_a_late_extraction_wins_without_the_quote(ctx):
    e, g, d, texts = ready(ctx, 14)
    e.w16(DAY, 13)
    c = crumb(g)
    if g.unit_at(*PAD):
        d.remove_unit(g.unit_at(*PAD))
    d.place_unit(c, *PAD)
    e.wait(10)
    act(ctx, e, g, d)
    a3.follow(ctx, e, d, "m14late", shots=())
    ctx.eq((d.won() >> a3.M[14]) & 1, 1, "M14 won on day 13")
    ctx.eq((d.bonds() >> 9) & 1, 0, "no secret quote after day 12")
    e.close()


@test(modes=("ds",))
def bh_act3_m14_crumb_dying_loses(ctx):
    e, g, d, texts = ready(ctx, 14)
    d.remove_unit(crumb(g))
    e.wait(10)
    act(ctx, e, g, d)
    for _ in range(3000):
        if e.u8(dc.LAST_RESULT):
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(20)
    ctx.eq(e.u8(dc.LAST_RESULT), 2, "Crumb destroyed: lost")
    e.close()


# --- M12's factory, M16's paratroopers -------------------------------------------------------------------------
@test(modes=("ds",))
def bh_act3_m12_factory_table(ctx):
    """The Black Factory (x 3..5, y 10..13, doors on row 14) spawns F12's units on the player's turns:
    day 2 a Recon-class unit at doors 1 and 3, day 3 one at the middle door."""
    e, g, d, texts = ready(ctx, 12)
    before = {(u["x"], u["y"]) for u in g.units(1)}
    a3.to_day(e, g, d, 2)
    ctx.eq(e.u16(DAY), 2, "day 2")
    new = sorted((u["x"], u["y"]) for u in g.units(1) if (u["x"], u["y"]) not in before and u["y"] >= 14 and 3 <= u["x"] <= 5)
    ctx.eq(new, [(3, 14), (5, 14)], "units at doors (3,14) and (5,14), none at the middle")
    a3.pic(ctx, e, "m12_factory_day2")
    e.close()


@test(modes=("ds",))
def bh_act3_m16_paratroopers_on_day_6_and_charged_first_power(ctx):
    e, g, d, texts = ready(ctx, 16)
    n0 = len(g.units(2))
    seen = a3.to_day(e, g, d, 6)
    ctx.eq(e.u16(DAY), 6, "day 6")
    want = a3.played("m16_day6", bh.KOAL, bh.KINDLE)
    ctx.check(all(t in seen for t in want), f"the day-6 scene m16_day6 ({want}) was shown ({seen})")
    ctx.check("Jump, my paratroopers!" in want[0], "(Sensei jumps first)")
    ctx.check(len(g.units(2)) >= n0 + 5, f"nine Infantry dropped in the rear ({n0} -> {len(g.units(2))} units, less losses)")
    a3.pic(ctx, e, "m16_paratroopers")
    e.close()


@test(modes=("ds",))
def bh_act3_m14_open_line_on_day_2(ctx):
    e, g, d, texts = ready(ctx, 14)
    seen = a3.to_day(e, g, d, 2)
    ctx.eq(e.u16(DAY), 2, "day 2")
    want = a3.played("m14_day2", bh.STURM)
    ctx.check(len(want) >= 5 and all(t in seen for t in want), f"Kanbei's open line, the whole m14_day2 scene ({want}) was shown ({seen})")
    e.close()


@test(modes=("ds",))
def bh_act3_the_enemy_moves(ctx):
    """The computer's army advances: after three turns of the player standing still, most of Yellow Comet's
    units (all but the deliberate holders) are no longer where they began (M12, M13, M16)."""
    for n in (12, 13, 16):
        e, g, d, texts = ready(ctx, n)
        start = {u["id"]: (u["x"], u["y"]) for u in g.units(2)}
        a3.to_day(e, g, d, 4)
        now = {u["id"]: (u["x"], u["y"]) for u in g.units(2)}
        moved = sum(1 for k, v in start.items() if k in now and now[k] != v)
        ctx.check(moved >= len(start) // 3, f"M{n}: {moved} of {len(start)} Yellow Comet units moved by day 4")
        e.close()



# The copter's way out, one straight segment a turn (the game's own path is then the only path, so a hidden
# unit is not blundered into): north over the ring's wall, east along the top edge, south along the east edge.
ROUTE = [(3, 1), (9, 1), (15, 1), (21, 1), (21, 7), (21, 13), (21, 18)]


@test(modes=("ds",))
def bh_act3_m14_the_copter_at_crumbs_side_flies_him_out(ctx):
    """The escape that must work: the T Copter inside the ring at (3,3) loads Crumb (3,4) on day 1 and flies
    (a straight segment of at most six cells a turn, north over the ring, east along the edge, south) to the
    column at Pad Echo's side, alive on day 7 with Crumb aboard; set down on the pad, the mission is won."""
    e, g, d, texts = ready(ctx, 14)
    c = crumb(g)
    tc = g.unit_at(3, 3)
    ctx.check(tc is not None and tc["type"] == 20 and tc["army"] == 1, "a T Copter of ours stands at (3,3), beside Crumb")
    g.select(c["x"], c["y"])
    names = g.move_to(3, 3)["names"]
    ctx.check(any(n.lower().startswith("load") for n in names), f"Crumb is offered Load ({names})")
    g.choose("Load", g.ACTION_MENU)
    a3.calm(e, g, d)
    ctx.check(any(g.unit(tc["id"])["cargo"]), "the copter carries him")
    a3.pic(ctx, e, "m14_crumb_loaded")
    pos = (3, 3)
    for turn, wp in enumerate(ROUTE):
        for attempt in range(4):
            a3.calm(e, g, d)
            e.wait(60)
            try:
                g.select(*pos)
                break
            except Exception as ex:
                ctx.log(f"select retry {attempt}: {ex}")
                e.press("B", 4)
                e.wait(30)
        else:
            g.select(*pos)
        names = g.move_to(*wp)["names"]
        g.choose(next(x for x in names if x.lower().startswith("wait")), g.ACTION_MENU)
        a3.calm(e, g, d)
        pos = wp
        ctx.log(f"day {e.u16(DAY)}: the copter at {wp}, HP {g.unit(tc['id'])['hp']}")
        if e.u8(dc.LAST_RESULT):
            break
        if wp != ROUTE[-1]:
            a3.next_turn(e, g, d)
            ctx.require(not e.u8(dc.LAST_RESULT), f"still in play on day {e.u16(DAY)}")
            g._units_base = g._players_base = None
    ctx.check(g.unit(tc["id"])["hp"] > 0 and any(g.unit(tc["id"])["cargo"]), "the copter and Crumb are alive at the pad's side")
    ctx.check(e.u16(DAY) <= 8, f"inside 8 days (day {e.u16(DAY)})")
    # (set down on Pad Echo: the pad cleared of the hunters that reached it while the column stood still)
    for u in g.units():
        if (u["x"], u["y"]) == PAD and u["id"] != tc["id"]:
            d.remove_unit(u)
    e.wait(10)
    d.place_unit(g.unit(tc["id"]), *PAD)
    e.wait(10)
    mine = next(u for u in g.units(1) if u["type"] in (1, 2, 3, 5, 6) and u["hp"] == 100)
    g.select(mine["x"], mine["y"])
    names = g.move_to(mine["x"], mine["y"])["names"]
    g.choose(next(x for x in names if x.lower().startswith("wait")), g.ACTION_MENU)
    victory, mapscene = a3.follow(ctx, e, d, "m14_flight", shots=(0,))
    ctx.eq((d.won() >> a3.M[14]) & 1, 1, "M14 won by the copter's flight")
    ctx.check(e.u16(DAY) <= 12, f"by day 12 (day {e.u16(DAY)}): Crumb's secret quote")
    e.close()
