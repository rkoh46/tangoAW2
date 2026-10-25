"""The Emerald Sun Campaign's world map: Dual Strike's Omega Land with the 16 missions as flags in story order (es_campaign::region), stitched from real screenshots
(`AW2TEST_REVIEW_DIR` gets es_world_map_<stage>.png): `-k es_world_map`."""
import os

from aw2test import escampaign as es
from aw2test import stitch
from aw2test.harness import test

WM = 0x0202FDFC
MAP_W, MAP_H = 480, 240


def stitched(ctx, e, name):
    """The whole 480 x 240 map as the game draws it now (flags, markers, the cleared stars; no panels, no cursor), from a sweep of camera positions."""
    from PIL import Image
    import numpy as np
    shots = {}
    for cy in (0, 40, 80):
        for cx in (0, 80, 160, 240):
            for _ in range(4):
                e.w16(WM, cx)
                e.w16(WM + 2, cy)
                e.w16(WM + 4, 700)
                e.w16(WM + 6, 700)
                e.wait(8)
                stitch.hide_hud(e)
            shots[(cx, cy)] = e.shot(os.path.join(ctx.out, f"{name}_{cx}_{cy}"))
    stack = [[[] for _ in range(MAP_W)] for _ in range(MAP_H)]
    for (cx, cy), p in shots.items():
        im = np.asarray(Image.open(p).convert("RGB"))
        for y in range(160):
            for x in range(240):
                stack[cy + y][cx + x].append(im[y, x])
    arr = np.zeros((MAP_H, MAP_W, 3), dtype=np.uint8)
    for y in range(MAP_H):
        for x in range(MAP_W):
            arr[y, x] = np.median(np.array(stack[y][x]), axis=0)
    full = Image.fromarray(arr)
    full.save(os.path.join(ctx.out, f"{name}.png"))
    out = os.environ.get("AW2TEST_REVIEW_DIR")
    if out:
        os.makedirs(out, exist_ok=True)
        full.save(os.path.join(out, f"{name}.png"))
    return full


@test(modes=("ds",))
def es_world_map_stages(ctx):
    """The map at the start (M1 open), mid-campaign (M1..M8 won, M9 open) and before M16 (M1..M15 won): the flags shown and cleared are the right ones."""
    for n, label in ((1, "start"), (9, "mid"), (16, "before_m16")):
        e, g, d = es.boot(ctx, n)
        d.wait_world_map()
        e.wait(120)
        flags = d.map_flags()
        ctx.log(f"M{n}: flags {flags[:16]}")
        for k in range(16):
            shown, cleared = bool(flags[k] & 1), bool(flags[k] & 2)
            ctx.eq(cleared, k < n - 1, f"M{n} stage: mission {k + 1} cleared")
            ctx.eq(shown, k == n - 1, f"M{n} stage: mission {k + 1} is the open flag")
        ctx.eq(d.map_mission(), n - 1, f"M{n} stage: the cursor is on mission {n}")
        e.shot(os.path.join(ctx.out, f"cursor_{label}"))
        stitched(ctx, e, f"es_world_map_{label}")
        e.close()


# --- the campaign's progression on the world map, end to end ---------------------------------------------------------------------------------------------------

ES_RECORD = 11
SHOT_AT = (1, 4, 8, 12, 15)         # the unlock moments the review sheet shows (before the win, then right after it)
RELOAD_AFTER = (3, 7, 11, 15)       # save, quit and Continue after these wins


def _map_state(ctx, e, d, n, tag):
    """The world map with missions 1..n-1 won and mission n open: its flag shown, theirs cleared, the later ones not there, the cursor on mission n."""
    flags = d.map_flags()[:16]
    for k in range(16):
        ctx.eq(bool(flags[k] & 2), k < n - 1, f"{tag}: mission {k + 1} cleared")
        ctx.eq(bool(flags[k] & 1), k == n - 1, f"{tag}: mission {k + 1} open")
    ctx.eq(d.map_mission(), n - 1, f"{tag}: the cursor is on mission {n}")
    ctx.check(e.u8(0x0202FDFC + 0x10) == 1, f"{tag}: the cursor is snapped to the flag")


