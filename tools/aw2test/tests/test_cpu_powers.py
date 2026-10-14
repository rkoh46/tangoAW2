"""The computer uses the new COs' powers, by Dual Strike's rules with the pack
(crate::ds_ai_power: each CO's profile, at the first power check of the turn):
with a full meter the CPU fires its Super CO Power on its turn, and its CO
Power when only that is paid for, where Dual Strike's CO would (Kindle with
enemy units on properties, Sasha with 30000 funds and an enemy nearer its
power); Rachel's profile never uses her CO Power (she saves for the Super)."""

from aw2test import ram, rom as romlib
from aw2test.harness import test

NEW = ["jugger", "koal", "kindle", "vonbolt", "grimm", "javier", "sasha", "jake", "rachel"]


# Dual Strike's profile never uses this CO Power (template byte 5 is 0).
NEVER_POWER = {"rachel"}


def cpu_fires(ctx, co, which):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(1, "infantry", 5, 5)
    m.unit(2, "tank", 14, 6).unit(2, "artillery", 18, 8).unit(2, "mech", 16, 10)
    if co == "kindle":
        # (Urban Blight with a fifth of the enemy's units on properties)
        m.terrain(10, 6, "city", 0).terrain(5, 5, "city", 0)
    g = ctx.start(m, ["andy", co])
    if co == "sasha" and which != "super":
        # (Market Crash with 30000 funds and an enemy meter fuller than hers)
        g.e.w32(g.player(2)["addr"] + ram.P_FUNDS, 30000)
        g.e.w32(g.player(1)["addr"] + ram.P_CHARGE, 200000)
    modes = set()
    def watch(gg):
        for _ in range(200):
            gg.e.wait(10)
            p = gg.player(2)
            modes.add(p["co_mode"])
            if gg.current_army() != 2:
                break
    # The CPU fires a CO Power 95% of the time it could (AW2's rule, the
    # same for the new COs): give it up to three turns.
    for turn in range(3):
        cost = g.charge_power(2, which)
        ctx.log(f"{co}: turn {turn}, meter set to {cost} for {which}")
        g.end_turn(observe=watch)
        if g.player(2)["powers_used"]:
            break
    p = g.player(2)
    ctx.log(f"{co}: modes seen on its turn {sorted(modes)}, powers used {p['powers_used']}")
    ctx.log("\n".join(l for l in g.e.decisions() if l.startswith("dsai power")))
    if which != "super" and co in NEVER_POWER:
        ctx.eq(p["powers_used"], 0, f"the CPU never fires {co}'s CO Power (it saves for the Super)")
        return
    ctx.eq(p["powers_used"], 1, f"the CPU fired {co}'s {which}")
    want = 2 if which == "super" else 1
    ctx.check(want in modes, f"{co}'s power mode {want} seen during its turn")


def make(co, which):
    def fn(ctx):
        cpu_fires(ctx, co, which)
    fn.__name__ = f"cpu_power_{co}_{'scop' if which == 'super' else 'cop'}"
    test(modes=("ds",))(fn)


for co in NEW:
    make(co, "super")
    if co != "vonbolt":
        make(co, "power")
