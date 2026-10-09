"""The BH Campaign (bh_campaign.rs, custom_campaign.rs): a campaign defined
as data, played by the DS Campaign's engine; Select Mode's Campaign
chooser lists it third, with the Dual Strike pack only. Two placeholder
missions prove the pipeline: New, the prologue, AW2's world map with the
first flag, mission 1 (Sturm against Von Bolt in Green Earth's colours),
its win unlocking Von Bolt and opening the second flag, mission 2 (the
player picks Sturm or Von Bolt), the staff roll."""

import os

from aw2test import bhcampaign as bh
from aw2test import bhtext
from aw2test import dscampaign as dc
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game, NavError
from aw2test.harness import test

OAM = 0x07000000
LABEL_TILES = (832, 868)          # campaign_menu::TILES, one label each


# The campaign as it stands: the mission whose win ends it (its index) and the staff roll's
# sections (bh_campaign::def). Act I only so far: the Act V builder moves both.
FINAL_MISSION = 29      # (the merged tree's last mission: bh30 Nell's Stand; Sturm and Clone Andy are picked on its CO screens)
ROLL_WIDTH, ROLL_SLOTS = 21, 6     # ds_credits.rs: a heading's width, the slots of a page


def credit_sections():
    """[(heading, [names], secret)] of bh_campaign.rs `credits()`."""
    import re
    src = open(os.path.join(paths.REPO, "tango-gamesupport-aw2", "src", "bh_campaign.rs")).read()
    body = src[src.index("fn credits()"):]
    body = body[:body.index("\n}\n")]
    q = r'"((?:[^"\\]|\\.)*)"'
    out = []
    for m in re.finditer(r'sec\(' + q + r',\s*&\[(.*?)\],\s*(true|false)\)', body, re.S):
        names = [n.replace('\\"', '"') for n in re.findall(q, m.group(2))]
        out.append((m.group(1), names, m.group(3) == "true"))
    return out


def roll_pages(secret=False):
    """The (kind, text) slots of the roll's pages as ds_credits.rs `pages` lays them out (1 heading, 2 name), blank slots dropped."""
    out = []
    for heading, names, sec in credit_sections():
        if sec and not secret:
            continue
        t = heading.replace("'", "~")
        if len(t) + 2 <= ROLL_WIDTH or " " not in t:
            heads = ["*" + t + "*"]
        else:
            mid = len(t) // 2
            i = min((i for i, c in enumerate(t) if c == " "), key=lambda i: abs(i - mid))
            heads = ["*" + t[:i] + "*", "*" + t[i + 1:] + "*"]
        rows = [(1, h) for h in heads] + [(2, n.replace("'", "~")) for n in names]
        if len(rows) <= ROLL_SLOTS:
            out += rows
        else:
            room = max(ROLL_SLOTS - len(heads), 1)
            body = rows[len(heads):]
            for k in range(0, len(body), room):
                out += ([(1, h) for h in heads] + body[k:k + room])[:ROLL_SLOTS]
    return out


CREDITS_PAGES = roll_pages()
PROLOGUE = bhtext.shown("prologue")        # (17 narration boxes, merged into texts of up to six)



