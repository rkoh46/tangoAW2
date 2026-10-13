"""BH M1: damage the units, end the turn, record every frame through the CPU turn (tiltall, stride 1) and the tilt's logs.
python3 fx/move.py OUTDIR [flat|tilt]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
out = os.path.abspath(sys.argv[1]); mode = sys.argv[2] if len(sys.argv) > 2 else "tilt"
os.makedirs(out, exist_ok=True)
os.environ["AW2TEST_OUT"] = out + "/_aw2"
os.environ.setdefault("AW2TEST_BASE_SAVE", os.path.expanduser("~/tangoAW2-integfix/tools/aw2test/out_c/base-clean.sav"))
from aw2test.harness import Ctx
from aw2test.bhcampaign import BhCampaign
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test import paths
log = out + f"/{mode}.log"
try: os.remove(log)
except OSError: pass
ctx = Ctx("mv", ds=True, out=out + "/_ctx")
e = Emu(save=paths.base_save(), ds=True, env={"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "0" if mode == "flat" else "1", "TANGOAW2_TILT_SCALE": os.environ.get("FX_SCALE", "2"),
        "TANGOAW2_TILT_LOG": log, "TANGOAW2_TILT_CAM_LOG": "1", "TANGOAW2_TILT_SKIP_LOG": "1"})
g = Game(e, ctx.image); ctx.games.append(g)
d = BhCampaign(g); d.start_bh(new=True)
d.wait_map(); d.through_dialogue(); d.wait_control()
for u in g.units(g.current_army()):
    a = g.unit_addr(u["id"]); e.w16(a + 4, (e.u16(a + 4) & ~0x7F) | 30)
fd = out + f"/{mode}_frames"; os.makedirs(fd, exist_ok=True)
for f in os.listdir(fd): os.remove(f"{fd}/{f}")
g.open_map_menu(); g.choose("End", g.MAP_MENU)
e.cmd(f"tiltall 1 {fd} 1")
e.cmd(f"oamlog {out}/{mode}.oam")
e.wait(int(os.environ.get("FX_FRAMES", "900")))
e.cmd("tiltall 0")
e.cmd("oamlog")
e.close()
