"""A picture walkthrough of the Gauntlet's second map, for review (`-k gauntlet_map2_pictures`): Iron Crown on day 1, each arrival's scene and the whole map with the new line on it, Rachel's fall and the switch scene,
Asuka's Keep (its opening scene, the whole fortress without the rain's fog, close-ups of the gate, the cannons and the west rim, the Silver Nova army on it and in a battle scene), the victory. One sheet:
`gauntlet_map2_sheet.png` in the test's output (and `AW2TEST_REVIEW_DIR`)."""

import os
import textwrap

from aw2test import gauntlet as ga
from aw2test import dscampaign as dc
from aw2test import stitch
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test import paths
from aw2test.harness import test
from tests.test_bh2_progression import dialogue_pic
from tests.test_bh2_review import home
from tests.test_bh_review import Quiet, unfog
from tests.test_gauntlet_map2 import png, start, stage, to_player_turn, wait_stage

HQ_NAMES = {"grit": "Grit (Blue Moon)", "jess": "Jess (Green Earth)", "kanbei": "Kanbei (Yellow Comet)", "rachel": "Rachel (Orange Star)"}


def sheet(frames, path, title):
    from PIL import Image, ImageDraw, ImageFont
    font = lambda s: ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", s)
    f1, f2, f3 = font(15), font(12), font(11)
    ims = [Image.open(p).convert("RGB") for p, _ in frames]
    w, h = 736, 448
    cols, pad, text_h = 2, 14, 110
    rows = (len(ims) + cols - 1) // cols
    out = Image.new("RGB", (cols * w + (cols + 1) * pad, rows * (h + text_h) + (rows + 1) * pad + 44), (18, 20, 28))
    d = ImageDraw.Draw(out)
    d.text((pad, 12), title, fill=(255, 220, 90), font=f1)
    for i, ((p, info), im) in enumerate(zip(frames, ims)):
        cx, cy = i % cols, i // cols
        ox, oy = pad + cx * (w + pad), 44 + pad + cy * (h + text_h + pad)
        if info.get("plain"):
            sc = min(w / im.width, h / im.height)
            big = im.resize((int(im.width * sc), int(im.height * sc)), Image.NEAREST)
            im = Image.new("RGB", (w, h), (0, 0, 0))
            im.paste(big, ((w - big.width) // 2, (h - big.height) // 2))
        else:
            im = im.copy()
            dr = ImageDraw.Draw(im)
            for (name, (x, y), state) in info.get("marks", []):
                col = {"next": (255, 230, 40), "taken": (90, 255, 120)}.get(state, (255, 255, 255))
                for r in (13, 14, 15):
                    dr.ellipse((x * 16 + 8 - r, y * 16 + 8 - r, x * 16 + 8 + r, y * 16 + 8 + r), outline=col)
                tag = name + ("  NEXT" if state == "next" else "  taken" if state == "taken" else "")
                tw = dr.textlength(tag, font=f3)
                tx = min(max(x * 16 + 8 - tw / 2, 2), im.width - tw - 4)
                ty = y * 16 - 26 if y > 3 else y * 16 + 22
                dr.rectangle((tx - 2, ty - 1, tx + tw + 2, ty + 12), fill=(0, 0, 0))
                dr.text((tx, ty), tag, fill=col, font=f3)
            sc = min(w / im.width, h / im.height)
            im = im.resize((int(im.width * sc), int(im.height * sc)), Image.NEAREST)
        out.paste(im, (ox, oy))
        d.text((ox, oy + h + 6), f"{i + 1}. {info['title']}", fill=(255, 255, 255), font=f1)
        for j, line in enumerate(t for ln in info["lines"] if ln for t in textwrap.wrap(ln, 100)):
            d.text((ox, oy + h + 28 + 15 * j), line, fill=(200, 210, 230), font=f2)
    out.save(path)
    return path


def crop_pic(ctx, g, e, at, name):
    """The screen with the cursor at `at` (a close-up of a place)."""
    g.goto(*at)
    e.wait(50)
    return png(ctx, e, name)


def battle_scene(ctx, e, g, d, me=1, them=2, tag="battle"):
    """The battle scene of the player's Tank against a Black Hole unit put next to it (animation option A on): the frame with the most colours."""
    from aw2test import ram
    from PIL import Image
    g._units_base = g._players_base = None
    e.w8(ram.ANIM_OPTS, 1)
    foe = next((u for u in g.units(army=them) if u["type"] in (5, 8)), None)
    if foe is None:
        return None
    from aw2test.game import NavError
    mine = free = None
    for cand in [u for u in g.units(army=me) if u["type"] == 5 and not u["flags"] & 0x08]:
        spot = next(((cand["x"] + dx, cand["y"] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                     if g.unit_at(cand["x"] + dx, cand["y"] + dy) is None and d.owner((cand["x"] + dx, cand["y"] + dy)) == 0), None)
        if spot is None:
            continue
        d.place_unit(foe, *spot)
        e.wait(10)
        ctx.log(f"cand {cand} foe at {spot} foe rec {g.unit_at(*spot)}")
        try:
            g.select(cand["x"], cand["y"])
        except NavError as ex:
            ctx.log(f"select {cand['x'], cand['y']} failed: {ex}")
            continue
        mine, free = cand, spot
        break
    if mine is None:
        return None
    g.move_to(mine["x"], mine["y"])
    g.choose("Fire", g.ACTION_MENU)
    g.pick_target(*free)
    best, ink = None, -1
    for k in range(30):
        p = png(ctx, e, f"{tag}_{k:02d}")
        n = len(set(Image.open(p).convert("RGB").getdata()))
        if n > ink:
            best, ink = p, n
        e.wait(10)
    g.wait_for_input()
    g._units_base = g._players_base = None
    left = g.unit_at(*free)
    if left is not None:
        d.remove_unit(left)                 # (the placed foe goes: the run goes on without it)
    e.wait(10)
    return best


@test(name="gauntlet_map2_pictures", modes=("ds",))
def gauntlet_map2_pictures(ctx):
    """Iron Crown and Asuka's Keep, picture by picture (Asuka picked as the player's CO: nobody else's face is on the sheet by chance)."""
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.open(map=ga.MAP2)
    d.choose_cos(1, prefs=[ga.ANDY])
    d.pick_colour(ga.EMERALD_SUN, free=[ga.EMERALD_SUN])
    frames = []
    pic = None
    for _ in range(900):
        if d.in_battle() and e.u32(0x0849_9598) != 0 and d.scripts_running():
            pic = dialogue_pic(ctx, e, d, "intro")
            break
        e.press("A", 4) if d.scripts_running() else None
        e.wait(10)
    ctx.require(d.in_battle(), "Iron Crown loaded")
    if pic:
        frames.append((pic, {"title": "Iron Crown opens with Grit", "plain": True, "lines": ["Mission start: Grit (Blue Moon) speaks over his river line. Map 2 of the Gauntlet; the player is Silver Nova, the fifth army."]}))
    d.leave_setup()
    d.wait_control()
    to_player_turn(e, g, d)
    w, h = d.size()
    HQS = [(HQ_NAMES[k], ga.IRON[k], "") for k in ("grit", "jess", "kanbei", "rachel")]

    def marks(taken, nxt):
        return [(HQ_NAMES[k] if k != "player" else "the player", ga.IRON[k], "taken" if i < taken else "next" if i == nxt else "") for i, k in enumerate(("grit", "jess", "kanbei", "rachel"))]

    def full(tag, unfogged=False):
        home(g, e)
        if unfogged:
            unfog(g, e)
        return stitch.stitch(Quiet(ctx), g, tag, w, h)

    frames.append((full("iron_day1"), {"title": "Day 1: only Grit's line is on the map", "marks": marks(0, 0), "lines": [
        "Iron Crown, 40 x 26 land map in five armies: the Silver Nova player in the south-west camp, Grit (Blue Moon) behind the Aube in the west-centre.",
        "Jess's forests, Kanbei's mountain keep and Rachel's lowlands are plain ground: no HQ, no units, no turn yet. Lake (middle) joins the Aube, the Brenne and the Marle."]}))
    day1 = png(ctx, e, "day1_screen")
    for k, (key, army, who, nxt) in enumerate(ga.IRON_ORDER[:3]):
        d.capture(ctx, ga.IRON[key], army=5)
        scene = dialogue_pic(ctx, e, d, f"arrive_{nxt}")
        ctx.check(scene is not None, f"{who}'s fall played an arrival scene")
        if scene:
            frames.append((scene, {"title": f"{who}'s HQ falls: {ga.IRON_ORDER[nxt - 1][2]} arrives", "plain": True, "lines": ["The arrival scene (each CO's own words and face)."]}))
        d.settle()
        ctx.check(len(g.units(army=nxt)) > 0, f"army {nxt} has landed")
        frames.append((full(f"iron_line{nxt}"), {"title": f"{ga.IRON_ORDER[nxt - 1][2]}'s line on the map", "marks": marks(k + 1, k + 1), "lines": [
            f"{len(g.units(army=nxt))} units landed in their zone, the HQ built, the zone's properties theirs, a war chest paid. The fallen lines stay on the map and fight on without income."]}))
    d.capture(ctx, ga.IRON["rachel"], army=5)
    scene = dialogue_pic(ctx, e, d, "switch")
    if scene:
        frames.append((scene, {"title": "Rachel's HQ falls: Asuka calls the survivors to her keep", "plain": True, "lines": ["The last line of Iron Crown has fallen: a scene, then the battle moves in place to Asuka's Keep."]}))
    wait_stage(ctx, e, g, d, 1)
    ctx.eq(stage(e), 1, "on Asuka's Keep")
    intro = dialogue_pic(ctx, e, d, "keep_intro")
    if intro:
        frames.append((intro, {"title": "Asuka's Keep: her opening words", "plain": True, "lines": ["Asuka (Black Hole), in her own voice and with her own face; the weather is her rain (fog)."]}))
    d.wait_control()
    g._units_base = g._players_base = None
    w, h = d.size()
    game_pic = png(ctx, e, "keep_first_turn")
    frames.append((game_pic, {"title": "Asuka's Keep, first turn (the rain's fog): the Silver Nova army lands", "plain": True, "lines": [
        "The player's survivors (Silver Nova look on Orange Star's colour, in fog) on the landing cells in the south-west; Black Hole's colour is Asuka's."]}))
    home(g, e)
    unfog(g, e)
    keep = stitch.stitch(Quiet(ctx), g, "keep_full", w, h)
    frames.append((keep, {"title": "Asuka's Keep, the whole fortress (fog off for the picture)", "marks": [("Asuka's HQ", ga.KEEP_ASUKA, "next")], "lines": [
        "Plateau with Black Crystals, two Black Cannons (dark 3x3) on its south wall, minicannons at the gate and on the west rim, the Laser on the moor, the Styx with four bridges; the player lands in the south-west."]}))
    frames.append((crop_pic(ctx, g, e, (22, 10), "keep_gate"), {"title": "The south gate: Black Cannons and minicannons cover the bridges", "plain": True, "lines": ["Cannons at (19,9) and (25,9), minicannons at (21,10) and (23,10) either side of the gate."]}))
    frames.append((crop_pic(ctx, g, e, (12, 8), "keep_west"), {"title": "The west rim: minicannons and the Laser", "plain": True, "lines": ["Laser (11,9) on the moor (row 9, column 11), minicannons at (15,3) and (15,7) face west."]}))
    d.capture(ctx, ga.KEEP_ASUKA, army=1)
    shots = []
    for k in range(120):
        if k < 8:
            shots.append(png(ctx, e, f"keep_win{k}"))
        if e.u8(0x03003FC3) or not d.in_battle():
            pass
        if d.scripts_running():
            e.press("A", 4)
        if not d.in_battle():
            break
        e.wait(40)
    from PIL import Image
    import numpy as np
    best = max(shots, key=lambda p: float(np.asarray(Image.open(p).convert("L"), float).std()))
    frames.append((best, {"title": "Asuka's HQ falls: her last words", "plain": True, "lines": ["Her HQ is held until the Win ends the battle: her own face on her lines."]}))
    e.close()
    out = os.environ.get("AW2TEST_REVIEW_DIR") or ctx.out
    os.makedirs(out, exist_ok=True)
    sheet(frames, os.path.join(out, "gauntlet_map2_sheet.png"), "Gauntlet map 2: Iron Crown and Asuka's Keep (played with real captures; the game's own pictures)")
    ctx.log("wrote " + os.path.join(out, "gauntlet_map2_sheet.png"))


@test(name="gauntlet_map2_battle_scenes", modes=("ds",))
def gauntlet_map2_battle_scenes(ctx):
    """Battle scenes of the Silver Nova army on both stages (animations on): the player's Tank fires on a unit placed next to it. `gauntlet_map2_battle_sheet.png`: the skin sits on Black Hole's colour on
    Iron Crown and moves to Orange Star's on Asuka's Keep, where Asuka is Black Hole's."""
    from PIL import Image
    e, g, d = start(ctx)
    frames = []
    one = battle_scene(ctx, e, g, d, me=5, them=1, tag="iron_battle")
    ctx.require(one is not None, "a battle scene on Iron Crown")
    frames.append((one, {"title": "Iron Crown: Silver Nova (on Black Hole's colour) vs Grit", "plain": True, "lines": ["Animation option A; the foe was placed next to the Tank for the picture."]}))
    for key, army, who, nxt in ga.IRON_ORDER:
        d.capture(ctx, ga.IRON[key], army=5)
        if nxt:
            d.settle()
    wait_stage(ctx, e, g, d, 1)
    d.dialogue()
    d.wait_control()
    e.wait(300)
    g._units_base = g._players_base = None
    g.wait_for_input()
    ctx.log(f"stage two: army {g.current_army()}, scripts {d.scripts_running()}, day {e.u16(dc.DAY)}")
    two = battle_scene(ctx, e, g, d, me=1, them=2, tag="keep_battle")
    ctx.require(two is not None, "a battle scene on Asuka's Keep")
    frames.append((two, {"title": "Asuka's Keep: Silver Nova (now on Orange Star's colour) vs Asuka", "plain": True, "lines": ["The skin moved with the stage switch: sage and red crests, not Orange Star's red or Black Hole's grey."]}))
    e.close()
    out = os.environ.get("AW2TEST_REVIEW_DIR") or ctx.out
    os.makedirs(out, exist_ok=True)
    sheet(frames, os.path.join(out, "gauntlet_map2_battle_sheet.png"), "Gauntlet map 2: the Silver Nova army's battle scenes on both stages")
