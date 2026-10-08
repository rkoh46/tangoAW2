"""The BH Campaign (bh_campaign.rs, custom_campaign.rs): a campaign defined
as data, played by the DS Campaign's engine; Select Mode's Campaign
chooser lists it third, with the Dual Strike pack only. Two placeholder
missions prove the pipeline: New, the prologue, AW2's world map with the
first flag, mission 1 (Sturm against Von Bolt in Green Earth's colours),
its win unlocking Von Bolt and opening the second flag, mission 2 (the
player picks Sturm or Von Bolt), the staff roll."""

import os

from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game, NavError
from aw2test.harness import test

OAM = 0x07000000
LABEL_TILES = (832, 868)          # campaign_menu::TILES, one label each


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
        t = t.replace("\x0f", "").replace("\r", " ") if t else t
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
    """New: the prologue (placeholder pages from data), then AW2's own world
    map with one flag, on the Black Hole land."""
    e, g, d = boot(ctx)
    d.start_bh(new=True, pick=False)
    ctx.eq(e.u8(bh.SOURCE), bh.BH, "the BH Campaign's session")
    texts = follow_prologue(ctx, e, d, "prologue")
    ctx.eq(texts, ["Placeholder prologue, page one. Black Hole rises again.",
                   "Placeholder prologue, page two. Sturm leads the way."], "the prologue's pages, from data")
    ctx.require(d.world_map_up(), "the world map is up")
    e.wait(60)
    flags = d.map_flags()
    ctx.eq(flags[:2], [1, 0], "one flag: mission 1 open, mission 2 not yet")
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
    are as the data says, the win unlocks Von Bolt and opens mission 2's flag."""
    from aw2test import campaigns as cp
    e, g, d = boot(ctx)
    first_mission(ctx, e, d)
    ctx.eq(d.mission(), 0, "mission 1")
    g._units_base = g._players_base = None
    ps = [g.player(1), g.player(2)]
    shot(ctx, e, "mission1")
    ctx.eq((ps[0]["co"], ps[1]["co"]), (bh.STURM, bh.VON_BOLT), "Sturm leads army 1, Von Bolt army 2")
    ctx.eq((ps[0]["colour"], ps[1]["colour"]), (5, 3), "army 1 in Black Hole's colours, army 2 in Green Earth's")
    ctx.eq(d.size(), (12, 8), "the data's map")
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
    ctx.eq((ps[0]["co"], ps[1]["co"]), (bh.VON_BOLT, bh.KINDLE), "the pick leads army 1; Kindle holds the Yellow Comet colours")
    ctx.eq((ps[0]["colour"], ps[1]["colour"]), (5, 4), "colour and CO are independent")
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
    """Mission 2 is the placeholder campaign's last: its win plays the scene on
    the map, then the staff roll from data (headings and names), then Select
    Mode with the session over and AW2's own pages back."""
    e, g, d = boot(ctx)
    d.start_at(won_mask=1, unlocked_mask=0b11)
    d.pick_mission()
    d.choose_cos(1, prefs=[bh.STURM])
    g._units_base = g._players_base = None
    d.wait_control()
    ctx.eq(d.mission(), 1, "mission 2")
    ctx.require(d.force_win(), "mission 2 won (test aid)")
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
    ctx.eq(got, [(1, "*BH CAMPAIGN*"), (2, "PLACEHOLDER"), (1, "*THANKS FOR PLAYING*")], "the pages are the data's sections")
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
    ctx.eq(d.won(), 0b11, "both missions won")


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
    ctx.eq(e.u32(g.player(1)["addr"]), 9900, "the trigger set army 1's funds")
    # The win unlocks Hawke (the data's recruit).
    from aw2test import campaigns as cp
    cp.win_here(e, d)
    ctx.eq(d.unlocked(), [bh.STURM, bh.HAWKE], "Hawke unlocked by mission 1's recruit entry")


def courier(g):
    return next(u for u in g.units(1) if u["type"] == bh.unit_id("infantry") and u["hp"] <= 10)


@test(modes=("ds",))
def bh_campaign_named_unit_must_reach_a_place(ctx):
    """A named 1 HP unit ("courier") must reach (10, 5): when it stands there
    after an action the mission is won (its scene first); at day 4 without
    that it is lost. The mission has a tag pair for the player (two picks)
    against Hawke and Koal in Orange Star's colours."""
    from aw2test import campaigns as cp
    for outcome in ("win", "lose"):
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
        if outcome == "win":
            d.place_unit(c, 10, 5)
            e.wait(4)
            tank = next(u for u in g.units(1) if u["type"] == 5)
            g.select(tank["x"], tank["y"])
            g.move_to(tank["x"], tank["y"])
            g.choose("Wait", g.ACTION_MENU)
            seen = []
            for _ in range(900):
                t = d.text_shown()
                if t and (not seen or seen[-1] != t):
                    seen.append(t.replace("\x0f", "").replace("\r", " "))
                if d.last_result()["result"] == 1:
                    break
                e.press("A", 4)
                e.wait(6)
            ctx.check("The courier is out." in seen, f"the trigger's scene ({seen})")
            ctx.eq(d.last_result()["result"], 1, "won by the named unit's arrival")
        else:
            e.w16(DAY, 3)
            d.end_turn()
            for _ in range(900):
                if d.last_result()["result"] == 2:
                    break
                e.press("A", 4)
                e.wait(6)
            ctx.eq(d.last_result()["result"], 2, "lost: day 4 and the courier not out")
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
