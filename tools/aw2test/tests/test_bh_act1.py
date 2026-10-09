"""The BH Campaign's Act I (bh_act1.rs): M1 Storm Landing (Von Bolt's recruit
mission), M2 The Sleeping Foundry (a Black Factory that wakes on day 3) and M3
Blockade Runner (a naval tag battle). Each mission: it loads, the opening scene,
a forced win with its unlocks and the next flag, its lose conditions, the bond,
the reachability of its map, a mission saved halfway and continued. Pictures:
AW2TEST_PICS=<dir>."""

import os
import shutil

from aw2test import bhcampaign as bh
from aw2test import bhtext
from aw2test import dscampaign as dc
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game, NavError
from aw2test.harness import test
from aw2test.stitch import stitch

PICS = os.environ.get("AW2TEST_PICS")
MAP = 0x0201E450
# The picks the CO screen asks for: M1 fixed, M2 one, M3 a fixed pair.
PICKS = {0: 0, 1: 1, 2: 0}
M = {1: "storm_landing", 2: "sleeping_foundry", 3: "blockade_runner"}


def export(ctx, path, name):
    """Keeps a picture in the output and, with AW2TEST_PICS, in that folder (upscaled)."""
    if not path or not PICS:
        return
    os.makedirs(PICS, exist_ok=True)
    try:
        from PIL import Image
        im = Image.open(path)
        im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(os.path.join(PICS, name + ".png"))
    except ImportError:
        shutil.copy(path, os.path.join(PICS, name + os.path.splitext(path)[1]))


