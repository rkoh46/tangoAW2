"""A region must be pixel-identical across variants (e.g. the NEXT TURN row with and without the Dual Strike pack: a font overwritten by pack art fails)."""
import numpy as np
from PIL import Image

NAME = "same"


def run(ctx):
    out = []
    for s in ctx.screen.get("same", []):
        a, b = s["variants"]
        x, y, w, h = s["region"]
        tol = s.get("tolerance", 0.0)
        for shot in ctx.shots(s.get("shots", ctx.screen.get("shots", []))):
            pa, pb = ctx.path(a, shot), ctx.path(b, shot)
            if not pa or not pb:
                continue
            A = np.asarray(Image.open(pa).convert("RGB"), dtype=int)[y:y + h, x:x + w]
            B = np.asarray(Image.open(pb).convert("RGB"), dtype=int)[y:y + h, x:x + w]
            d = (np.abs(A - B).sum(axis=2) > 24).mean()
            if d > tol:
                art = ctx.out / f"same_{shot}_{a}_vs_{b}.png"
                im = Image.new("RGB", (w * 3, h))
                im.paste(Image.fromarray(A.astype("uint8")), (0, 0))
                im.paste(Image.fromarray(B.astype("uint8")), (w, 0))
                im.paste(Image.fromarray((np.abs(A - B).sum(axis=2) > 24).astype("uint8").__mul__(255)).convert("RGB"), (2 * w, 0))
                im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(art)
                out.append({"detector": NAME, "shot": shot, "severity": "fail", "msg": f"region {x},{y},{w},{h} differs between {a} and {b} in {d * 100:.1f}% of pixels", "artifact": str(art)})
    return out
