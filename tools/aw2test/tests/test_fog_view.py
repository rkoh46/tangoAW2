"""The waiting player's window in a Fog of War netplay match.

Two humans (armies 1 and 2, seats 0 and 1) play on a fog map; the run is
replayed on two rollback peers (aw2_netplay_script) with `shot` marks taken
during each army's turn. Each peer's window must show the other army's turn
through the viewer's own fog (not a black screen), and everything but the
windows is untouched: both peers and the straight replay stay identical.

The pictures are written to AW2TEST_OUT/<mode>/fog_view_*/netplay/ as
<name>_peer0.bmp (seat 0's window) and <name>_peer1.bmp (seat 1's).
"""

import os
import subprocess

from aw2test import paths
from aw2test.harness import test


def end_turn(g, nxt, tag=None):
    """Map menu > End, then A on the hand-off screen ("Next turn") for the army that plays next."""
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    if tag:
        for k in range(4):
            g.e.timeline.append("wait 15")
            g.e.timeline.append(f"shot {tag}_{k}")
            if k == 3:
                g.e.timeline.append("peek 07000000 400")
                g.e.timeline.append("peek 05000000 400")
                g.e.timeline.append("peek 04000000 60")
            g.e.wait(15)
    g.e.wait(60)
    g.e.press("A", 6)
    g.e.wait_until(lambda: g.current_army() == nxt, 3000, step=10)
    g.wait_for_input()


def run(ctx, g, extra=()):
    lines = ["seat 0"] + list(g.e.timeline) + list(extra)
    path = os.path.join(ctx.out, "netplay.txt")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    env = dict(os.environ)
    if ctx.ds:
        env["TANGOAW2_DS_ROM"] = paths.ds_rom()
        env["AW2_SHARED_ART"] = "1"
    out = subprocess.run([paths.runner("aw2_netplay_script"), g.e.rom, os.path.join(ctx.out, "map.sav"), path,
                          os.path.join(ctx.out, "netplay")], capture_output=True, text=True, env=env, timeout=1800)
    text = out.stdout + out.stderr
    with open(os.path.join(ctx.out, "netplay.log"), "w") as f:
        f.write(text)
    return text


def fog_map(ctx, colours=None):
    m = ctx.map()
    # Army 1 (seat 0): a tank and a recon far away, an infantry in the open.  Army 2 (seat 1): infantry near the
    # tank (seen by army 1), a mech in the open far away (not seen), one in woods, and a base.
    m.terrain(16, 8, "wood").terrain(17, 8, "wood").terrain(25, 14, "base", 2)
    m.unit(1, "tank", 10, 8).unit(1, "recon", 4, 12).unit(1, "infantry", 17, 12)
    m.unit(2, "infantry", 13, 8).unit(2, "mech", 22, 12).unit(2, "infantry", 16, 8)
    if colours:
        m.colours = colours
    return m


def play(ctx, fog, cos=("andy", "grit"), colours=None):
    g = ctx.start(fog_map(ctx, colours), list(cos), humans=(1, 2), fog=fog)
    t = g.e.timeline
    tag = "fog" if fog else "nofog"
    def shot(name):
        t.append("wait 20")
        t.append(f"shot {tag}_{name}")
    t.append("wait 30")
    shot("t1_a1_start")
    g.select(10, 8)
    shot("t1_a1_selected")
    g.move_to(10, 10)
    shot("t1_a1_actionmenu")
    g.choose("Wait", g.ACTION_MENU)
    g.wait_for_input()
    shot("t1_a1_moved")
    end_turn(g, 2, "fog_handoff1")
    t.append("seat 1")
    t.append("wait 30")
    shot("t2_a2_start")
    g.goto(22, 12)
    shot("t2_a2_cursor_on_hidden_mech")
    g.e.press("A", 6)
    g.wait_menu(g.ACTION_MENU) if False else None
    shot("t2_a2_selected")
    g.move_to(20, 12)
    shot("t2_a2_actionmenu")
    g.choose("Wait", g.ACTION_MENU)
    g.wait_for_input()
    shot("t2_a2_moved")
    g.goto(25, 14)
    g.e.press("A", 6)
    g.e.wait(30)
    shot("t2_a2_buildmenu")
    g.e.press("B", 6)
    g.wait_for_input()
    g.open_map_menu()
    shot("t2_a2_mapmenu")
    g.e.press("B", 6)
    g.wait_for_input()
    end_turn(g, 1)
    t.append("seat 0")
    t.append("wait 30")
    shot("t3_a1_start")
    text = run(ctx, g, ["wait 60"])
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check("all identical: true" in text, "netplay: both peers and the straight replay identical")


@test(netplay=True)
def fog_view_both_turns(ctx):
    play(ctx, True)


@test(netplay=True)
def fog_off_view_both_turns(ctx):
    play(ctx, False)


@test(netplay=True)
def fog_view_yellow_comet_vs_black_hole(ctx):
    """Every portrait, panel, unit and building keeps its own army's colours in the waiting window."""
    play(ctx, True, ("sonja", "sturm"), colours=[0, 4, 5, 3, 2])


@test(netplay=True)
def fog_view_attack_scene(ctx):
    """The mover's attack (battle animations on): the waiting window never shows a garbled or concealed picture."""
    m = ctx.map()
    m.unit(1, "infantry", 17, 12).unit(2, "tank", 20, 12).unit(2, "infantry", 25, 5)
    g = ctx.start(m, ["andy", "grit"], humans=(1, 2), fog=True, visuals="a")
    t = g.e.timeline
    end_turn(g, 2)
    t.append("seat 1")
    t.append("wait 30")
    g.select(20, 12)
    g.move_to(18, 12)
    g.choose("Fire", g.ACTION_MENU)
    g.pick_target(17, 12)
    for k in range(6):
        t.append("wait 25")
        t.append(f"shot fog_scene_{k}")
        g.e.wait(25)
    g.wait_for_input()
    text = run(ctx, g, ["wait 60"])
    ctx.check("all identical: true" in text, "netplay: both peers and the straight replay identical")


@test(netplay=True)
def fog_view_menu_opening(ctx):
    """Shots at each stage of a menu opening and closing: the waiting window never shows it."""
    m = ctx.map()
    m.unit(1, "infantry", 17, 12).unit(2, "infantry", 25, 5)
    m.terrain(24, 6, "base", 2)
    g = ctx.start(m, ["andy", "grit"], humans=(1, 2), fog=True)
    t = g.e.timeline
    end_turn(g, 2)
    t.append("seat 1")
    t.append("wait 40")
    g.goto(29, 19)
    t.append("press A 6")
    g.e.press("A", 6)
    for k in range(10):
        t.append("wait 4")
        t.append(f"shot fog_open_{k}")
        g.e.wait(4)
    g.e.press("B", 6)
    for k in range(6):
        t.append("wait 4")
        t.append(f"shot fog_close_{k}")
        g.e.wait(4)
    text = run(ctx, g, ["wait 60"])
    ctx.check("all identical: true" in text, "netplay: both peers and the straight replay identical")
