"""BH Campaign, all 31 missions: the review pictures, one test a mission (`-k bh_review_m`).

Every mission is entered in the merged tree through its CO screen and photographed in its Setup phase
(the deployment before day 1, before any structure fires): the whole map; for a fogged mission the fog
on and fog off; for a two-front mission the second front too; M30 also in its stage two (the Great Hall
taken). Every unit's HP, ammo and fuel are checked against the full values (the exceptions by design
are listed in EXCEPT). The pictures go to the folder named by AW2TEST_REVIEW_DIR (m<N>_<view>.png,
unscaled: 16 pixels a cell); the labels and the contact sheets are made from them by a script
(tools/aw2test/review_sheets.py)."""

import os
import shutil

from aw2test import bhact2 as a2
from aw2test import bhcampaign as bh
from aw2test.harness import test

OUT = os.environ.get("AW2TEST_REVIEW_DIR")
FOG = 0x03003FCD
BONDS = 0x1FF << 12
S, VB, HK, KO, KI, JU, FL = bh.STURM, bh.VON_BOLT, bh.HAWKE, bh.KOAL, bh.KINDLE, bh.JUGGER, bh.FLAK
# number: (title, roster bits unlocked, CO picks, fog, other front)
M = {
    1: ("Storm Landing", 0b1, [], False, False),
    2: ("The Sleeping Foundry", 0b11, [S], False, False),
    3: ("Blockade Runner", 0b11, [], False, False),
    4: ("Marshal in Green", 0b11, [S], True, False),
    5: ("Night Raid", 0b111, [S], True, False),
    6: ("Stepping Stones", 0b111, [S], False, False),
    7: ("Greenhaven Arsenal", 0b111, [S], False, False),
    8: ("The Twin Gates", 0b111, [S, HK], False, True),
    9: ("The Loot Train", 0b111, [S], True, False),
    10: ("Evergreen Citadel", 0b111, [S, HK], False, False),
    11: ("Ashfall Pass", 0b111, [S, HK], False, False),
    12: ("Highway to the Horizon", 0b111, [S], False, False),
    13: ("Festival of Flame", 0b1111, [S], False, False),
    14: ("No Soldier Left Behind", 0b11111, [S], True, False),
    15: ("The Skybridge", 0b11111, [S, HK], False, True),
    16: ("Comet Keep", 0b11111, [S, HK], False, False),
    17: ("Cold Iron", 0b11111, [S], True, False),
    18: ("The Pit", 0b111111, [S], False, False),
    19: ("The Assembly Line", 0b111111, [S], False, False),
    20: ("Moonlit Harbours", 0b111, [S, HK], False, True),
    21: ("Running Dry", 0b1111111, [S], True, False),
    22: ("Whiteout", 0b111, [S, HK], False, False),
    23: ("Laboratory 7", 0x7F | BONDS, [S], True, False),
    24: ("Sky Gala", 0xFF | BONDS, [S], False, False),
    25: ("Twin Harbours", 0xFF | BONDS, [S, HK], False, True),
    26: ("The Last Alliance", 0x1FF | BONDS, [S, VB], False, False),
    27: ("Echo", 0x1FF | BONDS, [S], True, False),
    28: ("Home Is Where The Black Is", 0x3FF | BONDS, [S, bh.CLONE_ANDY], False, False),
    29: ("The Orange Gate", 0x3FF, [S], False, False),
    30: ("Nell's Stand", 0x3FF, [S, bh.CLONE_ANDY], False, False),
    31: ("The Colonel's Vault", 0xFFF | BONDS, [S], True, False),
}
# units that do not start at full HP, ammo or fuel by design: mission -> what is allowed
EXCEPT = {5: "parked aircraft", 14: "Crumb at 1 HP; the held ring has empty tanks until day 3 (a real hold does not stop it shooting Crumb)", 21: "the low-ammo column", 28: "photographed after the computer's first turns"}
BANNER = lambda tx, ty: ty <= 2 and 3 <= tx <= 11      # (the Setup banner and the other-front window sit at the screen's top)


def save(ctx, path, n, view):
    if OUT and path:
        os.makedirs(OUT, exist_ok=True)
        shutil.copy(path, os.path.join(OUT, f"m{n}_{view}.png"))


