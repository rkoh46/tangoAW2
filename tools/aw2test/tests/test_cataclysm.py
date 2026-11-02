"""Caulder's Cataclysm on the map (crate::co_powers::CATACLYSM_FN): the pictures of two Dual Strike powers, played without their damage, then the heal.

The Super Power plays Hawke's Black Storm overlay (the yellow lightning and stars sweeping the map), then, with the Dual Strike pack, Kindle's Urban Blight overlay (the pink sparkle wave), then
the per-unit heal sparkle over his units; the heal (5 HP) and the +25% are the engine's as before (`aw2dev co verify caulder`, coverify.hook_cataclysm). No unit of either army loses a single HP. Only the
pictures are reused: Hawke's Black Storm and Kindle's Urban Blight keep dealing their damage (the controls). The overlays are told apart by the colours the game loads into BG palette 8: the storm's is
`0x08113BC0` of the ROM, the wave's the pack's copy of Dual Strike's (`crate::power_anim::URBAN_PALETTE`); the game reloads that row from ROM for each overlay, so the order the colours show up in is the
order the overlays play in. Without the pack's pictures the storm plays alone (`co_powers::install_cataclysm`; Caulder himself needs the pack, so no run can show it). The pictures for review are `aw2dev co sheet cataclysm`'s (cataclysm_sheet.png)."""

import os

from aw2test import coverify as cv
from aw2test import damage
from aw2test.harness import test

ENV = cv.ENV
CAULDER = 88
STORM_PAL = 0x08113BC0         # Hawke's Black Storm palette (AW2's ROM)
URBAN_PAL = 0x087C0900         # crate::power_anim::URBAN_PALETTE (the pack's copy of Dual Strike's Urban Blight palette)
BG_PAL_8 = 0x05000100          # palette RAM: BG palette 8, 16 colours
OWN = [(10, 10, "tank", 100), (10, 14, "infantry", 35), (12, 12, "mech", 100)]
FOES = [(11, 10, "tank", 100), (20, 12, "infantry", 100), (22, 14, "artillery", 60), (6, 4, "infantry", 100)]


def field(ctx):
    m = ctx.map()
    m.terrain(4, 4, "city", 1).terrain(6, 4, "city", 2).terrain(21, 12, "city", 2)
    for x, y, kind, _ in OWN:
        m.unit(1, kind, x, y)
    for x, y, kind, _ in FOES:
        m.unit(2, kind, x, y)
    return m


def start(ctx, co, **kw):
    g = ctx.start(field(ctx), [co, "andy"], env=ENV, **kw)
    for x, y, _, hp in OWN + FOES:
        if hp != 100:
            ctx.set_hp(g, x, y, hp)
    return g


def healed(hp, points=5):
    """AW2's RepairUnit: +10 internal a point until the unit shows 10 HP, then rounded up to a whole displayed HP (3.5 HP + 5 -> 9 HP)."""
    for _ in range(points):
        if damage.hp_bars(hp) == 10:
            break
        hp = min(100, hp + 10)
    return damage.hp_bars(hp) * 10


def hp_of(g):
    return {(u["x"], u["y"], u["army"]): u["hp"] for u in g.units() if u["type"]}


def play(g, army=1, shots=None, every=14):
    """The Super Power from the map menu, watched frame by frame: the order in which the overlays' palettes were in BG palette 8 (run-length coded: [(name, frames)]) and, with `shots` (a function taking
    a key), a picture every `every` frames."""
    e = g.e
    storm, urban = bytes(e.read(STORM_PAL, 32)), bytes(e.read(URBAN_PAL, 32))
    g.charge_power(army, "super")
    g.open_map_menu()
    g.choose("Super", g.MAP_MENU)
    seq, n = [], 0
    for _ in range(1200):
        e.wait(2)
        n += 2
        pal = bytes(e.read(BG_PAL_8, 32))
        name = "storm" if pal == storm else "urban" if pal == urban else None
        if name:
            if seq and seq[-1][0] == name:
                seq[-1][1] += 2
            else:
                seq.append([name, 2])
        if shots and n % every == 0 and n < 900:
            shots(f"{n:04d}")
        if n > 60 and g.player(army)["co_mode"] == 2 and not name and seq and n > 120 and e.u8(0x0300_33EC) == army:
            break
    g.wait_for_input()
    return seq


