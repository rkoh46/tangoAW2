"""Tests of the CO kit (run by `aw2dev test`): the data files are valid, every portrait recipe composes and fits the game's 15 colours, a bad file is caught.
The portrait tests need the AW2 ROM and the Dual Strike .nds (skipped without)."""
import copy, unittest
from .. import cfg
from . import compose as cp, data, sheets

ROMS = cfg.aw2_rom().exists() and cfg.ds_rom().exists()


class Data(unittest.TestCase):
    def test_the_committed_files_are_valid(self):
        cos, tags = data.load_all()
        self.assertEqual(data.problems(cos, tags), [])

    def test_four_emerald_sun_cos_with_six_pairs(self):
        cos, tags = data.load_all()
        es = [c for c, d in cos.items() if d["army"] == "emerald_sun"]
        self.assertEqual(sorted(es), ["aurelia", "cassius", "klaus", "livia"])
        pairs = {frozenset((p["a"], p["b"])) for p in tags["pair"]}
        for a in es:
            for b in es:
                if a < b:
                    self.assertIn(frozenset((a, b)), pairs)

    def test_a_bad_file_is_caught(self):
        cos, tags = data.load_all()
        cos = copy.deepcopy(cos)
        cos["klaus"]["stars"] = {"cop": 6, "scop": 5}
        cos["klaus"]["cop"]["mods"] = [{"units": "all", "attack": 90}]
        tags = copy.deepcopy(tags)
        tags["pair"][0]["stars"] = 3
        msgs = " ".join(data.problems(cos, tags))
        self.assertIn("stars", msgs)
        self.assertIn("beyond AW2's range", msgs)
        self.assertIn("do not match compat", msgs)


@unittest.skipUnless(ROMS, "needs the AW2 ROM and the Dual Strike .nds")
class Portraits(unittest.TestCase):
    def test_every_option_composes_and_fits(self):
        cos, _ = data.load_all()
        for co, d in cos.items():
            for o in d["portrait"]["option"]:
                pics, donor, pal, merged = sheets.render_option(o)
                self.assertLessEqual(len(pal), 15, f"{co} {o['letter']}")
                self.assertEqual((pics["body"].w, pics["body"].h), (128, 160))
                self.assertEqual((pics["face"][0].w, pics["face"][0].h), (48, 48))
                self.assertEqual((pics["mini"].w, pics["mini"].h), (32, 24))
                self.assertEqual((pics["hud"].w, pics["hud"].h), (32, 16))

    def test_the_donor_readers_agree_with_the_games(self):
        a, d = cp.donor("aw2:andy"), cp.donor("ds:andy")
        self.assertEqual((len(a.body), len(a.body[0])), (160, 128))
        self.assertEqual((len(d.body), len(d.body[0])), (160, 128))
        self.assertTrue(any(any(r) for r in a.body) and any(any(r) for r in d.faces[0]))


@unittest.skipUnless(ROMS, "needs the AW2 ROM and the Dual Strike .nds (the similarity check reads the donors)")
class Originals(unittest.TestCase):
    """The v2 portraits: drawn by us (draw.py, heads.py, bodies.py, designs.py)."""

    def test_four_designs_per_co_all_pass_the_lint(self):
        from . import portraits as P
        ds = P.all_designs()
        for co in ("klaus", "aurelia", "cassius", "livia"):
            self.assertEqual(sorted(L for (c, L) in ds if c == co), ["A", "B", "C", "D"])
        for key, d in ds.items():
            bad, _ = P.lint(d)
            self.assertEqual(bad, [], key)

    def test_each_design_has_the_four_expressions_and_the_game_sizes(self):
        from . import portraits as P
        pics, pal, merged, (fig, faces) = P.make(next(iter(P.all_designs().values())))
        self.assertEqual(len(faces), 4)
        self.assertEqual((fig.w, fig.h), (128, 160))
        self.assertEqual((pics["mini"].w, pics["mini"].h, pics["hud"].w, pics["hud"].h), (32, 24, 32, 16))
        self.assertLessEqual(len(pal), 15)

    def test_the_similarity_check_catches_a_copy(self):
        from . import portraits as P, roms
        d = roms.aw2_portrait(14)    # Hawke, recoloured: the same picture must fail
        from .portraits import RPic
        from .draw import Art
        import numpy as np
        art = Art(128, 160)
        for y in range(160):
            for x in range(128):
                if d.body[y][x]:
                    art.g[y, x] = "ol"
        face = Art(48, 48)
        for y in range(48):
            for x in range(48):
                if d.faces[0][y][x]:
                    face.g[y, x] = "ol" if d.faces[0][y][x] in (15, 7, 8, 9) else "sk_m"
        cols = {"ol": "000000", "sk_m": "c08060"}
        pics = {"body": RPic(art, cols), "face": [RPic(face, cols)] * 4, "mini": RPic(face.crop(0, 0, 32, 24), cols), "hud": RPic(face.crop(0, 0, 32, 16), cols)}
        sim = P.similarity(pics)
        best = max(sim, key=lambda t: t[1])
        self.assertEqual(best[0], "aw2:Hawke")
        self.assertGreater(best[1], P.MAX_IOU)

    def test_names_fit_the_plates(self):
        cos, _ = data.load_all()
        for co, full, w, short, sw, fits in data.name_plates(cos):
            self.assertTrue(fits, f"{full} is {w} px")


if __name__ == "__main__":
    unittest.main()
