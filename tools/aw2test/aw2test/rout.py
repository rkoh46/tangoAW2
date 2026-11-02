"""The gauntlet engine's rout rule (docs/dev/gauntlet.md, "The rout"): capturing a line's HQ routes its army. Helpers shared by the live tests of every gauntlet map
(`-k gauntlet_rout`, `bh2_m31_hq_capture_routes_the_line`)."""

from . import dscampaign as dc

FIVE_ON = 0x0203_0206
UNIT_SIZE = 12
# the kinds a rout must not miss: AW2's own, Dual Strike's (Stealth 12, Black Bomb 13, Black Boat 18, Carrier 26, Oozium 27) and the hidden ones (a dived Sub 0x19, a hidden Stealth 0x1C)
KINDS = {"bomb": 13, "stealth": 12, "black_boat": 18, "carrier": 26, "oozium": 27, "sub_dived": 0x19, "stealth_hidden": 0x1C}


def per_army(e):
    return 51 if e.u8(FIVE_ON) in (1, 2) else 64


def ids_of(e, army):
    per = per_army(e)
    return range((army - 1) * per + 1, army * per)


def layer_cell(e, x, y):
    return dc.MAP + 0x12 + e.u16(dc.MAP + 0x417A + 2 * y) + x


def plant(e, g, army, utype, cell=None, carried_by=None):
    """A unit of `army` made from a copy of one of its own records: kind `utype`, on `cell` (an empty one near the cursor when None) or loaded into the unit `carried_by` (its id: the cargo slot,
    the loaded flag). Returns its id. Raw record writes: what the game's own destruction must find and remove."""
    tmpl = g.units(army=army)[0]
    uid = next(i for i in ids_of(e, army) if e.u8(g.unit_addr(i)) == 0)
    r = bytearray(tmpl["raw"])
    r[0], r[7], r[8] = utype, 0, 0
    if carried_by is None:
        x, y = cell or g.empty_cells()[0]
        r[1] = 0
        r[2], r[3] = x, y
        e.w8(layer_cell(e, x, y), uid)
    else:
        host = g.unit(carried_by)
        r[1] = 0x08
        r[2], r[3] = host["x"], host["y"]
        a = g.unit_addr(carried_by)
        slot = 7 if e.u8(a + 7) == 0 else 8
        e.w8(a + slot, uid)
    for i, b in enumerate(r):
        e.w8(g.unit_addr(uid) + i, b)
    g._units_base = g._players_base = None
    return uid


def plant_extras(e, g, army):
    """Every awkward unit a routed line may hold: DS-only kinds, hidden ones, a transport with cargo, a carrier with a plane. Returns {name: id}."""
    out = {}
    cells = g.empty_cells()[:40:3]
    for (name, kind), cell in zip(KINDS.items(), cells):
        out[name] = plant(e, g, army, kind, cell)
    boat = plant(e, g, army, 18, cells[-1])
    out["loaded_boat"] = boat
    out["cargo_a"] = plant(e, g, army, 1, carried_by=boat)
    out["cargo_b"] = plant(e, g, army, 2, carried_by=boat)
    return out


def layer_ids(e, army):
    """The map's unit layer cells that name a unit of `army` (a routed army has none)."""
    w, h = e.u16(dc.MAP), e.u16(dc.MAP + 2)
    mine = set(ids_of(e, army))
    return [(x, y) for y in range(h) for x in range(w) if e.u8(layer_cell(e, x, y)) in mine]


def owned_cells(e, army):
    """The map's cells whose owner bits are `army` (properties, towers, HQs)."""
    w, h = e.u16(dc.MAP), e.u16(dc.MAP + 2)
    out = []
    for y in range(h):
        row = e.u16(dc.MAP + 0x417A + 2 * y)
        for x in range(w):
            if e.u8(dc.MAP + 0x1432 + row + x) >> 5 == army:
                out.append((x, y))
    return out


def wait_routed(e, g, army, frames=3000):
    """The game destroys a routed army's units one after another (its explosions play): waits until none is left."""
    for _ in range(frames // 20):
        g._units_base = g._players_base = None
        if not g.units(army=army):
            break
        e.wait(20)


def check_routed(ctx, e, g, army, name, planted=()):
    """After the capture: the army has no unit record (any kind, loaded or hidden), nothing of it on the map's unit layer and no cell it owns."""
    g._units_base = g._players_base = None
    left = g.units(army=army)
    ctx.eq([(u["id"], u["type"]) for u in left], [], f"{name}: no unit is left (DS-only, loaded, dived and hidden ones included)")
    ctx.eq(layer_ids(e, army), [], f"{name}: nothing of it on the map's unit layer")
    ctx.eq(owned_cells(e, army), [], f"{name}: it owns no property (all neutral)")
    for k, uid in dict(planted).items():
        ctx.eq(e.u8(g.unit_addr(uid)), 0, f"{name}: the planted {k} is gone")


# five.rs PROPERTY_TILES: a property tile's kind (0 HQ, 1 base, 2 city, 3 airport, 4 port, 5 lab) by its row
_TILES = [[0x1C0, 0x1C5, 0x1CA, 0x1CF, 0x1D4, 0x1B4], [0x1C1, 0x1C6, 0x1CB, 0x1D0, 0x1D5, 0x1B5], [0x1C2, 0x1C7, 0x1CC, 0x1D1, 0x1D6, 0x1B6],
          [0x1C3, 0x1C8, 0x1CD, 0x1D2, 0x1D7, 0x1B7], [0x1C4, 0x1C9, 0x1CE, 0x1D3, 0x1D8, 0x1B8], [0x1D9, 0x1DA, 0x1DB, 0x1DC, 0x1DD, 0x1B9]]


def tile_kind(tile):
    return next((k for k, row in enumerate(_TILES) if tile in row), None)


def cell_class_tile(e, x, y):
    """(terrain class 0..0x1F, owner, tile) of a cell."""
    row = e.u16(dc.MAP + 0x417A + 2 * y)
    c = e.u8(dc.MAP + 0x1432 + row + x)
    return c & 0x1F, c >> 5, e.u16(dc.MAP + 0xA22 + 2 * (row + x))


def hq_cells(e, army):
    """The cells of HQ class (8) that `army` owns: what AW2 loses the army on if an enemy captures one."""
    w, h = e.u16(dc.MAP), e.u16(dc.MAP + 2)
    return [(x, y) for y in range(h) for x in range(w) if cell_class_tile(e, x, y)[:2] == (8, army)]


def check_captured_hq(ctx, e, cell, player, name):
    """A captured line's HQ is the player's city (AW2's own conversion), not a second HQ: the player owns exactly one HQ (its own) and the captured cell is of city class (the only class
    whose capture ends an army is HQ), so the computer taking it back cannot win."""
    cls, owner, tile = cell_class_tile(e, *cell)
    ctx.check(cls != 8, f"{name}'s captured HQ cell is no HQ any more (class {cls})")
    ctx.eq(owner, player, f"{name}'s captured HQ cell is the player's")
    ctx.eq(tile_kind(tile), 2, f"{name}'s captured HQ cell is a city (tile {tile:#x})")
    mine = hq_cells(e, player)
    ctx.eq(len(mine), 1, f"the player owns exactly one HQ after taking {name}'s ({mine})")