def _record(ctx, e, n, tag, out):
    """The campaign's record in its Flash slot: missions 1..n won, the COs unlocked by then."""
    from aw2test import saves
    img = saves.flash(e, os.path.join(out, f"es_prog_{tag}"))
    rec = img.slot(ES_RECORD)
    ctx.eq(rec[:4], b"AWEC", f"{tag}: the record's magic")
    won = int.from_bytes(rec[8:12], "little")
    ctx.eq(won, (1 << n) - 1, f"{tag}: the record has missions 1..{n} won")
    mask = rec[0x0D] | rec[0x0E] << 8 | rec[0x0F] << 16
    ctx.eq(mask, es.unlocked_before(n + 1) & 0x3F, f"{tag}: the COs unlocked after mission {n}")
    return img


def _win(ctx, e, g, d, n):
    """Mission n entered through its CO screens, played into its first turn, won (a test aid: the enemy routed), followed to the world map."""
    from aw2test import bhact2 as a2
    from aw2test import twofront
    a2.open_mission(ctx, e, g, d, n - 1, es.PICKS.get(n, []), f"m{n}")
    d.leave_setup() if d.in_setup() else None
    for _ in range(3000):
        if not d.scripts_running():
            e.wait(30)
            if not d.scripts_running():
                break
        e.press("A", 4)
        e.wait(10)
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), n - 1, f"M{n}: its own mission is in play")
    ctx.require(twofront.rout_enemy(d), f"M{n}: won (test aid)")
    if n == 16:
        return          # (the end: the scenes, the staff roll and Select Mode follow; the test reads them)
    for _ in range(8000):
        e.wait(30)
        if d.world_map_up() and e.u8(0x0202FDFC + 0x10) and not d.scripts_running():
            break
        if d.scripts_running() or not d.in_battle():
            e.press("A", 4)
    ctx.require(d.world_map_up(), f"M{n}: back on the world map")


@test(modes=("ds",))
def es_progression(ctx):
    """The Emerald Sun Campaign from New to the epilogue, every mission won by the test aid: after each win the next flag opens, the cursor goes to it, the cleared flags and the record are right, and
    Continue after a save brings the same map back. Pictures of the unlock moments go to AW2TEST_REVIEW_DIR (es_unlock_<n>_before / _after / _after2)."""
    from aw2test import saves
    review = os.environ.get("AW2TEST_REVIEW_DIR")

    def keep(e, name):
        p = e.shot(os.path.join(ctx.out, name))
        if review:
            import shutil
            os.makedirs(review, exist_ok=True)
            shutil.copy(p, os.path.join(review, os.path.basename(p)))
    e, g, d = es.boot(ctx, 1)
    d.wait_world_map()
    e.wait(90)
    for n in range(1, 17):
        _map_state(ctx, e, d, n, f"before M{n}")
        if n in SHOT_AT:
            keep(e, f"es_unlock_{n:02d}_before")
        _win(ctx, e, g, d, n)
        if n == 16:
            break
        # the unlock: the map after the win (the next flag appearing, the cursor moving on) a moment later and when it has settled
        if n in SHOT_AT:
            keep(e, f"es_unlock_{n:02d}_after")
        e.wait(240)
        if n in SHOT_AT:
            keep(e, f"es_unlock_{n:02d}_after2")
        _map_state(ctx, e, d, n + 1, f"after M{n}")
        img = _record(ctx, e, n, f"m{n}", ctx.out)
        if n in RELOAD_AFTER:
            e.close()
            e2 = es.Emu(save=img.path, ds=ctx.ds, env=es.ENV)
            g = es.Game(e2, ctx.image)
            ctx.games.append(g)
            d = es.EsCampaign(g)
            e = e2
            d.start_es(new=False, pick=False)
            d.wait_world_map()
            e.wait(90)
            _map_state(ctx, e, d, n + 1, f"after Continue (M{n} won)")
    # mission 16 won: the scenes on the map, then the staff roll, then Select Mode with the session over (the BH Campaign's end, bh_campaign_credits_after_the_last_mission)
    from aw2test import dscampaign as dc
    CREDITS, ROLL_FNS = 0x0203FD17, (0x0806C075, 0x0806C0E5)
    for f in range(3000):
        if e.u8(CREDITS) >= 3:
            break
        if d.scripts_running() or not d.in_battle():
            e.press("A", 4)       # (the results, the scenes on the map)
        e.wait(30)
    ctx.require(e.u8(CREDITS) == 3, "M16 won: the map is left for the credits after the epilogue")
    rolled = False
    for k in range(300):
        e.wait(60)
        fns = {e.u32(0x0200D610 + 0x6C * j + 0x10) for j in range(32)}
        if fns & set(ROLL_FNS):
            if not rolled:
                e.wait(70)
                keep(e, "es_staff_roll")
            rolled = True
        if rolled and any(e.u32(0x0200D610 + 0x6C * j) in dc.WHEELS for j in range(32)):
            break
    ctx.check(rolled, "the staff roll ran")
    e.wait(120)
    ctx.eq(e.u8(dc.ACTIVE), 0, "back on Select Mode: the session is over")
    ctx.eq(e.u8(dc.P_NEXT + 1), 1, "the campaign recorded as over")
    img = saves.flash(e, os.path.join(ctx.out, "es_prog_end"))
    ctx.eq(int.from_bytes(img.slot(ES_RECORD)[8:12], "little"), 0xFFFF, "the record has all sixteen missions won")
    e.close()


