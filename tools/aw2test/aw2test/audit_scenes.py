"""The audit's scenes, mode by mode (see audit.py). Each reaches its screens the way a player does and photographs them; the judging is in devkit/aw2/gfxlib/audit/.

Adding a screen: write a scene here (use the drivers of the other aw2test modules), tag its pictures, run `aw2dev gfx audit --modes MODE --scenes NAME`, LOOK at the sheet."""

import os

from . import saves
from .audit import scene
from .game import NavError

PANEL = 0x0203_0207          # the terrain panel's state byte (obelisk.rs PANEL): 6 while it shows a skin's HQ picture


# ---------------------------------------------------------------------------------------------------------------- menus
@scene("menus", "title", nopack=True)
def title(rec):
    """The title screen: logo, then PRESS START blinking."""
    e, g = rec.emu()
    e.wait(500)
    rec.snap(e, "title_a", ["menu", "title"])
    e.wait(40)
    rec.snap(e, "title_b", ["menu", "title"])
    e.wait(160)
    rec.snap(e, "title_c", ["menu", "title"])


@scene("menus", "select_mode", nopack=True)
def select_mode(rec):
    """Select Mode's wheel at every entry."""
    e, g = rec.emu()
    saves.to_select_mode(e)
    n = saves.wheel_size(e)
    for k in range(n):
        saves.wheel_to(e, k)
        e.wait(30)
        rec.snap(e, f"wheel_{k}", ["menu", "wheel"])


# ---------------------------------------------------------------------------------------------------------------- shared helpers
SKIN_STATE = 0x0203C500            # army_skin::STATE: +0 the colour the first skin sits on, +4.. the Teams screen's choices
ARMY_NAMES = {1: "orange_star", 2: "blue_moon", 3: "green_earth", 4: "yellow_comet", 5: "black_hole"}


def burst(rec, e, prefix, n, gap, tags, **meta):
    """n pictures `gap` frames apart (an animation: a power, a battle scene, a capture box)."""
    for k in range(n):
        rec.snap(e, f"{prefix}{k:02d}", list(tags) + ["burst"], **meta)
        e.wait(gap)


