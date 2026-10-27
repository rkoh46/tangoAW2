"""Harness scripts for the army-coloured screens (docs/dev/army-packs.md): one function per scenario, each returning the script text for
a list of seat identities (1 Orange Star, 2 Blue Moon, 3 Green Earth, 4 Yellow Comet, 5 Black Hole, 6 the skin) and the names of the shots it takes.

The seats' choices are poked into the room's army page (online_teams `SEL`, seat s colour at 0x0203CB11 + 0x10 s); the page turns them into the
game's colours when every seat is READY, so identity 6 is a skin whose colour is the lowest one nobody else has (with [6, 2] that is 1).
"""

SEL = 0x0203CB10


def header(identities, fog=False, five=False, extra=""):
    n = len(identities)
    pokes = "".join(f"poke {SEL + 0x10 * s + 1:08X} {c:02x}\n" for s, c in enumerate(identities))
    picks = "".join(f"press {s} A\nwait 20\n" for s in range(n))
    ready = "".join(f"press {s} DOWN\npress {s} DOWN\npress {s} DOWN\npress {s} A\n" for s in reversed(range(n)))
    return (
        f"n {n}\n"
        + ("until maparmies=5 100\n" if five else "until selectmap 100\n")
        + "wait 60\n"
        + picks
        + "until teams 100\nwait 90\n"
        + pokes
        + extra
        + "wait 10\n"
        + ready
        + "wait 300\n"
        + ("" if fog else "press 0 DOWN\n")
        + "wait 10\npress 0 A\nuntil battle 300\nuntil army=1 60\nwait 400\n"
    )


def redraw(cell):
    """The game draws units placed by the test aid once the map has been redrawn: open and close the map menu."""
    x, y = cell
    return f"wait 20\ngoto 0 {x} {y}\nwait 10\npress 0 A\nwait 30\npress 0 B\nwait 20\n"


# name -> (identities, description, shots, body builder)
SCENARIOS = {}


def scenario(name, ids, what, shots, seats_five=False, fog=False, ds=False, extra="", compare=None, look=False, sheet_only=False, crest=None, no_plume=False, keep_other=False, crest_boxes=None, gold=None):
    """`crest`: {shot: at least this many pixels of the skin's crest red} (the plume of the battle figures and the portraits); `look`: the shots are the real app's pictures with the Dual Strike tilt (`look.py`), not harness frames; `sheet_only`: left out of `check --live`."""
    def wrap(fn):
        SCENARIOS[name] = dict(ids=ids, what=what, shots=shots, five=seats_five, fog=fog, ds=ds, extra=extra, compare=compare, look=look, sheet_only=sheet_only, crest=crest or {}, no_plume=no_plume, keep_other=keep_other, crest_boxes=crest_boxes or {}, gold=gold or {}, body=fn)
        return fn
    return wrap


@scenario("units", [6, 2], "idle, done and moving units, the cursor panel, the build menu, the HQ and a city", ["units", "done", "hq", "build", "build_mech", "panel"], crest={"units": 10, "build": 25, "build_mech": 25})
def units():
    return (
        "aid unit 1 inf 8 4\naid unit 1 mech 9 4\naid unit 1 tank 8 5\naid unit 1 recon 10 5\naid unit 2 inf 7 4\naid unit 2 tank 6 5\n"
        + redraw((8, 4))
        + "shot units 0\nshot panel 0\n"
        + "aid done 9 4\naid done 10 5\n"
        + redraw((8, 4))
        + "shot done 0\n"
        + "goto 0 1 7\nwait 30\nshot hq 0\n"
        + "goto 0 1 6\nwait 10\npress 0 A\nwait 40\nshot build 0\npress 0 DOWN\nwait 20\nshot build_mech 0\npress 0 B\nwait 20\n"
    )


KINDS = [1, 2, 3, 5, 6, 7, 8, 10, 11, 14, 15, 16, 17, 19, 20, 21, 22, 23, 24]   # AW2's units (0x04, 0x09, 0x0C, 0x0D, 0x12, 0x1A, 0x1B are Dual Strike's)
DS_KINDS = [4, 9, 12, 13, 18, 26, 27]


