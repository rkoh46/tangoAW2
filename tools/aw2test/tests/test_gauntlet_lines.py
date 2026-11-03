"""The Gauntlet maps added after Cinder Sea and Iron Crown (aw2test/gauntlet_maps.py; `-k gauntlet_lines`): one family of tests per map.
 - the map is in the selector and starts from it: the sleeping lines are off the battlefield (no units, no funds, no HQ), only the first line's HQ is on the map;
 - each fall brings the next line (its wave, its war chest, its HQ built), routs the line that fell (no unit, no property left, the captured HQ is the player's city);
 - the last line's HQ wins the battle;
 - the CPU plays: the first line's units move and attack on the days the player does nothing."""

from aw2test import dscampaign as dc
from aw2test import gauntlet as ga
from aw2test import gauntlet_maps as gm
from aw2test import paths, rout, saves
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test


def funds(g, army):
    return int.from_bytes(g.player(army)["raw"][0:4], "little")


def start(ctx, info, co=ga.ANDY, env=None):
    """The map started from Select Mode: (emu, game, driver) with the player in control on day 1."""
    from tests.test_gauntlet_map2 import to_player_turn
    e = Emu(save=paths.base_save(), ds=ctx.ds, env=env)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.start(co, map=info.mission)
    to_player_turn(e, g, d, army=info.player)
    return e, g, d


def control(ctx, e, g, d, info, name):
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.eq(g.current_army(), info.player, f"{name}: it is the player's turn")
    ctx.check(d.in_battle() and not e.u8(dc.LAST_RESULT), f"{name}: the battle goes on")


def selector_and_start(info):
    def fn(ctx):
        e, g, d = start(ctx, info)
        sess = d.session()
        ctx.eq((sess["source"], sess["mission"]), (ga.GAUNTLET, info.mission), f"{info.title}: the session is the Gauntlet's mission {info.mission}")
        ctx.eq(e.u8(rout.FIVE_ON), 2 if info.five else 0, "five-army mode only on a five-army map")
        first = info.lines[0]
        ctx.check(len(g.units(army=first.army)) >= 15, f"{first.name} is on the field from the start ({len(g.units(army=first.army))} units)")
        for l in info.lines[1:]:
            ctx.eq(len(g.units(army=l.army)), 0, f"{l.name} (army {l.army}) is not on the battlefield at the start")
            ctx.eq(funds(g, l.army), 0, f"{l.name} has no funds at the start")
        ctx.eq([d.owner(l.hq) for l in info.lines], [first.army] + [0] * (len(info.lines) - 1), "only the first line's HQ is on the map")
        ctx.eq(d.owner(info.player_hq), info.player, "the player's HQ")
        e.close()
    fn.__name__ = f"gauntlet_lines_{info.key}_selector_and_start"
    test(modes=("ds",))(fn)


def falls(info):
    def fn(ctx):
        e, g, d = start(ctx, info)
        for k, l in enumerate(info.lines[:-1]):
            nxt = info.lines[k + 1]
            planted = rout.plant_extras(e, g, l.army)
            own = rout.owned_cells(e, l.army)
            ctx.check(len(own) >= 3, f"{l.name} owns properties ({len(own)})")
            d.capture(ctx, l.hq, army=info.player)
            d.settle()
            rout.wait_routed(e, g, l.army)
            rout.check_routed(ctx, e, g, l.army, l.name, planted)
            control(ctx, e, g, d, info, f"after {l.name}")
            ctx.eq(d.owner(l.hq), info.player, f"{l.name}'s HQ is the player's")
            rout.check_captured_hq(ctx, e, l.hq, info.player, l.name)
            rout.check_neutral(ctx, e, own, l.hq, l.name)
            ctx.check(len(g.units(army=nxt.army)) >= nxt.wave - 1, f"{nxt.name}'s wave is on the field ({len(g.units(army=nxt.army))} of {nxt.wave})")
            ctx.eq(d.owner(nxt.hq), nxt.army, f"{nxt.name}'s HQ is built")
            ctx.check(funds(g, nxt.army) >= nxt.chest[0], f"{nxt.name}'s war chest is paid ({funds(g, nxt.army)} >= {nxt.chest[0]})")
            ctx.eq(d.controllers()[nxt.army - 1], 2, f"{nxt.name} is the computer's")
        last = info.lines[-1]
        d.capture(ctx, last.hq, army=info.player)
        ctx.eq(d.through_results(), 1, f"{last.name}'s HQ wins the battle")
        e.close()
    fn.__name__ = f"gauntlet_lines_{info.key}_each_fall_reveals_the_next_and_the_last_wins"
    test(modes=("ds",))(fn)


for _info in gm.MAPS.values():
    selector_and_start(_info)
    falls(_info)


