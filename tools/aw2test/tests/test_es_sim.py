"""Emerald Sun Campaign: the mission sim (`aw2dev campaign sim`, docs/dev/es-campaign.md). Opt-in: AW2TEST_ES_SIM=<n>[,<n>..] names the missions;
AW2TEST_ES_PLAYER=bot|cpu (the test player of aw2test.bot, or the game's own computer playing both sides), AW2TEST_ES_SEED=<k> (another start for
the computer and another style for the bot), AW2TEST_ES_DAYS=<max days>, AW2TEST_ES_OUT=<file> (one JSON line per run is appended)."""

import json
import os

from aw2test import dscampaign as dc
from aw2test import escampaign as es
from aw2test.harness import test

NS = [int(x) for x in os.environ.get("AW2TEST_ES_SIM", "").replace(",", " ").split()]
PLAYER = os.environ.get("AW2TEST_ES_PLAYER", "bot")
SEED = int(os.environ.get("AW2TEST_ES_SEED", "0"))
DAYS = int(os.environ.get("AW2TEST_ES_DAYS", "25"))
OUT = os.environ.get("AW2TEST_ES_OUT")

# The test player's own settings by mission (aw2test.bot.Bot): the cells a mission is won on, a stance, a rush on the HQ.
BOT = {
    2: {"stance": "defend"},
    5: {"goals": [(15, 2), (15, 6), (15, 11)], "rush": True},
    6: {},
    11: {"goals": [(24, 6)]},
}


def run(ctx, n):
    e, g, d = es.enter(ctx, n)
    if SEED:
        e.wait(11 * SEED)            # (another frame: another run of the game's own dice)
    log = lambda s: ctx.log(f"M{n} {s}")
    if PLAYER == "cpu":
        if not d.in_setup():
            # (a mission with no Setup phase is already in the player's first turn: the computer takes the army over and the turn is ended)
            p = e.u32(0x08499598)
            for a in range(1, 5):
                if e.u8(p + 0x3C * a + 0x1B) == 1:
                    e.w8(p + 0x3C * a + 0x1B, 2)
            d.end_turn()
        r = d.autoplay(DAYS, log=log)
    else:
        opts = dict(BOT.get(n, {}))
        if SEED:
            opts["seed"] = SEED
        r = d.play(DAYS, log=log, **opts)
    ctx.log(f"after play: result byte {e.u8(dc.LAST_RESULT)} day {e.u16(dc.DAY)} in_battle {d.in_battle()} main {e.u32(0x03000000):#x}")
    ctx.shot(g, "end")
    units = {}
    for u in g.units():
        units.setdefault(u["army"], []).append(u["type"])
    p = e.u32(0x08499598)
    funds = {a: e.u32(p + 0x3C * a) for a in range(1, 6)}
    row = {"mission": n, "title": es.TITLES[n], "player": PLAYER, "seed": SEED, "result": {1: "won", 2: "lost"}.get(r.get("result"), "none"),
           "days": r.get("days"), "reason": r.get("reason"), "units": {a: len(v) for a, v in units.items()}, "funds": funds}
    ctx.log(json.dumps(row))
    if OUT:
        with open(OUT, "a") as f:
            f.write(json.dumps(row) + "\n")
    e.close()


def _sim(n):
    def fn(ctx):
        run(ctx, n)
    fn.__name__ = f"es_sim_m{n}"
    test(modes=("ds",))(fn)


for _n in NS:
    _sim(_n)