@scenario("parade", [6, 2], "every unit of the army, idle and done (Dual Strike's too with the pack)", ["parade", "parade_done"])
def parade(kinds=None):
    kinds = kinds or KINDS
    rows = [kinds[i:i + 15] for i in range(0, len(kinds), 15)]
    body = ""
    for r, row in enumerate(rows):
        for x, k in enumerate(row):
            body += f"aid unit 1 {k} {x} {4 + r}\n"
    body += redraw((7, 0)) + "shot parade 0\n"
    for r, row in enumerate(rows):
        for x, k in enumerate(row):
            body += f"aid done {x} {4 + r}\n"
    body += redraw((7, 0)) + "shot parade_done 0\n"
    return body


@scenario("battle", [6, 2], "a battle scene (the army attacks): the figures wear the skin's plumed helmet", ["scene1", "scene2", "scene3"], crest={"scene1": 15, "scene2": 80, "scene3": 80})
def battle():
    return (
        "aid unit 1 inf 8 4\naid unit 2 inf 7 4\n"
        + redraw((8, 4))
        + "press 0 A\nwait 30\npress 0 A\nwait 30\npress 0 A\nwait 20\npress 0 A\nwait 40\nshot scene1 0\nwait 60\nshot scene2 0\nwait 60\nshot scene3 0\n"
    )


TERRAIN = {"plains": 1, "mountain": 3, "wood": 4, "city": 6}


def _battle_pair(att, dfn, att_terrain, dfn_terrain):
    """Army 1 (at 8,4) attacks army 2 (at 7,4), each on its terrain (the scene's background and the figures' loading differ by terrain)."""
    return (
        f"aid unit 1 {att} 8 4\naid unit 2 {dfn} 7 4\n"
        + f"terrain 8 4 {TERRAIN[att_terrain]}\nterrain 7 4 {TERRAIN[dfn_terrain]}\n"
        + redraw((8, 4))
        + "press 0 A\nwait 30\npress 0 A\nwait 30\npress 0 A\nwait 20\npress 0 A\nwait 40\nshot scene1 0\nwait 60\nshot scene2 0\nwait 60\nshot scene3 0\n"
    )


# every pairing: who attacks (the skin's army, or Black Hole against it), the units and the two terrains: only the skin's own soldiers wear the plumed helmet
BATTLES = []
for _who, _ids in (("es", [6, 5]), ("bh", [5, 6])):
    for _att, _dfn, _ta, _td in (
        ("inf", "inf", "plains", "plains"),
        ("inf", "inf", "mountain", "city"),
        ("inf", "inf", "city", "mountain"),
        ("inf", "inf", "wood", "plains"),
        ("mech", "inf", "plains", "plains"),
        ("inf", "mech", "plains", "plains"),
    ):
        _name = f"bt_{_who}_{_att}_{_dfn}_{_ta}_{_td}"
        BATTLES.append(_name)
        _text = f"a battle scene, {'the skin attacks Black Hole' if _who == 'es' else 'Black Hole attacks the skin'}: {_att} on {_ta} against {_dfn} on {_td}; only the skin's soldiers wear the plumed helmet (the user's leak: Black Hole's wore it)"
        scenario(_name, _ids, _text, ["scene1", "scene2", "scene3"], no_plume=True, crest={"scene2": 40, "scene3": 40})(
            lambda a=_att, d=_dfn, ta=_ta, td=_td: _battle_pair(a, d, ta, td)
        )


@scenario("battle_mech", [6, 2], "a Mech attacking a Tank: the bazooka frames of the battle scene", ["scene1", "scene2", "scene3"], crest={"scene1": 15, "scene2": 80, "scene3": 80})
def battle_mech():
    return (
        "aid unit 1 mech 8 4\naid unit 2 tank 7 4\n"
        + redraw((8, 4))
        + "press 0 A\nwait 30\npress 0 A\nwait 30\npress 0 A\nwait 20\npress 0 A\nwait 40\nshot scene1 0\nwait 60\nshot scene2 0\nwait 60\nshot scene3 0\n"
    )


