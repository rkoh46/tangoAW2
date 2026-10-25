"""Tests of `aw2dev co verify` (run by `aw2dev test`): the specification module reads the data files, the tag table is complete, the table builder groups tagged log lines, the net scenarios
exist for every power and pair. No ROM is needed (the scenarios themselves are played by `aw2dev co verify`)."""
import sys
import tempfile
import unittest
from pathlib import Path

from .. import cfg, scenarios
from . import verify as V, verify_net as N

sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
from aw2test import cospec  # noqa: E402


class Spec(unittest.TestCase):
    def test_klaus_numbers_come_from_the_data_file(self):
        k = cospec.get("klaus")
        self.assertEqual((k.bonus(0, 1, 0), k.bonus(0, 1, 1), k.bonus(0, 5, 0)), (20, 20, 10))      # Imperium: all +10/+10, foot +10/+10 more
        self.assertEqual((k.bonus(1, 1, 1), k.bonus(1, 1, 2), k.bonus(1, 5, 2)), (40, 1, 0))        # Testudo: +20 defence on top, foot +1 move
        self.assertEqual((k.bonus(2, 1, 0), k.bonus(2, 1, 1), k.bonus(2, 5, 2)), (90, 60, 1))       # Legio Aeterna: +20 all, +40 foot, +10 of any power; defence +40 foot; +1 move
        self.assertEqual(k.heal, (0, 0, 3))

    def test_the_other_four(self):
        a, c, l = cospec.get("aurelia"), cospec.get("cassius"), cospec.get("livia")
        self.assertEqual((a.bonus(0, 10, 3), a.bonus(1, 10, 3), a.bonus(1, 15, 3), a.bonus(0, 5, 0)), (1, 2, 1, -10))
        self.assertEqual((c.bonus(0, 5, 2), c.bonus(2, 5, 2), c.bonus(2, 5, 0), c.bonus(0, 1, 2)), (1, 2, 60, 0))
        self.assertEqual((l.cost_percent(), l.income, l.tribute), (10, 25, (0, 200, 100)))
        self.assertEqual((l.bonus(2, 22, 2), l.bonus(2, 5, 2)), (2, 0))

    def test_unnamed_unit_types_are_not_covered(self):
        c = cospec.get("cassius")
        self.assertFalse(c.covers(4) or c.covers(9))
        with self.assertRaises(KeyError):
            c.bonus(1, 4, 2)
        self.assertTrue(cospec.get("klaus").covers(4))

    def test_every_pair_of_the_four_and_the_cross_army_pairs_are_listed(self):
        pairs = {frozenset((p["a"], p["b"])): p for p in cospec.tags()}
        for a in cospec.ES4:
            for b in cospec.ES4:
                if a < b:
                    self.assertIn(frozenset((a, b)), pairs)
        self.assertEqual(pairs[frozenset(("klaus", "aw2:kanbei"))]["name"], "Two Banners")
        self.assertEqual(pairs[frozenset(("crumb", "aw2:sturm"))]["compat"], 115)


class Table(unittest.TestCase):
    def test_columns(self):
        self.assertEqual(V.column("tag", ""), "tag")
        self.assertEqual(V.column("tag", "cpu"), "cpu")
        self.assertEqual(V.column("cop", "meter threshold"), "meter")
        self.assertEqual(V.column("scop", "Tank attacks Tank"), "scop")

    def test_a_failing_check_makes_its_cell_fail(self):
        with tempfile.TemporaryDirectory() as d:
            for name, lines in (("co_verify_a", ["ok    [klaus d2d] Tank attacks Tank: base damage 66", "ok    [klaus d2d] move: moves exactly 7"]),
                                ("co_verify_b", ["ok    [klaus cop] cpu: fired", "FAIL  [klaus scop] unit cost: a Tank costs 14000 (want 7000)", "ok    [aurelia tag] menu: Tag offered"])):
                (Path(d) / name).mkdir()
                (Path(d) / name / "log.txt").write_text("\n".join(lines) + "\n")
            V.out_dir = lambda n, d=d: Path(d) / n
            cells = V.collect(["co_verify_a", "co_verify_b"])
        self.assertEqual((cells[("klaus", "d2d")]["ok"], cells[("klaus", "scop")]["fail"], cells[("klaus", "cpu")]["ok"], cells[("aurelia", "tag")]["ok"]), (2, 1, 1, 1))
        t = V.table(["klaus", "aurelia"], cells)
        self.assertIn("PASS 2", t)
        self.assertIn("**FAIL** 1 of 1", t)


class Net(unittest.TestCase):
    def test_every_power_has_a_net_scenario_and_every_pair_of_the_four_too(self):
        for co in ("klaus", "aurelia", "cassius", "livia", "crumb", "varro", "cloneandy"):
            for p in ("cop", "scop"):
                self.assertIn(f"co_{co}_{p}", scenarios.SCEN)
            pokes, turns = scenarios.SCEN[f"co_{co}_scop"]("off")
            self.assertTrue(any(f" {scenarios.CO_IDS[co]:02X}" in l for l in pokes), co)


if __name__ == "__main__":
    unittest.main()
