"""BH2 M31 The Last Accord, one mission in two stages (development build, crate::bh2_campaign): the final mission played through, a picture at each stage (`-k bh2_m31_progression`).

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
from aw2test import tag as tagmod
from aw2test.emu import Emu
from aw2test.game import Game
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


def to_player_turn(e, g, d, frames=24000):
    """Presses A through the scripts until it is the player's (army 5's) turn with nothing running: the computer's turns of the four nations go by."""
    for _ in range(frames // 20):
        if d.scripts_running():
            e.press("A", 4)
        elif g.current_army() == 5 and d.in_battle():
            e.wait(30)
            if g.current_army() == 5 and not d.scripts_running():
                break
        e.wait(16)
    g._units_base = g._players_base = None


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
    d.text((pad, 12), "M31 The Last Accord, one mission in two stages: played with real captures (the game's own pictures)", fill=(255, 220, 90), font=f1)
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


def nation_of(a):
    return {2: "Olaf's Blue Moon", 3: "Kanbei's Yellow Comet", 4: "Eagle's Green Earth"}[a]


STAGE_AT = 0x0203_DCA0          # crate::ram_map::STAGE: +0 the stage the battle is on (0 the mission's own)
FIVE_ON = 0x0203_0206           # tangoAW2's five-army switch (2: a custom campaign's five-army mission)


def stage_of(e):
    return e.u8(STAGE_AT)


def signature(units):
    """The units' identity for the carry-over check: type, HP, ammo and fuel (positions change)."""
    return sorted((u["type"], u["hp"], u["ammo"], u["fuel"]) for u in units)


def wait_stage(ctx, e, g, d, k, frames=3000):
    """Through the scenes and the swap's fades until the battle is on stage k and the cursor answers."""
    for _ in range(frames // 20):
        if stage_of(e) != k and d.scripts_running():
            e.press("A", 4)
        e.wait(15)
        if stage_of(e) == k and e.u8(STAGE_AT + 1) == 0 and d.in_battle():
            break      # (the stage's own opening scene, if it has one, is for the caller)
    g._units_base = g._players_base = None


@test(name="bh2_m31_progression", modes=("ds",))
def bh2_m31_progression(ctx):
    """M31 The Last Accord, one mission in two stages: the gauntlet's four captures, then Eagle's fall moves the battle in place to the Last Citadel (the stage switch, crate::stage): the survivors, funds and
    COs carry over, Aria's fresh army is the new enemy, and capturing her HQ wins the campaign. One continuous run; the frames go on one sheet (m31_progression.png)."""
    n = 31
    e, g, d = b2.enter(ctx, n)
    w, h = d.size()
    d.leave_setup()
    a2.intro(ctx, e, d, "m31", (0,))
    to_player_turn(e, g, d)     # (the finale's own opening scene, m31_pre, runs to its end; the four nations' computer turns pass)
    d.wait_control()
    g._units_base = g._players_base = None
    player = 5
    frames = []
    prev = counts(g, (1, 2, 3, 4))
    ctx.log(f"start: units by army {prev}, HQ owners {[owner(e, *c) for _, c, _, _ in HQS]}")
    ctx.eq(stage_of(e), 0, "the battle starts on stage 0")
    ctx.eq([owner(e, *c) for _, c, _, _ in HQS], [1, 0, 0, 0], "only Nell's HQ is on the map at the start (the gauntlet engine: Olaf's, Kanbei's and Eagle's cells are plain)")
    ctx.check(prev[1] >= 20 and all(prev[a] == 0 for a in (2, 3, 4)), f"Nell's army is whole; the other nations have no units yet: {prev}")
    ctx.eq([e.u8(g.players_base + 0x3C * a + 0x1B) for a in (2, 3, 4)], [0, 0, 0], "Olaf, Kanbei and Eagle are not in the battle yet (controller 0: no turn)")

    def shoot(tag):
        home(g, e)
        return stitch.stitch(Quiet(ctx), g, f"m31_{tag}", w, h)

    frames.append((shoot("stage1"), {"title": "Start: Nell's Orange Star holds the river plateau", "marks": marks(0, 0), "lines": [
        f"Five armies: Orange Star (Nell) {prev[1]} units; Blue Moon (Olaf), Yellow Comet (Kanbei) and Green Earth (Eagle) are not on the map yet: no HQ, no units, no turn (the gauntlet engine).",
        "The next HQ to take is 1 Nell (8,8). No pipes: the Marne, the Sere, the lakes and the highland ring are the defences."]}))
    for k, (name, cell, army, nation) in enumerate(HQS):
        last = k == len(HQS) - 1
        if last:
            g._units_base = g._players_base = None
            mine = g.units(army=player)
            funds = g.player(player)["raw"]
            sig_before = signature(mine)
            n_before = len(mine)
            funds_before = int.from_bytes(funds[0:4], "little")
            capture(ctx, e, g, d, cell, player)
            pic = dialogue_pic(ctx, e, d, "m31_scene")
            ctx.check(pic is not None, "the scene after Eagle's fall was shown")
            frames.append((pic, {"title": "Eagle's HQ falls: the scene before the switch", "plain": True, "lines": [
                "Taking 4 Eagle (38,20) with every earlier HQ already taken plays a short scene (Eagle, then Aria) and the battle moves on, in place, to the Last Citadel: a fade, a new map, no world map, no results."]}))
            wait_stage(ctx, e, g, d, 1)
            ctx.eq(stage_of(e), 1, "the battle is on stage 1 (the Last Citadel) after the switch")
            ctx.eq(e.u8(FIVE_ON), 0, "the five-army game is off on the four-army stage")
            ctx.check(not e.u8(dc.LAST_RESULT), "no result screen: the mission goes on")
            ctx.eq(d.mission(), 30, "the mission is still M31")
            player2 = 1
            mine2 = g.units(army=player2)
            ctx.log(f"carried: {n_before} before, {len(mine2)} after; funds before {funds_before}")
            ctx.eq(len(mine2), min(n_before, 40), "every survivor came along (count)")
            ctx.eq(signature(mine2), sorted(sig_before)[: len(mine2)] if n_before > 40 else sig_before, "the survivors keep their type, HP, ammo and fuel")
            deploy = []
            for line in open(os.path.join(os.path.dirname(__file__), "..", "..", "..", "tango-gamesupport-aw2", "five", "bh2", "bh2_31b.txt")):
                f = line.split()
                if len(f) >= 5 and f[0] == "unit" and f[1] == "1":
                    deploy.append((int(f[3]), int(f[4])))
            far = [(u["x"], u["y"]) for u in mine2 if min(abs(u["x"] - x) + abs(u["y"] - y) for x, y in deploy) > 6]
            ctx.check(not far, f"every survivor stands on or near a deploy cell (the camp): far ones {far}")
            funds_after = int.from_bytes(g.player(player2)["raw"][0:4], "little")
            ctx.check(funds_after >= funds_before, f"the player's funds carry over ({funds_before} -> {funds_after})")
            aria = g.units(army=2)
            ctx.check(len(aria) >= 25 and all(u["hp"] >= 10 or u["hp"] == 100 for u in aria), f"Aria's army is {len(aria)} fresh units")
            ctx.log(f"stage 2: Aria's CO id {g.player(2)['co']}, the player's CO {g.player(1)['co']} (carried {g.player(player2)['co']})")
            ctx.eq(g.player(2)["co"], 93, "Aria commands the Citadel's army (CO 93: her Vengeance and Build Anew)")
            ctx.eq(g.player(1)["co"], 92, "the player's CO carries over (Asuka, picked on the CO screen)")
            colours = [e.u8(g.players_base + 0x3C * a + 0x1A) for a in (1, 2)]
            ctx.eq(colours, [5, 1], "the stage's armies wear their colours: Black Hole and Aria's Orange Star")
            break
        capture(ctx, e, g, d, cell, player)
        settle(e, g, d)
        cur = counts(g, (1, 2, 3, 4))
        woke = k + 2
        ctx.log(f"after {name}'s HQ: units by army {cur}, HQ owners {[owner(e, *c) for _, c, _, _ in HQS]}, day {e.u16(dc.DAY)}")
        ctx.check(owner(e, *cell) == player, f"{name}'s HQ is the player's after the capture")
        ctx.check(cur[woke] - prev[woke] >= WAVES[k], f"{ARMY_NAMES[woke]} wakes with its whole wave ({cur[woke] - prev[woke]} new units for {WAVES[k]} in the list)")
        ctx.check(all(cur[a] == prev[a] for a in (2, 3, 4) if a != woke), f"no other dormant nation changed ({prev} -> {cur})")
        nxt = HQS[k + 1][1]
        ctx.eq(owner(e, *nxt), woke, f"{ARMY_NAMES[woke]}'s HQ is built on its cell {nxt} (the gauntlet engine's reveal)")
        ctx.eq(e.u8(g.players_base + 0x3C * woke + 0x1B), 2, f"{ARMY_NAMES[woke]} is in the battle (the computer's)")
        zone = {2: (16, 1, 30, 13), 3: (32, 1, 45, 13), 4: (32, 14, 45, 26)}[woke]
        towns = sum(1 for y in range(zone[1], zone[3] + 1) for x in range(zone[0], zone[2] + 1) if owner(e, x, y) == woke)
        ctx.check(towns >= 8, f"its zone's towns are its own ({towns} properties)")
        if woke < 4:
            ctx.eq(owner(e, *HQS[k + 2][1]), 0, "the next nation's HQ is not built yet")
        pth = shoot(f"stage{k + 2}")
        frames.append((pth, {"title": f"{name}'s HQ falls: {nation_of(woke)} joins", "marks": marks(k + 1, k + 1), "lines": [
            f"{name}'s HQ (taken): {ARMY_NAMES[woke]} wakes and lands {cur[woke] - prev[woke]} units ({cur[woke]} in all). The fallen nations stay on the map: units by army {cur}.",
            f"The next HQ to take is {k + 2} {HQS[k + 1][0]} {HQS[k + 1][1]}; HQ owners now {[owner(e, *c) for _, c, _, _ in HQS]} (1..4 their nations, 5 the player)."]}))
        prev = cur
    # stage 2: the Last Citadel, on the same battle
    scene = dialogue_pic(ctx, e, d, "m31b_scene")
    d.wait_control()
    g._units_base = g._players_base = None
    frames.append((scene, {"title": "The switch: The Last Citadel opens with Aria", "plain": True, "lines": [
        "The same battle, on the second map: Aria's scene, the survivors on the deploy cells in the south-west camp, Aria (Orange Star, CO 93) leading a revived army of brand-new full-strength units."]}))
    home(g, e)
    full = stitch.stitch(Quiet(ctx), g, "m31b_full", w, h)
    frames.append((full, {"title": "Stage 2, the whole map: Aria's fortress on high ground", "marks": [("Aria's HQ", (33, 5), "next")], "lines": [
        f"{len(g.units(army=2))} units on the plateau, the player's {len(g.units(army=1))} survivors in the camp. Approaches: the Aisne's bridges and the passes. No pipes."]}))
    capture(ctx, e, g, d, (33, 5), 1)
    shots = []
    for k in range(120):          # (the victory scene, m31_post, is dialogue: A through its boxes until the battle is over)
        if k < 6:
            shots.append(a2.pic(ctx, e, f"m31b_win{k}"))
        if bool(e.u8(dc.LAST_RESULT)) or not d.in_battle():
            break
        if d.scripts_running():
            e.press("A", 4)
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
    sheet(ctx, frames, os.path.join(out, "m31_progression.png"))
    for i, (p, _) in enumerate(frames):
        save(ctx, p, n, f"stage{i + 1}")
    ctx.log("wrote " + os.path.join(out, "m31_progression.png"))


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


@test(name="bh2_m2_crate_reaches_the_depot", modes=("ds",))
def bh2_m2_crate_reaches_the_depot(ctx):
    """M2 The Quartermaster's Crate: the crate truck (Black Hole's APC) on the depot town's goal tile (26,19) wins the mission after the next action (no port: the goal is a city tile on land)."""
    e, g, d = b2.enter(ctx, 2)
    g._units_base = g._players_base = None
    apc = next(u for u in g.units(army=1) if u["type"] == 7)
    inf = next(u for u in g.units(army=1) if u["type"] == 1)
    d.place_unit(apc, 26, 19)
    e.wait(4)
    ctx.eq(g.terrain_class(26, 19) & 0x1F != 0, True, "the goal tile is land with a property")
    g.wait_unit(inf["x"], inf["y"])
    for _ in range(40):
        if e.u8(dc.LAST_RESULT) or not d.in_battle():
            break
        e.press("A", 4)
        e.wait(30)
    ctx.check(bool(e.u8(dc.LAST_RESULT)) or not d.in_battle(), "the crate on the goal tile wins the mission")
    e.close()


def play_to_stage_two(ctx):
    """M31 entered, deployed, the four HQs captured, the switch done: (emu, game, driver) on stage 1 (the Last Citadel)."""
    e, g, d = b2.enter(ctx, 31)
    d.leave_setup()
    a2.intro(ctx, e, d, "m31", (0,))
    to_player_turn(e, g, d)     # (the finale's own opening scene, m31_pre, runs to its end; the four nations' computer turns pass)
    d.wait_control()
    g._units_base = g._players_base = None
    home(g, e)
    e.wait(60)
    for k, (name, cell, army, nation) in enumerate(HQS):
        capture(ctx, e, g, d, cell, 5)
        if k < len(HQS) - 1:
            settle(e, g, d)
    wait_stage(ctx, e, g, d, 1)
    d.dialogue()
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.require(stage_of(e) == 1, "the battle is on stage 1")
    return e, g, d


@test(name="bh2_m31_stage_two_suspend_and_resume", modes=("ds",))
def bh2_m31_stage_two_suspend_and_resume(ctx):
    """A battle saved on stage 2 (map menu > Save), a reboot, Continue: it comes back on stage 2 (the Last Citadel): the stage number, the four-army game, Aria's army and HQ, the player's survivors, and
    capturing Aria's HQ still wins. Costs: the record gains five bytes (a mark and the stage) after AW2's block; no new Flash sector."""
    from aw2test import saves
    e, g, d = play_to_stage_two(ctx)
    mine = signature(g.units(army=1))
    aria = len(g.units(army=2))
    pairs = [tagmod.partner(e, a) for a in range(1, 5)]
    ctx.check(any(pairs), f"the player's tag pair is live before the save ({pairs[0]})")
    ctx.log("before the save: players " + str([(a, g.player(a)['raw'][0x14:0x16].hex(), g.player(a)['raw'][0x1B], g.player(a)['raw'][0x1A], g.player(a)['raw'][0x2A]) for a in range(1, 5)]))
    names = saves.suspend(g)
    ctx.check("Save" in names, f"Save on the map menu of stage 2 ({names})")
    saved = saves.flash(e, os.path.join(ctx.out, "saved"))
    e.close()
    e = Emu(save=saved.path, ds=ctx.ds, env=dict(b2.ENV))
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = b2.Bh2Campaign(g)
    d.open_campaign_box()
    d.chooser_row(b2.CHOOSER_ROW)
    e.press("A", 8)
    e.wait(30)
    d.box_row(0)
    e.press("A", 8)
    ctx.require(e.wait_until(lambda: e.u32(0x03000000) == 0x08022049, 1500, step=10), "Continue: the battle")
    g._units_base = g._players_base = None
    g.wait_for_input()
    ctx.eq(stage_of(e), 1, "resumed on stage 2 (the stage number came back)")
    ctx.eq(e.u8(FIVE_ON), 0, "the four-army game is on")
    ctx.eq(d.mission(), 30, "the mission is M31")
    ctx.eq([tagmod.partner(e, a) for a in range(1, 5)], pairs, "the tag pairs survive a stage-2 resume (the stage mark used to be written over the pairs' tail)")
    ctx.eq(len(g.units(army=2)), aria, "Aria's army as saved")
    ctx.eq(signature(g.units(army=1)), mine, "the player's units as saved")
    ctx.eq(owner(e, 33, 5), 2, "Aria's HQ is on the map")
    capture(ctx, e, g, d, (33, 5), 1)
    ctx.eq(owner(e, 33, 5), 1, "Aria's HQ is the player's after the capture")
    for _ in range(60):
        if e.u8(dc.LAST_RESULT) or not d.in_battle():
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(40)
    ctx.log(f"result {e.u8(dc.LAST_RESULT)} in_battle {d.in_battle()} state {e.u16(0x030032D8)} army {e.u8(0x030033EC)} scripts {d.scripts_running()} players {[ (a, g.player(a)['raw'][0x14:0x16].hex(), g.player(a)['raw'][0x1B]) for a in range(1,4)]}")
    ctx.check(bool(e.u8(dc.LAST_RESULT)) or not d.in_battle(), "after the resume, Aria's HQ taken wins the mission")
    e.close()


def stage_fingerprint(e, g):
    """What the switch decides, read back: the unit tables of both armies, the players, gPlaySt, the stage state, the map's unit plane and the random number state."""
    import hashlib
    h = hashlib.sha256()
    h.update(bytes(e.read(g.units_base, 12 * 256)))
    h.update(bytes(e.read(g.players_base, 0x3C * 6)))
    h.update(bytes(e.read(0x0300_3FC0, 0x48)))
    h.update(bytes(e.read(STAGE_AT, 0x20)))
    h.update(bytes(e.read(0x0201_E450 + 0x12, 0xA10)))
    h.update(bytes(e.read(0x0300_1FD4, 4)))
    return h.hexdigest()


@test(name="bh2_m31_switch_is_deterministic", modes=("ds",))
def bh2_m31_switch_is_deterministic(ctx):
    """The stage switch reads and writes only emulated RAM (no clock, no random number): the same inputs from the same start give the same battle, byte for byte, on stage 2 (what netplay peers and
    a replay need). Two independent runs of the whole mission up to the switch and a few turns of the new stage compare their fingerprints."""
    prints = []
    for run in range(2):
        e, g, d = play_to_stage_two(ctx)
        g._units_base = g._players_base = None
        # (a few actions on the new stage: the survivors wait in place, then the turn ends and the computer's turn runs)
        mine = [u for u in g.units(army=1) if u["type"] in (3, 5, 10)][:3]
        for u in mine:
            g.wait_unit(u["x"], u["y"])
        g.end_turn(human=1)
        g._units_base = g._players_base = None
        prints.append((stage_fingerprint(e, g), e.u16(dc.DAY), len(g.units(army=2))))
        ctx.log(f"run {run + 1}: {prints[-1]}")
        e.close()
    ctx.eq(prints[0], prints[1], "two runs give the same battle after the switch and a computer turn")


def m27_treasury(ctx, vault_empty, recover=False):
    """M27 entered; with `vault_empty` the day is 6 and Black Hole's funds are 0 (Von Bolt's vault is empty: the note's scene, `m27_vault_empty`, plays after the next action); Black Hole then really
    captures Colin's treasury, the fortress's central city (18,20): Colin's funds are 0 afterwards. Returns the texts of the scenes shown. Nothing wins the mission."""
    e, g, d = b2.enter(ctx, 27)
    d.leave_setup()
    a2.intro(ctx, e, d, "m27", (0,))
    d.wait_control()
    g._units_base = g._players_base = None
    funds2 = lambda: e.u32(g.player(2)["addr"])
    ctx.check(funds2() > 0, f"Colin has funds at the start ({funds2()})")
    if vault_empty:
        e.w16(dc.DAY, 6)
        e.w32(g.player(1)["addr"], 0)
    if recover:
        # the note opens after the next action (the vault is empty), then the funds come back: the note stays opened (the trigger's latch)
        u = next(u for u in g.units(army=1) if u["type"] in (1, 2, 5))
        try:
            g.wait_unit(u["x"], u["y"])
        except Exception:        # (the note's scene opens in the middle of the action: the harness waits for an idle map; the scene is pressed through next)
            pass
        settle(e, g, d)
        g._units_base = g._players_base = None
        e.w32(g.player(1)["addr"], 20000)
        e.wait(10)
    capture(ctx, e, g, d, (18, 20), 1)
    texts = []
    last = None
    for _ in range(600):
        t = d.text_shown()
        if t and t != last:
            texts.append(a2.clean(t))
            last = t
        if d.scripts_running():
            e.press("A", 4)
        elif not t and texts:
            break
        e.wait(10)
    settle(e, g, d)
    g._units_base = g._players_base = None
    ctx.eq(owner(e, 18, 20), 1, "the treasury is Black Hole's")
    ctx.eq(funds2(), 0, "Colin's funds are 0")
    ctx.check(not e.u8(dc.LAST_RESULT) and d.in_battle(), "the mission goes on: only the HQ or a rout wins it")
    e.close()
    return texts


@test(name="bh2_m27_note_and_treasury", modes=("ds",))
def bh2_m27_note_and_treasury(ctx):
    """M27 Von Bolt's Note: Black Hole's funds under 500 from day 6 open Sonja's note (a scene, no win); the capture of Colin's treasury then plays Von Bolt's sale (`m27_sale`) and zeroes Colin's funds."""
    texts = m27_treasury(ctx, True)
    ctx.log(f"scenes: {texts}")
    ctx.check(any("note" in t.lower() or "vault" in t.lower() for t in texts), "the note's scene was shown")
    ctx.check(any("sale" in t.lower() or "truth" in t.lower() for t in texts), "Von Bolt's sale was shown")


@test(name="bh2_m27_treasury_first_is_a_notice", modes=("ds",))
def bh2_m27_treasury_first_is_a_notice(ctx):
    """The treasury falls before the vault is empty: a one-line notice instead of the sale (the note is not opened), and Colin's funds are 0."""
    texts = m27_treasury(ctx, False)
    ctx.log(f"scenes: {texts}")
    ctx.check(any("treasury" in t.lower() for t in texts), "the notice was shown")
    ctx.check(not any("sale" in t.lower() for t in texts), "no sale: the note was not opened")


@test(name="bh2_m27_note_stays_opened_when_the_funds_recover", modes=("ds",))
def bh2_m27_note_stays_opened_when_the_funds_recover(ctx):
    """The note's "opened" state is the vault trigger's latch: the vault empties (funds 0 from day 6, the note's scene plays), the funds recover to 20000, and the treasury's capture still plays Von Bolt's sale."""
    texts = m27_treasury(ctx, True, recover=True)
    ctx.log(f"scenes: {texts}")
    ctx.check(any("sale" in t.lower() or "truth" in t.lower() for t in texts), "Von Bolt's sale was shown although the funds had recovered")
    ctx.check(not any("cannot pay another soldier" in t for t in texts), "not the plain notice")