@scenario("power", [6, 2], "the CO power: menu, dialogue and the map after", ["power_menu", "power_say", "power_after"])
def power():
    return (
        "aid unit 1 inf 8 4\naid meter 1 100\nwait 5\n"
        + redraw((5, 2))
        + "press 0 A\nwait 60\npress 0 DOWN\nwait 10\npress 0 DOWN\nwait 10\nshot power_menu 0\npress 0 A\nwait 60\nshot power_say 0\nwait 700\nshot power_after 0\n"
    )


@scenario("copage", [6, 2], "the CO page (map menu > CO) of the skin's army, unit chart: Infantry and Mech are the skin's soldiers (the chart copies only the game's own slots to VRAM; the skin's slots 52+ were garbage)", ["chart"], crest={"chart": 8}, crest_boxes={"chart": [((16, 38, 40, 60), 4), ((64, 38, 90, 60), 4)]})
def copage():
    return (
        "aid unit 1 inf 8 4\naid unit 1 mech 9 4\naid unit 2 inf 7 4\n"
        + redraw((5, 2))
        + "press 0 A\nwait 30\nshot menu 0\npress 0 A\nwait 90\nshot page1 0\n"
        + "press 0 DOWN\nwait 60\npress 0 DOWN\nwait 60\npress 0 DOWN\nwait 60\nshot page4 0\npress 0 DOWN\nwait 60\nshot chart 0\n"
    )


PROPERTIES = {"city": 6, "hq": 8, "airport": 10, "port": 11, "base": 14, "lab": 20}


def _capture(kind, owner):
    """Army 1's Infantry (8,4) captures the property under it (`kind`, owned by army `owner`, 0 neutral): the capture box shows the capturer's soldier and the
    property in its owner's colours. (An HQ is taken in one go with the points set: the box shows before the victory.)"""
    return (
        "aid unit 1 inf 8 4\n"
        + (f"aid capture 8 4 10\n" if kind == "hq" else "")
        + f"terrain 8 4 {PROPERTIES[kind]} {owner}\n"
        + redraw((8, 4))
        + "press 0 A\nwait 20\npress 0 A\nwait 20\npress 0 A\nwait 14\nshot capture1 0\nwait 20\nshot capture2 0\nwait 40\nshot capture3 0\n"
    )


@scenario("capture", [6, 2], "the skin's Infantry captures a neutral city: the capture box's soldier and city wear the skin's colours", ["capture1", "capture2", "capture3"], crest={"capture1": 6, "capture3": 6})
def capture():
    return _capture("city", 0)


CAPTURES = []
for _kind in PROPERTIES:
    for _dir, _ids, _text in (
        ("from_es", [5, 6], "Black Hole's Infantry captures the skin's {k}: the box's {k} is the skin's (its old owner) and the soldier is Black Hole's"),
        ("from_bh", [6, 5], "the skin's Infantry captures Black Hole's {k}: the box shows the skin's soldier and Black Hole's {k}"),
    ):
        _name = f"capture_{_dir}_{_kind}"
        CAPTURES.append(_name)
        _extra = {}
        if _dir == "from_bh":
            _extra["crest"] = {"capture1": 6, "capture3": 6}   # the skin's soldier wears the plume
        if _dir == "from_es" and _kind == "hq":
            _extra["gold"] = {"capture1": 3, "capture3": 3}    # the skin's domed HQ has its gold
        scenario(_name, _ids, _text.format(k=_kind), ["capture1", "capture2", "capture3"], keep_other=True, **_extra)(lambda k=_kind: _capture(k, 2))


