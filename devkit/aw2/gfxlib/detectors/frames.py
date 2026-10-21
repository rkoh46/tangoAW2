"""Black and frozen frames in a sequence of shots (the shots listed in `sequence`): all-black frames, and runs of identical frames longer than `max_same`."""
import numpy as np
from PIL import Image

NAME = "frames"


def run(ctx):
    out = []
    for s in ctx.screen.get("frames", []):
        shots = ctx.shots(s["sequence"])
        for vname in ctx.renders:
            prev, same, black = None, 0, 0
            for shot in shots:
                p = ctx.path(vname, shot)
                if not p:
                    continue
                a = np.asarray(Image.open(p).convert("L"), dtype=int)
                if (a < 20).mean() > 0.97:
                    black += 1
                same = same + 1 if prev is not None and np.array_equal(a, prev) else 0
                prev = a
                if same > s.get("max_same", 100):
                    out.append({"detector": NAME, "shot": f"{vname}/{shot}", "severity": "fail", "msg": f"frozen: {same} identical frames in a row"})
                    break
            if black > s.get("max_black", 0):
                out.append({"detector": NAME, "shot": vname, "severity": "fail", "msg": f"{black} black frames in the sequence"})
    return out
