"""Dual Strike's CO page (crate::ds_co_page): with the pack and the Dual
Strike map graphics (development byte 0x0203E3FE; run with
TANGOAW2_DS_GRAPHICS=1), the CO page (map menu > CO, and INFO on the CO
screens) is Dual Strike's, drawn on BG0 with every other layer covered and
the game's sprites hidden. Without the setting the game's own page is as it
always was. Offline only (the byte is never set in netplay)."""

import os

from aw2test.harness import Skip, test
from aw2test import ram, tag

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


def page_log(ctx):
    """What the CO page last laid out, a dict per page (the console's log, TANGOAW2_CO_PAGE_LOG)."""
    out = {}
    for line in open(os.path.join(ctx.out, "co_page.log")).read().splitlines():
        head, _, rest = line.partition(" fitted ")
        page = int(head.rpartition(" page ")[2])
        fitted, _, rest = rest.partition(" skills ")
        skills, _, rest = rest.partition(" tabs ")
        tabs, _, selected = rest.partition(" selected ")
        out[page] = {"fitted": fitted.startswith("true"), "skills": skills, "tabs": tabs, "selected": int(selected)}
    return out


def tag_battle3(ctx, cos, partners):
    """A Versus battle of three armies, each with the partner given (None: none), the CO page logging what it lays out."""
    log = os.path.join(ctx.out, "co_page.log")
    if os.path.exists(log):
        os.remove(log)
    m = ctx.map(hq=((1, 0, 0), (2, 29, 19), (3, 29, 0)))
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m, env={"TANGOAW2_CO_PAGE_LOG": log})
    for a, p in enumerate(partners, 1):
        tag.set_teams_partner(g.e, a, p)
    g.set_teams(cos, {1})
    g.teams_to_rules()
    g.set_rules()
    g.start_battle()
    g.wait_for_input()
    g.e.wait(30)
    return g


@test(modes=("ds",))
def ds_co_page_header_tabs_and_skills(ctx):
    """Dual Strike's CO page header has a pair of tabs for each army of the battle (a tab for each CO: its country's flag,
    the grey box for none), the page's own CO in the corner marks; RIGHT goes to the partner's tab, then on to the next
    army's. Page 2 lists the skills set (an icon, the name, the effect on one line) and nothing else: no "None set" and no
    tag partners (Dual Strike has those on its top screen)."""
    g = tag_battle3(ctx, ["jake", "sasha", "javier"], ["rachel", "colin", None])
    e = g.e
    if e.u8(DS_GRAPHICS) == 0:
        raise Skip("Dual Strike map graphics off: the game's own page")
    e.w8(0x0203F7E0 + 1, 0x04)  # army 1: Missile Guard (0x2A)
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    e.wait(90)
    ctx.shot(g, "tabs_p1")
    e.press("DOWN", 6)
    e.wait(45)
    ctx.shot(g, "tabs_p2")
    log = page_log(ctx)
    ctx.eq(log[1]["tabs"], "00,11,2-", "a pair of tabs for each army: Jake and Rachel (Orange Star), Sasha and Colin (Blue Moon), Javier alone")
    ctx.eq(log[1]["selected"], 0, "the page is on Jake's tab")
    ctx.eq((log[2]["fitted"], log[2]["skills"]), (True, "42=Missile Guard"), "page 2 lists the skill set, and only that")
    # (the page lists the skills only: Jake and Rachel's partner lists, Jess's .. are not on it)
    from PIL import Image
    px = Image.open(ctx.shot(g, "tabs_p2")).convert("RGB").load()
    icon = sum(1 for y in range(48, 64) for x in range(0, 16) if px[x, y] != (255, 255, 255) and px[x, y] != (248, 248, 248))
    ink = sum(1 for y in range(48, 64) for x in range(16, 90) if sum(px[x, y]) < 200)
    effect = sum(1 for y in range(48, 64) for x in range(88, 200) if sum(px[x, y]) < 200)
    ctx.check(icon > 40 and ink > 30 and effect > 30, f"the skill's row has its icon, name and effect ({icon}, {ink}, {effect})")
    below = sum(1 for y in range(70, 160) for x in range(0, 200) if sum(px[x, y]) < 200)
    ctx.eq(below, 0, "nothing below the skill's row (no TAG partners)")
    e.press("UP", 6)
    e.wait(45)
    e.press("RIGHT", 6)
    e.wait(80)
    ctx.shot(g, "tabs_partner")
    ctx.eq(page_log(ctx)[1]["selected"], 1, "RIGHT: Rachel's tab")
    ctx.eq(page_log(ctx)[1]["tabs"], "00,11,2-", "the tabs keep the pair's order on the partner's page")
    e.press("RIGHT", 6)
    e.wait(80)
    ctx.shot(g, "tabs_army2")
    ctx.eq(page_log(ctx)[1]["selected"], 2, "RIGHT again: Sasha's tab, the next army's")
    e.press("B", 6)
    e.wait(120)


@test(modes=("ds",))
def ds_co_page_page2_without_skills_is_the_heading(ctx):
    """A CO with no skills set: Dual Strike's page 2 is its "Existing skills" heading alone, no "None set." under it."""
    g = open_page(ctx, ["jake", "sasha"])
    e = g.e
    if e.u8(DS_GRAPHICS) == 0:
        raise Skip("Dual Strike map graphics off: the game's own page")
    e.press("DOWN", 6)
    e.wait(45)
    from PIL import Image
    px = Image.open(ctx.shot(g, "page2_empty")).convert("RGB").load()
    # (the wall's watermark is pale; text is dark ink)
    below = sum(1 for y in range(50, 160) for x in range(0, 200) if sum(px[x, y]) < 200)
    ctx.eq(below, 0, "nothing under the heading")
    heading = sum(1 for y in range(32, 50) for x in range(72, 200) if sum(px[x, y]) < 200)
    ctx.check(heading > 30, f"the heading is there ({heading})")
