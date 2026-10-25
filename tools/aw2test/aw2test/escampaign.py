"""Driving the Emerald Sun Campaign (crate::es_campaign): the BH Campaign's engine, a fourth entry on Select Mode's Campaign chooser, behind the development
flag TANGOAW2_ES_CAMPAIGN (set in every console's own environment: `ENV`). `boot` continues at a chosen progress; `enter` opens a mission through its CO
screens; `EsCampaign.play` plays it with the test player (aw2test.bot) or the computer (`autoplay`): the mission sim (`aw2dev campaign sim`)."""

from . import dscampaign as dc
from . import paths
from .bhcampaign import BhCampaign
from .emu import Emu
from .game import Game, NavError

SOURCE = 0x0203FD57               # crate::ds_campaign::SOURCE (0 DS, 1 BH, 2 Emerald Sun)
ES = 2
ES_MAGIC = 0x43455741             # "AWEC"
ES_SLOT, ES_MID_SLOT = 11, 12     # (the mid-mission slot is the BH Campaign's, told apart by the saved mission's top bits)
CHOOSER_ROW = 3                   # AW2 CAMPAIGN, DS CAMPAIGN, BH CAMPAIGN, EMERALD SUN
P_UNLOCKED = dc.PROGRESS + 0x0D
ENV = {"TANGOAW2_ES_CAMPAIGN": "1"}

# AW2 CO ids: Klaus, Aurelia, Cassius, Livia, Varro (crate::es_co), Colin, Kanbei.
KLAUS, AURELIA, CASSIUS, LIVIA, VARRO = 86, 87, 88, 89, 90
COLIN, KANBEI = 16, 6
ROSTER = [KLAUS, AURELIA, CASSIUS, LIVIA, COLIN, KANBEI]     # crate::es_campaign::ROSTER, the unlock order

# Per mission: (title, CO picks the CO screens ask for, fog). The picks a test makes are in PICKS.
TITLES = {
    1: "Landfall", 2: "Testudo", 3: "The Wall", 4: "The Second Legion", 5: "Dust and Wheels", 6: "Tribute", 7: "Mare Nostrum",
    8: "Hammer and Anvil", 9: "Grain Ships", 10: "The Quiet Pass", 11: "The Treasure Train", 12: "Siege of Iron", 13: "The Free Port",
    14: "Varro's Gambit", 15: "Pax Romana", 16: "Sol Invictus",
}
FOG = {4, 10}
RAIN = {3, 8}                     # (rain brings fog: their review pictures are taken fogged and with the fog off, as a fog mission's)
ARMIES = {1: (1, 2), 2: (1, 2), 3: (1, 2), 4: (1, 2), 5: (1, 2), 6: (1, 2, 3), 7: (1, 2, 3), 8: (1, 2, 3), 9: (1, 2), 10: (1, 2, 3), 11: (1, 2, 3), 12: (1, 2, 3),
          13: (1, 2, 3, 4), 14: (1, 2, 3), 15: (1, 2, 3), 16: (1, 2, 3)}      # the armies of each mission (the player is army 1)
# The COs a test player picks (none: a fixed army), in the order the CO screens ask: a lead, then a tag partner where the mission has one.
PICKS = {4: [KLAUS], 7: [LIVIA], 9: [KLAUS], 10: [KLAUS], 11: [CASSIUS], 13: [KLAUS, LIVIA], 14: [AURELIA], 15: [KLAUS, AURELIA], 16: [AURELIA]}
# The roster bits unlocked before each mission (Aurelia after M3, Cassius after M4, Livia and Colin after M6, Kanbei after M10).
def unlocked_before(n):
    bits = 0b1                    # Klaus
    if n > 3:
        bits |= 0b10              # Aurelia
    if n > 4:
        bits |= 0b100             # Cassius
    if n > 6:
        bits |= 0b11000           # Livia, Colin
    if n > 10:
        bits |= 0b100000          # Kanbei
    return bits


class EsCampaign(BhCampaign):
    """The BH Campaign's driver on the Emerald Sun entry."""
    picks = {}

    def unlocked(self):
        mask = self.mask() & 0x3F
        return [co for k, co in enumerate(ROSTER) if mask >> k & 1]

    def start_at(self, won_mask, unlocked_mask, from_title=True):
        e = self.e
        if from_title:
            self.open_campaign_box()
        self.chooser_row(CHOOSER_ROW)
        e.press("A", 8)
        e.wait(30)
        e.w32(dc.P_MAGIC, ES_MAGIC)
        e.w32(dc.P_WON, won_mask)
        for k in range(3):
            e.w8(P_UNLOCKED + k, (unlocked_mask >> (8 * k)) & 0xFF)
        e.w8(dc.P_FLAGS + 14, 0x40)           # (the prologue's flag 0x9E: not shown again)
        self.box_row(0)
        e.press("A", 8)
        for _ in range(40):
            if e.wait_until(self.active, 30, step=5):
                break
            e.press("A", 8)
        else:
            raise NavError("the Emerald Sun Campaign did not start (is TANGOAW2_ES_CAMPAIGN set?)")


def _start_es(self, new=True, from_title=True, pick=True):
    """From the title: Campaign -> EMERALD SUN -> New or Continue (BhCampaign.start_bh on this entry)."""
    e = self.e
    if from_title:
        self.open_campaign_box()
    self.chooser_row(CHOOSER_ROW)
    e.press("A", 8)
    e.wait(30)
    if e.u8(dc.MENU_LEVEL) != 2 or e.u8(SOURCE) != ES:
        raise NavError(f"not in the Emerald Sun box (level {e.u8(dc.MENU_LEVEL)}, source {e.u8(SOURCE)})")
    self.box_row(1 if new else 0)
    e.press("A", 8)
    for _ in range(40):
        if e.wait_until(self.active, 30, step=5):
            break
        e.press("A", 8)
    else:
        raise NavError("the Emerald Sun Campaign did not start")
    if pick:
        self.pick_mission()


EsCampaign.start_es = _start_es


def boot(ctx, n, env=None):
    """A console continued in the Emerald Sun Campaign with missions 1..n-1 won and the COs unlocked by then, the cursor on mission n."""
    e = Emu(save=paths.base_save(), ds=ctx.ds, env=dict(ENV, **(env or {})))
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = EsCampaign(g)
    d.picks = {n - 1: len(PICKS.get(n, []))}
    d.start_at((1 << (n - 1)) - 1, unlocked_before(n))
    e.w8(dc.P_NEXT, n - 1)
    return e, g, d


def enter(ctx, n):
    """Mission n entered through its CO screens: a mission with picks stands in its Setup phase; a fixed one is let play out its opening (the
    player has control, nothing has moved). Returns (emu, game, driver)."""
    from . import bhact2 as a2
    picks = PICKS.get(n, [])
    e, g, d = boot(ctx, n)
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
