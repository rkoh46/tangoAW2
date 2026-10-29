"""`aw2dev stage next <mission>` (docs/dev/stages.md "Inspecting and forcing a switch"): the mission is entered and played to its stage switch with real captures (the triggers that end the stage are the
mission's own: the HQs of STAGE_TRIGGERS, in order), the battle is read just before and just after, and a report says what the switch did: the stage, the map's size, each army's units and funds before and
after, the carried units and the player's meter. A pictures of the moment before and of the new stage's first frame. AW2TEST_STAGE_MISSION=<n> names another mission (a mission with stages gets a row in STAGE_TRIGGERS),
AW2TEST_STAGE_OUT=<file.json> where the report goes. `stage_tool_m31` runs it on M31 in the default suite."""

import importlib.util
import json
import os

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import dscampaign as dc
from aw2test import harness
from aw2test.harness import test

_n = len(harness.TESTS)
_spec = importlib.util.spec_from_file_location("bh2_progression_helpers3", os.path.join(os.path.dirname(__file__), "test_bh2_progression.py"))
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)
del harness.TESTS[_n:]

# mission -> (the player's army number, [(name, cell)] captured in order; the last one ends the stage)
STAGE_TRIGGERS = {31: (5, [(name, cell) for name, cell, _, _ in bp.HQS])}


def read_state(g, e, mine):
    p = g.players_base
    units, funds, types = {}, {}, {}
    for u in g.units():
        units[u["army"]] = units.get(u["army"], 0) + 1
        if u["army"] == mine:
            types[u["type"]] = types.get(u["type"], 0) + 1
    for a in range(1, 6):
        if units.get(a):
            funds[a] = e.u32(p + 0x3C * a)
    return {"stage": e.u8(bp.STAGE_AT) + 1, "map": [e.u16(dc.MAP), e.u16(dc.MAP + 2)], "day": e.u16(dc.DAY), "five_on": e.u8(bp.FIVE_ON), "units": units, "funds": funds,
            "player_types": types, "player_meter": e.u32(p + 0x3C * mine + 0x20)}


def switch_report(ctx, n):
    mine, hqs = STAGE_TRIGGERS[n]
    e, g, d = b2.enter(ctx, n)
    d.leave_setup()
    a2.intro(ctx, e, d, f"m{n}", (0,))
    d.wait_control()
    g._units_base = g._players_base = None
    from tests.test_bh2_review import home
    home(g, e)
    e.wait(60)
    for k, (name, cell) in enumerate(hqs):
        if k == len(hqs) - 1:
            before = read_state(g, e, mine)
            ctx.shot(g, "before_switch")
        bp.capture(ctx, e, g, d, cell, mine)
        if k < len(hqs) - 1:
            bp.settle(e, g, d)
    bp.wait_stage(ctx, e, g, d, 1)
    d.dialogue()
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.shot(g, "after_switch")
    after = read_state(g, e, 1 if after_is_four(e) else mine)
    rep = {"mission": n, "title": b2.TITLES[n], "triggers": [name for name, _ in hqs], "before": before, "after": after, "dir": ctx.out,
           "carried": sum(before["player_types"].values()) and {t: after["player_types"].get(t, 0) for t in before["player_types"]}}
    e.close()
    return rep


def after_is_four(e):
    return e.u8(bp.FIVE_ON) == 0


@test(name="stage_tool_m31", modes=("ds",))
def stage_tool_m31(ctx):
    """The stage report of M31: stage 1 before, stage 2 after, a smaller map, four armies, the player's survivors and funds carried (the report `aw2dev stage next 31` prints)."""
    rep = switch_report(ctx, 31)
    ctx.eq(rep["before"]["stage"], 1, "before: stage 1")
    ctx.eq(rep["after"]["stage"], 2, "after: stage 2")
    ctx.eq(rep["before"]["five_on"], 2, "before: the five-army mission")
    ctx.eq(rep["after"]["five_on"], 0, "after: four armies")
    ctx.check(sum(rep["after"]["units"].values()) > 0 and 1 in rep["after"]["units"], f"the player's survivors are on the new map ({rep['after']['units']})")
    ctx.check(rep["after"]["funds"].get(1, 0) >= 0, "the player's funds are read")
    out = os.environ.get("AW2TEST_STAGE_OUT")
    if out:
        with open(out, "w") as f:
            json.dump(rep, f, indent=1)
    ctx.log(json.dumps(rep))


_N = int(os.environ.get("AW2TEST_STAGE_MISSION", "0") or 0)
if _N and _N != 31:
    def _tool(ctx):
        rep = switch_report(ctx, _N)
        out = os.environ.get("AW2TEST_STAGE_OUT")
        if out:
            with open(out, "w") as f:
                json.dump(rep, f, indent=1)
        ctx.log(json.dumps(rep))
    _tool.__name__ = f"stage_tool_m{_N}"
    test(modes=("ds",))(_tool)
