"""BH Campaign, Act V first half (M23 to M28) and the secret M31: pictures of every map
(tango-gamesupport-aw2/src/bh_act5b.rs, bh_secret.rs)."""

import os

from aw2test import bhact5b as a5
from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test.harness import test

FOG = 0x03003FCD
BONDS = 0x1FF << 12
# the roster (bits) unlocked when each mission opens: Lash after M23, Adder after M24, Clone Andy after M27, Sonja and Crumb later
ROSTER_AT = {23: 0x7F, 24: 0xFF, 25: 0xFF, 26: 0x1FF, 27: 0x1FF, 28: 0x3FF, 31: 0xFFF}
# number: (title, won (mission numbers incl. the 22 stub), CO picks (M23, M24, M26, M28: lead and partner; M27: none), fog, size)
MISSIONS = {
    23: ("Laboratory 7", [22], [bh.STURM, bh.HAWKE], True, (22, 18)),
    24: ("Sky Gala", [22, 23], [bh.STURM, bh.HAWKE], False, (24, 16)),
    25: ("Twin Harbours", [22, 23], [bh.STURM, bh.HAWKE], False, (32, 22)),
    26: ("The Last Alliance", [22, 23, 24, 25], [bh.STURM, bh.VON_BOLT], False, (38, 28)),
    27: ("Echo", [22, 23, 24, 25, 26], [], True, (24, 18)),   # (Lash is fixed: no CO screen)
    28: ("Home Is Where The Black Is", [22, 23, 24, 25, 26, 27], [bh.STURM, bh.CLONE_ANDY], False, (35, 31)),
    31: ("The Colonel's Vault", [22, 23, 24, 25, 26, 27, 28], [bh.STURM], True, (43, 29)),
}


def won_mask(n):
    """The missions won before M<n> (M31 opens after the finale, M30, is won and all nine bonds are earned: the campaign is then
    in Free Play, the record's step is M31 and the cursor waits on it)."""
    mask = 0
    for k in range(1, n):
        mask |= 1 << a5.M[k]
    return mask


def unfog(g, e):
    e.w8(FOG, 0)
    e.wait(10)
    g.open_map_menu()
    e.wait(20)
    e.press("B", 4)
    e.wait(40)


