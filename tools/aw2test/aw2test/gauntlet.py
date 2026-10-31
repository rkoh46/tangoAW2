"""Driving the Gauntlet mode (crate::gauntlet, docs/dev/gauntlet-mode.md): Select Mode's GAUNTLET entry, the CO pick, the battle on the Gauntlet's first map (Cinder Sea), a win by the
mode's own captures, a loss, the record in Flash slot 13 and a run saved halfway and continued."""

import os
import struct

from . import dscampaign as dc
from . import saves
from .bhcampaign import BhCampaign
from .game import NavError

SOURCE = 0x0203FD57               # crate::ds_campaign::SOURCE (4: the Gauntlet's)
GAUNTLET = 4
PICKED, CONTINUING = 0x0203FD54, 0x0203FD55   # crate::gauntlet
MAGIC = b"AWGA"
SLOT, OFFSET, MID_SLOT = 13, 0x240, 12      # the record follows BH's (0) and BH2's (0x120) in slot 13; a run saved halfway shares slot 12 (tag 4 << 5)
RECORD_LEN = 0x120
WHEEL_LAST = 0x03005934           # the wheel's remembered position
ITEM_TABLE_POOL = 0x080814F0       # a word of the wheel's code that points at its item table
GAME_TABLE, PACK_TABLE = 0x0861696C, 0x08E40000   # AW2's six-item table; tangoAW2's eight-item one (crate::mode_menu)

# crate::gauntlet_ui::STATE: the map selector (step 1) and the colour pick (step 2)
UI = 0x0203D080
UI_STEP, UI_ANSWER, UI_MAP_CURSOR, UI_MAP, UI_COLOUR_CURSOR = UI, UI + 1, UI + 2, UI + 3, UI + 4
SELECTOR, COLOURS = 1, 2
PLAYER_COLOUR = lambda g: g.player(1)["colour"]   # (the player's army record's colour byte)
# the army codes of the Teams screen (crate::army_skin::SKIN: 6 is Emerald Sun) and AW2's colour bytes
ORANGE_STAR, BLUE_MOON, GREEN_EARTH, YELLOW_COMET, BLACK_HOLE, EMERALD_SUN = 1, 2, 3, 4, 5, 6
CINDER_FREE = [ORANGE_STAR, BLUE_MOON, EMERALD_SUN]   # AW2's five minus Cinder Sea's enemies (Green Earth, Yellow Comet, Black Hole), then the skin
CINDER_ENEMY_COLOURS = [GREEN_EARTH, YELLOW_COMET, BLACK_HOLE]

UI_SHOWN = UI + 0x20          # what the step shows: +0 maps listed, +1 enemies, +2.. (CO, colour) pairs, +0x0E free count, +0x0F.. free army codes
HOSTS = 0x0203C500            # crate::army_skin::STATE: the colour each skin sits on (0 none)


def shown(e):
    """What the selector (the highlighted map) or the colour pick (the map picked) offers: (maps, [(co, colour)] in order, [free army codes])."""
    b = e.read(UI_SHOWN, 0x17)
    return b[0], [(b[2 + 2 * k], b[3 + 2 * k]) for k in range(b[1])], list(b[0x0F:0x0F + b[0x0E]])


# crate::gauntlet_mode (Cinder Sea): the HQs and the enemy COs in order
CINDER = {"player": (3, 18), "drake": (27, 18), "sensei": (3, 3), "hawke": (29, 3)}
ENEMIES = ["Drake", "Sensei", "Hawke"]
TITLE = "Cinder Sea"
# crate::gauntlet_mode (Iron Crown, map 2, mission 1: `TANGOAW2_GAUNTLET_MAP=1` starts it): the player is the fifth army; the lines in order; stage two is Asuka's Keep
IRON = {"player": (4, 22), "grit": (8, 9), "jess": (24, 5), "kanbei": (34, 6), "rachel": (30, 20)}
IRON_ORDER = [("grit", 1, "Grit", 2), ("jess", 2, "Jess", 3), ("kanbei", 3, "Kanbei", 4), ("rachel", 4, "Rachel", None)]   # (HQ key, its army, CO, the army it brings)
KEEP_ASUKA = (22, 5)
MAP2 = 1                           # the selector's second entry (mission 1)
SKIN_STATE = 0x0203C500             # crate::army_skin::STATE: +0 the colour (1..5) skin 0 (Emerald Sun) sits on
STAGE_AT = 0x0203DCA0               # crate::ram_map::STAGE: +0 the stage the battle is on

