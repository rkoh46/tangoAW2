"""BH2 M25 The Last Accord (development build, crate::bh2_campaign): the TakeOver chain played through, one picture of the whole map at each of six stages (`-k bh2_m25_progression`).

The mission is entered through its CO screen (Crumb as the partner), deployed, and played to the end with real captures: a player's Infantry is put on the next stage HQ one capture point from done and captures it
(the game's own capture, its ownership change, its held-HQ rule and the trigger lists that follow it). After every capture the harness reads who commands Orange Star's army, what was spawned, who owns each stage HQ
and takes the game's own full-map picture (the cursor's sweep, 16 pixels a cell; no fog in this mission). The six frames are put on one sheet, labelled and with the stage HQs marked: m25_progression.png (AW2TEST_REVIEW_DIR).

Frames: 1 the start (Nell holds the citadel), 2 after Nell's HQ (Olaf and his troops), 3 after Olaf's HQ (Kanbei), 4 after Kanbei's HQ (Eagle), 5 after Eagle's HQ (Aria), 6 Aria's HQ taken (the mission is won).
Every stage HQ is an Allied (army 2) building from the first frame: the map's `zone` lines give the Allies every property east of Nell's keep, so no future HQ reads as neutral or as the player's."""

import os
import textwrap

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import dscampaign as dc
from aw2test import stitch
from aw2test.harness import test
from tests.test_bh2_review import home, save
from tests.test_bh_review import Quiet

HQS = [("Nell", (8, 10)), ("Olaf", (24, 6)), ("Kanbei", (39, 6)), ("Eagle", (38, 20)), ("Aria", (22, 21))]
CO_NAMES = {0: "Nell", 1: "Andy", 2: "Max (Aria's slot)", 3: "Olaf", 6: "Kanbei", 8: "Eagle"}
KINDS = ["-", "Infantry", "Mech", "Md Tank", "Megatank", "Tank", "Recon", "APC", "Neotank", "Piperunner", "Artillery", "Rockets", "Stealth", "Black Bomb", "Anti-Air", "Missiles", "Fighter", "Bomber",
         "Black Boat", "B Copter", "T Copter", "Battleship", "Cruiser", "Lander", "Sub", "-", "Carrier", "Oozium"]
MAP = dc.MAP
WAVES = [18, 9, 11, 8]          # (the wave lists of crate::bh2_campaign: OLAF_WAVE, KANBEI_WAVE, EAGLE_WAVE, ARIA_WAVE)


def owner(e, x, y):
    row = e.u16(MAP + 0x417A + 2 * y)
    return e.u8(MAP + 0x1432 + row + x) >> 5


def summary(e, g):
    units = g.units(army=2)
    kinds = {}
    for u in units:
        kinds[KINDS[u["type"]]] = kinds.get(KINDS[u["type"]], 0) + 1
    return {"co": CO_NAMES.get(g.player(2)["co"], str(g.player(2)["co"])), "n": len(units), "kinds": kinds, "ids": {(u["id"], u["type"], u["x"], u["y"]) for u in units}, "owners": [owner(e, *c) for _, c in HQS]}


def capture(ctx, e, g, d, cell):
    """A fresh player Infantry on `cell`, one capture point from done, captures it (the game's own Capture)."""
    g._units_base = g._players_base = None
    inf = next(u for u in g.units(army=1) if u["type"] == 1 and not u["flags"] & 0x08 and (u["x"], u["y"]) != cell)
    d.place_unit(inf, *cell)
    a = g.unit_addr(inf["id"])
    e.w8(a + 5, (e.u8(a + 5) & 7) | (19 << 3))
    e.wait(4)
    g.select(*cell)
    e.wait(8)
    d.dialogue()
    menu = g.move_to(*cell)
    d.dialogue()
    ctx.require(any(n.lower().startswith("capt") for n in menu["names"]), f"Capture offered at {cell} ({menu['names']})")
    g.choose("Capt", g.ACTION_MENU)
    e.wait(120)