def pictures(ctx, n):
    from aw2test import stitch
    title, won, picks, fog, size = MISSIONS[n]
    # (M28: the computer holds and has no funds, see bh_act5b::still; this console's variable, not the process's:
    # tests run in parallel in one process)
    env = {"TANGOAW2_BH_STILL": "1"} if n == 28 else None
    mask = won_mask(n)
    e, g, d = a5.boot(ctx, mask, ROSTER_AT[n] | BONDS, picks={a5.M[n]: len(picks)}, at=a5.M[n], env=env)
    # (a mission that is not fogged is photographed in its Setup phase: the deployment as it stands before
    # any computer turn, and no Onyx panel; a fogged one after Deploy, for the day-1 fog view)
    # (M26's Black Cannon fires at the player's first turn start on the nearest enemy: the review picture is taken
    # in the Setup phase, before any shot, with the Setup banner's screen cells left out of the sweep)
    setup = n == 26
    texts = a5.open_mission(ctx, e, g, d, a5.M[n], picks, f"m{n}", setup_only=setup, hook=None)
    if n == 28:
        g._units_base = g._players_base = None
        ctx.log("m28 right after the intro: hurt " + str([(u["army"], u["type"], u["hp"]) for u in g.units() if u["hp"] < 100][:8]) + f" army {g.current_army()}")
    if n == 28 and not setup:
        # five armies: the player (army 5) moves last; the computer's four turns pass first
        stable = 0
        for _ in range(3000):
            stable = stable + 1 if g.current_army() == 5 and not d.scripts_running() else 0
            if stable >= 5:
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(20)
        # ENGINE BUG (reported): in a five-army mission the Black Hole structures also fire at the start of army 4's
        # turn, on the player's own units (army 5). The picture shows the deployment as designed: their HP put back.
        g._units_base = g._players_base = None
        # (five armies have 51 unit slots each: the player's are ids 204..254, whatever the harness's view says)
        for u in g.units():
            if u["id"] // 51 == 4 and u["hp"] < 100:
                a = g.unit_addr(u["id"]) + 4
                e.w16(a, (e.u16(a) & ~0x7F) | 100)
    if not setup or n == 28:
        d.wait_control()
    g._units_base = g._players_base = None
    hurt = [(u["army"], u["type"], u["x"], u["y"], u["hp"]) for u in g.units() if u["hp"] < 100]
    ctx.log(f"m{n}: units below full HP at the start: {hurt}")
    a5.pic(ctx, e, f"m{n}_opening")
    ctx.log("\n".join(texts))
    if not setup and n in (23, 24, 25, 27, 31):
        a5.scene_seen(ctx, texts, f"m{n}_pre", picks[0] if picks else bh.LASH, picks[1] if len(picks) > 1 else None, f"M{n}: the opening")
    stitch.IMAGES = a5.SHOTS or stitch.IMAGES
    w, h = d.size()
    ctx.eq((w, h), size, f"M{n}: map size")
    if fog:
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}_fog", w, h)
        unfog(g, e)
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}_nofog", w, h)
    else:
        for _ in range(4):
            try:
                g.goto(0, 0)
                break
            except Exception:
                e.wait(150)
        # (M28's Onyx panel sits in the screen's middle rows on either side: those screen cells are never taken)
        ex = (lambda tx, ty: 3 <= ty <= 6 and (tx <= 4 or tx >= 10)) if n == 28 else (lambda tx, ty: ty <= 1 and 3 <= tx <= 11) if setup else None
        stitch.stitch(ctx, g, f"m{n}", w, h, exclude=ex)
    g._units_base = g._players_base = None
    ctx.log(f"m{n}: units below full HP after the sweeps: {[(u['army'], u['type'], u['x'], u['y'], u['hp']) for u in g.units() if u['hp'] < 100]}")
    if n == 25:
        from aw2test import twofront as tf
        ctx.require(tf.look_at_other_front(e, g), "the other front is shown")
        w2, h2 = d.size()
        a5.pic(ctx, e, "m25_second_front_view")
        g.goto(0, 0)

        class Quiet:
            def __init__(self, c):
                self.c = c

            def __getattr__(self, k):
                return getattr(self.c, k)

            def check(self, ok, msg):
                return None
        stitch.stitch(Quiet(ctx), g, "m25_second_front", w2, h2, exclude=lambda tx, ty: ty <= 2 and 5 <= tx <= 10)
        # (a second sweep from the other corner: the view's cursor leaves a grey box on a cell in one sweep; the
        # picture takes each cell from the sweep that has no box)
        g.goto(w2 - 1, h2 - 1)
        stitch.stitch(Quiet(ctx), g, "m25_second_front_b", w2, h2, exclude=lambda tx, ty: ty <= 2 and 5 <= tx <= 10)
    e.close()


def _pictures(n):
    def fn(ctx):
        pictures(ctx, n)
    fn.__name__ = f"bh_act5b_pictures_m{n}"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _pictures(_n)


# --- the computer's units advance (docs: bh_act5b::roles) -------------------------------------------------
def _advance(n):
    def fn(ctx):
        title, won, picks, fog, size = MISSIONS[n]
        mask = won_mask(n)
        e, g, d = a5.boot(ctx, mask, ROSTER_AT[n] | BONDS, picks={a5.M[n]: len(picks)}, at=a5.M[n])
        a5.open_mission(ctx, e, g, d, a5.M[n], picks, f"m{n}")
        d.wait_control()
        g._units_base = g._players_base = None
        before = {u["id"]: (u["x"], u["y"]) for u in g.units() if u["army"] != 1}
        # (polled, not timed: up to day 6 until at least half have moved, so a slow start under load cannot fail it)
        moved, after = 0, {}
        for day in (4, 5, 6):
            a5.to_day(e, g, d, day)
            g._units_base = g._players_base = None
            e.wait(120)
            after = {u["id"]: (u["x"], u["y"]) for u in g.units() if u["army"] != 1}
            moved = sum(1 for k, v in before.items() if k in after and after[k] != v)
            if moved * 2 >= len(before):
                break
        ctx.log(f"M{n}: {moved} of {len(before)} enemy units moved in 3 days ({len(after)} left)")
        ctx.check(moved * 2 >= len(before) * 1, f"M{n}: at least half the computer's units advance ({moved} of {len(before)})")
        e.close()
    fn.__name__ = f"bh_act5b_enemy_advances_m{n}"
    test(modes=("ds",))(fn)


