"""tangoAW2's Dual Strike Versus maps (five/design_ds_maps.py): the Wasteland
set and the sea set, a 2P, 3P, 4P and 5P map each, listed only with the Dual
Strike pack.

Each map is opened from its Versus tab like a player would (the last entry of
the tab); the list's preview and the battle map are checked tile by tile, and
every property's owner and every unit against five/map.py's build of
five/maps.txt; the whole map is photographed (screenshots stitched as the
cursor sweeps it) with the list entry; then every army is handed to the CPU
for several days. Without the pack the maps are not listed at all.

tangoAW2's other maps (five/design_maps.py: the 5P maps, the Obelisk maps)
are opened, checked and photographed the same way (five_map_*), with the
pack on so that every one of them is listed. AW2TEST_MAP_IMAGES=<dir> keeps
the pictures."""

import importlib.util
import os
import shutil
import struct
import sys

from aw2test import looks, paths, ram, traverse
from aw2test import rom as romlib
from aw2test.emu import Emu
from aw2test.game import MAP_TAB, SELECT_MODE_CURSOR, SELECT_MODE_VERSUS, Game, NavError
from aw2test.harness import Skip, test
from aw2test.stitch import stitch

FIVE = os.path.join(paths.REPO, "tango-gamesupport-aw2", "five")
_spec = importlib.util.spec_from_file_location("five_map_py", os.path.join(FIVE, "map.py"))
mappy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mappy)

# name -> (map id, Versus tab)
MAPS = {
    "Rust Basin": (0xC1, 3), "Dune Fork": (0xC2, 5), "Cinder Flats": (0xC3, 6), "Black Wastes": (0xC4, 9),
    "Coral Strait": (0xC5, 3), "Trident Isles": (0xC6, 5), "Harbor Cross": (0xC7, 6), "Coral Crown": (0xC8, 9),
    # the BH Campaign's prize map (crate::five_map::VAULT_ID): normal colours, pack only
    "The Colonel's Vault": (0xF1, 3),
}
# tangoAW2's own maps (crate::five_map::IDS, in five/maps.txt's order).
OWN = {
    "Five Seas": (0x00, 9), "Iron Crossing": (0xBC, 9), "Magma Crown": (0xBD, 9), "Skyreach": (0xBE, 9),
    "The Citadel": (0xBF, 9), "Obelisk Duel": (0xB8, 3), "Crystal Isles": (0xB9, 5), "Obelisk Plains": (0xBA, 6),
    "Black Monolith": (0xBB, 9), "Black Rampart": (0xC0, 9),
}
ALL = {**MAPS, **OWN}
# Maps meant to be crossed by air or sea alone in places (Skyreach's walled
# plateaus, Crystal Isles' islands without beaches).
AIRBORNE = ("Skyreach", "Crystal Isles")
NO_PIPES = ("The Colonel's Vault",)   # (a pack-only map without Piperunners)
WASTELAND = ("Rust Basin", "Dune Fork", "Cinder Flats", "Black Wastes")

# The Select Map screen: the highlighted map's tiles, decompressed for the
# preview (width, height, then u16 tiles).
PREVIEW = 0x02003010
PAL_BUFFER = 0x030020C0
WASTELAND_CLEAR = 0x08E97000  # crate::wasteland::look_rom(1) + AT_CLEAR
BIOME = 0x03004493
# gMap (battle): width/height at +0, camera (pixels) at +4/+6.
GMAP = 0x0201E450
DAY = 0x03004080
LAB = 0x14
PIPERUNNER = 9
CO_TABLE_POOL = 0x08042DDC
IMAGES = os.environ.get("AW2TEST_MAP_IMAGES")


