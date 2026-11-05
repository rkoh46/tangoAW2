"""Tests for the kit commands added to catch up with the Gauntlet, scene and BH2 work (no ROM, no game): `gauntlet new-map / cos / army-sheet / faces / start`, `campaign text-lint / scene-check`,
`bh2 waves`, `co consistency`."""
import subprocess
import unittest

from . import cfg, cli
from .commands import campaign, gauntlet


def parse(*argv):
    return cli.build_parser().parse_args(list(argv))


class Parsing(unittest.TestCase):
    def test_every_new_command_parses_and_has_its_function(self):
        for argv in (["gauntlet", "new-map", "13", "Salt Flats"], ["gauntlet", "new-map", "13", "X", "--apply"], ["gauntlet", "cos"], ["gauntlet", "army-sheet", "--map", "3", "5"],
                     ["gauntlet", "faces", "--map", "12"], ["campaign", "text-lint", "es"], ["campaign", "text-lint"], ["campaign", "scene-check", "-j", "2"],
                     ["bh2", "waves", "--mission", "32", "--list"], ["bh2", "waves", "--mission", "32", "--reuse", "--no-looks"], ["co", "consistency", "caulder"]):
            a = parse(*argv)
            self.assertTrue(callable(a.fn), argv)

    def test_score_and_two_maps_parse_and_the_score_table_is_consistent(self):
        for argv in (["gauntlet", "score"], ["gauntlet", "score", "--markdown"], ["gauntlet", "two-maps", "--out", "x.png"]):
            self.assertTrue(callable(parse(*argv).fn), argv)
        import sys
        sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
        from aw2test import gauntlet_score as gs
        rows = gs.table()
        self.assertEqual(len(rows), 12)
        for key, title, n, old, new, res in rows:
            self.assertGreaterEqual(new, old, f"{title}: no map's par got stricter")
            for name, (before, after) in res.items():
                self.assertGreaterEqual(after["total"], before["total"], f"{title} {name}")
        self.assertEqual(gs.speed(36, 36), 100)
        self.assertEqual(gs.speed(144, 36), 0)
        self.assertEqual(gs.rank(280), "S")
        self.assertEqual(gs.rank(279), "A")

    def test_gauntlet_start_help_names_the_army_screen(self):
        text = gauntlet.__doc__ + subprocess.run([str(cfg.REPO / "aw2dev"), "gauntlet", "start", "--help"], capture_output=True, text=True).stdout
        self.assertIn("army screen", text)
        self.assertNotIn("CO pick", text)
        self.assertIn("3_army_screen", gauntlet.START_PICTURES)


class GauntletMaps(unittest.TestCase):
    text = gauntlet.MODE_RS.read_text()

    def test_the_twelve_maps_are_read_with_their_enemies(self):
        maps = gauntlet.read_maps(self.text)
        self.assertGreaterEqual(len(maps), 12)
        self.assertEqual(maps[0][1:3], ("gauntlet_01", "Cinder Sea"))
        self.assertEqual(maps[0][3], ["DRAKE", "SENSEI", "HAWKE"])
        self.assertEqual(gauntlet.max_maps(), 32)

    def test_the_real_maps_reuse_only_named_exceptions(self):
        lines, bad = gauntlet.cos_report(gauntlet.read_maps(self.text), gauntlet.read_exceptions(self.text), gauntlet.read_roster(self.text))
        self.assertEqual(bad, [], lines)
        self.assertTrue(any("allowed exception" in l for l in lines))
        self.assertTrue(any("fight on no map yet" in l for l in lines))

    def test_an_unnamed_repeat_is_flagged_and_a_stale_exception_reported(self):
        maps = [("a", "gauntlet_01", "A", ["DRAKE", "SAMI"]), ("b", "gauntlet_02", "B", ["DRAKE", "MAX"])]
        lines, bad = gauntlet.cos_report(maps, {"SAMI": ["gauntlet_01", "gauntlet_09"]}, ["DRAKE", "SAMI", "MAX", "ANDY"])
        self.assertEqual(bad, ["DRAKE"])
        self.assertTrue(any("stale exception: SAMI" in l for l in lines))
        self.assertTrue(any("ANDY" in l and "no map" in l for l in lines))

    def test_new_map_refuses_a_duplicate_a_name_clash_and_the_limit(self):
        for nn, name, exists in (("12", "Anything", False), ("13", "Cinder Sea", False), ("33", "Over", False), ("13", "Fresh Name", True), ("zz", "X", False)):
            with self.assertRaises(ValueError, msg=(nn, name)):
                gauntlet.plan_new_map(nn, name, self.text, exists, 32)
        with self.assertRaises(ValueError):                       # a full list refuses, whatever the number
            gauntlet.plan_new_map("13", "Fresh Name", self.text, False, 12)

    def test_new_map_scaffold_inserts_the_stub_and_the_mission_name(self):
        spec, fn, stub, new = gauntlet.plan_new_map("13", "Salt Flats", self.text, False, 32)
        self.assertEqual(fn, "salt_flats")
        self.assertIn('MissionDef::new("gauntlet_13", "Salt Flats")', new)
        self.assertIn("last_eclipse(), salt_flats()]", new)
        self.assertLess(new.index("fn salt_flats"), new.index("pub fn def()"))
        self.assertIn("/// The Gauntlet mode's maps as a campaign", new[new.index("fn salt_flats"):])      # (def()'s doc comment stays above def())
        self.assertIn("gauntlet_13", spec)
        self.assertEqual(new.count("fn salt_flats"), 1)
        # the scaffold adds exactly one more map to the list read back
        self.assertEqual(len(gauntlet.read_maps(new)), len(gauntlet.read_maps(self.text)) + 1)
        self.assertEqual(gauntlet.read_maps(new)[-1][1], "gauntlet_13")

    def test_new_map_command_dry_path_writes_only_the_spec_and_refuses_twice(self):
        spec = gauntlet.SPEC_DIR / "gauntlet_13.py"
        self.assertFalse(spec.exists(), "a test must not find a map 13: use another number when the Gauntlet grows past 12")
        before = gauntlet.MODE_RS.read_text()
        try:
            a = parse("gauntlet", "new-map", "13", "Salt Flats")
            self.assertEqual(a.fn(a), 0)
            self.assertTrue(spec.exists())
            self.assertEqual(gauntlet.MODE_RS.read_text(), before, "no --apply: the Rust file is untouched")
            self.assertEqual(a.fn(a), 1, "the second run refuses: the spec exists")
        finally:
            if spec.exists():
                spec.unlink()