@test(modes=("ds",))
def cataclysm_plays_storm_then_urban_blight_without_damage(ctx):
    """Cataclysm heals 5 HP (the hurt Infantry 3.5 HP -> 9 HP shown, AW2's rounding), damages nobody (no enemy, no own unit, a unit on a property included), and BG palette 8 shows the storm's colours and then the pack's wave."""
    g = start(ctx, CAULDER)
    before = hp_of(g)
    seq = play(g)
    after = hp_of(g)
    ctx.log(f"overlay palettes seen: {seq}")
    ctx.check([s[0] for s in seq] == ["storm", "urban"], f"Black Storm's overlay plays, then Urban Blight's ({seq})")
    ctx.check(all(s[1] >= 20 for s in seq), f"each overlay plays for a while ({seq})")
    for c, hp in before.items():
        want = healed(hp) if c[2] == 1 else hp
        ctx.eq(after.get(c), want, f"unit at {c[:2]} of army {c[2]}: HP {hp} -> {want}")
    g.e.close()


@test(modes=("ds",))
def cataclysm_controls_black_storm_and_urban_blight_still_damage(ctx):
    """The controls: Hawke's Black Storm still takes 2 HP off every enemy unit (and gives his own 2), Kindle's Urban Blight 3 HP off the enemy units on a property, and both play their own overlay."""
    for co, enemy_lost in (("hawke", {(11, 10): 20, (20, 12): 20, (22, 14): 20, (6, 4): 20}), ("kindle", {(6, 4): 30})):
        g = start(ctx, co)
        before = hp_of(g)
        g.charge_power(1, "super" if co == "hawke" else "power")
        g.open_map_menu()
        g.choose("Super" if co == "hawke" else "Power", g.MAP_MENU)
        g.e.wait_until(lambda: g.player(1)["co_mode"] != 0, 3000, step=10)
        g.wait_for_input()
        after = hp_of(g)
        for (x, y), lost in enemy_lost.items():
            ctx.eq(after[(x, y, 2)], max(1, before[(x, y, 2)] - lost), f"{co}: the enemy at {(x, y)} loses {lost // 10} HP")
        if co == "kindle":
            for c in before:
                if c[2] == 2 and c[:2] != (6, 4):
                    ctx.eq(after[c], before[c], f"{co}: the enemy at {c[:2]} off a property is untouched")
        g.e.close()