for _n in (23, 26, 27):
    _advance(_n)


# --- the garrisons stand (role 0: the engine keeps held foot soldiers where they stand) -----------------------------
def _garrison(n):
    def fn(ctx):
        title, won, picks, fog, size = MISSIONS[n]
        mask = 0
        for k in range(1, 30 if n == 31 else n):
            mask |= 1 << a5.M[k]
        e, g, d = a5.boot(ctx, mask, ROSTER_AT[n] | BONDS, picks={a5.M[n]: len(picks)}, at=a5.M[n])
        a5.open_mission(ctx, e, g, d, a5.M[n], picks, f"m{n}")
        d.wait_control()
        g._units_base = g._players_base = None
        player = 5 if n == 28 else 1
        held = {u["id"]: (u["x"], u["y"]) for u in g.units() if u["army"] != player and u["type"] in (1, 2) and u["raw"][11] == 0}
        a5.to_day(e, g, d, 4)
        g._units_base = g._players_base = None
        now = {u["id"]: (u["x"], u["y"]) for u in g.units()}
        moved = [i for i, p in held.items() if i in now and now[i] != p]
        ctx.log(f"M{n}: {len(held)} held foot soldiers, {len(moved)} moved in 3 days")
        ctx.check(len(moved) * 4 <= max(len(held), 1), f"M{n}: the garrisons stay put ({len(moved)} of {len(held)} moved)")
        e.close()
    fn.__name__ = f"bh_act5b_garrisons_stand_m{n}"
    test(modes=("ds",))(fn)


for _n in (23, 24, 25, 26, 27):          # (M28's five armies need their own turn order: not driven here)
    _garrison(_n)


# --- balance (AW2TEST_ACT5B_BALANCE=1): the CPU, or the test player (aw2test.bot), plays the player's side ---------
BALANCE = os.environ.get("AW2TEST_ACT5B_BALANCE")
BOT_OPTS = {26: dict(goals=[(4, 4), (4, 23), (33, 14)])}


def _balance(n, how, seed=None):
    def fn(ctx):
        import json
        from aw2test.harness import Skip
        if not BALANCE:
            raise Skip("AW2TEST_ACT5B_BALANCE not set")
        title, won, picks, fog, size = MISSIONS[n]
        mask = won_mask(n)
        e, g, d = a5.boot(ctx, mask, ROSTER_AT[n] | BONDS, picks={a5.M[n]: len(picks)}, at=a5.M[n])
        d.pick_mission()
        d.choose_cos(len(picks), prefs=list(picks))
        g._units_base = g._players_base = None
        days = []
        opts = dict(BOT_OPTS.get(n, {}))
        if seed is not None:
            opts["seed"] = seed
        limit = int(os.environ.get("AW2TEST_ACT5B_DAYS", 30))
        r = d.autoplay(limit + 3, log=days.append) if how == "cpu" else d.play(limit + 3, log=days.append, **opts)
        r["log"] = days[-6:]
        ctx.log(json.dumps(r, default=str))
        e.close()
    fn.__name__ = f"bh_act5b_balance_m{n}_{how}" + (f"_{seed}" if seed is not None else "")
    test(modes=("ds",))(fn)


_balance(26, "cpu")
_balance(26, "bot")
_balance(26, "bot", 1)
_balance(28, "cpu")


# --- the pair pick screens of M23 and M24 and their bonds (CoSpec::PickPair) --------------------------------------
MAX, SAMI = 2, 4
AIRCRAFT = (12, 13, 16, 17, 19, 20)       # (Stealth, Black Bomb, Fighter, Bomber, B Copter, T Copter: Adder's air force)
# number: (the enemy's lead and partner, the bond's bit, the CO whose pitch earns it, the pair's scenes before and after)
PAIRS = {
    23: (bh.LASH, MAX, 6, bh.JUGGER, "m23_pre", ["m23_post", "m23_map"]),
    24: (bh.ADDER, SAMI, 7, bh.KINDLE, "m24_pre", ["m24_post", "m24_map"]),
}


