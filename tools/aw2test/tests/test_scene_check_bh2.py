"""BH2 M31's scenes (the five-army finale) for `aw2dev campaign scene-check` (`-k bh2_scene_check_m31`): the same two lessons as the Gauntlet maps' `arrival_boxes_are_all_shown_and_clean` and
`intro_and_victory_faces_have_their_own_palette` (tests/test_gauntlet_lines.py). In a five-army battle the moved-unit grey of the current army shares BG palette 9 with the dialogue faces, and a mid-battle
box re-opens per speaker, so every box of the opening scene and of the arrival scene after each HQ capture must (1) be up (a box is shown), (2) have a text layer that shares no tile with the face, and
(3) draw its face with a CO's own palette (the speaker is not known here: any CO of the game's table will do; the grey is none of them). Generic over HQS of tests/test_bh2_progression.py."""

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test.harness import test
from tests.test_bh2_review import home
from tests.test_bh2_progression import HQS, capture, settle, to_player_turn
from tests.test_gauntlet_lines import _scene_state, face_palette_of, own_face_palettes

OWN = set()
ALL_COS = list(range(0, 19)) + list(range(72, 81)) + [86, 87, 88, 92, 93]      # (the COs the game and tangoAW2 have: the table rows `own_face_palettes` reads)


def sample(ctx, e, g, d, label, frames=200):
    """Presses A through the scenes now running; returns [(tiles shared by text and face, face palette)] of every box that was up."""
    seen = []
    for _ in range(frames):
        if not d.scripts_running():
            break
        e.wait(90)
        text, face, _, _ = _scene_state(e)
        if any(f == 0x08014401 for _, _, f in g.procs()):
            pal = face_palette_of(e)
            seen.append((sorted(text & face), pal, len(face), len(text)))
        if not d.scripts_running():                # (the scene ended while we looked: an A now would open the map's menu)
            break
        e.press("A", 4)
        e.wait(30)
    return seen


@test(modes=("ds",))
def bh2_scene_check_m31(ctx):
    e, g, d = b2.enter(ctx, 31)
    d.leave_setup()
    own = OWN
    for co in ALL_COS:
        own.update(own_face_palettes(e, co))
    boxes = []
    # the opening scene (the intro's boxes come as the battle starts)
    for _ in range(600):
        if d.scripts_running():
            break
        e.wait(10)
    boxes.append(("opening", sample(ctx, e, g, d, "opening")))
    to_player_turn(e, g, d)
    d.wait_control()
    g._units_base = g._players_base = None
    for name, cell, army, nation in HQS[:-1]:
        home(g, e)                                   # (the cursor back at the corner: the next capture selects from there)
        capture(ctx, e, g, d, cell, 5)
        boxes.append((f"{name}'s fall", sample(ctx, e, g, d, name)))
        settle(e, g, d)                              # (a rout's explosions are procs between the scripts)
        g._units_base = g._players_base = None
    for label, seen in boxes:
        ctx.check(seen, f"M31 {label}: a dialogue box was shown")
        ctx.eq([s[0] for s in seen], [[]] * len(seen), f"M31 {label}: no text tile of a box is a tile of the face")
        spoken = [s for s in seen if s[3]]           # (a narration box has no text tiles on the text layer and shows no face: its palette bank is whatever it was)
        ctx.check(all(s[1] in own for s in spoken), f"M31 {label}: every spoken box's face has a CO's own palette, not the moved-unit grey ({len(spoken)} of {len(seen)} boxes)")
    e.close()