LOOKS = [("AW2 graphics", {"TANGOAW2_DS_GRAPHICS": "0", "TANGOAW2_TILT": "0"}),
         ("DS graphics + tilt", {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1"}),
         ("DS graphics, no tilt", {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "0"})]


def cinder_sea_cataclysm(ctx, env, per_stage=3):
    """Gauntlet on Cinder Sea with Caulder in Silver Nova, the Super Power from the map menu: frames of the storm, the wave and the heal sparkle (lists of PNG paths by stage), and the HP of the player's
    units before and after (some are hurt first so the heal shows)."""
    from PIL import Image
    from aw2test import gauntlet as ga, paths
    from aw2test.emu import Emu
    from aw2test.game import Game
    e = Emu(save=paths.base_save(), ds=ctx.ds, env=env)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.start(ga.CAULDER, colour=ga.EMERALD_SUN)
    ctx.eq(g.player(1)["co"], CAULDER, "the player is Caulder")
    mine = [u for u in g.units(army=1) if u["type"]]
    for k, u in enumerate(mine):
        if k % 2 == 0:
            a = g.unit_addr(u["id"]) + 4
            e.w16(a, (e.u16(a) & ~0x7F) | 30)
    before = {u["id"]: u["hp"] for u in g.units(army=1) if u["type"]}
    foes = {u["id"]: u["hp"] for u in g.units() if u["type"] and u["army"] != 1}
    g.goto(8, 16)
    e.wait(20)
    storm, urban = bytes(e.read(STORM_PAL, 32)), bytes(e.read(URBAN_PAL, 32))
    g.charge_power(1, "super")
    g.open_map_menu()
    g.choose("Super", g.MAP_MENU)
    frames = {"storm": [], "urban": [], "heal": []}
    seen, n, last_urban = [], 0, None
    for _ in range(1500):
        e.wait(2)
        n += 2
        pal = bytes(e.read(BG_PAL_8, 32))
        stage = "storm" if pal == storm else "urban" if pal == urban else None
        if stage and (not seen or seen[-1] != stage):
            seen.append(stage)
        if stage:
            last_urban = n if stage == "urban" else last_urban
            if n % 12 == 0:
                p = os.path.join(ctx.out, f"{len(frames[stage]):02d}_{stage}_{n}")
                e.shot(p)
                frames[stage].append(p + ".bmp")
        elif last_urban is not None and n - last_urban < 80 and n % 10 == 0:
            p = os.path.join(ctx.out, f"{len(frames['heal']):02d}_heal_{n}")
            e.shot(p)
            frames["heal"].append(p + ".bmp")
        if last_urban is not None and n - last_urban > 90 and g.player(1)["co_mode"] == 2:
            break
    g.wait_for_input()
    after = {u["id"]: u["hp"] for u in g.units(army=1) if u["type"]}
    foes_after = {u["id"]: u["hp"] for u in g.units() if u["type"] and u["army"] != 1}
    e.close()
    pick = lambda xs: [xs[round(i * (len(xs) - 1) / max(1, per_stage - 1))] for i in range(min(per_stage, len(xs)))] if xs else []
    return seen, {k: pick(v) for k, v in frames.items()}, before, after, foes, foes_after


@test(modes=("ds",))
def cataclysm_sheet_in_the_three_looks(ctx):
    """The review sheet (cataclysm_sheet.png, one row a look: the storm, the wave, the heal sparkle) of Cataclysm on Gauntlet's Cinder Sea with Caulder in Silver Nova, in AW2's graphics, the Dual Strike
    graphics with the tilt and without it; in each: storm then wave, the player's units healed 5 HP, nobody else touched."""
    from PIL import Image, ImageDraw
    rows = []
    for name, env in LOOKS:
        seen, frames, before, after, foes, foes_after = cinder_sea_cataclysm(ctx, env)
        ctx.log(f"{name}: overlays {seen}, frames {dict((k, len(v)) for k, v in frames.items())}")
        ctx.check(seen == ["storm", "urban"], f"{name}: Black Storm's overlay, then Urban Blight's ({seen})")
        for uid, hp in before.items():
            ctx.eq(after.get(uid), healed(hp), f"{name}: the player's unit {uid} heals 5 HP ({hp} -> {after.get(uid)})")
        ctx.check(foes == foes_after, f"{name}: no enemy unit lost a point")
        rows.append((name, [Image.open(p).convert("RGB") for k in ("storm", "urban", "heal") for p in frames[k]]))
    w = max(len(r[1]) for r in rows)
    sheet = Image.new("RGB", (240 * w, (160 + 12) * len(rows)), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for r, (name, ims) in enumerate(rows):
        dr.text((4, r * 172 + 1), name, fill=(255, 255, 255))
        for i, im in enumerate(ims):
            sheet.paste(im, (240 * i, r * 172 + 12))
    out = os.path.join(ctx.out, "cataclysm_sheet.png")
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(out)
    ctx.log(f"sheet: {out}")
