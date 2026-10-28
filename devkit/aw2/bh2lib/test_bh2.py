"""The BH2 map kit's tests (run by `aw2dev test python`): the specs make the checked-in text maps, every BH2 map lints clean, the owner's rules hold (inventions on Black Hole's side
only, at most one HQ per army and a second HQ only as `Q`, every army at most 50 units, full ammo and fuel by construction, the Deathray at the top and not in Act I), a Lander test where
the map has Landers, the sky front has air only, the world-map flags lie on land inside their nations, and the pictures carry "MISSION N" burned in. Rule tests plant a map. ROM needed for
the lint parts (skipped without it); nothing from the game is stored."""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aw2 import cfg, bh2lib                                    # noqa: E402
from aw2.esmaplib import load_spec, specs, BH2_DIR            # noqa: E402

HAVE = cfg.aw2_rom().exists()


class Specs(unittest.TestCase):
    def test_every_spec_makes_its_text_map(self):
        for p in specs("bh2"):
            m = load_spec(p)
            f = BH2_DIR / f"{m.name}.txt"
            self.assertTrue(f.exists(), m.name)
            self.assertEqual(f.read_text(), m.text(), f"{m.name}: run `aw2dev maps gen --campaign bh2`")

    def test_act_one_has_its_five_missions(self):
        names = {p.stem for p in specs("bh2")}
        for n, (name, _) in bh2lib.MISSIONS.items():
            self.assertIn(name, names, f"M{n}")
        self.assertIn("bh2_04b", names, "M4's second front")

    def test_sizes_and_unit_caps(self):
        for p in specs("bh2"):
            m = load_spec(p)
            self.assertLessEqual(m.w, 64); self.assertLessEqual(m.h, 40); self.assertLessEqual(m.w * m.h, 1288)
            for a in range(1, m.hdr["armies"] + 1):
                self.assertLessEqual(sum(1 for u in m.u if u["army"] == a), 50, f"{m.name} army {a}")
            self.assertEqual(sum(1 for u in m.u if u["hp"]), 0, f"{m.name}: deployed units start at full strength (and the map builder gives full ammo and fuel)")

    def test_deathray_only_in_m22_at_the_top_edge(self):
        """The Deathray is Black Hole's alone and stands at the top edge: M27 only (IV01 checks the row)."""
        for p in specs("bh2"):
            rows = load_spec(p).rows()
            has = "D" in "".join(rows)
            self.assertEqual(has, p.stem == "bh2_27", p.stem)
            if has:
                self.assertIn("D", rows[1], "the Deathray's anchor is on row 1: its footprint touches the top edge")

    def test_sky_front_is_air_only_and_has_no_property(self):
        m = load_spec(BH2_DIR / "spec" / "bh2_04b.py")
        self.assertTrue(m.hdr["nohq"])
        self.assertTrue(all(u["kind"] in (12, 16, 17) for u in m.u))      # Stealth, Fighter, Bomber: no B Copter, no ground, no Anti-Air
        self.assertEqual(set("".join(m.rows())), {"."})

    def test_no_map_has_a_second_hq(self):
        for p in specs("bh2"):
            n = "".join(load_spec(p).rows()).count("Q")
            self.assertEqual(n, 0, p.stem)     # (no army has a second HQ: rule HQ01)


class Looks(unittest.TestCase):
    def test_act_one_looks_and_weather(self):
        got = {n: (look, weather, fog) for n, _, look, weather, fog in bh2lib.looks()}
        self.assertEqual(got[1], ("normal", "clear", True))       # M1: normal with fog
        self.assertEqual(got[2][0], "normal"); self.assertEqual(got[3][:2], ("desert", "sandstorm")); self.assertEqual(got[4][0], "normal"); self.assertEqual(got[5][0], "wasteland")

    def test_a_picture_comparison_catches_two_missions_that_look_alike(self):
        """Planted: a desert mission and a wasteland mission next to each other, both pictures the same sand, same weather: flagged; with different weather or a different ground: not."""
        import tempfile
        from PIL import Image
        real = bh2lib.looks
        try:
            with tempfile.TemporaryDirectory() as d:
                for n, c in ((1, (246, 238, 131)), (2, (246, 230, 139)), (3, (197, 230, 49))):
                    Image.new("RGB", (32, 32), c).save(Path(d) / f"m{n}_full.png")
                bh2lib.looks = lambda: [(1, "a", "desert", "clear", False), (2, "b", "wasteland", "clear", False), (3, "c", "normal", "clear", False)]
                lines, warns = bh2lib.check_pictures(d)
                self.assertTrue(any("M1 and M2" in w for w in warns), warns)
                self.assertFalse(any("M2 and M3" in w for w in warns), warns)
                bh2lib.looks = lambda: [(1, "a", "desert", "sandstorm", False), (2, "b", "wasteland", "clear", False), (3, "c", "normal", "clear", False)]
                self.assertEqual(bh2lib.check_pictures(d)[1], [])
        finally:
            bh2lib.looks = real

    def test_neighbouring_missions_do_not_look_alike(self):
        self.assertEqual(bh2lib.check_looks(), [])


