"""Opt-in audit of the Black Factory's choices (AW2TEST_BH_AUDIT=<folder>): plays BH Campaign missions with the
Black Hole army through the bot and copies every decision (with all candidates, TANGOAW2_BH_LOG_ALL) to the folder.
AW2TEST_BH_AUDIT_MISSIONS=2,7 and AW2TEST_BH_AUDIT_DAYS=14 narrow it."""

import os
import shutil

from aw2test import bhact5 as a5
from aw2test import bhcampaign as bh
from aw2test import paths
from aw2test.harness import Skip, test

OUT = os.environ.get("AW2TEST_BH_AUDIT")
MISSIONS = [int(x) for x in os.environ.get("AW2TEST_BH_AUDIT_MISSIONS", "2,7,12,19,28,29").split(",")]
DAYS = int(os.environ.get("AW2TEST_BH_AUDIT_DAYS", "14"))


def audit_m12(ctx, save):
    """M12 asks for a pair (Sturm, Hawke) and has its own opening: driven with the Act III helpers."""
    from aw2test import bhact3 as a3
    mask = sum(1 << a3.M[k] for k in range(1, 12))
    e, g, d = a3.boot(ctx, mask, a3.ST | a3.VB | a3.HK, picks={a3.M[12]: 2}, at=a3.M[12], save=save)
    a3.open_mission(ctx, e, g, d, a3.M[12], [bh.STURM, bh.HAWKE], "m12")
    d.wait_control()
    g._units_base = g._players_base = None
    return e, g, d


def audit_mission(ctx, n):
    if not OUT:
        raise Skip("AW2TEST_BH_AUDIT not set")
    os.makedirs(OUT, exist_ok=True)
    save = os.path.join(ctx.out, f"m{n}.sav")       # (its own copy: the factory log is named after the save)
    shutil.copy(paths.base_save(), save)
    if n == 12:
        e, g, d = audit_m12(ctx, save)
    else:
        e, g, d = a5.boot(ctx, a5.WON(n - 1), 0xFFF, picks={a5.M[n]: 0}, at=a5.M[n], save=save,
                          env={"TANGOAW2_BH_LOG_ALL": "1"})
        d.pick_mission()
        for _ in range(80):
            if d.on_co_select():
                d.choose_cos(1)
            elif d.in_battle() and d.players() != 0:
                break
            else:
                e.press("A", 4)
                e.wait(20)
        g._units_base = g._players_base = None
    r = d.play(max_days=DAYS, log=ctx.log)
    ctx.log(f"M{n}: {r}")
    lines = e.decisions()
    shutil.copy(e.bh_log, os.path.join(OUT, f"m{n:02d}.log")) if os.path.exists(e.bh_log) else None
    ctx.log(f"{len([l for l in lines if not l.startswith('    cand')])} decisions")


def _make(n):
    @test(name=f"bh_smart_audit_m{n}", modes=("ds",))
    def audit(ctx):
        audit_mission(ctx, n)
    return audit


for _n in MISSIONS:
    globals()[f"bh_smart_audit_m{_n}"] = _make(_n)
