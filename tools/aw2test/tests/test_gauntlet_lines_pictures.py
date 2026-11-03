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


def scene_pics(ctx, e, d, tag, most=4):
    """The boxes of the running script, one picture each (A through them)."""
    pics = []
    for _ in range(400):
        if d.scripts_running():
            if len(pics) < most:
                e.wait(70)
                pics.append(png(ctx, e, f"{tag}_box{len(pics)}"))
            e.press("A", 4)
        elif pics:
            break
        e.wait(20)
    return pics


def pictures(info):
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
                bs = battle_scene(ctx, e, g, d, me=info.player, them=nxt.army, tag=f"{look}_battle_{nxt.name}")
                if bs:
                    frames.append((bs, {"title": f"Battle scene: the player against {nxt.name}'s army", "plain": True, "lines": ["Animations on; the foe was placed next to the player's Tank for the picture."]}))
            e.close()
            path = sheet(frames, os.path.join(out, f"{info.key}_{look}_sheet.png"), f"Gauntlet {info.title} ({look})")
            ctx.log("wrote " + path)
    fn.__name__ = f"gauntlet_lines_pictures_{info.key}"
    test(modes=("ds",))(fn)


for _info in gm.MAPS.values():
    pictures(_info)
