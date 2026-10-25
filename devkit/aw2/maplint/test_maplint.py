"""Regression tests of the map linter (run by `aw2dev test python`): every rule fires on a planted map that has the problem and stays quiet on the
same map finished properly, and the BH Campaign's maps are clean. Needs the AW2 ROM (skipped without it); nothing from the game is stored."""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aw2 import cfg                                   # noqa: E402
from aw2.maplint import load, rules                  # noqa: E402

HAVE = cfg.aw2_rom().exists()


def build(rows, units=()):
    """A MapData from text rows (the legend of five/map.py; HQs 1 and 2 are added in the corners if the rows have none)."""
    mappy, _, _ = load._five()
    rows = list(rows)
    if not any(c in "12" for r in rows for c in r):
        rows[0] = "1" + rows[0][1:]
        rows[-1] = rows[-1][:-1] + "2"
    m = {"name": "t", "rows": rows, "armies": 2, "colours": [1, 2], "units": {}, "tab": 3, "wasteland": False}
    edge = mappy.sea_edges(load.rom_bytes())
    return load.MapData("t", "bh", mappy.tiles(m, edge), units=list(units), text=rows, meta=m)


DESIGN = ("DQ", "SP")


def ids(m, design=False):
    """The rules a map trips (the integrity rules; `design=True`: only the design-quality rules, DQ.. and SP..)."""
    return {p.rule for p in rules.lint(m) if p.rule.startswith(DESIGN) == design}


FLAT = ["1" + "." * 10, *["." * 11] * 7, "." * 10 + "2"]


