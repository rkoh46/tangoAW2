"""BH Campaign, Act V (Orange Star: M29 The Orange Gate and M30 Nell's Stand: tango-gamesupport-aw2/src/bh_act5.rs)."""

import os

from aw2test import bhact5 as a5
from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test.harness import test

GMAP = 0x0201E450
DS_TABLE = 0x08E00000
ALL = (1 << 10) - 1   # every roster CO but Sonja (the secret mission's recruit: with her the CO screen has a second country tab and the partner pick cannot reach the Black Hole tab)
# number: (title, won mask, CO picks, armies: (colour, CO), map size, day limit)
MISSIONS = {
    29: ("The Orange Gate", a5.WON(28), [bh.STURM], [(5, bh.STURM), (1, None)], (34, 28), 32),
    30: ("Nell's Stand", a5.WON(29), [bh.STURM, bh.CLONE_ANDY], [(5, None), (1, None)], (36, 28), 34),
}
MAP_FILES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tango-gamesupport-aw2", "five", "bh")


def map_units(name):
    out = {}
    for line in open(os.path.join(MAP_FILES, name + ".txt")):
        f = line.split()
        if f and f[0] == "unit":
            out[int(f[1])] = out.get(int(f[1]), 0) + 1
    return out


def load_mission(ctx, n):
    title, won, picks, armies, size, limit = MISSIONS[n]
    e, g, d = a5.boot(ctx, won, ALL, picks={a5.M[n]: len(picks)}, at=a5.M[n])
    return e, g, d, MISSIONS[n]


def check_load(ctx, n):
    e, g, d, spec = load_mission(ctx, n)
    title, won, picks, armies, size, limit = spec
    units = map_units(f"bh{n:02d}")
    texts = a5.open_mission(ctx, e, g, d, a5.M[n], picks, f"m{n}")
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), a5.M[n], f"M{n}: the mission")
    ctx.eq(d.size(), size, f"M{n}: the map's size")
    for army, count in units.items():
        ctx.eq(len(g.units(army)), count, f"M{n}: army {army}'s units")
    a5.pic(ctx, e, f"m{n}_opening")
    ctx.log("\n".join(texts))
    e.close()


def _loads(n):
    def fn(ctx):
        check_load(ctx, n)
    fn.__name__ = f"bh_act5_m{n}_loads"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _loads(_n)


def _pictures(n):
    def fn(ctx):
        from aw2test import stitch
        e, g, d, spec = load_mission(ctx, n)
        title, won, picks, armies, size, limit = spec
        # the full map in the Setup phase: the deployment as designed, before any structure fires
        a5.open_mission(ctx, e, g, d, a5.M[n], picks, f"m{n}", setup_only=True)
        g._units_base = g._players_base = None
        ctx.check(all(u["hp"] == 100 for a_ in (1, 2) for u in g.units(a_)), "every unit starts at full HP (Setup phase)")
        stitch.IMAGES = a5.SHOTS or stitch.IMAGES
        w, h = d.size()
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}", w, h, exclude=lambda tx, ty: ty == 0 and 5 <= tx <= 10)   # (the Setup banner sits on the screen's top)
        d.leave_setup()
        texts = a5.intro(ctx, e, d, f"m{n}", (0,))
        d.wait_control()
        g._units_base = g._players_base = None
        a5.pic(ctx, e, f"m{n}_opening")
        for _ in range(6):
            a5.calm(e, g, d)
            e.wait(150)
        FRONT = {29: (17, 13), 30: (18, 17)}[n]
        g.goto(*FRONT)
        e.wait(40)
        a5.pic(ctx, e, f"m{n}_opening_front")
        g._units_base = g._players_base = None
        hurt = [(u["army"], u["type"], u["x"], u["y"], u["hp"]) for a_ in (1, 2) for u in g.units(a_) if u["hp"] < 100]
        ctx.log(f"units under full HP after the first turn start: {hurt}")
        ctx.check(not hurt, "nothing is hit at the first turn start")
        e.close()
    fn.__name__ = f"bh_act5_m{n}_pictures"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _pictures(_n)


INVENTIONS = 0x02028360


def inventions(e):
    out = []
    for i in range(24):
        b = e.read(INVENTIONS + 8 * i, 8)
        if any(b):
            out.append((i, list(b)))
    return out