def boot(ctx, save=None):
    e = Emu(save=save or paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = bh.BhCampaign(g)
    d.picks = PICKS
    return e, g, d


def won_mask(k):
    return (1 << k) - 1                 # missions 1..k won (k counted from 0)


def unlocked(k):
    return 0b11 if k >= 1 else 0b1      # Sturm; Von Bolt once M1 is won


def enter(ctx, k, cos=None, save=None, wait=True):
    """Continue with missions before `k` (0-based) won, pick mission k, its
    CO screen (`cos` the preferred COs) and the opening (not played through
    when wait is False). Returns (e, g, d)."""
    e, g, d = boot(ctx, save)
    d.start_at(won_mask=won_mask(k), unlocked_mask=unlocked(k))
    d.pick_mission()
    if PICKS[k] and cos is not None:
        d.choose_cos(PICKS[k], prefs=cos)
    if wait:
        d.wait_map()
    g._units_base = g._players_base = None
    return e, g, d


def units_of(g, army):
    return [(u["type"], u["x"], u["y"]) for u in g.units(army=army)]


@test(modes=("ds",))
def bh_act1_pictures(ctx):
    """Pictures for review (AW2TEST_PICS=<dir> keeps them there, upscaled): each mission's whole map
    (the sweep hides the panels), and the world map with Act I's flags: M1 and M2 cleared (starred),
    M3 open. The opening frames and a dialogue frame come from the missions' own tests."""
    for k in (0, 1, 2):
        e, g, d = enter(ctx, k, cos=[bh.STURM])
        w, h = d.size()
        path = stitch(ctx, g, f"m{k + 1}", w, h)
        export(ctx, path, f"m{k + 1}_{M[k + 1]}_full")
        e.close()
    e, g, d = boot(ctx)
    d.start_at(won_mask=0b011, unlocked_mask=0b11)
    d.wait_world_map()
    e.wait(90)
    ctx.eq(d.map_flags()[:3], [2, 2, 1], "M1 and M2 cleared, M3 open")
    d.cleared_flags()
    export(ctx, e.shot(os.path.join(ctx.out, "world_map")), "world_map_act1")
    e.close()


HERE = os.path.dirname(os.path.abspath(__file__))
BH_MAPS = os.path.join(paths.REPO, "tango-gamesupport-aw2", "five", "bh")
SIZE = {0: (22, 15), 1: (22, 24), 2: (26, 16)}
PLAYER_CO = {0: bh.STURM, 1: bh.STURM, 2: bh.STURM}
ENEMY_CO = {0: bh.VON_BOLT, 1: 17, 2: 9}          # Von Bolt, Jess, Drake (Eagle his partner)
FUNDS = {0: (6000, 20000), 1: (0, 8000), 2: (12000, 20000)}
DAY_LIMIT = {0: 20, 1: 18, 2: 25}
HQS = {0: ((2, 12), (19, 2)), 1: ((11, 1), (11, 22)), 2: ((2, 8), (24, 8))}
CLASS_HQ, CLASS_CITY, CLASS_BASE, CLASS_AIRPORT, CLASS_PORT, CLASS_SHOAL = 8, 6, 0xE, 0xA, 0xB, 13


def map_units(k):
    """The units of mission k's map file: (army, type, x, y) lines."""
    out = []
    for line in open(os.path.join(BH_MAPS, f"bh0{k + 1}.txt")):
        f = line.split()
        if f and f[0] == "unit":
            out.append(tuple(int(x) for x in f[1:5]))
    return out


def funds(g, army):
    return g.e.u32(g.player(army)["addr"])


def terrain(g, x, y):
    c = g.terrain_class(x, y)
    return c & 0x1F, c >> 5


@test(modes=("ds",))
def bh_act1_missions_load(ctx):
    """Each mission starts as its sheet says: armies, COs and colours, funds,
    map size, the units of its map file, its properties, structures, day
    limit, no fog, clear weather."""
    for k in (0, 1, 2):
        e, g, d = enter(ctx, k, cos=[bh.STURM])
        ctx.eq(d.mission(), k, f"M{k + 1} is the mission being played")
        ctx.eq(d.size(), SIZE[k], f"M{k + 1}: the map's size")
        p1, p2 = g.player(1), g.player(2)
        ctx.eq((p1["colour"], p2["colour"]), (5, 3), f"M{k + 1}: Black Hole against Green Earth")
        ctx.eq(p1["co"], PLAYER_CO[k], f"M{k + 1}: Sturm leads the player's army")
        ctx.eq(p2["co"], ENEMY_CO[k], f"M{k + 1}: the enemy's CO")
        ctx.eq(d.controllers()[:2], [1, 2], f"M{k + 1}: the player and the computer")
        want = map_units(k)
        for a in (1, 2):
            have = sorted(units_of(g, a))
            mine = sorted((t, x, y) for aa, t, x, y in want if aa == a)
            ctx.eq(have, mine, f"M{k + 1}: army {a}'s units are the map file's")
        st = g.playst()
        ctx.eq((st["fog"], st["weather"]), (0, 0), f"M{k + 1}: no fog, clear")
        (h1, h2) = HQS[k]
        ctx.eq(terrain(g, *h1), (CLASS_HQ, 1), f"M{k + 1}: Black Hole's HQ at {h1}")
        ctx.eq(terrain(g, *h2), (CLASS_HQ, 2), f"M{k + 1}: Green Earth's HQ at {h2}")
        if k == 0:
            ctx.eq((funds(g, 1), funds(g, 2)), FUNDS[k], "M1: starting funds")
        e.close()





def scenes(lead="STURM", partner=None):
    """{scene key: [cleaned text, ...]} of the dialogue files for a player leading `lead` (names as bhtext's)."""
    return {k: bhtext.shown(k, lead, partner) for k in bhtext.keys() if k.startswith("m0")}


def collect_texts(e, d, until, max_frames=40000, seen=None, snap=None, tick=None):
    """Presses A through event scripts, collecting each box's text once (shown in
    full), until `until()` holds."""
    texts, last, stable, n = seen if seen is not None else [], None, 0, 0
    while n < max_frames and not until():
        if tick:
            tick()
        t = d.text_shown()
        stable = stable + 1 if t and t == last else 0
        last = t
        if t and stable == 12:
            t1 = bhtext.clean(t)
            if not texts or texts[-1] != t1:
                texts.append(t1)
                if snap:
                    snap(len(texts), t1)
        if d.scripts_running() and stable >= 16:
            e.press("A", 4)
            stable = 0
        elif not d.scripts_running() and not d.in_battle():
            e.press("A", 4)
        e.wait(4)
        n += 6
    return texts


def win_and_collect(ctx, e, g, d, count=None):
    """A forced win (a test aid), then every text shown until the world map is
    back with the pad: (the victory scene's, the world-map scene's)."""
    ctx.require(d.force_win(), "the enemy is left to one unit, which is destroyed")
    texts = []
    # (`count`: stop after that many boxes: the last mission of the act so far is the campaign's
    # last, and its win goes on to the staff roll)
    collect_texts(e, d, lambda: (count is not None and len(texts) >= count and not d.scripts_running())
                  or (d.world_map_up() and e.u8(dc.WM_STATE + 0x10) and not d.scripts_running()), seen=texts)
    return texts


def intro_texts(ctx, e, g, d, label=None, snap_at=2):
    """From the CO screen on: the Setup phase's Deploy, then the opening scene's
    texts (each box once, shown in full), up to the player's control. With a
    `label`, pictures of the first boxes."""
    for _ in range(400):
        if d.in_battle():
            break
        if d.on_co_select():
            d.co_screen_a()
        e.wait(20)
    texts, quiet = [], 0

    waited = 0

    def over():
        nonlocal quiet, waited
        waited += 1
        quiet = 0 if d.scripts_running() else quiet + 1
        # (after the Setup phase's Deploy: the scene starts a moment later)
        return quiet > 12 and not d.in_setup() and (texts or waited > 150)

    snap = None
    if label:
        def snap(n, t):
            if n == snap_at:
                e.wait(240)            # (the box types its text out: the picture is of the whole of it)
                export(ctx, e.shot(os.path.join(ctx.out, f"{label}_dialogue")), f"{label}_dialogue")
    collect_texts(e, d, over, seen=texts, snap=snap, tick=lambda: d.in_setup() and d.deploy())
    g._units_base = g._players_base = None
    d.wait_control()
    return texts


def pass_turn(e, g, d, texts=None):
    """End the player's turn; the computer's turn runs; the texts shown at the
    next turn's start are collected into `texts`. Returns when the player has control."""
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    texts = texts if texts is not None else []
    state = {"left": False, "quiet": 0}

    def over():
        army = e.u8(0x030033EC)
        if army != 1:
            state["left"] = True
            state["quiet"] = 0
            return False
        if not state["left"]:
            return False
        # (back at the player's turn: its start-of-turn scenes may still come)
        state["quiet"] = 0 if d.scripts_running() else state["quiet"] + 1
        return state["quiet"] > 40

    collect_texts(e, d, over, max_frames=40000, seen=texts)
    d.wait_control()
    return texts


def next_flag_open(d, k):
    """After mission k (0-based): its flag cleared, the next one open."""
    flags = d.map_flags()
    return flags[k] == 2 and flags[k + 1] == 1


@test(modes=("ds",))
def bh_act1_m1_intro_win_bond_unlocks(ctx):
    """M1: the opening scene as designed (after the Setup phase there is none: Sturm is
    fixed), a picture of the first frame and of a dialogue box; a forced win shows the
    victory scene and the world-map scene as designed; Von Bolt is unlocked, his bond
    earned, mission 2's flag open."""
    exp = scenes()
    e, g, d = enter(ctx, 0, wait=False)
    texts = intro_texts(ctx, e, g, d, label="m1", snap_at=5)
    ctx.eq(texts, exp["m01_pre"], "the opening scene, box by box")
    ctx.eq(d.unlocked(), [bh.STURM], "only Sturm before the win")
    ctx.eq(d.bonds(), 0, "no bond yet")
    export(ctx, e.shot(os.path.join(ctx.out, "m1_opening")), "m1_opening")
    texts = win_and_collect(ctx, e, g, d)
    ctx.eq(texts, exp["m01_post"] + exp["m01_map"], "the victory scene, then the world-map scene")
    ctx.eq(d.won() & 1, 1, "mission 1 won")
    ctx.eq(d.unlocked(), [bh.STURM, bh.VON_BOLT], "Von Bolt unlocked by the win")
    ctx.eq(d.bonds(), 1, "Von Bolt's hidden bond is earned (bit 0)")
    ctx.check(next_flag_open(d, 0), f"mission 1 cleared, mission 2's flag open: {d.map_flags()[:4]}")
    export(ctx, e.shot(os.path.join(ctx.out, "world_map")), "world_map_act1_after_m1")


@test(modes=("ds",))
def bh_act1_m1_crystal_scene_loot_sale_and_day_seven(ctx):
    """M1's turn-start rules: day 3's scene needs a Black Hole unit in a Crystal's light
    (within 2 of it); day 4: Von Bolt, with six or more properties, gets two Md Tanks;
    day 7: his charge scene."""
    exp = scenes()
    e, g, d = enter(ctx, 0)
    day = lambda: e.u16(0x03004080)
    # (a test aid: Sturm's Recon stands by the west Crystal at (6, 6))
    recon = next(u for u in g.units(army=1) if u["type"] == 6)
    d.place_unit(recon, 6, 5)
    texts = []
    pass_turn(e, g, d, texts)       # day 2
    ctx.eq(texts, [], "day 2: no scene")
    pass_turn(e, g, d, texts)       # day 3
    ctx.eq(day(), 3, "day 3")
    ctx.eq(texts, exp["m01_day3"], "day 3: Von Bolt and Sturm on the Crystals")
    mds = [(u["x"], u["y"]) for u in g.units(army=2) if u["type"] == 3]
    n0 = len(mds)
    texts = []
    pass_turn(e, g, d, texts)       # day 4
    ctx.eq(day(), 4, "day 4")
    cells = {(19, 4), (21, 4)}
    spawned = [(u["x"], u["y"]) for u in g.units(army=2) if u["type"] == 3 and (u["x"], u["y"]) in cells]
    ctx.check(len(spawned) == 2 or len([u for u in g.units(army=2) if u["type"] == 3]) >= n0 + 2, f"day 4: the loot sale: two Md Tanks more (spawned at {spawned}, Md Tanks before {n0})")
    for _ in range(3):
        texts = []
        pass_turn(e, g, d, texts)
    ctx.eq(day(), 7, "day 7")
    ctx.eq(texts, exp["m01_day7"], "day 7: Von Bolt charges")
    e.close()


@test(modes=("ds",))
def bh_act1_m1_replay_plays_its_triggers_again(ctx):
    """Free Play: replaying M1 after winning it (its once-latch flags are set in the
    record) still shows day 3's scene and sends day 4's Md Tanks, and the record's
    flags are as they were afterwards."""
    e, g, d = boot(ctx)
    d.start_at(won_mask=(1 << 30) - 1, unlocked_mask=1)
    d.wait_world_map()
    for at in (dc.P_FLAGS, 0x0203FD20):          # (the latches M1's triggers set when it was won)
        e.w8(at, 0x07)
    d.pick_mission()
    d.choose_cos(PICKS[0], prefs=[bh.STURM])
    d.wait_map()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), 0, "mission 1 replayed")
    ctx.eq(e.u8(0x0203FD20), 0, "the latches lifted for the replay")
    exp = scenes()
    recon = next(u for u in g.units(army=1) if u["type"] == 6)
    d.place_unit(recon, 6, 5)
    texts = []
    pass_turn(e, g, d, texts)
    pass_turn(e, g, d, texts)
    ctx.eq(texts, exp["m01_day3"], "day 3's scene shows again in the replay")
    mds = len([u for u in g.units(army=2) if u["type"] == 3])
    pass_turn(e, g, d, [])
    ctx.check(len([u for u in g.units(army=2) if u["type"] == 3]) >= mds + 2, "day 4: the loot sale again")
    e.close()