def boot(ctx, save=None):
    e = Emu(save=save or paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    return e, g, bh.BhCampaign(g)


def shot(ctx, e, name):
    e.shot(os.path.join(ctx.out, name))


def oam_tiles(e):
    oam = e.read(OAM, 0x400)
    out = set()
    for i in range(128):
        a0 = oam[8 * i] | oam[8 * i + 1] << 8
        if (a0 >> 8) & 3 == 2:
            continue
        out.add((oam[8 * i + 4] | oam[8 * i + 5] << 8) & 0x3FF)
    return out


@test()
def bh_campaign_menu_entry(ctx):
    """Campaign's chooser lists AW2 CAMPAIGN, DS CAMPAIGN, BH CAMPAIGN with the
    pack; without it the box is AW2's own and the list unchanged."""
    e, g, d = boot(ctx)
    d.open_campaign_box()
    e.wait(30)
    if not ctx.ds:
        tiles = oam_tiles(e)
        ctx.check(not (tiles & set(LABEL_TILES)), "no chooser labels without the pack")
        ctx.eq(e.u8(dc.MENU_LEVEL), 0, "no sub-menu state")
        ctx.eq(e.u8(bh.SOURCE), 0, "no campaign chosen")
        # (UP / DOWN in AW2's own box do not reach a third campaign)
        shot(ctx, e, "menu_pack_off")
        return
    ctx.eq(e.u8(dc.MENU_LEVEL), 0, "the chooser")
    shot(ctx, e, "menu_first_two")
    d.chooser_row(1)
    e.wait(10)
    ctx.eq(e.u8(dc.MENU_CHOICE), 1, "DS CAMPAIGN is the second entry")
    d.chooser_row(2)
    e.wait(20)
    ctx.eq(e.u8(dc.MENU_CHOICE), 2, "BH CAMPAIGN is the third entry")
    ctx.check(set(LABEL_TILES) <= oam_tiles(e), "two labels shown, the window on DS and BH")
    shot(ctx, e, "menu")
    e.press("A", 8)
    e.wait(30)
    ctx.eq(e.u8(dc.MENU_LEVEL), 2, "A: the BH Campaign's Continue / New")
    ctx.eq(e.u8(bh.SOURCE), bh.BH, "the BH Campaign is the chosen one")
    shot(ctx, e, "bh_box")
    e.press("B", 8)
    e.wait(30)
    ctx.eq(e.u8(dc.MENU_LEVEL), 0, "B: back to the chooser")
    ctx.eq(e.u8(dc.MENU_CHOICE), 2, "on BH CAMPAIGN")


def follow_prologue(ctx, e, d, label):
    """From the start: the prologue's pages (each shown in full once, A through
    them) until the world map takes the pad. Returns the texts seen."""
    texts, last, stable = [], None, 0
    for _ in range(2000):
        if d.world_map_up() and e.u8(dc.WM_STATE + 0x10) and not d.scripts_running():
            break
        t = d.text_shown()
        stable = stable + 1 if t and t == last else 0
        last = t
        t = bhtext.clean(t) if t else t
        if t and stable == 6 and (not texts or texts[-1] != t):
            texts.append(t)
            shot(ctx, e, f"{label}{len(texts)}")
        if d.scripts_running() and stable >= 12:
            e.press("A", 4)
            stable = 0
        e.wait(4)
    return texts


@test(modes=("ds",))
def bh_campaign_new_prologue_world_map(ctx):
    """New: the prologue (17 narration boxes in three texts, from the text file), then AW2's own world
    map with the first flag, on the Black Hole land."""
    e, g, d = boot(ctx)
    d.start_bh(new=True, pick=False)
    ctx.eq(e.u8(bh.SOURCE), bh.BH, "the BH Campaign's session")
    texts = follow_prologue(ctx, e, d, "prologue")
    ctx.eq(texts, PROLOGUE, "the prologue's pages, from data")
    ctx.require(d.world_map_up(), "the world map is up")
    e.wait(60)
    flags = d.map_flags()
    ctx.eq(flags[:3], [1, 0, 0], "one flag: mission 1 open, mission 2 not yet")
    ctx.eq(d.map_mission(), 0, "the cursor on mission 1")
    shot(ctx, e, "world_map")
    # AW2's own picture, not Omega Land's (its tile pool words are AW2's)
    ctx.eq(e.u32(0x080769B4), 0x081CC5F0, "AW2's map tiles")
    ctx.eq(d.progress()["valid"], False, "(the DS record's magic is not the BH Campaign's)")
    ctx.eq(e.u32(dc.P_MAGIC), bh.BH_MAGIC, "the BH Campaign's own record")
    ctx.log(f"progress {e.read(dc.PROGRESS, 0x20).hex()}")
    ctx.eq(d.unlocked(), [bh.STURM], "Sturm only")


def first_mission(ctx, e, d):
    """New, through the prologue, mission 1 started and under the player's control."""
    d.start_bh(new=True, pick=False)
    follow_prologue(ctx, e, d, "prologue")
    d.pick_mission()
    d.wait_map()


@test(modes=("ds",))
def bh_campaign_mission_one_unlocks_von_bolt(ctx):
    """Mission 1 (Sturm against Von Bolt in Green Earth's colours): the armies
    are as the data says, the win unlocks Von Bolt and opens mission 2's flag
    (Act I's own tests: test_bh_act1.py)."""
    from aw2test import campaigns as cp
    e, g, d = boot(ctx)
    first_mission(ctx, e, d)
    ctx.eq(d.mission(), 0, "mission 1")
    g._units_base = g._players_base = None
    ps = [g.player(1), g.player(2)]
    shot(ctx, e, "mission1")
    ctx.eq((ps[0]["co"], ps[1]["co"]), (bh.STURM, bh.VON_BOLT), "Sturm leads army 1, Von Bolt army 2")
    ctx.eq((ps[0]["colour"], ps[1]["colour"]), (5, 3), "army 1 in Black Hole's colours, army 2 in Green Earth's")
    ctx.eq(d.size(), (22, 15), "the data's map")
    ctx.eq(d.controllers()[:2], [1, 2], "the player and the computer")
    cp.win_here(e, d)
    ctx.eq(d.won(), 1, "mission 1 won")
    ctx.eq(d.unlocked(), [bh.STURM, bh.VON_BOLT], "Von Bolt unlocked by the win")
    flags = d.map_flags()
    ctx.eq(flags[:2], [2, 1], "mission 1 cleared, mission 2's flag open")
    shot(ctx, e, "world_map_two_flags")


def to_co_select(ctx, e, d, label):
    """On the world map: A, A on the mission's panel, until the CO screen is up
    and its cursor found; returns the COs it offers."""
    d.pick_mission()
    for _ in range(300):
        if d.on_co_select() and d.co_cursor():
            break
        e.press("A", 4) if d.scripts_running() else None
        e.wait(10)
    ctx.require(d.on_co_select(), f"{label}: the CO screen")
    e.wait(40)
    return d.offered()


@test(modes=("ds",))
def bh_campaign_co_select_only_unlocked(ctx):
    """Mission 2 lets the player pick Sturm or Von Bolt: after mission 1 both
    are offered; with only Sturm unlocked, only Sturm; and a CO unlocked but
    not in the mission's pool (Hawke) is not offered. The pick leads the army."""
    from aw2test import campaigns as cp
    # Both unlocked, by mission 1's win.
    e, g, d = boot(ctx)
    first_mission(ctx, e, d)
    cp.win_here(e, d)
    offered = to_co_select(ctx, e, d, "after mission 1")
    ctx.eq(offered, sorted([bh.STURM, bh.VON_BOLT]), "Sturm and Von Bolt offered")
    shot(ctx, e, "co_select_two")
    ctx.eq(d.choose_cos(1, prefs=[bh.VON_BOLT]), [bh.VON_BOLT], "Von Bolt picked")
    g._units_base = g._players_base = None
    d.wait_control()
    ctx.eq(d.mission(), 1, "mission 2")
    ps = [g.player(1), g.player(2)]
    ctx.eq((ps[0]["co"], ps[1]["co"]), (bh.VON_BOLT, 17), "the pick leads army 1; Jess holds Green Earth's colours")
    ctx.eq((ps[0]["colour"], ps[1]["colour"]), (5, 3), "the picked CO leads Black Hole's colours")
    shot(ctx, e, "mission2")
    e.close()
    # Only Sturm unlocked (mission 1 won, no recruit), Hawke unlocked too.
    for unlocked, want, label in ((0b1, [bh.STURM], "only Sturm unlocked: only Sturm"),
                                  (0b101, [bh.STURM], "Hawke unlocked but not in the pool: not offered")):
        e, g, d = boot(ctx)
        d.start_at(won_mask=1, unlocked_mask=unlocked)
        ctx.eq(d.map_flags()[:2], [2, 1], f"{label}: mission 2 open")
        ctx.eq(to_co_select(ctx, e, d, label), want, label)
        shot(ctx, e, f"co_select_{len(want)}_unlocked")
        e.close()


AW2_PAGES = 0x0858265C
PAGE_POOLS = (0x0806BFEC, 0x0806C0B0, 0x0806C108, 0x0806C134)
CREDITS = 0x0203FD17
ROLL_FNS = (0x0806C075, 0x0806C0E5)


def roll_lines(e, pages):
    out, k = [], 0
    while True:
        page = e.u32(pages + 4 * k)
        if not page:
            return out
        for s in range(6):
            kind, ptr = e.u32(page + 8 * s), e.u32(page + 8 * s + 4)
            if kind:
                t = e.read(ptr, 40)
                out.append((kind, t[:t.index(0)].decode("latin-1")))
        k += 1


@test(modes=("ds",))
def bh_campaign_credits_after_the_last_mission(ctx):
    """The campaign's last mission (FINAL_MISSION): its win plays the scene on
    the map, then the staff roll from data (headings and names), then Select
    Mode with the session over and AW2's own pages back."""
    e, g, d = boot(ctx)
    d.picks = {FINAL_MISSION: 2}
    d.start_at(won_mask=(1 << FINAL_MISSION) - 1, unlocked_mask=0x3FF)
    d.pick_mission()
    d.choose_cos(2, prefs=[bh.STURM, bh.CLONE_ANDY])
    g._units_base = g._players_base = None
    d.leave_setup()
    d.wait_control()
    ctx.eq(d.mission(), FINAL_MISSION, "the last mission")
    # (a naval mission has no foot soldier to rout: the enemy's Fighter is made an Infantry, a test aid)
    foe = next((u for u in g.units(army=2) if u["type"] == 16), None)
    if foe and not any(u["type"] in dc.DIRECT for u in g.units(army=2)):
        at = g.unit_addr(foe["id"])
        e.w8(at, 1)
        e.w16(at + 4, (e.u16(at + 4) & ~0x7F) | 100)
    ctx.require(d.force_win(), "the last mission won (test aid)")
    for f in range(80000):
        if e.u8(CREDITS) >= 3:
            break
        if f % 20 == 0 and (e.u8(CREDITS) == 0 or not d.world_map_up()):
            e.press("A", 4)
        e.wait(1)
    ctx.require(e.u8(CREDITS) == 3, "the map left for the credits after the scene")
    pages = e.u32(PAGE_POOLS[0])
    ctx.check(pages != AW2_PAGES and all(e.u32(a) == pages for a in PAGE_POOLS), f"the roll reads the campaign's pages ({pages:#x})")
    got = roll_lines(e, pages)
    ctx.eq(got, CREDITS_PAGES, "the pages are the data's sections")
    rolled = False
    for k in range(200):
        e.wait(60)
        fns = {e.u32(0x0200D610 + 0x6C * j + 0x10) for j in range(32)}
        if fns & set(ROLL_FNS):
            if not rolled:
                e.wait(70)
                shot(ctx, e, "credits")
                e.wait(200)
                shot(ctx, e, "credits_page_2")
            rolled = True
        if rolled and any(e.u32(0x0200D610 + 0x6C * j) in dc.WHEELS for j in range(32)):
            break
    ctx.check(rolled, "the roll ran")
    e.wait(60)
    ctx.eq(e.u8(dc.ACTIVE), 0, "back on Select Mode: the session is over")
    ctx.check(all(e.u32(a) == AW2_PAGES for a in PAGE_POOLS), "AW2's own pages back")
    ctx.eq(e.u8(dc.P_NEXT + 1), 1, "the campaign recorded as over")
    ctx.eq(d.won(), 1 << FINAL_MISSION | ((1 << FINAL_MISSION) - 1), "every mission won")


# -- the data format's fields (bh_campaign::features_def, played with TANGOAW2_BH_FEATURES) ----------
DS_TABLE = 0x08E00000
GMAP = 0x0201E450
DAY = 0x03004080
FEATURE_PICKS = {0: 0, 1: 2}


def boot_features(ctx, save=None):
    e = Emu(save=save or paths.base_save(), ds=ctx.ds, env=bh.FEATURES)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = bh.BhCampaign(g)
    d.picks = FEATURE_PICKS
    return e, g, d


def tile_at(e, x, y):
    w = e.u16(GMAP)
    row = e.u16(GMAP + 0x417A + 2 * y)
    return e.u16(GMAP + 0xA22 + 2 * (row + x)) & 0x1FF


@test(modes=("ds",))
def bh_campaign_mission_data_fields(ctx):
    """A mission's data reaches the game: each army's starting funds, rain
    and fog, a day limit in the map header, structures (a Black Factory, a
    Black Crystal, a Black Obelisk, a laser) stamped on the map, a trigger
    that sets funds and plays a scene on day 2, and the recruit a win unlocks."""
    e, g, d = boot_features(ctx)
    d.start_bh(new=True, pick=False)
    follow_prologue(ctx, e, d, "p")
    d.pick_mission()
    d.wait_map()
    g._units_base = g._players_base = None
    ctx.eq(e.u32(g.player(1)["addr"]), 5000, "army 1's starting funds, from the data")
    ctx.eq(e.u32(g.player(2)["addr"]), 7000, "army 2's starting funds")
    ps = g.playst()
    ctx.eq((ps["weather"], ps["fog"]), (2, 1), "rain, and fog")
    ctx.eq(e.u16(DS_TABLE + 0x5C * dc.DS_MAP_ID + 0x24), 6, "the day limit in the map's header")
    for (x, y), tile, what in (((6, 4), 0x18D, "the Black Factory"), ((3, 3), 0x192, "the Black Crystal"),
                               ((9, 2), 0x193, "the Black Obelisk"), ((1, 6), 0x181, "the laser")):
        ctx.eq(tile_at(e, x, y), tile, f"{what} stamped at ({x}, {y})")
    shot(ctx, e, "features_one")
    ctx.eq(e.u16(0x086A0000 + 0x104 * bh.STURM + 4), 220, "the mission's song is in the CO table (every army's turn plays it)")
    ctx.eq(e.u16(0x030005CA), 220, "the game started the mission's song")
    ctx.eq(d.size(), (12, 9), "the map's size")
    # Day 2: the trigger sets army 1's funds and plays its scene.
    d.end_turn()
    seen = []
    for _ in range(600):
        t = d.text_shown()
        if t:
            seen.append(t.replace("\x0f", "").replace("\r", " "))
            break
        e.wait(10)
    ctx.eq(seen, ["Day two."], "the day-2 scene")
    d.dialogue()
    g._units_base = g._players_base = None
    d.wait_control()
    ctx.eq(e.u16(DAY), 2, "day 2")
    ctx.eq(e.u32(g.player(1)["addr"]), 10000, "the trigger set army 1's funds (9900) and added 100")
    ctx.eq(d.bonds(), 1, "bond 0 earned by the trigger")
    ctx.eq(d.unlocked(), [bh.STURM, bh.CRUMB], "Crumb unlocked in the middle of the mission by the trigger's Action::Unlock (the promotion)")
    hawke_page = e.u32(0x08610A38 + 4 * e.u16(0x086A0000 + 0x104 * bh.HAWKE + 0x2C))
    ctx.eq(e.read(hawke_page, 40).split(b"\0")[0], b"Bond test: Hawke's\rsecret page.", "Hawke's CO page shows the secret quote, wrapped to the page")
    e.wait(600)
    hit = [(u["army"], u["hp"]) for u in g.units() if u["hp"] < 100]
    ctx.log(f"units after the strike: {[(u['army'], u['type'], u['hp']) for u in g.units()]}")
    ctx.check(any(a == 2 for a, _ in hit), f"the strike (3 HP) hit the enemy cluster ({hit})")
    # The win unlocks Hawke (the data's recruit).
    from aw2test import campaigns as cp
    cp.win_here(e, d)
    ctx.eq(d.unlocked(), [bh.STURM, bh.HAWKE, bh.CRUMB], "Hawke unlocked by mission 1's recruit entry (and Crumb, kept, by the trigger)")
    ctx.check(e.u16(0x086A0000 + 0x104 * bh.STURM + 4) != 220, "back on the world map: the COs' own themes are put back")
    ctx.eq(d.map_flags()[5], 1, "the secret mission's flag: every bond earned (the one the test has)")
    e.close()
    e, g, d = boot_features(ctx)
    d.start_at(won_mask=1, unlocked_mask=0b1)
    ctx.eq(d.map_flags()[5], 0, "the secret mission's flag stays hidden without the bond")


def courier(g):
    return next(u for u in g.units(1) if u["type"] == bh.unit_id("infantry") and u["hp"] <= 10)


@test(modes=("ds",))
def bh_campaign_named_unit_must_reach_a_place(ctx):
    """A named 1 HP unit ("courier") must reach (10, 5): when it stands there
    after an action the mission is won (its scene first); at day 4 without
    that it is lost; a named unit that has gone stays gone (a unit built in
    its slot is not it: the death latch). The mission has a tag pair for the
    player (two picks) against Hawke and Koal in Orange Star's colours; the
    pair has its own scene; the courier at (5, 5) calls reinforcements and
    funds."""
    from aw2test import campaigns as cp

    def settle(e, d, until, frames=900):
        seen = []
        for _ in range(frames):
            t = d.text_shown()
            if t and (not seen or seen[-1] != t):
                seen.append(t.replace("\x0f", "").replace("\r", " "))
            if until():
                break
            e.press("A", 4)
            e.wait(6)
        return seen

    for outcome in ("win", "lose", "gone"):
        e, g, d = boot_features(ctx)
        d.start_at(won_mask=1, unlocked_mask=0b101)
        d.pick_mission()
        picks = d.choose_cos(2, prefs=[bh.STURM, bh.HAWKE])
        ctx.eq(sorted(picks), sorted([bh.STURM, bh.HAWKE]), "the pair picked from the unlocked ones in the pool")
        g._units_base = g._players_base = None
        d.wait_control()
        ctx.eq(d.mission(), 1, "mission 2")
        c = courier(g)
        ctx.eq((c["x"], c["y"], c["hp"]), (1, 1, 10), "the named unit starts at (1, 1) with 1 HP")
        ps = [g.player(1), g.player(2)]
        ctx.eq((ps[0]["colour"], ps[1]["colour"], ps[1]["co"]), (5, 1, bh.HAWKE), "Hawke leads army 2 in Orange Star's colours")
        shot(ctx, e, f"courier_{outcome}")
        tank = next(u for u in g.units(1) if u["type"] == 5)
        if outcome == "win":
            funds = e.u32(g.player(1)["addr"])
            d.place_unit(c, 5, 5)
            e.wait(40)
            g.select(tank["x"], tank["y"])
            g.move_to(tank["x"], tank["y"])
            g.choose("Wait", g.ACTION_MENU)
            seen = settle(e, d, lambda: e.u32(g.player(1)["addr"]) == funds + 500 and not d.scripts_running(), 600)
            ctx.check("Together." in seen, f"the pair's scene (Sturm and Hawke) ({seen})")
            ctx.eq(e.u32(g.player(1)["addr"]), funds + 500, "the courier at (5, 5): funds added")
            ctx.check(g.unit_at(3, 3) is not None, "the courier at (5, 5): a unit reinforces (3, 3)")
            spawned = g.unit_at(4, 3)
            ctx.require(spawned is not None and spawned["type"] == 5, "the reinforcement Tank at (4, 3)")
            ctx.eq((spawned["ammo"], spawned["fuel"], spawned["hp"]), (9, 70, 100), "a spawned Tank has full ammo, fuel and HP")
            d.place_unit(c, 10, 5)
            e.wait(4)
            fresh = g.unit_at(3, 3)
            g.select(3, 3)
            g.move_to(3, 3)
            g.choose("Wait", g.ACTION_MENU)
            seen = settle(e, d, lambda: d.last_result()["result"] == 1)
            ctx.check("The courier is out." in seen, f"the trigger's scene ({seen})")
            ctx.eq(d.last_result()["result"], 1, "won by the named unit's arrival")
        elif outcome == "lose":
            e.w16(DAY, 3)
            d.end_turn()
            settle(e, d, lambda: d.last_result()["result"] == 2)
            ctx.eq(d.last_result()["result"], 2, "lost: day 4 and the courier not out")
        else:
            a = g.unit_addr(c["id"])
            e.w8(a, 0)          # the courier is gone ...
            e.wait(10)
            e.w8(a, 5)          # ... and a new unit takes its slot
            e.wait(4)
            d.end_turn()
            settle(e, d, lambda: d.last_result()["result"] == 2)
            ctx.eq(d.last_result()["result"], 2, "the courier gone stays gone, whoever has its slot: lost")
        e.close()


@test(modes=("ds",))
def bh_campaign_two_fronts_from_data(ctx):
    """A mission's second front, from data: the player's tag pair on the main
    front (two picks) and a CO of the player's own for the second (a third
    pick, after the main front's); the second front's own map; the main
    front's round ending starts the second front."""
    from aw2test import twofront as tf
    e, g, d = boot_features(ctx)
    d.picks = {0: 0, 1: 2, 2: 2}   # (the main front's pick, then the second front's: another CO)
    d.start_at(won_mask=0b11, unlocked_mask=0b101)
    d.pick_mission()
    d.wait_map()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), 2, "mission 3")
    ctx.eq(tf.state(e)["second"], 1, f"the mission is on two fronts ({tf.state(e)})")
    ctx.eq(g.player(1)["co"], bh.STURM, "the main front's army 1: the first pick (Sturm)")
    ctx.eq((e.u8(tf.SECOND_COS), e.u8(tf.SECOND_COS + 1)), (bh.HAWKE, bh.KOAL), "the second front: the player's own pick (Hawke), Koal from the data")
    ctx.eq(d.size(), (10, 4), "the main front's map")
    ctx.eq(e.u8(tf.LIVE), 0, "the main front on the screen")
    shot(ctx, e, "two_fronts_main")
    d.end_turn()
    ctx.require(e.wait_until(lambda: e.u8(tf.SECOND) == 1 or e.u8(tf.LIVE) == 1, 3000, step=10), "the second front starts after the main front's round")
    for _ in range(600):
        if e.u8(tf.LIVE) == 1 and not e.u8(tf.BUSY):
            break
        e.wait(10)
    ctx.eq(e.u8(tf.LIVE), 1, "the second front on the screen")
    e.wait(60)
    ctx.eq(d.size(), (7, 3), "the second front's own map")
    shot(ctx, e, "two_fronts_second")


