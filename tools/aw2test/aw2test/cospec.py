"""The custom COs' *specification*, read from the data files and the design docs, never from the engine's own numbers (`crate::es_co::bonus`, `crate::crumb::bonus`)
and not from `damage.es_bonus` (the Python mirror of the engine). `aw2dev co verify` plays real battles and compares what the game did with these numbers.

Sources, one per CO:
  Klaus, Aurelia, Cassius, Livia  `tango-gamesupport-aw2/cos/<id>.toml` (d2d / cop / scop `mods`, `income`, `tribute`, `heal`, `stars`, `luck`) and
                                  `docs/ES_CAMPAIGN.md` section 2.1 (which units a class word means); Tag Powers: `cos/tags.toml`
  Crumb                           `crate::crumb` module doc (docs/BH_CAMPAIGN.md 3.9, 4.7c): Rank and File, Ration Run, Gerald's Blessing; Tag Power with Sturm: 115%, 2 stars
  Varro                           the table in the module doc of `crate::es_co` (he has no data file)
  Clone Andy                      Dual Strike's Andy (`crate::co_new`: "Dual Strike's Andy's data under another name"), read from the .nds

A class word of a `mods` line means (docs/ES_CAMPAIGN.md 2.1): `foot` Infantry and Mech; `vehicle` the ground vehicles Recon, APC, Tank, Md. Tank, Megatank, Neotank, Piperunner and Anti-Air
(the Megatank and the Piperunner count as vehicles, not as indirect units: the user's answer); `indirect` Artillery, Rockets, Missiles and the Battleship; `artillery rockets` those two; `naval`
every ship; `all` everything. A power's mods are on top of the day-to-day ones (not on top of the CO Power's), and every power adds the game's own +10% firepower and +10% defence
(AW2's power baseline, the Dual Strike pack's `temp_defence` and `stat`), which `bonus` adds for firepower and the game's player block adds for defence.
"""

import pathlib
import tomllib

REPO = pathlib.Path(__file__).resolve().parents[3]
COS_DIR = REPO / "tango-gamesupport-aw2" / "cos"

IDS = {"andy": 1, "cloneandy": 81, "crumb": 82, "klaus": 86, "aurelia": 87, "cassius": 88, "livia": 89, "varro": 90}
ES4 = ("klaus", "aurelia", "cassius", "livia")

FOOT = {1, 2}
VEHICLE = {3, 4, 5, 6, 7, 8, 9, 14}      # Md. Tank, Megatank, Tank, Recon, APC, Neotank, Piperunner, Anti-Air (docs/ES_CAMPAIGN.md 2.1; the Megatank and the Piperunner are vehicles: the user's answer)
AMBIGUOUS = set()
INDIRECT = {10, 11, 15, 21}              # Artillery, Rockets, Missiles, Battleship
NAVAL = {18, 21, 22, 23, 24, 26}
ALL = set(range(1, 27))
CLASSES = {"all": ALL, "foot": FOOT, "vehicle": VEHICLE, "indirect": INDIRECT, "artillery rockets": {10, 11}, "artillery": {10}, "rockets": {11}, "naval": NAVAL,
           "air": {12, 13, 16, 17, 19, 20}, "direct": ALL - INDIRECT}


class Spec:
    """One CO's numbers: `mods[level]` is a list of {units, attack, defence, move, range, cost}; `luck[level]`; `heal[level]`; `income` percent; `tribute[level]` funds a property."""

    def __init__(self, name, stars, d2d, cop, scop, luck=(10, 10, 10), heal=(0, 0, 0), income=0, tribute=(0, 0, 0), power_names=("", ""), source=""):
        self.name, self.stars, self.luck, self.heal, self.income, self.tribute, self.source = name, stars, tuple(luck), tuple(heal), income, tuple(tribute), source
        self.mods = (d2d, cop, scop)
        self.power_names = power_names

    @property
    def id(self):
        return IDS[self.name]

    def levels(self, mode):
        """The mods in force at power level `mode` (0 none, 1 CO Power, 2 Super Power): day to day plus that power's."""
        return list(self.mods[0]) + (list(self.mods[mode]) if mode else [])

    def sum(self, mode, t, key):
        if t in AMBIGUOUS and any(m["units"] == "vehicle" and m.get(key, 0) for m in self.levels(mode)):
            raise KeyError(f"unit type {t} is not covered by the spec")
        return sum(m.get(key, 0) for m in self.levels(mode) if t in CLASSES[m["units"]])

    def bonus(self, mode, t, which):
        """Firepower (0), defence (1), move (2), range (3) points at power level `mode` for unit type `t`; firepower includes the game's +10 of any power
        (the game adds the +10 defence in the player's block)."""
        key = ("attack", "defence", "move", "range")[which]
        v = self.sum(mode, t, key)
        if which == 0 and mode:
            v += 10
        return v

    def covers(self, t):
        return t not in AMBIGUOUS or not any(m["units"] == "vehicle" for lvl in self.mods for m in lvl)

    def cost_percent(self):
        return sum(m.get("cost", 0) for m in self.mods[0] if m["units"] == "all")


