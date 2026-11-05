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
SLOTS, SLOT_LEN, TOP = 32, 0x18, 5          # crate::gauntlet: the top five of up to 32 maps, keyed by the map's id (gauntlet_NN is NN)
TABLE_LEN = SLOTS * SLOT_LEN
RECORD_LEN = 0x20 + TABLE_LEN              # the progress record (version byte at +5: 2), then the table
WHEEL_LAST = 0x03005934           # the wheel's remembered position
ITEM_TABLE_POOL = 0x080814F0       # a word of the wheel's code that points at its item table
GAME_TABLE, PACK_TABLE = 0x0861696C, 0x08E40000   # AW2's six-item table; tangoAW2's eight-item one (crate::mode_menu)

# crate::gauntlet_ui::STATE: the map selector (step 1) and the army screen (step 2); the army screen's CO cursor (an index into the roster) and the CO it is on (an AW2 CO id)
UI = 0x0203D080
UI_STEP, UI_ANSWER, UI_MAP_CURSOR, UI_MAP, UI_COLOUR_CURSOR, UI_CO_CURSOR, UI_CO = UI, UI + 1, UI + 2, UI + 3, UI + 4, UI + 5, UI + 7
SELECTOR, ARMY = 1, 2
PLAYER_COLOUR = lambda g: g.player(1)["colour"]   # (the player's army record's colour byte)
# the army codes of the Teams screen (crate::army_skin::SKIN: 6 is Silver Nova) and AW2's colour bytes
ORANGE_STAR, BLUE_MOON, GREEN_EARTH, YELLOW_COMET, BLACK_HOLE, EMERALD_SUN = 1, 2, 3, 4, 5, 6
CINDER_FREE = [ORANGE_STAR, BLUE_MOON, EMERALD_SUN]   # AW2's five minus Cinder Sea's enemies (Green Earth, Yellow Comet, Black Hole), then the skin
CINDER_ENEMY_COLOURS = [GREEN_EARTH, YELLOW_COMET, BLACK_HOLE]

# the game's SELECT MAP list (crate::five_map::LIST_IDS, LIST_LAST) and its cursor words; the Gauntlet's maps are map-table ids SLOT_IDS (below: crate::gauntlet_ui::SLOT_IDS)
LIST_IDS, LIST_LAST = 0x0203DC24, 0x0203DC24 + 0x6E + 1
LIST_FIRST, LIST_CURSOR_ROW = 0x03005900, 0x03005930
# the map-table ids a list may use, ascending (crate::gauntlet_ui::SLOT_IDS): Survival's 0xC9..0xEF borrowed only by a list of more than twelve maps, then the free 0xF2..0xFD; a list of n maps takes the last n
SLOT_IDS = list(range(0xC9, 0xF0)) + list(range(0xF2, 0xFE))
MAX_MAPS = 32
ROW_BASE = SLOT_IDS[-MAX_MAPS]      # crate::gauntlet_ui::ROW_BASE: the first id the record rows cover
PLAY_ST = 0x03003FC0                # the play state: +1 the game mode (2 while the selector is up: the War Room's), +2 the map id (0 until A)

BLOCK = 0x0203E800                 # crate::gauntlet::BLOCK: the record rows the selector's record box reads, one per map-table id from ROW_BASE to 0xFD, then the top-five table
ROWS = BLOCK
ROW_COUNT = 0xFD - ROW_BASE + 1
TABLE = BLOCK + 0x14 * ROW_COUNT   # crate::gauntlet::TABLE: the table in RAM
UI_SHOWN = UI + 0x20          # what the step shows: +0 maps listed, +1 enemies, +2.. (CO, colour) pairs, +0x0E free count, +0x0F.. free army codes
HOSTS = 0x0203C500            # crate::army_skin::STATE: the colour each skin sits on (0 none)


def shown(e):
    """What the selector (the highlighted map) or the army screen (the map picked) offers: (maps, [(co, colour)] in order, [free army codes])."""
    b = e.read(UI_SHOWN, 0x17)
    return b[0], [(b[2 + 2 * k], b[3 + 2 * k]) for k in range(b[1])], list(b[0x0F:0x0F + b[0x0E]])


# The selector lists the maps by their number of enemy COs, fewest first (crate::gauntlet_mode::order; ties in the definition's order): the missions by row and their names. A map's identity is its
# mission (the record, `Gauntlet.open(map=<mission>)`), never its row.
SELECTOR_ORDER = [2, 3, 7, 8, 0, 4, 9, 5, 6, 10, 11, 1]
# (the names the list shows: a two-map run is listed under `MissionDef::list_title`)
SELECTOR_TITLES = ["Dustwind Basin", "Brass Canal", "Tidewater Atoll", "Silverpine Ford", "Cinder Sea", "Granite Spine", "Neon Row", "Harvest Run", "Chrome Meridian", "Blue Bastion", "Last Eclipse", "Iron Crown 2 maps"]