@scenario("turn", [6, 2], "ending the turn: the NEXT TURN hand-off and the DAY banner of the next army", ["endturn", "nextturn", "day"])
def turn():
    return (
        "aid unit 1 inf 8 4\n"
        + redraw((3, 3))
        + "press 0 A\nwait 30\npress 0 UP\nwait 10\nshot endturn 0\npress 0 A\nwait 30\npress 0 A\nwait 100\nshot nextturn 0\nwait 100\nshot nextturn 1\npress 1 A\nwait 40\nshot day 0\n"
    )


@scenario("results", [6, 2], "the army's defeat: its VICTORY / DEFEAT screens", ["defeat", "victory"])
def results():
    return (
        redraw((3, 3))
        + "press 0 A\nwait 40\npress 0 DOWN\nwait 10\npress 0 DOWN\nwait 10\npress 0 A\nwait 40\npress 0 DOWN\nwait 10\npress 0 A\nwait 200\npress 0 LEFT\nwait 20\npress 0 A\nwait 20\n"
        + "waitfor victory 60\nshot defeat 0\nshot victory 1\n"
    )


@scenario("teams", [6, 2], "the Teams screen (SELECT YOUR ARMY) with the skin: its emblem and chip at actual size", ["teams"], extra="wait 40\nshot teams 0\nwait 5\nshot teams1 1\n")
def teams():
    return ""


@scenario("rematch", [6, 2], "the room's next match on the same console: the first had the skin, the second has Orange Star and Blue Moon and must look exactly as if there had been no skin before", ["rematch"], compare="rematch")
def rematch():
    second = [1, 2]
    pokes = "".join(f"poke {SEL + 0x10 * s_ + 1:08X} {c:02x}\n" for s_, c in enumerate(second))
    ready = "".join(f"press {s_} DOWN\npress {s_} DOWN\npress {s_} DOWN\npress {s_} A\n" for s_ in reversed(range(2)))
    return (
        redraw((3, 3))
        + "press 0 A\nwait 40\npress 0 DOWN\nwait 10\npress 0 DOWN\nwait 10\npress 0 A\nwait 40\npress 0 DOWN\nwait 10\npress 0 A\nwait 200\npress 0 LEFT\nwait 20\npress 0 A\nwait 20\n"
        + "waitfor victory 60\nwait 100\nwaitfor selectmap 120 pressA 0,1\nwait 60\npress 0 A\nwait 20\npress 1 A\nwait 20\nuntil teams 100\nwait 90\n"
        + pokes + "wait 10\n" + ready + "wait 300\npress 0 DOWN\nwait 10\npress 0 A\nuntil battle 300\nuntil army=1 60\nwait 400\n"
        + "aid unit 1 inf 8 4\naid unit 1 mech 9 4\naid unit 2 inf 7 4\n"
        + redraw((8, 4)) + "shot rematch 0\n"
    )


@scenario("lost3p", [6, 2, 3], "a three-army match: the skin's army yields and the game says it has lost", ["lost_msg"])
def lost3p():
    return (
        redraw((3, 3))
        + "press 0 A\nwait 40\npress 0 DOWN\nwait 10\npress 0 DOWN\nwait 10\npress 0 A\nwait 40\npress 0 DOWN\nwait 10\npress 0 A\nwait 200\npress 0 LEFT\nwait 20\npress 0 A\nwait 60\nshot lost_msg 1\n"
    )


@scenario("dsunits", [6, 2], "Dual Strike's units (with the pack): the map, the build menu's picture and a battle scene", ["ds_parade", "ds_build", "ds_scene1", "ds_scene2"], ds=True)
def dsunits():
    body = ""
    for x, k in enumerate(DS_KINDS):
        body += f"aid unit 1 {k} {x} 4\n"
    body += "aid unit 1 4 8 6\naid unit 2 inf 7 6\n"
    body += redraw((7, 0)) + "shot ds_parade 0\n"
    body += "goto 0 1 6\nwait 10\npress 0 A\nwait 40\n" + "press 0 DOWN\nwait 5\n" * 6 + "wait 20\nshot ds_build 0\npress 0 B\nwait 20\n"
    body += "goto 0 8 6\nwait 10\npress 0 A\nwait 30\npress 0 A\nwait 30\npress 0 A\nwait 20\npress 0 A\nwait 40\nshot ds_scene1 0\nwait 80\nshot ds_scene2 0\n"
    return body