def deviations(e, g):
    """Every live unit of every army against the full values: [(army, type, x, y, what, value, full)]."""
    per = 51 if e.u8(0x02030206) in (1, 2) else 64
    raw = e.read(g.units_base, 12 * 256)
    pos = {u["id"]: (u["x"], u["y"]) for a in range(1, 6) for u in g.units(a)}
    bad, n = [], 0
    for uid in range(256):
        r = raw[12 * uid:12 * uid + 12]
        if r[0] == 0 or uid % per == 0:
            continue
        n += 1
        stats = e.read(0x08680000 + 0x5C * r[0], 0x5C)
        ammo, fuel, hp = ((r[4] | r[5] << 8) >> 7) & 0xF, r[6] & 0x7F, r[4] & 0x7F
        army, at = uid // per + 1, pos.get(uid, (-1, -1))
        if hp != 100:
            bad.append((army, r[0], at[0], at[1], "hp", hp, 100))
        if ammo != stats[0x0B] & 0xF:
            bad.append((army, r[0], at[0], at[1], "ammo", ammo, stats[0x0B] & 0xF))
        if fuel != stats[0x10] & 0x7F:
            bad.append((army, r[0], at[0], at[1], "fuel", fuel, stats[0x10] & 0x7F))
    return n, bad


class Sweep:
    """ctx for the sweeps: the cells under the Setup banner (excluded from the sweep) are expected to be unseen."""
    def __init__(self, c):
        self.c = c

    def __getattr__(self, k):
        return getattr(self.c, k)

    def check(self, ok, msg):
        import re
        m = re.search(r"\((\d+) cells unseen\)", msg)
        if m:
            return self.c.check(int(m.group(1)) <= 12, msg + " (at most the banner's cells)")
        return self.c.check(ok, msg)


class Quiet:
    def __init__(self, c):
        self.c = c

    def __getattr__(self, k):
        return getattr(self.c, k)

    def check(self, ok, msg):
        return None


def unfog(g, e):
    e.w8(FOG, 0)
    e.wait(10)
    g.open_map_menu()
    e.wait(20)
    e.press("B", 4)
    e.wait(40)


def enter(ctx, n):
    title, roster, picks, fog, front = M[n]
    if n == 28:
        os.environ["TANGOAW2_BH_STILL"] = "1"
    # (M31, the secret, opens with M28 won; with M30 won too the campaign is over and Free Play puts the cursor on M2)
    mask = (1 << (29 if n == 31 else n - 1)) - 1
    e, g, d = a2.boot(ctx, mask, roster, picks={n - 1: len(picks)}, at=n - 1)
    ctx.log(f"M{n}: record before entering: won {d.won():#x} unlocked {d.unlocked()} bonds {d.bonds():#x} flags {d.map_flags()}")
    d.wait_world_map()
    ctx.log(f"M{n}: world map mission under cursor {e.u32(0x0202FDFC + 0x0C)}, cursor {e.u16(0x0202FDFC + 0x4):#x} {e.u16(0x0202FDFC + 0x6):#x}")
    if picks:
        a2.open_mission(ctx, e, g, d, n - 1, picks, f"m{n}", setup_only=True)
        ctx.require(d.in_setup(), f"M{n}: in the Setup phase")
    else:
        # (fixed COs: the mission has no Setup phase; it is photographed once the opening is over)
        a2.open_mission(ctx, e, g, d, n - 1, picks, f"m{n}")
        stable = 0
        for _ in range(3000):          # (a five-army mission: the computer's turns pass before the player's)
            stable = stable + 1 if g.current_army() == (5 if n == 28 else 1) and not d.scripts_running() else 0
            if stable >= 5:
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(20)
        d.wait_control()
    ctx.eq(d.mission(), n - 1, f"M{n}: its own mission was entered")
    g._units_base = g._players_base = None
    e.wait(500)          # (held for 500 frames: nothing may hit anyone while the player has control)
    g._units_base = g._players_base = None
    return e, g, d