@test(modes=("ds",))
def bh_act1_m1_lose_conditions(ctx):
    """M1 is lost when the days run out (the day after the 20th begins), when the
    army is routed, and when Sturm's HQ is taken."""
    from aw2test import campaigns as cp
    for how in ("days", "routed", "hq"):
        e, g, d = enter(ctx, 0)
        if how == "days":
            e.w16(0x03004080, DAY_LIMIT[0])
            pass_turn_to_result(e, g, d)
        elif how == "routed":
            for u in g.units(army=1):
                d.remove_unit(u)
            pass_turn_to_result(e, g, d)
        else:
            lose_hq(ctx, e, g, d, 0)
        r = d.last_result()
        ctx.eq(r["result"], 2, f"M1 lost: {how}")
        e.close()


def pass_turn_to_result(e, g, d, max_frames=20000):
    """End the turn (a unit waits first if the army has none: the map menu) and wait for a result."""
    try:
        g.open_map_menu()
        g.choose("End", g.MAP_MENU)
    except Exception:
        pass
    n = 0
    while n < max_frames and not e.u8(dc.LAST_RESULT):
        if d.scripts_running() or not d.in_battle():
            e.press("A", 4)
        e.wait(20)
        n += 24
    for _ in range(300):
        if d.world_map_up() or e.u8(dc.LAST_RESULT):
            break
        e.press("A", 4)
        e.wait(10)


