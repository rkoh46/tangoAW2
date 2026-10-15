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


def fog_map(ctx):
    m = ctx.map()
    # Army 1 (seat 0): a tank and a recon.  Army 2 (seat 1): infantry near the tank
    # (seen by army 1), a mech in the open far away (not seen) and one in woods.
    m.terrain(16, 8, "wood").terrain(17, 8, "wood")
    m.unit(1, "tank", 10, 8).unit(1, "recon", 4, 12).unit(1, "infantry", 17, 12)
    m.unit(2, "infantry", 13, 8).unit(2, "mech", 22, 12).unit(2, "infantry", 16, 8)
    return m


def end_turn(g, nxt):
    """Map menu > End, then A on the hand-off screen ("Next turn") for the army that plays next."""
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
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


@test(netplay=True)
def fog_view_both_turns(ctx):
    g = ctx.start(fog_map(ctx), ["andy", "grit"], humans=(1, 2), fog=True)
    t = g.e.timeline
    t.append("wait 30")
    t.append("shot t1_a1_start")
    # Army 1: tank forward, then end the turn.
    g.select(10, 8)
    g.move_to(10, 10)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_for_input()
    t.append("shot t1_a1_moved")
    end_turn(g, 2)
    t.append("seat 1")
    t.append("wait 30")
    t.append("shot t2_a2_start")
    # Army 2: the far mech walks toward the tank; the infantry steps back into the open.
    g.select(22, 12)
    t.append("shot t2_a2_selected")
    g.move_to(20, 12)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_for_input()
    t.append("wait 20")
    t.append("shot t2_a2_moved")
    end_turn(g, 1)
    t.append("seat 0")
    t.append("wait 30")
    t.append("shot t3_a1_start")
    text = run(ctx, g, ["wait 60"])
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check("all identical: true" in text, "netplay: both peers and the straight replay identical")
