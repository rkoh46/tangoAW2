"""Every new CO's CO page (map menu > CO) pages cleanly: down through every page
and back up, then to the other army's page. Von Bolt has no CO Power (his COP
texts are empty in Dual Strike), which once left a text slot pointing at
nothing and garbled the screen; every text slot of every new CO must point at
a string in the ROM image."""

import os

from aw2test.harness import test

TEXT_TABLE = 0x08610A38
TEXT_BASE = 0x6D72
TEXTS_PER_CO = 16
TEXTS_USED = 14

NEW = ["jugger", "koal", "kindle", "vonbolt", "grimm", "javier", "sasha", "jake", "rachel"]


def make(co):
    def fn(ctx):
        m = ctx.map()
        m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
        g = ctx.start(m, [co, "sasha" if co != "sasha" else "koal"])
        g.open_map_menu()
        g.choose("CO", g.MAP_MENU)
        g.e.wait(90)
        ctx.shot(g, "p00")
        seq = ["DOWN"] * 6 + ["UP"] * 6 + ["RIGHT"] + ["DOWN"] * 5 + ["UP"] * 5
        for i, k in enumerate(seq, 1):
            g.e.press(k, 6)
            g.e.wait(45)
            ctx.shot(g, f"p{i:02d}")
    fn.__name__ = f"co_page_{co}"
    test(modes=("ds",))(fn)


for co in NEW:
    make(co)


@test(modes=("ds",))
def new_co_texts_all_point_at_strings(ctx):
    m = ctx.map()
    g = ctx.start(m, ["vonbolt", "andy"])
    for k, co in enumerate(NEW):
        for w in range(TEXTS_USED):
            tid = TEXT_BASE + TEXTS_PER_CO * k + w
            p = g.e.u32(TEXT_TABLE + 4 * tid)
            ctx.check(0x08000000 <= p < 0x08800000, f"{co} text {w} (id {tid:#x}) points into the ROM: {p:#x}")
            if 0x08000000 <= p < 0x08800000:
                s = b"".join(g.e.read(p + i, 16) for i in range(0, 256, 16))
                ctx.check(0 in s, f"{co} text {w} is a string (ends within 256 bytes)")


# tangoAW2's own COs: their pages (bio, day to day, CO Power, Super Power) are the review sheet's "CO pages" row (`aw2dev co sheet pages`) and must show their whole text.
OWN = ["aria", "asuka", "tabitha", "lili", "caulder", "crumb", "cloneandy"]


def make_own(co):
    def fn(ctx):
        from aw2test import coverify as cv, cospec
        m = ctx.map()
        m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
        g = ctx.start(m, [cospec.IDS.get(co, co), "andy"], env=cv.ENV)
        g.open_map_menu()
        g.choose("CO", g.MAP_MENU)
        g.e.wait(90)
        ctx.shot(g, "page1")
        for k in (2, 3, 4):
            g.e.press("DOWN", 6)
            g.e.wait(60)
            ctx.shot(g, f"page{k}")
    fn.__name__ = f"co_pages_own_{co}"
    test(modes=("ds",))(fn)


for co in OWN:
    make_own(co)


@test(modes=("ds",))
def silver_nova_name_plates_are_their_own_on_every_screen(ctx):
    """Tabitha, Lili and Caulder read their own names on the screens that show a name plate: the Teams card and the CO page; no CO page's header plate is
    Hawke's (the CO the old placeholder took after) or another one's of the three."""
    from aw2test import coverify as cv, cospec
    from tests.test_tag import read_bmp
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    plate = lambda n: [row[48:112] for row in read_bmp(os.path.join(ctx.out, n + ".bmp"))[24:42]]
    plates = {}
    for name in ("tabitha", "lili", "caulder", "hawke"):
        co = cospec.IDS.get(name, 14)
        if name != "hawke":
            g = ctx.boot_teams(m, env=cv.ENV)
            g.set_teams([co, "andy"], {1})
            g.e.wait(60)
            ctx.shot(g, f"teams_{name}")
            g.e.close()
        g2 = ctx.start(m, [co, "andy"], env=cv.ENV)
        g2.open_map_menu()
        g2.choose("CO", g2.MAP_MENU)
        g2.e.wait(90)
        ctx.shot(g2, f"page_{name}")
        plates[name] = plate(f"page_{name}")
        g2.e.close()
    for a in ("tabitha", "lili", "caulder"):
        for b in plates:
            if a < b or b == "hawke":
                if a != b:
                    ctx.check(plates[a] != plates[b], f"the CO page's name plate of {a} is not {b}'s")
