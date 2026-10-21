"""Stray tiles: regions that must be empty (one plain colour) for that screen, e.g. around the SELECT MAP logo during the roulette."""
import numpy as np
from PIL import Image

NAME = "stray"


def run(ctx):
    out = []
    for s in ctx.screen.get("stray", []):
        x, y, w, h = s["region"]
        for vname in ctx.renders:
            for shot in ctx.shots(s.get("shots", ctx.screen.get("shots", []))):
                p = ctx.path(vname, shot)
                if not p:
                    continue
                a = np.asarray(Image.open(p).convert("RGB"), dtype=int)[y:y + h, x:x + w].reshape(-1, 3)
                vals, counts = np.unique(a, axis=0, return_counts=True)
                mode = vals[counts.argmax()]
                other = float((np.abs(a - mode).sum(axis=1) > s.get("dist", 24)).mean())
                if other > s.get("tolerance", 0.01):
                    out.append({"detector": NAME, "shot": f"{vname}/{shot}", "severity": "fail", "msg": f"{other * 100:.1f}% of region {x},{y},{w},{h} is not background {tuple(mode)} ({s.get('what', 'must be empty')})"})
    return out