@test(modes=("ds",))
def bh_campaign_maps_of_aw2_and_dual_strike(ctx):
    """A mission can name one of AW2's maps or one of Dual Strike's (read from
    the player's ROM) and keeps its terrain and deployment: AW2's first
    campaign map (15 x 10, 6 units) and Dual Strike's Jake's Trial (16 x
    12), with the data's armies and COs."""
    for index, size, units, cos in ((3, (15, 10), 6, (bh.STURM, bh.LASH)), (4, (16, 12), 6, (bh.STURM, bh.ADDER))):
        e, g, d = boot_features(ctx)
        d.picks = {3: 0, 4: 0}
        d.start_at(won_mask=(1 << index) - 1, unlocked_mask=0b1)
        d.pick_mission()
        d.wait_map()
        g._units_base = g._players_base = None
        ctx.eq(d.mission(), index, f"mission {index + 1}")
        ctx.eq(d.size(), size, "the map's size")
        ctx.eq(len(g.units()), units, "the map's own deployment")
        ctx.eq((g.player(1)["co"], g.player(2)["co"]), cos, "the data's COs")
        shot(ctx, e, f"map_{index}")
        e.close()


@test(modes=("ds",))
def bh_campaign_and_ds_campaign_in_one_boot(ctx):
    """The two campaigns share the engine's ROM range and the world map's
    tables, rewritten when the other is chosen: BH, then DS (its Omega Land
    art and its data), then BH again, each with its own record, in one
    boot."""
    from aw2test import campaigns as cp
    DATA, TILES_POOL = 0x08F00000, 0x080769B4
    e, g, d = boot(ctx)
    d.start_bh(new=True, pick=False)
    d.wait_world_map()
    ctx.eq(e.u32(DATA), 0x44445344, "the BH Campaign's data in the range")
    ctx.eq(e.u32(TILES_POOL), 0x081CC5F0, "BH: AW2's map art")
    ctx.eq(d.map_flags()[:2], [1, 0], "BH: its one flag")
    cp.leave_map(e, d, close=True)
    cp.ds_start(e, d, new=True, from_title=False)
    ctx.eq(e.u8(bh.SOURCE), 0, "the DS Campaign chosen")
    ctx.eq(e.u32(DATA), 0x44435344, "the DS Campaign's data written over it")
    ctx.eq(e.u32(TILES_POOL), 0x08FC0100, "DS: Omega Land's art")
    ctx.eq(e.u8(0x08FC0100), 0x10, "DS: its tiles are in the ROM (written after the BH session's tables)")
    ctx.eq(e.u32(dc.P_MAGIC), dc.PROGRESS_MAGIC, "DS: its own record")
    ctx.eq(d.map_flags()[0], 1, "DS: Jake's Trial's flag")
    shot(ctx, e, "ds_after_bh")
    cp.leave_map(e, d, close=True)
    d.start_bh(new=False, from_title=False, pick=False)
    d.wait_world_map()
    ctx.eq(e.u8(bh.SOURCE), bh.BH, "the BH Campaign chosen again")
    ctx.eq(e.u32(DATA), 0x44445344, "its data back")
    ctx.eq(e.u32(TILES_POOL), 0x081CC5F0, "AW2's map art again")
    ctx.eq(e.u32(dc.P_MAGIC), bh.BH_MAGIC, "its record")
    ctx.eq(d.map_flags()[:2], [1, 0], "its flag")


