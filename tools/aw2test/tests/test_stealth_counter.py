"""An Anti-Air always fires back at a Stealth that attacked it, hidden or not (tangoAW2's rule; Dual Strike lets only
Fighters and Stealths hit a hidden Stealth, the Anti-Air included). Only the counterattack changes: nothing else counters a
hidden Stealth, and an Anti-Air still cannot start an attack on one (crate::roster::dived_column).
docs/dev/stealth-counter.md."""

from aw2test.harness import test


def hidden_stealth_turn(ctx, victim, hide):
    """A Stealth (army 1) beside a `victim` (army 2); `hide` hides it on day 1, then it is army 1's turn again.
    Returns (g, stealth before, stealth after, victim before, victim after) of its attack."""
    m = ctx.map()
    m.unit(1, "stealth", 10, 10).unit(2, victim, 11, 10)
    g = ctx.start(m, ["andy", "andy"], humans=(1, 2))
    if hide:
        g.select(10, 10)
        g.move_to(10, 10)
        g.choose("Hide", g.ACTION_MENU)
        g.wait_idle()
        ctx.check(g.unit_at(10, 10)["flags"] & 0x20, "the Stealth is hidden")
    g.end_turn(human=2)
    g.end_turn(human=1)
    ctx.eq(bool(g.unit_at(10, 10)["flags"] & 0x20), hide, f"the Stealth is {'hidden' if hide else 'visible'} when it attacks")
    names = g.action_menu_at(10, 10)
    ctx.check("Fire" in names, f"the Stealth can Fire at the {victim}: {names}")
    (a0, a1), (d0, d1) = g.attack((10, 10), (10, 10), (11, 10))
    ra, rd = ctx.battle_records(g)
    return g, a0, a1, d0, d1, ra, rd


@test(modes=("ds",))
def stealth_counter_hidden_vs_antiair(ctx):
    """A hidden Stealth attacks an Anti-Air: the Anti-Air counters (the Stealth loses HP), with the chart's damage for a
    Stealth (Anti-Air vs Stealth) and Dual Strike's counter rules."""
    g, a0, a1, d0, d1, ra, rd = hidden_stealth_turn(ctx, "antiair", True)
    ctx.log(f"stealth {a0['hp']}->{a1['hp']}, anti-air {d0['hp']}->{d1['hp']}, records {ra} {rd}")
    ctx.check(d1["hp"] < d0["hp"], "the Stealth hit the Anti-Air")
    ctx.check(d1["hp"] > 0, "the Anti-Air survived (it can counter)")
    ctx.check(a1["hp"] < a0["hp"], "the Anti-Air countered the hidden Stealth")
    ctx.eq(rd["attack_type"], 1, "the counter is the Anti-Air's gun")
    ctx.check(rd["base"] > 0, f"the counter's base damage is {rd['base']}")
    ctx.eq(ra["display"] > 0, True, "the forecast shows the Stealth's damage")
    ctx.shot(g, "stealth_counter_hidden")


@test(modes=("ds",))
def stealth_counter_hidden_equals_visible(ctx):
    """The same Anti-Air counter whether the Stealth is hidden or not (normal damage from the chart)."""
    out = []
    for hide in (True, False):
        g, a0, a1, d0, d1, ra, rd = hidden_stealth_turn(ctx, "antiair", hide)
        ctx.check(a1["hp"] < a0["hp"], f"the Anti-Air counters a {'hidden' if hide else 'visible'} Stealth")
        out.append((d0["hp"] - d1["hp"], a0["hp"] - a1["hp"], rd["base"], rd["attack_type"]))
        g.e.close()
    ctx.log(f"(hidden, visible): {out}")
    ctx.eq(out[0][2:], out[1][2:], "the counter's base damage and weapon are the same hidden and visible")
    ctx.check(abs(out[0][0] - out[1][0]) <= 10, "the Stealth's own hit is the usual one (luck apart)")