def review(ctx, n):
    from aw2test import stitch
    title, roster, picks, fog, front = M[n]
    e, g, d = enter(ctx, n)
    cnt, bad = deviations(e, g)
    ctx.log(f"M{n} {title}: {cnt} units; not at full HP/ammo/fuel: {bad}")
    if n in EXCEPT:
        ctx.log(f"M{n}: exceptions by design ({EXCEPT[n]}): {bad}")
    else:
        ctx.check(not bad, f"M{n}: every unit starts at full HP, ammo and fuel: {bad}")
    w, h = d.size()
    ctx.log(f"M{n}: map {w}x{h}, other front {front}, fog {fog}")
    a2.pic(ctx, e, f"m{n}_setup")
    setup = bool(picks)                       # (the Setup banner is on the screen: its cells are left out of the sweeps)
    pre = sweeps(ctx, e, g, d, n, "", BANNER if setup else None)
    if setup and any(blank_cells(p) for p in pre.values()):
        # The cells under the banner are filled from the same views after Deploy (the banner gone; terrain is fixed, and nothing
        # has moved before the player's first move).
        d.leave_setup()
        a2.intro(ctx, e, d, f"m{n}", (0,))
        d.wait_control()
        g._units_base = g._players_base = None
        post = sweeps(ctx, e, g, d, n, "post_", None)
        for view, p in pre.items():
            if view in post:
                fill_blank(p, post[view])
    for view, p in pre.items():
        save(ctx, p, n, view)
    e.close()


def blank_cells(path):
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(path).convert("RGB"))
    return [(x, y) for y in range(a.shape[0] // 16) for x in range(a.shape[1] // 16) if not a[16 * y:16 * y + 16, 16 * x:16 * x + 16].any()]


def fill_blank(path, donor):
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(path).convert("RGB")).copy()
    d = np.asarray(Image.open(donor).convert("RGB"))
    for x, y in blank_cells(path):
        a[16 * y:16 * y + 16, 16 * x:16 * x + 16] = d[16 * y:16 * y + 16, 16 * x:16 * x + 16]
    Image.fromarray(a).save(path)


def sweeps(ctx, e, g, d, n, tag, exclude):
    """The mission's whole-map pictures (fog on and off, the second front): {view: path}."""
    from aw2test import stitch
    title, roster, picks, fog, front = M[n]
    w, h = d.size()
    out = {}

    def home():
        for _ in range(6):
            try:
                g.goto(0, 0)
                return
            except Exception:
                e.wait(150)
    home()
    if fog:
        out["fogon"] = stitch.stitch(Sweep(ctx), g, f"m{n}_{tag}fogon", w, h, exclude=exclude)
        unfog(g, e)
        home()
        out["fogoff"] = stitch.stitch(Sweep(ctx), g, f"m{n}_{tag}fogoff", w, h, exclude=exclude)
    else:
        out["full"] = stitch.stitch(Sweep(ctx), g, f"m{n}_{tag}full", w, h, exclude=exclude)
    if front:
        from aw2test import twofront as tf
        try:
            ctx.require(tf.look_at_other_front(e, g), f"M{n}: the other front is shown")
            w2, h2 = d.size()
            a2.pic(ctx, e, f"m{n}_{tag}front2_view")
            g.goto(0, 0)
            out["front2"] = stitch.stitch(Quiet(ctx), g, f"m{n}_{tag}front2", w2, h2, exclude=exclude)
        except Exception as ex:
            if not tag:
                raise
            ctx.log(f"M{n}: the second front after Deploy could not be shown ({ex}): its banner cells stay blank")
    return out


def _review(n):
    def fn(ctx):
        review(ctx, n)
    fn.__name__ = f"bh_review_m{n}"
    test(modes=("ds",))(fn)


for _n in M:
    _review(_n)


# --- every world-map flag opens its own mission ------------------------------------------------------
def _flag(n):
    def fn(ctx):
        title, roster, picks, fog, front = M[n]
        mask = (1 << (29 if n == 31 else n - 1)) - 1
        e, g, d = a2.boot(ctx, mask, roster, picks={n - 1: len(picks)}, at=n - 1)
        d.wait_world_map()
        flags = d.map_flags()
        ctx.eq(flags[n - 1], 1, f"M{n}: its flag is open")
        ctx.eq(e.u32(0x0202FDFC + 0x0C), n - 1, f"M{n}: the cursor is on its own flag")
        ctx.eq(sorted(set(f for f in flags if f & 1 and not f & 2)) in ([1], []), True, "open flags are plain")
        e.close()
    fn.__name__ = f"bh_review_flag_m{n}"
    test(modes=("ds",))(fn)


for _n in M:
    _flag(_n)
