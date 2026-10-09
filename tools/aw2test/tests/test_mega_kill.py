"""A battle scene with a Dual Strike unit leaves the map as AW2's own scene does
(ds_battle.rs): the map's OBJ palettes (the cursor, the funds, the panels'
text, the buildings, the effects' rows 12 and 13) are put back when the scene
is over, and a destroyed defender never counters (no shot, no damage).

Before the fix the map after any such battle drew its cursor, funds digits and
panel text as black silhouettes: AW2 puts the map's palettes back a few frames
before the scene's proc ends and the module kept writing the unit's colours."""

from aw2test.harness import test
from tests.test_battle_scenes import fire, MAIN_CALLBACK, PAL

SHOTS = 0x020296B0 + 0x18  # per side 0x28: the shots a side's figures fired
# (attacker, defender, distance, terrain of each): a kill by a new unit, and a
# control, an AW2 unit's kill, that is how AW2's own scene leaves the map.
KILLS = [
    ("megatank", "antiair", 1, ("plain", "plain")),
    ("megatank", "tank", 1, ("plain", "plain")),
    ("piperunner", "tank", 2, ("pipe", "plain")),
    ("stealth", "tank", 1, ("plain", "plain")),
    ("carrier", "fighter", 3, ("sea", "plain")),
]
CONTROL = ("neotank", "antiair", 1, ("plain", "plain"))
# A new unit killed by an AW2 unit.
DEFENCES = [("tank", "megatank", 1), ("artillery", "megatank", 2), ("battleship", "carrier", 3)]


def run(ctx, name, att, dfd, dist, terrain, visuals="a", hp=5, att_hp=None):
    m = ctx.map()
    m.terrain(10, 10, terrain[0]).terrain(10 + dist, 10, terrain[1])
    m.unit(1, att, 10, 10).unit(2, dfd, 10 + dist, 10)
    g = ctx.start(m, ["andy", "olaf"], visuals=visuals)
    ctx.set_hp(g, 10 + dist, 10, hp)
    if att_hp:
        ctx.set_hp(g, 10, 10, att_hp)
    g.e.wait(30)
    fire(g, (10, 10), (10 + dist, 10))
    frames, shots = 0, [0, 0]
    for _ in range(600):
        g.e.wait(3)
        if g.e.u32(MAIN_CALLBACK) == 0:
            frames += 1
            for side in (0, 1):
                shots[side] = max(shots[side], g.e.u16(SHOTS + 0x28 * side))
        elif frames:
            break
    g.wait_for_input()
    g.e.wait(90)
    ctx.shot(g, name)
    pal = g.e.read(PAL, 0x200)
    survivors = [(u["type"], u["hp"]) for u in g.units() if u["y"] == 10 and 10 <= u["x"] <= 10 + dist]
    ctx.log(f"RUN {name}: scene frames {frames}, shots {shots}, left {survivors}")
    g.e.close()
    return pal, shots, frames, survivors


ANIMATED = (1, 7, 9, 10)  # the cursor's, the CO panel's and the panels' colours blink


def diff_rows(a, b):
    """The OBJ palette rows that differ; the animated rows only by the colours
    they have blacked out."""
    def zeros(p, r):
        return sum(1 for k in range(1, 16) if p[32 * r + 2 * k:32 * r + 2 * k + 2] == b"\0\0")
    return [r for r in range(16) if (zeros(a, r) != zeros(b, r) if r in ANIMATED else a[32 * r:32 * r + 32] != b[32 * r:32 * r + 32])]


@test(modes=("ds",), name="battle_scene_kill_leaves_map_palettes_and_no_counter")
def kills(ctx):
    control, cshots, cframes, _ = run(ctx, "control_neotank_kill", *CONTROL)
    ctx.check(cframes > 0 and cshots[1] == 0, f"control: a Neotank's kill shows a scene, no counter ({cshots})")
    ctx.eq(diff_rows(control, run(ctx, "control_neotank_kill_off", *CONTROL, visuals="off")[0]), [],
           "control: AW2's own scene leaves the palettes as with no scene")
    for att, dfd, dist, terrain in KILLS:
        label = f"{att} destroys {dfd}"
        pal, shots, frames, left = run(ctx, f"{att}_kills_{dfd}", att, dfd, dist, terrain)
        ctx.check(frames > 0, f"{label}: the battle scene ran ({frames})")
        ctx.eq(shots[1], 0, f"{label}: the destroyed defender fires no counter")
        ctx.check(len(left) == 1 and left[0][1] == 100, f"{label}: only the attacker is left, undamaged {left}")
        off = run(ctx, f"{att}_kills_{dfd}_off", att, dfd, dist, terrain, visuals="off")[0]
        ctx.eq(diff_rows(pal, off), [], f"{label}: the map's OBJ palettes are as with no scene")


@test(modes=("ds",), name="battle_scene_kill_of_new_unit_leaves_map_palettes")
def killed(ctx):
    for att, dfd, dist in DEFENCES:
        ter = ("sea", "sea") if att == "battleship" else ("plain", "plain")
        pal, shots, frames, left = run(ctx, f"{att}_kills_{dfd}", att, dfd, dist, ter)
        control = run(ctx, f"{att}_kills_{dfd}_off", att, dfd, dist, ter, visuals="off")[0]
        ctx.check(frames > 0, f"{att} destroys {dfd}: the scene ran")
        ctx.eq(shots[1], 0, f"{att} destroys {dfd}: no counter from the destroyed unit")
        ctx.eq(diff_rows(pal, control), [], f"{att} destroys {dfd}: the map's OBJ palettes are put back")


@test(modes=("ds",), name="battle_scene_hit_leaves_map_palettes")
def survives(ctx):
    """A battle that destroys nothing (the defender counters), and one with
    animations off, leave the same palettes."""
    control = run(ctx, "megatank_hits_megatank_off", "megatank", "megatank", 1, ("plain", "plain"), hp=100, att_hp=100, visuals="off")[0]
    pal, shots, frames, left = run(ctx, "megatank_hits_megatank", "megatank", "megatank", 1, ("plain", "plain"), hp=100, att_hp=100)
    ctx.check(frames > 0 and shots[1] > 0, f"Megatank against Megatank: a scene with a counter ({shots})")
    ctx.eq(diff_rows(pal, control), [], "palettes after a battle both sides survive are as with no scene")
    ctx.eq(run(ctx, "megatank_kills_antiair_off", "megatank", "antiair", 1, ("plain", "plain"), visuals="off")[2], 0,
           "animations off: no scene")