def lose_hq(ctx, e, g, d, k):
    """An enemy Infantry stands on Black Hole's HQ and captures it (a test aid places
    it; the game's own capture takes two turns)."""
    hx, hy = HQS[k][0]
    foe = next(u for u in g.units(army=2))
    a = g.unit_addr(foe["id"])
    e.w8(a, 1)                                         # an Infantry
    e.w16(a + 4, (e.u16(a + 4) & ~0x7F) | 100)
    e.w8(a + 0x0B, 1)                                  # (the AI role 1: goes for the enemy HQ; the map's soldiers have role 0 and stand, custom_campaign::ai_unit)
    for u in g.units(army=1):
        if (u["x"], u["y"]) == (hx, hy):
            d.place_unit(u, hx + 1, hy)
    d.place_unit(g.unit(foe["id"]), hx, hy)
    for _ in range(3):
        if e.u8(dc.LAST_RESULT):
            break
        pass_turn_to_result(e, g, d, 6000) if False else None
        try:
            g.open_map_menu()
            g.choose("End", g.MAP_MENU)
        except Exception:
            pass
        for _ in range(400):
            if e.u8(dc.LAST_RESULT) or (g.current_army() == 1 and not d.scripts_running() and d.in_battle()):
                break
            if d.scripts_running() or not d.in_battle():
                e.press("A", 4)
            e.wait(20)
        e.wait(30)


@test(modes=("ds",))
def bh_act1_m2_foundry_waves_and_flow(ctx):
    """M2: the opening as designed, with the last line Sturm's own (Sturm leads) or the
    leader's (Von Bolt), no bases and no funds; the Foundry wakes on day 3 (its
    own table: a unit within a Tank's price on the middle door at day 3's start, none before) with
    its scene and Green Earth's first wave; the win shows the victory and map scenes
    and opens mission 3."""
    for lead, last, name in ((bh.STURM, "m02_pre_sturm", "STURM"), (bh.VON_BOLT, "m02_pre_other", "VON BOLT")):
        exp = scenes(name)
        e, g, d = enter(ctx, 1, cos=[lead], wait=False)
        texts = intro_texts(ctx, e, g, d, label="m2" if lead == bh.STURM else None, snap_at=7)
        ctx.eq(texts, exp["m02_pre"] + exp[last], f"M2 led by CO {lead}: the opening scene, box by box")
        ctx.eq(g.player(1)["co"], lead, "the picked CO leads army 1")
        if lead == bh.STURM:
            export(ctx, e.shot(os.path.join(ctx.out, "m2_opening")), "m2_opening")
            ctx.eq(funds(g, 1), 0, "no funds")
            factory = [(x, y) for y in range(24) for x in range(22) if g.terrain_class(x, y) & 0x1F == 0x1D]
            ctx.check(factory, f"the Black Foundry's tiles are on the map ({factory[:3]})")
            doors = [(10, 7), (11, 7), (12, 7)]
            ctx.eq([g.unit_at(*c) for c in doors], [None, None, None], "the doors are empty on day 1")
            day = lambda: e.u16(0x03004080)
            texts = []
            pass_turn(e, g, d, texts)   # day 2
            ctx.eq(day(), 2, "day 2")
            ctx.eq([g.unit_at(*c) for c in doors], [None, None, None], "day 2: the Foundry still sleeps")
            ge0 = len(g.units(army=2))
            pass_turn(e, g, d, texts)   # day 3
            ctx.eq(day(), 3, "day 3")
            ctx.eq(texts, exp["m02_day3"], "day 3: the Foundry wakes: its scene")
            door = g.unit_at(11, 7)
            # (the table is the schedule and the cost cap: the smart spawner picks what the battle needs within the Tank's price)
            ctx.check(door is not None and door["army"] == 1 and door["type"] in (1, 2, 5, 6, 7, 10), f"a unit of the Tank's price class on the middle door: {door and (door['army'], door['type'])}")
            ctx.eq([g.unit_at(*c) is None for c in ((10, 7), (12, 7))], [True, True], "the side doors give nothing on day 3")
            wave = [u for u in g.units(army=2) if u["type"] == 5 and u["y"] >= 15]
            ctx.check(len(g.units(army=2)) >= ge0 + 3 or len(wave) >= 3, f"Green Earth's first wave of three Tanks has come ({len(g.units(army=2))} units, was {ge0})")
            export(ctx, e.shot(os.path.join(ctx.out, "m2_day3")), "m2_day3_foundry_wakes")
        texts = win_and_collect(ctx, e, g, d)
        ctx.eq(texts, exp["m02_post"] + exp["m02_map"], "the victory scene, then the world-map scene")
        ctx.eq(d.won() & 2, 2, "mission 2 won")
        ctx.eq(d.unlocked(), [bh.STURM, bh.VON_BOLT], "no new CO")
        ctx.check(next_flag_open(d, 1), f"mission 2 cleared, mission 3's flag open: {d.map_flags()[:4]}")
        e.close()


