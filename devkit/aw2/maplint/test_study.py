"""Tests of the map design study and the principle rules MD01..MD08 (`aw2dev maps study`, docs/dev/map-design.md): AWBW ids read as the right
terrain and armies, the measures on small planted maps, and each rule firing on a map with the problem and quiet on the same map done properly.
No ROM needed: the maps are built as StudyMaps from text rows."""
import sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aw2.maplint import study as st, principles as pr          # noqa: E402


def sm(rows, units=(), player=1, side=None):
    """A StudyMap from text rows (study legend; digits = HQs; B C A P owned by the nearest HQ's army, b c a p neutral)."""
    g = [list(r.upper() if False else r) for r in rows]
    hq = {int(c): (x, y) for y, r in enumerate(rows) for x, c in enumerate(r) if c.isdigit()}
    own = [[0] * len(rows[0]) for _ in rows]
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            if c.isdigit():
                g[y][x] = "H"
                own[y][x] = int(c)
            elif c in "BCAP" and hq:
                own[y][x] = min(hq, key=lambda a: abs(hq[a][0] - x) + abs(hq[a][1] - y))
            elif c in "bcap":
                g[y][x] = c.upper()
    return st.StudyMap("t", "test", g, own, side or {}, list(units), player)


def rules_of(m):
    return {p.rule for p in pr.check_study(m)}


# a well-made small campaign field: cities every few cells, roads to them, woods and hills, a city in the middle
GOOD = [
    "1.RC.f.C..f.C.^",
    "B.R..f..R...f.^",
    ".fR.C..cR.c...f",
    "..RRRRRRRRRRR..",
    ".c..f.^.C.f..c.",
    "...^..R.f...^..",
    "f.c..cR..c..f..",
    "..RRRRRRRRRRR.B",
    ".f..C.f..c..f.2",
]


class Awbw(unittest.TestCase):
    def test_ids(self):
        self.assertEqual(st.awbw_char(1), (".", ""))
        self.assertEqual(st.awbw_char(42), ("H", "OS"))
        self.assertEqual(st.awbw_char(39), ("B", "OS"))
        self.assertEqual(st.awbw_char(125), ("H", "JS"))          # Jade Sun's HQ (confirmed: jadesunhq on AWBW's preview)
        self.assertEqual(st.awbw_char(123), ("B", "JS"))
        self.assertEqual(st.awbw_char(160), ("H", "PC"))          # Pink Cosmos (the map API's country code "pc")
        self.assertEqual(st.awbw_char(185), ("H", "AR"))
        self.assertEqual(st.awbw_char(146), ("L", "OS"))          # Orange Star's lab
        self.assertEqual(st.awbw_char(133), ("T", ""))
        self.assertEqual(st.awbw_char(112), ("m", ""))

    def test_parse_and_owners(self):
        grid = "\n".join(["# 1 players=2 size=5x3 name=Tiny cats=x", "42,1,34,1,47", "39,1,1,1,44", "1,1,28,1,1", ""])
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.txt").write_text(grid)
            ms = st.load_dir(d)
        self.assertEqual(len(ms), 1)
        m = ms[0]
        self.assertEqual(m.meta["title"], "Tiny")
        self.assertEqual(m.g[0], list("H.C.H"))
        self.assertEqual(m.own[0], [1, 0, 0, 0, 2])
        self.assertEqual(m.own[1][0], 1)
        self.assertEqual(m.own[1][4], 2)

    def test_lab_seats(self):
        grid = "\n".join(["# 2 players=2 size=4x2 name=Labs cats=x", "146,39,1,140", "1,1,44,1", ""])
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.txt").write_text(grid)
            m = st.load_dir(d)[0]
        self.assertEqual(sorted(m.meta["seats"]), [1, 2])