@test(modes=("ds",))
def bh_act5_m29_deathray_probe(ctx):
    """The Deathray's real area (docs/AW2.md: columns x..x+2 from row y+3 to the bottom edge, enemies only), measured: enemy
    Infantry stand in a row of cells; its counter is set to fire at the next turn start; the cells that lost HP are the area."""
    e, g, d, spec = load_mission(ctx, 29)
    a5.open_mission(ctx, e, g, d, a5.M[29], spec[2], "m29")
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.log("inventions: " + str(inventions(e)))
    a5.calm(e, g, d)
    # every Orange unit stranded without fuel (no moves), a column of them across the map
    us = g.units(2)
    cells = [(x, y) for y in range(4, 12) for x in (15, 16, 17, 18, 19)]
    for u, c in zip(us, cells):
        d.place_unit(u, *c)
    for u in g.units(2):
        e.w8(g.unit_addr(u["id"]) + 6, 0)
        e.w8(g.unit_addr(u["id"]) + 4, 100)
    mine = g.units(1)
    ctx.log("army 1 at the start: " + str(sorted((u["x"], u["y"], u["type"], u["hp"]) for u in mine)))
    for u, c in zip(mine, [(16, 20), (17, 20), (18, 20), (16, 21), (17, 21), (18, 21), (15, 20), (19, 20)]):
        d.place_unit(u, *c)
        e.w8(g.unit_addr(u["id"]) + 6, 0)
    before1 = {u["id"]: (u["x"], u["y"], u["hp"]) for u in g.units(1)}
    before = {u["id"]: (u["x"], u["y"], u["hp"]) for u in g.units(2)}
    e.w8(INVENTIONS + 6, 1)            # the Deathray fires at the next turn start
    ctx.log("before: " + str(sorted((u["x"], u["y"], u["type"], u["hp"]) for u in g.units(2))))
    a5.next_turn(e, g, d)
    for _ in range(60):
        if e.u16(0x03004080) >= 2 and g.current_army() == 1:
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(60)
    a5.calm(e, g, d)
    g._units_base = g._players_base = None
    hurt = [(u["type"], u["x"], u["y"], u["hp"]) for u in g.units(2) if u["id"] in before and u["hp"] < before[u["id"]][2]]
    ctx.log("hurt after the turn: " + str(sorted(hurt)))
    hurt1 = [(u["type"], u["x"], u["y"], u["hp"]) for u in g.units(1) if u["id"] in before1 and u["hp"] < before1[u["id"]][2]]
    ctx.log("own units hurt: " + str(sorted(hurt1)))
    import json
    json.dump(sorted((x, y) for (_, x, y, _) in hurt), open(os.path.join(os.environ.get("SP", "/tmp"), "deathray_hits.json"), "w"))
    ctx.log("army 2 after: " + str(sorted((u["x"], u["y"], u["type"], u["hp"]) for u in g.units(2))))
    ctx.log("army 1 after: " + str(sorted((u["x"], u["y"], u["type"], u["hp"]) for u in g.units(1))))
    ctx.log("day " + str(e.u16(0x03004080)))
    e.close()


@test(modes=("ds",))
def bh_act5_m30_nell_pushes_and_uses_her_powers(ctx):
    """With the player passing every turn: Nell's army leaves its walls (the roles in bh_act5.rs's doc), the camp's
    structures wear it down at the moat, and her powers come on days 3 and 7 (the meter scripts)."""
    e, g, d, spec = load_mission(ctx, 30)
    a5.open_mission(ctx, e, g, d, a5.M[30], spec[2], "m30")
    d.wait_control()
    g._units_base = g._players_base = None
    for _ in range(6):
        a5.calm(e, g, d)
        e.wait(100)
    start = {u["id"]: (u["x"], u["y"]) for u in g.units(2)}
    log = []
    for day in range(2, 11):
        a5.to_day(e, g, d, day)
        a5.calm(e, g, d)
        g._units_base = g._players_base = None
        p2 = g.player(2)
        us = g.units(2)
        moved = sum(1 for u in us if u["id"] in start and (u["x"], u["y"]) != start[u["id"]])
        south = sum(1 for u in us if u["y"] >= 16)
        log.append((day, len(us), len(g.units(1)), moved, south, p2["co"], p2["powers_used"], p2["charge"]))
        ctx.log(f"day {day}: orange {len(us)} units ({moved} moved from their start, {south} south of the moat), black hole {len(g.units(1))}, "
                f"Nell uses {p2['powers_used']} charge {p2['charge']} mode {p2['co_mode']}")
    ctx.check(any(r[3] > 10 for r in log), "Nell's army leaves its start cells (more than ten units moved)")
    ctx.check(log[-1][6] >= 2, "Nell has used both a power and a Super by day 10")
    e.close()


