"""The computer attacks a human's inventions (cpu_inventions.rs): in the BH Campaign and in Versus
with the pack; nowhere else.

The BH Campaign tests play the fixture mission `bh_campaign::inventions_def`
(TANGOAW2_BH_FEATURES=inventions): the player (Black Hole) holds a Black Cannon (12, 7), an Obelisk
(5, 7), a Crystal (9, 9), a minicannon (16, 9) and a Black Factory (7, 13), the numbers being the squares
the units aim at; Green Earth's computer comes from the north east with tanks, artillery, rockets and
infantry. `OFF` (RAM 0x0203FE6E, 0xA5: a development byte) switches the module off: the computer as it was
before it. Pictures: AW2TEST_PICS=<dir> (3x, with the invention's hit points in the terrain panel)."""

import os
import re
import shutil
import subprocess

from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game, NavError
from aw2test.harness import Skip, test

PICS = os.environ.get("AW2TEST_PICS")
INV = 0x02028360
ENV = {"TANGOAW2_BH_FEATURES": "inventions"}
OFF = 0x0203FE6E          # cpu_inventions::DEV_OFF (0xA5: off)
DAY = 0x03004080
UNIT_TABLE = 0x085D5ABC
KINDS = {1: "laser", 2: "volcano", 3: "cannon", 4: "mini", 5: "deathray", 7: "factory"}
# The squares units aim at (the fixture's inventions), by name.
AIM = {"cannon": (12, 7), "obelisk": (5, 7), "crystal": (9, 9), "mini": (16, 9), "factory": (7, 13)}
# Where each invention stands (the entry's corner).
CORNER = {(11, 5): "cannon", (4, 5): "obelisk", (9, 9): "crystal", (16, 9): "mini", (6, 10): "factory"}
FULL = {"cannon": 99, "obelisk": 99, "crystal": 99, "mini": 99, "factory": 200}


def save_copy(ctx, name="inv.sav"):
    save = os.path.join(ctx.out, name)
    shutil.copyfile(paths.base_save(), save)
    return save


def boot_inv(ctx, save=None, env=None):
    e = Emu(save=save or save_copy(ctx), ds=ctx.ds, env=dict(ENV, **(env or {})))
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = bh.BhCampaign(g)
    d.picks = {0: 0}
    return e, g, d


def fill_ammo(e, g):
    """The mission's deployed units start with no ammunition (the format has no field for it): every unit gets its full load."""
    for u in g.units():
        a = g.unit_addr(u["id"])
        mx = e.u8(UNIT_TABLE + 0x5C * u["type"] + 0x0B) & 0xF
        w = e.u16(a + 4)
        e.w16(a + 4, (w & ~0x780) | (mx << 7))


def start_inv(ctx, off=False, env=None, save=None, mission=0):
    e, g, d = boot_inv(ctx, save=save, env=env)
    d.picks = {0: 0, 1: 0}
    d.start_at(won_mask=(1 << mission) - 1, unlocked_mask=0b1)
    d.pick_mission()
    d.wait_map()
    g._units_base = g._players_base = None
    if off:
        e.w8(OFF, 0xA5)
    fill_ammo(e, g)
    return e, g, d


def inventions(e):
    """The invention list: {name: hp}; a destroyed one has hp 0 or is gone from the list."""
    out = {}
    for k in range(16):
        a = INV + 8 * k
        w = e.u16(a + 2)
        kind = (w >> 6) & 15
        if kind == 0:
            break
        name = CORNER.get((e.u8(a), e.u8(a + 1)), KINDS.get(kind, kind))
        out[name] = e.u8(a + 4)
    return {n: out.get(n, 0) for n in AIM}


def cpu_units(g, army=2):
    return [(u["id"], u["type"], u["x"], u["y"], u["hp"]) for u in g.units(army=army)]


def next_day(e, g, d):
    g.end_turn(human=1, max_frames=60000)
    g._units_base = g._players_base = None
    d.wait_control()


def near(units, target, types=None):
    """The shortest distance from a unit (of `types`) to a square."""
    ds = [abs(x - target[0]) + abs(y - target[1]) for _, t, x, y, _ in units if types is None or t in types]
    return min(ds) if ds else 99


def in_range(e, units, targets=None):
    """How many of the units stand where their weapon reaches an invention's square."""
    n = 0
    for _, t, x, y, _ in units:
        rmin, rmax = max(1, e.u8(UNIT_TABLE + 0x5C * t + 0x0E)), max(1, e.u8(UNIT_TABLE + 0x5C * t + 0x0F))
        if any(rmin <= abs(x - ax) + abs(y - ay) <= rmax for ax, ay in (targets or AIM.values())):
            n += 1
    return n