@test(modes=("ds",))
def es_world_map_replay_a_cleared_mission(ctx):
    """Like Dual Strike's map: a cleared flag can be picked again (the mission panel, the mission); winning it again changes nothing in the record (no new flag, the same open mission)."""
    from aw2test import dscampaign as dc
    from aw2test import twofront
    e, g, d = es.boot(ctx, 3)
    d.wait_world_map()
    e.wait(60)
    before = (d.won(), e.u8(dc.P_NEXT), list(d.map_flags()[:16]))
    x, y = 214, 176                                     # M1's flag (es_campaign::region)
    cx, cy = max(0, min(240, x - 120)), max(0, min(80, y - 80))
    for off, v in ((0, cx), (2, cy), (4, x - cx), (6, y - cy)):
        e.w16(WM + off, v)
    e.w32(WM + 0xC, 0)
    e.wait(60)
    ctx.eq(d.map_flags()[0] & 2, 2, "mission 1 is cleared")
    d.pick_mission()
    d.wait_map() if not d.in_battle() else None
    ctx.require(d.in_battle(), "a cleared mission can be played again: the battle loaded")
    ctx.eq(d.mission(), 0, "it is mission 1")
    g._units_base = g._players_base = None
    d.leave_setup() if d.in_setup() else None
    for _ in range(3000):
        if not d.scripts_running():
            e.wait(30)
            if not d.scripts_running():
                break
        e.press("A", 4)
        e.wait(10)
    d.wait_control()
    ctx.require(twofront.rout_enemy(d), "mission 1 won again (test aid)")
    for _ in range(4000):
        e.wait(30)
        if d.world_map_up() and e.u8(WM + 0x10) and not d.scripts_running():
            break
        if d.scripts_running() or not d.in_battle():
            e.press("A", 4)
    ctx.require(d.world_map_up(), "back on the world map")
    e.wait(120)
    after = (d.won(), e.u8(dc.P_NEXT), list(d.map_flags()[:16]))
    ctx.eq(after[0], before[0], "the won missions are the same")
    ctx.eq(after[1], before[1], "the campaign's next mission is the same")
    ctx.eq([f & 3 for f in after[2]], [f & 3 for f in before[2]], "the flags are the same (mission 3 open, none new)")
    e.close()
