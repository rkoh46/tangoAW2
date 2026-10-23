"""Tests of the army-skin kit (run by `aw2dev test`): the committed harness scripts match their generators, the scenarios are well-formed, the
data file's checks run. Needs the AW2 ROM and the built `aw2_skin_dump` for the checks (skipped without)."""
import unittest
from pathlib import Path
from .. import cfg
from . import scenarios, check, EXE

EX = cfg.REPO / "tango-gamesupport-aw2" / "examples"


class Scripts(unittest.TestCase):
    def test_committed_scripts_match_the_generators(self):
        for fname, name in (("aw2_skin_units_2p.txt", "units"), ("aw2_skin_5p.txt", "map5p")):
            text = (EX / fname).read_text().split("\n", 1)[1]
            self.assertEqual(text, scenarios.script(name), f"{fname} is out of date: `aw2dev armyskin scenario {name}` and copy, or regenerate (docs/dev/army-packs.md)")

    def test_every_scenario_takes_the_shots_it_names(self):
        for n, sc in scenarios.SCENARIOS.items():
            text = scenarios.script(n)
            for shot in ([] if sc["look"] else sc["shots"]):   # (a look scenario's picture is the app's, not a harness shot)
                self.assertRegex(text, rf"shot {shot} \d", f"{n}: shot {shot} is never taken")
            self.assertRegex(text.splitlines()[0], r"^n \d$")

    def test_identities_become_pokes(self):
        text = scenarios.script("units", [6, 2])
        self.assertIn("poke 0203CB11 06", text)
        self.assertIn("poke 0203CB21 02", text)


@unittest.skipUnless(cfg.aw2_rom().exists() and EXE().exists(), "needs the AW2 ROM and aw2_skin_dump")
class Skin(unittest.TestCase):
    def test_static_checks_pass(self):
        fails, rep = check.static()
        self.assertEqual(fails, [], "\n".join(rep))

    def test_thresholds_catch_a_green_skin(self):
        # a skin in Green Earth's own greens must be refused by the palette margins
        import tempfile, re
        text = (cfg.REPO / "tango-gamesupport-aw2" / "skins" / "emerald_sun.toml").read_text()
        green = re.sub(r"ramp = \[.*?\]", 'ramp = ["67FBA0", "27EC48", "1BE63C", "0B0030", "024018", "00E008"]', text, count=1)
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write(green)
        fails, _ = check.static(f.name)
        Path(f.name).unlink()
        self.assertTrue(any("Green Earth" in x for x in fails), fails)


class Originality(unittest.TestCase):
    def test_the_match_ratio(self):
        from ..armyskinlib import check
        a = {(x, y) for x in range(4) for y in range(4)}
        self.assertEqual(check._jaccard(a, a), 1.0)
        self.assertEqual(check._jaccard(a, {(10, 10)}), 0.0)
        self.assertEqual(check._best(a, check._shift(a, 2, 1))[0], 1.0)           # found at its offset
        self.assertEqual(check._best(a, check._shift(a, 0, 0, True, 4))[0], 1.0)   # and mirrored