@test(modes=("ds",))
def bh_campaign_built_map(ctx):
    """A map built by the map tool (five/bhmap.py, five/bh/example.txt) plays as
    built: its size, its joined tiles (the road, the river, the shoal) and its
    own units, one of them named; the secret mission it is used for opens
    only with every bond."""
    e, g, d = boot_features(ctx)
    d.picks = {5: 0}
    d.start_at(won_mask=0xDF, unlocked_mask=1 | 1 << 12)
    ctx.eq(d.map_flags()[5], 1, "the secret mission is open with the bond earned")
    d.pick_mission()
    d.wait_map()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), 5, "mission 6")
    ctx.eq(d.size(), (14, 8), "the built map's size")
    ctx.eq(len(g.units()), 4, "its four units")
    road = [tile_at(e, 3, y) for y in range(1, 4)]
    ctx.check(all(t in (0x40, 0x41, 0x42, 0x60, 0x61, 0x62, 0xE0, 0xE1, 0xC0, 0xC1, 0x80, 0xA0, 0xA1) for t in road), f"the road is joined road tiles ({[hex(t) for t in road]})")
    shot(ctx, e, "built_map")


@test(modes=("ds",))
def bh_campaign_five_armies(ctx):
    """A five-army mission in the campaign (crate::five): Orange Star, Blue
    Moon, Green Earth and Yellow Comet against the player's Black Hole, the
    game's fifth army, with a tag pair (Sturm and Hawke); a built map with
    five HQs."""
    e, g, d = boot_features(ctx)
    d.picks = {6: 0}
    d.start_at(won_mask=0b0111111, unlocked_mask=1 | 1 << 12)
    d.pick_mission()
    d.wait_map()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), 6, "mission 7")
    shot(ctx, e, "five_armies")
    ctx.eq(d.size(), (16, 15), "the map")
    players = [g.player(a) for a in range(1, 6)]
    ctx.eq([p["co"] for p in players], [bh.ANDY, bh.OLAF, bh.EAGLE, bh.KANBEI, bh.STURM], "the COs, the player's the fifth army's")
    ctx.eq([p["colour"] for p in players], [1, 2, 3, 4, 5], "the colours")
    ps = d.controllers_five()
    ctx.eq(ps, [2, 2, 2, 2, 1], "the computer commands four armies, the player the fifth")
    ctx.eq(len(g.units()), 6, "the map's six units")
    from aw2test import tag
    ctx.eq(e.u8(tag.rec(5) + tag.P_CO) if e.u8(tag.MAGIC_AT) == 0x7A else None, bh.HAWKE, "the player's tag partner (Hawke) on army 5")
    ctx.eq(e.u8(0x02030206), 2, "the five-army game is on (crate::five)")
    from aw2test import campaigns as cp
    # the four computer armies yield (the player's win by AW2's own rules)
    for a in range(1, 5):
        e.w8(g.player(a)["addr"] + 0x31, 1)
    d.end_turn()
    for _ in range(900):
        if d.last_result()["result"] == 1 and d.world_map_up():
            break
        e.press("A", 4)
        e.wait(10)
    ctx.eq(d.last_result()["result"], 1, "the four enemy armies routed: won")
    ctx.eq(d.won() >> 6 & 1, 1, "mission 7 won")
    ctx.eq(e.u8(0x02030206), 0, "back on the world map the patched game is off again")


