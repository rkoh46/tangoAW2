"""Pictures of Dual Strike's arrows (opt-in: `AW2TEST_VSPARTNER_PICS=<dir>`): Versus' Teams screen with the cursor going CO ->
partner (a partner being picked) -> the next army, and the War Room's grid with the cursor moving in all four directions.
Each frame at 3x, and a sheet of them."""

import os

from aw2test import png, shots
from aw2test.harness import Skip, test

from tests.test_ds_arrows import WALK, tap
from tests.test_ds_coselect import BYTE_DRIVEN, DS_GRAPHICS, shot, war_room_co_screen


def sheet(path, frames, cols=2, scale=3, gap=6):
    h, w = len(frames[0]), len(frames[0][0])
    rows_n = -(-len(frames) // cols)
    out = [[(30, 30, 30)] * (cols * w + (cols - 1) * gap) for _ in range(rows_n * h + (rows_n - 1) * gap)]
    for i, f in enumerate(frames):
        ox, oy = (i % cols) * (w + gap), (i // cols) * (h + gap)
        for y, r in enumerate(f):
            out[oy + y][ox:ox + w] = r
    png.write(path, out, scale)


def save(frames, d, name):
    for i, f in enumerate(frames):
        png.write(os.path.join(d, f"{name}_{i:02d}.png"), f, 3)
    sheet(os.path.join(d, f"{name}_sheet.png"), frames)


@test(modes=("ds",))
def vspartner_pictures(ctx):
    d = os.environ.get("AW2TEST_VSPARTNER_PICS")
    if not d:
        raise Skip("AW2TEST_VSPARTNER_PICS not set")
    os.makedirs(d, exist_ok=True)
    g = ctx.boot_teams(ctx.map(), env=BYTE_DRIVEN)
    e = g.e
    e.w8(DS_GRAPHICS, 1)
    e.wait(40)
    frames = [shot(ctx, e, "vp_0")]
    # CO -> partner -> partner picked (DOWN twice) -> the next army's CO -> its partner -> picked -> the tabs
    for i, (k, n) in enumerate([("RIGHT", 1), ("DOWN", 1), ("DOWN", 1), ("RIGHT", 1), ("DOWN", 1), ("RIGHT", 1), ("DOWN", 1), ("DOWN", 1),
                                ("RIGHT", 1), ("RIGHT", 1)]):
        tap(e, k, 35)
        frames.append(shot(ctx, e, f"vp_{i + 1}"))
    save(frames, d, "versus")
    e, _ = war_room_co_screen(ctx, True)
    e.w8(DS_GRAPHICS, 1)
    e.wait(40)
    frames = [shot(ctx, e, "wr_0")]
    for i, k in enumerate(["RIGHT", "RIGHT", "DOWN", "DOWN", "LEFT", "UP", "UP", "UP", "LEFT", "DOWN"]):
        e.press(k, 6)
        e.wait(WALK)
        frames.append(shot(ctx, e, f"wr_{i + 1}"))
    save(frames, d, "war_room")
