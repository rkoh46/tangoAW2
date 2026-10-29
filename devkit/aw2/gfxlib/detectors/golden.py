"""Golden-image diff: each shot against the reference rendered locally from a known-good build (~/.aw2dev/golden, never committed); tolerance per screen,
heat-map image of where it differs."""
import numpy as np
from PIL import Image

NAME = "golden"


def run(ctx):
    out = []
    g = ctx.screen.get("golden", {})
    tol = g.get("tolerance", 0.005)
    for vname, d in ctx.renders.items():
        gd = ctx.golden.get(vname)
        if gd is None:
            out.append({"detector": NAME, "shot": vname, "severity": "warn", "msg": "no golden image set: run `aw2dev gfx golden` from a known-good build"})
            continue
        for shot in ctx.shots(g.get("shots", ctx.screen.get("shots", []))):
            p, q = ctx.path(vname, shot), gd / f"{shot}.png"
            if not p or not q.exists():
                continue
            A = np.asarray(Image.open(p).convert("RGB"), dtype=int)
            B = np.asarray(Image.open(q).convert("RGB"), dtype=int)
            if A.shape != B.shape:
                out.append({"detector": NAME, "shot": f"{vname}/{shot}", "severity": "fail", "msg": "size differs from the golden image"})
                continue
            diff = np.abs(A - B).sum(axis=2)
            for x0, y0, w, h in g.get("ignore", []):   # animated parts (e.g. the banner's bobbing PRESS A BUTTON, its phase follows the wall clock)
                diff[y0:y0 + h, x0:x0 + w] = 0
            frac = float((diff > 24).mean())
            if frac > tol:
                heat = np.zeros(A.shape, dtype="uint8")
                heat[..., 0] = np.clip(diff * 2, 0, 255)
                heat[..., 1] = (A.mean(axis=2) * 0.35).astype("uint8")
                heat[..., 2] = (A.mean(axis=2) * 0.35).astype("uint8")
                art = ctx.out / f"heat_{vname}_{shot}.png"
                sheet = Image.new("RGB", (A.shape[1] * 3, A.shape[0]))
                sheet.paste(Image.fromarray(A.astype("uint8")), (0, 0))
                sheet.paste(Image.fromarray(B.astype("uint8")), (A.shape[1], 0))
                sheet.paste(Image.fromarray(heat), (2 * A.shape[1], 0))
                sheet.resize((sheet.width * 3, sheet.height * 3), Image.NEAREST).save(art)
                ys, xs = np.where(diff > 24)
                out.append({"detector": NAME, "shot": f"{vname}/{shot}", "severity": "fail", "artifact": str(art),
                            "msg": f"{frac * 100:.2f}% of pixels differ from golden (tolerance {tol * 100:.2f}%), box x {xs.min()}..{xs.max()} y {ys.min()}..{ys.max()}"})
    return out