def built(name):
    """(width, height, tiles, units) of `name` as five/map.py builds it:
    tiles row by row, units [(army, x, y, type)]."""
    rom = open(paths.aw2_rom(), "rb").read()
    for m in mappy.parse(os.path.join(FIVE, "maps.txt")):
        if m["name"] == name:
            lz, units, (w, h), _ = mappy.build(m, mappy.sea_edges(rom))
            raw = bytearray()
            n = struct.unpack_from("<I", lz, 0)[0] >> 8
            p = 4
            while len(raw) < n:
                p += 1  # literal blocks only
                raw += lz[p:p + 8]
                p += 8
            raw = bytes(raw[:n])
            tiles = [struct.unpack_from("<H", raw, 2 + 2 * k)[0] for k in range(w * h)]
            out, army = [], 0
            for k in range(0, len(units), 12):
                r = units[k:k + 12]
                if r[0] == 0xFE:
                    army = r[1]
                elif r[0] != 0xFF:
                    out.append((army, r[0], r[1], r[2]))
            return m, w, h, tiles, out
    raise KeyError(name)


def select_map(ctx, name, save=None):
    """Boot, open Versus > New > the map's tab, walk down to it, check the
    preview, and press A: the Teams screen. Returns the Game."""
    mid, tab = ALL[name]
    _, w, h, tiles, _ = built(name)
    if save is None:
        save = os.path.join(ctx.out, "map.sav")
        shutil.copy(paths.base_save(), save)
    e = Emu(save=save, ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    e.wait(700)
    e.press("START", 8)
    e.wait(300)
    e.press("A", 8)
    e.wait(150)
    for _ in range(8):
        cur = e.u8(SELECT_MODE_CURSOR)
        if cur == SELECT_MODE_VERSUS:
            break
        e.press("UP" if cur < SELECT_MODE_VERSUS else "DOWN", 8)
        e.wait(50)
    e.press("A", 8)
    e.wait(150)
    e.press("A", 8)
    e.wait(150)
    if not g.press_until("LEFT", lambda: e.u8(MAP_TAB) == tab, tries=12, hold=8, settle=50):
        raise NavError(f"tab {tab} not reached (tab {e.u8(MAP_TAB)})")
    e.wait(30)

    def previewed():
        b = e.read(PREVIEW, 2 + 2 * w * h)
        return b[0] == w and b[1] == h and list(struct.unpack_from(f"<{w * h}H", b, 2)) == tiles

    found = False
    for _ in range(40):
        if previewed():
            found = True
            break
        e.press("DOWN", 8)
        e.wait(24)
    return g, found


def to_teams(g):
    g.e.press("A", 8)
    if not g.e.wait_until(g.on_teams, 400, step=10):
        raise NavError("Teams screen did not open")
    g.e.wait(40)


def start(ctx, g, humans):
    g.set_teams(None, set(humans))
    g.teams_to_rules()
    g.set_rules(fog=False, weather="clear", power=True, visuals="off")
    g.start_battle()


def check_map(ctx, g, name):
    """The battle map against the build: tiles' classes and owners, units."""
    m, w, h, tiles, units = built(name)
    e = g.e
    ctx.eq((e.u16(GMAP), e.u16(GMAP + 2)), (w, h), f"{name}: map size")
    ctx.eq(e.u8(ram.VS_MAP), ALL[name][0], f"{name}: map id")
    classes = e.read(ram.MAP_TERRAIN, 0x4000)
    live = e.read(romlib.TILE_CLASS, 0x400)
    rows = [e.u16(ram.MAP_ROW_OFFSETS + 2 * y) for y in range(h)]
    bad = []
    towers = 0
    # With the pack in Versus the Black Factory's building is a wall, its pipe end at the top included (class 15 -> 9,
    # crate::factory_hp); the factory is the invention list's kind 7 at (x - 1, y).
    factories = set()
    for k in range(16):
        a = 0x02028360 + 8 * k
        if not e.u16(a + 2) & 0x3C0:
            break
        if (e.u16(a + 2) >> 6) & 15 == 7:
            factories.add((e.u8(a) + 1, e.u8(a + 1)))
    for y in range(h):
        for x in range(w):
            want = live[tiles[y * w + x]]
            got = classes[rows[y] + x]
            if want == 0xF and got == 9 and ctx.ds and (x, y) in factories:
                continue
            if want != got:
                bad.append((x, y, hex(want), hex(got)))
            towers += (got & 0x1F) == LAB
    ctx.check(not bad, f"{name}: every tile's terrain and owner as built ({len(bad)} differ: {bad[:6]})")
    ctx.check(towers == sum(r.count("t") + r.count("T") for r in m["rows"]), f"{name}: {towers} Com Towers")
    ctx.check(all(classes[rows[y] + x] & 0x1F != LAB or classes[rows[y] + x] >> 5 == 0
                  for y in range(h) for x in range(w)), f"{name}: every Com Tower starts neutral")
    have = sorted((u["army"], u["x"], u["y"], u["type"]) for u in g.units())
    ctx.eq(have, sorted(units), f"{name}: the pre-deployed units")
    # Every army gets everywhere, with the game's own movement chart (the one
    # army 1's CO moves by: tangoAW2's copy with the pack, pipe row included).
    chart_at = e.u32(e.u32(CO_TABLE_POOL) + romlib.CO_RECORD * g.player(1)["co"] + 0x38 + 0x18)
    chart = [list(e.read(chart_at + 32 * r, 32)) for r in range(8)]
    grid = traverse.Grid(w, h, [classes[rows[y] + x] for y in range(h) for x in range(w)])
    bad = traverse.check(grid, chart, range(1, m["armies"] + 1),
                         [(a, x, y) for a, x, y, t in units if t == PIPERUNNER], need_piperunners=name in MAPS and name not in NO_PIPES)
    if name in AIRBORNE:
        ctx.log(f"{name}: by design not every army gets everywhere on the ground ({len(bad)}: {bad[:6]})")
    else:
        ctx.check(not bad, f"{name}: every army can get everywhere, in play ({len(bad)} failures: {bad[:6]})")
    beach_check(ctx, name, grid, m["armies"])
    return m, w, h


def beach_check(ctx, name, grid, armies):
    """Every army the map's symmetry maps onto another has as many beaches,
    and an enemy beach as far from its HQ."""
    bal = traverse.beach_balance(grid)
    ctx.log(f"{name}: beaches (count, HQ to nearest enemy beach) per army {bal}")
    same = {bal[a] for a in traverse.symmetric_armies(armies)}
    ctx.check(len(same) == 1, f"{name}: every army gets the same beaches ({bal})")


def export(ctx, bmp, label):
    if not IMAGES:
        return
    try:
        from PIL import Image
    except ImportError:
        return
    os.makedirs(IMAGES, exist_ok=True)
    im = Image.open(bmp).convert("RGB")
    im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(os.path.join(IMAGES, label + ".png"))


def open_and_check(ctx, name):
    if not ctx.ds:
        raise Skip("the pack's maps")
    g, found = select_map(ctx, name)
    fn = name.lower().replace(" ", "_")
    ctx.require(found, f"{name} is on its tab ({ALL[name][1]}) with its preview")
    export(ctx, ctx.shot(g, "list"), f"{fn}_list")
    to_teams(g)
    export(ctx, ctx.shot(g, "teams"), f"{fn}_teams")
    start(ctx, g, humans=(1,))
    g.wait_for_input()
    m, w, h = check_map(ctx, g, name)
    if name in WASTELAND:
        ctx.eq(g.e.u8(BIOME) >> 4 & 7, 1, f"{name}: the biome is Wasteland")
        ctx.check(g.e.read(PAL_BUFFER, 128) == g.e.read(WASTELAND_CLEAR, 128), f"{name}: drawn in Wasteland's colours")
        looks.check_screen(ctx, g, looks.WASTELAND, f"{name}: ")
    else:
        ctx.eq(g.e.u8(BIOME) >> 4 & 7, 0, f"{name}: AW2's own look")
    export(ctx, ctx.shot(g, "battle"), f"{fn}_battle")
    sweep = looks.Sweep(ctx, g, looks.WASTELAND, f"{name}: ") if name in WASTELAND else None
    stitch(ctx, g, name, w, h, each=sweep)
    if sweep:
        sweep.done(w, h)
    return g


def cpu_days(ctx, name, days=6, netplay=False):
    """Every army a CPU: several days pass with no hang, and the armies act."""
    if not ctx.ds and name in MAPS:
        raise Skip("the pack's maps")
    g, found = select_map(ctx, name)
    ctx.require(found, f"{name} is listed")
    to_teams(g)
    start(ctx, g, humans=())
    e = g.e
    armies = m_armies = built(name)[0]["armies"]
    before = {u["id"]: (u["x"], u["y"], u["hp"]) for u in g.units()}
    start_day = e.u8(DAY)
    for _ in range(days * m_armies * 12):
        e.wait(300)
        if e.u8(DAY) >= start_day + days or g.battle_over():
            break
    ctx.shot(g, "cpu")
    day = e.u8(DAY)
    ctx.check(day >= start_day + days or g.battle_over(), f"{name}: {day - start_day} CPU days passed ({armies} armies)")
    moved = {u["army"] for u in g.units() if before.get(u["id"]) != (u["x"], u["y"], u["hp"])}
    ctx.check(len(moved) == armies, f"{name}: every army's units acted ({sorted(moved)})")
    if netplay:
        identical, _, text = ctx.netplay_replay(g, [(ram.MAP_TERRAIN, 0x400)])
        ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
        ctx.check(identical, f"{name}: netplay: both peers and the straight replay identical")
    return g


def _open(name, prefix="ds_map_"):
    def fn(ctx):
        open_and_check(ctx, name)
    fn.__name__ = prefix + name.lower().replace(" ", "_")
    return test(modes=("ds",))(fn)


def _cpu(name, netplay=False):
    def fn(ctx):
        cpu_days(ctx, name, netplay=netplay)
    fn.__name__ = ("netplay_" if netplay else "") + "cpu_ds_map_" + name.lower().replace(" ", "_")
    return test(modes=("ds",), netplay=netplay)(fn)


for _name in MAPS:
    _open(_name)
    _cpu(_name)
for _name in OWN:
    _open(_name, "five_map_")
_cpu("Dune Fork", netplay=True)
_cpu("Coral Crown", netplay=True)
# Five Seas is tangoAW2's own and is listed without the pack too: both modes.
for _nl in (False, True):
    def _five_seas(ctx, _nl=_nl):
        cpu_days(ctx, "Five Seas", netplay=_nl)
    _five_seas.__name__ = ("netplay_" if _nl else "") + "cpu_five_seas"
    test(modes=("aw2", "ds"), netplay=_nl)(_five_seas)


@test(modes=("aw2",))
def ds_maps_hidden_without_pack(ctx):
    """Without the pack no tab lists them: every tab's last entry is the
    game's (or an older tangoAW2 map)."""
    for name in MAPS:
        g, found = select_map(ctx, name)
        ctx.check(not found, f"{name} is not listed without the pack")
        ctx.shot(g, name.lower().replace(" ", "_"))
        g.e.close()


@test(modes=("aw2",))
def ds_maps_traversal_static(ctx):
    """The same traversal check on five/map.py's build, with the movement
    chart from the ROM file (no pack needed): ports reach ports, every island
    has a beach, bases are not boxed in, Piperunner bases sit behind seams."""
    rom = open(paths.aw2_rom(), "rb").read()
    chart = traverse.aw2_chart(rom)
    army5 = {0x1B4: 0xA8, 0x1B5: 0xAE, 0x1B6: 0xA6, 0x1B7: 0xAA, 0x1B8: 0xAB, 0x1B9: 0xB4}  # five_map::ARMY5_TILES
    for name in ALL:
        if name in AIRBORNE:
            continue
        m, w, h, tiles, units = built(name)
        grid = traverse.Grid(w, h, [army5.get(t, rom[romlib.TILE_CLASS - romlib.ROM_BASE + t]) for t in tiles])
        bad = traverse.check(grid, chart, range(1, m["armies"] + 1),
                             [(a, x, y) for a, x, y, t in units if t == PIPERUNNER], need_piperunners=name in MAPS and name not in NO_PIPES)
        ctx.check(not bad, f"{name}: every army can get everywhere ({len(bad)} failures: {bad[:6]})")
        beach_check(ctx, name, grid, m["armies"])


_spec = importlib.util.spec_from_file_location("five_tilecheck_py", os.path.join(FIVE, "tilecheck.py"))
tilecheck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tilecheck)


