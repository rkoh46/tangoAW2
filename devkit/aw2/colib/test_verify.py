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
    def test_tabitha_numbers_come_from_the_data_file(self):
        t = cospec.get("tabitha")
        self.assertEqual((t.has_cop, t.has_scop, t.stars), (False, True, (0, 9)))
        self.assertEqual((t.bonus(0, 1, 0), t.bonus(0, 1, 1), t.bonus(2, 1, 0), t.bonus(2, 5, 1)), (18, 18, 28, 18))      # Mega Boost +18 / +18; the power's own +10 firepower
        self.assertEqual(t.levels_played, (0, 2))
        self.assertEqual(cospec.strike("tabitha"), {"hp": 8, "radius": 2, "pick": "value", "stun": False, "can_kill": False})

    def test_lili_has_only_a_co_power_and_one_more_move(self):
        l = cospec.get("lili")
        self.assertEqual((l.has_cop, l.has_scop, l.stars, l.levels_played), (True, False, (3, 0), (0, 1)))
        self.assertEqual((l.bonus(0, 5, 0), l.bonus(1, 5, 0), l.bonus(1, 5, 1), l.bonus(1, 5, 2), l.bonus(0, 5, 2)), (10, 20, 10, 1, 0))
        self.assertEqual(l.power_names, ("Enigma", ""))

    def test_caulder_is_plus_43_in_cataclysm_and_heals_five(self):
        c = cospec.get("caulder")
        self.assertEqual((c.has_cop, c.has_scop, c.stars, c.heal), (False, True, (0, 4), (0, 0, 5)))
        self.assertEqual((c.bonus(0, 5, 0), c.bonus(2, 5, 0), c.bonus(0, 5, 1), c.bonus(2, 5, 1)), (18, 43, 18, 33))      # +18, then 18 + 15 + the power's own 10 (the defence's 10 is in the player's block)
        self.assertEqual(cospec.movement("caulder"), "sturm")

    def test_megatank_and_piperunner_are_covered_like_any_unit(self):
        for name in ("tabitha", "lili", "caulder"):
            s = cospec.get(name)
            for t in (4, 9):
                self.assertTrue(s.covers(t))
                self.assertEqual(s.bonus(0, t, 0), s.bonus(0, 5, 0))

    def test_every_pair_of_the_three_and_the_cross_army_pairs_are_listed(self):
        pairs = {frozenset((p["a"], p["b"])): p for p in cospec.tags()}
        for a in cospec.ES3:
            for b in cospec.ES3:
                if a < b:
                    self.assertIn(frozenset((a, b)), pairs)
        self.assertEqual({k: (v["compat"], v["stars"]) for k, v in ((tuple(sorted(k)), v) for k, v in pairs.items()) if "asuka" not in k and "aria" not in k and "crumb" not in k and "cloneandy" not in k},
                         {("lili", "tabitha"): (120, 2), ("caulder", "tabitha"): (108, 1), ("caulder", "lili"): (115, 2), ("aw2:kanbei", "tabitha"): (120, 2), ("aw2:colin", "lili"): (116, 2)})
        self.assertEqual(pairs[frozenset(("tabitha", "aw2:kanbei"))]["name"], "Iron Pact")
        self.assertEqual(pairs[frozenset(("crumb", "aw2:sturm"))]["compat"], 115)


class Hq(unittest.TestCase):
    def test_the_hq_follows_the_data_file(self):
        for co in ("tabitha", "lili", "caulder"):
            self.assertEqual(cospec.hq_style(co), "emerald_sun", co)
        for co in ("cloneandy", "crumb"):
            self.assertEqual(cospec.hq_style(co), "default", co)
        self.assertEqual(cospec.hq_style_of_id(86), "emerald_sun")
        self.assertEqual(cospec.hq_style_of_id(1), "default")


class Table(unittest.TestCase):
    def test_columns(self):
        self.assertEqual(V.column("tag", ""), "tag")
        self.assertEqual(V.column("tag", "cpu"), "cpu")
        self.assertEqual(V.column("cop", "meter threshold"), "meter")
        self.assertEqual(V.column("scop", "Tank attacks Tank"), "scop")

    def test_a_failing_check_makes_its_cell_fail(self):
        with tempfile.TemporaryDirectory() as d:
            for name, lines in (("co_verify_a", ["ok    [tabitha d2d] Tank attacks Tank: base damage 66", "ok    [tabitha d2d] move: moves exactly 7"]),
                                ("co_verify_b", ["ok    [tabitha cop] cpu: fired", "FAIL  [tabitha scop] unit cost: a Tank costs 14000 (want 7000)", "ok    [lili tag] menu: Tag offered"])):
                (Path(d) / name).mkdir()
                (Path(d) / name / "log.txt").write_text("\n".join(lines) + "\n")
            V.out_dir = lambda n, d=d: Path(d) / n
            cells = V.collect(["co_verify_a", "co_verify_b"])
        self.assertEqual((cells[("tabitha", "d2d")]["ok"], cells[("tabitha", "scop")]["fail"], cells[("tabitha", "cpu")]["ok"], cells[("lili", "tag")]["ok"]), (2, 1, 1, 1))
        t = V.table(["tabitha", "lili"], cells)
        self.assertIn("PASS 2", t)
        self.assertIn("**FAIL** 1 of 1", t)


class Net(unittest.TestCase):
    def test_every_power_has_a_net_scenario_and_every_pair_of_the_four_too(self):
        for co in ("tabitha", "lili", "caulder", "crumb", "cloneandy"):
            have = [p for p in ("cop", "scop") if f"co_{co}_{p}" in scenarios.SCEN]
            self.assertEqual(have, {"tabitha": ["scop"], "lili": ["cop"], "caulder": ["scop"]}.get(co, ["cop", "scop"]), co)
            pokes, turns = scenarios.SCEN[f"co_{co}_{have[-1]}"]("off")
            self.assertTrue(any(f" {scenarios.CO_IDS[co]:02X}" in l for l in pokes), co)


if __name__ == "__main__":
    unittest.main()