class CampaignKit(unittest.TestCase):
    def test_results_are_read_per_map(self):
        out = ("PASS ds   gauntlet_lines_gauntlet_08_arrival_boxes_are_all_shown_and_clean   6 checks  /x\n"
               "FAIL ds   gauntlet_lines_gauntlet_08_intro_and_victory_faces_have_their_own_palette   2 checks  /y\n"
               "PASS ds   bh2_scene_check_m31   19 checks  /z\n")
        rows = dict(campaign.scene_table(campaign.parse_results(out)))
        self.assertEqual(rows["gauntlet_08"], {"arrival": True, "intro/victory": False})
        self.assertEqual(rows["bh2 M31"], {"scenes": True})

    def test_text_lint_runs_the_real_lints_clean(self):
        a = parse("campaign", "text-lint", "all")
        self.assertEqual(a.fn(a), 0)


class WavesAndConsistency(unittest.TestCase):
    def test_the_waves_example_lists_m32_when_built(self):
        exe = cfg.REPO / "target" / "release" / "examples" / "aw2_campaign_waves"
        if not exe.exists():
            self.skipTest("example not built (aw2dev build --examples)")
        out = subprocess.run([str(exe), "bh2", "bh2_32"], capture_output=True, text=True).stdout
        days = sorted({int(l.split("\t")[1]) for l in out.splitlines() if l.split("\t")[2] != "-"})
        self.assertEqual(days, [3, 5, 7])

    def test_consistency_static_checks_pass_on_the_committed_art(self):
        from .colib import consistency
        for co in ("caulder", "lili", "tabitha", "asuka", "aria"):
            res = consistency.static(co)
            self.assertTrue(all(ok for _, ok, _ in res), (co, res))
        self.assertFalse(consistency.static("nobody")[0][1])


class SaveExp(unittest.TestCase):
    """`aw2dev save exp`: a synthetic Flash (a profile listing one sector as slot 15) with a skill record of the old layout (no later COs' block)."""

    @staticmethod
    def sector(tag, payload, gen=1, directory=None):
        import struct
        sec = bytearray(0x1000)
        struct.pack_into("<I", sec, 0, 0x73726132)
        sec[4], sec[0xFFF], sec[5] = 0x55, 0xAA, 0x0F
        struct.pack_into("<I", sec, 8, gen)
        sec[0xD] = tag
        struct.pack_into("<H", sec, 0x50, len(payload))
        sec[0x52:0x52 + len(payload)] = payload
        if directory is not None:
            sec[0xFEF:0xFEF + 16] = bytes(directory)
        total = (sum(sec) + 0xFF) & 0xFF
        sec[6], sec[7] = total, (~total) & 0xFF
        return bytes(sec)

    def image(self, path):
        import struct
        from aw2 import savelib
        record = bytearray(savelib.SKILLS_AT) + b"SKL1" + bytearray(32 * 30) + bytes(savelib.HISTORY_LEN) + b"DSWR"     # (the old layout: the War Room's mark where the later block now is)
        struct.pack_into("<I", record, savelib.co_offset(2), 3210)           # Max
        profile = self.sector(0, bytes(0x20), directory=[0, 15] + [0xFF] * 14)
        data = profile + self.sector(15, bytes(record)) + b"\xff" * 0x1000 * 14
        with open(path, "wb") as f:
            f.write(data)

    def test_an_old_record_reads_the_later_cos_as_zero_and_set_exp_adds_their_block(self):
        import os
        import tempfile
        from aw2 import savelib
        with tempfile.TemporaryDirectory() as d:
            old = os.path.join(d, "old.sav")
            self.image(old)
            rows = {r[0]: r for r in savelib.exp_table(old)}
            self.assertEqual(len(rows), 35)
            self.assertEqual(rows[2][2], 3210)
            self.assertEqual(rows[92][2], 0)
            new = savelib.set_exp(old, os.path.join(d, "new.sav"), {92: 7000, 1: 2500})
            rows = {r[0]: r for r in savelib.exp_table(new)}
            self.assertEqual((rows[92][2], rows[92][3], rows[1][2], rows[2][2], rows[93][2]), (7000, 7, 2500, 3210, 0))
            self.assertEqual(savelib._saveimg().Image(new).slot(15)[savelib.EXTRA_AT:savelib.EXTRA_AT + 4], b"SKX1")
            self.assertEqual(savelib.co_slot(89), savelib.co_slot(87), "a retired Silver Nova id is its copy's")
            with self.assertRaises(ValueError):
                savelib.co_slot(40)