def held(e, rec):
    """Unit-days spent in range of an invention that still stood that day."""
    return sum(in_range(e, r["cpu"], [AIM[n] for n, hp in r["inv"].items() if hp > 0]) for r in rec)


def logged(e, what):
    return [l for l in e.decisions() if l.startswith(what)]


def pic(ctx, g, name, at=None):
    """A picture with the cursor on a square (the terrain panel then shows an invention's hit points)."""
    if not PICS:
        return
    if at is not None:
        g.goto(*at)
        g.e.wait(100)
    bmp = g.e.shot(os.path.join(ctx.out, name))
    os.makedirs(PICS, exist_ok=True)
    from PIL import Image
    im = Image.open(bmp)
    im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(os.path.join(PICS, name + ".png"))


def play_mission(ctx, off, days, pics=None):
    """The fixture played for `days` days (the player passes): per day the inventions' hit points and the computer's units
    after its turn. Returns (emulator, game, campaign, per-day records)."""
    e, g, d = start_inv(ctx, off=off)
    rec = []
    for day in range(1, days + 1):
        rec.append({"day": e.u16(DAY), "inv": inventions(e), "cpu": cpu_units(g)})
        if pics and day in pics:
            pics[day](ctx, g)
        next_day(e, g, d)
    rec.append({"day": e.u16(DAY), "inv": inventions(e), "cpu": cpu_units(g)})
    return e, g, d, rec


@test(modes=("ds",))
def cpu_inv_bh_campaign_cpu_marches_on_and_hits_inventions(ctx):
    """BH Campaign: over nine days the computer's units go for the player's inventions and damage them, the
    threatening ones first (the Black Cannon); with the module off (the computer as before) nothing touches them."""
    e, g, d, on = play_mission(ctx, off=False, days=9)
    for r in on:
        ctx.log(f"day {r['day']}: {r['inv']}  cpu {r['cpu']}")
    strikes = logged(e, "inv strike")
    goals = logged(e, "inv goal")
    ctx.log("\n".join(strikes[:12]))
    last = on[-1]["inv"]
    ctx.check(len(strikes) >= 6, f"the computer struck inventions {len(strikes)} times")
    ctx.check(last["cannon"] < 99, f"the Black Cannon was hit ({last['cannon']} of 99 hit points left)")
    ctx.check(sum(last.values()) < sum(FULL.values()) - 100, f"the inventions lost hit points: {last}")
    # The threatening cannon first for those that can reach it from outside its cone: the first artillery sent goes for it,
    # and no tank or infantry is sent into the cone's front while it stands whole.
    ranged = [l for l in goals if " type 10 " in l or " type 11 " in l]
    ctx.check(ranged and "for the cannon" in ranged[0], f"the first artillery sent goes for the Black Cannon, the invention that hurts the computer most: {ranged[:1]}")
    melee_in = [l for l in goals if "for the cannon" in l and re.search(r" type (1|3|5) ", l) and "(hp 99)" in l]
    ctx.eq(melee_in, [], "no tank is sent in front of the whole Black Cannon (its cone costs more than it gains)")
    ctx.check(goals, "units were sent (goals logged)")
    pic(ctx, g, "cpu_after_on_cannon", at=AIM["cannon"])
    e.close()
    # Off: the same battle with the module switched off.
    e2, g2, d2, off = play_mission(ctx, off=True, days=9)
    for r in off:
        ctx.log(f"off day {r['day']}: {r['inv']}  cpu {r['cpu']}")
    ctx.eq(off[-1]["inv"], FULL, "off: no invention loses a hit point")
    ctx.eq(logged(e2, "inv strike") + logged(e2, "inv goal"), [], "off: no strike, no goal")
    pic(ctx, g2, "cpu_after_off_cannon", at=AIM["cannon"])
    e2.close()


def play_two(ctx, off, days):
    """Mission i02 (a Black Cannon aimed at (3, 6), the player's HQ at (18, 12), a computer tank pair for it and an artillery):
    the computer's units after each of `days` days."""
    e, g, d = start_inv(ctx, off=off, mission=1)
    rec = []
    for _ in range(days):
        next_day(e, g, d)
        rec.append(cpu_units(g))
    return e, g, d, rec


