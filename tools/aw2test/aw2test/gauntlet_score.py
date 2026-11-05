"""AW2's end-of-battle score as the Gauntlet applies it (crate::gauntlet `POWER_SUM`, `carry_score_*`, crate::gauntlet_mode `par_days`; docs/dev/gauntlet-mode.md "Scoring"), written from the ROM's code
(`0x080263A4` Speed, `0x08026424` Power, `0x080264BC` Technique, `0x08037D80` the rank) for the tests and `aw2dev gauntlet score`.

Speed   = 100 up to the map's par day, then falling to 0 at four times par: 100 - 100 * (day - par) / (3 * par).
Power   = min(100, 1000 * (the most units the player destroyed in one turn) / (the units the enemy armies built)); the Gauntlet divides the enemy sum by the map's lines (rounded up).
Technique (campaign) = clamp(120 - 100 * lost / built, 0, 100); 0 when nothing was built or more was lost than built.
Rank    = C up to 199, B to 249, A to 279, S above."""

import os
import re

from . import paths

SRC = os.path.join(paths.REPO, "tango-gamesupport-aw2", "src", "gauntlet_mode.rs")
RANKS = {2: "C", 3: "B", 4: "A", 5: "S"}
# the par days the maps had before the rework (`m.rank_days = N` in each map's function, in `def()`'s order) and the lines of each map (the selector's enemies)
OLD_PAR = {"gauntlet_01": 24, "gauntlet_02": 40, "gauntlet_03": 22, "gauntlet_04": 22, "gauntlet_05": 26, "gauntlet_06": 40, "gauntlet_07": 40, "gauntlet_08": 24, "gauntlet_09": 24, "gauntlet_10": 26,
           "gauntlet_11": 40, "gauntlet_12": 44}
LINES = {"gauntlet_01": 3, "gauntlet_02": 5, "gauntlet_03": 2, "gauntlet_04": 2, "gauntlet_05": 3, "gauntlet_06": 4, "gauntlet_07": 4, "gauntlet_08": 2, "gauntlet_09": 2, "gauntlet_10": 3,
         "gauntlet_11": 4, "gauntlet_12": 4}
TITLES = {"gauntlet_01": "Cinder Sea", "gauntlet_02": "Iron Crown", "gauntlet_03": "Dustwind Basin", "gauntlet_04": "Brass Canal", "gauntlet_05": "Granite Spine", "gauntlet_06": "Harvest Run",
          "gauntlet_07": "Chrome Meridian", "gauntlet_08": "Tidewater Atoll", "gauntlet_09": "Silverpine Ford", "gauntlet_10": "Neon Row", "gauntlet_11": "Blue Bastion", "gauntlet_12": "Last Eclipse"}


def par_rules():
    """(days per line, {key: override}) as crate::gauntlet_mode declares them."""
    text = open(SRC).read()
    per = int(re.search(r"pub const PAR_PER_LINE: u16 = (\d+);", text).group(1))
    over = dict((k, int(v)) for k, v in re.findall(r'\("(gauntlet_\d+)", (\d+)\)', re.search(r"PAR_OVERRIDES: &\[\(&str, u16\)\] = &\[(.*?)\];", text, re.S).group(1)))
    return per, over


def par(key):
    """The map's par days now."""
    per, over = par_rules()
    return over.get(key, per * LINES[key])


def speed(day, par_days):
    if day <= par_days:
        return 100
    if day >= 4 * par_days:
        return 0
    return 100 - (100 * (day - par_days)) // (3 * par_days)


def power(kills, enemy_built, lines=1):
    enemy = -(-enemy_built // max(lines, 1))
    if enemy == 0:
        return 0
    return min(100, 1000 * kills // enemy)


def technique(built, lost):
    if built == 0 or built < lost:
        return 0
    return max(0, min(100, 120 - 100 * lost // built))


def rank(total):
    return RANKS[2 if total <= 199 else 3 if total <= 249 else 4 if total <= 279 else 5]


# a run, by the lines it fights (n): days taken, the most kills in one turn, the units the enemy built (all lines), the player's units built and lost
SCENARIOS = {
    "quick": lambda n: dict(day=9 * n, kills=3, enemy=30 * n, built=50, lost=10),
    "steady": lambda n: dict(day=14 * n, kills=2, enemy=30 * n, built=60, lost=18),
    "slow": lambda n: dict(day=20 * n, kills=2, enemy=36 * n, built=80, lost=30),
}


def score(run, par_days, lines):
    s, p, t = speed(run["day"], par_days), power(run["kills"], run["enemy"], lines), technique(run["built"], run["lost"])
    return dict(speed=s, power=p, tech=t, total=s + p + t, rank=rank(s + p + t))


def table():
    """[(key, title, lines, old par, new par, {scenario: (old score, new score)})] for every map."""
    rows = []
    for key in sorted(LINES):
        n = LINES[key]
        res = {}
        for name, mk in SCENARIOS.items():
            run = mk(n)
            res[name] = (score(run, OLD_PAR[key], 1), score(run, par(key), n))
        rows.append((key, TITLES[key], n, OLD_PAR[key], par(key), res))
    return rows


def fmt(s):
    return f"{s['total']}{s['rank']}"


def lines():
    out = [f"{'map':16s} {'lines':>5s} {'par old':>7s} {'par new':>7s}  " + "  ".join(f"{n:>13s}" for n in SCENARIOS) + "   (total and rank, old -> new)"]
    for key, title, n, old, new, res in table():
        out.append(f"{title:16s} {n:5d} {old:7d} {new:7d}  " + "  ".join(f"{fmt(res[s][0]) + ' -> ' + fmt(res[s][1]):>13s}" for s in SCENARIOS))
    return out