@test(modes=("ds",))
def bh_act1_m3_blockade_flow(ctx):
    """M3: the tag pair Sturm + Von Bolt fixed against Drake + Eagle (no CO screen); the
    opening as designed; day 4's scene; day 8's scene once the middle isle's cities are held;
    the win shows the victory and map scenes."""
    exp = scenes("STURM", "VON BOLT")
    e, g, d = enter(ctx, 2, wait=False)
    texts = intro_texts(ctx, e, g, d, label="m3", snap_at=10)
    ctx.eq(texts, exp["m03_pre"], "the opening scene, box by box")
    from aw2test import tag
    ctx.eq(g.player(1)["co"], bh.STURM, "Sturm leads")
    ctx.eq(g.player(2)["co"], 9, "Drake leads Green Earth")
    ctx.eq((tag.partner(e, 1) or {}).get("co"), bh.VON_BOLT, "Von Bolt is the player's partner")
    ctx.eq((tag.partner(e, 2) or {}).get("co"), 8, "Eagle is Drake's partner")
    export(ctx, e.shot(os.path.join(ctx.out, "m3_opening")), "m3_opening")
    day = lambda: e.u16(0x03004080)
    e.w16(0x03004080, 3)
    texts = []
    pass_turn(e, g, d, texts)
    ctx.eq(day(), 4, "day 4")
    ctx.eq(texts, exp["m03_day4"], "day 4: Eagle's Fighters")
    # day 8 needs two of the isle's three cities
    row = e.u16(0x0201E450 + 0x417A + 2 * 9)
    for (x, y) in ((11, 9), (14, 8)):
        row = e.u16(0x0201E450 + 0x417A + 2 * y)
        at = 0x0201E450 + 0x1432 + row + x
        e.w8(at, (e.u8(at) & 0x1F) | 1 << 5)
    e.w16(0x03004080, 7)
    texts = []
    pass_turn(e, g, d, texts)
    ctx.eq(day(), 8, "day 8")
    ctx.eq(texts, exp["m03_day8"], "day 8: Drake, once the isle is held")
    post = exp["m03_post"] + exp["m03_map"] + exp["m03_warroom"]
    texts = win_and_collect(ctx, e, g, d, count=len(post))
    ctx.eq(texts, post, "the victory scene, the world-map scene, then the war room")
    ctx.eq(d.won() & 4, 4, "mission 3 won")
    ctx.eq(d.unlocked(), [bh.STURM, bh.VON_BOLT], "no new CO")
    e.close()


def map_rows(k):
    """Mission k's map file rows (the characters of five/map.py's legend)."""
    rows = [l.rstrip("\n") for l in open(os.path.join(BH_MAPS, f"bh0{k + 1}.txt"))
            if l.strip() and not l.startswith(("#", "map ", "armies ", "team ", "unit ", "objective "))]
    return rows


def sea_start(rows, beach, dist=3):
    """Sea cells `dist` steps by sea from the beach, nearest first (where a Lander is put before it sails there)."""
    h, w = len(rows), len(rows[0])
    seen, todo = {beach: 0}, [beach]
    while todo:
        x, y = todo.pop(0)
        for X, Y in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if 0 <= X < w and 0 <= Y < h and (X, Y) not in seen and rows[Y][X] in "~,":
                seen[(X, Y)] = seen[(x, y)] + 1
                todo.append((X, Y))
    return sorted((c for c, n in seen.items() if n == dist and rows[c[1]][c[0]] == "~"), key=lambda c: (abs(c[0] - beach[0]) + abs(c[1] - beach[1]), c))


def land_next(rows, beach):
    """The land cell beside a beach where a soldier is dropped (plain ground, road, wood)."""
    x, y = beach
    for X, Y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if 0 <= Y < len(rows) and 0 <= X < len(rows[0]) and rows[Y][X] in ".fR":
            return (X, Y)
    return None


# Every army's beaches (five/bh/bh03.txt): its own island's and the middle isle's four.
BEACHES = {1: [(6, 5), (6, 8), (6, 11), (9, 6), (9, 9), (16, 6), (16, 9)], 2: [(19, 7), (19, 9), (19, 12), (16, 6), (16, 9), (9, 6), (9, 9)]}


