"""Palette integrity: palette banks a screen depends on (unit banks, text, HUD) equal the known-good dump's; plus the harness's own colour checks
(`rc = true`: the script's exit code is a finding, e.g. `unitcolours` in aw2_waiting_colours_ship_5p)."""
from ..vram import Dump

NAME = "palette"


def run(ctx):
    out = []
    pc = ctx.screen.get("palette")
    if not pc:
        return out
    for vname, d in ctx.renders.items():
        if pc.get("rc") and ctx.rcs.get(vname):
            out.append({"detector": NAME, "shot": vname, "severity": "fail", "msg": f"the script's own colour check failed (exit {ctx.rcs[vname]}): see {d / 'render.log'}"})
        for b in pc.get("banks", []):
            gd = ctx.golden.get(vname)
            cur = d / f"{b['dump']}.vram"
            ref = gd / f"{b['dump']}.vram" if gd else None
            if not cur.exists() or ref is None or not ref.exists():
                continue
            X, Y = Dump.load(cur), Dump.load(ref)
            for n in b["banks"]:
                for obj in (False, True):
                    if X.bank(n, obj) != Y.bank(n, obj):
                        out.append({"detector": NAME, "shot": f"{vname}/{b['dump']}", "severity": "fail", "msg": f"{'OBJ' if obj else 'BG'} palette bank {n} differs from golden: {X.bank(n, obj)[:4]}.. vs {Y.bank(n, obj)[:4]}.."})
    return out
