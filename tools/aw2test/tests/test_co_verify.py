"""`aw2dev co verify`: every ability of the custom COs (Tabitha, Lili, Caulder, Crumb, Clone Andy, Aria; Asuka through her own suite) in real battles, compared with the specification (aw2test.cospec).
Test names: `co_verify_<facet>_<co>[_<mode>]`; every check is tagged `[<co> <ability>]` (aw2test.coverify). Run: `aw2dev co verify [CO ...]`."""

from aw2test import coverify as cv
from aw2test.harness import test

NAMES = ("tabitha", "lili", "caulder", "crumb", "cloneandy", "aria")
NO_COP = ("aria", "tabitha", "caulder")      # only a Super Power (like Sturm): no CO Power level is played for them
NO_SCOP = ("lili",)                          # only a CO Power (0 stars for the Super Power): no Super Power level is played, and the map menu offers none


def stats(name, mode):
    def fn(ctx):
        cv.stat_fights(ctx, name, mode)
    fn.__name__ = f"co_verify_stats_{name}_{cv.LEVEL[mode]}"
    test(modes=("ds",))(fn)


def played(name, mode):
    """Whether power level `mode` (0 day to day, 1 CO Power, 2 Super Power) exists for the CO."""
    return not ((name in NO_COP and mode == 1) or (name in NO_SCOP and mode == 2))


for _n in NAMES:
    for _m in (0, 1, 2):
        if played(_n, _m):
            stats(_n, _m)


def moves(name, mode):
    def fn(ctx):
        cv.move_range_moves(ctx, name, mode)
    fn.__name__ = f"co_verify_move_{name}_{cv.LEVEL[mode]}"
    test(modes=("ds",))(fn)


def ranges(name, mode, beyond):
    def fn(ctx):
        cv.move_range_range(ctx, name, mode, beyond)
    fn.__name__ = f"co_verify_range_{name}_{cv.LEVEL[mode]}_{'beyond' if beyond else 'edge'}"
    test(modes=("ds",))(fn)


for _n in NAMES + ("andy",):
    for _m in (0, 1, 2):
        if (_n == "andy" and _m) or not played(_n, _m):
            continue
        moves(_n, _m)
for _n in ("tabitha", "lili", "caulder"):
    for _m in (0, 1, 2):
        for _b in (0, 1):
            if played(_n, _m):
                ranges(_n, _m, _b)


def economy(name, fpp=1000):
    def fn(ctx):
        cv.economy(ctx, name, fpp)
    fn.__name__ = f"co_verify_economy_{name}_{fpp}"
    test(modes=("ds",))(fn)


for _n in NAMES + ("andy",):
    economy(_n)
economy("andy", 2000)
economy("lili", 2000)


def meter(name):
    def fn(ctx):
        cv.meter(ctx, name)
    fn.__name__ = f"co_verify_meter_{name}"
    test(modes=("ds",))(fn)


for _n in NAMES:
    meter(_n)


def tags():
    from aw2test import cospec
    seen = set()
    for p in cospec.tags():
        for act, par in ((p["a"], p["b"]), (p["b"], p["a"])):
            if act.startswith("aw2:"):
                continue          # (the other CO's own numbers are Dual Strike's, not under test; its pair is run from the Silver Nova side as the partner)
            def fn(ctx, act=act, par=par):
                cv.tag_pair(ctx, act, par)
            fn.__name__ = "co_verify_tag_" + act.split(":")[-1] + "_with_" + par.split(":")[-1]
            test(modes=("ds",))(fn)


tags()


def unlisted_tags():
    from aw2test import cospec
    for act, par in cospec.UNLISTED_PAIRS:
        def fn(ctx, act=act, par=par):
            cv.tag_pair(ctx, act, par)
        fn.__name__ = "co_verify_tag_" + act + "_with_" + par.split(":")[-1] + "_unlisted"
        test(modes=("ds",))(fn)


unlisted_tags()


@test(modes=("ds",))
def co_verify_hooks_tabitha(ctx):
    cv.hook_firestorm(ctx)


@test(modes=("ds",))
def co_verify_hooks_lili(ctx):
    cv.hook_enigma_roll(ctx)


@test(modes=("ds",))
def co_verify_hooks_lili_permanent(ctx):
    cv.hook_enigma_permanent(ctx)


@test(modes=("ds",))
def co_verify_hooks_lili_immunity(ctx):
    cv.hook_enigma_immunity(ctx)


@test(modes=("ds",))
def co_verify_hooks_lili_move(ctx):
    cv.hook_enigma_move(ctx)


@test(modes=("ds",))
def co_verify_hooks_lili_suspend(ctx):
    cv.hook_enigma_suspend(ctx)


def days(rules):
    def fn(ctx):
        cv.hook_enigma_days(ctx, rules)
    fn.__name__ = f"co_verify_hooks_lili_days_{rules}"
    test(modes=("ds",))(fn)


for _r in ("clear", "snow", "random"):
    days(_r)


@test(modes=("ds",))
def co_verify_hooks_caulder(ctx):
    cv.hook_cataclysm(ctx)


@test(modes=("ds",))
def co_verify_hooks_caulder_move(ctx):
    cv.hook_sturm_move(ctx)


def cpu(name, which):
    def fn(ctx):
        cv.cpu_fires(ctx, name, which)
    fn.__name__ = f"co_verify_cpu_{name}_{'scop' if which == 'super' else 'cop'}"
    test(modes=("ds",))(fn)


for _n in NAMES:
    if played(_n, 1):
        cpu(_n, "power")
    if played(_n, 2):
        cpu(_n, "super")


@test(modes=("ds",))
def co_verify_cpu_tabitha_firestorm(ctx):
    cv.cpu_firestorm(ctx)


def cpu_tags():
    from aw2test import cospec
    for p in cospec.tags():
        for act, par in ((p["a"], p["b"]), (p["b"], p["a"])):
            if act.startswith("aw2:") or act in NO_SCOP:
                continue          # (a CO with no Super Power, Lili, never starts the computer's Tag Power: its AI wants a Super paid for; she is the partner of the others' pairs)
            def fn(ctx, act=act, par=par):
                cv.cpu_tag(ctx, act, par)
            fn.__name__ = "co_verify_cpu_tag_" + act.split(":")[-1] + "_with_" + par.split(":")[-1]
            test(modes=("ds",))(fn)


cpu_tags()


def clone(mode):
    def fn(ctx):
        cv.clone_vs_andy(ctx, mode)
    fn.__name__ = f"co_verify_cloneandy_{cv.LEVEL[mode]}"
    test(modes=("ds",))(fn)


for _m in (0, 1, 2):
    clone(_m)


def pin(name):
    def fn(ctx):
        cv.pin_vehicles(ctx, name)
    fn.__name__ = f"co_verify_vehicles_{name}"
    test(modes=("ds",))(fn)


for _n in ("tabitha", "lili", "caulder"):
    pin(_n)


def hq(name):
    def fn(ctx):
        cv.hq_versus(ctx, name)
    fn.__name__ = f"co_verify_hq_{name}"
    test(modes=("ds",))(fn)


for _n in NAMES:
    hq(_n)


@test(modes=("ds",))
def co_verify_hq_tag(ctx):
    cv.hq_tag(ctx)


def hq_m(n):
    def fn(ctx):
        cv.hq_mission(ctx, n)
    fn.__name__ = f"co_verify_hq_m{n}"
    test(modes=("ds",))(fn)


for _k in range(1, 17):
    hq_m(_k)