def play(ctx, e, g, d, bot, day_to, label, army=1):
    """The bot plays the player's turns until the player's turn of day `day_to` (or the battle ends)."""
    while e.u16(0x03004080) < day_to and not e.u8(dc.LAST_RESULT):
        bot.play_turn(army)
        a5.calm(e, g, d) if not e.u8(dc.LAST_RESULT) else None
        for _ in range(4000):
            if e.u8(dc.LAST_RESULT) or g.current_army() == army:
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(20)
        g._units_base = g._players_base = None
        if e.u8(dc.LAST_RESULT):
            break
        us = g.units(2)
        ctx.log(f"{label} day {e.u16(0x03004080)}: orange {len(us)} (Great Hall owner {g.terrain_class(18, 3) >> 5}), black hole {len(g.units(1))}, "
                f"Nell {g.player(2)['co']} uses {g.player(2)['powers_used']}")


@test(modes=("ds",))
def bh_act5_m30_balance_run(ctx):
    """The intended strategy played by the test bot (docs/BH_CAMPAIGN.md M30): dig in on the South Field behind the structures
    until Nell's Super on day 7, then counter and push for the Great Hall."""
    from aw2test.bot import Bot
    e, g, d, spec = load_mission(ctx, 30)
    a5.open_mission(ctx, e, g, d, a5.M[30], spec[2], "m30")
    d.wait_control()
    g._units_base = g._players_base = None
    a5.calm(e, g, d)
    bot = Bot(d, log=lambda s: None, stance="defend", garrison=True)
    play(ctx, e, g, d, bot, 10, "defend")
    bot2 = Bot(d, log=lambda s: None, stance="attack", garrison=True, goals=[(18, 3)])
    play(ctx, e, g, d, bot2, 24, "push")
    ctx.log(f"result {e.u8(dc.LAST_RESULT)} day {e.u16(0x03004080)}")
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "the camp still stands on day 24 (the bot does not win; a human has to)")
    ctx.check(len(g.units(1)) >= 6, f"Black Hole still has an army ({len(g.units(1))} units) at the end")
    e.close()


def my_turn(e, g, d):
    """End the turn and wait until it is the player's again (through the other army's whole turn and its dialogue)."""
    a5.next_turn(e, g, d)
    for _ in range(400):
        if e.u8(dc.LAST_RESULT) or (g.current_army() == 1 and not d.scripts_running()):
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(30)
    for _ in range(5):                 # (the structures fire at the turn start, a script after it)
        a5.calm(e, g, d)
        e.wait(150)
    g._units_base = g._players_base = None


def capture(e, g, d, x, y):
    a5.calm(e, g, d)
    g.select(x, y)
    g.move_to(x, y)
    g.choose("Capt", g.ACTION_MENU)
    a5.calm(e, g, d)


