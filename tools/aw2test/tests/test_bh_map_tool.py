"""The BH Campaign's map tool (tango-gamesupport-aw2/five/bhmap.py): text maps
become tile maps with every road, river, pipe, coast and shoal joined as AW2
draws them (the rules of five/map.py, checked against the game's own maps by
five/tilecheck.py), and the reachability checks find a stranded island, an
HQ no one can reach, and a Lander with nowhere to load or unload."""

import os
import subprocess
import sys
import tempfile

from aw2test import paths
from aw2test.harness import test

TOOL = os.path.join(paths.REPO, "tango-gamesupport-aw2", "five", "bhmap.py")


def run(text):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.txt")
        open(p, "w").write(text)
        r = subprocess.run([sys.executable, TOOL, "--check", paths.aw2_rom(), p], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr


GOOD = """map ok
armies 2 3 5 3
team 1 2
unit 1 1 2 1
unit 2 1 11 6
~~~~~~~~~~~~~~
~1.R...f.....~
~..R.^^f..Cc.~
~..RRRRRR.^..~
~..b...f..R..~
~......f..RRB~
~..........2~~
~~~~~~~~~~~~~~
"""

def rows(*r):
    assert len({len(x) for x in r}) == 1, r
    return "\n".join(r) + "\n"


# Two lands with a strait between, a Lander and a beach on each side.
SEA_OK = ("map sea_ok\narmies 2 3 5 3\nteam 1 2\nunit 1 1 1 2\nunit 1 23 6 2\nunit 2 1 11 2\n"
          + rows("~~~~~~~~~~~~~~", "~1.,~~~~~~,.2~", "~..,~~~~~~,..~", "~.C,~~~~~~,C.~", "~~~~~~~~~~~~~~"))

# Same, but the left land has no beach on the strait (a Lander cannot load).
SEA_NO_LOAD = ("map sea_no_load\narmies 2 3 5 3\nteam 1 2\nunit 1 1 1 2\nunit 1 23 6 2\nunit 2 1 11 2\n"
               + rows("~~~~~~~~~~~~~~", "~1..~~~~~~,.2~", "~...~~~~~~,..~", "~.C.~~~~~~,C.~", "~~~~~~~~~~~~~~"))

# A third land nobody reaches.
ISLAND = GOOD.replace("map ok", "map island").replace("~~~~~~~~~~~~~~\n", "~~~~~~~~~~~~~~\n", 1).replace("~..........2~~", "~..........2~~\n~~~~~~~~~~~~~~\n~~~~~~~Cc~~~~~\n~~~~~~~..~~~~~\n~~~~~~~~~~~~~~", 1).replace("~~~~~~~~~~~~~~\n~~~~~~~Cc", "~~~~~~~~~~~~~~\n~~~~~~~Cc", 1)

# An HQ across the water with no way over.
NO_WAY = SEA_OK.replace("map sea_ok", "map no_way").replace("unit 1 23 6 2\n", "")


@test(modes=("aw2",))
def bh_map_tool_checks(ctx):
    code, out = run(GOOD)
    ctx.eq(code, 0, f"a good map passes ({out.strip()})")
    code, out = run(SEA_OK)
    ctx.eq(code, 0, f"two lands, a Lander, a beach each side ({out.strip()})")
    code, out = run(SEA_NO_LOAD)
    ctx.check(code == 1 and "no port or beach to load" in out, f"a Lander with no beach to load at is found ({out.strip()})")
    code, out = run(NO_WAY)
    ctx.check(code == 1 and "cannot reach" in out, f"an HQ no one can reach is found ({out.strip()})")
    code, out = run(ISLAND)
    ctx.check(code == 1 and "stranded island" in out, f"a stranded island is found ({out.strip()})")
