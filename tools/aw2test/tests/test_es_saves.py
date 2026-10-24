"""Save integrity, the Emerald Sun Campaign (docs/dev/es-campaign.md "Saves"): New writes its record in slot 11 only ("AWEC"); a mission saved halfway goes to slot 12, shared
with the BH Campaign, its saved mission byte carrying the campaign in its top bits; rebooted, EMERALD SUN's Continue brings the battle back as saved and a BH CAMPAIGN
with no record of its own does not take it; won, the halfway save is dropped and the record has the mission."""

import os

from aw2test import campaigns as cp
from aw2test import dscampaign as dc
from aw2test import escampaign as es
from aw2test import paths, saves
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

ES_RECORD, ES_SUSPEND = 11, 12


def boot(ctx, save):
    e = Emu(save=save, ds=ctx.ds, env=es.ENV)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    return e, g, es.EsCampaign(g)


@test(modes=("ds",))
def save_es_campaign_record_and_a_mission_saved_halfway(ctx):
    e, g, d = boot(ctx, paths.base_save())
    base = saves.flash(e, os.path.join(ctx.out, "base"))
    d.start_es(new=True, pick=False)
    d.wait_world_map()
    img = saves.flash(e, os.path.join(ctx.out, "es_new"))
    saves.expect_slots(ctx, base, img, [ES_RECORD], "Emerald Sun New", profile_allow=[saves.MODE_BYTE])
    rec = img.slot(ES_RECORD)
    ctx.eq(rec[:4], b"AWEC", "the record's magic")
    ctx.eq(rec[0x0D] | rec[0x0E] << 8 | rec[0x0F] << 16, 1, "Klaus unlocked, nobody else")
    # Mission 1 won.
    d.pick_mission()
    d.wait_map()
    cp.win_here(e, d)
    won = saves.flash(e, os.path.join(ctx.out, "es_won1"))
    ctx.eq(int.from_bytes(won.slot(ES_RECORD)[8:12], "little"), 1, "mission 1 won, saved")
    ctx.eq(sorted(won.tags()), [0, ES_RECORD], "only the profile and the record")
    # Mission 2 (Klaus fixed) saved from its map menu.
    d.pick_mission()
    g._units_base = g._players_base = None
    d.wait_control()
    names = saves.suspend(g)
    ctx.check("Save" in names, f"Save on an Emerald Sun mission's map menu ({names})")
    snap = saves.snapshot(g)
    saved = saves.flash(e, os.path.join(ctx.out, "es_saved"))
    ctx.eq(sorted(saved.tags()), [0, ES_RECORD, ES_SUSPEND], "the slots: the profile, the record, the shared halfway slot")
    block = saved.slot(ES_SUSPEND)
    at = block.find(b"DS")
    ctx.check(at > 0 and block[at + 2] == (1 | 0x40), f"the saved mission byte is mission 2 (1) tagged Emerald Sun (0x40): {block[at + 2] if at > 0 else None}")
    e.close()
    # Rebooted: Continue brings mission 2 back as saved.
    e, g, d = boot(ctx, saved.path)
    d.start_es(new=False, pick=False)
    ctx.require(e.wait_until(lambda: e.u32(0x03000000) == 0x08022049, 1200, step=10), "EMERALD SUN's Continue: the battle")
    g._units_base = g._players_base = None
    g.wait_for_input()
    ctx.eq((d.mission(), e.u8(es.SOURCE)), (1, es.ES), "mission 2, the Emerald Sun session")
    saves.compare_snapshots(ctx, snap, saves.snapshot(g), "after a reboot, Emerald Sun Continue")
    ctx.eq(d.unlocked(), [es.KLAUS], "the unlocked COs from the record")
    e.close()
