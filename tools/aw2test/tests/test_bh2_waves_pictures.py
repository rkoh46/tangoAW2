"""Pictures of a BH2 mission's day waves, any mission (`-k bh2_waves_pictures`; `aw2dev bh2 waves --mission NN` runs it and composes the sheet). Environment:
AW2TEST_WAVES_MISSION (default 32), AW2TEST_WAVES_OUT (the folder for the PNGs, default the test's own), AW2TEST_WAVES_CKPT (a folder: the console is also saved as checkpoints there, for the real app's
looks: `m<N>_after_setup`, `m<N>_day<D>_box` while the scene's first box is up and `m<N>_day<D>_wave` once control is back, the cursor on the wave).

The waves come from the campaign model, never from this file: the example `aw2_campaign_waves` (tango-gamesupport-aw2/examples) lists every day-based trigger of a mission (its day, the units a
Spawn lands, the boxes of its scene). The mission is entered through its CO screens (Setup phase and opening scene played through), the whole map is stitched after Setup, then turns end until each wave's day:
the first box of the day's scene is photographed, and after the scene the whole map and a cursor view on the wave. Checks: the wave's units are on the map (up to the army's 50-unit cap), a scene day shows a box."""

import os
import subprocess

from PIL import Image

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import dscampaign as dc
from aw2test import stitch
from aw2test.harness import test
from tests.test_bh2_review import home
from tests.test_bh_review import Quiet

DAY = 0x03004080
REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def waves_of(n, campaign="bh2"):
    """{day: {"units": [(army, kind, x, y)], "boxes": scene boxes}} of mission n from the campaign model (the example binary's lines)."""
    exe = os.path.join(REPO, "target", "release", "examples", "aw2_campaign_waves")
    out = subprocess.run([exe, campaign, f"bh2_{n:02d}"], capture_output=True, text=True, check=True).stdout
    return parse_waves(out)


def parse_waves(text):
    waves = {}
    for line in text.splitlines():
        key, day, spawn, boxes = line.split("\t")
        w = waves.setdefault(int(day), {"units": [], "boxes": 0})
        if spawn != "-":
            w["units"] += [tuple(int(v) for v in u.split(":")) for u in spawn.split(";")]
        w["boxes"] += int(boxes)
    return waves


def save_png(path, dest):
    Image.open(path).convert("RGB").save(dest)


def play_to_day(ctx, e, g, d, day, ck, out, tag):
    """End turns until army 1's turn of `day`. When the day's scene is up the first box is photographed (and saved as a checkpoint); A through the rest. Returns whether a box was seen."""
    seen = False
    for _ in range(40):
        if e.u16(DAY) >= day:
            break
        d0 = e.u16(DAY)
        a2.end_turn(e, g, d)
        stable, last = 0, None
        for _ in range(4000):
            if e.u16(DAY) > d0 or e.u8(dc.LAST_RESULT):
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(20)
    stable, last = 0, None
    for _ in range(1500):
        t = d.text_shown()
        stable = stable + 1 if t and t == last else 0
        last = t
        if d.scripts_running():
            if t and stable == 5 and not seen:
                seen = True
                if ck:
                    e.cmd(f"checkpoint save {tag}_box")
                save_png(e.shot(os.path.join(ctx.out, f"{tag}_box")), os.path.join(out, f"{tag}_box.png"))
            if stable >= 8:
                e.press("A", 4)
                stable = 0
        elif not t and seen or (not d.scripts_running() and _ > 60):
            break
        e.wait(4)
    d.wait_control()
    g._units_base = g._players_base = None
    return seen


@test(name="bh2_waves_pictures", modes=("ds",))
def bh2_waves_pictures(ctx):
    n = int(os.environ.get("AW2TEST_WAVES_MISSION", "32"))
    out = os.environ.get("AW2TEST_WAVES_OUT") or ctx.out
    ck = os.environ.get("AW2TEST_WAVES_CKPT")
    os.makedirs(out, exist_ok=True)
    waves = {day: w for day, w in waves_of(n).items() if w["units"]}
    ctx.require(waves, f"M{n} has day waves in the campaign model (units spawned on a day)")
    ctx.log(f"M{n} {b2.TITLES[n]}: waves on days {sorted(waves)}: " + str({k: (len(w['units']), w['boxes']) for k, w in sorted(waves.items())}))
    e, g, d = b2.enter(ctx, n, env={"AW2_CKPT_DIR": ck} if ck else None)
    w, h = d.size()
    if b2.PICKS.get(n):
        d.leave_setup()
        a2.intro(ctx, e, d, f"m{n}", (0,))
        d.wait_control()
    g._units_base = g._players_base = None
    home(g, e)
    if ck:
        e.cmd(f"checkpoint save m{n}_after_setup")
    save_png(stitch.stitch(Quiet(ctx), g, f"m{n}_after_setup", w, h), os.path.join(out, f"m{n}_after_setup_map.png"))
    for day in sorted(waves):
        army = waves[day]["units"][0][0]
        before = {u["id"] for u in g.units(army=army)}
        tag = f"day{day}"
        box = play_to_day(ctx, e, g, d, day, ck, out, f"m{n}_{tag}")
        ctx.eq(e.u16(DAY), day, f"M{n}: it is day {day}")
        want = len(waves[day]["units"])
        on = [c for c in ((x, y) for _, _, x, y in waves[day]["units"]) if (g.unit_at(*c) or {}).get("army") == army]
        free = 50 - len(before)               # (production and a trigger's reinforcements stop at 50 units an army)
        ctx.check(len(on) >= 1 and len(on) >= min(want, free) // 2, f"M{n} day {day}: the wave's units stand on their cells ({len(on)} of {want} in the list, {free} slots free)")
        if waves[day]["boxes"]:
            ctx.check(box, f"M{n} day {day}: the wave's scene showed a box ({waves[day]['boxes']} boxes in the model)")
        cx = sum(x for _, _, x, _ in waves[day]["units"]) // want
        cy = sum(y for _, _, _, y in waves[day]["units"]) // want
        try:
            g.goto(cx, cy)
        except Exception:
            home(g, e)
        e.wait(30)
        if ck:
            e.cmd(f"checkpoint save m{n}_{tag}_wave")
        home(g, e)
        save_png(stitch.stitch(Quiet(ctx), g, f"m{n}_{tag}", w, h), os.path.join(out, f"m{n}_{tag}_map.png"))
        try:
            g.goto(cx, cy)
        except Exception:
            pass
    e.close()
