"""The computer defends its HQ (docs/AW2.md, "The CPU defends its HQ"; tango-gamesupport-aw2/src/cpu_defend.rs).

A player's Infantry stands on the enemy HQ and captures it; the enemy's units are held (role 0) two squares away, the order
AW2's CPU leaves alone (a held soldier is skipped by the unit queue unless an enemy stands next to it). After the enemy's
turn the soldier has been attacked (its HP is lower, or it is dead) and the HQ is still the enemy's. The first mission of
the BH Campaign, the BH2 Campaign and the Emerald Sun Campaign. `-k cpu_defends_hq_m1_off` is the same scene with the
rule's development switch off (`cpu_defend::OFF_DEFEND`): the held soldiers watch and the soldier is not touched, which
is the report that led to the rule (the player took the HQ of the first mission with the enemy's units standing by).
Pictures: tools/aw2test/out/ds/<test>/before_end.bmp and after_enemy.bmp."""

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import cpuprobe as cp
from aw2test import dscampaign as dc
from aw2test import escampaign as es
from aw2test.bot import HQ
from aw2test.harness import test

SWITCHES = 0x0203C7F0          # crate::ds_ai::SWITCHES (bit 4 = 16: the HQ's defence off)
OFF_DEFEND = 16
LAND = dc.LAND


def enter(kind, ctx):
    if kind == "bh":
        return cp.enter(ctx, 1)
    if kind == "bh2":
        return b2.enter(ctx, 1)
    return es.enter(ctx, 1)


def enemy_hq(snap, me=1):
    for (x, y), (k, o) in sorted(snap["props"].items()):
        if k == HQ and o != me and snap["team"][o] != snap["team"][me]:
            return (x, y), o
    return None, None


def free_land(e, g, d, x, y, w, h):
    if not (0 <= x < w and 0 <= y < h):
        return False
    return e.u8(d.layer_cell(x, y)) == 0 and g.terrain_class(x, y) & 0x1F in LAND


def scene(ctx, kind, off):
    """Returns (before, after, the HQ's owner after, before): the capturer's record before the enemy's turn and after."""
    e, g, d = enter(kind, ctx)
    if off:
        e.w8(SWITCHES, e.u8(SWITCHES) | OFF_DEFEND)
    snap = cp.snapshot(e, g, 1)
    hq, owner = enemy_hq(snap)
    ctx.require(hq is not None, f"{kind}: the enemy has an HQ")
    w, h = d.size()
    ctx.log(f"{kind}: the enemy's HQ is at {hq}, army {owner}")
    units = cp.all_units(e, g)
    foes = [u for u in units if u["army"] != 1 and snap["team"][u["army"]] != snap["team"][1]]
    mine = [u for u in units if u["army"] == 1 and u["type"] in (1, 2)]
    ctx.require(mine, f"{kind}: the player has a foot soldier")
    # the HQ's square is empty; the enemy keeps four soldiers held two squares from it (no other unit of its own)
    for u in units:
        if (u["x"], u["y"]) == hq:
            d.remove_unit(u)
    keep = sorted((u for u in foes if (u["x"], u["y"]) != hq), key=lambda u: abs(u["x"] - hq[0]) + abs(u["y"] - hq[1]))[:4]
    for u in foes:
        if u not in keep and (u["x"], u["y"]) != hq:
            d.remove_unit(u)
    ring = [(hq[0] + dx, hq[1] + dy) for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2), (1, 1), (-1, -1), (1, -1), (-1, 1))]
    ring = [c for c in ring if free_land(e, g, d, c[0], c[1], w, h)]
    ctx.require(len(ring) >= len(keep), f"{kind}: room for the held soldiers ({len(ring)} squares)")
    for u, c in zip(keep, ring):
        a = g.unit_addr(u["id"])
        e.w8(a, 1)                       # an Infantry
        e.w16(a + 4, (e.u16(a + 4) & ~0x7F) | 100)
        e.w8(a + 6, 99)
        e.w8(a + 11, 0)                  # role 0: holds
        e.w8(a + 1, 0)
        d.place_unit(u, *c)
    g._units_base = g._players_base = None
    # the player's soldier captures the HQ
    u = mine[0]
    d.place_unit(u, *hq)
    g.select(*hq)
    g.move_to(*hq)
    g.choose("Capt", g.ACTION_MENU)
    g.wait_idle()
    before = g.unit(u["id"])
    g.goto(*hq)
    ctx.shot(g, "before_end")
    a2.to_day(e, g, d, 2)
    g._units_base = g._players_base = None
    alive = [x for x in cp.all_units(e, g) if x["id"] == u["id"]]
    after = alive[0] if alive else None
    s2 = cp.snapshot(e, g, 1)
    ctx.log(f"{kind}: the soldier had {before['hp']} HP, after the enemy's turn {after['hp'] if after else 'dead'}; HQ owner {s2['props'].get(hq)}")
    try:
        g.goto(*hq)
    except Exception:
        pass
    ctx.shot(g, "after_enemy")
    ctx.log(f"{kind}: the enemy's units now: " + str({x["id"]: (x["x"], x["y"], x["hp"]) for x in cp.all_units(e, g) if x["army"] != 1}))
    e.close()
    return before, after, s2["props"].get(hq), snap["props"].get(hq)


def check_defended(ctx, kind):
    before, after, hq_now, hq_was = scene(ctx, kind, off=False)
    ctx.check(after is None or after["hp"] < before["hp"], f"{kind}: the soldier on the enemy's HQ was attacked (HP {before['hp']} -> {after['hp'] if after else 'dead'})")
    ctx.check(hq_now == hq_was, f"{kind}: the HQ is still the enemy's ({hq_now})")
    # (a soldier with 10 HP still standing takes 10 of the 20 points: it needs another turn at full HP, which a hit prevents)


def _defends(kind):
    def fn(ctx):
        check_defended(ctx, kind)
    fn.__name__ = f"cpu_defends_hq_{kind}"
    test(modes=("ds",))(fn)


for _k in ("bh", "bh2", "es"):
    _defends(_k)


@test(modes=("ds",))
def cpu_defends_hq_m1_off(ctx):
    """With the rule's switch off the held soldiers leave the capturer alone (the bug the rule answers)."""
    before, after, hq_now, hq_was = scene(ctx, "bh", off=True)
    ctx.check(after is not None and after["hp"] == before["hp"], f"switch off: the held soldiers do not attack (HP {before['hp']} -> {after['hp'] if after else 'dead'})")
