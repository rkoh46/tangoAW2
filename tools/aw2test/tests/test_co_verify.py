"""`aw2dev co verify`: every ability of the custom COs (Klaus, Aurelia, Cassius, Livia, Varro, Crumb) in real battles, compared with the specification (aw2test.cospec).
Test names: `co_verify_<facet>_<co>[_<mode>]`; every check is tagged `[<co> <ability>]` (aw2test.coverify). Run: `aw2dev co verify [CO ...]`."""

from aw2test import coverify as cv
from aw2test.harness import test

NAMES = ("klaus", "aurelia", "cassius", "livia", "crumb", "varro")


def stats(name, mode):
    def fn(ctx):
        cv.stat_fights(ctx, name, mode)
    fn.__name__ = f"co_verify_stats_{name}_{cv.LEVEL[mode]}"
    test(modes=("ds",))(fn)


for _n in NAMES:
    for _m in (0, 1, 2):
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
        if _n == "andy" and _m:
            continue
        moves(_n, _m)
for _n in ("aurelia", "klaus"):
    for _m in (0, 1, 2):
        for _b in (0, 1):
            ranges(_n, _m, _b)


def economy(name, fpp=1000):
    def fn(ctx):
        cv.economy(ctx, name, fpp)
    fn.__name__ = f"co_verify_economy_{name}_{fpp}"
    test(modes=("ds",))(fn)


for _n in NAMES + ("andy",):
    economy(_n)
economy("andy", 2000)
economy("livia", 2000)


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
                continue          # (the other CO's own numbers are Dual Strike's, not under test; its pair is run from the Emerald Sun side as the partner)
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
def co_verify_hooks_klaus(ctx):
    cv.hook_testudo(ctx)


@test(modes=("ds",))
def co_verify_hooks_aurelia(ctx):
    cv.hook_onager(ctx)


@test(modes=("ds",))
def co_verify_hooks_cassius(ctx):
    cv.hook_triumph(ctx)


def cpu(name, which):
    def fn(ctx):
        cv.cpu_fires(ctx, name, which)
    fn.__name__ = f"co_verify_cpu_{name}_{'scop' if which == 'super' else 'cop'}"
    test(modes=("ds",))(fn)


for _n in NAMES + ("cloneandy",):
    cpu(_n, "power")
    cpu(_n, "super")


def cpu_tags():
    from aw2test import cospec
    for p in cospec.tags():
        for act, par in ((p["a"], p["b"]), (p["b"], p["a"])):
            if act.startswith("aw2:"):
                continue
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
economy("cloneandy")
meter("cloneandy")


@test(modes=("ds",))
def co_verify_limits_cassius(ctx):
    cv.triumph_limits(ctx)