@test(modes=("ds",))
def bh_act1_m3_lander_unloads_on_every_beach(ctx):
    """Every army, played by a human in turn: its Lander is put at sea three steps from one of its
    beaches (its own island's three and the middle isle's four), sails onto the beach, an Infantry
    beside it walks on and boards (Load); on the army's next turn the Lander drops it onto the land
    next to the beach. Read from RAM: the Lander on a shoal, the Infantry inside it, then standing
    on land beside the beach, the Lander empty. (As Five Seas' test.)"""
    rows = map_rows(2)
    plans = {}
    for a, beaches in BEACHES.items():
        plans[a] = []
        for b in beaches:
            land, start = land_next(rows, b), sea_start(rows, b)
            ctx.check(rows[b[1]][b[0]] == "," and land is not None and start, f"army {a}: beach {b} is a shoal with land {land} beside it and sea to sail from {start[:1]}")
            plans[a].append((b, land, start))
    ctx.require(all(p[1] and p[2] for ps in plans.values() for p in ps), "every beach has a land cell and a sea start")
    e, g, d = enter(ctx, 2)
    for a in (1, 2):
        e.w8(g.player(a)["addr"] + 0x1B, 1)             # both armies by hand
    # Green Earth has no foot soldier: its Fighter at (22, 5) is made an Infantry (a test aid)
    foe = next(u for u in g.units(army=2) if u["type"] == 16)
    a_ = g.unit_addr(foe["id"])
    e.w8(a_, 1)
    e.w16(a_ + 4, (e.u16(a_ + 4) & ~0x7F) | 100)
    ids = {}
    for a in (1, 2):
        lander = next(u for u in g.units(army=a) if u["type"] == 23)
        inf = next(u for u in g.units(army=a) if u["type"] == 1)
        ids[a] = (lander["id"], inf["id"])
    state = {a: ["sail", 0] for a in (1, 2)}
    done = lambda: all(s[1] >= len(plans[a]) for a, s in state.items())
    for rnd in range(40):
        if done():
            break
        a = g.current_army()
        mode, n = state[a]
        if n >= len(plans[a]):
            pass_turn_by_hand(e, g, d)
            continue
        b, land, starts = plans[a][n]
        lid, iid = ids[a]
        start = next((c for c in starts if g.unit_at(*c) is None), starts[0])
        if mode == "sail":
            d.place_unit(g.unit(lid), *start)
            d.place_unit(g.unit(iid), *land)
            g.select(*start)
            g.move_to(*b)
            g.choose("Wait", g.ACTION_MENU)
            g.wait_idle()
            lu = g.unit(lid)
            ctx.check((lu["x"], lu["y"]) == b and g.terrain_class(*b) & 0x1F == CLASS_SHOAL, f"army {a}: its Lander sailed from {start} onto the beach {b}")
            g.select(*land)
            names = g.move_to(*b)["names"]
            ctx.check(any(t.lower().startswith("load") for t in names), f"army {a}: the Infantry beside the beach is offered Load at {b}: {names}")
            g.choose("Load", g.ACTION_MENU)
            g.wait_idle()
            lu = g.unit(lid)
            ctx.check(any(lu["cargo"]), f"army {a}: the Lander on {b} carries the Infantry (cargo {lu['cargo']})")
            state[a][0] = "drop"
        else:
            lu = g.unit(lid)
            g.select(lu["x"], lu["y"])
            names = g.move_to(lu["x"], lu["y"])["names"]
            ctx.check(any(t.lower().startswith("drop") for t in names), f"army {a}: the Lander on the beach {b} offers Drop: {names}")
            g.choose("Drop", g.ACTION_MENU)
            e.wait(20)
            if g.menu():
                e.press("A", 4)
                e.wait(20)
            for _ in range(8):                          # the cursor cycles through the cells the game offers
                if g.cursor() == land:
                    break
                e.press("RIGHT", 4)
                e.wait(10)
            if n == 0:
                export(ctx, e.shot(os.path.join(ctx.out, f"lander_drop_army{a}")), f"m3_lander_drop_target_army{a}")
            e.press("A", 4)
            e.wait(40)
            mm = g.menu()
            if mm and any(t.lower().startswith("wait") for t in mm["names"]):
                g.choose("Wait", g.ACTION_MENU)
            g.wait_idle()
            iu, lu = g.unit(iid), g.unit(lid)
            ctx.check(abs(iu["x"] - b[0]) + abs(iu["y"] - b[1]) == 1 and not any(lu["cargo"]) and (iu["x"], iu["y"]) != (lu["x"], lu["y"]),
                      f"army {a}: the Infantry was dropped from the Lander on {b} to {(iu['x'], iu['y'])} (land beside it: {land}), the Lander empty ({lu['cargo']})")
            ctx.check(rows[iu["y"]][iu["x"]] in ".fR", f"army {a}: it stands on land ({rows[iu['y']][iu['x']]!r})")
            if n == 0:
                export(ctx, e.shot(os.path.join(ctx.out, f"lander_dropped_army{a}")), f"m3_lander_dropped_army{a}")
            state[a] = ["sail", n + 1]
        pass_turn_by_hand(e, g, d)
    ctx.check(done(), f"every beach of both armies was used ({state})")
    e.close()


def pass_turn_by_hand(e, g, d):
    """End a human army's turn; wait for the next army's control (scenes answered)."""
    army = g.current_army()
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    e.wait_until(lambda: g.current_army() != army, 600, step=8)
    d.wait_control()


