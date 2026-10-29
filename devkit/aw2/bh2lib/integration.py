"""The BH2 integration proof sheet (`aw2dev bh2 integration`): the harness's own frames of the real game, 240 x 160 each, labelled: the Campaign chooser with BH2 listed, the prologue, the world map,
one pre-mission scene per act with its dialogue box showing, and Aria's CO select (the War Room grid). The frames come from `tools/aw2test/out/ds/` (run `-k story_trace_bh2`, `-k aria_pics_co_select_grid` and `-k aria_pics_co_page_one` first)."""
import json
from pathlib import Path

from PIL import Image, ImageDraw

from .. import cfg

OUT = cfg.REPO / "tools" / "aw2test" / "out" / "ds"
ACTS = [(1, "Act I, M1 Black Insight"), (9, "Act II, M9 Paper Lanterns"), (17, "Act III, M17 Lot 42"), (22, "Act IV, M22 Echo, Again"), (26, "Act V, M26 The Second Folder"), (31, "Finale, M31 (Aria)"), (32, "Secret, M32")]


def _rows(label, folder):
    return json.loads((OUT / folder / f"{label}.json").read_text())


def _dialogue_frame(label, folder, skip=0):
    """The `skip`-th distinct dialogue box's frame of a trace (the first is often the card's fade)."""
    seen = 0
    for r in _rows(label, folder):
        if r.get("settled") and r["battle"]:
            if seen >= skip:
                return OUT / folder / r["settled"]
            seen += 1
    raise SystemExit(f"{label}: no dialogue frame")


def _world_map(label, folder):
    for r in _rows(label, folder):
        if r.get("shot") and r["map"] and not r["text"] and r["frame"] > 1000:
            return OUT / folder / r["shot"]
    raise SystemExit(f"{label}: no world-map frame")


def _prologue(label, folder):
    for r in _rows(label, folder):
        if r.get("settled") and r["song"] == 425:
            return OUT / folder / r["settled"]
    raise SystemExit("no prologue frame")


def frames():
    f = []
    f.append(("Campaign chooser: BH2 CAMPAIGN listed", OUT / "story_trace_bh2_chooser" / "bh2_chooser.bmp"))
    f.append(("Prologue", _prologue("bh2_opening", "story_trace_bh2_opening")))
    f.append(("World map", _world_map("bh2_opening", "story_trace_bh2_opening")))
    # (the prologue's chained scenes: the castle, the Allies, the Obelisk)
    seen = {}
    for r in _rows("bh2_opening", "story_trace_bh2_opening"):
        if r.get("settled") and r["song"] in (517, 520, 554) and r["song"] not in seen:
            seen[r["song"]] = OUT / "story_trace_bh2_opening" / r["settled"]
    for song, name in ((517, "Prologue scene: the Orange Castle"), (520, "Prologue scene: the quay"), (554, "Prologue scene: the Obelisk")):
        if song in seen:
            f.append((name, seen[song]))
    for n, name in ACTS:
        f.append((f"{name}: pre-mission scene", _dialogue_frame(f"bh2_m{n:02d}", "story_trace_bh2_missions")))
    f.append(("Aria's CO select (War Room grid)", OUT / "aria_pics_co_select_grid" / "grid_aria.bmp"))
    f.append(("Aria's CO page 1", OUT / "aria_pics_co_page_one" / "co_page1.bmp"))
    return f


def sheet(path):
    fs = frames()
    cols, S, pad, head = 3, 2, 10, 22
    w, h = 240 * S, 160 * S
    rows = (len(fs) + cols - 1) // cols
    img = Image.new("RGB", (cols * (w + pad) + pad, rows * (h + head + pad) + pad), (20, 24, 40))
    d = ImageDraw.Draw(img)
    for i, (cap, p) in enumerate(fs):
        x, y = pad + (i % cols) * (w + pad), pad + (i // cols) * (h + head + pad)
        d.text((x, y + 4), cap, fill=(250, 235, 120))
        img.paste(Image.open(p).convert("RGB").resize((w, h), Image.NEAREST), (x, y + head))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def prologue_sheet(path, run=True):
    """`aw2dev bh2 prologue-sheet`: runs the harness test `story_trace_bh2_prologue_frames` (every page and dialogue box of the prologue, one frame each, typed out), then a contact sheet of all the frames
    (numbered, 6 across) at `path` and every frame as a PNG in a folder beside it (`prologue_frames/NNN.png`) with `prologue.json` (the text and song of each)."""
    import subprocess
    import sys
    if run:
        r = subprocess.run([sys.executable, str(cfg.REPO / "tools" / "aw2test" / "run.py"), "-k", "story_trace_bh2_prologue_frames"], cwd=cfg.REPO)
        if r.returncode:
            raise SystemExit("the prologue frames test failed")
    src = OUT / "story_trace_bh2_prologue_frames"
    rows = json.loads((src / "prologue.json").read_text())
    path = Path(path)
    frames = path.parent / "prologue_frames"
    frames.mkdir(parents=True, exist_ok=True)
    cols, w, h, head = 6, 240, 160, 14
    n = len(rows)
    img = Image.new("RGB", (cols * (w + 4) + 4, ((n + cols - 1) // cols) * (h + head + 4) + 4), (20, 24, 40))
    d = ImageDraw.Draw(img)
    for r in rows:
        k = r["n"]
        im = Image.open(src / r["shot"]).convert("RGB")
        im.save(frames / f"{k:03d}.png")
        x, y = 4 + (k % cols) * (w + 4), 4 + (k // cols) * (h + head + 4)
        d.text((x, y), f"{k}  song {r['song']}", fill=(250, 235, 120))
        img.paste(im, (x, y + head))
    (frames / "prologue.json").write_text(json.dumps(rows, indent=1))
    img.save(path)
    return path, n