def list_ids(span=0):
    """The map-table ids the selector lists, in its order: the last n of SLOT_IDS (with `span` more than n, the ids laid out for that many maps, as the app does under the test aid TANGOAW2_GAUNTLET_SLOTS=<span>:
    it borrows Survival's entries)."""
    n = len(SELECTOR_ORDER)
    span = max(n, min(MAX_MAPS, span))
    return SLOT_IDS[len(SLOT_IDS) - span:][:n]

def row_of(mission):
    """The selector's row (and the record row the game reads for it) of the map of this mission."""
    return SELECTOR_ORDER.index(mission)


SELECTOR_ENEMIES = [2, 2, 2, 2, 3, 3, 3, 4, 4, 4, 4, 5]       # the number of enemy COs of each row (never decreasing: fewest first)

# crate::gauntlet_mode (Cinder Sea): the HQs and the enemy COs in order
CINDER = {"player": (3, 18), "drake": (27, 18), "sensei": (3, 3), "hawke": (29, 3)}
ENEMIES = ["Drake", "Sensei", "Hawke"]
TITLE = "Cinder Sea"
# crate::gauntlet_mode (Iron Crown, map 2, mission 1: `TANGOAW2_GAUNTLET_MAP=1` starts it): the player is the fifth army; the lines in order; stage two is Asuka's Keep
IRON = {"player": (4, 22), "grit": (8, 9), "jess": (24, 5), "kanbei": (34, 6), "rachel": (30, 20)}
IRON_ORDER = [("grit", 1, "Grit", 2), ("jess", 2, "Jess", 3), ("kanbei", 3, "Kanbei", 4), ("rachel", 4, "Rachel", None)]   # (HQ key, its army, CO, the army it brings)
KEEP_ASUKA = (22, 5)
MAP2 = 1                           # the selector's second entry (mission 1)
SKIN_STATE = 0x0203C500             # crate::army_skin::STATE: +0 the colour (1..5) skin 0 (Silver Nova) sits on
STAGE_AT = 0x0203DCA0               # crate::ram_map::STAGE: +0 the stage the battle is on