# Crumb is index 26 of the Teams screen's CO list with the Dual Strike pack (`aw2dev harness --ds` with the `cos` command lists it); seat 0's CO is
# the first byte of its selector (0x0203CB10). His HQ is the skin's, a placeholder for one of his own.
@scenario("crumb", [1, 2], "Crumb leads Orange Star (no skin on): his HQ is Black Hole's tower (with the Dual Strike pack)", ["crumb_hq", "crumb_map"], ds=True, extra="poke 0203CB10 1a\n", sheet_only=True)   # (no skin on: Orange Star's own colours are right there)
def crumb():
    return "goto 0 1 7\nwait 40\nshot crumb_hq 0\ngoto 0 8 5\nwait 30\nshot crumb_map 0\n"


@scenario("map5p", [1, 6, 3, 4, 5], "a five-army map: the skin with Green Earth and Black Hole on the same map", ["map5", "map5_far"], seats_five=True)
def map5p():
    return (
        "aid unit 2 inf 8 17\naid unit 2 mech 10 17\naid unit 3 inf 12 17\naid unit 5 inf 9 17\naid unit 5 mech 11 17\n"
        + redraw((9, 19))
        + "shot map5 0\ngoto 0 3 3\nwait 60\nshot map5_far 0\n"
    )


@scenario("hqs", [1, 6, 3, 4, 5], "the five-army map's five HQs on the map: Orange Star's, Emerald Sun's, Black Hole's, Green Earth's, Yellow Comet's (depth and scale beside each other)",
          ["hq_os", "hq_es", "hq_bh", "hq_ge", "hq_yc"], seats_five=True)
def hqs():
    body = ""
    # the map's HQs (the harness `hq` command lists them): column 9 at rows 2 (army 1), 10 (army 2), 19 (army 5), 29 (army 3), 37 (army 4)
    for shot_name, y in (("hq_os", 2), ("hq_es", 10), ("hq_bh", 19), ("hq_ge", 29), ("hq_yc", 37)):
        body += f"goto 0 12 {y + 1}\nwait 50\nshot {shot_name} 0\n"
    return body


@scenario("tilt", [6, 2], "the Dual Strike tilted map (pack; the app's own picture through the AI debug channel): the skin's idle and done units, properties and HQ in the tilt",
          ["tilt"], ds=True, look=True)
def tilt():
    return (
        "aid unit 1 inf 8 4\naid unit 1 mech 9 4\naid unit 1 tank 8 5\naid unit 1 recon 10 5\naid unit 2 inf 7 4\naid unit 2 tank 6 5\n"
        + redraw((8, 4))
        + "aid done 9 4\naid done 10 5\n"
        + redraw((6, 6))
        + "goto 0 3 7\nwait 40\n"
    )


@scenario("tilt5p", [1, 6, 3, 4, 5], "the Dual Strike tilted map on the five-army map: the skin beside Green Earth and Black Hole (for the sheet)", ["tilt5p"], seats_five=True, ds=True, look=True, sheet_only=True)
def tilt5p():
    return "aid unit 2 inf 8 17\naid unit 2 mech 10 17\naid unit 3 inf 12 17\naid unit 5 inf 9 17\naid unit 5 mech 11 17\n" + redraw((9, 19))


def script(name, identities=None, fog=None, vram=False, checkpoint=None):
    """The harness script; with `vram` every shot also dumps its video memory (NAME.vram: palettes, tiles, OAM)."""
    sc = SCENARIOS[name]
    ids = identities or sc["ids"]
    text = header(ids, fog=sc["fog"] if fog is None else fog, five=sc["five"], extra=sc["extra"]) + sc["body"]()
    if checkpoint:
        text += f"checkpoint save {checkpoint}\n"
    if vram:
        text = "".join(l + ("vram " + l.split()[1] + "\n" if l.startswith("shot ") else "") for l in text.splitlines(True))
    return text
