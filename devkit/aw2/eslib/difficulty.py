"""The difficulty score of an Emerald Sun mission: how hard it is to beat, from numbers a designer can read.

Static (from the mission report and the map): the enemy's start force against the player's (unit prices, as the games' own damage-to-cost sense), the
reinforcements by day 10, the production and income on each side (properties that earn, bases, the funds given), the share of the enemy's guns that hold
(fortified), the lanes (how many the enemy attacks through is read from the number of enemy armies and its production kinds). Dynamic (from the sim, `aw2dev
campaign sim`): the CPU-vs-CPU win rate of the player's side over seeds, the days the test player needs to win, the share of its force it loses.

    score = 100 * (0.35 * force + 0.20 * economy + 0.10 * fortified + 0.10 * pressure) / 0.75 (static, 0..~100)  [+ dynamic part when sims exist]

where force = enemy start + reinforcement value over the player's, economy = (enemy funds + 10 days' income) over the player's, fortified = the share of the enemy's
indirect and anti-air that hold, pressure = enemy armies' production kinds (ground, air, sea) over 3. Each ratio is mapped with `r / (1 + r)` so a mission
twice as heavy scores about twice a mission as heavy as the player's. `dynamic` = 100 * (1 - win rate) blended 50 / 50 with min(days / 20, 1) * 100 where
the test player won; both only with sim results.
"""
import json
from . import report

INDIRECT = {10, 11, 15, 14}


def side(d, team_of_player):
    """(player armies, enemy armies) by team."""
    mine = [a["n"] for a in d["armies"] if a["team"] == team_of_player]
    foes = [a["n"] for a in d["armies"] if a["team"] != team_of_player]
    return mine, foes


def numbers(d):
    mine, foes = side(d, d["armies"][0]["team"])
    # a five-army map's player is the fifth: not used by Emerald Sun (the player is army 1)
    pv = sum(report.value(d["units"][a]) for a in mine) + sum(report.spawn_value(d, a, 10) for a in mine)
    ev = sum(report.value(d["units"][a]) for a in foes) + sum(report.spawn_value(d, a, 10) for a in foes)
    funds = {a["n"]: max(a["funds"], 0) for a in d["armies"]}
    inc = lambda armies: sum(d["owned"].get(a, 0) for a in armies) * 1000
    pe = sum(funds[a] for a in mine) + 10 * inc(mine)
    ee = sum(funds[a] for a in foes) + 10 * inc(foes)
    held = sum(d["hold"].get(a, 0) for a in foes)
    guns = sum(sum(1 for k in d["units"][a] for _ in range(d["units"][a][k]) if k in INDIRECT) for a in foes) or 1
    holding_guns = held and min(1.0, held / max(1, sum(d["units"][a].total() for a in foes)) * 2)
    kinds = set()
    for a in foes:
        for k, n in d["units"][a].items():
            kinds.add("air" if k in (16, 17, 19, 20) else "sea" if k in (21, 22, 23, 24, 26) else "ground")
    return {"player_value": pv, "enemy_value": ev, "force": ev / max(pv, 1), "player_econ": pe, "enemy_econ": ee, "economy": ee / max(pe, 1),
            "fortified": round(holding_guns, 2), "pressure": len(kinds) / 3.0, "enemy_armies": len(foes),
            "player_income": inc(mine), "enemy_income": inc(foes)}


def squash(r):
    return r / (1.0 + r)


def static_score(n):
    s = 0.35 * squash(n["force"]) + 0.20 * squash(n["economy"]) + 0.10 * n["fortified"] + 0.10 * n["pressure"]
    return round(100 * s / 0.75, 1)


def dynamic_score(runs):
    """runs: sim result rows of one mission (`campaign sim`)."""
    # (a handicap run, `campaign sim --scale`, plays a weaker enemy: it measures something else and stays out of the score)
    runs = [r for r in (runs or []) if r.get("scale", 100) == 100]
    if not runs:
        return None
    bot = [r for r in runs if r["player"] == "bot"]
    cpu = [r for r in runs if r["player"] == "cpu"]
    parts = []
    if cpu:
        win = sum(1 for r in cpu if r["result"] == "won") / len(cpu)
        parts.append(100 * (1 - win))
    if bot:
        won = [r for r in bot if r["result"] == "won"]
        if won:
            parts.append(min(sum(r["days"] for r in won) / len(won) / 20, 1) * 100)
        else:
            parts.append(100)
    return round(sum(parts) / len(parts), 1)


def load_runs(path):
    out = {}
    try:
        for line in open(path):
            r = json.loads(line)
            out.setdefault(r["mission"], []).append(r)
    except OSError:
        pass
    return out
