"""Driving the BH Campaign's Act V missions (crate::bh_act5): booting at a
chosen progress, entering a mission through its CO screen and Setup phase,
reading the intro's boxes, forcing the win, taking the pictures."""

import os

from . import bhcampaign as bh
from . import dscampaign as dc
from . import paths
from .emu import Emu
from .bhact4 import CO_NAMES, expect_scene, _flat   # (the dialogue files against what the screen showed; see bhtext.py)
from .game import Game, NavError

# Roster bits (crate::bh_campaign::roster) and the mission indexes (world-map order).
ST, VB, HK = 1, 2, 4
M = {n: n - 1 for n in range(1, 32)}   # mission indexes (world-map order: bh01, bh02, the M03 stand-in, bh04..bh11, the M28 stand-in, M29, M30)
WON = lambda upto: (1 << upto) - 1
SHOTS = os.environ.get("AW2TEST_ACT5_SHOTS")   # a folder the pictures are also copied to


def boot(ctx, won, unlocked, picks=None, at=None, save=None, env=None):
    """Continue with the record set: missions won (bits), COs unlocked (roster
    bits), the map's cursor at mission index `at`. `env`: variables of this console only (tests run in
    parallel in one process: never set os.environ for one test)."""
    e = Emu(save=save or paths.base_save(), ds=ctx.ds, env=env)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = bh.BhCampaign(g)
    if picks:
        d.picks = dict(picks)
    start_at(e, d, won, unlocked, at)
    return e, g, d


def start_at(e, d, won, unlocked, at=None, from_title=True):
    """bhcampaign.BhCampaign.start_at with the cursor's place (the record's next step) too."""
    if from_title:
        d.open_campaign_box()
    d.chooser_row(bh.CHOOSER_ROW)
    e.press("A", 8)
    e.wait(30)
    e.w32(dc.P_MAGIC, bh.BH_MAGIC)
    e.w32(dc.P_WON, won)
    for k in range(3):
        e.w8(bh.P_UNLOCKED + k, (unlocked >> (8 * k)) & 0xFF)
    e.w8(dc.P_FLAGS + 14, 0x40)
    if at is not None:
        e.w8(dc.P_NEXT, at)
    d.box_row(0)
    e.press("A", 8)
    for _ in range(40):
        if e.wait_until(d.active, 30, step=5):
            break
        e.press("A", 8)
    else:
        raise NavError("the BH Campaign did not start")


def clean(t):
    return t.replace("\x0f", " ").replace("\r", " ").replace("  ", " ").strip() if t else t


def intro(ctx, e, d, label, shots=(0,), max_frames=40000):
    """After Deploy: the opening dialogue box by box (A through them), the
    text of each, and a picture of the boxes numbered in `shots` (and of the
    opening frame once control is back). Returns the boxes' texts."""
    texts, last, stable = [], None, 0
    n = 0
    while n < max_frames:
        if d.in_battle() and not d.scripts_running():
            e.wait(30)
            if not d.scripts_running():
                break
        t = d.text_shown()
        stable = stable + 1 if t and t == last else 0
        last = t
        if t and stable == 5 and (not texts or texts[-1] != clean(t)):
            texts.append(clean(t))
            if len(texts) - 1 in shots:
                e.wait(60)
                pic(ctx, e, f"{label}_dialogue{len(texts)}")
        if d.scripts_running() and stable >= 8:
            e.press("A", 4)
            stable = 0
        e.wait(4)
        n += 4
    return texts


def pic(ctx, e, name):
    """A screenshot (BMP in the test's output; a 3x PNG too when AW2TEST_ACT5_SHOTS names a folder)."""
    p = e.shot(os.path.join(ctx.out, name))
    if SHOTS:
        try:
            from PIL import Image
            os.makedirs(SHOTS, exist_ok=True)
            im = Image.open(p).convert("RGB")
            im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(os.path.join(SHOTS, name + ".png"))
        except ImportError:
            pass
    return p