@test(modes=("aw2",))
def five_map_tiles_as_aw2_draws_them(ctx):
    """Every tangoAW2 map, as five/map.py builds it, drawn the way the game's
    own maps are (five/tilecheck.py, learned from every built-in map): each
    pair of neighbouring tiles is one the game places (or meets as grass
    does, or joins as a pipe, spring or base does), every mountain is the
    game's tile for what stands above and below it, and every plain above a
    mountain shows its peak."""
    rom = open(paths.aw2_rom(), "rb").read()
    for name, bad in tilecheck.check_all(rom, os.path.join(FIVE, "maps.txt")).items():
        ctx.check(not bad, f"{name}: every tile as the game draws it ({len(bad)} not: "
                           f"{[tilecheck.describe(v) for v in bad[:6]]})")
    # The check catches v0.4.0's broken mountains (every one 0x22): a 2x2
    # block under and over plains.
    rows = [[0x001, 0x001], [0x022, 0x022], [0x022, 0x022], [0x001, 0x001]]
    bad = tilecheck.mountain_violations(rows, tilecheck.mountain_rules(rom))
    ctx.check(len(bad) == 4, f"a 2x2 block of 0x22 mountains is caught: the lower two, the plains above ({len(bad)} tiles)")


# ---- Five Seas' beaches --------------------------------------------------------------
FOOT, LANDER = traverse.FOOT, traverse.LANDER
SHOAL, PORT, HQ_KIND = traverse.SHOAL, traverse.PORT, traverse.HQ
ARMY5_TILES = {0x1B4: 0xA8, 0x1B5: 0xAE, 0x1B6: 0xA6, 0x1B7: 0xAA, 0x1B8: 0xAB, 0x1B9: 0xB4}  # five_map::ARMY5_TILES