def _toml(name):
    with open(COS_DIR / f"{name}.toml", "rb") as f:
        return tomllib.load(f)


def _from_toml(name):
    d = _toml(name)
    mods = lambda sec: [dict(m) for m in d.get(sec, {}).get("mods", [])]
    stars = (d["stars"]["cop"], d["stars"]["scop"])
    luck = tuple(d.get("luck", [10, 10, 10]))
    heal = (0, 0, d.get("scop", {}).get("heal", 0))
    tribute = (0, d.get("cop", {}).get("tribute", 0), d.get("scop", {}).get("tribute", 0))
    return Spec(name, stars, mods("d2d"), mods("cop"), mods("scop"), luck=luck, heal=heal, income=d.get("d2d", {}).get("income", 0), tribute=tribute,
                power_names=(d["cop"]["name"], d["scop"]["name"]), source=f"cos/{name}.toml")


def crumb():
    # crate::crumb module doc: Rank and File +10% attack and defence on Infantry and Mech (and a resupply on his properties), Ration Run: heal 1 HP, resupply, foot +1 move,
    # Gerald's Blessing: heal 2 HP, foot +30% attack on top, luck 0..19% (20), no bad luck. Stars 3 / 6.
    d2d = [{"units": "foot", "attack": 10, "defence": 10}]
    return Spec("crumb", (3, 6), d2d, [{"units": "foot", "move": 1}], [{"units": "foot", "attack": 30}], luck=(10, 10, 20), heal=(0, 1, 2),
                power_names=("Ration Run", "Gerald's Blessing"), source="crate::crumb module doc")


def varro():
    # crate::es_co module doc table: Imperator +15/+15 all; Edict +25 attack +15 defence +1 move; Sol Invictus +45 attack +30 defence +1 move, heal 2. Stars 4 / 8, luck 10 10 20.
    d2d = [{"units": "all", "attack": 15, "defence": 15}]
    return Spec("varro", (4, 8), d2d, [{"units": "all", "attack": 25, "defence": 15, "move": 1}], [{"units": "all", "attack": 45, "defence": 30, "move": 1}],
                luck=(10, 10, 20), heal=(0, 0, 2), power_names=("Edict", "Sol Invictus"), source="crate::es_co module doc")


def andy():
    """The control: Andy has no day-to-day or power mods of his own in the pack (Dual Strike's Andy heals, which `heal` says)."""
    return Spec("andy", (3, 6), [], [], [], heal=(0, 2, 5), power_names=("Hyper Repair", "Hyper Upgrade"), source="Dual Strike (control)")


def cloneandy():
    """Clone Andy is Dual Strike's Andy under another name (crate::co_new): the specification is "same as Andy" -- verified by playing both."""
    return Spec("cloneandy", (3, 6), [], [], [], heal=(0, 2, 5), power_names=("Hyper Repair", "Hyper Upgrade"), source="crate::co_new: Dual Strike's Andy")


def get(name):
    if name == "cloneandy":
        return cloneandy()
    if name == "andy":
        return andy()
    if name in ES4:
        return _from_toml(name)
    if name == "crumb":
        return crumb()
    if name == "varro":
        return varro()
    raise KeyError(name)


def all_specs():
    return {n: get(n) for n in (*ES4, "crumb", "varro")}


# --- Tag Powers (cos/tags.toml) ---------------------------------------------------------------------------------------------------------------

def tags():
    """[{a, b, compat, stars, name}] from cos/tags.toml, plus the Crumb + Sturm pair (crate::crumb / sturm_pairs.rs: 115, 2 stars, "No One Left Behind")."""
    with open(COS_DIR / "tags.toml", "rb") as f:
        pairs = [dict(p) for p in tomllib.load(f)["pair"]]
    pairs.append({"a": "crumb", "b": "aw2:sturm", "compat": 115, "stars": 2, "name": "No One Left Behind"})
    pairs.append({"a": "cloneandy", "b": "aw2:sturm", "compat": 118, "stars": 2, "name": "Perfect Copy"})      # crate::sturm_pairs
    return pairs


AW2_IDS = {"andy": 1, "kanbei": 6, "colin": 16, "sturm": 10}
# Pairs with no entry in tags.toml: the file says "Every unlisted pair is 95" (its header and docs/ES_CAMPAIGN.md 2.3).
UNLISTED_COMPAT = 95
UNLISTED_PAIRS = [("klaus", "aw2:colin"), ("klaus", "aw2:andy"), ("aurelia", "aw2:kanbei"), ("cassius", "aw2:colin"), ("livia", "aw2:kanbei")]


def co_id(ref):
    """A tags.toml reference to the game's CO id."""
    if ref.startswith("aw2:"):
        return AW2_IDS[ref[4:]]
    return IDS[ref]