@test(modes=("ds",))
def gauntlet_lines_last_eclipse_the_minicannon_fires_down_its_lane_on_sturms_turn(ctx):
    """Last Eclipse's minicannon behind the first seam (W at (17,12): it fires on (16..13, 12), the lane in front of the seam (13,12)), on Black Hole's turn: with Sturm's army reduced to one far Infantry (so nothing
    else can hurt them), a Tank of the player's put in the lane loses hit points on his turn and one put beside the lane does not. The map's inventions list holds the four cannons."""
    info = gm.MAPS[11]
    e, g, d = start(ctx, info)
    got = [bytes(e.read(0x0202_8360 + 8 * i, 8)) for i in range(4)]
    ctx.eq(sorted((b[0], b[1]) for b in got), [(17, 12), (28, 5), (29, 16), (38, 19)], "the map's inventions: the four minicannons")
    sturm = g.units(army=1)
    keep = next(u for u in sturm if u["type"] == 1)
    for u in sturm:
        if u["id"] != keep["id"]:
            d.remove_unit(u)
    d.place_unit(keep, 22, 23)
    tanks = [u for u in g.units(army=info.player) if u["type"] == 5]
    inn, out = tanks[0], tanks[1]
    d.place_unit(inn, 15, 12)
    d.place_unit(out, 15, 16)
    e.wait(10)
    d.end_turn()
    left = False
    for _ in range(3000):
        left = left or g.current_army() != info.player
        if left and g.current_army() == info.player and d.in_battle() and not d.scripts_running():
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(10)
    d.wait_control()
    g._units_base = g._players_base = None
    now = {u["id"]: u["hp"] for u in g.units(army=info.player)}
    ctx.log(f"in the lane {inn['id']}: {now.get(inn['id'])}; beside it {out['id']}: {now.get(out['id'])}")
    ctx.check(now.get(inn["id"], 0) < 100, "the Tank in the lane was hit on Sturm's turn")
    ctx.eq(now.get(out["id"]), 100, "the Tank beside the lane was not")
    e.close()


def _scene_state(e):
    """What the screen shows of a dialogue box: (the tile ids of the box's text layer (BG0), the tile ids the face layer (BG1) uses, the box's side ('top' or 'bottom' by the rows of BG0 that hold text))."""
    import struct
    cnt = [e.u16(0x04000008 + 2 * i) for i in range(4)]
    vofs = e.u16(0x04000012)
    v0 = bytes(e.read(0x06000000 + ((cnt[0] >> 8) & 31) * 0x800, 0x800))
    v1 = bytes(e.read(0x06000000 + ((cnt[1] >> 8) & 31) * 0x800, 0x800))
    m0 = struct.unpack_from("<1024H", v0)
    m1 = struct.unpack_from("<1024H", v1)
    rows = [r for r in range(32) if any((x & 0x3FF) not in (0, 257) for x in m0[r * 32:(r + 1) * 32])]
    text = {x & 0x3FF for x in m0 if (x & 0x3FF) not in (0, 257)}
    face = {x & 0x3FF for x in m1 if (x & 0x3FF) not in (0, 1023)}
    return text, face, vofs, rows


def arrival_boxes(info):
    def fn(ctx):
        """Every arrival scene shows every speaker's box, one after the other, and a box's text tiles are its own: none is also a tile of the face beside it (a tile two pictures draw into is how the first box's
        text came out garbled), whichever side of the screen the box is on."""
        from PIL import Image
        from tests.test_gauntlet_map2 import png
        e, g, d = start(ctx, info)
        for k, l in enumerate(info.lines[:-1]):
            nxt = info.lines[k + 1]
            d.capture(ctx, l.hq, army=info.player)
            seen = []
            for _ in range(200):
                if not d.scripts_running():
                    break
                e.wait(90)
                text, face, vofs, rows = _scene_state(e)
                px = Image.open(png(ctx, e, f"{info.key}_{nxt.name}_box{len(seen)}")).convert("RGB")
                w, h = px.size
                pink = sum(1 for y in range(6, 36, 3) for x in range(60, w - 4, 6) if px.getpixel((x, y))[0] > 235 and 225 < px.getpixel((x, y))[1] < 250) + \
                    sum(1 for y in range(h - 36, h - 6, 3) for x in range(60, w - 4, 6) if px.getpixel((x, y))[0] > 235 and 225 < px.getpixel((x, y))[1] < 250)
                if pink > 40:
                    seen.append((sorted(text & face), pink))
                    e.press("A", 4)
                    e.wait(30)
                else:
                    e.press("A", 4)
            ctx.check(len(seen) >= 2, f"{info.title}: {nxt.name}'s arrival shows {len(seen)} boxes (the departing CO's and {nxt.name}'s)")
            ctx.eq([s[0] for s in seen], [[]] * len(seen), f"{info.title}: no text tile of a box is a tile of the face")
            d.settle()
        e.close()
    fn.__name__ = f"gauntlet_lines_{info.key}_arrival_boxes_are_all_shown_and_clean"
    test(modes=("ds",))(fn)


for _info in gm.MAPS.values():
    arrival_boxes(_info)


# (the first two maps are not in the registry: their lines and HQs, for the same check)
arrival_boxes(gm.MapInfo(0, "gauntlet_01", "Cinder Sea", 1, (3, 18), [gm.Line("drake", 9, 2, (27, 18)), gm.Line("sensei", 18, 3, (3, 3)), gm.Line("hawke", 14, 4, (29, 3))]))
arrival_boxes(gm.MapInfo(1, "gauntlet_02", "Iron Crown", 5, (4, 22), [gm.Line("grit", 5, 1, (8, 9)), gm.Line("jess", 17, 2, (24, 5)), gm.Line("kanbei", 6, 3, (34, 6)), gm.Line("rachel", 80, 4, (30, 20))]))