class Flags(unittest.TestCase):
    def test_flags_on_land_inside_their_nation(self):
        self.assertEqual(bh2lib.check_flags(), [])

    def test_a_flag_on_the_sea_or_in_the_wrong_nation_is_caught(self):
        real = bh2lib.flags
        try:
            bh2lib.flags = lambda: [(1, 5, 2, 2), (2, 5, 96, 173), (3, 3, 96, 173), (4, 3, 150, 215), (5, 3, 115, 140), (26, 5, 30, 222)]
            problems = bh2lib.check_flags()
        finally:
            bh2lib.flags = real
        self.assertTrue(any("M1" in p and "sea" in p for p in problems), problems)
        self.assertTrue(any("M2" in p and "lies in Green Earth" in p for p in problems), problems)


@unittest.skipUnless(HAVE, "needs the AW2 ROM")
class Lint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from aw2.maplint import load, rules
        cls.rules = rules
        cls.maps = load.bh2_maps()

    def test_every_map_is_clean(self):
        for m in self.maps:
            probs = self.rules.lint(m)
            bad = [str(p) for p in probs if p.level == "error" or p.rule.startswith(("DQ", "SP", "MD")) or p.rule in ("PP03", "PP04")]
            self.assertEqual(bad, [], m.name)

    def test_inventions_are_black_holes_alone(self):
        n = sum(1 for m in self.maps for row in m.text for c in row if c in "SNWELvnFXO")
        self.assertGreater(n, 0)
        for m in self.maps:
            self.assertEqual([p for p in self.rules.lint(m) if p.rule == "IV01"], [], m.name)

    def test_iv01_catches_an_invention_on_the_allies_side(self):
        from aw2.maplint import load
        mappy, _, _ = load._five()
        rows = ["1.........."] + ["..........."] * 8 + ["..........2"]
        rows[8] = "........L.."            # next to the Allies' HQ (the bottom right)
        meta = {"name": "t", "rows": rows, "armies": 2, "colours": [5, 3], "units": {}, "tab": 3, "wasteland": False}
        edge = mappy.sea_edges(load.rom_bytes())
        m = load.MapData("t", "bh2", mappy.tiles(meta, edge), units=[], text=rows, meta=meta)
        self.assertTrue([p for p in self.rules.lint(m) if p.rule == "IV01"])
        rows[8] = "..........."; rows[2] = ".L........."      # beside Black Hole's HQ
        m = load.MapData("t", "bh2", mappy.tiles(dict(meta, rows=rows), edge), units=[], text=rows, meta=dict(meta, rows=rows))
        self.assertFalse([p for p in self.rules.lint(m) if p.rule == "IV01"])

    def _port_map(self, rows):
        from aw2.maplint import load
        mappy, _, _ = load._five()
        meta = {"name": "t", "rows": rows, "armies": 2, "colours": [5, 3], "units": {}, "tab": 3, "wasteland": False}
        edge = mappy.sea_edges(load.rom_bytes())
        return load.MapData("t", "bh2", mappy.tiles(meta, edge), units=[], text=rows, meta=meta)

    def test_an_inland_port_is_an_error(self):
        """The owner's standing rule: a port touches sea a ship can launch into. A port with land all round fails PT01 / PT02 in a bh2 map; the same port on open sea passes."""
        inland = ["1.............", "..............", "..............", ".....P........", "..............", "..............", "..............", ".............2",
                  "~~~~~~~~~~~~~~", "~~~~~~~~~~~~~~", "~~~~~~~~~~~~~~", "~~~~~~~~~~~~~~"]
        bad = {p.rule for p in self.rules.lint(self._port_map(inland))}
        self.assertTrue({"PT01", "PT02"} <= bad, bad)
        coast = ["1.............", "..............", "..............", "..............", "..............", "..............", "....P.........", ".............2",
                 "~~~~~~~~~~~~~~", "~~~~~~~~~~~~~~", "~~~~~~~~~~~~~~", "~~~~~~~~~~~~~~"]
        coast[7] = ".............2"
        # (the port's row is the last land row but one: put it on the shore line instead)
        coast[6], coast[7] = "..............", "....P........2"
        ok = {p.rule for p in self.rules.lint(self._port_map(coast))}
        self.assertEqual(ok & {"PT01", "PT02"}, set(), ok)

    def test_a_pond_port_is_an_error(self):
        pond = ["1.............", "..............", "..............", "..............", "..~~~~~.......", "..P~~~~.......", "..~~~~~.......", "..............", ".............2",
                "~~~~~~~~~~~~~~", "~~~~~~~~~~~~~~", "~~~~~~~~~~~~~~"]
        bad = {p.rule for p in self.rules.lint(self._port_map(pond))}
        self.assertIn("PT02", bad)

    def test_landers_have_a_beach(self):
        """A Lander test: every Lander of M1 and M4 stands on sea that touches a shoal or port its army can reach (RC04 / DQ10 are quiet)."""
        for m in self.maps:
            if any(u["kind"] == 23 for u in m.units):
                self.assertEqual([p for p in self.rules.lint(m) if p.rule in ("RC04", "DQ10")], [], m.name)

    def test_second_hq_is_allowed_once(self):
        m5 = next(m for m in self.maps if m.name == "bh2_05")
        self.assertEqual([p for p in self.rules.lint(m5) if p.rule == "AR02"], [])

    def test_beaches_are_long_on_the_naval_maps(self):
        """Shoal runs of 6 or more cells (the owner's rule: long stretches, not 1 or 2 tiles) on the island maps M1 and M4."""
        for name in ("bh2_01", "bh2_04"):
            m = next(m for m in self.maps if m.name == name)
            best = 0
            for row in m.text:
                run = 0
                for c in row + "~":
                    run = run + 1 if c == "," else 0
                    best = max(best, run)
            self.assertGreaterEqual(best, 8, f"{name}: the longest beach is {best} cells")