@test(modes=("ds",))
def stealth_counter_other_units_unchanged(ctx):
    """A hidden Stealth attacks a Tank: no counter (a Tank cannot hit air). A Fighter counters it as before. An Anti-Air
    still cannot start an attack on a hidden Stealth (only the counter changed)."""
    g, a0, a1, d0, d1, ra, rd = hidden_stealth_turn(ctx, "tank", True)
    ctx.check(d1["hp"] < d0["hp"], "the Stealth hit the Tank")
    ctx.eq(a1["hp"], a0["hp"], "a Tank does not counter a hidden Stealth")
    g.e.close()
    g, a0, a1, d0, d1, ra, rd = hidden_stealth_turn(ctx, "fighter", True)
    ctx.check(d1["hp"] > 0 and a1["hp"] < a0["hp"], "a Fighter still counters a hidden Stealth")
    g.e.close()
    # An Anti-Air beside a hidden Stealth cannot fire at it on its own turn.
    m = ctx.map()
    m.unit(1, "stealth", 10, 10).unit(2, "antiair", 11, 10)
    g = ctx.start(m, ["andy", "andy"], humans=(1, 2))
    g.select(10, 10)
    g.move_to(10, 10)
    g.choose("Hide", g.ACTION_MENU)
    g.wait_idle()
    g.end_turn(human=2)
    names = g.action_menu_at(11, 10)
    ctx.check("Fire" not in names, f"an Anti-Air cannot attack a hidden Stealth: {names}")


# The pictures: the forecast box (the cursor on the Anti-Air after Fire) and the battle with its counter, in the three looks
# (AW2 graphics; Dual Strike graphics with the tilt; Dual Strike graphics without it). AW2TEST_STEALTH_SHEET=<png> writes the sheet.
LOOKS = (("aw2", {}), ("ds_tilt", {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1", "TANGOAW2_TILT_SNAP": "1"}),
         ("ds_flat", {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "0"}))


def look_pictures(ctx, name, env, frames=14, step=45):
    m = ctx.map()
    m.unit(1, "stealth", 10, 10).unit(2, "antiair", 11, 10)
    g = ctx.start(m, ["andy", "drake"], humans=(1, 2), visuals="a", env=env)
    g.select(10, 10)
    g.move_to(10, 10)
    g.choose("Hide", g.ACTION_MENU)
    g.wait_idle()
    g.end_turn(human=2)
    g.end_turn(human=1)
    g.select(10, 10)
    g.move_to(10, 10)
    g.choose("Fire", g.ACTION_MENU)
    g.e.wait(40)
    g.goto(11, 10) if g.cursor() != (11, 10) else None
    g.e.wait(60)
    forecast = ctx.shot(g, f"{name}_forecast")
    g.e.press("A", 4)
    shots = []
    for k in range(frames):
        g.e.wait(step)
        shots.append(ctx.shot(g, f"{name}_battle_{k:02d}"))
    g.wait_for_input()
    stealth, aa = g.unit_at(10, 10), g.unit_at(11, 10)
    ctx.log(f"{name}: stealth hp {stealth['hp'] if stealth else None}, anti-air hp {aa['hp'] if aa else None}")
    ctx.check(stealth is not None and stealth["hp"] < 100, f"{name}: the Anti-Air's counter hurt the hidden Stealth")
    return forecast, shots


@test(modes=("ds",))
def stealth_counter_pictures(ctx):
    import os
    done = {}
    for name, env in LOOKS:
        done[name] = look_pictures(ctx, name, env)
    out = os.environ.get("AW2TEST_STEALTH_SHEET")
    if not out:
        return
    from PIL import Image
    cols = 5
    rows = []
    for name, _ in LOOKS:
        forecast, shots = done[name]
        pick = [forecast] + shots[1::3][:cols - 1]
        rows.append([Image.open(p).convert("RGB") for p in pick])
    w, h = rows[0][0].size
    sheet = Image.new("RGB", (cols * w * 2, len(rows) * h * 2), (20, 20, 20))
    for r, row in enumerate(rows):
        for c, im in enumerate(row):
            sheet.paste(im.resize((w * 2, h * 2), Image.NEAREST), (c * w * 2, r * h * 2))
    sheet.save(out)
    ctx.log(f"sheet {out}")
