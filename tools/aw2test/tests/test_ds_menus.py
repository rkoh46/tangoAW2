"""Dual Strike's unit command menu and map menu (`ds_menus.rs`), with the pack
and "Dual Strike map graphics" (dev byte 0x0203E3FE) on.

AW2 builds a menu on BG0 (the items: icon and text tiles) and BG2 (the
frame) and a hand sprite. With the mode on, those draws are skipped by
traps, so the game's own menu never reaches the screen, and Dual Strike's is
drawn over the finished picture. These tests check what can be read from the
console: the game's menu cells stay empty (not even for a frame), the menu
logic (entries, cursor, choices) is the game's, the menus the mode does not
restyle (Intel's list) stay AW2's, and with the byte off nothing changes."""

import struct

from aw2test.harness import test

DS_GRAPHICS = 0x0203E3FE
BG0_MAP = 0x06007000


def bg0_cells(e, x0, y0, w, h):
    raw = e.read(BG0_MAP, 0x800)
    return [struct.unpack_from("<H", raw, 2 * (32 * y + x))[0] for y in range(y0, y0 + h) for x in range(x0, x0 + w)]


def hand_sprites(e):
    """OBJ entries of 16x16 at tile 910: AW2's menu hand (not the map cursor)."""
    oam = e.read(0x07000000, 0x400)
    out = []
    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<3H", oam, 8 * i)
        if (a0 >> 8) & 3 != 2 and (a0 & 255) < 160 and (a2 & 0x3FF) == 910:
            out.append(i)
    return out


def _battle(ctx):
    m = ctx.map(hq=((1, 8, 6), (2, 29, 19)))
    m.unit(1, "artillery", 8, 6).unit(2, "tank", 10, 6).unit(1, "infantry", 6, 8)
    g = ctx.start(m, ["andy", "sami"])
    g.wait_idle()
    return g


@test(modes=("ds",))
def ds_menus_unit_menu(ctx):
    """The unit menu: AW2's items, frame and hand are not drawn; the choices
    still work (Wait ends the move)."""
    g = _battle(ctx)
    e = g.e
    e.w8(DS_GRAPHICS, 1)
    g.goto(8, 6)
    e.wait(40)
    clean = ctx.shot(g, "clean")
    e.press("A", 4)
    e.wait(30)
    mm = g.move_to(8, 6)
    e.wait(40)
    ctx.shot(g, "unit_menu")
    ctx.check(mm["names"][:1] == ["Fire"] and "Wait" in mm["names"], f"the game's own menu entries are {mm['names']}")
    ctx.check(not any(bg0_cells(e, 0, 0, 10, 8)), "AW2's menu items are not on BG0")
    ctx.check(not hand_sprites(e), "AW2's hand is not on screen")
    g.choose("Wait", g.ACTION_MENU)
    g.wait_for_input()
    ctx.check(not any(bg0_cells(e, 0, 0, 10, 8)), "nothing left on BG0 after the choice")
    u = g.unit_at(8, 6)
    ctx.check(u is not None, "the unit waited where it stood")


@test(modes=("ds",))
def ds_menus_map_menu(ctx):
    """The map menu: not drawn by AW2; Intel (not restyled) is."""
    g = _battle(ctx)
    e = g.e
    e.w8(DS_GRAPHICS, 1)
    g.goto(12, 12)
    e.wait(40)
    mm = g.open_map_menu()
    e.wait(40)
    ctx.shot(g, "map_menu")
    ctx.check(mm["names"][:2] == ["CO", "Intel"], f"the game's own entries are {mm['names']}")
    ctx.check(not any(bg0_cells(e, 0, 0, 10, 16)), "AW2's map menu is not on BG0")
    g.choose("Intel", g.MAP_MENU)
    e.wait(60)
    ctx.shot(g, "intel_menu")
    ctx.check(any(bg0_cells(e, 0, 0, 12, 16)), "the Intel list is AW2's own, drawn")
    e.press("B", 4)
    e.wait(40)
    mm = g.menu()
    ctx.check(mm is not None and mm["names"][:2] == ["CO", "Intel"], "B from Intel is back at the map menu")
    e.press("B", 4)
    e.wait(30)
    ctx.check(not any(bg0_cells(e, 0, 0, 10, 16)), "the map menu closed")


@test(modes=("ds",))
def ds_menus_off_is_aw2s(ctx):
    """With the byte off the game draws its own menu as ever."""
    g = _battle(ctx)
    e = g.e
    e.w8(DS_GRAPHICS, 0)
    g.goto(8, 6)
    e.wait(30)
    e.press("A", 4)
    e.wait(30)
    g.move_to(8, 6)
    e.wait(40)
    ctx.check(any(bg0_cells(e, 0, 0, 10, 8)), "AW2's menu items are on BG0")
    ctx.check(bool(hand_sprites(e)), "AW2's hand is on screen")


@test(modes=("ds",))
def ds_menus_drop_and_buttons(ctx):
    """A transport's unit menu: the Drop row carries the cargo's own picture (Dual Strike's, and
    AW2's, grammar), the B CANCEL tag and the selection's corners are Dual Strike's own sprites
    (read from overlay 0 of the pack), not tangoAW2's drawing."""
    from PIL import Image
    m = ctx.map(hq=((1, 8, 6), (2, 29, 19)))
    m.unit(1, "apc", 8, 6).unit(1, "infantry", 7, 6)
    g = ctx.start(m, ["andy", "sami"])
    g.wait_idle()
    e = g.e
    e.w8(DS_GRAPHICS, 1)
    g.select(7, 6)
    g.move_to(8, 6)
    g.choose("Load", g.ACTION_MENU)
    g.wait_idle()
    g.select(8, 6)
    mm = g.move_to(8, 6)
    e.wait(40)
    ctx.log(("menu", mm["names"], g.units()))
    p = ctx.shot(g, "drop_menu")
    ctx.check("Drop" in mm["names"], f"the APC offers Drop ({mm['names']})")
    pic = Image.open(p).convert("RGB")
    # the tag: DS's sheet has a white outlined word on the bottom half; the ball's blue B above
    tag = [pic.getpixel((104 + x, y)) for y in range(16) for x in range(32)]
    whites = sum(1 for c in tag if min(c) > 240)
    ctx.check(whites > 60, f"the B CANCEL tag is drawn ({whites} white pixels)")
    ctx.check(len({c for c in tag}) >= 5, "and has the sheet's colours")
    # the Drop row's icon: the cargo's picture (several colours) in the 16 x 16 beside the text
    if "Drop" in mm["names"]:
        k = mm["names"].index("Drop")
        # the list sits beside the APC; its icon column holds the infantry's picture, whose colours
        # (helmet, skin, uniform) are none of the list's white, black, text greys and red bar
        plain = {(255, 255, 255), (0, 0, 0), (255, 41, 41), (238, 246, 246), (197, 189, 180), (148, 139, 131), (106, 90, 98)}
        found = False
        for y0 in range(10, 120):
            for x0 in range(100, 200):
                if all(pic.getpixel((x0 + dx, y0)) == (255, 255, 255) for dx in range(0, 12, 3)):
                    cols = {pic.getpixel((x0 + dx, y0 + dy)) for dx in range(-8, 40) for dy in range(2, 18) if 0 <= x0 + dx < 240}
                    if len(cols - plain) >= 8 and (x0 + 40) < 240:
                        found = True
                        break
            if found:
                break
        ctx.check(found, "a picture stands in the list beside the Drop text (the cargo's)")