@test(modes=("ds",))
def bh_act1_save_and_continue_mid_mission(ctx):
    """Act I played from New through the saves: each mission saved halfway from its map menu
    (Save), the console rebooted from that Flash, BH CAMPAIGN's Continue bringing the battle back as
    saved (units, funds, day: `saves.compare_snapshots`), then won (a test aid), the record kept (won
    bits, unlocked COs, the bond) and the next mission opened from it."""
    from aw2test import saves
    snap = flash = None
    for k in (0, 1, 2):
        if k == 0:
            e, g, d = boot(ctx)
            d.start_bh(new=True, pick=False)
            d.wait_world_map()
            d.pick_mission()
            d.wait_map()
        else:
            e, g, d = boot(ctx, flash.path)
            d.start_bh(new=False, pick=False)
            ctx.require(e.wait_until(lambda: e.u32(0x03000000) == 0x08022049, 1500, step=10), f"M{k}: Continue brings the battle back")
            g._units_base = g._players_base = None
            g.wait_for_input()
            ctx.eq((d.mission(), e.u8(bh.SOURCE)), (k - 1, bh.BH), f"mission {k}, the BH Campaign's session")
            saves.compare_snapshots(ctx, snap, saves.snapshot(g), f"M{k}: after a reboot, Continue")
            ctx.require(d.force_win(), f"mission {k} won (test aid)")
            for _ in range(600):
                if d.world_map_up() and e.u8(dc.WM_STATE + 0x10) and not d.scripts_running():
                    break
                if d.scripts_running() or not d.in_battle():
                    e.press("A", 4)
                e.wait(20)
            e.wait(60)
            ctx.eq(d.won() & ((1 << k) - 1), (1 << k) - 1, f"missions 1..{k} won in the record")
            ctx.eq(d.unlocked(), [bh.STURM] if k == 0 else [bh.STURM, bh.VON_BOLT], "the unlocked COs from the record")
            if k == 2:
                ctx.eq(d.bonds() & 1, 1, "Von Bolt's bond kept in the record")
            d.pick_mission()
            if PICKS[k]:
                d.choose_cos(PICKS[k], prefs=[bh.STURM])
            d.wait_map()
        g._units_base = g._players_base = None
        names = saves.suspend(g)
        ctx.check("Save" in names, f"M{k + 1}: Save on the map menu ({names})")
        snap = saves.snapshot(g)
        flash = saves.flash(e, os.path.join(ctx.out, f"saved{k + 1}"))
        ctx.check(not flash.problems(), f"M{k + 1}: every slot passes AW2's check {flash.problems()}")
        ctx.check(12 in flash.tags() and 13 in flash.tags(), f"M{k + 1}: the halfway save (slot 12) and the record (13) are there ({flash.tags()})")
        e.close()
    # the last save, once more
    e, g, d = boot(ctx, flash.path)
    d.start_bh(new=False, pick=False)
    ctx.require(e.wait_until(lambda: e.u32(0x03000000) == 0x08022049, 1500, step=10), "M3: Continue brings the battle back")
    g._units_base = g._players_base = None
    g.wait_for_input()
    ctx.eq(d.mission(), 2, "mission 3")
    saves.compare_snapshots(ctx, snap, saves.snapshot(g), "M3: after a reboot, Continue")
    e.close()


def tool():
    """five/bhmap.py as a module (the map tool and its reachability checker)."""
    import importlib.util
    path = os.path.join(paths.REPO, "tango-gamesupport-aw2", "five", "bhmap.py")
    spec = importlib.util.spec_from_file_location("bhmap_tool", path)
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.path.insert(0, os.path.dirname(path))
    spec.loader.exec_module(mod)
    return mod