@test(modes=("ds",))
def bh_act5_m30_stage_two_is_the_same_army_under_andy(ctx):
    """The Great Hall falls (two captures): Orange Star is not defeated; the same army (2) goes on with Andy as its CO
    (his own meter), the Rail Yard (the map's second HQ) as its HQ, reserves on the platform and +10000 funds; capturing
    the Rail Yard then wins. Pictures: the stage-two state."""
    from aw2test import stitch
    e, g, d, spec = load_mission(ctx, 30)
    a5.open_mission(ctx, e, g, d, a5.M[30], spec[2], "m30")
    d.wait_control()
    g._units_base = g._players_base = None
    for _ in range(4):
        a5.calm(e, g, d)
        e.wait(100)
    # Nell's army as it stands at about day 8: some twenty units, held where they are (no fuel), none near the keep
    keep = [u for u in g.units(2) if u["x"] >= 22 or u["y"] >= 12]
    keep = keep[::2][:20]
    for u in g.units(2):
        if u["id"] not in {k["id"] for k in keep}:
            d.remove_unit(u)
    for u in keep:
        e.w8(g.unit_addr(u["id"]) + 6, 0)
    g._units_base = g._players_base = None
    n_before = len(g.units(2))
    funds_before = e.u32(g.player(2)["addr"])
    mine = next(u for u in g.units(1) if u["type"] == 1)
    d.place_unit(mine, 18, 3)
    e.wait(10)
    g._units_base = g._players_base = None
    capture(e, g, d, 18, 3)
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "the first capture action: the battle goes on")
    my_turn(e, g, d)
    ctx.eq(g.player(2)["co"], bh.NELL_ID if hasattr(bh, "NELL_ID") else 0, "stage one: Nell leads Orange Star")
    capture(e, g, d, 18, 3)
    a5.calm(e, g, d)
    for _ in range(6):
        e.wait(60)
        a5.calm(e, g, d)
    g._units_base = g._players_base = None
    ctx.eq(g.terrain_class(18, 3) >> 5, 1, "the Great Hall is Black Hole's")
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "the battle goes on: Orange Star is not defeated by the loss of the Great Hall")
    p2 = g.player(2)
    ctx.eq(p2["co"], 1, "stage two: Andy leads the same army")
    ctx.eq(p2["powers_used"], 0, "Andy's own count of powers")
    cost = e.u32(0x0)  if False else None
    ctx.check(p2["charge"] > 0, f"Andy's meter is his own and charged ({p2['charge']})")
    us = g.units(2)
    reserve_cells = {(u["x"], u["y"]) for u in us if u["x"] >= 32 and u["y"] <= 10}
    ctx.check(len(reserve_cells) >= 12, f"the reserves stand on the Rail Yard ({len(reserve_cells)} units)")
    ctx.check(len(us) <= 50, "the army cap holds")
    ctx.log(f"army 2: {n_before} units before, {len(us)} after; funds {funds_before} -> {e.u32(p2['addr'])}")
    a5.pic(ctx, e, "m30_stage2_opening")
    stitch.IMAGES = a5.SHOTS or stitch.IMAGES
    w, h = d.size()
    g.goto(0, 0)
    stitch.stitch(ctx, g, "m30_stage2", w, h)
    # the Rail Yard falls: a win
    g._units_base = g._players_base = None
    for u in g.units(2):
        if abs(u["x"] - 33) + abs(u["y"] - 6) <= 14:     # (nothing near to shoot the capturer in the test)
            d.remove_unit(u)
    g._units_base = g._players_base = None
    a5.calm(e, g, d)
    mine = next(u for u in g.units(1) if u["type"] in (1, 2) and (u["x"], u["y"]) != (18, 3))
    d.place_unit(mine, 33, 7)
    e.wait(10)
    g._units_base = g._players_base = None
    u0 = g.unit_at(33, 7)
    ctx.log(f"unit_at(33,6): {u0}; cursor {g.cursor()}; army {g.current_army()}; day {e.u16(0x03004080)}")
    ctx.log("at the Rail Yard: " + str([(u["army"], u["type"]) for a_ in (1, 2) for u in g.units(a_) if (u["x"], u["y"]) == (33, 6)]))
    g.select(33, 7)
    g.move_to(33, 6)
    g.choose("Capt", g.ACTION_MENU)
    a5.calm(e, g, d)
    my_turn(e, g, d)
    ctx.log(f"before the second capture: {g.unit_at(33, 6)} army {g.current_army()} day {e.u16(0x03004080)}")
    capture(e, g, d, 33, 6)
    for _ in range(30):
        if e.u8(dc.LAST_RESULT):
            break
        e.press("A", 4)
        e.wait(60)
    ctx.eq(e.u8(dc.LAST_RESULT), 1, "capturing the Rail Yard wins the battle")
    e.close()