def showcase_map(ctx, armies=2, name="showcase", hq1=(0, 0)):
    """30 x 20: terrain of every kind (top left), two armies' units face to face (top right), sea with ships and air units (bottom left), properties of every owner (bottom right)."""
    m = ctx.map(name, hq=[(1, *hq1), (2, 29, 19)] + ([(3, 29, 0), (4, 0, 19)] if armies >= 4 else []), spare=True)
    if armies >= 5:
        m.terrain(14, 10, 0x1B4)          # (Black Hole's HQ and a unit make the fifth army, as test_co_skills.skills_five_armies does)
        m.unit(5, "infantry", 15, 10)
        m.colours = [5, 1, 2, 3, 4]
    owners = 3 if armies == 2 else 5
    SEA = 0x0A           # (the open-sea tile: `tile_for("sea")` is 0x08, an island-sea tile that draws an eye)
    kinds = ["plain", "wood", "mountain", "river", "road", SEA, "shoal", "reef", "bridge", "pipe"]
    for k, kind in enumerate(kinds):
        for r in range(3):
            m.terrain(2 + k, 2 + r, kind)
    for x in range(1, 14):
        m.terrain(x, 6, "road")
        m.terrain(x, 7, "river" if x not in (6, 7) else "bridge")
    for x in range(0, 14):
        for y in range(11, 19):
            m.terrain(x, y, SEA)
    for x in range(5, 9):
        m.terrain(x, 15, "shoal")
    for k in range(5):
        m.terrain(15 + k * 2, 12, "city", k % owners)
        m.terrain(15 + k * 2, 14, "base", k % owners)
        m.terrain(15 + k * 2, 16, "airport", k % owners)
        m.terrain(15 + k * 2, 18, "port", k % owners)
    m.terrain(25, 12, "lab")
    ground = ["infantry", "mech", "recon", "tank", "mdtank", "neotank", "apc", "artillery", "rockets", "antiair", "missiles", "megatank"]
    for k, u in enumerate(ground):
        try:
            m.unit(1, u, 16 + (k % 6), 1 + 2 * (k // 6))
            m.unit(2, u, 16 + (k % 6), 2 + 2 * (k // 6))
        except (KeyError, AssertionError):
            pass
    for k, u in enumerate(["battleship", "cruiser", "submarine", "lander", "fighter", "bomber"]):
        try:
            m.unit(1, u, 2 + 2 * k, 13)
            m.unit(2, u, 2 + 2 * k, 16)
        except (KeyError, AssertionError):
            pass
    return m


def versus(rec, m, cos=("andy", "max"), humans=(1,), skin=False, extra=None, **rules):
    """Boot with `m`, pick COs on the Teams screen (the skin with R), the Rules, start the battle. Returns (emu, game)."""
    ctx = rec.ctx
    g = ctx.boot_teams(m, env=rec.env)
    e = g.e
    if skin:
        for _ in range(8):
            if e.u8(SKIN_STATE + 4):
                break
            e.press("R", 4)
            e.wait(10)
    g.set_teams(list(cos), set(humans))
    if extra:
        extra(g)
    g.teams_to_rules()
    g.set_rules(**rules)
    g.start_battle()
    g.wait_for_input()
    e.wait(40)
    rec.tilt(e)
    return e, g


def look_at(rec, g, x, y, name, tags=("battle", "map"), wait=30, **meta):
    g.goto(x, y)
    g.e.wait(wait)
    return rec.snap(g.e, name, list(tags), **meta)


def tour(rec, g, prefix, cells, tags=("battle", "map"), **meta):
    for k, (x, y) in enumerate(cells):
        look_at(rec, g, x, y, f"{prefix}{k}", tags, **meta)


VIEWS = ((3, 3), (22, 4), (4, 15), (22, 15))      # the four quarters of a 30 x 20 map under the 15 x 10 window


# ---------------------------------------------------------------------------------------------------------------- Versus
@scene("versus", "teams_rules", nopack=True)
def teams_rules(rec):
    """Versus: the Teams screen (army cards, CO cards) and the Rules screen."""
    m = rec.ctx.map("teams")
    g = rec.ctx.boot_teams(m, env=rec.env)
    e = g.e
    rec.snap(e, "teams_default", ["menu", "teams"])
    g.set_teams(["andy", "sonja"], {1})
    e.wait(80)
    rec.snap(e, "teams_andy_sonja", ["menu", "teams"])
    g.teams_to_rules()
    rec.snap(e, "rules", ["menu", "rules"])


@scene("versus", "map_select", nopack=True)
def map_select(rec):
    """Versus > New: SELECT MAP, the game's tabs scrolled."""
    from . import versusmaps as vm
    e, g = rec.emu()
    if rec.ds:
        vm._open_tabs(e)
    else:
        e.wait(700)
        e.press("START", 8)
        e.wait(300)
        e.press("A", 8)
        e.wait(150)
        saves.wheel_to(e, saves.VERSUS)
        e.press("A", 8)
        e.wait(150)
        e.press("A", 8)
        e.wait(150)
    rec.snap(e, "tab0", ["menu", "maplist"])
    for k in range(1, 6):
        e.press("LEFT", 8)
        e.wait(90)
        rec.snap(e, f"tab{k}", ["menu", "maplist"])
    for k in range(4):
        e.press("DOWN", 8)
        e.wait(20)
    rec.snap(e, "scrolled", ["menu", "maplist"])


@scene("versus", "battle_map", nopack=True)
def battle_map(rec):
    """Versus battle: terrain, units, properties and ships in the four quarters, the map menu, the CO page."""
    m = showcase_map(rec.ctx)
    e, g = versus(rec, m)
    tour(rec, g, "view", VIEWS)
    g.open_map_menu()
    e.wait(20)
    rec.snap(e, "map_menu", ["battle", "menu"])
    g.choose("CO", g.MAP_MENU)
    e.wait(90)
    rec.snap(e, "co_page1", ["battle", "copage"])
    for k in range(3):
        e.press("RIGHT", 6)
        e.wait(45)
        rec.snap(e, f"co_page{k + 2}", ["battle", "copage"])
    e.press("B", 4)
    e.wait(40)
    g.wait_for_input()
    # the Options screen of the map menu
    g.open_map_menu()
    g.choose("Options", g.MAP_MENU)
    e.wait(60)
    rec.snap(e, "options", ["battle", "menu", "options"])
    e.press("DOWN", 6)
    e.wait(30)
    rec.snap(e, "options2", ["battle", "menu", "options"])
    e.press("B", 4)
    e.wait(60)


@scene("versus", "powers", nopack=True)
def powers(rec):
    """CO Power and Super CO Power activation (cut-in, flash)."""
    m = showcase_map(rec.ctx)
    for cos, which in ((("andy", "max"), "power"), (("sami", "max"), "super")):
        e, g = versus(rec, m, cos)
        g.charge_power(1, which)
        g.open_map_menu()
        g.choose("Super" if which == "super" else "Power", g.MAP_MENU)
        burst(rec, e, f"{which}_", 14, 12, ["battle", "power"])
        e.close()


@scene("versus", "animations", nopack=True)
def animations(rec):
    """Battle animations (the Rules' animation option on): an attack's scene, frame by frame."""
    m = rec.ctx.map("anim")
    m.unit(1, "tank", 10, 10).unit(2, "infantry", 11, 10).unit(1, "mech", 10, 12).unit(2, "tank", 11, 12)
    e, g = versus(rec, m, visuals="a")
    for src, dst, tgt, tag in (((10, 10), (10, 10), (11, 10), "a"), ((10, 12), (10, 12), (11, 12), "b")):
        g.select(*src)
        g.move_to(*dst)
        g.choose("Fire", g.ACTION_MENU)
        g.pick_target(*tgt)
        burst(rec, e, f"scene_{tag}", 10, 14, ["battle", "scene"])
        g.wait_for_input()


@scene("versus", "capture", nopack=True)
def capture(rec):
    """Capturing a city: the capture box."""
    m = rec.ctx.map("capt")
    m.terrain(10, 10, "city", 2)
    m.unit(1, "infantry", 9, 10)
    e, g = versus(rec, m, visuals="a")
    g.select(9, 10)
    g.move_to(10, 10)
    rec.snap(e, "capt_menu", ["battle", "menu"])
    g.choose("Capt", g.ACTION_MENU)
    burst(rec, e, "capt_", 12, 10, ["battle", "capture"])


@scene("versus", "hq_capture_defeat", nopack=True)
def hq_capture_defeat(rec):
    """Three armies: Orange Star takes Blue Moon's HQ; Blue Moon is defeated (its CO's quote box, the army's units going) and the battle goes on against Green Earth."""
    m = rec.ctx.map("defeat", hq=((1, 0, 0), (2, 11, 10), (3, 29, 19)))
    m.unit(1, "infantry", 10, 10)
    e, g = versus(rec, m, cos=("andy", "max", "eagle"), visuals="a")
    inf = next(u for u in g.units(army=1) if (u["x"], u["y"]) == (10, 10))
    a = g.unit_addr(inf["id"])
    e.w8(a + 5, (e.u8(a + 5) & 7) | (19 << 3))      # (one capture point left: the unit's capture count, as Gauntlet.capture does)
    e.wait(4)
    g.select(10, 10)
    g.move_to(11, 10)
    g.choose("Capt", g.ACTION_MENU)
    burst(rec, e, "defeat_", 26, 8, ["battle", "capture"])
    for _ in range(40):
        if g.idle():
            break
        e.press("A", 4)
        e.wait(20)
    rec.snap(e, "after", ["battle", "map"])


@scene("versus", "fog", nopack=True)
def fog(rec):
    """Fog of war: the four quarters and the map menu."""
    m = showcase_map(rec.ctx)
    e, g = versus(rec, m, fog=True)
    tour(rec, g, "fog", VIEWS)


@scene("versus", "weather", nopack=True)
def weather(rec):
    """Rain, snow and a sandstorm over the map."""
    m = showcase_map(rec.ctx)
    for w in ("rain", "snow", "sandstorm"):
        e, g = versus(rec, m, weather="clear" if w == "sandstorm" else w)
        if w == "sandstorm":
            if not rec.ds:
                e.close()
                continue
            e.write(0x03003FEC, bytes([0, 3, 0, 0]))
        e.wait(120)
        for k, v in enumerate(VIEWS[:2]):
            look_at(rec, g, *v, f"{w}{k}", wait=60)
        e.close()


@scene("versus", "com_towers", pack=True)
def com_towers(rec):
    """Com Towers of every owner (the pack's tiles) on a map."""
    m = rec.ctx.map("towers")
    for k, t in enumerate((0x1D9, 0x1DA, 0x1DB, 0x1DC, 0x1DD, 0x1B9)):
        m.terrain(3 + 2 * k, 9, t)
        m.terrain(3 + 2 * k, 11, t)
    e, g = versus(rec, m)
    look_at(rec, g, 8, 9, "towers", wait=40)
    look_at(rec, g, 12, 11, "towers2", wait=40)


@scene("versus", "five_army", pack=True)
def five_army(rec):
    """A five-army map: Orange Star, Blue Moon, Green Earth, Yellow Comet and Black Hole at once."""
    m = showcase_map(rec.ctx, armies=5, name="five")
    e, g = versus(rec, m, cos=("andy", "max", "eagle", "kanbei", "sturm"))
    tour(rec, g, "five", VIEWS)
    g.open_map_menu()
    e.wait(20)
    rec.snap(e, "five_menu", ["battle", "menu"])


@scene("versus", "silver_nova", pack=True)
def silver_nova(rec):
    """Silver Nova in a Versus battle: its units, HQ, the terrain panel, capture box and a battle scene."""
    m = showcase_map(rec.ctx, hq1=(8, 9))
    m.unit(1, "infantry", 7, 9).unit(2, "infantry", 9, 9).unit(1, "mech", 7, 10)
    e, g = versus(rec, m, cos=(86, "andy"), skin=True, visuals="a")
    g.wait_for_input()
    tour(rec, g, "sn", VIEWS)
    look_at(rec, g, 8, 9, "sn_hq", ("battle", "map", "hq_panel"), wait=50)
    rec.fact(e.u8(PANEL) == 6, f"the terrain panel on Silver Nova's HQ draws its own HQ picture (panel state {e.u8(PANEL)})")
    g.select(7, 9)
    g.move_to(8, 9)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_idle()


# ---------------------------------------------------------------------------------------------------------------- shared: story scenes
def scene_boxes(rec, e, d, prefix, most=6, early=True, tags=("dialogue",), patience=160, max_frames=30000):
    """From the first box on screen: A through the running script, a picture of each box (the first one twice: as it starts typing and once typed out; a garbled first box is a past bug).
    Returns the number of boxes photographed."""
    n = quiet = frames = 0
    last, stable = None, 0
    while frames < max_frames:
        t = d.text_shown()
        stable = stable + 1 if t and t == last else 0
        last = t
        if d.scripts_running():
            quiet = 0
        else:
            quiet += 1
            if n and (quiet > patience or d.world_map_up()):
                break
        if t and stable >= 5:
            if early and n == 0:
                rec.snap(e, f"{prefix}_first_early", list(tags) + ["first_box"])
            e.wait(150)
            if n < most:
                rec.snap(e, f"{prefix}_box{n:02d}", list(tags))
            n += 1
            e.press("A", 4)
            e.wait(30)
            stable, last = 0, None
            continue
        e.wait(4)
        frames += 4
        if d.scripts_running() and not t and frames % 80 == 0:
            e.press("A", 4)
    return n


def press_through(rec, e, d, prefix, until, most=8, step=70, tags=("story",), max_frames=12000):
    """A story the box reader cannot follow (AW2's own campaign): A every few frames, a picture each `step`, until `until()`."""
    n = frames = 0
    while frames < max_frames and not until():
        e.press("A", 4)
        e.wait(step - 10)
        frames += step
        if n < most:
            rec.snap(e, f"{prefix}{n:02d}", list(tags))
            n += 1
    return n


def world_map(rec, e, d, name="world_map"):
    d.wait_world_map()
    e.wait(90)
    rec.snap(e, name, ["worldmap"])


# ---------------------------------------------------------------------------------------------------------------- War Room, Survival
@scene("war_room", "selector_and_battle", nopack=True)
def war_room(rec):
    """War Room: SELECT MAP (the list and its records), the CO screen, the battle."""
    from . import warroom as wr
    from . import survival as sv
    e, g = rec.emu()
    wr.set_ds(rec.ds)
    saves.to_select_mode(e)
    rec.snap(e, "wheel", ["menu", "wheel"])
    saves.wheel_to(e, saves.WAR_ROOM)
    e.press("A", 8)
    e.wait(60)
    rec.snap(e, "box", ["menu"])
    saves.box_row(e, 1)
    e.press("A", 8)
    if not e.wait_until(lambda: sv.running(e, sv.SELECT_MAP_PROC), 600, step=10):
        raise RuntimeError("War Room's SELECT MAP did not open")
    e.wait(90)
    rec.snap(e, "selector", ["menu", "maplist"])
    for k in range(3):
        e.press("DOWN", 8)
        e.wait(30)
    rec.snap(e, "selector_row3", ["menu", "maplist"])
    e.press("R", 8)
    e.wait(40)
    rec.snap(e, "records_R", ["menu", "records"])
    e.press("R", 8)
    e.wait(30)
    e.press("A", 8)
    if not e.wait_until(lambda: wr.proc(e) is not None, 900, step=10):
        raise RuntimeError("the CO screen did not open")
    e.wait(60)
    rec.snap(e, "co_screen", ["menu", "coselect"])
    e.press("RIGHT", 6)
    e.wait(40)
    rec.snap(e, "co_screen2", ["menu", "coselect"])
    wr.start_battle(e, g)
    e.wait(40)
    rec.tilt(e)
    rec.snap(e, "battle", ["battle", "map"])
    g.open_map_menu()
    e.wait(20)
    rec.snap(e, "map_menu", ["battle", "menu"])


@scene("survival", "screens", pack=True)
def survival(rec):
    """Survival: SELECT MAP (the course strip), the CO screen, the battle with its budget."""
    from . import survival as sv
    from . import warroom as wr
    e, g = rec.emu()
    if not sv.open_survival(e):
        raise RuntimeError("Survival's SELECT MAP did not open")
    rec.snap(e, "course", ["menu", "maplist"])
    e.press("DOWN", 8)
    e.wait(40)
    rec.snap(e, "course2", ["menu", "maplist"])
    e.press("R", 8)
    e.wait(40)
    rec.snap(e, "records", ["menu", "records"])
    e.press("R", 8)
    e.wait(30)
    e.press("A", 8)
    if not e.wait_until(lambda: wr.proc(e) is not None, 900, step=10):
        raise RuntimeError("Survival's CO screen did not open")
    e.wait(60)
    rec.snap(e, "co_screen", ["menu", "coselect"])
    wr.start_battle(e, g)
    e.wait(60)
    rec.tilt(e)
    rec.snap(e, "battle", ["battle", "map"])


# ---------------------------------------------------------------------------------------------------------------- Campaigns
@scene("aw2_campaign", "new_and_first_mission", nopack=True)
def aw2_campaign(rec):
    """AW2's own campaign: the box, Mission 1's story, its first turn, a win and the world map."""
    from . import campaigns as cm
    from .dscampaign import DsCampaign
    e, g = rec.emu()
    d = DsCampaign(g)
    d.to_select_mode() if hasattr(d, "to_select_mode") else saves.to_select_mode(e)
    cm.aw2_box(e, d, rec.ds, from_title=False)
    rec.snap(e, "box", ["menu"])
    d.box_row(1)
    e.wait(30)
    e.press("A", 8)
    e.wait(60)
    n = press_through(rec, e, d, "m1_story", lambda: d.in_battle() and e.u8(0x030033EC) == 1 and not d.scripts_running(), most=8)
    rec.note(f"{n} story pictures before the battle")
    cm.to_first_battle(e, d)
    e.wait(60)
    rec.tilt(e)
    rec.snap(e, "m1_turn1", ["battle", "map"])
    cm.win_here(e, d)
    e.wait(60)
    rec.snap(e, "world_map", ["worldmap"])


@scene("ds_campaign", "world_map_and_mission", pack=True)
def ds_campaign(rec):
    """DS Campaign: the world map, a mission's card, its CO screen, Setup phase, story boxes, the first turn, a win and the map again."""
    from . import campaigns as cm
    from .dscampaign import DsCampaign
    e, g = rec.emu()
    d = DsCampaign(g)
    cm.ds_start(e, d, True, from_title=True)
    world_map(rec, e, d)
    d.pick_mission()
    for k in range(4):
        e.wait(60)
        rec.snap(e, f"card{k}", ["menu", "card", "fade"] if k == 0 else ["menu", "card"])
        e.press("A", 6)
    rec.note("the DS mission card, then its CO screens")
    for _ in range(300):
        if d.in_setup() or d.in_battle():
            break
        e.press("A", 4)
        e.wait(15)
    e.wait(40)
    rec.snap(e, "setup_or_battle", ["battle", "setup"])
    if d.in_setup():
        d.leave_setup()
    scene_boxes(rec, e, d, "intro", most=4)
    d.wait_control()
    rec.tilt(e)
    rec.snap(e, "turn1", ["battle", "map"])
    cm.win_here(e, d)
    rec.snap(e, "after_win", ["worldmap"])


def _bh_enter(rec, n):
    """BH Campaign mission n (test_bh_review's table), entered through its CO screens, in the look's environment."""
    from . import bhact2 as a2
    from tests.test_bh_review import M, boot
    title, roster, picks, fog, front = M[n]
    env = dict(rec.env)
    if n == 28:
        env["TANGOAW2_BH_STILL"] = "1"
    mask = (1 << (n - 1)) - 1
    e, g, d = boot(rec.ctx, mask, roster, {n - 1: len(picks)}, n - 1, env)
    d.wait_world_map()
    return e, g, d, picks


@scene("bh_campaign", "missions", pack=True)
def bh_campaign(rec):
    """BH Campaign: world map, mission card, Setup phase, intro scene, a mission's first turn, for an early and a late mission."""
    from . import bhact2 as a2
    for n in (1, 11):
        e, g, d, picks = _bh_enter(rec, n)
        rec.snap(e, f"m{n}_world_map", ["worldmap"])
        d.pick_mission()
        if picks:
            d.choose_cos(len(picks), prefs=list(picks))
        for _ in range(600):
            if d.in_setup() or (d.in_battle() and not d.scripts_running()):
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(10)
        e.wait(40)
        rec.snap(e, f"m{n}_setup", ["battle", "setup"])
        if d.in_setup():
            d.leave_setup()
        scene_boxes(rec, e, d, f"m{n}_intro", most=4)
        d.wait_control()
        rec.tilt(e)
        rec.snap(e, f"m{n}_turn1", ["battle", "map"])
        e.close()


@scene("bh2_campaign", "missions", pack=True)
def bh2_campaign(rec):
    """BH2 Campaign: world map, Setup phase, intro scene and first turn of early and late missions."""
    from . import bh2campaign as b2
    for n in (1, 14, 26):
        e, g, d = b2.enter(rec.ctx, n, env=rec.env)
        rec.snap(e, f"m{n}_setup", ["battle", "setup"])
        d.leave_setup()
        scene_boxes(rec, e, d, f"m{n}_intro", most=4)
        d.wait_control()
        rec.tilt(e)
        rec.snap(e, f"m{n}_turn1", ["battle", "map"])
        e.close()


@scene("bh2_campaign", "m32_secret", pack=True)
def bh2_m32(rec):
    """The secret mission M32 Through the Door: day 1, its pre-scene, the three waves (days 3, 5, 7) as each lands."""
    from . import bh2campaign as b2
    from . import bhact2 as a2
    from . import dscampaign as dc
    e, g, d = b2.enter(rec.ctx, 32, env=rec.env)
    rec.snap(e, "setup", ["battle", "setup"])
    d.leave_setup()
    n = scene_boxes(rec, e, d, "pre", most=5)
    d.wait_control()
    g._units_base = g._players_base = None
    rec.tilt(e)
    rec.snap(e, "day1", ["battle", "map"])
    w, h = d.size()
    for day, tagname, cell in ((3, "wave1", (12, 4)), (5, "wave2", (37, 24)), (7, "wave3", (22, 4))):
        for _ in range(12):
            if e.u16(0x03004080) >= day:
                break
            d0 = e.u16(0x03004080)
            a2.end_turn(e, g, d)
            for _ in range(4000):
                if e.u16(0x03004080) > d0 or e.u8(dc.LAST_RESULT):
                    break
                if d.scripts_running() and not d.text_shown():
                    e.wait(20)
                elif d.scripts_running():
                    e.press("A", 4)
                e.wait(20)
        scene_boxes(rec, e, d, tagname, most=2)
        d.wait_control()
        rec.snap(e, f"{tagname}_map", ["battle", "map"])


@scene("bh2_campaign", "m31_stage_switch", pack=True)
def bh2_stage_switch(rec):
    """M31 The Last Accord: the gauntlet's captures, then the stage switch to the Last Citadel (its scene boxes, the new map and the player's survivors)."""
    from . import bh2campaign as b2
    from tests import test_bh2_progression as bp
    from tests.test_bh2_review import home
    from tests.test_stage_tool import STAGE_TRIGGERS
    mine, hqs = STAGE_TRIGGERS[31]
    e, g, d = b2.enter(rec.ctx, 31, env=rec.env)
    from . import bhact2 as a2
    d.leave_setup()
    a2.intro(rec.ctx, e, d, "m31", ())
    bp.to_player_turn(e, g, d)
    d.wait_control()
    g._units_base = g._players_base = None
    home(g, e)
    e.wait(60)
    rec.tilt(e)
    rec.snap(e, "stage1", ["battle", "map"])
    for k, (name, cell) in enumerate(hqs):
        bp.capture(rec.ctx, e, g, d, cell, mine)
        if k < len(hqs) - 1:
            n = scene_boxes(rec, e, d, f"fall{k}_{name}", most=3)
            bp.settle(e, g, d)
    n = scene_boxes(rec, e, d, "switch", most=6)
    bp.wait_stage(rec.ctx, e, g, d, 1)
    d.dialogue()
    d.wait_control()
    g._units_base = g._players_base = None
    e.wait(60)
    rec.snap(e, "stage2", ["battle", "map"])
    look_at(rec, g, 6, 6, "stage2_view", wait=40)


@scene("sn_campaign", "missions", pack=True)
def sn_campaign(rec):
    """Silver Nova Campaign: Setup phase, intro, first turn of early and late missions."""
    from . import escampaign as es
    for n in (1, 9, 16):
        e, g, d = es.boot(rec.ctx, n, env=rec.env)
        d.wait_world_map()
        rec.snap(e, f"m{n}_world_map", ["worldmap"])
        from . import bhact2 as a2
        picks = es.PICKS.get(n, [])
        a2.open_mission(rec.ctx, e, g, d, n - 1, picks, f"m{n}", setup_only=True)
        e.wait(40)
        rec.snap(e, f"m{n}_setup", ["battle", "setup"])
        if d.in_setup():
            d.leave_setup()
        scene_boxes(rec, e, d, f"m{n}_intro", most=4)
        d.wait_control()
        rec.tilt(e)
        rec.snap(e, f"m{n}_turn1", ["battle", "map"])
        e.close()


# ---------------------------------------------------------------------------------------------------------------- Gauntlet
@scene("gauntlet", "selector_and_army", pack=True)
def gauntlet_selector(rec):
    """Gauntlet: the wheel entry, the map selector (the list, the R records box), the army screen (CO, colour)."""
    from . import gauntlet as ga
    e, g = rec.emu()
    d = ga.Gauntlet(g)
    saves.to_select_mode(e)
    saves.wheel_to(e, "gauntlet")
    rec.snap(e, "wheel", ["menu", "wheel"])
    e.press("A", 8)
    d.wait_step(ga.SELECTOR)
    rec.snap(e, "selector", ["menu", "maplist"])
    for k in range(3):
        e.press("DOWN", 4)
        e.wait(50)
        rec.snap(e, f"selector_row{k + 1}", ["menu", "maplist"])
    e.press("R", 8)
    e.wait(40)
    rec.snap(e, "records_R", ["menu", "records"])
    e.press("R", 8)
    e.wait(30)
    for _ in range(len(ga.SELECTOR_ORDER) + 2):
        if e.u8(ga.UI_MAP_CURSOR) == 0:
            break
        e.press("UP", 4)
        e.wait(40)
    e.press("A", 6)
    d.wait_army()
    e.wait(60)
    rec.snap(e, "army", ["menu", "army"])
    for k in range(3):
        e.press("DOWN", 4)
        e.wait(40)
        rec.snap(e, f"army_co{k + 1}", ["menu", "army"])
    e.press("R", 4)
    e.wait(40)
    rec.snap(e, "army_colour", ["menu", "army"])


@scene("gauntlet", "cinder_sea_run", pack=True)
def gauntlet_run(rec):
    """Gauntlet on Cinder Sea with Silver Nova: Setup, day 1, a capture box, Drake's rout and arrival scene, then Sensei's."""
    from . import gauntlet as ga
    e, g = rec.emu()
    d = ga.Gauntlet(g)
    d.open(True, map=0)
    d.wait_army()
    d.pick_co(ga.CAULDER if hasattr(ga, "CAULDER") else 0x58)
    d.pick_colour(ga.EMERALD_SUN)
    e.press("A", 6)
    for _ in range(600):
        if d.in_battle() and e.u32(0x0849_9598) != 0:
            break
        e.press("A", 4) if d.scripts_running() else None
        e.wait(10)
    e.wait(40)
    rec.snap(e, "setup", ["battle", "setup"])
    d.leave_setup()
    d.wait_control()
    g._units_base = g._players_base = None
    rec.tilt(e)
    look_at(rec, g, 8, 16, "day1_player", wait=40)
    look_at(rec, g, 24, 16, "day1_drake", wait=40)
    look_at(rec, g, *ga.CINDER["player"], "day1_hq", ("battle", "map", "hq_panel"), wait=50)
    rec.fact(e.u8(PANEL) == 6, f"Gauntlet: the terrain panel on Silver Nova's HQ draws its own HQ picture, not Black Hole's or the CO country's (panel state {e.u8(PANEL)})")
    for k, name in enumerate(("drake", "sensei")):
        def snap(i, name=name):
            if i % 3 == 0:
                rec.snap(e, f"{name}_capture{i:02d}", ["battle", "capture"])
        d.capture(rec.ctx, ga.CINDER[name], snap=snap)
        # the rout and the arrival scene: boxes and the map after
        n = scene_boxes(rec, e, d, f"{name}_arrival", most=4, early=True)
        d.settle()
        rec.snap(e, f"{name}_after", ["battle", "map", "moved"])
        x, y = [(5, 4), (26, 4)][k]
        look_at(rec, g, x, y, f"{name}_new_line", wait=60, ) 


@scene("gauntlet", "five_army_arrival", pack=True)
def gauntlet_five(rec):
    """Two five-army Gauntlet maps (Harvest Run, Chrome Meridian: the player is the fifth army): day 1, the first line's fall (box text, face palettes) and the arrival boxes."""
    from . import gauntlet as ga
    from . import gauntlet_maps as gm
    from tests.test_gauntlet_lines import start
    for mission in (5, 6):
        info = gm.MAPS[mission]
        e, g, d = start(rec.ctx, info, env=rec.env)
        key = info.key
        rec.tilt(e)
        look_at(rec, g, *info.player_hq, f"{key}_day1", wait=50)
        first = info.lines[0]
        def snap(i, key=key):
            if i % 4 == 0:
                rec.snap(e, f"{key}_capture{i:02d}", ["battle", "capture"])
        d.capture(rec.ctx, first.hq, army=info.player, snap=snap)
        scene_boxes(rec, e, d, f"{key}_arrival", most=5)
        d.settle()
        look_at(rec, g, *info.lines[1].hq, f"{key}_next_line", wait=60, ) if len(info.lines) > 1 else None
        e.close()


# ---------------------------------------------------------------------------------------------------------------- COs
NEW_COS = (("sturm", 10, False), ("asuka", 92, False), ("aria", 93, False), ("caulder", 88, True), ("lili", 87, True), ("tabitha", 86, True), ("cloneandy", 81, False), ("crumb", 82, False))


@scene("cos", "pages_and_chart", pack=True)
def co_pages(rec):
    """The new COs (Asuka, Aria, Caulder, Lili, Tabitha, Clone Andy, Crumb): the Teams card, the CO page and its chart pages in battle."""
    tabs = {}
    for name, cid, skin in NEW_COS:
        m = rec.ctx.map(f"co_{name}"[:16])
        m.unit(1, "infantry", 4, 3).unit(2, "infantry", 5, 3)
        g = rec.ctx.boot_teams(m, env=rec.env)
        e = g.e
        g.set_teams([cid, "andy"], {1})
        e.wait(80)
        rec.snap(e, f"{name}_teams", ["menu", "teams"])
        g.teams_to_rules()
        g.set_rules()
        g.start_battle()
        g.wait_for_input()
        e.wait(40)
        rec.tilt(e)
        g.open_map_menu()
        g.choose("CO", g.MAP_MENU)
        e.wait(90)
        p = rec.snap(e, f"{name}_page1", ["battle", "copage"])
        from PIL import Image
        tabs[name] = Image.open(p).convert("RGB").crop((20, 4, 48, 28)).tobytes()
        for k in range(3):
            e.press("RIGHT", 6)
            e.wait(45)
            rec.snap(e, f"{name}_page{k + 2}", ["battle", "copage"])
        e.close()
    # the army emblem on the page's first tab: Black Hole's COs show Black Hole's, Silver Nova's their own sun
    same = lambda a, b: tabs.get(a) is not None and tabs.get(a) == tabs.get(b)
    rec.fact(same("asuka", "sturm"), "Asuka's CO page tab is Black Hole's emblem, like Sturm's")
    for n in ("tabitha", "lili", "caulder"):
        rec.fact(not same(n, "sturm"), f"{n}'s CO page tab is not Black Hole's emblem")
    rec.fact(same("tabitha", "lili") and same("lili", "caulder"), "the three Silver Nova COs' CO page tabs show the same emblem")


# ---------------------------------------------------------------------------------------------------------------- online pages
@scene("online", "pages", looks=("aw2",), nopack=True)
def online_pages(rec):
    """The in-game ONLINE pages (lobby, browser, room, army screen, unranked, colour pick, stats, waiting view, messages): `aw2_online_text_audit` renders every page at its longest strings; its BMPs are the pictures."""
    import glob
    import subprocess
    from PIL import Image
    from . import paths
    exe = paths.runner("aw2_online_text_audit")
    env = dict(os.environ)
    if rec.ds:
        env["TANGOAW2_DS_ROM"] = paths.ds_rom()
    else:
        env.pop("TANGOAW2_DS_ROM", None)
    d = os.path.join(rec.out, "pages")
    os.makedirs(d, exist_ok=True)
    r = subprocess.run([exe, paths.aw2_rom(), d], env=env, capture_output=True, text=True)
    problems = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith("PROBLEM")]
    for l in problems:
        rec.fact(False, l)
    for f in sorted(glob.glob(os.path.join(d, "*.bmp"))):
        name = os.path.basename(f)[:-4]
        Image.open(f).convert("RGB").save(os.path.join(rec.out, name + ".png"))
        os.remove(f)
        rec.shots.append({"name": name, "png": name + ".png", "vram": None, "tags": ["online", "menu"], "size": [240, 160], "frame": 0})