def static_grid(name):
    rom = open(paths.aw2_rom(), "rb").read()
    m, w, h, tiles, units = built(name)
    classes = [ARMY5_TILES.get(t, rom[romlib.TILE_CLASS - romlib.ROM_BASE + t]) for t in tiles]
    return m, traverse.Grid(w, h, classes), traverse.aw2_chart(rom), units


def land_islands(g, chart):
    """The map's islands for the foot soldier: sets of cells joined overland
    (a beach counts as land; a port too)."""
    seen, out = set(), []
    for c in g.cells():
        if c in seen or chart[FOOT][g.kind(*c)] == 0xFF:
            continue
        isle = traverse.flood(g, chart[FOOT], [c])
        seen |= isle
        out.append(isle)
    return out


@test(modes=("aw2",))
def five_seas_every_army_has_beaches(ctx):
    """Five Seas (20x40, five islands and eight neutral ones): every army has
    at least two beaches (shoals, where a Lander loads and unloads) on its own
    island, reached from its HQ and bases on foot and touching sea a Lander
    sails, each of which a Lander from any other army's beach can sail to;
    every neutral island has a beach too. The beaches are even: the same
    count and distance for the four outer armies."""
    m, g, chart, units = static_grid("Five Seas")
    islands = land_islands(g, chart)
    hq = {g.owner(*c): c for c in g.cells() if g.kind(*c) == HQ_KIND}
    ctx.eq(sorted(hq), [1, 2, 3, 4, 5], "five HQs")
    beaches = {}
    for a, c in hq.items():
        own = next(i for i in islands if c in i)
        homes = [c] + [b for b in own if g.kind(*b) == traverse.BASE and g.owner(*b) == a]
        reach = traverse.flood(g, chart[FOOT], homes)
        beaches[a] = sorted(b for b in own if g.kind(*b) == SHOAL and b in reach
                            and any(chart[LANDER][g.kind(*n)] != 0xFF and g.kind(*n) != SHOAL for n in g.near(*b)))
        ctx.check(len(beaches[a]) >= 2, f"army {a}: {len(beaches[a])} beaches on its island, by land from its HQ and bases: {beaches[a]}")
    everything = {b for bs in beaches.values() for b in bs}
    for a, bs in beaches.items():
        for b in bs:
            sail = traverse.flood(g, chart[LANDER], [b])
            lost = sorted(o for o in everything if o not in sail)
            ctx.check(not lost, f"army {a}: a Lander leaving beach {b} sails to every other army's beaches (cannot reach {lost})")
    neutral = [i for i in islands if not any(h in i for h in hq.values())]
    ctx.check(len(neutral) >= 8, f"{len(neutral)} neutral islands")
    bare = [min(i) for i in neutral if not any(g.kind(*c) == SHOAL for c in i)]
    ctx.check(not bare, f"every neutral island has a beach (none on the ones at {bare})")
    bal = traverse.beach_balance(g)
    ctx.log(f"beaches (count, HQ to nearest enemy beach) per army {bal}")
    ctx.check(len({bal[a] for a in (1, 2, 3, 4)}) == 1, f"the four outer armies have the same beaches ({bal})")
    ctx.check(bal[5][0] >= 2, f"Black Hole's beaches count ({bal[5]})")


