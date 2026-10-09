"""The world map's mission panel: its ENEMY portrait (bottom left, OBJ tiles 152..163, palette 2) is the lead enemy
CO's small face. AW2's panel draws the face of the army in Black Hole's colour (5), which in the BH Campaign is the
player's own army (its CO, or CO 0xFF's row, stripes, where the player picks) and in the DS Campaign often no army
(whatever the last battle left in the tiles); `crate::ds_worldmap::panel_army` makes the lead enemy that army.

`-k bh_panel_portraits` (all 31 BH missions, with AW2TEST_REVIEW_DIR a contact sheet), `-k bh_panel_after_battle`
(the garbage a battle left), `-k ds_panel_portraits` (the DS Campaign's 28)."""
import os
import struct

from aw2test import bhact2 as a2
from aw2test import dscampaign as dc
from aw2test.harness import test
from aw2test.rom import co_name

MISSION_TABLE = 0x08FC0000 + 0xA000
MISSION_RECORD = 0x30
MAP_TABLE_POOL = 0x080773A8      # the panel's pointer to the map table
PRESENTATION_POOL = 0x08039B7C
PRESENTATION_ROW = 0x44
MINI = 0x18                      # the row's small face: 12 raw tiles (32x16 and 16x16)
OBJ_FACE = 0x06010000 + 152 * 32
FACE_BYTES = 12 * 32
MAP_ID = 0xF0


def open_panel(e, d, i):
    """Cursor on mission i, A: the panel up and its text written."""
    x, y = struct.unpack_from("<hh", e.read(MISSION_TABLE + MISSION_RECORD * i + 6, 4))
    cam_x, cam_y = min(max(x - 120, 0), 192), min(max(y - 80, 0), 96)
    e.w16(dc.WM_STATE, cam_x)
    e.w16(dc.WM_STATE + 2, cam_y)
    e.w16(dc.WM_STATE + 4, x - cam_x)
    e.w16(dc.WM_STATE + 6, y - cam_y)
    e.w32(dc.WM_STATE + 0x0C, i)
    e.wait(30)
    e.press("A", 6)
    e.wait_until(lambda: d.proc_fn_running(dc.WM_INFO_LOOP), 300, step=5)
    e.wait(240)


def header(e):
    """The mission under the cursor's header (the map table's entry for the campaign's map id)."""
    return e.read(e.u32(MAP_TABLE_POOL) + 0x5C * MAP_ID, 0x5C)


def lead_enemy(h):
    """The first army that is not army 1 and on another team than it, with a CO: (army, CO) (five-army missions: the
    player is a fifth army, so the header's armies on the ally's team count as the player's: not told apart here)."""
    for k in range(1, h[0x18]):
        if h[0x44 + k] != h[0x44] and h[0x3C + k] < 96:
            return k, h[0x3C + k]
    return None


def face_of(e, co):
    return e.read(e.u32(e.u32(PRESENTATION_POOL) + PRESENTATION_ROW * co + MINI), FACE_BYTES)


def sweep(ctx, e, d, missions, label, lead_of=None):
    out = os.environ.get("AW2TEST_REVIEW_DIR")
    bad = 0
    for i in missions:
        open_panel(e, d, i)
        h = header(e)
        lead = lead_enemy(h)
        if lead_of and i in lead_of:
            lead = lead_of[i]
        tiles = e.read(OBJ_FACE, FACE_BYTES)
        shot = e.shot(os.path.join(out, f"panel_{i:02d}")) if out else None
        if lead is None:
            ctx.log(f"{label} M{i + 1}: no enemy with a CO (armies {h[0x18]}, COs {h[0x3C:0x40].hex()}, teams {h[0x44:0x48].hex()})")
            ctx.check(tiles == bytes(FACE_BYTES), f"{label} M{i + 1}: no enemy CO: the portrait is blank")
            e.press("B", 6)
            e.wait(60)
            continue
        k, co = lead
        want = face_of(e, co)
        ok = tiles == want
        bad += not ok
        ctx.log(f"{label} M{i + 1}: lead enemy army {k + 1} CO {co} ({co_name(co)}) armies {h[0x18]} teams {h[0x44:0x48].hex()} COs {h[0x3C:0x40].hex()}")
        ctx.check(ok, f"{label} M{i + 1}: the ENEMY portrait is CO {co} ({co_name(co)})'s face")
        e.press("B", 6)
        e.wait(60)
    return bad


@test(modes=("ds",))
def bh_panel_portraits(ctx):
    """All 31 BH Campaign panels (the world map as the finale's Free Play shows it): the portrait is the lead enemy's."""
    e, g, d = a2.boot(ctx, (1 << 30) - 1, 0xFFF | (0x1FF << 12), picks={}, at=0)
    d.wait_world_map()
    e.wait(60)
    # (M28 is a five-army mission: the player is the fifth army, picks a pair, and the header's first army, Rachel (80),
    # an enemy of Black Hole's like the other three, has no CO in it: the CO screen's slot)
    sweep(ctx, e, d, range(31), "BH", lead_of={27: (0, 80)})
    e.close()


@test(modes=("ds",))
def bh_panel_after_battle(ctx):
    """The user's case: Mission 1 played and won, the cursor on Mission 2 (a CO pick, Jess the enemy): the portrait is Jess's
    face, not what the battle left in OBJ VRAM."""
    e, g, d = a2.boot(ctx, 0, 1, picks={0: 0, 1: 1}, at=0)
    d.wait_world_map()
    a2.open_mission(ctx, e, g, d, 0, [], "m1", shots=())
    a2.win(ctx, e, d, "m1", shots=())
    d.wait_world_map()
    e.wait(60)
    out = os.environ.get("AW2TEST_REVIEW_DIR")
    e.press("A", 6)
    e.wait(300)
    h = header(e)
    ctx.eq(h[0x3C + 1], 17, "Mission 2's enemy is Jess")
    if out:
        e.shot(os.path.join(out, "after_battle_m2"))
    ctx.check(e.read(OBJ_FACE, FACE_BYTES) == face_of(e, 17), "after a battle, the ENEMY portrait of Mission 2 is Jess's face")
    e.close()


@test(modes=("ds",))
def ds_panel_portraits(ctx):
    """The DS Campaign's 28 panels (the last mission reached, every other won): the portrait is the lead enemy CO's, or
    blank where no enemy has a CO."""
    from aw2test import paths
    from aw2test.emu import Emu
    from aw2test.game import Game
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    d.start(step=27, pick=False)
    d.wait_world_map()
    e.wait(60)
    sweep(ctx, e, d, range(28), "DS")
    e.close()
