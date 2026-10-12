"""Dual Strike's CO page (crate::ds_co_page): with the pack and the Dual
Strike map graphics (development byte 0x0203E3FE; run with
TANGOAW2_DS_GRAPHICS=1), the CO page (map menu > CO, and INFO on the CO
screens) is Dual Strike's, drawn on BG0 with every other layer covered and
the game's sprites hidden. Without the setting the game's own page is as it
always was. Offline only (the byte is never set in netplay)."""

from aw2test.harness import Skip, test

DS_GRAPHICS = 0x0203E3FE
DISPCNT = 0x04000000
LAYERS = 0x1F00
BG0_ONLY = 0x0500  # (BG0, the page, and BG2, the wall behind it)
MAIN_LOOP = 0x03000000
CO_PAGE_LOOP = 0x08043591
GAME_PAGE = 0x03005940
OAM = 0x07000000


def layers(e):
    return e.u16(DISPCNT) & LAYERS


def open_page(ctx, cos, skills=None):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.start(m, cos)
    e = g.e
    if skills:
        e.w8(0x0203F7E0, skills[0])
        e.w8(0x0203F7E1, skills[1])
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    e.wait(90)
    return g


def visible_sprites(e):
    """OAM entries that are drawn (not disabled, not below the screen)."""
    n = 0
    for i in range(128):
        a0 = e.u16(OAM + 8 * i)
        if a0 & 0x300 != 0x200 and (a0 & 0xFF) < 160:
            n += 1
    return n


@test(modes=("ds",))
def ds_co_page_pages(ctx):
    """Down through the pages and back, then to the other army's page and
    closed. On: BG0 and the wall on all four pages (the game stays on its Super
    Power's page under them), the unit chart as page 4, UP back;
    off: the game's own pages, layers untouched."""
    g = open_page(ctx, ["andy", "sami"])
    e = g.e
    on = e.u8(DS_GRAPHICS) != 0
    ctx.eq(e.u32(MAIN_LOOP), CO_PAGE_LOOP, "the CO page is up")
    ctx.shot(g, "p1")
    if on:
        ctx.eq(layers(e), BG0_ONLY, "page 1: only BG0 shows")
        ctx.eq(visible_sprites(e), 0, "the game's sprites are hidden")
    else:
        ctx.check(layers(e) != BG0_ONLY, "off: the game's own layers")
    for n in (2, 3):
        e.press("DOWN", 6)
        e.wait(45)
        ctx.shot(g, f"p{n}")
        if on:
            ctx.eq(layers(e), BG0_ONLY, f"page {n}: only BG0 shows")
            ctx.eq(e.u32(GAME_PAGE), 3, "the game waits on its Super Power's page")
        else:
            ctx.eq(e.u32(GAME_PAGE), n - 1 if n == 2 else 2, "off: the game's own page")
    e.press("DOWN", 6)
    e.wait(90)
    ctx.shot(g, "p4")
    if on:
        ctx.eq(layers(e), BG0_ONLY, "page 4 is Dual Strike's unit chart")
        ctx.eq(e.u32(GAME_PAGE), 3, "the game waits on its Super Power's page")
        e.press("UP", 6)
        e.wait(45)
        ctx.eq(layers(e), BG0_ONLY, "UP: Dual Strike's page 3 again")
        ctx.shot(g, "p3b")
    e.press("RIGHT", 6)
    e.wait(80)
    ctx.shot(g, "army2")
    if on:
        ctx.eq(layers(e), BG0_ONLY, "the other army's page is Dual Strike's too")
    e.press("B", 6)
    e.wait(150)
    ctx.check(e.u32(MAIN_LOOP) != CO_PAGE_LOOP, "B closes the page")
    ctx.check(layers(e) != BG0_ONLY, "the map's layers are back")
    ctx.shot(g, "after")


@test(modes=("ds",))
def ds_co_page_every_kind_of_co(ctx):
    """Screenshots of the page for an AW2 CO, a Dual Strike one, Sturm
    (AW2's text and art), Clone Andy and Crumb (tangoAW2's text), with
    skills on (the page lists them): every page must show text and never
    leave BG0's layer (a page that fitted no layout is left with the strip
    only)."""
    for co in ("andy", "jake", "flak", "sturm", "cloneandy", "crumb", "vonbolt"):
        g = open_page(ctx, [co, "sasha"], skills=(0x01, 0x10))
        e = g.e
        on = e.u8(DS_GRAPHICS) != 0
        for n in (1, 2, 3, 4):
            ctx.shot(g, f"{co}_p{n}")
            if on:
                ctx.eq(layers(e), BG0_ONLY, f"{co} page {n}: Dual Strike's")
            e.press("DOWN", 6)
            e.wait(45)
        e.press("B", 6)
        e.wait(120)
        ctx.check(e.u32(MAIN_LOOP) != CO_PAGE_LOOP, f"{co}: closed")


@test(modes=("ds",))
def ds_co_page_unit_chart_and_wall(ctx):
    """Page 4 is Dual Strike's unit chart: four or five units to a row, one thin attack gauge each, filled with the CO's stats (Max's direct
    vehicles +20 %: a few pink pixels in their gauges; Andy's gauges are plain), and the page has the wall behind
    it (Dual Strike's watermark: the page is not plain white)."""
    from PIL import Image
    pink = {}
    for co in ("max", "andy"):
        g = open_page(ctx, [co, "sami"])
        e = g.e
        if e.u8(DS_GRAPHICS) == 0:
            raise Skip("Dual Strike map graphics off: the game's own chart")
        for _ in range(3):
            e.press("DOWN", 6)
            e.wait(45)
        p = Image.open(ctx.shot(g, f"chart_{co}")).convert("RGB")
        px = p.load()
        pink[co] = sum(1 for y in range(40, 160) for x in range(0, 200) if px[x, y][0] > 240 and 160 < px[x, y][1] < 185 and 160 < px[x, y][2] < 185)
        white = sum(1 for y in range(40, 160) for x in range(200) if px[x, y] in ((248, 248, 248), (255, 255, 255)))
        ctx.check(white < 120 * 200 * 0.9, f"{co}: the page has the wall behind it ({white} plain white pixels)")
        e.press("B", 6)
        e.wait(120)
    ctx.log(f"pink pixels: {pink}")
    ctx.check(pink["max"] >= 20, f"Max's chart has pink gauge fill ({pink['max']})")
    ctx.eq(pink["andy"], 0, "Andy's gauges are plain")