def _dijkstra(g, chart, mtype, start, budget, blocked=()):
    """Cells reachable at no more than `budget` movement points, with their cost."""
    best = {start: 0}
    todo = [start]
    while todo:
        c = min(todo, key=best.get)
        todo.remove(c)
        for n in g.near(*c):
            cost = chart[mtype][g.kind(*n)]
            if cost == 0xFF or n in blocked:
                continue
            v = best[c] + cost
            if v <= budget and v < best.get(n, 1 << 20):
                best[n] = v
                todo.append(n)
    return best


def _unload_plan(g, chart, units, army):
    """Where army's Lander and one of its Infantry meet on a beach: (lander,
    infantry, beach, landing cell). The Lander sails there in a turn; the
    Infantry walks (a few turns where the beach is far) and boards on it;
    the Lander then drops it on land beside the beach."""
    mine = [u for u in units if u[0] == army]
    lander = next(u for u in mine if u[3] == 23)
    inf = [u for u in mine if u[3] == 1]
    occupied = {(u[1], u[2]) for u in units}
    sail = _dijkstra(g, chart, LANDER, (lander[1], lander[2]), 6)
    best = None
    for b in sail:
        if g.kind(*b) != SHOAL or b in occupied:
            continue
        land = [n for n in g.near(*b) if g.kind(*n) not in (SHOAL, PORT) and chart[FOOT][g.kind(*n)] != 0xFF
                and chart[LANDER][g.kind(*n)] == 0xFF and n not in occupied]
        if not land:
            continue
        walk = _dijkstra(g, chart, FOOT, b, 99)
        for i in inf:
            d = walk.get((i[1], i[2]))
            if d is not None and (best is None or (d, sail[b], b) < best[0]):
                best = ((d, sail[b], b), lander, i, b, land[0])
    return best[1:] if best else None