@test(modes=("ds",))
def bh_act5_m29_laser_probe(ctx):
    """The Laser (8,8): who its row 8 and column 8 hurt at the next turn start (enemy and own units stranded without fuel on them)."""
    e, g, d, spec = load_mission(ctx, 29)
    a5.open_mission(ctx, e, g, d, a5.M[29], spec[2], "m29")
    d.wait_control()
    g._units_base = g._players_base = None
    a5.calm(e, g, d)
    orange = g.units(2)
    mine = g.units(1)
    oc = [(x, 8) for x in (14, 15, 16)] + [(8, y) for y in (17, 18, 19, 22)] + [(8, 12), (8, 13)]
    mc = [(x, 8) for x in (20, 21, 22)] + [(8, y) for y in (10, 11)] + [(25, 7), (25, 9)]
    for u, c in zip(orange, oc):
        d.place_unit(u, *c)
    for u, c in zip(mine, mc):
        d.place_unit(u, *c)
    for u in g.units(1) + g.units(2):
        e.w8(g.unit_addr(u["id"]) + 6, 0)
    g._units_base = g._players_base = None
    snap = {(u["army"], u["id"]): u["hp"] for a_ in (1, 2) for u in g.units(a_)}
    a5.next_turn(e, g, d)
    for _ in range(60):
        if e.u16(0x03004080) >= 2 and g.current_army() == 1:
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(60)
    a5.calm(e, g, d)
    g._units_base = g._players_base = None
    for a_ in (1, 2):
        hurt = [(u["x"], u["y"], u["hp"]) for u in g.units(a_) if snap.get((a_, u["id"]), 0) > u["hp"]]
        ctx.log(f"army {a_} hurt: {sorted(hurt)}")
    e.close()


@test(modes=("ds",))
def bh_act5_m30_balance_turtle(ctx):
    """The kill-zone version of the intended strategy: every unit stays where it was deployed (the camp behind the moat, the structures
    covering the crossings) and fires at what comes into reach, to day 10."""
    from aw2test.bot import Bot
    e, g, d, spec = load_mission(ctx, 30)
    a5.open_mission(ctx, e, g, d, a5.M[30], spec[2], "m30")
    d.wait_control()
    g._units_base = g._players_base = None
    a5.calm(e, g, d)
    start = len(g.units(1))
    bot = Bot(d, log=lambda s: None, stance="defend", garrison=True, hold=set(range(1, 30)))
    play(ctx, e, g, d, bot, 16, "turtle")
    ctx.log(f"result {e.u8(dc.LAST_RESULT)} day {e.u16(0x03004080)}")
    e.close()


@test(modes=("ds",))
def bh_act5_m30_cannon_reach_probe(ctx):
    """How far the Black Cannons (6,22), (30,22) reach at the first turn start: one Orange Megatank at (X, Y) (the environment's PROBE_X, PROBE_Y),
    every other Orange unit far in the north (on the Inner Bailey's top rows), is hit or not."""
    px, py = int(os.environ.get("PROBE_X", "18")), int(os.environ.get("PROBE_Y", "13"))
    e, g, d, spec = load_mission(ctx, 30)
    a5.open_mission(ctx, e, g, d, a5.M[30], spec[2], "m30", setup_only=True)
    g._units_base = g._players_base = None
    us = g.units(2)
    far = [(x, 1) for x in range(3, 31)] + [(x, 2) for x in range(3, 31)]
    mega = next(u for u in us if u["type"] == 4)
    i = 0
    for u in us:
        if u["id"] == mega["id"]:
            d.place_unit(u, px, py)
        else:
            d.place_unit(u, *far[i]); i += 1
    for u in g.units(1):
        pass
    d.leave_setup()
    a5.intro(ctx, e, d, "m30")
    d.wait_control()
    for _ in range(6):
        a5.calm(e, g, d)
        e.wait(150)
    g._units_base = g._players_base = None
    hurt = [(u["type"], u["x"], u["y"], u["hp"]) for u in g.units(2) if u["hp"] < 100]
    ctx.log(f"probe ({px},{py}): orange hurt {hurt}; black hole hurt {[(u['x'], u['y'], u['hp']) for u in g.units(1) if u['hp'] < 100]}")
    e.close()


