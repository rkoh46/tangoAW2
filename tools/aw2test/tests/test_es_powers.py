"""The Silver Nova COs' powers that need engine hooks (crate::es_co, crate::co_powers): Tabitha's Firestorm (8 HP in a 13-cell diamond at AW2's own site, never kills, spares her
team, no stun) and Lili's Enigma (a weather drawn from the game's RNG for two days, her units immune to it). Their numbers and rules are played against the specification by
`aw2dev co verify` (tests/test_co_verify.py, aw2test/coverify.py: `hooks`, `cpu` and `tag` facets); this file holds what a determinism run adds. Each scenario is played twice from the
same start and must end with the same RAM (what both peers of a match need), and once on two rollback peers."""

from aw2test import coverify as cv
from aw2test.harness import test

ENV = cv.ENV
TABITHA, LILI, CAULDER = 86, 87, 88


def ram_dump(g):
    return g.e.read(0x02000000, 0x40000) + g.e.read(0x03000000, 0x7E00)


def differing(a, b):
    return [i for i in range(len(a)) if a[i] != b[i]]


def twice(ctx, scenario, what):
    """Both peers of a match run the game from identical inputs (docs/dev/architecture-online.md); each rule reads and writes only emulated memory, so two consoles given the same
    inputs must end with the same RAM. Each scenario is played on two consoles (each its own process) and the whole of EWRAM and IWRAM is compared."""
    dumps = []
    for run in (1, 2):
        g = scenario()
        g.e.wait(120)
        dumps.append((g.e.frame, ram_dump(g)))
        g.e.close()
    (f1, d1), (f2, d2) = dumps
    ctx.eq(f1, f2, f"{what}: both runs are at the same frame")
    bad = differing(d1, d2)
    shown = [(f"{(0x02000000 + i) if i < 0x40000 else (0x03000000 + i - 0x40000):#010x}", d1[i], d2[i]) for i in bad[:8]]
    ctx.check(not bad, f"{what}: EWRAM and IWRAM are identical after both runs ({len(bad)} bytes differ {shown})")
    return d1


@test(modes=("ds",))
def es_tabitha_firestorm_is_deterministic(ctx):
    def run():
        g = cv.firestorm_game(ctx)
        ctx.power(g, 1, "super")
        return g
    twice(ctx, run, "Firestorm")


@test(modes=("ds",))
def es_lili_enigma_is_deterministic(ctx):
    for weather in ("snow", "sand"):
        def run():
            g = cv.enigma_game(ctx)
            cv.use_enigma(ctx, g, cv.SEEDS[weather])
            cv.pass_turn(g, 2)
            return g
        twice(ctx, run, f"Enigma ({weather})")


@test(modes=("ds",))
def es_caulder_cataclysm_is_deterministic(ctx):
    def run():
        m = ctx.map()
        m.unit(1, "tank", 10, 10).unit(1, "infantry", 10, 14).unit(2, "tank", 11, 10)
        g = ctx.start(m, [CAULDER, "andy"], env=ENV)
        ctx.set_hp(g, 10, 14, 35)
        ctx.power(g, 1, "super")
        g.attack((10, 10), (10, 10), (11, 10))
        return g
    twice(ctx, run, "Cataclysm")


@test(modes=("ds",), netplay=True)
def netplay_firestorm(ctx):
    """Firestorm, then the turn passes and comes back: replayed on two rollback peers, identical (EWRAM, IWRAM), the stun marks as played (none)."""
    g = cv.firestorm_game(ctx)
    ctx.power(g, 1, "super")
    cv.pass_turn(g, 2)
    cv.pass_turn(g, 1)
    identical, values, text = ctx.netplay_replay(g, [(cv.STUN_PENDING, 80)], env=ENV)
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check(identical, "both peers and the straight replay identical")
    ctx.eq(values.get(cv.STUN_PENDING), g.e.read(cv.STUN_PENDING, 80), "the stun marks as played")


@test(modes=("ds",), netplay=True)
def netplay_enigma(ctx):
    """Enigma (sand), two turn changes: replayed on two rollback peers, identical (EWRAM, IWRAM), Enigma's state bytes as played."""
    g = cv.enigma_game(ctx, humans=(1,))
    cv.use_enigma(ctx, g, cv.SEEDS["sand"])
    g.end_turn(human=1)
    identical, values, text = ctx.netplay_replay(g, [(cv.LILI_STATE, 41)], env=ENV)
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check(identical, "both peers and the straight replay identical")
    ctx.eq(values.get(cv.LILI_STATE), g.e.read(cv.LILI_STATE, 41), "Enigma's state as played")
