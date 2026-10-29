"""Driving the BH2 Campaign's development build (crate::bh2_campaign): the BH Campaign's engine, a fifth entry on Select Mode's Campaign chooser, behind the
development flag TANGOAW2_BH2_CAMPAIGN (set in every console's own environment: `ENV`). `boot` continues at a chosen progress; `enter` opens a mission through its CO
screens (docs/dev/bh2-maps.md)."""

from . import dscampaign as dc
from . import paths
from .bhcampaign import BhCampaign
from .emu import Emu
from .game import Game, NavError

SOURCE = 0x0203FD57               # crate::ds_campaign::SOURCE (0 DS, 1 BH, 2 Emerald Sun, 3 BH2)
BH2 = 3
BH2_MAGIC = 0x32425741            # "AWB2"
BH2_SLOT, BH2_MID_SLOT = 10, 12   # (the mid-mission slot is the BH Campaign's, told apart by the saved mission's top bits)
CHOOSER_ROW = 4                   # AW2 CAMPAIGN, DS CAMPAIGN, BH CAMPAIGN, EMERALD SUN, BH2 (development)
P_UNLOCKED = dc.PROGRESS + 0x0D
ENV = {"TANGOAW2_BH2_CAMPAIGN": "1"}

ASUKA, CRUMB, HAWKE, STURM = 92, 82, 14, 10          # AW2 CO ids (crate::co_new, the BH roster)
TITLES = {1: "Black Insight", 2: "The Quartermaster's Crate", 3: "Iron Ledger", 4: "Talons",
          5: "Evergreen in Exile", 6: "Forest of Spears", 7: "Drake's Harbour", 8: "Fuel Line",
          9: "Paper Lanterns", 10: "Comet Highway", 11: "Black Lanterns", 12: "The Table",
          13: "Two Tides", 14: "The Long Border", 15: "Iron Gate Pass", 16: "Cold Wire",
          17: "Lot 42", 18: "Whiteout Harbour", 19: "Thirty Years of Iron", 20: "Every Colour",
          21: "The East Tower", 22: "Echo, Again", 23: "The Door Is Open", 24: "Skyfall",
          25: "The Rail East", 26: "The Second Folder", 27: "Von Bolt's Note", 28: "Where the Map Ends",
          29: "The Gate of Colours", 30: "(reserved)", 31: "The Last Accord", 32: "Through the Door"}
FOG = {1, 9, 13, 17, 18, 22, 25}
FRONT2 = {4, 13, 25}
# The COs a test player picks (none: a fixed army or pair), in the order the CO screens ask.
PICKS = {3: [ASUKA], 4: [ASUKA], 6: [ASUKA], 7: [ASUKA], 9: [ASUKA], 11: [ASUKA], 13: [ASUKA], 14: [ASUKA, CRUMB], 17: [ASUKA], 19: [ASUKA, CRUMB], 20: [ASUKA, CRUMB], 21: [ASUKA], 25: [ASUKA, CRUMB], 27: [ASUKA], 29: [ASUKA, CRUMB], 31: [ASUKA, CRUMB], 32: [ASUKA, CRUMB]}      # (M13: front 1 is Asuka's; the pick is front 2's)
ROSTER_BITS = 0xFFF               # every officer is open in the development build


M32_FLAG = (30, 222)               # crate::world_picture::BH2_FLAGS (the secret mission's flag on Black Hole's island)


class Bh2Campaign(BhCampaign):
    """The BH Campaign's driver on the BH2 entry."""
    picks = {}
    target = 0

    def pick_mission(self):
        """The world map's cursor starts on the first open mission: the secret M32 (the model's order stops at M30) needs the cursor put on its flag, as the BH Campaign's M31 does."""
        if self.target == 31:
            self.wait_world_map()
            e = self.e
            x, y = M32_FLAG
            cam_x, cam_y = min(max(x - 120, 0), 16), min(max(y - 80, 0), 96)
            e.w16(dc.WM_STATE, cam_x)
            e.w16(dc.WM_STATE + 2, cam_y)
            e.w16(dc.WM_STATE + 4, x - cam_x)
            e.w16(dc.WM_STATE + 6, y - cam_y)
            e.w32(dc.WM_STATE + 0x0C, 31)
            e.wait(30)
            return dc.DsCampaign.pick_mission(self)
        return super().pick_mission()

    def unlocked(self):
        return []

    def start_at(self, won_mask, unlocked_mask, from_title=True):
        e = self.e
        if from_title:
            self.open_campaign_box()
        self.chooser_row(CHOOSER_ROW)
        e.press("A", 8)
        e.wait(30)
        e.w32(dc.P_MAGIC, BH2_MAGIC)
        e.w32(dc.P_WON, won_mask)
        for k in range(3):
            e.w8(P_UNLOCKED + k, (unlocked_mask >> (8 * k)) & 0xFF)
        e.w8(dc.P_FLAGS + 14, 0x40)           # (the prologue's flag: not shown again)
        self.box_row(0)
        e.press("A", 8)
        for _ in range(40):
            if e.wait_until(self.active, 30, step=5):
                break
            e.press("A", 8)
        else:
            raise NavError("the BH2 Campaign did not start (is TANGOAW2_BH2_CAMPAIGN set?)")


def boot(ctx, n, env=None, save=None):
    """A console continued in the BH2 Campaign with missions 1..n-1 won, the cursor on mission n. `save`: a copy of its own (the factory's log is named after it)."""
    e = Emu(save=save or paths.base_save(), ds=ctx.ds, env=dict(ENV, **(env or {})))
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = Bh2Campaign(g)
    d.picks = {n - 1: len(PICKS.get(n, []))}
    d.target = n - 1
    won = (1 << 29) - 1 if n == 32 else (1 << (n - 1)) - 1          # (the secret M32 opens after M29: M30, the final, stays unwon so the campaign is not finished)
    d.start_at(won, ROSTER_BITS)
    e.w8(dc.P_NEXT, n - 1)
    return e, g, d


def enter(ctx, n, env=None, save=None):
    """Mission n entered through its CO screens: a mission with picks stands in its Setup phase; a fixed one is let play out its opening. Returns (emu, game, driver)."""
    from . import bhact2 as a2
    picks = PICKS.get(n, [])
    e, g, d = boot(ctx, n, env=env, save=save)
    d.wait_world_map()
    if picks:
        a2.open_mission(ctx, e, g, d, n - 1, picks, f"m{n}", setup_only=True)
        ctx.require(d.in_setup(), f"M{n}: in the Setup phase")
    else:
        a2.open_mission(ctx, e, g, d, n - 1, picks, f"m{n}")
        stable = 0
        for _ in range(3000):
            stable = stable + 1 if g.current_army() == 1 and not d.scripts_running() else 0
            if stable >= 5:
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(20)
        d.wait_control()
    ctx.eq(d.mission(), n - 1, f"M{n}: its own mission was entered")
    g._units_base = g._players_base = None
    return e, g, d
