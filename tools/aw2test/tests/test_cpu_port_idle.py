"""No computer unit idles on a base, port or airport (aw2test/cpuports.py; docs/dev/cpu-unit-use.md). One test per mission and map: `-k cpu_port_idle`."""

from aw2test import cpuports as cpo
from aw2test import cpuprobe as cp
from aw2test.harness import test


def _bh(n):
    def fn(ctx):
        e, g, (snaps, fronts) = cpo.run_bh(ctx, n)
        cpo.report(ctx, f"BH M{n}", snaps, scripted=True)
        if fronts:
            cpo.report(ctx, f"BH M{n} other front", fronts, scripted=True)
        e.close()
    fn.__name__ = f"cpu_port_idle_bh_m{n}"
    test(modes=("ds",))(fn)


for _n in cp.M:
    _bh(_n)


def _bh2(n):
    def fn(ctx):
        e, g, (snaps, fronts) = cpo.run_bh2(ctx, n)
        cpo.report(ctx, f"BH2 M{n}", snaps, scripted=True)
        if fronts:
            cpo.report(ctx, f"BH2 M{n} other front", fronts, scripted=True)
        e.close()
    fn.__name__ = f"cpu_port_idle_bh2_m{n}"
    test(modes=("ds",))(fn)


def _es(n):
    def fn(ctx):
        e, g, (snaps, _) = cpo.run_es(ctx, n)
        cpo.report(ctx, f"Silver Nova M{n}", snaps, scripted=True)
        e.close()
    fn.__name__ = f"cpu_port_idle_es_m{n}"
    test(modes=("ds",))(fn)


def _dsc(step):
    def fn(ctx):
        e, g, (snaps, fronts) = cpo.run_dsc(ctx, step)
        cpo.report(ctx, f"DS step {step}", snaps, scripted=True)
        if fronts:
            cpo.report(ctx, f"DS step {step} other front", fronts, scripted=True)
        e.close()
    fn.__name__ = f"cpu_port_idle_dscampaign_s{step:02d}"
    test(modes=("ds",))(fn)


from aw2test import bh2campaign as _b2
from aw2test import dscampaign as _dc
from aw2test import escampaign as _es_mod

for _n in _b2.TITLES:
    _bh2(_n)
for _n in _es_mod.TITLES:
    _es(_n)
for _s in range(len(_dc.ORDER)):
    _dsc(_s)


def _gauntlet_maps():
    """The selector's entries: five/gauntlet/gauntlet_NN.txt is entry NN-1 (a name ending in b is the same map's later stage)."""
    import glob
    import os
    import re
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "tango-gamesupport-aw2", "five", "gauntlet")
    out = []
    for f in sorted(glob.glob(os.path.join(here, "gauntlet_*.txt"))):
        m = re.fullmatch(r"gauntlet_(\d+)\.txt", os.path.basename(f))
        if m:
            out.append(int(m.group(1)) - 1)
    return out


def _gauntlet(k):
    def fn(ctx):
        e, g, (snaps, _) = cpo.run_gauntlet(ctx, k)
        cpo.report(ctx, f"Gauntlet map {k}", snaps)
        e.close()
    fn.__name__ = f"cpu_port_idle_gauntlet_{k}"
    test(modes=("ds",))(fn)


for _k in _gauntlet_maps():
    _gauntlet(_k)


# --- Versus: every map the game lists with the pack (SELECT MAP's tabs, read from the game once and cached) ------------------
from aw2test import versusmaps as _vm


def _versus(tab, row, mid):
    def fn(ctx):
        e, g, (snaps, _) = cpo.run_versus(ctx, tab, row, mid)
        # (scripted: a pre-deployed unit whose map data gives it role 0 is the map's own garrison, as a mission's)
        cpo.report(ctx, f"Versus map {mid:#x} (tab {tab}, row {row})", snaps, scripted=True)
        e.close()
    fn.__name__ = f"cpu_port_idle_versus_{mid:02x}"
    test(modes=("ds",))(fn)


