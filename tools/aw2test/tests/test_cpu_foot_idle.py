"""The computer's foot soldiers work (aw2test/cpuports.py `foot_idle`): with the player passive for six turns, on Silver Nova's M1 the computer's
Infantry and Mechs take property (at least one neutral building changes hands) and on average at least 60% of its units act each turn. `-k cpu_foot_idle`.
`cpu_foot_idle_report_*` log the same figures for every Silver Nova mission (no checks: the report is how an idle pattern is found)."""

from aw2test import cpuports as cpo
from aw2test import escampaign as es_mod
from aw2test.harness import test


def play_with_bot(ctx, n, days, **opts):
    """Mission `n` with the test player (aw2test.bot) playing army 1 and a snapshot at the start of each of its days: the player lands, so the computer's units have targets."""
    from aw2test import bhact2 as a2
    e, g, d = cpo.start_campaign(ctx, es_mod, n)
    snaps = []

    def log(t):
        if t.startswith("day "):
            g._units_base = g._players_base = None
            snaps.append(cpo.snapshot(ctx, e, g))
    opts.setdefault("cap", 42)
    d.play(days, log=log, **opts)
    return e, g, snaps


@test(modes=("ds",))
def cpu_foot_idle_es_m1_captures_and_acts(ctx):
    e, g, (snaps, _) = cpo.run_es(ctx, 1, days=7)
    res = cpo.foot_report(ctx, "Silver Nova M1", snaps)
    ctx.check(len(snaps) >= 6, f"the game ran six turns ({len(snaps)} snapshots)")
    gained = {c for c, (k, o) in snaps[-1]["props"].items() if o == 2 and snaps[0]["props"][c][1] != 2}
    ctx.check(len(gained) >= 1, f"Green Earth's foot soldiers took at least one property ({sorted(gained)})")
    r = res[2]
    ctx.check(r["soldiers"] > 0 and r["acted"] * 100 >= 60 * r["soldiers"], f"at least 60% of Green Earth's foot-soldier turns are work ({r['acted']}/{r['soldiers']}; the two HQ guards hold by the map's design)")
    e.close()


@test(modes=("ds",))
def cpu_foot_idle_es_m1_vs_bot_units_act(ctx):
    """With the test player landing (the way a person plays it), over six days Green Earth's foot soldiers take property and on average at least 60% of its units act each turn."""
    e, g, snaps = play_with_bot(ctx, 1, 7, goals=[(14, 4)])
    cpo.foot_report(ctx, "Silver Nova M1 vs bot", snaps)
    ctx.check(len(snaps) >= 6, f"the game ran six turns ({len(snaps)} snapshots)")
    gained = {c for c, (k, o) in snaps[-1]["props"].items() if o == 2 and snaps[0]["props"][c][1] != 2}
    ctx.check(len(gained) >= 1, f"Green Earth took at least one property ({sorted(gained)})")
    k, n = cpo.acting_share(snaps, 2)
    ctx.check(n > 0 and k * 100 >= 60 * n, f"at least 60% of Green Earth's units acted each turn ({k}/{n})")
    e.close()


def _report(n):
    def fn(ctx):
        e, g, (snaps, _) = cpo.run_es(ctx, n, days=7)
        cpo.foot_report(ctx, f"Silver Nova M{n}", snaps)
        e.close()
    fn.__name__ = f"cpu_foot_idle_report_es_m{n}"
    test(modes=("ds",))(fn)


for _n in es_mod.TITLES:
    _report(_n)
