"""The CO page's TAG box draws its stars as sprites (`tag_extras::flush`): closing the page must take every one of them off the map (they stayed
on screen until the CO menu was opened again). Played for COs with few and many partners; the map after the page has no star sprite."""

from aw2test.coverify import ENV
from aw2test.harness import test

ENV = dict(ENV, TANGOAW2_DS_GRAPHICS="0")   # (AW2's own CO page; Dual Strike's has no TAG box)
STAR_TILE = 0x321     # tag_extras::STAR_TILE + 1
OAM = 0x07000000


def stars(g):
    """The OAM entries that show a TAG star (tile 0x321 in OBJ palette 12, not hidden)."""
    raw = g.e.read(OAM, 0x400)
    out = []
    for i in range(128):
        a0, a1, a2 = (int.from_bytes(raw[8 * i + 2 * k:8 * i + 2 * k + 2], "little") for k in range(3))
        if a2 == (STAR_TILE | 12 << 12) and (a0 >> 8) & 3 != 2 and (a0 & 0xFF) < 160:   # (not disabled, not below the screen: the game parks unused entries at y 160)
            out.append((i, a1 & 0x1FF, a0 & 0xFF))
    return out


def make(co):
    co_name = {86: "klaus", 87: "aurelia", 82: "crumb"}.get(co, co)

    def fn(ctx):
        m = ctx.map()
        m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
        g = ctx.start(m, [co, "andy"], env=ENV)
        g.open_map_menu()
        g.choose("CO", g.MAP_MENU)
        g.e.wait(90)
        for _ in range(4):
            g.e.press("DOWN", 6)
            g.e.wait(40)
        ctx.shot(g, "tag_page")
        on = stars(g)
        ctx.log(f"{co_name}: {len(on)} star sprites on the TAG page")
        ctx.check(len(on) > 0, f"{co_name}: the TAG page shows its stars")
        g.e.press("B", 6)
        g.e.wait(40)
        ctx.shot(g, "map_after")
        left = stars(g)
        ctx.check(not left, f"{co_name}: no star sprite left on the map after the page closes ({len(left)} at {left[:4]})")
        # and after a second visit
        g.open_map_menu()
        g.choose("CO", g.MAP_MENU)
        g.e.wait(60)
        g.e.press("B", 6)
        g.e.wait(60)
        left = stars(g)
        ctx.check(not left, f"{co_name}: no star sprite left after a second visit ({len(left)})")
    fn.__name__ = f"co_tag_stars_{co_name}"

    test(modes=("ds",))(fn)


for co in ("asuka", 86, 87, 82, "andy", "sturm"):   # Klaus and Aurelia (Emerald Sun), Crumb
    make(co)
