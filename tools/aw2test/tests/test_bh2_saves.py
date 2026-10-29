"""Save integrity, the BH2 Campaign (docs/dev/bh2-maps.md "Flash slot budget"): its record has no sector of its own. It follows the BH Campaign's record in slot 13 (the BH record "AWBC" at +0,
the BH2 record "AWB2" at +0x120); nothing is written to slot 10; the Emerald Sun Campaign keeps slot 11. A save and a reboot round-trip with all three campaigns' progress present, each Continue brings its own
progress back, and a BH save from before BH2 existed (a 0x120-byte payload) still loads (`-k bh2_saves`)."""

import os

from aw2test import bh2campaign as b2
from aw2test import bhcampaign as bh
from aw2test import campaigns as cp
from aw2test import dscampaign as dc
from aw2test import escampaign as es
from aw2test import paths, saves
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

BH_SLOT, ES_SLOT, DEV_SLOT = 13, 11, 10
OFF = b2.BH2_OFFSET


def boot(ctx, save, driver, env):
    e = Emu(save=save, ds=ctx.ds, env=env)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    return e, g, driver(g)


def won_of(rec):
    return int.from_bytes(rec[8:12], "little")


@test(modes=("ds",))
def bh2_saves_share_slot_13_with_the_bh_campaign_and_emerald_sun_keeps_its_own(ctx):
    out = ctx.out
    # BH Campaign New: the record "AWBC" in slot 13 (0x120 bytes at least), nothing else but the profile.
    e, g, d = boot(ctx, paths.base_save(), bh.BhCampaign, {})
    base = saves.flash(e, os.path.join(out, "b2s_base"))
    d.start_bh(new=True, pick=False)
    d.wait_world_map()
    img_bh = saves.flash(e, os.path.join(out, "b2s_bh"))
    saves.expect_slots(ctx, base, img_bh, [BH_SLOT], "BH Campaign New", profile_allow=[saves.MODE_BYTE])
    ctx.eq(img_bh.slot(BH_SLOT)[:4], b"AWBC", "the BH record's magic at +0")
    bh_record = bytes(img_bh.slot(BH_SLOT)[:OFF])
    e.close()
    # BH2 Campaign New over it: the same slot 13 carries both records, slot 10 is not used.
    e, g, d = boot(ctx, img_bh.path, b2.Bh2Campaign, b2.ENV)
    d.start_bh2(new=True, pick=False)
    d.wait_world_map()
    img = saves.flash(e, os.path.join(out, "b2s_bh2_new"))
    tags = sorted(img.tags())
    ctx.eq(tags, [0, BH_SLOT], f"the slots after BH2 New: the profile and slot 13 only ({tags})")
    ctx.check(DEV_SLOT not in tags, "slot 10 is not written")
    s13 = bytes(img.slot(BH_SLOT))
    ctx.eq(s13[OFF:OFF + 4], b"AWB2", "the BH2 record's magic at +0x120")
    ctx.eq(s13[:OFF], bh_record, "the BH record is untouched by BH2 New")
    # Mission 1 won: the BH2 record has it, the BH record is as it was.
    d.pick_mission()
    d.wait_map()
    cp.win_here(e, d)
    won = saves.flash(e, os.path.join(out, "b2s_bh2_won1"))
    s13 = bytes(won.slot(BH_SLOT))
    ctx.eq(won_of(s13[OFF:]) & 0xFFFF, 1, "BH2: mission 1 won, saved")
    ctx.eq(s13[:OFF], bh_record, "the BH record is untouched by BH2's win")
    ctx.eq(sorted(won.tags()), [0, BH_SLOT], "only the profile and slot 13")
    e.close()
    # Emerald Sun New on top of both: slot 11 appears, slot 13 is as it was.
    e, g, d = boot(ctx, won.path, es.EsCampaign, es.ENV)
    d.start_es(new=True, pick=False)
    d.wait_world_map()
    both = saves.flash(e, os.path.join(out, "b2s_es_new"))
    ctx.eq(sorted(both.tags()), [0, ES_SLOT, BH_SLOT], "the profile, Emerald Sun's record and slot 13")
    ctx.eq(bytes(both.slot(BH_SLOT)), s13, "slot 13 (BH and BH2) is untouched by Emerald Sun New")
    ctx.eq(bytes(both.slot(ES_SLOT)[:4]), b"AWEC", "Emerald Sun's record")
    e.close()
    # Rebooted: each campaign's Continue brings its own progress back.
    e, g, d = boot(ctx, both.path, b2.Bh2Campaign, b2.ENV)
    d.start_bh2(new=False, pick=False)
    d.wait_world_map()
    ctx.eq(e.u8(b2.SOURCE), b2.BH2, "the BH2 session")
    ctx.eq(d.won() & 0xFFFF, 1, "BH2 Continue: mission 1 won")
    e.close()
    e, g, d = boot(ctx, both.path, bh.BhCampaign, {})
    d.start_bh(new=False, pick=False)
    d.wait_world_map()
    ctx.eq(e.u8(bh.SOURCE), bh.BH, "the BH session")
    ctx.eq(d.won() & 0xFFFF, won_of(bh_record) & 0xFFFF, "BH Continue: the BH progress as saved")
    e.close()
    e, g, d = boot(ctx, both.path, es.EsCampaign, es.ENV)
    d.start_es(new=False, pick=False)
    d.wait_world_map()
    ctx.eq(e.u8(es.SOURCE), es.ES, "the Emerald Sun session")
    ctx.eq(d.unlocked(), [es.KLAUS], "Emerald Sun Continue: its record")
    e.close()


@test(modes=("ds",))
def bh2_saves_a_bh_save_from_before_bh2_still_loads(ctx):
    """The BH record alone (a payload of 0x120 bytes, as every build before BH2 wrote) continues as before; BH2's first save grows the slot to 0x240 bytes and keeps the BH record."""
    e, g, d = boot(ctx, paths.base_save(), bh.BhCampaign, {})
    d.start_bh(new=True, pick=False)
    d.wait_world_map()
    old = saves.flash(e, os.path.join(ctx.out, "b2s_old_bh"))
    e.close()
    rec = bytes(old.slot(BH_SLOT))
    ctx.check(len(rec) >= 0x120, f"the BH record is {len(rec)} bytes")
    e, g, d = boot(ctx, old.path, bh.BhCampaign, {})
    d.start_bh(new=False, pick=False)
    d.wait_world_map()
    ctx.eq(e.u8(bh.SOURCE), bh.BH, "BH Continue on a save without BH2's region")
    e.close()
    e, g, d = boot(ctx, old.path, b2.Bh2Campaign, b2.ENV)
    d.start_bh2(new=True, pick=False)
    d.wait_world_map()
    img = saves.flash(e, os.path.join(ctx.out, "b2s_old_plus_bh2"))
    s13 = bytes(img.slot(BH_SLOT))
    ctx.eq(s13[:OFF], rec[:OFF], "the BH record is kept")
    ctx.eq(s13[OFF:OFF + 4], b"AWB2", "BH2's region follows it")
    e.close()