@unittest.skipUnless(HAVE, "needs the AW2 ROM")
class Lint(unittest.TestCase):
    def test_clean_control(self):
        self.assertEqual(ids(build(FLAT)), set())

    def test_river_dry_end_and_no_outlet(self):
        rows = list(FLAT)
        rows[4] = ".....---...".ljust(11, ".")             # a river with both ends dry on plain
        got = ids(build(rows))
        self.assertIn("RV01", got)
        self.assertIn("RV03", got)

    def test_river_edge_to_edge_is_fine(self):
        rows = list(FLAT)
        rows[4] = "-" * 11
        self.assertEqual(ids(build(rows)), set())

    def test_river_from_mountain_spring_to_sea(self):
        rows = list(FLAT)
        rows[8] = "." * 10 + "2"
        for y in range(3, 7):
            rows[y] = rows[y][:5] + "-" + rows[y][6:]
        rows[2] = rows[2][:5] + "^" + rows[2][6:]
        rows[7] = rows[7][:5] + "~" + rows[7][6:]
        for x in range(4, 7):
            rows[8] = rows[8][:x] + "~" + rows[8][x + 1:]
        self.assertFalse(ids(build(rows)) & {"RV01", "RV03"}, ids(build(rows)))

    def test_road_crossing_river_needs_a_bridge(self):
        rows = list(FLAT)
        rows[4] = "-" * 11
        rows[3] = "R" * 11
        rows[5] = "R" * 11
        for y in range(3, 6):
            pass
        rows = list(FLAT)
        for y in range(0, 9):
            rows[y] = rows[y][:5] + "-" + rows[y][6:]
        rows[4] = "R" * 5 + "-" + "R" * 5
        self.assertIn("RV04", ids(build(rows)))
        rows[4] = "R" * 5 + "=" + "R" * 5
        self.assertNotIn("RV04", ids(build(rows)))

    def test_puddle(self):
        rows = list(FLAT)
        rows[4] = rows[4][:5] + "~" + rows[4][6:]
        self.assertIn("SE01", ids(build(rows)))
        rows[4] = rows[4][:5] + "~" + rows[4][6:]
        rows[4] = rows[4][:6] + "~" + rows[4][7:]
        self.assertNotIn("SE01", ids(build(rows)))       # (two cells: a pond the games draw)

    def test_unit_on_terrain(self):
        rows = list(FLAT)
        rows[4] = rows[4][:5] + "^" + rows[4][6:]
        tank = {"army": 1, "kind": 5, "x": 5, "y": 4, "hp": 100, "hold": False, "name": ""}
        self.assertIn("UN01", ids(build(rows, [tank])))
        inf = dict(tank, kind=1)
        self.assertNotIn("UN01", ids(build(rows, [inf])))
        two = [inf, dict(inf, kind=2)]
        self.assertIn("UN02", ids(build(rows, two)))

    def test_isolated_road_and_gap(self):
        rows = list(FLAT)
        rows[4] = rows[4][:5] + "R" + rows[4][6:]
        self.assertIn("RD01", ids(build(rows)))
        rows[4] = "RRRR.RRRR.."
        self.assertIn("RD02", ids(build(rows)))

    # ---- design-quality rules: a planted bad map for each, the same map finished properly

    def wide(self, f=None, units=(), w=30, h=20):
        rows = [["."] * w for _ in range(h)]
        if f:
            f(rows)
        rows[0][0] = "1"
        rows[-1][-1] = "2"
        # (a diagonal scatter of woods, in runs of three at most, so the plain-field and sparse-map rules stay quiet unless the test is about them)
        base = [["f" if (x + 2 * y) % 5 < 3 else "." for x in range(w)] for y in range(h)]
        for y in range(h):
            for x in range(w):
                if rows[y][x] == ".":
                    rows[y][x] = base[y][x]
        return build(["".join(r) for r in rows], units)

    def test_design_clean_control(self):
        self.assertEqual(ids(self.wide(), design=True), set())

    def test_dq01_straight_river(self):
        def river(rows):
            for y in range(len(rows)):
                rows[y][14] = "-"
        got = ids(self.wide(river), design=True)
        self.assertIn("DQ01", got)

        def bent(rows):
            for y in range(len(rows)):
                rows[y][14 + (3 if 6 < y < 14 else 0)] = "-"
            for x in range(14, 18):
                rows[6][x] = "-"
                rows[14][x] = "-"
        self.assertNotIn("DQ01", ids(self.wide(bent), design=True))

    def test_dq02_dq03_drawn_blocks_and_stripes(self):
        def blocks(rows):
            for k in range(4):
                for y in range(3 + k * 4, 6 + k * 4):
                    for x in range(3 + k * 6, 8 + k * 6):
                        rows[y][x] = "^"
        got = ids(self.wide(blocks), design=True)
        self.assertIn("DQ02", got)
        self.assertIn("DQ03", got)

    def test_dq04_dq05_empty_land(self):
        got = ids(build(["1" + "." * 29] + ["." * 30] * 18 + ["." * 29 + "2"]), design=True)
        self.assertTrue({"DQ04", "DQ05"} <= got, got)

    def test_dq06_dq08_dq09_roads_and_properties(self):
        def road(rows):
            for x in range(1, 29):
                rows[10][x] = "R"
        self.assertIn("DQ06", ids(self.wide(road), design=True))

        def lone(rows):
            rows[10][20] = "C"
        self.assertIn("DQ08", ids(self.wide(lone), design=True))

        def pocket(rows):
            rows[10][10] = "1"
            for y in range(7, 14):
                for x in range(7, 14):
                    if (x, y) != (10, 10) and max(abs(x - 10), abs(y - 10)) <= 2:
                        rows[y][x] = "~"
        self.assertIn("DQ09", ids(self.wide(pocket), design=True))

    def test_dq07_unit_blob_and_sp01_room(self):
        blob = [{"army": 1, "kind": 1, "x": 4 + i % 4, "y": 4 + i // 4, "hp": 100, "hold": False, "name": ""} for i in range(16)]
        self.assertIn("DQ07", ids(self.wide(units=blob), design=True))
        spread = [dict(u, x=3 + 2 * (i % 5), y=3 + 3 * (i // 5)) for i, u in enumerate(blob)]
        self.assertNotIn("DQ07", ids(self.wide(units=spread), design=True))
        packed = [{"army": 1 + i % 2, "kind": 5, "x": 1 + i % 8, "y": 1 + (i // 8) * 2, "hp": 100, "hold": False, "name": ""} for i in range(40)]
        small = build(["1" + "." * 7] + ["........"] * 6 + ["." * 7 + "2"], packed)
        self.assertIn("SP01", ids(small, design=True))

    def test_dq10_lander_needs_a_beach(self):
        def sea(rows):
            for y in range(len(rows)):
                for x in range(20, 30):
                    rows[y][x] = "~"
        lander = {"army": 1, "kind": 23, "x": 25, "y": 10, "hp": 100, "hold": False, "name": ""}
        self.assertNotIn("DQ10", ids(self.wide(sea, [lander]), design=True))

        def island(rows):
            sea(rows)
            for y in range(len(rows)):
                rows[y][19] = "^"
        self.assertIn("DQ10", ids(self.wide(island, [lander]), design=True))

    def test_render_check_flags_a_wrong_drawing_and_forgives_animation(self):
        import random, tempfile
        from PIL import Image
        from aw2.maplint import render_check as rc
        rows = list(FLAT)
        for y in range(0, 9):
            rows[y] = rows[y][:5] + "-" + rows[y][6:]
        m = build(rows)
        G = rules.Grid(m)
        rnd = random.Random(5)
        base = {}                                    # one made-up drawing a tile id, so every river cell of the map is drawn alike

        def picture(tweak=None, animate=False):
            im = Image.new("RGB", (G.w * 16, G.h * 16), (150, 200, 90))
            for y in range(G.h):
                for x in range(G.w):
                    if G.g[y][x] == "-":
                        t = G.t[y][x]
                        if t not in base:
                            base[t] = [tuple(rnd.randrange(256) for _ in range(3)) for _ in range(256)]
                        px = list(base[t])
                        if animate:
                            for k in range(10):
                                px[rnd.randrange(256)] = (1, 2, 3)           # (a few moving pixels)
                        if tweak and (x, y) == tweak:
                            px = [(200, 0, 0)] * 256                          # a tile that is not the river's drawing
                        tile = Image.new("RGB", (16, 16))
                        tile.putdata(px)
                        im.paste(tile, (x * 16, y * 16))
            return im
        with tempfile.TemporaryDirectory() as d:
            ref = []
            for k in range(8):
                f = f"{d}/r{k}.png"
                picture(animate=True).save(f)
                ref.append((m, f))
            r = rc.learn(ref)
            good, bad, moving = f"{d}/good.png", f"{d}/bad.png", f"{d}/moving.png"
            picture().save(good)
            picture(tweak=(5, 4)).save(bad)
            picture(animate=True).save(moving)
            self.assertEqual(rc.check(m, good, r), [])
            self.assertEqual(rc.check(m, moving, r), [])
            self.assertEqual([(x, y) for x, y, _ in rc.check(m, bad, r)], [(5, 4)])

    def test_a_river_ends_in_water_or_at_the_edge_never_on_land(self):
        rows = list(FLAT)
        for y in range(3, 9):
            rows[y] = rows[y][:5] + "-" + rows[y][6:]
        rows[2] = rows[2][:5] + "^" + rows[2][6:]            # a mountain 'spring': AW2 has no source tile, the river looks cut off
        rows[8] = rows[8][:5] + "~" + rows[8][6:]
        for x in range(4, 7):
            rows[8] = rows[8][:x] + "~" + rows[8][x + 1:]
        self.assertIn("RV05", ids(build(rows)))
        rows[2] = rows[2][:5] + "." + rows[2][6:]
        self.assertIn("RV01", ids(build(rows)))            # (on plain it is the old rule)
        rows = list(FLAT)
        for y in range(0, 9):
            rows[y] = rows[y][:5] + "-" + rows[y][6:]
        for x in range(4, 7):
            rows[8] = rows[8][:x] + "~" + rows[8][x + 1:]
        self.assertFalse(ids(build(rows)) & {"RV01", "RV03", "RV05"})   # (edge to sea)

    def test_emerald_sun_rivers_all_end_in_water_or_at_the_edge(self):
        bad = [(m.name, str(p)) for m in load.es_maps() for p in rules.lint(m, {"RV01", "RV03", "RV05"})]
        self.assertEqual(bad, [])

    def test_bh_campaign_maps_are_clean(self):
        # (nothing is excused: bh10 and bh31 once were, with a river cut off against a mountain; their rivers now run to the edge and the sea)
        self.assertEqual(rules.KNOWN, {})
        bad = [(m.name, str(p)) for m in load.bh_maps() for p in rules.lint(m) if p.level == "error"]
        self.assertEqual(bad, [])

    def test_games_own_maps_stay_quiet_on_the_joins_we_learned_from(self):
        # (the pair and transition rules are learned from AW2's maps: they must not flag AW2 itself)
        for m in load.aw2_maps():
            got = {p.rule for p in rules.lint(m)} & {"TJ01", "TJ02", "GB01", "SE03"}
            self.assertEqual(got, set(), m.name)


if __name__ == "__main__":
    unittest.main()