@test(modes=("ds",))
def bh_campaign_second_stage(ctx):
    """The second-stage pattern: army 2 (Nell) has an HQ; army 3 (Andy), on her
    team, holds one token unit. When army 2 is defeated the battle goes on
    (army 3's team is alive) and the trigger gives army 3 its reinforcements,
    funds and scene, instead of the player winning."""
    e, g, d = boot_features(ctx)
    d.picks = {7: 0}
    d.start_at(won_mask=0b01111111, unlocked_mask=1)
    d.pick_mission()
    d.wait_map()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), 7, "mission 8")
    n0 = len(g.units())
    e.w8(g.player(2)["addr"] + 0x31, 1)       # army 2 yields at its turn
    d.end_turn()
    d.wait_control()
    ctx.eq(e.u16(0x03004080), 2, "day 2")
    e.wait(120)
    g.select(1, 1)
    g.move_to(1, 1)
    g.choose("Wait", g.ACTION_MENU)
    seen = []
    for _ in range(900):
        t = d.text_shown()
        if t and (not seen or seen[-1] != t):
            seen.append(t.replace("\x0f", ""))
        if d.last_result()["result"]:
            break
        if e.u32(g.player(3)["addr"]) >= 9000 and not d.scripts_running():
            break
        e.press("A", 4)
        e.wait(8)
    ctx.eq(d.last_result()["result"], 0, "the battle went on (the player did not win)")
    ctx.check("Stage two." in seen, f"the scene ({seen})")
    ctx.check(e.u32(g.player(3)["addr"]) >= 9000, "army 3's funds added")
    ctx.log(f"units: {[(u['army'], u['type'], u['x'], u['y']) for u in g.units()]}")
    ctx.eq(len(g.units(3)), 3, f"army 3: the token and two reinforcements ({len(g.units(3))})")
    shot(ctx, e, "second_stage")


