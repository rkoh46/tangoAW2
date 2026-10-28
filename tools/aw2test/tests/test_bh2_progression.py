"""BH2 M30 The Last Accord, both maps (development build, crate::bh2_campaign): the final mission played through, a picture at each stage (`-k bh2_m30_progression`).

Part one (bh2_30, five armies: Nell's Orange Star 1, Olaf's Blue Moon 2, Kanbei's Yellow Comet 3, Eagle's Green Earth 4, the player's Black Hole 5) is entered through its CO screen, deployed and played with real captures:
a player's Infantry is put on the next HQ one capture point from done and captures it (the game's own capture, its ownership change, the held-HQ rule and the trigger lists that follow it). After each capture the harness
reads which nation woke (its units before and after, by army), who owns each HQ, and takes the game's own full-map picture (the cursor's sweep, 16 pixels a cell; no fog). Eagle's HQ ends part one: a scene, then the win.
Part two (bh2_31, The Last Citadel: Aria's Orange Star against the player) is entered as the next mission: its opening scene, the full map and the capture of Aria's HQ (the campaign's victory).
The frames are put on one sheet, labelled and with the HQs marked: m25_progression_v2.png (AW2TEST_REVIEW_DIR)."""

import os
import textwrap

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import dscampaign as dc
from aw2test import stitch
from aw2test.harness import test
from tests.test_bh2_review import home, save
from tests.test_bh_review import Quiet

HQS = [("Nell", (8, 8), 1, "Orange Star"), ("Olaf", (24, 6), 2, "Blue Moon"), ("Kanbei", (39, 6), 3, "Yellow Comet"), ("Eagle", (38, 20), 4, "Green Earth")]
WAVES = [20, 16, 16]            # (the wave lists of crate::bh2_campaign: OLAF_WAVE, KANBEI_WAVE, EAGLE_WAVE)
ARMY_NAMES = {1: "Orange Star (Nell)", 2: "Blue Moon (Olaf)", 3: "Yellow Comet (Kanbei)", 4: "Green Earth (Eagle)"}
MAP = dc.MAP


def owner(e, x, y):
    row = e.u16(MAP + 0x417A + 2 * y)
    return e.u8(MAP + 0x1432 + row + x) >> 5


def counts(g, armies):
    return {a: len(g.units(army=a)) for a in armies}


