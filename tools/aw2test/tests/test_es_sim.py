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
# AW2TEST_ES_SCALE=<percent>: the enemy's strength for a handicap run: only that share of each enemy army's units is deployed (every unit kind thinned alike) and its funds are
# scaled; the largest scale a player still wins at is a measure of how hard the mission is (`aw2dev campaign sim --scale`).
SCALE = int(os.environ.get("AW2TEST_ES_SCALE", "100"))

# The test player's own settings by mission (aw2test.bot.Bot): the cells a mission is won on, a stance, a rush on the HQ.
BOT = {
    1: {"goals": [(15, 4)]},
    2: {"stance": "defend"},
    3: {"goals": [(16, 12)]},
    4: {"goals": [(28, 3)]},
    5: {"goals": [(27, 5), (27, 12), (27, 21)], "rush": True},
    6: {"goals": [(10, 12), (12, 17), (17, 2), (13, 22), (28, 12), (24, 23), (28, 19), (26, 8), (24, 28), (30, 3), (36, 9), (37, 16)]},
    7: {"goals": [(34, 12)]},
    8: {"goals": [(26, 10)]},
    9: {"goals": [(12, 4)]},
    10: {"goals": [(16, 2)]},
    11: {"goals": [(37, 10)]},
    12: {"goals": [(17, 12)]},
    13: {"goals": [(19, 15)]},
    # (M14 storms the camp: Varro's HQ)
    14: {"goals": [(38, 12)]},
    15: {"goals": [(39, 13)]},
    # (M16: hold the line while the computer's waves break on it, then go for the enemy HQs)
    16: [{"stance": "defend", "days": 10, "goals": [(34, 10)], "nearest": True, "hunt": True}, {"goals": [(34, 10), (31, 2)]}],
}


def handicap(ctx, e, g, d, n):
    """Thins the enemy armies (the ones on another team than army 1) to SCALE percent."""
    p = e.u32(0x08499598)
    team = e.u8(p + 0x3C + 0x2A)
    for a in range(2, 5):
        if e.u8(p + 0x3C * a + 0x1B) == 0 or e.u8(p + 0x3C * a + 0x2A) == team:
            continue
        # (the units a mission's rules name stay: M7's flagship, M9's barges)
        units = sorted((u for u in g.units(a) if u["type"] not in {7: (21,), 9: (23,), 15: (21,)}.get(n, ())), key=lambda u: (u["type"], u["y"], u["x"]))
        keep, seen = [], {}
        for u in units:
            k = seen.get(u["type"], 0)
            seen[u["type"]] = k + 1
        # (every kind thinned alike: the units of a kind are dropped evenly)
        per = {}
        for u in units:
            per.setdefault(u["type"], []).append(u)
        gone = 0
        for t, us in per.items():
            want = max(1, round(len(us) * SCALE / 100)) if SCALE > 0 else 0
            drop = len(us) - want
            for i in range(drop):
                d.remove_unit(us[(i * len(us)) // max(drop, 1)])
                gone += 1
        e.w32(p + 0x3C * a, e.u32(p + 0x3C * a) * SCALE // 100)
        ctx.log(f"handicap {SCALE}%: army {a} loses {gone} of {len(units)} units")
    g._units_base = g._players_base = None


def run(ctx, n):
    e, g, d = es.enter(ctx, n)
    if SCALE != 100:
        handicap(ctx, e, g, d, n)
    if SEED:
        e.wait(11 * SEED)            # (another frame: another run of the game's own dice)
    dump = {int(x) for x in os.environ.get("AW2TEST_ES_DUMP", "").split(",") if x}

    def log(t):
        ctx.log(f"M{n} {t}")
        if t.startswith("day ") and int(t.split(":")[0].split()[1]) in {int(x) for x in os.environ.get("AW2TEST_ES_SHOTS", "").split(",") if x}:
            try:
                for k, (cx, cy) in enumerate(((13, 24), (13, 17), (24, 22))):
                    g.goto(cx, cy)
                    e.wait(30)
                    ctx.shot(g, f"day{t.split(':')[0].split()[1]}_{k}")
            except Exception as ex:
                ctx.log(f"(no pictures: {ex})")
        if t.startswith("day ") and int(t.split(":")[0].split()[1]) in dump:
            for a in (1, 2, 3):
                ctx.log(f"M{n}   army {a}: " + " ".join(f"{u['type']}@{u['x']},{u['y']}:{u['hp']}" for u in g.units(a)))

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
        plan = BOT.get(n, {})
        # (a list is phases: each one's options and the days it lasts; the last runs to the end)
        phases = plan if isinstance(plan, list) else [dict(plan, days=DAYS)]
        total, r = 0, None
        for k, ph in enumerate(phases):
            opts = {key: v for key, v in ph.items() if key != "days"}
            opts.setdefault("cap", 42)          # (the campaign's armies are bigger than the bot's default of 20: it keeps buying)
            if SEED:
                opts["seed"] = SEED
            span = DAYS - total if k == len(phases) - 1 else ph.get("days", DAYS)
            r = d.play(span, log=log, **opts)
            total += r.get("days") or span
            if e.u8(dc.LAST_RESULT) or total >= DAYS:
                break
    ctx.log(f"after play: result byte {e.u8(dc.LAST_RESULT)} day {e.u16(dc.DAY)} in_battle {d.in_battle()} main {e.u32(0x03000000):#x}")
    ctx.shot(g, "end")
    units = {}
    for u in g.units():
        units.setdefault(u["army"], []).append(u["type"])
    p = e.u32(0x08499598)
    funds = {a: e.u32(p + 0x3C * a) for a in range(1, 6)}
    row = {"mission": n, "title": es.TITLES[n], "player": PLAYER, "seed": SEED, "scale": SCALE, "result": {1: "won", 2: "lost"}.get(r.get("result"), "none"),
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