@test(modes=("ds",))
def bh_campaign_free_play_replays_change_nothing(ctx):
    """With the last mission won (Free Play) the map offers every mission
    again, the won ones too; a replay's win changes neither the won missions,
    nor the roster, nor the bonds, nor the progress step, nor the best score,
    and starts no staff roll; a campaign still being played offers only its
    open missions."""
    from aw2test import campaigns as cp
    e, g, d = boot(ctx)
    d.start_at(won_mask=0b01, unlocked_mask=1)
    d.wait_world_map()
    ctx.eq(d.map_flags()[:2], [2, 1], "before the end: mission 1 cleared, mission 2 open")
    e.close()
    e, g, d = boot(ctx)
    every = (1 << (FINAL_MISSION + 1)) - 1
    d.start_at(won_mask=every, unlocked_mask=1)
    d.wait_world_map()
    flags = d.map_flags()
    ctx.eq(flags[:FINAL_MISSION + 1], [2] * (FINAL_MISSION + 1), "Free Play: every mission cleared (a cleared flag is still on the map)")
    shot(ctx, e, "free_play_map")
    step, records = e.u8(dc.P_NEXT), e.read(dc.RECORDS, 16)
    d.pick_mission()
    if d.picks.get(0):
        d.choose_cos(d.picks[0], prefs=[bh.STURM])
    g._units_base = g._players_base = None
    d.wait_control()
    ctx.eq(d.mission(), 0, "mission 1 replayed")
    cp.win_here(e, d)
    e.wait(120)
    ctx.eq(d.won(), every, "the won missions as they were")
    ctx.eq(d.unlocked(), [bh.STURM], "Von Bolt not unlocked again by the replay")
    ctx.eq(e.u8(dc.P_NEXT), step, "the progress step as it was")
    ctx.eq(e.read(dc.RECORDS, 16), records, "the records as they were")
    ctx.eq(e.u8(CREDITS), 0, "no staff roll for a replay")
    ctx.eq(d.last_result()["result"], 1, "the replay was won")


@test(modes=("ds",))
def bh_campaign_lose_when_the_gate_city_is_captured(ctx):
    """A named city (a city of army 1 at (5, 0)) is lost with the mission once
    an enemy owns it: a trigger on the city's owner."""
    e, g, d = boot_features(ctx)
    d.picks = {8: 0}
    d.start_at(won_mask=0xFF, unlocked_mask=0b1)
    d.pick_mission()
    d.wait_map()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), 8, "mission 9")
    row = e.u16(GMAP + 0x417A)
    at = GMAP + 0x1432 + row + 5
    ctx.eq(e.u8(at) >> 5, 1, "the Gate city starts as army 1's")
    ctx.eq(d.last_result()["result"], 0, "not lost")
    e.w8(at, (e.u8(at) & 0x1F) | 2 << 5)       # army 2 captures it (test aid)
    e.wait(10)
    g.select(1, 1)
    g.move_to(1, 1)
    g.choose("Wait", g.ACTION_MENU)
    seen = []
    for _ in range(600):
        t = d.text_shown()
        if t and (not seen or seen[-1] != t):
            seen.append(t.replace("\x0f", ""))
        if d.last_result()["result"]:
            break
        e.press("A", 4)
        e.wait(8)
    ctx.check("The Gate has fallen." in seen, f"the scene ({seen})")
    ctx.eq(d.last_result()["result"], 2, "lost")


@test(modes=("ds",))
def bh_campaign_secret_mission_credits_and_sonja(ctx):
    """The secret mission (f06, open with every bond earned and the campaign
    played) recruits Sonja when won, and its win adds the secret sections to
    the staff roll (a credits line); before it the roll has the plain
    sections only."""
    from aw2test import campaigns as cp
    e, g, d = boot_features(ctx)
    d.picks = {5: 0}
    d.start_at(won_mask=0xDF, unlocked_mask=1 | 1 << 12)
    d.wait_world_map()
    e.wait(30)
    pages = e.u32(PAGE_POOLS[0])
    ctx.check(pages != AW2_PAGES, "the campaign's pages are installed")
    texts = [t for _, t in roll_lines(e, pages)]
    ctx.check("*SECRET LINE*" not in texts, f"no secret line before the secret mission ({texts})")
    ctx.check(bh.SONJA not in d.unlocked(), "Sonja not in the roster yet")
    d.pick_mission()
    d.wait_map()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), 5, "the secret mission")
    cp.win_here(e, d)
    e.wait(120)
    ctx.check(bh.SONJA in d.unlocked(), f"Sonja recruited by the secret mission ({d.unlocked()})")
    ctx.eq(d.won() >> 5 & 1, 1, "won")
    pages = e.u32(PAGE_POOLS[0])
    texts = [t for _, t in roll_lines(e, pages)]
    ctx.check("*SECRET LINE*" in texts and "THE AUDITOR" in texts, f"the secret section is in the roll ({texts})")


ONYX = 0x0203FFC8              # crate::onyx::STATE
O_ON, O_HITS, O_PHASE, O_LAST, O_OFFLINE = ONYX, ONYX + 1, ONYX + 2, ONYX + 0x17, ONYX + 0x18
SILOS = [(2, 1), (12, 1), (1, 12), (12, 12)]        # five/bh/five_onyx.txt
OBELISK = (5, 7)


