"""Pictures of the Gauntlet maps added after Cinder Sea and Iron Crown, for review (`-k gauntlet_lines_pictures`; `AW2TEST_REVIEW_DIR` copies the sheets where a person looks): per map and per look
(AW2 graphics, Dual Strike graphics with the tilt, Dual Strike graphics without it: the owner's standing rule) a sheet with day 1 on the player's side and on the first line's, the whole map (the two
flat looks: the tilt is a host-side overlay of the same frame), every later line's arrival scene boxes and its units on the map, and a battle scene of the line's army. On Chrome Meridian the Silver Nova
lines' faces, orb-tower HQs and battle scenes are the point; Harvest Run's four lines are one colour. The selector's order is `gauntlet_pictures_selector_and_colour_pick_in_the_three_looks`."""

import os

from aw2test import gauntlet as ga
from aw2test import gauntlet_maps as gm
from aw2test import stitch
from aw2test.harness import test
from tests.test_bh2_review import home
from tests.test_bh_review import Quiet
from tests.test_gauntlet_lines import start
from tests.test_gauntlet_map2 import png
from tests.test_gauntlet_map2_pictures import battle_scene, sheet

LOOKS = (
    ("aw2", {}),
    ("ds_tilt", {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1"}),
    ("ds_flat", {"TANGOAW2_DS_GRAPHICS": "1"}),
)


def settled_png(ctx, e, name):
    """A picture of the screen once it is not a fade or a flash: a frame that is mostly white (the screen flashes white when a line is revealed and when a scene's fade starts) is taken again after a
    few frames (up to 40 tries), so a sheet never holds a blank capture."""
    from PIL import Image
    for _ in range(40):
        p = png(ctx, e, name)
        px = list(Image.open(p).convert("RGB").getdata())
        white = sum(1 for r, g, b in px if r > 245 and g > 245 and b > 245) / len(px)
        bright = sum(r + g + b for r, g, b in px) / (3 * len(px))
        if white < 0.6 and bright < 205:         # (a half-faded frame is washed out too: its mean brightness is high)
            return p
        e.wait(6)
    return p


def scene_pics(ctx, e, d, tag, most=4):
    """The boxes of the running script, one picture each (A through them); a flash between two boxes is waited out."""
    pics = []
    for _ in range(400):
        if d.scripts_running():
            if len(pics) < most:
                e.wait(70)
                pics.append(settled_png(ctx, e, f"{tag}_box{len(pics)}"))
            e.press("A", 4)
        elif pics:
            break
        e.wait(20)
    return pics


def pictures(info, battles=True):
    def fn(ctx):
        out = os.environ.get("AW2TEST_REVIEW_DIR") or ctx.out
        os.makedirs(out, exist_ok=True)
        for look, env in LOOKS:
            e, g, d = start(ctx, info, env=env)
            w, h = d.size()
            frames = []
            first = info.lines[0]
            g.goto(*info.player_hq)
            e.wait(50)
            frames.append((png(ctx, e, f"{look}_day1_player"), {"title": f"{info.title} ({look}): day 1, the player's camp", "plain": True, "lines": [f"The player (army {info.player}), a free CO."]}))
            g.goto(*first.hq)
            e.wait(50)
            frames.append((png(ctx, e, f"{look}_day1_{first.name}"), {"title": f"{first.name}'s line on the field from the start", "plain": True, "lines": [f"{first.name}'s HQ at {first.hq}."]}))
            if look != "ds_tilt":
                home(g, e)
                frames.append((stitch.stitch(Quiet(ctx), g, f"{look}_whole", w, h), {"title": f"The whole map ({look})", "marks": [(l.name, l.hq, "") for l in info.lines] + [("player", info.player_hq, "")],
                                                                                      "lines": ["Every HQ cell is shown: the later lines' are plain ground until their line arrives."]}))
            for k, l in enumerate(info.lines[:-1]):
                nxt = info.lines[k + 1]
                d.capture(ctx, l.hq, army=info.player)
                boxes = scene_pics(ctx, e, d, f"{look}_arrive_{nxt.name}")
                ctx.check(boxes, f"{l.name}'s fall played a scene")
                for b, p in enumerate(boxes[:3]):
                    frames.append((p, {"title": f"{l.name} falls: {nxt.name} arrives (box {b + 1})", "plain": True, "lines": ["The arrival scene."]}))
                d.settle()
                g.goto(*nxt.hq)
                e.wait(60)
                frames.append((png(ctx, e, f"{look}_{nxt.name}_arrived"), {"title": f"{nxt.name}'s line is on the map", "plain": True,
                                                                          "lines": [f"{len(g.units(army=nxt.army))} units landed, HQ {nxt.hq} built."]}))
                try:
                    if not battles:
                        raise RuntimeError("(a five-army map's battle scenes are taken in their own runs: `battle_pictures`)")
                    bs = battle_scene(ctx, e, g, d, me=info.player, them=nxt.army, tag=f"{look}_battle_{nxt.name}")
                except Exception as ex:          # (a picture aid: a stuck cursor after a battle scene must not lose the sheet)
                    ctx.log(f"battle scene against {nxt.name}: {ex}")
                    bs = None
                if bs:
                    frames.append((bs, {"title": f"Battle scene: the player against {nxt.name}'s army", "plain": True, "lines": ["Animations on; the foe was placed next to the player's Tank for the picture."]}))
            e.close()
            path = sheet(frames, os.path.join(out, f"{info.key}_{look}_sheet.png"), f"Gauntlet {info.title} ({look})")
            ctx.log("wrote " + path)
    fn.__name__ = f"gauntlet_lines_pictures_{info.key}"
    test(modes=("ds",))(fn)


def battle_pictures(info, k):
    """The battle scene of line k's army (one run: the first k lines are taken, then the player's Tank fires on a unit of the line placed next to it), in the three looks side by side."""
    line = info.lines[k]

    def fn(ctx):
        from PIL import Image
        out = os.environ.get("AW2TEST_REVIEW_DIR") or ctx.out
        os.makedirs(out, exist_ok=True)
        frames = []
        for look, env in LOOKS:
            e, g, d = start(ctx, info, env=env)
            for prev in info.lines[:k]:
                d.capture(ctx, prev.hq, army=info.player)
                d.settle()
            g.goto(*line.hq)
            e.wait(60)
            hq = png(ctx, e, f"{look}_hq_{line.name}")
            bs = battle_scene(ctx, e, g, d, me=info.player, them=line.army, tag=f"{look}_battle_{line.name}")
            ctx.check(bs is not None, f"{look}: a battle scene against {line.name}")
            frames.append((hq, {"title": f"{line.name}'s HQ ({look})", "plain": True, "lines": [f"army {line.army}"]}))
            if bs:
                frames.append((bs, {"title": f"Battle scene: the player against {line.name}'s army ({look})", "plain": True, "lines": ["Animations on."]}))
            e.close()
        sheet(frames, os.path.join(out, f"{info.key}_battle_{line.name}_sheet.png"), f"Gauntlet {info.title}: {line.name}'s army, HQ and battle scene in the three looks")
    fn.__name__ = f"gauntlet_lines_pictures_battle_{info.key}_{line.name}"
    test(modes=("ds",))(fn)


for _info in gm.MAPS.values():
    pictures(_info, battles=not _info.five)
    if _info.five:
        for _k in range(1, len(_info.lines)):
            battle_pictures(_info, _k)


@test(name="gauntlet_lines_pictures_chrome_extras", modes=("ds",))
def gauntlet_lines_pictures_chrome_extras(ctx):
    """Chrome Meridian's Silver Nova lines on the screens besides the map and the battle scene, in the three looks: the capture box while the player takes Caulder's orb-tower HQ (the property in the
    skin's chrome, the old owner's), the terrain/CO panel and the CO page of Caulder's army (map menu > CO, RIGHT to his army: the page's colours and the unit chart). The skin sits on the corps' host
    colour: none of these may show it as Yellow Comet's."""
    info = gm.MAPS[6]
    out = os.environ.get("AW2TEST_REVIEW_DIR") or ctx.out
    os.makedirs(out, exist_ok=True)
    frames = []
    for look, env in LOOKS:
        e, g, d = start(ctx, info, env=env)
        d.capture(ctx, info.lines[0].hq, army=info.player)
        d.settle()
        cau = info.lines[1]
        g.goto(*cau.hq)
        e.wait(50)
        frames.append((png(ctx, e, f"{look}_panel_on_caulders_hq"), {"title": f"The cursor on Caulder's HQ ({look}): the orb tower and the terrain panel", "plain": True, "lines": ["The panel's small HQ icon is the game's own (documented limit)."]}))
        shots = []
        d.capture(ctx, cau.hq, army=info.player, snap=lambda k: shots.append(png(ctx, e, f"{look}_capture_{k:02d}")) if k % 2 == 0 else None)
        from PIL import Image
        best = max(shots, key=lambda p: len(set(Image.open(p).convert("RGB").getdata())))
        frames.append((best, {"title": f"Capture box, the player taking Caulder's HQ ({look})", "plain": True, "lines": ["The property and the old owner in the skin's chrome (Silver Nova), not Yellow Comet's."]}))
        e.close()
    for look, env in LOOKS:
        e, g, d = start(ctx, info, env=env)
        d.capture(ctx, info.lines[0].hq, army=info.player)
        d.settle()
        try:
            g.open_map_menu()
            g.choose("CO", g.MAP_MENU)
            e.wait(90)
            pages = [png(ctx, e, f"{look}_co_own")]
            for k in range(1, 3):
                e.press("RIGHT", 6)
                e.wait(60)
                pages.append(png(ctx, e, f"{look}_co_next{k}"))
            e.press("DOWN", 6)
            e.wait(60)
            pages.append(png(ctx, e, f"{look}_co_next2_chart"))
            for i, p in enumerate(pages):
                frames.append((p, {"title": f"CO page {i + 1} ({look})", "plain": True, "lines": ["map menu > CO, RIGHT through the armies: Caulder's page is one of them (white hair)."]}))
        except Exception as ex:
            ctx.log(f"CO page ({look}): {ex}")
        e.close()
    sheet(frames, os.path.join(out, "gauntlet_07_extras_sheet.png"), "Chrome Meridian: capture box, panel and CO pages of the Silver Nova lines (three looks)")


@test(name="gauntlet_lines_pictures_sn_units", modes=("ds",))
def gauntlet_lines_pictures_sn_units(ctx):
    """Silver Nova's units on the map as an *enemy* (Chrome Meridian: Caulder's corps at the start of the player's turn, unmoved, none greyed: every unit's flags are 0) in the three looks, beside the
    player's Silver Nova (`silver_nova_gauntlet_looks`' aw2_map0) and the Versus skin (`armyskin scenario units`), when those pictures exist: they must show the same palette (light
    helmets and trim, dark charcoal tanks with white highlights: the skin's design, not a greyed-out unit). One sheet `gauntlet_07_sn_units_sheet.png`."""
    from PIL import Image, ImageDraw
    info = gm.MAPS[6]
    out = os.environ.get("AW2TEST_REVIEW_DIR") or ctx.out
    os.makedirs(out, exist_ok=True)
    tiles = []
    for look, env in LOOKS:
        e, g, d = start(ctx, info, env=env)
        d.capture(ctx, info.lines[0].hq, army=info.player)
        d.settle()
        ctx.check(all(not (u["flags"] & 1) for u in g.units(army=2)), f"{look}: Caulder's units are all unmoved (none is greyed by a done flag)")
        g.goto(*info.lines[1].hq)
        e.wait(60)
        tiles.append((f"Caulder's corps, enemy skin ({look})", png(ctx, e, f"{look}_caulder_units")))
        e.close()
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    for label, rel in (("Silver Nova as the player (released Gauntlet look, aw2)", "tools/aw2test/out/ds/silver_nova_gauntlet_looks/aw2_map0.png"),
                       ("Silver Nova in Versus (armyskin scenario units)", "devkit/work/armyskin/scenario_units/units_s0.png")):
        p = os.path.join(repo, rel)
        if not os.path.exists(p) and os.path.exists(p[:-4] + ".bmp"):
            Image.open(p[:-4] + ".bmp").convert("RGB").save(p)
        if os.path.exists(p):
            tiles.append((label, p))
    ims = [(t, Image.open(p).convert("RGB")) for t, p in tiles]
    w, h = 480, 320
    sheet = Image.new("RGB", (w * 3, (h + 24) * ((len(ims) + 2) // 3)), (18, 20, 28))
    dr = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(ims):
        x, y = (i % 3) * w, (i // 3) * (h + 24)
        sheet.paste(im.resize((w, h), Image.NEAREST), (x, y + 24))
        dr.text((x + 6, y + 6), t, fill=(255, 255, 255))
    sheet.save(os.path.join(out, "gauntlet_07_sn_units_sheet.png"))