def open_mission(ctx, e, g, d, index, cos, label, shots=(0,), setup_only=False):
    """On the world map (the cursor on the mission): the mission picked, its
    CO screens answered with `cos`, Setup left with Deploy, the intro read.
    Returns the intro's boxes."""
    d.pick_mission()
    if not cos and not setup_only:
        # a fixed mission (no CO screen): the battle loads and the opening plays around the Setup phase
        return fixed_intro(ctx, e, g, d, label, shots)
    picked = (pick_cos(d, list(cos)) if len(cos) > 1 else d.choose_cos(len(cos), prefs=list(cos))) if cos else []
    for _ in range(600):
        if d.in_battle() and e.u32(0x0849_9598) != 0:
            break
        e.press("A", 4) if d.scripts_running() else None
        e.wait(10)
    ctx.require(d.in_battle(), f"{label}: the battle loaded")
    if cos:
        ctx.eq(picked, list(cos), f"{label}: the CO screen's picks")
    g._units_base = g._players_base = None
    if setup_only:
        d.leave_setup  # (the caller works in the Setup phase, then deploys)
        for _ in range(200):
            if d.in_setup():
                break
            e.press("A", 4) if d.scripts_running() else None
            e.wait(10)
        return []
    d.leave_setup()
    return intro(ctx, e, d, label, shots)


def fixed_intro(ctx, e, g, d, label, shots=(0,), max_frames=40000):
    """A mission without a CO screen: from the battle's loading, Deploy chosen when the Setup phase is up, every
    box of the opening (A through them) until the player has control. Returns the boxes' texts."""
    texts, last, stable, n, quiet = [], None, 0, 0, 0
    while n < max_frames:
        if d.in_setup():
            d.deploy()
            quiet = 0
        t = d.text_shown()
        stable = stable + 1 if t and t == last else 0
        last = t
        if t and stable == 5 and (not texts or texts[-1] != clean(t)):
            texts.append(clean(t))
            if len(texts) - 1 in shots:
                e.wait(60)
                pic(ctx, e, f"{label}_dialogue{len(texts)}")
        if d.scripts_running():
            quiet = 0
            if stable >= 8:
                e.press("A", 4)
                stable = 0
        elif d.in_battle() and e.u32(0x0849_9598) != 0 and not d.in_setup():
            quiet += 1
            if quiet > 40 and (texts or n > 600):
                break
        e.wait(4)
        n += 4
    ctx.require(d.in_battle(), f"{label}: the battle loaded")
    g._units_base = g._players_base = None
    return texts


def pick_cos(d, cos, max_frames=8000):
    """The CO screens answered with `cos` one pick at a time, each pick checked on the screen's own count of picks: the A
    that follows the screen's opening can be lost (Sturm's cursor is on it already), and the next screen would then be
    answered for a CO that was never picked. Returns the COs picked, in order."""
    e = d.e
    n = 0
    last = 0
    while not d.in_battle() and n < max_frames:
        if d.on_co_select() and d.co_cursor():
            k = len(d.picked())
            if k >= len(cos):
                e.press("A", 6)         # (every pick made: the screen asks for the last confirmation)
                e.wait(60)
                n += 60
                continue
            d.choose_co([cos[k]])
            last = max(last, k + 1)
            e.wait(60)
            n += 60
        elif d.scripts_running():
            e.press("A", 6)
        e.wait(10)
        n += 16
    return list(cos[:last])


def follow(ctx, e, d, label, shots=(0,), max_frames=30000):
    """From a mission's end to the world map: every dialogue box in full once
    (A through them, a picture of the numbered ones) -- the victory scene in
    the battle, then the scene on the map. Returns (victory boxes, map boxes):
    the split is where the battle was left."""
    texts, last, stable, n = [], None, 0, 0
    in_battle_texts = 0
    while n < max_frames:
        t = d.text_shown()
        stable = stable + 1 if t and t == last else 0
        last = t
        if t and stable == 5 and (not texts or texts[-1] != clean(t)):
            if d.in_battle():
                in_battle_texts += 1
            texts.append(clean(t))
            if len(texts) - 1 in shots:
                e.wait(60)
                pic(ctx, e, f"{label}_{'victory' if d.in_battle() else 'map_scene'}{len(texts)}")
        if d.scripts_running() and stable >= 8:
            e.press("A", 4)
            stable = 0
        if d.world_map_up() and e.u8(dc.WM_STATE + 0x10) and not d.scripts_running():
            e.wait(60)
            if d.world_map_up() and not d.scripts_running():
                break
        elif not d.scripts_running() and d.in_battle() is False:
            e.press("A", 4)
        e.wait(4)
        n += 4
    return texts[:in_battle_texts], texts[in_battle_texts:]


def win(ctx, e, d, label, shots=(0,)):
    """Wins the mission in play (the test aid: the enemy routed) and follows it to the world map."""
    ctx.require(d.force_win(), f"{label}: won (test aid)")
    return follow(ctx, e, d, label, shots)