def scene_shots(ctx, e, g, d, prefix, max_frames=6000, patience=60):
    """A real screenshot of every dialogue box shown (A through them): prefix_1, prefix_2 ..."""
    texts, last, stable, n = [], None, 0, 0
    quiet = 0
    while n < max_frames:
        t = d.text_shown()
        stable = stable + 1 if t and t == last else 0
        last = t
        if t and stable == 5 and (not texts or texts[-1] != a5.clean(t)):
            texts.append(a5.clean(t))
            e.wait(100)           # (the box types its text out)
            a5.pic(ctx, e, f"{prefix}_{len(texts)}")
        if d.scripts_running():
            quiet = 0
            if stable >= 8:
                e.press("A", 4)
                stable = 0
        else:
            quiet += 1
            if quiet > patience:
                break
        e.wait(4)
        n += 4
    return texts


@test(modes=("ds",))
def bh_act5_m30_takeover_proof(ctx):
    """Real screenshots of the stage-two takeover (Sturm + Clone Andy): the capture, no Victory, the dialogue, Andy's CO panel, the
    Rail Yard HQ, the reserves, Nell's survivors, Andy's turn, the duel, and the Rail Yard's capture winning."""
    e, g, d, spec = load_mission(ctx, 30)
    a5.open_mission(ctx, e, g, d, a5.M[30], spec[2], "m30")
    d.wait_control()
    g._units_base = g._players_base = None
    for _ in range(4):
        a5.calm(e, g, d)
        e.wait(100)
    # Nell's army as it stands mid-battle: about half, none near the keep
    keepers = [u for u in g.units(2) if abs(u["x"] - 18) + abs(u["y"] - 3) > 9]
    keepers = keepers[::2]
    ids = {k["id"] for k in keepers}
    for u in g.units(2):
        if u["id"] not in ids:
            d.remove_unit(u)
    g._units_base = g._players_base = None
    n_before = len(g.units(2))
    mine = next(u for u in g.units(1) if u["type"] == 1)
    d.place_unit(mine, 18, 4)
    e.wait(10)
    g._units_base = g._players_base = None
    # (the first of the two capture actions: stand on the Great Hall and capture)
    g.select(18, 4)
    g.move_to(18, 3)
    g.goto(18, 3)
    a5.pic(ctx, e, "m30_s1_a_before_capture")
    g.choose("Capt", g.ACTION_MENU)
    a5.calm(e, g, d)
    my_turn(e, g, d)
    ctx.eq(g.player(2)["co"], 0, "stage one: Nell leads Orange Star")
    a5.pic(ctx, e, "m30_s4_a_nell_panel_stage_one")
    g.goto(18, 3)
    a5.pic(ctx, e, "m30_s1_b_capturing_second_action")
    g.select(18, 3)
    g.move_to(18, 3)
    g.choose("Capt", g.ACTION_MENU)
    texts = []
    for i in range(12):                      # the capture completes: the HQ flips, the scene plays
        e.wait(45)
        a5.pic(ctx, e, f"m30_s1_c_flip{i}")
        if d.scripts_running():
            break
    texts = scene_shots(ctx, e, g, d, "m30_s3_line")
    ctx.log("takeover dialogue: " + " | ".join(texts))
    a5.calm(e, g, d)
    g._units_base = g._players_base = None
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "no Victory: the battle goes on")
    a5.pic(ctx, e, "m30_s2_no_victory")
    ctx.eq(g.player(2)["co"], 1, "Andy leads Orange Star")
    ctx.log(f"fall day var {e.u8(0x0203FD7C)}, now day {e.u16(0x03004080)}")
    # the Rail Yard and the reserves, Nell's survivors
    g.goto(33, 6)
    e.wait(60)
    a5.pic(ctx, e, "m30_s5_rail_yard_hq")
    g.goto(33, 8)
    e.wait(60)
    a5.pic(ctx, e, "m30_s5_b_reserves")
    surv = next((u for u in g.units(2) if u["x"] < 31 and u["id"] in ids), None)
    if surv:
        g.goto(surv["x"], surv["y"])
        e.wait(60)
        a5.pic(ctx, e, "m30_s6_nells_survivor")
    ctx.log(f"orange units {n_before} -> {len(g.units(2))}")
    # the CO info page (map menu > CO): ours first, then RIGHT to the other armies' pages
    try:
        g.open_map_menu()
        e.wait(30)
        g.choose("CO", g.MAP_MENU)
        e.wait(120)
        a5.pic(ctx, e, "m30_s4_c_co_page_ours")
        for k in range(3):
            e.press("RIGHT", 6)
            e.wait(120)
            a5.pic(ctx, e, f"m30_s4_d_co_page_right{k}")
        for _ in range(4):
            e.press("B", 4)
            e.wait(40)
        a5.calm(e, g, d)
    except Exception as ex:
        ctx.log(f"CO page: {ex}")
    # Andy's first turn: end the turn and shoot the computer's turn
    d0 = e.u16(0x03004080)
    a5.end_turn(e, g, d)
    shot = 0
    first_lines = []
    for it in range(900):
        if e.u8(dc.LAST_RESULT):
            break
        t = d.text_shown()
        if t and a5.clean(t) not in first_lines:
            e.wait(100)
            first_lines.append(a5.clean(t))
            a5.pic(ctx, e, f"m30_s7_first_turn_line_{len(first_lines)}")
        if d.scripts_running():
            e.press("A", 4)
        elif g.current_army() == 2 and shot < 8 and it % 25 == 0:
            a5.pic(ctx, e, f"m30_s7_andy_turn{shot}")
            shot += 1
        if g.current_army() == 1 and e.u16(0x03004080) > d0 and not d.scripts_running() and it > 40:
            quiet_turn = locals().get("quiet_turn", 0) + 1
            if quiet_turn > 120:
                break
        e.wait(8)
    ctx.log("Andy's turn-start lines: " + " | ".join(first_lines))
    for _ in range(4):
        a5.calm(e, g, d)
        e.wait(100)
    a5.pic(ctx, e, "m30_s7_z_back_to_us")
    # the scene at the start of our turn after Andy's (his first-turn line), then the next turn's (the duel)
    ctx.log(f"vars: fall {e.u8(0x0203FD7C)} duel {e.u8(0x0203FD7D)} first {e.u8(0x0203FD7E)}")
    ctx.log(f"after Andy's turn: day {e.u16(0x03004080)} army {g.current_army()}")
    for k in range(2):
        d0 = e.u16(0x03004080)
        a5.calm(e, g, d)
        a5.end_turn(e, g, d)
        for _ in range(300):
            if e.u8(dc.LAST_RESULT) or (g.current_army() == 1 and e.u16(0x03004080) > d0):
                break
            if d.scripts_running():
                scene_shots(ctx, e, g, d, f"m30_s9_turn{k}_cpu_line")
            e.wait(60)
        texts = scene_shots(ctx, e, g, d, f"m30_s9_turn{k}_line", max_frames=6000, patience=700)
        ctx.log(f"turn {k} scenes: " + " | ".join(texts))
    for _ in range(4):
        a5.calm(e, g, d)
        e.wait(100)
    # the Rail Yard falls
    g._units_base = g._players_base = None
    for u in g.units(2):
        if abs(u["x"] - 33) + abs(u["y"] - 6) <= 14:
            d.remove_unit(u)
    g._units_base = g._players_base = None
    mine = next(u for u in g.units(1) if u["type"] in (1, 2))
    d.place_unit(mine, 33, 7)
    e.wait(10)
    g._units_base = g._players_base = None
    g.select(33, 7)
    g.move_to(33, 6)
    g.choose("Capt", g.ACTION_MENU)
    a5.calm(e, g, d)
    my_turn(e, g, d)
    g.select(33, 6)
    g.move_to(33, 6)
    g.choose("Capt", g.ACTION_MENU)
    for i in range(60):
        e.wait(40)
        if i % 4 == 0:
            a5.pic(ctx, e, f"m30_s8_win{i // 4:02d}")
        if d.scripts_running():
            e.press("A", 4)
        if e.u8(dc.LAST_RESULT):
            break
    for k in range(4):
        e.wait(120)
        a5.pic(ctx, e, f"m30_s8_victory{k}")
    for _ in range(40):                  # (A through the results to the world map: the result is then recorded)
        if e.u8(dc.LAST_RESULT):
            break
        e.press("A", 4)
        e.wait(60)
    ctx.eq(e.u8(dc.LAST_RESULT), 1, "capturing the Rail Yard gives the Victory screen")
    e.close()