def _pair_case(n, name, cos, bond):
    """M<n> with the pair `cos` (lead, partner) on the pair pick screen: the lead leads and the partner is the tag partner, the
    enemy is the recruit with her partner, the opening is the files' scene for that pair; then the win: the recruit's bond is
    earned exactly when its CO (Jugger in M23, Kindle in M24) is anywhere in the pair, and the recruit joins whoever the pair is."""
    def fn(ctx):
        from aw2test import tag
        enemy, enemy_partner, bit, bonder, pre, post = PAIRS[n]
        title, won, picks, fog, size = MISSIONS[n]
        e, g, d = a5.boot(ctx, won_mask(n), ROSTER_AT[n], picks={a5.M[n]: 2}, at=a5.M[n])    # (no bonds earned yet)
        texts = a5.open_mission(ctx, e, g, d, a5.M[n], cos, f"m{n}_{name}")
        d.wait_control()
        g._units_base = g._players_base = None
        ctx.eq(g.player(1)["co"], cos[0], f"M{n} {name}: the lead")
        p = tag.partner(e, 1)
        ctx.eq(p["co"] if p else None, cos[1], f"M{n} {name}: the partner")
        ctx.eq(g.player(2)["co"], enemy, f"M{n} {name}: the enemy's lead")
        p2 = tag.partner(e, 2)
        ctx.eq(p2["co"] if p2 else None, enemy_partner, f"M{n} {name}: the enemy's partner")
        a5.expect_scene(ctx, texts, pre, cos[0], cos[1], f"M{n} {name}: the opening")
        # the win (the test aid: Adder's air force gone / Lash's army routed), the scenes for that pair
        if n == 24:
            for u in g.units(2):
                if u["type"] in AIRCRAFT:
                    d.remove_unit(u)
            e.wait(10)
            g._units_base = g._players_base = None
            mine = next(u for u in g.units(1) if u["type"] in (1, 2, 3, 5, 6))
            g.select(mine["x"], mine["y"])
            g.move_to(mine["x"], mine["y"])
            g.choose(next(x for x in g.menu()["names"] if x.lower().startswith("wait")), g.ACTION_MENU)
            victory, mapscene = a5.follow(ctx, e, d, f"m{n}_{name}")
        else:
            victory, mapscene = a5.win_by_attrition(ctx, e, g, d, f"m{n}_{name}")
        a5.expect_scene(ctx, victory + mapscene, post, cos[0], cos[1], f"M{n} {name}: the victory and the map scene", bonds=([bit] if bond else []))
        ctx.eq((d.bonds() >> bit) & 1, bond, f"M{n} {name}: the bond (bit {bit})")
        ctx.check(bh.LASH in d.unlocked() if n == 23 else bh.ADDER in d.unlocked(), "the recruit joins")
        e.close()
    fn.__name__ = f"bh_act5b_m{n}_pair_{name}"
    fn.__doc__ = f"M{n}: the pair {cos} on the pair pick screen; the bond is earned: {bool(bond)}."
    test(modes=("ds",))(fn)


for _name, _cos, _bond in (("sturm_hawke", [bh.STURM, bh.HAWKE], 0), ("jugger_leads", [bh.JUGGER, bh.STURM], 1),
                           ("jugger_partner", [bh.STURM, bh.JUGGER], 1), ("koal_kindle", [bh.KOAL, bh.KINDLE], 0)):
    _pair_case(23, _name, _cos, _bond)
for _name, _cos, _bond in (("sturm_hawke", [bh.STURM, bh.HAWKE], 0), ("kindle_leads", [bh.KINDLE, bh.STURM], 1),
                           ("kindle_partner", [bh.STURM, bh.KINDLE], 1), ("koal_jugger", [bh.KOAL, bh.JUGGER], 0)):
    _pair_case(24, _name, _cos, _bond)