def settle(e, g, d, frames=6000):
    """Through the scripts the capture started (the TakeOver's scene, the spawns) until the cursor answers."""
    for _ in range(frames // 40):
        if d.scripts_running():
            e.press("A", 4)
        e.wait(30)
        if not d.scripts_running() and d.in_battle():
            e.wait(30)
            if not d.scripts_running():
                break
    g._units_base = g._players_base = None


def sheet(ctx, frames, path):
    from PIL import Image, ImageDraw, ImageFont
    font = lambda s: ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", s)
    f1, f2, f3 = font(15), font(12), font(11)
    ims = [Image.open(p).convert("RGB") for p, _ in frames]
    w, h = ims[0].size
    cols, pad, text_h = 2, 14, 125
    rows = (len(ims) + cols - 1) // cols
    W = cols * w + (cols + 1) * pad
    H = rows * (h + text_h) + (rows + 1) * pad + 44
    out = Image.new("RGB", (W, H), (18, 20, 28))
    d = ImageDraw.Draw(out)
    d.text((pad, 12), "M25 The Last Accord: the TakeOver chain, played through with real captures (the game's own full-map picture at each stage)", fill=(255, 220, 90), font=f1)
    for i, ((p, info), im) in enumerate(zip(frames, ims)):
        cx, cy = i % cols, i // cols
        ox, oy = pad + cx * (w + pad), 44 + pad + cy * (h + text_h + pad)
        if info["next"] < 0:                                  # (the game's own victory screen, enlarged to the map's size)
            sc = min(w / im.width, h / im.height)
            big = im.resize((int(im.width * sc), int(im.height * sc)), Image.NEAREST)
            im = Image.new("RGB", (w, h), (0, 0, 0))
            im.paste(big, ((w - big.width) // 2, (h - big.height) // 2))
        dr = ImageDraw.Draw(im)
        for k, (name, (x, y)) in enumerate(HQS if info["next"] >= 0 else []):
            col = (255, 255, 255)
            if info["next"] == k:
                col = (255, 230, 40)
            elif k < info["done"]:
                col = (90, 255, 120)
            for r in (13, 14, 15):
                dr.ellipse((x * 16 + 8 - r, y * 16 + 8 - r, x * 16 + 8 + r, y * 16 + 8 + r), outline=col)
            tag = f"{k + 1} {name}" + ("  NEXT" if info["next"] == k else "  taken" if k < info["done"] else "")
            tw = dr.textlength(tag, font=f3)
            tx = min(max(x * 16 + 8 - tw / 2, 2), w - tw - 4)
            ty = y * 16 - 26 if y > 3 else y * 16 + 22
            dr.rectangle((tx - 2, ty - 1, tx + tw + 2, ty + 12), fill=(0, 0, 0))
            dr.text((tx, ty), tag, fill=col, font=f3)
        out.paste(im, (ox, oy))
        d.text((ox, oy + h + 6), f"{i + 1}. {info['title']}", fill=(255, 255, 255), font=f1)
        wrapped = [t for line in info["lines"] if line for t in textwrap.wrap(line, 100)]
        for j, line in enumerate(wrapped):
            d.text((ox, oy + h + 28 + 15 * j), line, fill=(200, 210, 230), font=f2)
    out.save(path)
    return path


@test(name="bh2_m25_progression", modes=("ds",))
def bh2_m25_progression(ctx):
    n = 25
    e, g, d = b2.enter(ctx, n)
    w, h = d.size()
    d.leave_setup()
    a2.intro(ctx, e, d, "m25", (0,))
    d.wait_control()
    g._units_base = g._players_base = None
    frames = []
    prev = summary(e, g)
    ctx.log(f"start: {prev['co']} commands Orange Star, {prev['n']} units, HQ owners {prev['owners']}")
    ctx.check(all(o == 2 for o in prev["owners"]), f"every stage HQ is an Allied (army 2) building at the start: owners {prev['owners']}")

    def shoot(tag):
        home(g, e)
        return stitch.stitch(Quiet(ctx), g, f"m25_{tag}", w, h)

    frames.append((shoot("stage1"), {"title": "Start: Nell holds the citadel", "next": 0, "done": 0, "lines": [
        f"Orange Star's army is commanded by {prev['co']}; {prev['n']} units; every stage HQ is already an Allied building (owners {prev['owners']}).",
        "The next HQ to take is 1 Nell (8,10). The other four are Allied too, and capturing one early moves nothing.", "", ""]}))
    wins = []
    for k, (name, cell) in enumerate(HQS):
        capture(ctx, e, g, d, cell)
        settle(e, g, d)
        cur = summary(e, g)
        ctx.log(f"after {name}'s HQ: {cur['co']} commands, {cur['n']} units ({cur['n'] - prev['n']:+d}), HQ owners {cur['owners']}, day {e.u16(dc.DAY)}")
        new = cur["ids"] - prev["ids"]
        gone = len(prev["ids"] - cur["ids"])
        kinds = {}
        for (_, t, _, _) in new:
            kinds[KINDS[t]] = kinds.get(KINDS[t], 0) + 1
        ctx.check(cur["owners"][k] == 1, f"{name}'s HQ is the player's after the capture (owners {cur['owners']})")
        wins.append((name, cur, kinds))
        if k < len(HQS) - 1:
            ctx.check(len(new) >= WAVES[k] - 1, f"{name}'s fall brings the whole wave ({len(new)} new units for {WAVES[k]} in the list; {gone} of the old line retired to make room; {cur['n']} units, cap 50)")
        last = k == len(HQS) - 1
        if last:
            ended = bool(e.u8(dc.LAST_RESULT)) or not d.in_battle()
            ctx.check(ended, "Aria's HQ taken after the other four: the mission ends in a win")
            pic = a2.pic(ctx, e, "m25_win")
            frames.append((pic, {"title": "Win: Aria's HQ falls", "next": -1, "done": 5, "lines": [
                f"Capturing 5 Aria (22,21) with every earlier HQ already taken wins the mission (the game's own victory).",
                f"Orange Star's last commander: {cur['co']}; {cur['n']} units on the map at the end.", "", ""]}))
        else:
            nxt = HQS[k + 1][0]
            spawned = ", ".join(f"{v} {kd}" for kd, v in sorted(kinds.items(), key=lambda t: -t[1]))
            ctx.check(cur["co"] != prev["co"], f"{name}'s fall changes Orange Star's commander ({prev['co']} -> {cur['co']})")
            pth = shoot(f"stage{k + 2}")
            frames.append((pth, {"title": f"After {name}'s HQ falls: {cur['co']} takes over", "next": k + 1, "done": k + 1, "lines": [
                f"{name}'s HQ (taken) -> Orange Star's army goes on under {cur['co']}: {len(new)} fresh units arrive, {gone} of the old line retire (cap 50): {cur['n']} now.",
                f"New units: {spawned or 'none (the 50-unit army cap?)'}.",
                f"The next HQ to take is {k + 2} {nxt} {HQS[k + 1][1]}; HQ owners now {cur['owners']} (1 = player, 2 = Allied).", ""]}))
        prev = cur
    out = os.environ.get("AW2TEST_REVIEW_DIR") or ctx.out
    os.makedirs(out, exist_ok=True)
    sheet(ctx, frames, os.path.join(out, "m25_progression.png"))
    for i, (p, _) in enumerate(frames):
        save(ctx, p, n, f"stage{i + 1}")
    ctx.log("wrote " + os.path.join(out, "m25_progression.png"))
    e.close()