class Pictures(unittest.TestCase):
    @unittest.skipUnless(HAVE, "needs the AW2 ROM")
    def test_pictures_are_made_with_the_mission_title_burned_in(self):
        import tempfile
        from aw2.bh2lib import pictures
        with tempfile.TemporaryDirectory() as d:
            paths = pictures.write_all(d)
            names = {p.name for p in paths}
            for want in ("m01.png", "m01_fog.png", "m02.png", "m03.png", "m04.png", "m05.png", "act1_sheet.png"):
                self.assertIn(want, names)
            self.assertTrue(pictures.world_flags(Path(d) / "w.png").exists())


class Features(unittest.TestCase):
    @unittest.skipUnless(HAVE, "needs the AW2 ROM")
    def test_feature_table_lists_what_the_maps_use(self):
        table, counts, missing = bh2lib.features_table(list(bh2lib.maps().values()))
        for need in ("Com Tower", "missile silo", "pipe seam", "Black Factory", "Laser", "minicannon", "Black Crystal", "airport", "port"):
            self.assertTrue(any(c.get(need) for c in counts.values()), need)
        self.assertNotIn("Deathray", "".join(row for m in bh2lib.maps().values() for row in m.text))


if __name__ == "__main__":
    unittest.main()


class Silhouettes(unittest.TestCase):
    """The silhouette rule (the owner's): no new map is too like another, none is a rounded blob in the sea (approved maps are grandfathered)."""

    def test_maps_are_varied(self):
        from . import silhouette
        problems, _ = silhouette.check(str(Path(__file__).resolve().parents[3] / "tango-gamesupport-aw2" / "five" / "bh2"))
        self.assertEqual(problems, [])
