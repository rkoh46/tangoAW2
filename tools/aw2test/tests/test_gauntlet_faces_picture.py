"""Every CO of the Gauntlet's maps: the face as a dialogue box draws it next to the same CO on AW2's own CO screen (`-k gauntlet_faces_vs_copage`): the screen the Gauntlet's CO pick opens shows each CO with
the colours the battle uses for it (`GetLoadedCoPalette`). Pictures in the test's folder (`AW2TEST_FACES` copies them where a person looks); tools/aw2test/compose_faces.py makes `faces_vs_copage.png` of them."""

import os

from PIL import Image

from aw2test import gauntlet as ga
from aw2test import gauntlet_maps as gm
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test
from tests.test_gauntlet_lines import start
from tests.test_gauntlet_map2 import png


def box_crop(im):
    w, h = im.size

    def pink(y0, y1):
        return sum(1 for y in range(y0, y1, 3) for x in range(80, 220, 6) if im.getpixel((x, y))[0] > 235 and 225 < im.getpixel((x, y))[1] < 250)
    return im.crop((0, 0, 64, 44)) if pink(4, 40) >= pink(h - 40, h - 4) else im.crop((0, h - 44, 64, h))


def cos_of_maps():
    out = {}
    for info in gm.MAPS.values():
        for l in info.lines:
            out.setdefault(l.co, l.name)
    return out


@test(modes=("ds",))
def gauntlet_faces_vs_copage_boxes(ctx):
    """The box face of every CO of every new map (the departing CO's first box, the arriving CO's last)."""
    out = os.environ.get("AW2TEST_FACES") or ctx.out
    os.makedirs(out, exist_ok=True)
    for info in gm.MAPS.values():
        e, g, d = start(ctx, info)
        for k, l in enumerate(info.lines[:-1]):
            nxt = info.lines[k + 1]
            d.capture(ctx, l.hq, army=info.player)
            boxes = []
            for _ in range(200):
                if not d.scripts_running():
                    break
                e.wait(90)
                if any(f == 0x08014401 for _, _, f in g.procs()):
                    for _ in range(20):                                # (a flash or a fade is waited out)
                        im = Image.open(png(ctx, e, f"{info.key}_{nxt.name}_b{len(boxes)}")).convert("RGB")
                        px = list(im.getdata())
                        if sum(r + g_ + b for r, g_, b in px) / (3 * len(px)) < 205:
                            break
                        e.wait(8)
                    boxes.append(box_crop(im))
                e.press("A", 4)
                e.wait(30)
            if boxes:
                boxes[0].save(os.path.join(out, f"box_{l.co}.png"))
                boxes[-1].save(os.path.join(out, f"box_{nxt.co}.png"))
            d.settle()
        e.close()


@test(modes=("ds",))
def gauntlet_faces_vs_copage_screens(ctx):
    """AW2's CO screen with the cursor on each CO the maps use."""
    out = os.environ.get("AW2TEST_FACES") or ctx.out
    os.makedirs(out, exist_ok=True)
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.open(True, map=0)
    d.wait_co_screen()
    for co in cos_of_maps():
        c = None
        for _ in range(60):
            c = d.co_cursor()
            if c:
                break
            e.wait(10)
        k = c["cos"].index(co)
        tab = next(t for t in range(len(c["counts"])) if k < sum(c["counts"][:t + 1]))
        at = k - sum(c["counts"][:tab])
        for _ in range(12):
            c = d.co_cursor()
            if c["tab"] == tab:
                break
            e.press("DOWN" if c["tab"] < tab else "UP", 6)
            e.wait(30)
        for _ in range(30):
            c = d.co_cursor()
            if c["at"] == at:
                break
            e.press("RIGHT" if c["at"] < at else "LEFT", 6)
            e.wait(30)
        e.wait(60)
        ctx.check(d.co_cursor()["co"] == co, f"the CO screen's cursor is on CO {co}")
        os.replace(png(ctx, e, f"screen_{co}"), os.path.join(out, f"screen_{co}.png"))
    e.close()