@test(modes=("ds",))
def cpu_inv_units_leave_their_way_for_a_cannon(ctx):
    """A tank sent for the player's HQ (role 1) and an artillery (role 5) are given the Black Cannon far off their way
    as their goal: after five days the artillery stands in range of it (outside its cone) and has hit it, while the
    tanks, which could reach it only through its cone, play as AW2 does; the computer as before marches the pieces to the HQ."""
    e, g, d, on = play_two(ctx, False, 5)
    ctx.log(f"on: {on}")
    ctx.log("\n".join(logged(e, "inv")))
    aim = (3, 6)
    dist = lambda us: min((abs(x - aim[0]) + abs(y - aim[1]) for _, _, x, y, _ in us), default=99)
    arty = [u for u in on[-1] if u[1] == 10]
    ctx.check(arty and 2 <= dist(arty) <= 3, f"after five days the artillery is in range of the cannon, off its way south: {arty}")
    ctx.check(logged(e, "inv strike"), "the cannon was hit")
    # (no tank walks into the cannon's line for nothing: its square is in its cone, five bars of damage a turn)
    ctx.check(all(dist([u]) > 1 for u in on[-1] if u[1] == 5), f"no tank stands in front of the cannon: {[u for u in on[-1] if u[1] == 5]}")
    e.close()
    e2, g2, d2, off = play_two(ctx, True, 2)
    ctx.log(f"off: {off}")
    tanks = [u for u in off[-1] if u[1] == 5]
    ctx.check(tanks and dist(tanks) > 8, f"as before, the tanks head for the HQ and are far from the cannon after two days: {tanks}")
    e2.close()


def cone(apex, down, length, w=26, h=16):
    """The cells of a cone widening by one each side per row from its apex, down (or up)."""
    ax, ay = apex
    return {(ax + s, ay + (k if down else -k)) for k in range(length) for s in range(-k, k + 1) if 0 <= ax + s < w and 0 <= ay + (k if down else -k) < h}


CANNON_CONE = cone((12, 7), True, 10)          # the Black Cannon at (11..13, 5..7), facing down: from the middle of its front edge
MINI_CONE = cone((16, 10), True, 4)            # the minicannon at (16, 9), facing down: from the cell in front of it


@test(modes=("ds",))
def cpu_inv_firing_zones_are_the_games(ctx):
    """The cone `cpu_inventions::zone` uses for a Black Cannon (ten rows widening from the middle of its front) and a
    minicannon (four, from the cell in front of it) is the game's: nine of the computer's units are put on squares in the
    cannon's cone, in the minicannon's and outside both; when the Black Hole turn begins the cannons hit some of those in a cone
    (each fires at one) and none outside."""
    e, g, d = start_inv(ctx, off=True)
    cells = [(12, 8), (11, 9), (10, 10), (16, 10), (17, 11), (18, 12), (14, 8), (10, 8), (18, 10)]
    for u, (x, y) in zip(g.units(army=2), cells):
        d.place_unit(u, x, y)
        e.w8(g.unit_addr(u["id"]) + 0x0B, 0)        # (held in place: AW2's role 0; some move anyway)
    ids = [u["id"] for u in g.units(army=2)]
    next_day(e, g, d)
    hit_in, hit_out, seen = 0, [], []
    for uid, c in zip(ids, cells):
        u = g.unit(uid)
        lost = 100 - u["hp"]
        at = (u["x"], u["y"])
        inside = at in CANNON_CONE or at in MINI_CONE
        seen.append((uid, c, at, lost, inside))
        if lost and inside:
            hit_in += 1
        elif lost:
            hit_out.append((uid, at, lost))
    ctx.log(f"(unit, put at, now at, hit points lost, in a cone): {seen}")
    ctx.eq(hit_out, [], "no unit outside both cones lost a hit point")
    ctx.check(hit_in >= 2, f"both cannons hit units in their cones ({hit_in} units hit)")
    ctx.check(any(not s[4] and not s[3] for s in seen), "units outside the cones were left alone")
    e.close()


# --- Versus with the pack: a human army in Black Hole's colour owns a Black Factory and a Black Cannon ------------------

FACTORY_ANCHOR, CANNON_MIDDLE = 0x18D, 0x187
VERSUS_AIM = {"factory": (6, 9), "cannon": (13, 7)}      # the squares units aim at: the factory at (5..7, 6..9) (anchor (6, 8)), the cannon at (12..14, 5..7)
VS_INV = 0x02028360


def versus_map(ctx, cannon=True):
    """30x20, army 1 (human, Black Hole's colour) with its HQ at (1, 1), a Black Factory (anchor (6, 8)) and a Black Cannon
    (middle (13, 6)); army 2 (the computer, Orange Star) from the south east: tanks, artillery and rockets."""
    m = ctx.map(hq=((1, 1, 1), (2, 28, 18)))
    m.colours = [0, 5, 1, 3, 4]         # ([0] is the five-army marker; then each army's colour)
    m.terrain(6, 8, FACTORY_ANCHOR)
    if cannon:
        m.terrain(13, 6, CANNON_MIDDLE)
    for x, y, kind in [(24, 14, 5), (25, 15, 5), (24, 16, 5), (26, 14, 10), (26, 16, 10), (27, 15, 11), (23, 15, 3)]:
        m.unit(2, kind, x, y)
    return m


