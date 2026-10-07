"""The results screen's quote box: its text is broken into lines that fit
(AW2 does not wrap there: a longer line runs on into the next row at the
screen's left). Every new CO's victory line and the special pairs'
exchanges (crate::co_new::wrap_quote, crate::tag_extras::compose_victory;
the pairs' are checked by the crate's own ignored test against the .nds).
Pack only."""

from aw2test.harness import test
from aw2test import tag
from aw2test import rom as romlib

# --- The results screen's quote box ------------------------------------------------------

TEXT_TABLE = 0x08610A38
FONT_WIDTHS = 0x084C36E4
QUOTE_PIXELS = 104        # the box's line: from x = 128 to the screen's right edge
QUOTE_LINES = 3           # AW2's own longest victory quotes
NEW_COS = ["jugger", "koal", "kindle", "vonbolt", "grimm", "javier", "sasha", "jake", "rachel"]


def text_at(e, tid):
    p = e.u32(TEXT_TABLE + 4 * tid)
    b = e.read(p, 0x100)
    return b[:b.index(0)] if 0 in b else b


def pixels(widths, line):
    return sum(widths[c] + 1 for c in line) - 1 if line else 0


def win_battle(ctx, cos, partners=(None, None)):
    """A Versus battle army 1 wins at once (a Tank next to a one-HP Infantry);
    returns the Game with the results screen coming."""
    m = ctx.map(spare=False)
    m.unit(1, "tank", 10, 10).unit(2, "infantry", 11, 10)
    g = ctx.boot_teams(m)
    e = g.e
    for a, p in enumerate(partners, 1):
        tag.set_teams_partner(e, a, p)
    g.set_teams(cos, {1})
    g.teams_to_rules()
    g.set_rules()
    g.start_battle()
    g.wait_for_input()
    inf = g.unit_at(11, 10)
    a = g.unit_addr(inf["id"])
    e.w16(a + 4, (e.u16(a + 4) & ~0x7F) | 1)
    g.select(10, 10)
    g.move_to(10, 10)
    g.choose("Fire", g.ACTION_MENU)
    g.pick_target(11, 10)
    return g


def quote_fits(ctx, e, t, label):
    widths = e.read(FONT_WIDTHS, 256)
    lines = t.split(b"\r")
    ctx.check(len(lines) <= QUOTE_LINES, f"{label}: {len(lines)} lines, the box takes {QUOTE_LINES} ({t!r})")
    for l in lines:
        ctx.check(pixels(widths, l) <= QUOTE_PIXELS, f"{label}: {l!r} is {pixels(widths, l)} px, the box's line is {QUOTE_PIXELS}")


@test(modes=("ds",))
def victory_quotes_fit_the_box(ctx):
    """Every new CO's victory quote (the results screen's text box: lines
    start at x = 128, 104 px to the screen's edge, and AW2's text does not
    wrap there but runs on into the next row at the screen's left) is broken
    into lines of at most 104 px, at most the 3 lines of AW2's own."""
    g = ctx.start(ctx.map(), ["andy", "olaf"])
    e = g.e
    for k, name in enumerate(NEW_COS):
        tid = 0x6D72 + 16 * k + 13
        t = text_at(e, tid)
        ctx.check(t != b"", f"{name} has a victory quote")
        quote_fits(ctx, e, t, name)
    for co in range(0, 17):
        row = e.u32(0x08042DDC) + 0x104 * co
        quote_fits(ctx, e, text_at(e, e.u16(row + 0x34)), f"AW2 CO {co}")


@test(modes=("ds",))
def victory_quote_new_co_battle(ctx):
    """Jake (his line "You got dropped like a phat beat!") wins a battle:
    the quote's box shows it in AW2's lines, none past the box."""
    g = win_battle(ctx, ["jake", "olaf"])
    e = g.e
    e.wait(240)
    e.press("A", 2)
    e.wait(300)
    ctx.shot(g, "victory_jake")
    jake = 0x6D72 + 16 * NEW_COS.index("jake") + 13
    t = text_at(e, jake)
    ctx.log(f"Jake's victory text {t!r}")
    quote_fits(ctx, e, t, "Jake")
