"""Driving Conquest Run (crate::conquest, docs/dev/conquest.md): Select Mode's CONQUEST entry (a game mode of its own on the Gauntlet's engine; its map selector lists the one row), five of AW2's Versus
maps in a row with the survivors and funds carried over, a reward between maps, the run's record under key `gauntlet_50` in the Gauntlet's record table. The Gauntlet's own driver (`Gauntlet`) does the
selector, the army screen and the end; this adds the run's maps and the stage steps."""

from . import dscampaign as dc
from . import gauntlet as ga
from .game import NavError

MISSION = ga.CONQUEST_MISSION      # crate::gauntlet_mode::def(): the run's mission is the last of the campaign's list (the Gauntlet's selector does not list it)
RECORD_ID = 50                     # crate::conquest::KEY, gauntlet_50
STAGES = 5
STAGE_BUSY = ga.STAGE_AT + 1       # crate::stage: a swap is running

# crate::conquest::MAPS: (name, map id, size, player's HQ, enemy's HQ, the enemy's starting units, its funds, the player's starting units)
MAPS = [
    {"name": "Sabre Range", "id": 0x18, "size": (15, 11), "player": (1, 9), "enemy": (13, 1), "funds": 3000, "force": 3, "mine": 4},
    {"name": "Switchback", "id": 0x1C, "size": (21, 15), "player": (1, 13), "enemy": (19, 1), "funds": 6000, "force": 4, "mine": 0},
    {"name": "Piston Dam", "id": 0x22, "size": (26, 14), "player": (2, 1), "enemy": (23, 12), "funds": 10000, "force": 6, "mine": 0},
    {"name": "Cube Keys", "id": 0x0E, "size": (32, 30), "player": (5, 6), "enemy": (26, 23), "funds": 15000, "force": 7, "mine": 0},
    {"name": "Mial's Hope", "id": 0x75, "size": (45, 28), "player": (4, 16), "enemy": (34, 23), "funds": 22000, "force": 9, "mine": 0},
]
BLACK_HOLE = 5
STATE = 0x0203D0E0                 # crate::conquest::STATE: +0 the reward page (0 none, 1 rewards, 2 units), +1 the cursor, +2 taken, +3 the map won, +4..+6 the units on offer
PAGE, CURSOR, TAKEN, WON, OFFER = STATE, STATE + 1, STATE + 2, STATE + 3, STATE + 4
CHEST, REINFORCE, REPAIR = 0, 1, 2
CHEST_FUNDS = [10000, 15000, 20000, 25000]        # crate::conquest::chest_funds
OFFERED = [[5, 3, 19], [3, 11, 16], [8, 11, 17], [4, 8, 17]]   # crate::conquest::offered: Tank, Md Tank, B Copter; Md Tank, Rockets, Fighter; Neotank, Rockets, Bomber; Megatank, Neotank, Bomber
UNIT_MAX = {1: (0, 99), 3: (8, 50), 4: (3, 50), 5: (9, 70), 8: (9, 99), 11: (6, 50), 16: (9, 99), 17: (9, 99), 19: (6, 99)}   # (not used for checks: read from the ROM)


def stage(e):
    return e.u8(ga.STAGE_AT)


class Conquest(ga.Gauntlet):
    """The Gauntlet's driver on the CONQUEST wheel entry (its selector is the one row)."""
    ENTRY = "conquest"

    def open(self, from_title=True, pick=True, map=MISSION, box=None):
        """CONQUEST, A (the box over a saved Conquest run: `box="continue"` / `"new"`), the one-row selector's A."""
        return super().open(from_title, pick, map, box)

    def begin(self, co=ga.ANDY, colour=None, from_title=True, box=None):
        """From the title: CONQUEST, the one row (Conquest Run), the army screen's CO and colour, the battle on day 1 of the first map with the player in control."""
        return self.start(co, from_title=from_title, colour=colour, map=MISSION, box=box)

    def size(self):
        e = self.e
        return e.u16(dc.MAP), e.u16(dc.MAP + 2)

    def funds(self, army=1):
        p = self.g.player(army)
        return p["funds"] if "funds" in p else int.from_bytes(p["raw"][0:4], "little")

    def reward_page(self):
        return self.e.u8(PAGE)

    def wait_reward(self, frames=2400):
        """The map is won: the reward page opens over it (the stage engine waits before its fade)."""
        e = self.e
        if not e.wait_until(lambda: e.u8(PAGE) != 0, frames, step=10):
            raise NavError(f"the reward page did not open (stage {stage(e)})")
        e.wait(10)

    def choose_reward(self, which=CHEST, unit=0):
        """On the reward page: the cursor to `which` (LEFT / RIGHT), A; the free unit's page takes `unit` (0..2) and A."""
        e = self.e
        for _ in range(4):
            if e.u8(CURSOR) == which:
                break
            e.press("RIGHT", 4)
            e.wait(6)
        e.press("A", 4)
        e.wait(10)
        if which == REINFORCE:
            for _ in range(4):
                if e.u8(PAGE) == 2 and e.u8(CURSOR) == unit:
                    break
                e.press("RIGHT", 4)
                e.wait(6)
            e.press("A", 4)
            e.wait(10)

    def wait_stage(self, k, frames=6000, reward=CHEST, unit=0):
        """Through the swap's fades until the battle is on stage k, the swap is over and the cursor answers (A is pressed for scenes only; a reward page that opens takes `reward`)."""
        e, g = self.e, self.g
        for _ in range(frames // 20):
            if e.u8(PAGE) != 0:
                self.choose_reward(reward, unit)
            elif stage(e) != k and self.scripts_running():
                e.press("A", 4)
            e.wait(15)
            if stage(e) == k and e.u8(STAGE_BUSY) == 0 and self.in_battle():
                break
        if stage(e) != k:
            raise NavError(f"the run did not reach map {k + 1} (stage {stage(e)})")
        g._units_base = g._players_base = None
        self.wait_control()
        g._units_base = g._players_base = None

    def capture_enemy_hq(self, ctx, k=None):
        """The player's Infantry takes the enemy's HQ on the map the run is on (the game's own Capture)."""
        k = stage(self.e) if k is None else k
        self.capture(ctx, MAPS[k]["enemy"], army=1)

    def win_map(self, ctx, k=None, reward=CHEST, unit=0):
        """Capture the enemy HQ; for a map but the last, through the reward (`reward`) to the next map's first turn."""
        k = stage(self.e) if k is None else k
        self.capture_enemy_hq(ctx, k)
        if k + 1 < STAGES:
            self.wait_stage(k + 1, reward=reward, unit=unit)

    def units_by_type(self, army=1):
        return sorted((u["type"], u["hp"]) for u in self.g.units(army=army))