def versus_inventions(e):
    out = {}
    for k in range(16):
        a = VS_INV + 8 * k
        kind = (e.u16(a + 2) >> 6) & 15
        if kind == 0:
            break
        out[KINDS.get(kind, kind)] = (e.u8(a), e.u8(a + 1), e.u8(a + 4))
    return out


def play_versus(ctx, off, days, cannon=True):
    g = ctx.start(versus_map(ctx, cannon), ["andy", "vonbolt"], humans=(1,))
    e = g.e
    if off:
        e.w8(OFF, 0xA5)
    fill_ammo(e, g)
    rec = []
    for _ in range(days):
        rec.append((versus_inventions(e), cpu_units(g, 2)))
        try:
            g.end_turn(human=1, max_frames=60000)
        except NavError as ex:
            ctx.log(f"stopped after {len(rec)} days: {ex}; mine {[(u['type'], u['x'], u['y'], u['hp']) for u in g.units(army=1)]}")
            ctx.shot(g, "stopped")
            break
    return g, rec


@test(modes=("ds",))
def cpu_inv_versus_human_factory_is_marched_on_and_hit(ctx):
    """Versus with the pack, a human in Black Hole's colour: the computer's units go for its Black Factory and Black Cannon
    (its artillery sets up in range, its tanks come in beside them) and hit them; with the module off (the computer as before) it
    strikes the factory only when a unit is already in range at the start of its turn, and marches on the HQ."""
    g, on = play_versus(ctx, False, 8)
    e = g.e
    ctx.log("\n".join(f"day {k + 1}: {inv}  cpu {cpu}" for k, (inv, cpu) in enumerate(on)))
    ctx.log("\n".join(e.decisions()[:20]))
    inv0 = on[0][0]
    ctx.check("factory" in inv0 and inv0["factory"][2] == 200, f"the factory has its 200 hit points: {inv0}")
    strikes = logged(e, "inv strike")
    goals = logged(e, "inv goal")
    ctx.check(goals, "units were sent for an invention")
    ctx.check(strikes, "units hit an invention")
    last = on[-1][0]
    ctx.check(last.get("factory", (0, 0, 0))[2] < 200 or last.get("cannon", (0, 0, 0))[2] < 99 or "factory" not in last, f"an invention lost hit points: {last}")
    aims = list(VERSUS_AIM.values())
    d_on = min(near(on[3][1], a) for a in aims)
    ctx.check(d_on <= 3, f"by day 4 a computer unit is within 3 squares of an invention square ({d_on})")
    g.e.close()
    g2, off = play_versus(ctx, True, 8)
    e2 = g2.e
    ctx.log("\n".join(f"off day {k + 1}: {inv}  cpu {cpu}" for k, (inv, cpu) in enumerate(off)))
    ctx.eq(logged(e2, "inv "), [], "off: nothing logged by the module")
    d_off = min(near(off[3][1], a) for a in aims)
    ctx.log(f"day 4 distance to an invention square: on {d_on}, off {d_off}")
    e2.close()


@test(modes=("ds",))
def cpu_inv_versus_factory_alone_is_destroyed(ctx):
    """Versus, a human's Black Factory the only invention: the computer's units come for it (the artillery sets up in
    range, the others come in by its doors) and take it down; with the module off the factory is not touched in the
    same days."""
    g, on = play_versus(ctx, False, 10, cannon=False)
    e = g.e
    ctx.log("\n".join(f"day {k + 1}: {inv}  cpu {cpu}" for k, (inv, cpu) in enumerate(on)))
    hp_on = [inv.get("factory", (0, 0, 0))[2] for inv, _ in on]
    strikes = logged(e, "inv strike")
    ctx.log("\n".join(strikes))
    ctx.check(strikes and all("aims at (6, 9)" in s for s in strikes), f"every strike is at the factory's square: {len(strikes)} strikes")
    ctx.check(min(hp_on) < 200, f"the factory lost hit points: {hp_on}")
    ctx.check(min(near(cpu, VERSUS_AIM["factory"]) for _, cpu in on[2:5]) <= 3, "by day 5 the computer's units are at the factory")
    pic(ctx, g, "versus_factory_attacked", at=VERSUS_AIM["factory"])
    e.close()
    g2, off = play_versus(ctx, True, 10, cannon=False)
    hp_off = [inv.get("factory", (0, 0, 0))[2] for inv, _ in off]
    ctx.log(f"off: {hp_off}")
    ctx.check(min(hp_off) == 200, f"with the module off the computer does not touch the factory ({hp_off})")
    pic(ctx, g2, "versus_factory_not_attacked_before", at=VERSUS_AIM["factory"])
    g2.e.close()


# --- The other modes are as before (AW2TEST_COMPARE_RUNNER: an aw2_script built from 5ff9b2500) -------------------------------