def _pass_turn(g):
    e = g.e
    army = g.current_army()
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    if not e.wait_until(lambda: g.current_army() != army, 600, step=8):
        raise NavError("turn did not end")
    g.wait_for_input()


@test(modes=("aw2", "ds"))
def five_seas_lander_unloads_on_every_beach(ctx):
    """Every army, played by a human in turn: its Lander sails onto one of its
    new beaches, an Infantry walks over (over several turns when the beach is
    far) and boards (Load), and on the turn after the Lander drops it onto
    the land next to the beach. Read from RAM: the Lander on a shoal, the
    Infantry inside it, then standing on land where it was dropped, the
    Lander empty."""
    m, grid, chart, units = static_grid("Five Seas")
    plans = {a: _unload_plan(grid, chart, units, a) for a in range(1, 6)}
    ctx.check(all(plans.values()), f"every army has a beach its Lander reaches in a turn: { {a: p and p[2:] for a, p in plans.items()} }")
    ctx.require(all(plans.values()), "plans")
    g, found = select_map(ctx, "Five Seas")
    ctx.require(found, "Five Seas is listed")
    to_teams(g)
    start(ctx, g, humans=(1, 2, 3, 4, 5))
    g.wait_for_input()
    e = g.e
    ids = {}
    for a, (l, i, b, land) in plans.items():
        ids[a] = (next(u["id"] for u in g.units(army=a) if (u["type"], u["x"], u["y"]) == (23, l[1], l[2])),
                  next(u["id"] for u in g.units(army=a) if (u["type"], u["x"], u["y"]) == (1, i[1], i[2])))
    state = {a: "sail" for a in plans}
    for rnd in range(6):
        for _ in range(5):
            a = g.current_army()
            l, i, b, land = plans[a]
            lid, iid = ids[a]
            lu, iu = g.unit(lid), g.unit(iid)
            if state[a] == "sail":
                g.select(lu["x"], lu["y"])
                g.move_to(*b)
                g.choose("Wait", g.ACTION_MENU)
                g.wait_idle()
                state[a] = "board"
            elif state[a] == "board":
                g.select(iu["x"], iu["y"])
                reach = _dijkstra(grid, chart, FOOT, (iu["x"], iu["y"]), 3)
                if b in reach:
                    names = g.move_to(*b)["names"]
                    ctx.check(any(n.lower().startswith("load") for n in names), f"army {a}: Infantry offered Load at {b}: {names}")
                    g.choose("Load", g.ACTION_MENU)
                    g.wait_idle()
                    lu = g.unit(lid)
                    ctx.check((lu["x"], lu["y"]) == b and grid.kind(*b) == SHOAL and any(lu["cargo"]),
                              f"army {a}: Lander on the beach {b} carries the Infantry (cargo {lu['cargo']})")
                    state[a] = "drop"
                else:
                    walk = _dijkstra(grid, chart, FOOT, b, 99)
                    occ = {(u["x"], u["y"]) for u in g.units()}
                    cell = min((c for c in reach if c not in occ or c == (iu["x"], iu["y"])), key=lambda c: (walk.get(c, 999), c))
                    g.move_to(*cell)
                    g.choose("Wait", g.ACTION_MENU)
                    g.wait_idle()
            elif state[a] == "drop":
                g.select(lu["x"], lu["y"])
                names = g.move_to(lu["x"], lu["y"])["names"]
                ctx.check(any(n.lower().startswith("drop") for n in names), f"army {a}: Lander on the beach offers Drop: {names}")
                g.choose("Drop", g.ACTION_MENU)
                e.wait(20)
                if g.menu():
                    e.press("A", 4)
                    e.wait(20)
                for _k in range(8):  # the cursor cycles through the cells the game offers
                    if g.cursor() == land:
                        break
                    e.press("RIGHT", 4)
                    e.wait(10)
                if a in (1, 5):
                    export(ctx, ctx.shot(g, f"drop_target_army{a}"), f"five_seas_lander_drop_target_army{a}")
                e.press("A", 4)
                e.wait(40)
                mm = g.menu()
                if mm and any(n.lower().startswith("wait") for n in mm["names"]):
                    g.choose("Wait", g.ACTION_MENU)
                g.wait_idle()
                iu, lu = g.unit(iid), g.unit(lid)
                ctx.check(abs(iu["x"] - b[0]) + abs(iu["y"] - b[1]) == 1 and not any(lu["cargo"]) and (iu["x"], iu["y"]) != (lu["x"], lu["y"]),
                          f"army {a}: Infantry dropped from the Lander on beach {b} next to it, at {(iu['x'], iu['y'])} (wanted {land}), the Lander empty (cargo {lu['cargo']})")
                if a in (1, 5):
                    export(ctx, ctx.shot(g, f"dropped_army{a}"), f"five_seas_lander_dropped_army{a}")
                state[a] = "done"
            if all(v == "done" for v in state.values()):
                return
            _pass_turn(g)
    ctx.check(False, f"every army's Infantry landed ({state})")