@test(modes=("ds",))
def bh_act1_maps_are_reachable(ctx):
    """The map tool's checks on Act I's three maps (every tile as the game draws it, HQs reachable,
    no stranded island, no boxed-in unit, every Lander with beaches to load and unload at), and
    more: on M1 and M2 foot, tires and treads each walk from either HQ to every property of the
    map (the bridges are the only crossings of the rivers); on M3 each army's foot soldiers reach
    every property of their island, every port opens to the sea lanes (ships from any port reach
    every other port and every beach of the isle), and every beach is a shoal that a Lander can
    reach."""
    import subprocess
    import sys
    files = [os.path.join(BH_MAPS, f"bh0{k}.txt") for k in (1, 2, 3)]
    r = subprocess.run([sys.executable, os.path.join(paths.REPO, "tango-gamesupport-aw2", "five", "bhmap.py"), "--check", paths.aw2_rom()] + files,
                       capture_output=True, text=True)
    ctx.eq(r.returncode, 0, f"the map tool's checks pass ({r.stdout.strip()} {r.stderr.strip()})")
    mod = tool()
    maps = {m["name"]: m for m in mod.parse(files)}
    props = lambda rows: [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c in "HBCAPbcap12"]
    for name in ("bh01", "bh02"):
        rows = maps[name]["rows"]
        hqs = {int(c): (x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c in "12"}
        for cls in (mod.FOOT, mod.TIRES, mod.TREADS):
            for a, hq in hqs.items():
                got = mod.reach(rows, hq, cls)
                missing = [c for c in props(rows) if c not in got]
                ctx.eq(missing, [], f"{name}: {cls} units from army {a}'s HQ reach every property")
    rows = maps["bh03"]["rows"]
    hqs = {int(c): (x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c in "12"}
    for a, hq in hqs.items():
        got = mod.reach(rows, hq, mod.FOOT)
        island = [c for c in props(rows) if (c[0] < 8) == (hq[0] < 8) and c[0] not in range(9, 17)]
        ctx.eq([c for c in island if c not in got], [], f"bh03: army {a}'s foot soldiers reach every property of their island")
    ports = [(6, 6), (6, 10), (19, 5), (19, 11)]
    beaches = [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == ","]
    ctx.eq(len(beaches), 10, "bh03 has ten beaches")
    for cls in (mod.SEA, mod.LANDER):
        sea = mod.reach(rows, (7, 6), cls)
        for p in ports:
            ctx.check(any(n in sea for n in ((p[0] - 1, p[1]), (p[0] + 1, p[1]), (p[0], p[1] - 1), (p[0], p[1] + 1))), f"bh03: {cls} from the west port reaches the sea beside the port {p}")
    sea = mod.reach(rows, (7, 6), mod.LANDER)
    for b in beaches:
        ctx.check(any(n in sea for n in ((b[0] - 1, b[1]), (b[0] + 1, b[1]), (b[0], b[1] - 1), (b[0], b[1] + 1))), f"bh03: a Lander reaches the beach {b}")
    # the centre channels are two cells wide the whole way (x 7..8 and 17..18)
    for x0 in (7, 17):
        clear = [y for y in range(16) if all(rows[y][x] == "~" for x in (x0, x0 + 1))]
        ctx.check(len(clear) >= 14, f"bh03: the channel at x {x0}..{x0 + 1} is two cells wide in {len(clear)} of its 16 rows")


@test(modes=("ds",))
def bh_act1_m2_m3_lose_conditions(ctx):
    """M2 and M3 are lost when the days run out, when the army is routed, and when Black Hole's HQ is
    taken (M2's HQ sits behind the Foundry)."""
    for k in (1, 2):
        for how in ("days", "routed", "hq"):
            e, g, d = enter(ctx, k, cos=[bh.STURM])
            if how == "days":
                e.w16(0x03004080, DAY_LIMIT[k])
                pass_turn_to_result(e, g, d)
            elif how == "routed":
                for u in g.units(army=1):
                    d.remove_unit(u)
                pass_turn_to_result(e, g, d)
            else:
                lose_hq(ctx, e, g, d, k)
            ctx.eq(d.last_result()["result"], 2, f"M{k + 1} lost: {how}")
            e.close()


def campaign_texts(e):
    """Every text of the campaign's id range (0x7400..) as the game has it: {id: bytes} (a text holds up to six boxes joined by 0x0F)."""
    out = {}
    for tid in range(0x7400, 0x8000):
        p = e.u32(0x08610A38 + 4 * tid)
        if 0x08F00000 <= p < 0x08FC0000:
            b = e.read(p, 1024)
            out[tid] = b[:b.index(0)] if 0 in b else b
    return out


@test(modes=("ds",))
def bh_act1_dialogue_is_the_designs_and_fits_its_boxes(ctx):
    """Every text of Act I's scenes (tango-gamesupport-aw2/src/bh_text/act1.txt, as each CO the scene offers sees it)
    is in the game exactly (several boxes of one speaker merged into one text, joined by 0x0F, lines by 0x0D); no
    box of any campaign text has more than two lines (so no line is cut or spilled into a second box), and no text
    has more than six boxes."""
    e, g, d = boot(ctx)
    d.start_at(won_mask=0, unlocked_mask=1)
    d.wait_world_map()
    have = campaign_texts(e)
    held = {b.decode("latin-1").rstrip("\x0f") for b in have.values()}
    tall, long_, cut = [], [], []
    for tid, b in have.items():
        parts = [x for x in b.split(b"\x0f") if x]      # (every box ends with 0x0F)
        tall += [(tid, part) for part in parts if part.count(b"\r") > 1]
        if len(parts) > bhtext.MERGE_BOXES:
            long_.append(tid)
        if len(b) >= 1023:
            cut.append(tid)
    ctx.eq(tall, [], "no box of the campaign has more than two lines")
    ctx.eq(long_, [], "no text of the campaign has more than six boxes")
    ctx.eq(cut, [], "no text is longer than the 1024 bytes the test reads")
    n, missing = 0, []
    keys = [k for k in bhtext.keys() if k.startswith(("m01", "m02", "m03"))]
    for key in keys:
        pool = bhtext.book()[key][0]
        for lead in pool:
            for partner in ([None] if key != "m03_pre" else [None]):
                for t in bhtext.scene(key, lead, partner):
                    n += 1
                    if t not in held:
                        missing.append((key, lead, t[:60]))
    ctx.eq(missing, [], "every scene text is a text of the game")
    ctx.check(n >= 100, f"{n} scene texts checked")
    e.close()


BALANCE = os.environ.get("AW2TEST_BH_ACT1_BALANCE")


# How the test player plays each mission: the enemy HQ its capturers make for.
BOT = {0: {"goals": [(19, 2)], "stance": "attack"}, 1: {"goals": [(11, 22)], "stance": "attack"}, 2: {"goals": [(24, 8)], "stance": "attack"}}


def play_out(ctx, k, how, cos, max_days, **bot):
    import json
    bot = bot or dict(BOT[k], **json.loads(os.environ.get("AW2TEST_BH_ACT1_BOT", "{}")))
    e, g, d = enter(ctx, k, cos=cos, wait=False)
    for _ in range(400):
        if d.in_battle():
            break
        if d.on_co_select():
            d.co_screen_a()
        e.wait(20)
    def log(s):
        ctx.log(s)
        if s.startswith("day") and d.in_battle():
            try:
                for a in (1, 2):
                    us = g.units(army=a)
                    ctx.log(f"   army {a}: " + " ".join(f"{u['type']}@{u['x']},{u['y']}/{u['hp'] // 10}" for u in us))
            except Exception:
                pass
    r = d.autoplay(max_days, log=log) if how == "cpu" else d.play(max_days, log=log, **bot)
    ctx.log(f"M{k + 1} {how}: result {r['result']} (1 won, 2 lost, 0 none) on day {r['days']}: {r['reason']}")
    e.close()
    return r


if BALANCE:
    for _k, _cos in ((0, None), (1, [bh.STURM]), (2, None)):
        for _how in ("cpu", "bot"):
            def _mk(k=_k, cos=_cos, how=_how):
                def f(ctx):
                    play_out(ctx, k, how, cos, int(os.environ.get("AW2TEST_BH_ACT1_DAYS", "30")))
                f.__name__ = f"bh_act1_balance_m{k + 1}_{how}"
                f.__doc__ = "Balance run (opt-in): the mission played through to its end."
                return f
            _f = _mk()
            test(modes=("ds",))(_f)