def campaign_day(e, d, human=None):
    """End the turn in a campaign mission (dialogue answered with A) and play on until army 1's next day begins: the other
    human armies (Crystal Calamity has three) end theirs too, the computer's turns run."""
    day = e.u16(DAY)
    d.end_turn()
    for i in range(6000):
        army = e.u16(0x030033EC)
        if e.u16(DAY) > day and army == 1:
            break
        if e.u8(dc.LAST_RESULT) and not d.in_battle():
            return False
        controllers = d.controllers()
        if 1 <= army <= len(controllers) and controllers[army - 1] == 1 and army != 1 and not d.scripts_running():
            try:
                d.wait_control()
            except NavError:
                return False
            d.end_turn()
            e.wait(60)
            continue
        if i % 5 == 4:
            e.press("A", 4)
        e.wait(20)
    else:
        raise NavError(f"army 1's turn did not come back on day {day + 1}")
    try:
        d.wait_control()
    except NavError:
        return False            # (the mission ended on its own)
    return True


def other_runner():
    other = os.environ.get("AW2TEST_COMPARE_RUNNER")
    if not other:
        raise Skip("AW2TEST_COMPARE_RUNNER not set")
    return other


def compare_replays(ctx, g, ds, pristine, name, env=None):
    """The run so far (g's timeline) replayed on this build and the other one from a pristine copy of the save each;
    all of EWRAM and IWRAM must match at the end."""
    other = other_runner()
    e = g.e
    e.wait(30)
    script = ctx.script(g, f"{name}.txt", tail=["dump end", "shot end"])
    dumps = {}
    for tag, runner in (("this build", paths.runner("aw2_script")), ("other build", other)):
        save = os.path.join(ctx.out, f"{name}_{tag.split()[0]}.sav")
        shutil.copyfile(pristine, save)
        run_env = dict(os.environ, **(env or {}))
        if ds:
            run_env["TANGOAW2_DS_ROM"] = paths.ds_rom()
        else:
            run_env.pop("TANGOAW2_DS_ROM", None)
        out = subprocess.run([runner, paths.aw2_rom(), script, "--save", save], capture_output=True, text=True,
                             env=run_env, timeout=3600, cwd=ctx.out)
        text = out.stdout + out.stderr
        ctx.log(f"{tag}: {text.strip().splitlines()[-1] if text.strip() else ''}")
        dumps[tag] = [open(os.path.join(ctx.out, "end" + ext), "rb").read() for ext in (".ewram", ".iwram")]
        for ext in (".ewram", ".iwram", ".bmp"):
            os.replace(os.path.join(ctx.out, "end" + ext), os.path.join(ctx.out, f"{name}_end_{tag.split()[0]}{ext}"))
    for i, (what, base) in enumerate((("EWRAM", 0x02000000), ("IWRAM", 0x03000000))):
        a, b = dumps["this build"][i], dumps["other build"][i]
        diff = [base + k for k in range(len(a)) if a[k] != b[k]]
        ctx.check(not diff, f"{name}: {what} identical to the other build ({len(diff)} bytes differ: {', '.join(hex(x) for x in diff[:12])})")


