"""Screenshots of every dialogue box of a scene, for the review of the BH Campaign's dialogue (no overflow, no cut-off).

`shoot(ctx, e, d, prefix)` presses A through the scene the game is showing and photographs each box once its text
has been typed out; `sheet(...)` puts the pictures of one scene on contact sheets (3 columns, 2x). Both need PIL
for the sheets; the single pictures are BMPs in the test's output folder."""

import os

from . import dscampaign as dc

SHOTS = os.environ.get("AW2TEST_DIALOGUE_SHOTS")   # a folder the contact sheets are copied to


def shoot(ctx, e, d, prefix, max_boxes=140, patience=90, tick=None, typed=150, first=0, only=None, wait_map=False):
    """From the first box on screen to the end of the scene (no script for `patience` frames). `only` (a set of
    box numbers, from 1) limits the pictures; every box is still stepped through. Returns the pictures' paths."""
    paths, n, stable, quiet, last = [], 0, 0, 0, None
    frames = 0
    while n < max_boxes and frames < 120000:
        if tick:
            tick()
        t = d.text_shown()
        stable = stable + 1 if t and t == last else 0
        last = t
        if d.scripts_running():
            quiet = 0
        else:
            quiet += 1
            if n > 0 and ((d.world_map_up() and e.u8(dc.WM_STATE + 0x10)) or (quiet > patience and not wait_map)):
                break
            if not t and not d.in_battle() and not d.world_map_up() and quiet % 10 == 0:
                e.press("A", 4)                       # (the result screens between a win and its scenes)
        if t and stable >= 5:
            e.wait(typed)                              # (the box types its text out)
            n += 1
            if only is None or n in only:
                paths.append(e.shot(os.path.join(ctx.out, f"{prefix}_{n:02d}")))
            e.press("A", 4)
            e.wait(30)
            stable = 0
            last = None
            continue
        if d.scripts_running() and not t:
            # (a command between boxes: a face change, a pause)
            pass
        e.wait(4)
        frames += 4
    return paths


def sheet(ctx, paths, name, cols=3, scale=2):
    """Contact sheets of the pictures (nine to a sheet): returns the files' paths."""
    try:
        from PIL import Image
    except ImportError:
        return []
    out = []
    for s in range(0, len(paths), cols * 3):
        chunk = paths[s:s + cols * 3]
        ims = [Image.open(p).convert("RGB") for p in chunk]
        w, h = ims[0].width * scale, ims[0].height * scale
        rows = (len(ims) + cols - 1) // cols
        im = Image.new("RGB", (cols * w + (cols + 1) * 6, rows * h + (rows + 1) * 6), (40, 40, 40))
        for k, p in enumerate(ims):
            im.paste(p.resize((w, h), Image.NEAREST), (6 + (k % cols) * (w + 6), 6 + (k // cols) * (h + 6)))
        f = os.path.join(ctx.out, f"{name}_sheet{s // (cols * 3) + 1}.png")
        im.save(f)
        out.append(f)
        if SHOTS:
            os.makedirs(SHOTS, exist_ok=True)
            im.save(os.path.join(SHOTS, os.path.basename(f)))
    return out