class Measure(unittest.TestCase):
    def test_numbers(self):
        r = st.measure(sm(GOOD, player=0))
        self.assertGreater(r["props_per100"], 10)
        self.assertEqual(r["sides"], 2)
        self.assertTrue(r["contested_centre"])
        self.assertLessEqual(r["prop_gap"], 3)
        self.assertGreaterEqual(r["road_lanes"], 1)

    def test_lanes(self):
        cut = [(x, 0) for x in range(12)]
        m = sm(["...^^^.....^", "1..........2"], player=0)
        self.assertEqual(st.lanes_on(m, cut), [3, 5])
        self.assertEqual(st.lanes_on(sm(["...^.......^", "1..........2"], player=0), cut), [10])     # (one cell does not split a lane)


class Principles(unittest.TestCase):
    def test_good_is_quiet(self):
        self.assertEqual(rules_of(sm(GOOD)), set())

    def test_md01_sparse(self):
        rows = ["1" + "." * 14] + ["." * 15] * 7 + ["." * 14 + "2"]
        self.assertIn("MD01", rules_of(sm(rows)))

    def test_md02_dead_corner(self):
        rows = [r + "f.f.f.f.f." for r in GOOD]
        got = rules_of(sm(rows))
        self.assertIn("MD02", got)
        rows2 = [r + "f.f.c.f.f." for r in GOOD]
        self.assertNotIn("MD02", rules_of(sm(rows2)))

    def test_md03_corridor(self):
        rows = ["..c....^....c..", ".C.....^.....C.", "..R....^....R..", "..R..c...c..R..", "1RRRRRR=RRRRRR2", "..R..c...c..R..", "..R....^....R..",
                ".C.....^.....C.", "..c....^....c.."]
        rows = [r[:7] + ("^" if r[7] in ".=" and i not in (3, 4, 5) else r[7]) + r[8:] for i, r in enumerate(rows)]
        rows = [r.replace("=", "R") for r in rows]
        self.assertIn("MD03", rules_of(sm(rows)))             # one gate of three cells in a wall between the two HQs
        rows2 = [r[:7] + ("." if i in (0, 1, 7, 8) else r[7]) + r[8:] for i, r in enumerate(rows)]
        self.assertNotIn("MD03", rules_of(sm(rows2)))          # gates at both ends too: three ways

    def test_md04_base_in_reach(self):
        rows = list(GOOD)
        rows[1] = "B.B..f..R...f.^"                            # an enemy-owned base two cells from the player's (own of the nearest HQ: give it to 2)
        m = sm(rows)
        m.own[1][2] = 2
        self.assertIn("MD04", rules_of(m))
        m2 = sm(GOOD, units=[{"army": 2, "kind": 1, "x": 2, "y": 0}])
        self.assertIn("MD04", rules_of(m2))
        self.assertNotIn("MD04", rules_of(sm(GOOD, units=[{"army": 2, "kind": 1, "x": 12, "y": 8}])))

    def test_md05_nothing_in_the_middle(self):
        rows = [r.replace("C", "f").replace("c", "f") if 0 <= i <= 8 and True else r for i, r in enumerate(GOOD)]
        rows[0], rows[8] = "1.RC.f......C.^", ".f..C.f.....f.2"
        rows = [r[:4] + r[4:11].replace("C", "f").replace("c", "f") + r[11:] for r in rows]
        self.assertIn("MD05", rules_of(sm(rows)))

    def test_md06_open_field(self):
        rows = [r.replace("f", ".").replace("^", ".") for r in GOOD]
        self.assertIn("MD06", rules_of(sm(rows)))

    def test_md07_long_river(self):
        rows = list(GOOD) + ["-" * 15]
        self.assertIn("MD07", rules_of(sm(rows)))
        rows[-1] = "------=--------"
        self.assertNotIn("MD07", rules_of(sm(rows)))

    def test_md08_roads_to_nowhere(self):
        rows = [r.replace("R", ".") for r in GOOD]
        rows[8] = "RRRRRRRRRRRRRR2"
        self.assertIn("MD08", rules_of(sm(rows)))


if __name__ == "__main__":
    unittest.main()
