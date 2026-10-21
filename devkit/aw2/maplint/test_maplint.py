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


def ids(m):
    return {p.rule for p in rules.lint(m)}


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

    def test_bh_campaign_maps_are_clean(self):
        bad = [(m.name, str(p)) for m in load.bh_maps() for p in rules.lint(m) if p.level == "error"]
        self.assertEqual(bad, [])

    def test_games_own_maps_stay_quiet_on_the_joins_we_learned_from(self):
        # (the pair and transition rules are learned from AW2's maps: they must not flag AW2 itself)
        for m in load.aw2_maps():
            got = {p.rule for p in rules.lint(m)} & {"TJ01", "TJ02", "GB01", "SE03"}
            self.assertEqual(got, set(), m.name)


if __name__ == "__main__":
    unittest.main()