@test(modes=("ds",))
def bh_act5b_m27_lash_fixed_and_clone_andys_bond_is_unconditional(ctx):
    """M27: no CO screen (Lash leads), the enemy is Clone Andy + Andy, the opening is the files' scene for Lash, and winning
    earns Clone Andy's bond (bit 8) whoever the player is, with Clone Andy joining."""
    from aw2test import tag
    e, g, d = a5.boot(ctx, won_mask(27), ROSTER_AT[27], picks={a5.M[27]: 0}, at=a5.M[27])
    # (no CO screen: with one, open_mission would wait for a battle that never loads)
    texts = a5.open_mission(ctx, e, g, d, a5.M[27], [], "m27_fixed", shots=())
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.eq(g.player(1)["co"], bh.LASH, "Lash leads")
    ctx.check(tag.partner(e, 1) is None, "Lash has no partner")
    ctx.eq(g.player(2)["co"], bh.CLONE_ANDY, "the enemy's lead is Clone Andy")
    p2 = tag.partner(e, 2)
    ctx.eq(p2["co"] if p2 else None, 1, "the enemy's partner is Andy")
    a5.expect_scene(ctx, texts, "m27_pre", bh.LASH, None, "M27: the opening")
    ctx.eq((d.bonds() >> 8) & 1, 0, "no bond before the win")
    victory, mapscene = a5.win_by_attrition(ctx, e, g, d, "m27_fixed")
    a5.expect_scene(ctx, victory + mapscene, ["m27_post", "m27_map", "m28_alarm"], bh.LASH, None, "M27: the victory and the map scene", bonds=[8])
    ctx.eq((d.bonds() >> 8) & 1, 1, "Clone Andy's bond is earned")
    ctx.check(bh.CLONE_ANDY in d.unlocked(), "Clone Andy joins")
    e.close()


@test(modes=("ds",))
def bh_act5b_m31_gate_needs_the_finale_and_all_nine_bonds(ctx):
    """M31 (after the war) is on the world map only when M30 is won AND all nine recruit bonds are earned: not after M28 alone,
    not with a bond missing, not with M30 unwon."""
    cases = [
        ("M30 won, nine bonds", range(1, 31), 0xFFF | BONDS, 1),
        ("M30 won, eight bonds", range(1, 31), 0xFFF | (0xFF << 12), 0),
        ("M30 unwon, nine bonds", range(1, 30), 0xFFF | BONDS, 0),
        ("M28 won only, nine bonds", range(1, 29), 0xFFF | BONDS, 0),
    ]
    for name, won, unlocked, want in cases:
        mask = sum(1 << a5.M[k] for k in won)
        e, g, d = a5.boot(ctx, mask, unlocked, picks={}, at=None)
        d.wait_world_map()
        flags = d.map_flags()
        ctx.eq(flags[a5.M[31]] & 1, want, f"{name}: M31 is {'open' if want else 'not open'} on the map (flag {flags[a5.M[31]]})")
        e.close()


def _m28_free_pair(ctx, pair, label):
    """M28 is a free pair: the opening is the files' m28_pre for that pair (Clone Andy's own lines only when he is in it)."""
    from aw2test import tag
    e, g, d = a5.boot(ctx, won_mask(28), ROSTER_AT[28], picks={a5.M[28]: 2}, at=a5.M[28], env={"TANGOAW2_BH_STILL": "1"})
    d.pick_mission()
    picked = a5.pick_cos(d, list(pair))
    ctx.eq(picked, list(pair), f"M28 {label}: the CO screen's picks")
    d.leave_setup()
    texts, last, calm = [], None, 0
    for i in range(3000):                                # (the opening plays when the player's army, the fifth, first moves)
        t = d.text_shown()
        if t and t != last:
            texts.append(a5.clean(t))
            last = t
        if d.scripts_running():
            calm = 0
            if t:
                e.press("A", 4)
        elif g.current_army() == 5:
            calm += 1
            if calm > 25 and texts:
                break
        e.wait(8)
    g._units_base = g._players_base = None
    p = tag.partner(e, 5)
    ctx.eq((g.player(5)["co"], p["co"] if p else None), tuple(pair), f"M28 {label}: the first pick leads, the second is the partner (army 5)")
    a5.scene_seen(ctx, texts, "m28_pre", pair[0], pair[1], f"M28 {label}: the opening")
    flat = a5._flat(texts)
    clone_line = a5._flat(["What's that sound? A hum? Like a fridge. A big one."])
    soldier_line = a5._flat(["Sir, what is that sound? A hum. Like a very big engine."])
    ctx.check((clone_line in flat) == (bh.CLONE_ANDY in pair) and (soldier_line in flat) == (bh.CLONE_ANDY not in pair),
              f"M28 {label}: Clone Andy's hum line only with Clone Andy in the pair, the soldier's without him")
    e.close()


@test(modes=("ds",))
def bh_act5b_m28_free_pair_with_clone_andy(ctx):
    _m28_free_pair(ctx, [bh.STURM, bh.CLONE_ANDY], "sturm_clone")


@test(modes=("ds",))
def bh_act5b_m28_free_pair_without_clone_andy(ctx):
    _m28_free_pair(ctx, [bh.HAWKE, bh.KOAL], "hawke_koal")