_seen = set()
for _tab, _row, _mid in _vm.entries():
    if _mid not in _seen:        # (a map on two tabs is one map)
        _seen.add(_mid)
        _versus(_tab, _row, _mid)


# --- Design Room maps with ports, bases and airports on both sides (tests/test_cpu_design_maps.py) -------------------------
def _design(name, five):
    def fn(ctx):
        from tests.test_cpu_design_maps import everything_map
        m = everything_map(ctx, five=five)
        e, g, (snaps, _) = cpo.run_design(ctx, m, None if five else ["andy", "vonbolt"])
        cpo.report(ctx, f"design map {name}", snaps)
        e.close()
    fn.__name__ = f"cpu_port_idle_design_{name}"
    test(modes=("ds",))(fn)


_design("everything", False)
_design("five_armies", True)


# --- AW2's own campaign, Survival and the War Room: AW2's ORIGINAL AI plays them (not Dual Strike's): run so that we know ---
def _aw2_campaign(k):
    def fn(ctx):
        e, g, (snaps, _) = cpo.run_aw2_campaign(ctx, k)
        cpo.report(ctx, f"AW2 campaign mission {k + 1} (map {g.playst()['map']:#x})", snaps)
        e.close()
    fn.__name__ = f"cpu_port_idle_aw2campaign_m{k + 1:02d}"
    test(modes=("ds",))(fn)


for _k in range(cpo.AW2_CAMPAIGN_MISSIONS):
    _aw2_campaign(_k)


def _survival(kind):
    def fn(ctx):
        from aw2test import survival as sv
        e, g, (snaps, _) = cpo.run_survival(ctx, kind)
        cpo.report(ctx, f"Survival {sv.NAMES[kind]}", snaps)
        e.close()
    fn.__name__ = "cpu_port_idle_survival_" + {0: "time", 1: "money", 2: "turn"}.get(kind, str(kind))
    test(modes=("ds",))(fn)


def _warroom(row, mode):
    def fn(ctx):
        e, g, (snaps, _) = cpo.run_warroom(ctx, row)
        cpo.report(ctx, f"War Room ({mode}) row {row}", snaps)
        e.close()
    fn.__name__ = f"cpu_port_idle_warroom_{mode}_{row:02d}"
    test(modes=(mode,))(fn)


from aw2test import survival as _sv
from aw2test import warroom as _wr

for _kind in _sv.LIST_ORDER:
    _survival(_kind)
for _row in range(len(_wr.DS_IDS)):       # (with the pack the War Room lists Dual Strike's 44 maps)
    _warroom(_row, "ds")
for _row in range(30):                    # (without it AW2's own 30: ids 0x6C..)
    _warroom(_row, "aw2")


@test(modes=("ds",))
def war_room_dual_strike_cpu_plays_then_the_win_is_recorded(ctx):
    """The War Room is played by Dual Strike's CPU: three days with the player passive, then every computer army yields (the win aid): the results and the record screen follow, and
    the win is in the War Room's records."""
    from aw2test import warroom as wr
    from aw2test import survival as sv
    e, g, (snaps, _) = cpo.run_warroom(ctx, 0, days=3)
    ctx.check(len(snaps) >= 3, f"three days played ({len(snaps)})")
    log = [l for l in e.decisions() if l.startswith("dsai")]
    ctx.check(log, "Dual Strike's CPU logged its decisions in the War Room")
    wr.set_ds(ctx.ds)
    before = wr.rows(e)
    wr.win_map(e, g)       # (raises if SELECT MAP does not come back after the results and the rank screen)
    ctx.check(sv.running(e, sv.SELECT_MAP_PROC), "back on SELECT MAP after the results")
    ctx.check(len(wr.rows(e)) > len(before) or wr.rows(e) != before, "the win is in the War Room's records")
    e.close()
