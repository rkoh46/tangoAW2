"""Driving the BH Campaign (crate::bh_campaign, crate::custom_campaign): the
same engine as the DS Campaign, a third entry on Select Mode's Campaign
chooser. The helpers reuse `DsCampaign` (world map, CO screen, forcing a
win)."""

import struct

from . import dscampaign as dc
from .dscampaign import DsCampaign
from .game import NavError

SOURCE = 0x0203FD57               # crate::ds_campaign::SOURCE (0 DS, 1 BH)
BH = 1
P_UNLOCKED = dc.PROGRESS + 0x0D   # the unlocked COs: bits of the roster
BH_MAGIC = 0x43425741             # "AWBC"
BH_SLOT, BH_MID_SLOT = 13, 12
CHOOSER_ROW = 2                   # AW2 CAMPAIGN, DS CAMPAIGN, BH CAMPAIGN

# The campaign's roster (crate::bh_campaign::ROSTER), AW2 CO ids.
ANDY, OLAF, EAGLE, KANBEI = 1, 3, 8, 6
STURM, VON_BOLT, HAWKE, KINDLE, KOAL, JUGGER, FLAK, LASH, ADDER, CLONE_ANDY, SONJA = 10, 75, 14, 74, 73, 72, 11, 12, 13, 81, 7
ROSTER = [STURM, VON_BOLT, HAWKE, KOAL, KINDLE, JUGGER, FLAK, LASH, ADDER, CLONE_ANDY, SONJA]   # (the unlock order: Koal before Kindle)
# The placeholder missions: the picks the CO screen asks for.
PICKS = {0: 0, 1: 1, 2: 0}
FLAG_POINTS = {0: (160, 30), 1: (180, 46), 2: (188, 54)}


FEATURES = {"TANGOAW2_BH_FEATURES": "1"}   # crate::bh_campaign::features_def: the format's fields


class BhCampaign(DsCampaign):
    picks = PICKS

    def total_picks(self):
        return self.picks.get(self.mission(), 1)

    def start_bh(self, new=True, from_title=True, pick=True):
        """From the title (or Select Mode's wheel): Campaign -> BH CAMPAIGN -> New or Continue."""
        e = self.e
        if from_title:
            self.open_campaign_box()
        else:
            from . import campaigns
            campaigns.box_from_wheel(e, self)
        self.chooser_row(CHOOSER_ROW)
        e.press("A", 8)
        e.wait(30)
        if e.u8(dc.MENU_LEVEL) != 2 or e.u8(SOURCE) != BH:
            raise NavError(f"not in the BH box (level {e.u8(dc.MENU_LEVEL)}, source {e.u8(SOURCE)})")
        self.box_row(1 if new else 0)
        e.press("A", 8)
        for _ in range(40):
            if e.wait_until(self.active, 30, step=5):
                break
            e.press("A", 8)
        else:
            raise NavError("the BH Campaign did not start")
        if pick:
            self.pick_mission()

    def unlocked(self):
        """The roster's COs unlocked, as AW2 CO ids."""
        mask = self.mask() & 0xFFF
        return [co for k, co in enumerate(ROSTER) if mask >> k & 1]

    def mask(self):
        b = self.e.read(P_UNLOCKED, 3)
        return b[0] | b[1] << 8 | b[2] << 16

    def bonds(self):
        """The hidden bonds earned (bit k: bond k)."""
        return self.mask() >> 12

    def won(self):
        return struct.unpack("<I", self.e.read(dc.P_WON, 4))[0]

    def offered(self):
        """On the CO screen: the COs it offers (all country tabs)."""
        c = self.co_cursor()
        return None if c is None else sorted(c["cos"])

    def start_at(self, won_mask, unlocked_mask, from_title=True):
        """Continue with the progress record set (a test aid): the missions
        won (bits) and the COs unlocked (roster bits)."""
        e = self.e
        if from_title:
            self.open_campaign_box()
        self.chooser_row(CHOOSER_ROW)
        e.press("A", 8)
        e.wait(30)
        e.w32(dc.P_MAGIC, BH_MAGIC)
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
            raise NavError("the BH Campaign did not start")


UNIT_IDS = {"infantry": 1, "mech": 2, "mdtank": 3, "megatank": 4, "tank": 5, "recon": 6}


def unit_id(name):
    return UNIT_IDS[name]


def _controllers_five(self):
    """Player +0x1B for armies 1..5 (the patched player table, five.rs)."""
    p = self.players()
    return [self.e.u8(p + 0x3C * a + 0x1B) for a in range(1, 6)]


BhCampaign.controllers_five = _controllers_five
