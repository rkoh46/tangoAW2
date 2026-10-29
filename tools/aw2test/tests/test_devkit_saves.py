"""The devkit's reading of a suspended save (`aw2dev save inspect`, devkit/aw2/savelib.py) against a real five-army suspend, and the playthrough report's formatting (devkit/aw2/playlib.py)."""

import os
import sys

from aw2test import saves
from aw2test.harness import test
from tests.test_five_unit_palettes import five_map

DEVKIT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "devkit")


def devkit():
    if DEVKIT not in sys.path:
        sys.path.insert(0, DEVKIT)
    from aw2 import savelib, playlib
    return savelib, playlib


@test(name="save_inspect_reads_the_five_army_record")
def save_inspect_reads_the_five_army_record(ctx):
    """A five-army Versus game saved: `save inspect` finds the Versus slot, the record after AW2's block, its hash matching the block, FIVE_ON 1, five armies with their unit counts (the units the game has), and the sectors used."""
    savelib, _ = devkit()
    g = ctx.start(five_map(ctx), None, humans=(1,))
    g.wait_for_input()
    counts = {a: len(g.units(army=a)) for a in range(1, 6)}
    saves.suspend(g)
    saved = saves.flash(g.e, os.path.join(ctx.out, "saved"))
    g.e.close()
    rep = savelib.inspect(saved.path)
    ctx.eq([s["slot"] for s in rep["slots"]], [4], "one suspended game, in the Versus slot")
    f = rep["slots"][0].get("five")
    ctx.require(f is not None, "the five-army record is found")
    ctx.check(f["hash_matches"], "its hash matches AW2's block")
    ctx.eq(f["five_on"], 1, "FIVE_ON in the record")
    ctx.check(f["decoded_ok"], "its length is what its units add up to")
    ctx.eq({a["army"]: a["units"] for a in f["armies"]}, counts, "the units of each army")
    ctx.eq(rep["sectors"]["by_slot"].get(4), 2, "the slot takes two Flash sectors")
    text = savelib.render(rep)
    ctx.check("five-army record" in text and "matches this block" in text, "the text report says so")
    # a record that does not belong to the block: one byte of AW2's part changed
    blk = bytearray(saved_slot := bytes(saves_slot(saved)))
    blk[0x100] ^= 0xFF
    ctx.check(not savelib.describe_slot(4, bytes(blk))["five"]["hash_matches"], "a changed block no longer matches the record (stale)")


def saves_slot(img):
    return img.slot(4)


@test(name="playthrough_report_formats")
def playthrough_report_formats(ctx):
    """The playthrough report's Markdown carries the outcome, the takeovers, the stage switch, the stalls and a row a day."""
    _, playlib = devkit()
    rep = {"mission": 31, "title": "The Last Accord", "player": "cpu", "result": "won", "days": 3, "frames": 1000, "reason": "the enemy HQ taken", "stages_reached": 2,
           "events": [{"event": "takeover", "hq": "Nell", "owner": 5, "day": 2, "stage": 1}, {"event": "stage switch", "from": 1, "to": 2, "day": 3, "frame": 900}],
           "daily": [{"day": 1, "stage": 1, "units": {"1": 3, "5": 2}, "funds": {"1": 100, "5": 50}}], "stalls": [{"day": 3, "stage": 2, "why": "day limit 3"}], "shots": [], "dir": ctx.out}
    md = playlib.markdown(rep)
    for needle in ("**won**", "Nell's HQ taken", "stage 1 -> 2", "day limit 3", "| 1 | 1 |"):
        ctx.check(needle in md, f"the report has {needle!r}")