def capture(ctx, e, g, d, cell, army):
    """A fresh Infantry of the player's `army` on `cell`, one capture point from done, captures it (the game's own Capture)."""
    g._units_base = g._players_base = None
    inf = next(u for u in g.units(army=army) if u["type"] == 1 and not u["flags"] & 0x08 and (u["x"], u["y"]) != cell)
    occ = g.unit_at(*cell)
    if occ is not None and occ["id"] != inf["id"]:             # (an enemy unit stands on the HQ: it is taken off first)
        d.remove_unit(occ)
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
    for _ in range(frames // 40):
        if d.scripts_running():
            e.press("A", 4)
        e.wait(30)
        if not d.scripts_running() and d.in_battle():
            e.wait(30)
            if not d.scripts_running():
                break
    g._units_base = g._players_base = None


def dialogue_pic(ctx, e, d, name, max_frames=3000):
    """Waits for the first dialogue box of the running script, photographs it, goes on through the rest. Returns the picture's path (or None)."""
    pic = None
    last, stable, n = None, 0, 0
    while n < max_frames:
        t = d.text_shown()
        stable = stable + 1 if t and t == last else 0
        last = t
        if t and stable == 5 and pic is None:
            e.wait(60)
            pic = a2.pic(ctx, e, name)
        if d.scripts_running() and (pic is not None and stable >= 8):
            e.press("A", 4)
            stable = 0
        if not d.scripts_running() and pic is not None:
            break
        e.wait(4)
        n += 4
    return pic


def sheet(ctx, frames, path):
    from PIL import Image, ImageDraw, ImageFont
    font = lambda s: ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", s)
    f1, f2, f3 = font(15), font(12), font(11)
    ims = [Image.open(p).convert("RGB") for p, _ in frames]
    w, h = 736, 448
    cols, pad, text_h = 2, 14, 140
    rows = (len(ims) + cols - 1) // cols
    W = cols * w + (cols + 1) * pad
    H = rows * (h + text_h) + (rows + 1) * pad + 44
    out = Image.new("RGB", (W, H), (18, 20, 28))
    d = ImageDraw.Draw(out)
    d.text((pad, 12), "M30 The Last Accord, both maps: the whole final mission played with real captures (the game's own pictures)", fill=(255, 220, 90), font=f1)
    for i, ((p, info), im) in enumerate(zip(frames, ims)):
        cx, cy = i % cols, i // cols
        ox, oy = pad + cx * (w + pad), 44 + pad + cy * (h + text_h + pad)
        if info.get("plain"):                                  # (a screenshot of the game: enlarged to the frame)
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


def marks(done, nxt):
    out = []
    for k, (name, cell, army, nation) in enumerate(HQS):
        out.append((f"{k + 1} {name} ({nation})", cell, "taken" if k < done else "next" if k == nxt else ""))
    return out


@test(name="bh2_m30_progression", modes=("ds",))
def bh2_m30_progression(ctx):
    n = 30
    e, g, d = b2.enter(ctx, n)
    w, h = d.size()
    d.leave_setup()
    a2.intro(ctx, e, d, "m25", (0,))
    d.wait_control()
    g._units_base = g._players_base = None
    player = 5
    frames = []
    prev = counts(g, (1, 2, 3, 4))
    ctx.log(f"start: units by army {prev}, HQ owners {[owner(e, *c) for _, c, _, _ in HQS]}")
    ctx.check([owner(e, *c) for _, c, _, _ in HQS] == [1, 2, 3, 4], "each nation owns its own HQ at the start (armies 1..4)")
    ctx.check(prev[1] >= 20 and all(0 < prev[a] <= 5 for a in (2, 3, 4)), f"Nell's army is whole; the other nations are a few holding units each: {prev}")

    def shoot(tag):
        home(g, e)
        return stitch.stitch(Quiet(ctx), g, f"m25_{tag}", w, h)

    frames.append((shoot("stage1"), {"title": "Start: Nell's Orange Star holds the river plateau", "marks": marks(0, 0), "lines": [
        f"Five armies: Orange Star (Nell) {prev[1]} units; Blue Moon (Olaf) {prev[2]}, Yellow Comet (Kanbei) {prev[3]} and Green Earth (Eagle) {prev[4]} are a few holding units round their HQs: dormant, no property but the HQ, no production.",
        "The next HQ to take is 1 Nell (8,8). No pipes: the Marne, the Sere, the lakes and the highland ring are the defences."]}))
    for k, (name, cell, army, nation) in enumerate(HQS):
        capture(ctx, e, g, d, cell, player)
        last = k == len(HQS) - 1
        if last:
            pic = dialogue_pic(ctx, e, d, "m25_scene")
            settle(e, g, d)
            ended = bool(e.u8(dc.LAST_RESULT)) or not d.in_battle()
            ctx.check(ended, "Eagle's HQ taken after the other three: part one ends in a win (the scene, then the world map)")
            ctx.check(pic is not None, "the scene after Eagle's fall was shown")
            frames.append((pic, {"title": "Eagle's HQ falls: the scene, then part one is won", "plain": True, "lines": [
                "Taking 4 Eagle (38,20) with every earlier HQ already taken plays a short scene (Eagle, then Aria) and wins part one; the campaign goes on to part two, Aria's citadel."]}))
            break
        settle(e, g, d)
        cur = counts(g, (1, 2, 3, 4))
        woke = k + 2
        ctx.log(f"after {name}'s HQ: units by army {cur}, HQ owners {[owner(e, *c) for _, c, _, _ in HQS]}, day {e.u16(dc.DAY)}")
        ctx.check(owner(e, *cell) == player, f"{name}'s HQ is the player's after the capture")
        ctx.check(cur[woke] - prev[woke] >= WAVES[k], f"{ARMY_NAMES[woke]} wakes with its whole wave ({cur[woke] - prev[woke]} new units for {WAVES[k]} in the list)")
        ctx.check(all(cur[a] == prev[a] for a in (2, 3, 4) if a != woke), f"no other dormant nation changed ({prev} -> {cur})")
        pth = shoot(f"stage{k + 2}")
        frames.append((pth, {"title": f"{name}'s HQ falls: {nation_of(woke)} joins", "marks": marks(k + 1, k + 1), "lines": [
            f"{name}'s HQ (taken): {ARMY_NAMES[woke]} wakes and lands {cur[woke] - prev[woke]} units ({cur[woke]} in all). The fallen nations stay on the map: units by army {cur}.",
            f"The next HQ to take is {k + 2} {HQS[k + 1][0]} {HQS[k + 1][1]}; HQ owners now {[owner(e, *c) for _, c, _, _ in HQS]} (1..4 their nations, 5 the player)."]}))
        prev = cur
    e.close()
    # part two: the next mission
    e, g, d = b2.enter(ctx, 31)
    w, h = d.size()
    d.leave_setup()
    scene = dialogue_pic(ctx, e, d, "m25b_scene")
    d.wait_control()
    g._units_base = g._players_base = None
    aria = len(g.units(army=2))
    ctx.log(f"part two: Aria's army {aria} units, CO id {g.player(2)['co']}")
    ctx.check(aria >= 25 and all(u["hp"] >= 10 or u["hp"] == 100 for u in g.units(army=2)), f"Aria's army is {aria} fresh units")
    frames.append((scene, {"title": "Part two, the map swap: The Last Citadel opens with Aria", "plain": True, "lines": [
        "The campaign moves to the second map: the opening scene (Aria, then Asuka). Aria (Orange Star; her CO is the placeholder until the Aria CO lands) leads a revived army of brand-new full-strength units."]}))
    home(g, e)
    full = stitch.stitch(Quiet(ctx), g, "m25b_full", w, h)
    frames.append((full, {"title": "Part two, the whole map: Aria's fortress on high ground", "marks": [("Aria's HQ", (33, 5), "next")], "lines": [
        f"{aria} units on the plateau (Megatanks, Neotanks, Md Tanks, rockets, missiles, Fighters and a Bomber). Approaches: the Aisne's five bridges and the passes (west, south, east). No pipes.",
        "The player re-forms in the south-west camp: the engine cannot carry survivors from map 1 (see the report)."]}))
    capture(ctx, e, g, d, (33, 5), 1)
    shots = []
    for k in range(6):
        shots.append(a2.pic(ctx, e, f"m25b_win{k}"))
        e.wait(40)
    ended = bool(e.u8(dc.LAST_RESULT)) or not d.in_battle()
    ctx.check(ended, "Aria's HQ taken: the campaign's final mission is won")
    from PIL import Image
    import numpy as np
    pic = max(shots, key=lambda p: float(np.asarray(Image.open(p).convert("L"), float).std()))
    frames.append((pic, {"title": "Aria's HQ falls: the final mission is won", "plain": True, "lines": ["Capturing Aria's HQ (33,5) wins the campaign's last mission (the credits follow)."]}))
    e.close()
    out = os.environ.get("AW2TEST_REVIEW_DIR") or ctx.out
    os.makedirs(out, exist_ok=True)
    sheet(ctx, frames, os.path.join(out, "m25_progression_v2.png"))
    for i, (p, _) in enumerate(frames):
        save(ctx, p, n, f"stage{i + 1}")
    ctx.log("wrote " + os.path.join(out, "m25_progression_v2.png"))


def nation_of(a):
    return {2: "Olaf's Blue Moon", 3: "Kanbei's Yellow Comet", 4: "Eagle's Green Earth"}[a]


@test(name="bh2_m6_towers_and_eagle", modes=("ds",))
def bh2_m6_towers_and_eagle(ctx):
    """M6 Forest of Spears: Black Hole captures Javier's four Com Towers with real captures; the last one makes Eagle take command of the same army (a scene, a CO change with no second HQ) and an air wing land."""
    e, g, d = b2.enter(ctx, 6)
    d.leave_setup()
    a2.intro(ctx, e, d, "m6", (0,))
    d.wait_control()
    g._units_base = g._players_base = None
    towers = [(25, 5), (31, 10), (28, 16), (35, 14)]
    before = len(g.units(army=2))
    co0 = g.player(2)["co"]
    ctx.log(f"Javier's army {before} units, CO id {co0}")
    for k, t in enumerate(towers):
        capture(ctx, e, g, d, t, 1)
        if k < len(towers) - 1:
            settle(e, g, d)
            ctx.eq(g.player(2)["co"], co0, f"tower {k + 1} of 4 taken: Javier still commands")
    pic = dialogue_pic(ctx, e, d, "m6_scene")
    settle(e, g, d)
    ctx.eq(g.player(2)["co"], 8, "all four towers held: Eagle commands the same army")
    after = len(g.units(army=2))
    ctx.check(after >= before + 5, f"an air wing landed ({before} -> {after} units)")
    ctx.check(pic is not None, "the takeover scene was shown")
    ctx.check(not e.u8(dc.LAST_RESULT), "the mission goes on (no second HQ, no win)")
    e.close()