def win_by_attrition(ctx, e, g, d, label, shots=(0,), keep=1, hostile=None):
    """The test aid for a mission won by routing the enemy: every enemy army but `keep` units
    removed, then a player's unit takes an action (the after-action rules look), and the end
    is followed."""
    units = g.units()
    mine = next(u for u in units if u["army"] == 1 and u["type"] in (1, 2, 3, 5, 6))
    foes = [u for u in units if u["army"] != 1 and (hostile is None or u["army"] in hostile)]
    by = {}
    for u in foes:
        by.setdefault(u["army"], []).append(u)
    for army, us in by.items():
        for u in us[keep:]:
            d.remove_unit(u)
    e.wait(10)
    g.select(mine["x"], mine["y"])
    g.move_to(mine["x"], mine["y"])
    names = g.menu()["names"]
    g.choose(next(n for n in names if n.lower().startswith("wait")), g.ACTION_MENU)
    return follow(ctx, e, d, label, shots)


def calm(e, g, d, max_frames=6000):
    """Until the map is idle (A through any dialogue box on the way): an action's end."""
    n, run = 0, 0
    while n < max_frames:
        if d.scripts_running():
            e.press("A", 4)
            run = 0
        elif g.idle():
            run += 1
            if run >= 6:
                return True
        else:
            run = 0
        e.wait(4)
        n += 4
    raise NavError("the map did not settle")


def end_turn(e, g, d):
    """Map menu > End from the first empty cell the cursor reaches (on a fogged map some cells refuse it)."""
    g.wait_idle()
    for x, y in g.empty_cells()[:30]:
        try:
            g.goto(x, y)
        except NavError:
            continue
        e.press("A", 4)
        try:
            g.wait_menu(g.MAP_MENU, max_frames=90)
        except NavError:
            e.press("B", 4)
            e.wait(20)
            g.wait_idle()
            continue
        g.choose("End", g.MAP_MENU)
        return
    e.shot("/tmp/act2_no_cell")
    raise NavError(f"no cell opened the map menu (cursor {g.cursor()}, scripts {d.scripts_running()}, day {e.u16(0x03004080)})")


def next_turn(e, g, d):
    """End the turn and wait for the player's next (A through dialogue and the other armies' turns)."""
    d0 = e.u16(0x03004080)
    army = g.current_army()
    end_turn(e, g, d)
    for _ in range(4000):
        if e.u16(0x03004080) > d0 or g.current_army() != army or e.u8(dc.LAST_RESULT):
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(20)
    boxes(e, d, 2000)
    d.wait_control()


def to_day(e, g, d, day, max_turns=40):
    """End turns (A through dialogue) until the player's turn of day `day`; the dialogue shown on the way."""
    seen = []
    for _ in range(max_turns):
        if e.u16(0x03004080) >= day:
            break
        d0 = e.u16(0x03004080)
        end_turn(e, g, d)
        for _ in range(4000):
            if e.u16(0x03004080) > d0 or e.u8(dc.LAST_RESULT):
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(20)
        seen += boxes(e, d, 4000)
        d.wait_control()
    g._units_base = g._players_base = None
    return seen


def boxes(e, d, frames=1500):
    """Dialogue boxes shown until none for a while (A through them), cleaned."""
    texts, last, stable, quiet = [], None, 0, 0
    for _ in range(frames // 4):
        t = d.text_shown()
        stable = stable + 1 if t and t == last else 0
        last = t
        if t and stable == 5 and (not texts or texts[-1] != clean(t)):
            texts.append(clean(t))
        if d.scripts_running():
            quiet = 0
            if stable >= 8:
                e.press("A", 4)
                stable = 0
        else:
            quiet += 1
            if quiet > 40:
                break
        e.wait(4)
    return texts


def scene_seen(ctx, seen, keys, lead, partner, label, bonds=(), absent=()):
    """The scene(s) `keys` of the dialogue files (for this lead and partner, CO ids) appear whole and in order among the
    texts read from the screen (`seen`: a longer run of boxes than the scene); `absent` are scenes that must not appear."""
    from . import bhtext
    if isinstance(keys, str):
        keys = [keys]
    flat = _flat(seen)
    want = _flat([t for k in keys for t in bhtext.shown(k, CO_NAMES.get(lead), CO_NAMES.get(partner), bonds)])
    ctx.check(bool(want) and want in flat, f"{label}: the dialogue shows {'+'.join(keys)} (the files have {len(want)} characters; seen {len(flat)})")
    for k in ([absent] if isinstance(absent, str) else absent):
        other = _flat(bhtext.shown(k, CO_NAMES.get(lead), CO_NAMES.get(partner), bonds))
        ctx.check(not other or other not in flat, f"{label}: the dialogue does not show {k}")
