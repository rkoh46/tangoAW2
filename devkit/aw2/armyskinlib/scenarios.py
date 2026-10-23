"""Harness scripts for the army-coloured screens (docs/dev/army-packs.md): one function per scenario, each returning the script text for
a list of seat identities (1 Orange Star, 2 Blue Moon, 3 Green Earth, 4 Yellow Comet, 5 Black Hole, 6 the skin) and the names of the shots it takes.

The seats' choices are poked into the room's army page (online_teams `SEL`, seat s colour at 0x0203CB11 + 0x10 s); the page turns them into the
game's colours when every seat is READY, so identity 6 is a skin whose colour is the lowest one nobody else has (with [6, 2] that is 1).
"""

SEL = 0x0203CB10


def header(identities, fog=False, five=False):
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


def scenario(name, ids, what, shots, seats_five=False, fog=False, ds=False):
    def wrap(fn):
        SCENARIOS[name] = dict(ids=ids, what=what, shots=shots, five=seats_five, fog=fog, ds=ds, body=fn)
        return fn
    return wrap


@scenario("units", [6, 2], "idle, done and moving units, the cursor panel, the build menu, the HQ and a city", ["units", "done", "hq", "build", "panel"])
def units():
    return (
        "aid unit 1 inf 8 4\naid unit 1 mech 9 4\naid unit 1 tank 8 5\naid unit 1 recon 10 5\naid unit 2 inf 7 4\naid unit 2 tank 6 5\n"
        + redraw((8, 4))
        + "shot units 0\nshot panel 0\n"
        + "aid done 9 4\naid done 10 5\n"
        + redraw((8, 4))
        + "shot done 0\n"
        + "goto 0 1 7\nwait 30\nshot hq 0\n"
        + "goto 0 1 6\nwait 10\npress 0 A\nwait 40\nshot build 0\npress 0 B\nwait 20\n"
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


@scenario("battle", [6, 2], "a battle scene (the army attacks)", ["scene1", "scene2", "scene3"])
def battle():
    return (
        "aid unit 1 inf 8 4\naid unit 2 inf 7 4\n"
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


@scenario("capture", [6, 2], "an Infantry capturing a city (the capture animation and the flag)", ["capture1", "capture2", "capture3"])
def capture():
    return (
        "aid unit 1 inf 8 4\n"
        + redraw((8, 4))
        + "press 0 A\nwait 20\npress 0 A\nwait 20\npress 0 DOWN\nwait 5\npress 0 A\nwait 8\nshot capture1 0\nwait 12\nshot capture2 0\nwait 20\nshot capture3 0\n"
    )


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


@scenario("map5p", [1, 6, 3, 4, 5], "a five-army map: the skin with Green Earth and Black Hole on the same map", ["map5", "map5_far"], seats_five=True)
def map5p():
    return (
        "aid unit 2 inf 8 17\naid unit 2 mech 10 17\naid unit 3 inf 12 17\naid unit 5 inf 9 17\naid unit 5 mech 11 17\n"
        + redraw((9, 19))
        + "shot map5 0\ngoto 0 3 3\nwait 60\nshot map5_far 0\n"
    )


def script(name, identities=None, fog=None, vram=False):
    """The harness script; with `vram` every shot also dumps its video memory (NAME.vram: palettes, tiles, OAM)."""
    sc = SCENARIOS[name]
    ids = identities or sc["ids"]
    text = header(ids, fog=sc["fog"] if fog is None else fog, five=sc["five"]) + sc["body"]()
    if vram:
        text = "".join(l + ("vram " + l.split()[1] + "\n" if l.startswith("shot ") else "") for l in text.splitlines(True))
    return text