# AW2 CO ids (crate::co_new, crate::es_co): the pick any CO can be
ANDY, MAX, SAMI, KANBEI, JAVIER, CLONE_ANDY, CRUMB, TABITHA, LILI, CAULDER, ASUKA, ARIA = 1, 2, 4, 6, 77, 81, 82, 86, 87, 88, 92, 93
EVERY_CO = 35                      # crate::gauntlet_mode::ROSTER


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
        if step == SELECTOR:
            self.wait_select_map()

    def wait_select_map(self, frames=900):
        """The map selector is the game's own SELECT MAP: it takes the pad once its list is in and its idle loop runs (its fade-in and list take about a hundred frames)."""
        from . import survival as sv
        e = self.e
        if not e.wait_until(lambda: sv.running(e, sv.SELECT_MAP_PROC), frames, step=10):
            raise NavError("the Gauntlet's SELECT MAP did not open")
        e.wait(150)

    def selector_ids(self):
        """The list the screen shows: the map-table ids it holds (crate::five_map::LIST_IDS, up to the last row) and the row under the cursor."""
        e = self.e
        last = e.u8(LIST_LAST)
        ids = list(e.read(LIST_IDS, last + 1))
        return ids, e.u32(LIST_FIRST) + e.u32(LIST_CURSOR_ROW)

    def table(self):
        """The map table the game reads now (the word `0x080196EC` points at its first entry)."""
        return self.e.u32(0x080196EC)

    def entry_name(self, map_id):
        """A map-table entry's name: its text id (+0x14) through the text table (`crate::campaign_model::TEXT_TABLE`)."""
        e = self.e
        text = e.u16(self.table() + 0x5C * map_id + 0x14)
        at = e.u32(0x0861_0A38 + 4 * text)
        out = bytearray()
        while len(out) < 40 and e.u8(at + len(out)):
            out.append(e.u8(at + len(out)))
        return out.decode("latin-1")

    def entry_cos(self, map_id):
        """The COs a map-table entry names per army (header +0x3C..+0x3F, AW2's ids; 0xFF the player's pick): what the screen draws the enemies' faces from."""
        return list(self.e.read(self.table() + 0x5C * map_id + 0x3C, 4))

    def entry_tab(self, map_id):
        return self.e.u16(self.table() + 0x5C * map_id + 0x1A)

    def record_rows(self, span=0):
        """The War Room record rows the screen reads for the Gauntlet's maps (crate::gauntlet_ui::rows): per map five (CO, score) records."""
        b = bytes(self.e.read(ROWS, 0x14 * ROW_COUNT))
        rows = [0x14 * (i - ROW_BASE) for i in list_ids(span)]       # (the game reads the row of the map-table id it lists a map by)
        return [[(b[o + 4 * k], int.from_bytes(b[o + 4 * k + 1:o + 4 * k + 4], "little")) for k in range(5)] for o in rows]

    def open(self, from_title=True, pick=True, map=0, box=None):
        """Select Mode's GAUNTLET, A: with no run saved the map selector (the mode starts at once: no box, no world map); with a run saved AW2's item box (Continue / New) opens: `box="continue"` or
        `"new"` takes that row (Continue resumes the battle: no selector). With `pick` A takes the highlighted map and the army screen follows."""
        e = self.e
        if from_title:
            saves.to_select_mode(e)
        saves.wheel_to(e, "gauntlet")
        e.press("A", 8)
        if box:
            self.choose_in_box(box)
            if box == "continue":
                return
        if pick:
            self.wait_step(SELECTOR)
            # (the selector lists the maps by their number of enemy COs, fewest first, crate::gauntlet_mode::order: DOWN until the cursor is on the mission `map`;
            # the cursor's move takes a moment to settle before it takes A)
            for _ in range(len(SELECTOR_ORDER) + 2):
                if e.u8(UI_MAP_CURSOR) == map:
                    break
                e.press("DOWN", 4)
                e.wait(40)
            if e.u8(UI_MAP_CURSOR) != map:
                raise NavError(f"the selector's cursor is on map {e.u8(UI_MAP_CURSOR)}, not {map}")
            e.press("A", 6)

    def choose_in_box(self, which):
        """The Gauntlet's item box is open (a run is saved): its cursor to the row `which` ("continue": the top row, "new": the bottom) and A."""
        e = self.e
        if not e.wait_until(self.box_open, 120, step=4):
            raise NavError("the Gauntlet's item box did not open")
        e.wait(45)
        self.box_row({"continue": 0, "new": 1}[which])
        e.press("A", 8)

    def wait_army(self, frames=600):
        """The army screen (it follows the selector's A) is up and takes the pad."""
        if not self.e.wait_until(lambda: self.step() == ARMY, frames, step=10):
            raise NavError(f"the Gauntlet's army screen did not come up (step {self.step()})")
        self.e.wait(12)

    def pick_co(self, co):
        """On the army screen: DOWN until the cursor is on `co` (an AW2 CO id); returns the CO it stopped on."""
        e = self.e
        for _ in range(EVERY_CO + 1):
            if e.u8(UI_CO) == co:
                break
            e.press("DOWN", 4)
            e.wait(8)
        return e.u8(UI_CO)

    def pick_colour(self, code):
        """On the army screen: R until the colour cursor is on the army `code` of those the map leaves free; returns the code it stopped on."""
        e = self.e
        free = shown(e)[2]
        for _ in range(len(free) + 1):
            if free[e.u8(UI_COLOUR_CURSOR) % len(free)] == code:
                break
            e.press("R", 4)
            e.wait(8)
        return free[e.u8(UI_COLOUR_CURSOR) % len(free)]

    def pick_army(self, co=None, colour=None):
        """On the army screen: the CO `co` and the army colour `colour` (None: leave the cursor), then A. Returns the CO picked."""
        e = self.e
        self.wait_army()
        if co is not None:
            self.pick_co(co)
        if colour is not None:
            self.pick_colour(colour)
        picked = e.u8(UI_CO)
        e.press("A", 6)
        return picked

    def start(self, co=ANDY, from_title=True, setup=True, colour=None, map=0, box=None):
        """From the title: GAUNTLET, the map (the first), the army screen's CO `co` and army colour `colour` (an army code; None: the cursor's), the battle's start, Setup left with Deploy, the
        intro read: the player in control on day 1. Returns the CO the screen picked."""
        e, g = self.e, self.g
        self.open(from_title, map=map, box=box)
        picked = self.pick_army(co, colour)
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
        return picked

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

    def capture(self, ctx, cell, army=1, snap=None):
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
        if snap:                        # (the capture box's frames: `snap(k)` every few frames while it plays)
            for k in range(24):
                snap(k)
                e.wait(6)
        e.wait(120)

    def settle(self, frames=6000):
        """Through the scenes a fall brings until the player has control again."""
        e, g = self.e, self.g
        for _ in range(frames // 40):
            if self.scripts_running():
                e.press("A", 4)
            e.wait(30)
            # (a rout's explosions run as procs between the scripts: the map is idle only once they are over)
            if not self.scripts_running() and self.in_battle() and g.idle():
                e.wait(30)
                if not self.scripts_running() and g.idle():
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

    def results(self, map_id=1):
        """The map's five results as the session's table holds them, best first: [(co, days, score)] (empty places left out)."""
        return table_results(bytes(self.e.read(TABLE, TABLE_LEN)), map_id)

    def put_results(self, map_id, results):
        """Writes the map's results [(co, days, score)] (best first) into the session's table, as a record made earlier (for the selector's pictures)."""
        t = bytearray(self.e.read(TABLE, TABLE_LEN))
        s = next((k for k in range(SLOTS) if t[k * SLOT_LEN] == map_id), next((k for k in range(SLOTS) if t[k * SLOT_LEN] == 0), None))
        t[s * SLOT_LEN] = map_id
        for k in range(TOP):
            w = encode(*results[k]) if k < len(results) else 0
            struct.pack_into("<I", t, s * SLOT_LEN + 4 + 4 * k, w)
        self.e.write(TABLE, bytes(t))


def saved_record(img):
    """The Gauntlet's region of slot 13 in a Flash image (bytes, or None)."""
    s = bytes(img.slot(SLOT)) if SLOT in img.tags() else b""
    return s[OFFSET:OFFSET + RECORD_LEN] if s[OFFSET:OFFSET + 4] == MAGIC else None


def encode(co, days, score):
    return co | days << 8 | score << 20


def decode(w):
    return None if w == 0 else (w & 0xFF, (w >> 8) & 0xFFF, w >> 20)


def table_results(t, map_id):
    """A map's results in a table (the saved one, or RAM's): [(co, days, score)] best first, empty places left out."""
    for k in range(SLOTS):
        if t[k * SLOT_LEN] == map_id:
            ws = struct.unpack_from("<5I", t, k * SLOT_LEN + 4)
            return [decode(w) for w in ws if w]
    return []


def record_results(rec, map_id=1):
    """A saved record region's results of a map (id 1 is Cinder Sea): best first."""
    return table_results(rec[0x20:], map_id)


def record_best(rec, map_id=1):
    """(co, days, score) of a map's first place in a saved record region, or None."""
    r = record_results(rec, map_id)
    return r[0] if r else None


def war_room_place(results, days, score):
    """Where the War Room puts a new result among a map's five (read from `InsertBestScoreRecord` at 0x08017760, written again here from the code, not from crate::gauntlet): past every record
    with a higher score, and past those with the same score and no more days. 5: below all five."""
    for k, (co, d, sc) in enumerate(results):
        if sc < score or (sc == score and d > days):
            return k
    return len(results)


def war_room_insert(results, entry):
    """The map's results [(co, days, score)] with `entry` inserted the War Room's way (at most five kept)."""
    k = war_room_place(results, entry[1], entry[2])
    return (list(results[:k]) + [entry] + list(results[k:]))[:TOP]


def region_bytes(by_map, legacy=None):
    """A Gauntlet record region as the game saves it: {map id: [(co, days, score)]} in the top-five format, or (`legacy`: a list of (co, days, score) or None per list position) in 0.9.4's."""
    r = bytearray(RECORD_LEN if legacy is None else 0x120)
    r[:4] = MAGIC
    if legacy is None:
        r[5] = 2
        for slot, (mid, results) in enumerate(sorted(by_map.items())):
            r[0x20 + slot * SLOT_LEN] = mid
            for k, e in enumerate(results[:TOP]):
                struct.pack_into("<I", r, 0x20 + slot * SLOT_LEN + 4 + 4 * k, encode(*e))
    else:
        for k, e in enumerate(legacy):
            if e:
                struct.pack_into("<I", r, 0x20 + 8 * k, encode(*e))
    return bytes(r)


def with_record(save_path, out_path, region):
    """A copy of a save whose slot 13 holds `region` at the Gauntlet's offset (the rest of the slot as it was, zero-filled up to there). Returns the path."""
    from . import save as savelib, saveimg
    img = saveimg.Image(save_path)
    s13 = bytes(img.slot(SLOT) or b"")
    s13 = s13.ljust(OFFSET, b"\0")[:OFFSET] + region
    with open(save_path, "rb") as f:
        data = f.read()
    with open(out_path, "wb") as f:
        f.write(savelib.write_slot(data, SLOT, s13))
    return out_path


def wheel_items(e):
    """The wheel's item ids by position: the pack's eight-entry table or AW2's six (read from the ROM image the console runs)."""
    if e.ds:
        t = list(e.read(PACK_TABLE, 8))
        return [t[(p + 2) % 8] for p in range(8)]
    t = list(e.read(GAME_TABLE, 6))
    return [t[(p + 2) % 6] for p in range(6)]
