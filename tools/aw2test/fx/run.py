"""Every on-map animation, flat and tilted: `python3 fx/run.py SCENE flat|tilt OUTDIR` records every frame (stride 2) and, for flat, the
sprites shown each frame (oamlog); the tilt's skip and leak logs are kept (tiltall). Scenes are functions in fx/scenes.py."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
scene, mode, out = sys.argv[1], sys.argv[2], os.path.abspath(sys.argv[3])
os.makedirs(out, exist_ok=True)
os.environ["AW2TEST_OUT"] = out + "/_aw2"
os.environ.setdefault("AW2TEST_BASE_SAVE", os.path.expanduser("~/tangoAW2-integfix/tools/aw2test/out_c/base-clean.sav"))
import scenes
from aw2test.harness import Ctx

log = f"{out}/{scene}_{mode}.log"
for p in (log, f"{out}/{scene}_{mode}.oam"):
    try:
        os.remove(p)
    except OSError:
        pass
env = {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "0" if mode == "flat" else "1", "TANGOAW2_TILT_SCALE": os.environ.get("FX_SCALE", "2"),
       "TANGOAW2_TILT_SKIP_LOG": "1", "TANGOAW2_TILT_LEAK_LOG": "1", "TANGOAW2_TILT_LOG": log}
ctx = Ctx("fx_" + scene, ds=True, out=f"{out}/_{scene}_{mode}")
os.makedirs(ctx.out, exist_ok=True)
fd = f"{out}/{scene}_{mode}"
os.makedirs(fd, exist_ok=True)
for f in os.listdir(fd):
    os.remove(f"{fd}/{f}")


class Rec:
    """scenes call rec.on() when the effect is about to start and rec.off() when it is over."""
    def __init__(self, e):
        self.e = e

    def on(self):
        self.e.cmd(f"tiltall 1 {fd} {os.environ.get('FX_STRIDE', '2')}")
        if mode == "flat":
            self.e.cmd(f"oamlog {out}/{scene}_{mode}.oam")

    def off(self):
        self.e.cmd("tiltall 0")
        self.e.cmd("oamlog")


getattr(scenes, scene)(ctx, env, Rec)
for g in ctx.games:
    g.e.close()
print("done", scene, mode, len(os.listdir(fd)), "frames")