# AW2 CO ids (crate::co_new, crate::es_co): the pick any CO can be
ANDY, MAX, SAMI, KANBEI, JAVIER, CLONE_ANDY, CRUMB, KLAUS, AURELIA, CASSIUS, LIVIA, ASUKA, ARIA = 1, 2, 4, 6, 77, 81, 82, 86, 87, 88, 89, 92, 93
EVERY_CO = 36                      # crate::gauntlet_mode::ROSTER


class Gauntlet(BhCampaign):
    """The BH Campaign's driver (CO screen, Setup, dialogue helpers) on the Gauntlet's entry."""
    picks = {0: 1}

    def total_picks(self):
        return 1

    def step(self):
        return self.e.u8(UI_STEP)

    def wait_step(self, step, frames=1500):
        if not self.e.wait_until(lambda: self.step() == step, frames, step=10):
            raise NavError(f"the Gauntlet's step {step} did not come up (step {self.step()})")
        self.e.wait(12)

    def open(self, from_title=True, pick=True, map=0):
        """Select Mode's GAUNTLET, A: the map selector (the mode starts at once: no box, no world map); with `pick` A takes the highlighted map and the CO screen follows."""
        e = self.e
        if from_title:
            saves.to_select_mode(e)
        saves.wheel_to(e, "gauntlet")
        e.press("A", 8)
        if pick:
            self.wait_step(SELECTOR)
            for _ in range(map):                # (the selector's list: DOWN to the map)
                e.press("DOWN", 4)
                e.wait(10)
            ctx_ok = e.u8(UI_MAP_CURSOR) == map
            if not ctx_ok:
                raise NavError(f"the selector's cursor is on map {e.u8(UI_MAP_CURSOR)}, not {map}")
            e.press("A", 6)

    def pick_colour(self, code=None, free=None):
        """On the colour pick (it follows the CO screen): move the cursor to the army `code` (None: leave it) and A."""
        e = self.e
        if not e.wait_until(lambda: self.step() == COLOURS, 400, step=10):
            if self.in_battle() or self.scripts_running() or free is not None:       # (a map with one colour free has nothing to pick: the battle follows the CO screen at once)
                return
            raise NavError(f"the Gauntlet's colour pick did not come up (step {self.step()})")
        e.wait(12)
        if code is not None:
            want = (free or CINDER_FREE).index(code)
            for _ in range(8):
                if e.u8(UI_COLOUR_CURSOR) == want:
                    break
                e.press("RIGHT", 4)
                e.wait(8)
        e.press("A", 6)

    def on_co_screen(self):
        return self.on_co_select() and self.co_cursor() is not None

    def wait_co_screen(self, frames=1200):
        if not self.e.wait_until(self.on_co_screen, frames, step=10):
            raise NavError("the Gauntlet's CO screen did not come up")
        self.e.wait(30)

    def start(self, co=ANDY, from_title=True, setup=True, colour=None, map=0):
        """From the title: GAUNTLET, the map (the first), the pick of `co`, the army colour `colour` (an army code; None: the cursor's), the battle's start, Setup left with Deploy, the intro read: the
        player in control on day 1. Returns the CO the screen picked."""
        e, g = self.e, self.g
        self.open(from_title, map=map)
        picked = self.choose_cos(1, prefs=[co])
        self.pick_colour(colour)
        for _ in range(600):
            if self.in_battle() and e.u32(0x0849_9598) != 0:
                break
            e.press("A", 4) if self.scripts_running() else None
            e.wait(10)
        if not self.in_battle():
            raise NavError("the Gauntlet's battle did not load")
        self.leave_setup()
        self.wait_control()
        g._units_base = g._players_base = None
        return picked[0] if picked else None

    def session(self):
        e = self.e
        return {"active": e.u8(dc.ACTIVE), "source": e.u8(SOURCE), "mission": e.u8(dc.MISSION), "map_id": e.u8(dc.MAP_ID),
                "game_mode": e.u8(0x03003FC1)}

    def select_mode_up(self):
        return saves.wheel(self.e) is not None

    def owner(self, cell):
        e = self.e
        row = e.u16(dc.MAP + 0x417A + 2 * cell[1])
        return e.u8(dc.MAP + 0x1432 + row + cell[0]) >> 5

    def counts(self, armies=(1, 2, 3, 4)):
        return {a: len(self.g.units(army=a)) for a in armies}

    def capture(self, ctx, cell, army=1):
        """A fresh Infantry of the player's army on `cell` with one capture point left: the game's own Capture."""
        e, g = self.e, self.g
        g._units_base = g._players_base = None
        inf = next(u for u in g.units(army=army) if u["type"] == 1 and not u["flags"] & 0x08 and (u["x"], u["y"]) != cell)
        occ = g.unit_at(*cell)
        if occ is not None and occ["id"] != inf["id"]:
            self.remove_unit(occ)
        self.place_unit(inf, *cell)
        a = g.unit_addr(inf["id"])
        e.w8(a + 5, (e.u8(a + 5) & 7) | (19 << 3))
        e.wait(4)
        g.select(*cell)
        e.wait(8)
        self.dialogue()
        menu = g.move_to(*cell)
        self.dialogue()
        ctx.require(any(n.lower().startswith("capt") for n in menu["names"]), f"Capture offered at {cell} ({menu['names']})")
        g.choose("Capt", g.ACTION_MENU)
        e.wait(120)

    def settle(self, frames=6000):
        """Through the scenes a fall brings until the player has control again."""
        e, g = self.e, self.g
        for _ in range(frames // 40):
            if self.scripts_running():
                e.press("A", 4)
            e.wait(30)
            if not self.scripts_running() and self.in_battle():
                e.wait(30)
                if not self.scripts_running():
                    break
        self.wait_control()
        g._units_base = g._players_base = None

    def play_to_the_last_line(self, ctx):
        """Drake's HQ and Sensei's are taken in turn (each fall brings the next line: the scene, the line's HQ, its wave), then Hawke's: his HQ's fall leaves the first two lines' survivors on the field.
        Returns [(name, units by army, controllers)] read when the line is in (after the scene), Hawke's right after his HQ fell."""
        seen = []
        for name in ("drake", "sensei", "hawke"):
            self.capture(ctx, CINDER[name])
            if name != "hawke":
                self.settle()
            seen.append((name, self.counts(), self.controllers()))
        return seen

    def win(self, ctx):
        """The whole gauntlet won: the three lines taken; Hawke's fall wins (the survivors of the first two lines need not be hunted)."""
        self.play_to_the_last_line(ctx)
        return self.through_results()

    def through_results(self, frames=8000):
        """A through the scenes, VICTORY or DEFEAT and the results, until Select Mode is up (A is not pressed once it is). Returns the mission's result (1 won, 2 lost)."""
        e = self.e
        n = 0
        while n < frames:
            if self.select_mode_up() and e.u8(dc.ACTIVE) == 0:
                break
            if self.scripts_running() or not self.in_battle():
                if not self.select_mode_up():
                    e.press("A", 4)
            e.wait(14)
            n += 18
        return e.u8(dc.LAST_RESULT)

    def lose(self, ctx):
        """The player's army left one Infantry on 1 HP next to an enemy that hits it, the turn ended: the army falls (AW2's rout)."""
        from . import twofront
        e, g = self.e, self.g
        ctx.require(twofront.force_lose(self), "the player's last unit is put in reach of the enemy")
        g.open_map_menu()
        g.choose("End", g.MAP_MENU)
        return self.through_results()

    # -- the record -----------------------------------------------------------------------------
    def best(self, mission=0):
        """The mission's best result as the session's records hold it: (co, days, score) or None."""
        w = self.e.u32(dc.RECORDS + 8 * mission)
        return None if w == 0 else (w & 0xFF, (w >> 8) & 0xFFF, w >> 20)


def saved_record(img):
    """The Gauntlet's region of slot 13 in a Flash image (bytes, or None)."""
    s = bytes(img.slot(SLOT)) if SLOT in img.tags() else b""
    return s[OFFSET:OFFSET + RECORD_LEN] if s[OFFSET:OFFSET + 4] == MAGIC else None


def record_best(rec, mission=0):
    """(co, days, score) of a record region's mission word, or None (the progress is 0x20 bytes, then 8 bytes a mission)."""
    w = struct.unpack_from("<I", rec, 0x20 + 8 * mission)[0]
    return None if w == 0 else (w & 0xFF, (w >> 8) & 0xFFF, w >> 20)


def wheel_items(e):
    """The wheel's item ids by position: the pack's eight-entry table or AW2's six (read from the ROM image the console runs)."""
    if e.ds:
        t = list(e.read(PACK_TABLE, 8))
        return [t[(p + 2) % 8] for p in range(8)]
    t = list(e.read(GAME_TABLE, 6))
    return [t[(p + 2) % 6] for p in range(6)]