def five_units(e, g):
    """(id, army, type, x, y, hp) of every live unit, the campaign's five-army ids (51 an army)."""
    raw = e.read(g.units_base, 12 * 256)
    out = []
    for uid in range(256):
        r = raw[12 * uid:12 * uid + 12]
        if r[0] == 0 or uid % 51 == 0:
            continue
        out.append((uid, uid // 51 + 1, r[0], r[2], r[3], (r[4] | r[5] << 8) & 0x7F))
    return out


def my_turn(e, d, day, frames=6000):
    """After End: the four computer armies play; then the fifth, the player's (Black Hole), on day `day`."""
    for _ in range(frames // 20):
        if e.u16(0x030033EC) == 5 and e.u16(DAY) == day:
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(20)
    d.wait_control()


@test(modes=("ds",))
def bh_campaign_reversed_onyx(ctx):
    """The reversed Black Onyx (crate::onyx, MissionDef::onyx): Black Hole's
    own satellite on a day cycle. It warns the day before a shot, fires on
    Black Hole's turn every fifth day (the enemy near the target loses 8 HP);
    a foot soldier of the other team on a silo launches at it once (the
    silo spent; a scene by the hit left); four hits destroy it: debris hurts
    Black Hole's units near the Obelisk (never below 1 HP), the Obelisk heals
    nothing for three turns, the player's meters lose 30%; the shots stop."""
    e, g, d = boot_features(ctx)
    d.picks = {9: 0}
    d.start_at(won_mask=0x1DF, unlocked_mask=1)
    d.pick_mission()
    d.wait_map()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), 9, "mission 10")
    ctx.log(f"silo fired at {e.u16(ONYX + 0x10)}, {e.u16(ONYX + 0x12)}; units {five_units(e, g)}")
    ctx.eq((e.u8(O_ON), e.u8(O_HITS), e.u8(O_PHASE)), (3, 4, 1), "the satellite: reversed, 4 hits, charging")
    shot(ctx, e, "reversed_onyx_panel_day1")
    mine = [u for u in five_units(e, g) if u[1] == 5]
    theirs = [u for u in five_units(e, g) if u[1] != 5]
    ctx.eq(len(mine), 2, "the player's two units")
    # Day 4 (the day before a shot): the warning.
    e.w16(DAY, 3)
    d.end_turn()
    my_turn(e, d, 4)
    ctx.eq(e.u16(DAY), 4, "day 4")
    e.wait(30)
    ctx.eq(e.u8(O_PHASE), 2, "day 4: the warning (the day before a shot)")
    shot(ctx, e, "reversed_onyx_panel_warning")
    # Day 5, Black Hole's turn: it fires at the spot the computer scores best for Black Hole.
    before = {u[0]: u[5] for u in five_units(e, g) if u[1] != 5}
    try:
        d.end_turn()
        my_turn(e, d, 5)
    except Exception:
        ctx.log(f"state {[hex(e.u8(ONYX + k)) for k in range(0x1C)]} units {five_units(e, g)} procs {[(hex(a), hex(s0), hex(f)) for a, s0, f in g.procs()]} dayword {e.u16(DAY)} army {e.u16(0x030033EC)}")
        raise
    ctx.eq(e.u16(DAY), 5, "day 5")
    for _ in range(400):
        if e.u8(O_LAST) == 5 and e.u8(O_PHASE) == 1 and not d.scripts_running():
            break
        e.press("A", 4)
        e.wait(10)
    ctx.eq(e.u8(O_LAST), 5, "the shot of day 5 was fired")
    ctx.eq(e.u8(O_PHASE), 1, "charging again")
    after = {u[0]: u[5] for u in five_units(e, g) if u[1] != 5}
    hurt = [k for k in after if after[k] < before.get(k, 0)]
    ctx.log(f"hurt by the shot: {[(k, before[k], after[k]) for k in hurt]}")
    ctx.check(all(before[k] - after[k] <= 80 and after[k] >= 10 for k in hurt), "the shot takes 8 HP at most and never kills")
    shot(ctx, e, "reversed_onyx_after_shot")
    # The silos: an enemy foot soldier on each launches once. (The allies' Tanks are turned
    # into soldiers here: left alone, the computer's soldiers walk onto silos by themselves.)
    ctx.eq(e.u8(O_HITS), 4, "no hit yet: the allies have no foot soldiers")
    allies = [u for u in five_units(e, g) if u[1] != 5]
    ctx.require(len(allies) >= 4, f"four allied units ({len(allies)})")
    # (a Black Hole unit near the Obelisk, hurt, and the meters full, to see the fall)
    near = [u for u in five_units(e, g) if u[1] == 5][0]
    d.place_unit({"id": near[0], "x": near[3], "y": near[4]}, OBELISK[0] + 3, OBELISK[1] + 1)
    a = g.unit_addr(near[0])
    e.w16(a + 4, (e.u16(a + 4) & ~0x7F) | 90)
    meter = g.player(5)["addr"] + 0x20
    e.w32(meter, 40000)
    for k, (sx, sy) in enumerate(SILOS):
        u = allies[k]
        e.w8(g.unit_addr(u[0]), 1)             # a foot soldier
        d.place_unit({"id": u[0], "x": u[3], "y": u[4]}, sx, sy)
        for _ in range(900):
            if e.u8(O_HITS) == 3 - k:
                break
            e.wait(10)
        ctx.eq(e.u8(O_HITS), 3 - k, f"silo {k + 1}: a hit ({e.u8(O_HITS)} left)")
        tile = lambda: e.u16(GMAP + 0xA22 + 2 * (e.u16(GMAP + 0x417A + 2 * sy) + sx)) & 0x1FF
        ctx.check(tile() != 0x180, f"silo {k + 1} is spent (tile {tile():#x})")
        for _ in range(300):
            if e.u8(O_PHASE) in (1, 2, 0) and not d.scripts_running() and e.u8(ONYX + 0xA) == 0:
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(10)
        if k == 0:
            shot(ctx, e, "reversed_onyx_one_hit")
    for _ in range(600):
        if e.u8(O_PHASE) == 0 and not d.scripts_running():
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(10)
    ctx.eq(e.u8(O_HITS), 0, "destroyed")
    ctx.eq(e.u8(O_PHASE), 0, "the satellite is gone")
    ctx.eq(e.u8(O_OFFLINE), 3, "the Obelisk is offline for three turns")
    now = {u[0]: u[5] for u in five_units(e, g)}
    ctx.eq(now[near[0]], 60, "debris: 3 HP off a Black Hole unit near the Obelisk")
    ctx.check(e.u32(meter) < 40000, f"the meter lost a share ({e.u32(meter)} of 40000)")
    shot(ctx, e, "reversed_onyx_destroyed")
    # The scenes by the hits left (after the next action): one down, and the fall.
    seen = []
    for _ in range(300):
        t = d.text_shown()
        if t and (not seen or seen[-1] != t):
            seen.append(t.replace("\x0f", ""))
        if g.idle():
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(10)
    for _ in range(3):
        e.press("B", 4)               # (the cursor may have selected a unit)
        e.wait(10)
    d.end_turn()                  # the allies' turn: after their actions the scenes play
    for _ in range(600):
        t = d.text_shown()
        if t and (not seen or seen[-1] != t):
            seen.append(t.replace("\x0f", ""))
        if "The Onyx falls." in seen and not d.scripts_running():
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(20)
    ctx.check("One down." in seen and "The Onyx falls." in seen, f"the scenes by the hits left ({seen})")


def obj_sprites(e):
    """(tile, x, y) of every visible sprite."""
    import struct
    oam = e.read(0x07000000, 0x400)
    out = []
    for k in range(128):
        a0, a1, a2, _ = struct.unpack_from("<HHHH", oam, 8 * k)
        if (a0 >> 8) & 3 != 2 and (a0 & 0xFF) < 160:
            out.append((a2 & 0x3FF, a1 & 0x1FF, a0 & 0xFF))
    return out


LEGEND_TILE = 735


def title_palette(e):
    """The OBJ palette of the sprites at the map's top left (the "CAMPAIGN"
    title), legend sprites left out."""
    import struct
    oam = e.read(0x07000000, 0x400)
    banks = set()
    for k in range(128):
        a0, a1, a2, _ = struct.unpack_from("<HHHH", oam, 8 * k)
        if (a0 >> 8) & 3 != 2 and (a0 & 0xFF) < 30 and (a1 & 0x1FF) < 110 and (a2 & 0x3FF) != LEGEND_TILE and not 735 <= (a2 & 0x3FF) < 800:
            banks.add(a2 >> 12)
    return {b: e.read(0x05000200 + 32 * b, 32) for b in banks}


@test(modes=("ds",))
def bh_campaign_bond_legend_on_the_world_map(ctx):
    """Nothing about bonds shows on the world map until one is earned. From
    the first bond on a legend (a gold star, "RECRUIT WON OVER", "BONDS n/9",
    AW2's font) sits at the top left: below the "CAMPAIGN" title while that
    shows, at the very top with the mission panel open (the title gone). The
    title keeps its colours (the legend takes an OBJ palette no sprite of the
    frame uses)."""
    titles = {}
    for bonds in (0, 1):
        e, g, d = boot_features(ctx)
        d.start_at(won_mask=0, unlocked_mask=1 | (bonds << 12))
        d.wait_world_map()
        e.wait(30)
        legend = [s for s in obj_sprites(e) if s[0] == LEGEND_TILE]
        ctx.eq(bool(legend), bonds > 0, f"the legend with {bonds} bonds")
        if bonds:
            ctx.require(legend, "the legend")
            ctx.check(all(s[2] >= 30 for s in legend), f"below the title ({legend})")
        titles[bonds] = title_palette(e)
        shot(ctx, e, f"bond_legend_{bonds}")
        e.press("A", 6)
        e.wait(240)
        legend = [s for s in obj_sprites(e) if s[0] == LEGEND_TILE]
        ctx.eq(bool(legend), bonds > 0, f"the legend with the panel open, {bonds} bonds")
        if bonds:
            ctx.check(all(s[2] < 20 for s in legend), f"at the very top with the title gone ({legend})")
        shot(ctx, e, f"bond_panel_{bonds}")
        e.close()
    ctx.check(titles[0], "the title's palette found")
    ctx.eq(titles[0], titles[1], "the title's colours are the same with and without the legend")


@test(modes=("ds",))
def bh_campaign_bond_quote_on_the_co_page(ctx):
    """With the bond earned Hawke's CO page (in a BH mission) reads the secret
    quote; without it the page's own text. Pictures of the page, both ways."""
    for earned in (False, True):
        e, g, d = boot_features(ctx)
        d.picks = {1: 2}
        d.start_at(won_mask=1, unlocked_mask=0b101 | (1 << 12 if earned else 0))
        d.pick_mission()
        d.choose_cos(2, prefs=[bh.HAWKE, bh.STURM])
        g._units_base = g._players_base = None
        d.wait_control()
        ctx.eq(d.mission(), 1, "mission 2")
        g.open_map_menu()
        g.choose("CO", g.MAP_MENU)
        e.wait(120)
        for page in range(3):
            shot(ctx, e, f"co_page_{'bond' if earned else 'plain'}_{page}")
            e.press("DOWN", 4)
            e.wait(60)
        e.close()


def stock_check(ctx, e, g, label, hurt=(), empty_armies=(), dry=()):
    """Every live unit, both sides, has its type's full ammo and fuel (the
    unit table in use: the pack's, `0x08680000`, 0x5C a record: +0x0B ammo,
    +0x10 fuel)."""
    per = 51 if e.u8(0x02030206) in (1, 2) else 64
    raw = e.read(g.units_base, 12 * 256)
    bad, n = [], 0
    for uid in range(256):
        r = raw[12 * uid:12 * uid + 12]
        if r[0] == 0 or uid % per == 0:
            continue
        n += 1
        stats = e.read(0x08680000 + 0x5C * r[0], 0x5C)
        ammo, fuel, hp = ((r[4] | r[5] << 8) >> 7) & 0xF, r[6] & 0x7F, r[4] & 0x7F
        if hp != 100 and (r[0], hp) not in hurt:
            bad.append(("hp", uid // per + 1, r[0], hp))
        # (a computer army may have moved a square before the check: fuel burns)
        if uid // per + 1 in empty_armies:
            if ammo != 0:
                bad.append(("ammo", uid // per + 1, r[0], ammo))
            continue
        if ammo == 0 and (uid // per + 1, r[0]) in dry:
            continue        # (asked for on purpose: UnitDef::ammo(0))
        if ammo != stats[0x0B] & 0xF or not stats[0x10] & 0x7F >= fuel >= (stats[0x10] & 0x7F) - 9:
            bad.append((uid // per + 1, r[0], ammo, fuel, stats[0x0B] & 0xF, stats[0x10] & 0x7F))
    ctx.require(n > 0, f"{label}: units on the map")
    ctx.check(not bad, f"{label}: every unit starts with 10 HP (100) and full ammo and fuel; wrong ((army, type, ammo, fuel, max ammo, max fuel) or (hp, army, type, hp)): {bad}")


@test(modes=("ds",))
def bh_campaign_units_start_with_full_ammo_and_fuel(ctx):
    """Units deployed from data (both sides, a built map's, a named one's, a
    five-army mission's, a second front's) start with their type's full
    ammo and fuel; `UnitDef::ammo` / `fuel` ask for less on purpose."""
    cases = [(0, 0b0), (1, 0b1), (6, 0x3F & ~0), (9, 0x1DF), (10, 0x3FF & ~(1 << 5))]
    for mission, won in cases:
        e, g, d = boot_features(ctx)
        d.picks = {mission: 0, 1: 2}
        d.start_at(won_mask=won & ((1 << mission) - 1) if mission else 0, unlocked_mask=0b101)
        d.pick_mission()
        d.wait_map()
        g._units_base = g._players_base = None
        ctx.eq(d.mission(), mission, f"mission {mission + 1}")
        stock_check(ctx, e, g, f"mission {mission + 1}", hurt=((1, 10),) if mission == 1 else (), empty_armies=(1, 2, 3, 4) if mission == 9 else (),
                    dry=((1, 5), (2, 5), (3, 5), (4, 5)) if mission == 9 else ())
        e.wait(30)
        shot(ctx, e, f"start_units_{mission + 1}")
        e.close()


@test(modes=("ds",))
def bh_campaign_unit_ammo_and_fuel_on_purpose(ctx):
    """`UnitDef::ammo(2).fuel(30)` starts a Tank with 2 rounds and 30 fuel
    (the mission asks for it; every other unit stays full)."""
    e, g, d = boot_features(ctx)
    d.picks = {8: 0}
    d.start_at(won_mask=0xFF, unlocked_mask=1)
    d.pick_mission()
    d.wait_map()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), 8, "mission 9")
    tanks = [u for u in g.units() if u["type"] == 5]
    ctx.eq([(t["ammo"], t["fuel"]) for t in tanks], [(2, 30)], "the Tank's own ammo and fuel")
    inf = [u for u in g.units() if u["type"] == 1]
    ctx.check(all(u["fuel"] == 99 for u in inf), "the soldiers' fuel is full")


@test(modes=("ds",))
def bh_campaign_an_extra_bond_does_not_count(ctx):
    """The last bond of the features campaign is an extra (as Crumb's): earned
    alone it opens no secret mission and shows no legend; with the counted one
    the secret mission is open and the legend counts 1 of 1."""
    for mask, want_secret, want_legend in ((1 << 13, 0, False), (1 << 12, 1, True), (3 << 12, 1, True)):
        e, g, d = boot_features(ctx)
        d.start_at(won_mask=1, unlocked_mask=1 | mask)
        d.wait_world_map()
        e.wait(30)
        ctx.eq(d.map_flags()[5], want_secret, f"bond bits {mask >> 12:02b}: the secret mission's flag")
        ctx.eq(any(s[0] == LEGEND_TILE for s in obj_sprites(e)), want_legend, f"bond bits {mask >> 12:02b}: the legend")
        e.close()