@test(modes=("aw2",))
def compat_cpu_inv_aw2_campaign_missions(ctx):
    """AW2's own campaign (Black Hole's inventions are the computer's there; its first three missions are tutorials, won
    here by force_win): the fourth mission (map 0x8F: the computer builds an army), twelve days, plays byte for byte as in
    5ff9b2500 (without the pack: with it AW2's world map after the third mission does not answer the harness's pad). (Factory Blues, the sixteenth, cannot be reached by the harness: its tutorials
    and branching world map; the gate is the same for every campaign mission: AW2's campaign is neither Versus nor the BH
    Campaign.)"""
    other_runner()
    from aw2test import campaigns as cp
    pristine = os.path.join(ctx.out, "aw2_pristine.sav")
    live = os.path.join(ctx.out, "aw2_live.sav")
    shutil.copyfile(paths.base_save(), pristine)
    shutil.copyfile(paths.base_save(), live)
    e = Emu(save=live, ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    cp.aw2_new(e, d, ctx.ds)
    for _ in range(3):
        cp.win_here(e, d)
        cp.through_to_map(e, d)
        pick_open_aw2(e, d)
    ctx.log(f"map {e.u8(0x03003FC2):02x}: {[(u['army'], u['type']) for u in g.units()]}")
    for day in range(12):
        campaign_day(e, d)
    ctx.log(f"day {e.u16(DAY)}: {[(u['army'], u['type'], u['x'], u['y']) for u in g.units()]}")
    compare_replays(ctx, g, ctx.ds, pristine, "aw2campaign")


def pick_open_aw2(e, d):
    """On AW2's world map: the cursor moved to the open mission and its battle begun."""
    from aw2test import campaigns as cp
    keys = ["RIGHT", "LEFT", "UP", "DOWN"]
    for i in range(80):
        e.wait(60)
        m = d.map_mission()
        if m < 28 and d.map_flags()[m] == 1:
            break
        e.press(keys[i % 4], 6)
    else:
        raise NavError("no open mission under the cursor")
    for _ in range(10):
        e.press("A", 6)
        if e.wait_until(lambda: d.proc_fn_running(dc.WM_INFO_LOOP), 240, step=5):
            break
    else:
        raise NavError("AW2's mission panel did not open")
    for _ in range(12):
        e.wait(30)
        e.press("A", 6)
        if not d.proc_fn_running(dc.WM_INFO_LOOP) and not d.world_map_up():
            break
    cp.to_first_battle(e, d)


def ds_mission_compat(index, title, days):
    def fn(ctx):
        other_runner()
        pristine = os.path.join(ctx.out, "ds_pristine.sav")
        live = os.path.join(ctx.out, "ds_live.sav")
        shutil.copyfile(paths.base_save(), pristine)
        shutil.copyfile(paths.base_save(), live)
        e = Emu(save=live, ds=True)
        g = Game(e, ctx.image)
        ctx.games.append(g)
        d = dc.DsCampaign(g)
        d.start(step=dc.ORDER.index(index))
        d.wait_map()
        d.wait_control()
        kinds = [(e.u16(INV + 8 * k + 2) >> 6) & 15 for k in range(16) if (e.u16(INV + 8 * k + 2) >> 6) & 15]
        ctx.log(f"map {e.u8(0x03003FC2):02x} ({title}), {len(g.units())} units, inventions {kinds}, controllers {d.controllers()}")
        played = 0
        for _ in range(days):
            if not campaign_day(e, d):
                break
            played += 1
        ctx.log(f"day {e.u16(DAY)} after {played} days passed")
        ctx.check(played >= min(days, MIN_DAYS.get(index, days)), f"the mission ran {played} days")
        compare_replays(ctx, g, True, pristine, f"ds{index}")
    fn.__name__ = f"compat_cpu_inv_ds_campaign_{title.lower().replace(' ', '_').replace('!', '')}"
    fn.__doc__ = f"The DS Campaign's {title} (Black Hole's inventions are the computer's there): up to {days} days (the human armies end their turns, the computers play) play byte for byte as in 5ff9b2500."
    test(modes=("ds",))(fn)


MIN_DAYS = {18: 2, 23: 2}          # (Crystal Calamity ends itself by day 5: Black Hole's computer on a silo is the mission lost; For the Future! within two: the human armies only pass)
CRYSTAL_CALAMITY, FOR_THE_FUTURE = 18, 23
ds_mission_compat(CRYSTAL_CALAMITY, "Crystal Calamity", 12)
ds_mission_compat(FOR_THE_FUTURE, "For the Future!", 12)


@test(modes=("ds",))
def compat_cpu_inv_versus_computer_owns_the_inventions(ctx):
    """Versus with the pack where Black Hole is a computer (the inventions are its own): a Black Factory, a Black Cannon and
    the human's army against it for twelve days play byte for byte as in 5ff9b2500."""
    other_runner()
    m = ctx.map(hq=((1, 28, 18), (2, 1, 1)))
    m.colours = [0, 1, 5, 3, 4]
    m.terrain(6, 8, FACTORY_ANCHOR)
    m.terrain(13, 6, CANNON_MIDDLE)
    for x, y, kind in [(24, 14, 5), (25, 15, 5), (24, 16, 5), (26, 14, 10), (26, 16, 10), (27, 15, 11), (23, 15, 3)]:
        m.unit(1, kind, x, y)
    g = ctx.start(m, ["andy", "vonbolt"], humans=(1,))
    # (what this protects is the computer's handling of the inventions, not the smart factory's choice, which changes
    # on purpose between builds: the factory spawns the table's units, as AW2's does, via the development byte)
    g.e.w8(0x0203E3FF, 1)
    pristine = os.path.join(ctx.out, "versus_pristine.sav")
    shutil.copyfile(os.path.join(ctx.out, "map.sav"), pristine)
    for _ in range(12):
        g.end_turn(human=1, max_frames=60000)
    ctx.log(f"day {g.e.u16(DAY)}")
    compare_replays(ctx, g, True, pristine, "versus")


# --- Netplay: both rollback peers and the straight replay agree ----------------------------------------------

@test(modes=("ds",), netplay=True)
def netplay_cpu_inv_versus(ctx):
    """Versus, a human's Black Factory and Black Cannon attacked by the computer (goals, strikes, the factory's fall):
    both rollback peers and the straight replay of the same inputs end identical."""
    g, rec = play_versus(ctx, False, 8)
    ctx.log(f"inventions at the end: {rec[-1][0]}; strikes {len(logged(g.e, 'inv strike'))}, goals {len(logged(g.e, 'inv goal'))}")
    ctx.check(logged(g.e, "inv strike") and logged(g.e, "inv goal"), "the computer sent units and hit inventions in the run")
    identical, _, text = ctx.netplay_replay(g, [(INV, 0x40)])
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check(identical, "netplay: both peers and the straight replay identical")


@test(modes=("ds",), netplay=True)
def netplay_cpu_inv_bh_campaign(ctx):
    """The BH Campaign's inventions mission, the computer attacking the player's inventions for six days: both rollback peers and
    the straight replay of the same inputs end identical."""
    pristine = save_copy(ctx, "inv_pristine.sav")
    live = save_copy(ctx, "inv_live.sav")
    e, g, d = start_inv(ctx, save=live)
    for _ in range(6):
        next_day(e, g, d)
    ctx.check(logged(e, "inv strike") and logged(e, "inv goal"), "the computer sent units and hit inventions in the run")
    lines = ["seat 0"] + list(e.timeline) + ["wait 60", f"peek {INV:08x} 64"]
    path = os.path.join(ctx.out, "netplay.txt")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    env = dict(os.environ, TANGOAW2_DS_ROM=paths.ds_rom(), AW2_SHARED_ART="1", **ENV)
    out = subprocess.run([paths.runner("aw2_netplay_script"), e.rom, pristine, path, os.path.join(ctx.out, "netplay")],
                         capture_output=True, text=True, env=env, timeout=3600)
    text = out.stdout + out.stderr
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check("all identical: true" in text and "(differs)" not in text, "netplay: both peers and the straight replay identical")


# --- Pictures (AW2TEST_PICS=<dir>) ------------------------------------------------------------------------------

def strike_shots(ctx, e, g, d, prefix, off):
    """The computer's turn, a picture each time it hits an invention (the hit's animation under way), told by the module's log
    (the log has no strike lines when the module is off: then a picture of the same frame of the turn: 60 frames in)."""
    seen = len(logged(e, "inv strike"))
    shots = []
    day = e.u16(DAY)
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    start = e.frame
    for i in range(3000):
        e.wait(10)
        now = logged(e, "inv strike")
        if len(now) > seen:
            aim = re.search(r"aims at \((\d+), (\d+)\)", now[-1]).groups()
            seen = len(now)
            e.wait(45)
            name = {"12, 7": "cannon", "5, 7": "obelisk", "9, 9": "crystal", "16, 9": "mini", "7, 13": "factory"}.get(", ".join(aim), "x")
            shots.append(name)
            pic(ctx, g, f"{prefix}_strike_{name}_{len(shots)}")
        if e.u16(DAY) > day and e.u16(0x030033EC) == 1:
            break
        if off and i == 6:
            pic(ctx, g, f"{prefix}_turn_frame_{i}")
    g._units_base = g._players_base = None
    d.wait_control()
    return shots


@test(modes=("ds",))
def cpu_inv_pictures(ctx):
    """With AW2TEST_PICS: the computer's units set beside the player's Black Factory, Obelisk and Black Cannon, hitting each at
    the start of its turn (the hit's animation), and each invention's hit points in the terrain panel after, against the same
    battle with the module off (the old computer: nothing happens to the inventions)."""
    if not PICS:
        raise Skip("AW2TEST_PICS not set")
    for off in (False, True):
        e, g, d = start_inv(ctx, off=off)
        tag = "old_cpu" if off else "new_cpu"
        units = {u["type"]: u for u in g.units(army=2)}
        # Tanks beside the factory's and the Obelisk's squares, artillery two squares from the cannon's.
        spots = [(5, 8), (7, 14), (13, 8), (14, 7)]
        mine = [u for u in g.units(army=2) if u["type"] in (5, 3)]
        arty = [u for u in g.units(army=2) if u["type"] in (10, 11)]
        d.place_unit(mine[0], 5, 8)           # the Obelisk's aim (5, 7)
        d.place_unit(mine[1], 7, 14)          # the factory's aim (7, 13)
        d.place_unit(arty[0], 12, 9)          # (12, 7): two squares, in the cannon's cone
        d.place_unit(arty[1], 14, 6)          # (12, 7): three squares, outside it
        for u in g.units(army=2):
            e.w8(g.unit_addr(u["id"]) + 0x0B, 0)
        fill_ammo(e, g)
        g._units_base = g._players_base = None
        ctx.log(f"{tag}: inventions before {inventions(e)}")
        pic(ctx, g, f"{tag}_before_cannon", at=AIM["cannon"])
        pic(ctx, g, f"{tag}_before_obelisk", at=AIM["obelisk"])
        pic(ctx, g, f"{tag}_before_factory", at=AIM["factory"])
        shots = strike_shots(ctx, e, g, d, tag, off)
        ctx.log(f"{tag}: strikes shown {shots}; inventions after {inventions(e)}")
        pic(ctx, g, f"{tag}_after_cannon", at=AIM["cannon"])
        pic(ctx, g, f"{tag}_after_obelisk", at=AIM["obelisk"])
        pic(ctx, g, f"{tag}_after_factory", at=AIM["factory"])
        if off:
            ctx.eq(inventions(e), FULL, "old computer: the inventions are untouched (the factory too: not a target in the campaign as it was)")
        else:
            inv = inventions(e)
            ctx.check(inv["cannon"] < 99 and inv["obelisk"] < 99 and inv["factory"] < 200, f"the computer hit the cannon, the Obelisk and the factory: {inv}")
        e.close()


# --- Act I's balance: what the computer's attack on the inventions changes (opt-in: AW2TEST_BH_ACT1_BALANCE=1) ---------------

BALANCE = os.environ.get("AW2TEST_BH_ACT1_BALANCE")
# How the test player plays each Act I mission (as test_bh_act1.BOT): the enemy HQ its capturers make for.
ACT1_BOT = {0: {"goals": [(19, 2)], "stance": "attack"}, 1: {"goals": [(9, 18)], "stance": "attack"}, 2: {"goals": [(24, 8)], "stance": "attack"}}
ACT1_PICKS = {0: 0, 1: 1, 2: 0}
ACT1_COS = {0: None, 1: [bh.STURM], 2: None}
ACT1_DAYS = int(os.environ.get("AW2TEST_BH_ACT1_DAYS", "30"))


def raw_inventions(e):
    out = []
    for k in range(16):
        a = INV + 8 * k
        kind = (e.u16(a + 2) >> 6) & 15
        if kind == 0:
            break
        out.append((KINDS.get(kind, kind), e.u8(a), e.u8(a + 1), e.u8(a + 4)))
    return out


def act1_run(ctx, k, off):
    """Act I's mission k played by the test player, the computer's attack on the inventions on or off."""
    save = save_copy(ctx, f"act1_m{k + 1}_{'off' if off else 'on'}.sav")
    e = Emu(save=save, ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = bh.BhCampaign(g)
    d.picks = ACT1_PICKS
    d.start_at(won_mask=(1 << k) - 1, unlocked_mask=0b11 if k >= 1 else 0b1)
    d.pick_mission()
    if ACT1_PICKS[k] and ACT1_COS[k] is not None:
        d.choose_cos(ACT1_PICKS[k], prefs=ACT1_COS[k])
    for _ in range(400):
        if d.in_battle():
            break
        if d.on_co_select():
            d.co_screen_a()
        e.wait(20)
    if off:
        e.w8(OFF, 0xA5)
    trace = []

    def log(line):
        if line.startswith("day") and d.in_battle():
            try:
                trace.append((e.u16(DAY), raw_inventions(e)))
            except Exception:
                pass

    r = d.play(ACT1_DAYS, log=log, **ACT1_BOT[k])
    inv_end = raw_inventions(e)
    strikes, goals = logged(e, "inv strike"), logged(e, "inv goal")
    e.close()
    return r, trace, inv_end, strikes, goals


if BALANCE:
    def _mk(k):
        def f(ctx):
            res = {}
            for off in (False, True):
                r, trace, inv_end, strikes, goals = act1_run(ctx, k, off)
                res[off] = r
                tag = "off (as before)" if off else "on"
                ctx.log(f"M{k + 1} {tag}: result {r['result']} (1 won, 2 lost) on day {r['days']}: {r['reason']}; strikes {len(strikes)}, goals {len(goals)}; inventions at the end {inv_end}")
                first = {}
                for day, inv in trace:
                    first.setdefault(day, inv)
                ctx.log(f"M{k + 1} {tag}: inventions by day {[(d_, [(a, h) for a, _, _, h in inv]) for d_, inv in sorted(first.items())][:30]}")
                for line in strikes[:40]:
                    ctx.log(f"M{k + 1} {tag}: {line}")
            ctx.log(f"M{k + 1}: on {res[False]['result']}/{res[False]['days']} days, off {res[True]['result']}/{res[True]['days']} days")
        f.__name__ = f"cpu_inv_act1_balance_m{k + 1}"
        f.__doc__ = "Balance run (opt-in): Act I's mission played by the test player with the computer's attack on the player's inventions on and off."
        test(modes=("ds",))(f)
    for _k in (0, 1, 2):
        _mk(_k)
