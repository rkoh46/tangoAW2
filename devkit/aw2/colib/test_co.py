"""Tests of the CO kit (run by `aw2dev test`): the data files are valid, the committed art is what the supplied pictures give and passes the lint, the lint catches bad art, the importer's
steps (background cut, palette, outline, expressions) behave, the names fit. No ROM is needed."""
import copy, tempfile, unittest
from pathlib import Path
import numpy as np
from PIL import Image
from .. import cfg
from . import data, importer as I, namefont, style

COS = ("klaus", "aurelia", "cassius", "livia")


class Data(unittest.TestCase):
    def test_the_committed_files_are_valid(self):
        cos, tags = data.load_all()
        self.assertEqual(data.problems(cos, tags), [])

    def test_four_emerald_sun_cos_with_six_pairs(self):
        cos, tags = data.load_all()
        es = [c for c, d in cos.items() if d["army"] == "emerald_sun"]
        self.assertEqual(sorted(es), sorted(COS))
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
        del cos["livia"]["portrait"]
        tags = copy.deepcopy(tags)
        tags["pair"][0]["stars"] = 3
        msgs = " ".join(data.problems(cos, tags))
        for want in ("stars", "beyond AW2's range", "do not match compat", "portrait.source missing"):
            self.assertIn(want, msgs)

    def test_names_fit_the_plates(self):
        cos, _ = data.load_all()
        for co, full, w, short, sw, fits in data.name_plates(cos):
            self.assertTrue(fits, f"{full} is {w} px")

    def test_the_name_graphics_fit_48_pixels(self):
        for n in ("Klaus", "Aurelia", "Cassius", "Livia"):
            g = namefont.name_grid(n)
            self.assertEqual(g.shape, (16, 48))
            self.assertTrue((g[:, 0] == 0).all() and (g[:, 47] == 0).all() or n == "Cassius", n)
        with self.assertRaises(ValueError):
            namefont.name_grid("Cassiusss")


class Art(unittest.TestCase):
    def test_the_committed_art_passes_the_lint(self):
        for co in COS:
            self.assertEqual(I.lint_art(co), [], co)

    def test_the_committed_art_is_what_the_pictures_give(self):
        for co in COS:
            cos, _ = data.load_all()
            im = I.import_co({"source": cos[co]["portrait"]["source"]})
            I.all_expressions(im, im.spec)
            old, _pal = I.read_art(co)
            for name, idx in I.pictures(im).items():
                self.assertTrue(np.array_equal(old[name], idx), f"{co} {name}: `aw2dev co portrait import` and commit")

    def test_the_lint_catches_bad_art(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            d = root / "klaus"
            d.mkdir()
            for n in I.FILES:
                (d / f"{n}.png").write_bytes((I.ART_DIR / "klaus" / f"{n}.png").read_bytes())
            (d / "name.png").write_bytes((I.ART_DIR / "klaus" / "name.png").read_bytes())
            self.assertEqual(I.lint_art("klaus", root), [])
            # a coloured pixel against transparency, and a wrong size
            a = np.array(Image.open(d / "face_normal.png"))
            ys, xs = np.nonzero(a == 15)
            a[ys[0], xs[0]] = 3
            Image.fromarray(a, mode="P").save(d / "face_normal.png")
            im = Image.open(d / "face_sad.png").crop((0, 0, 40, 48))
            im.save(d / "face_sad.png")
            msg = " ".join(I.lint_art("klaus", root))
            self.assertIn("without an outline", msg)
            self.assertIn("40 x 48", msg)


@unittest.skipUnless(cfg.aw2_rom().exists(), "needs the AW2 ROM (AW2's own art is the yardstick)")
class Style(unittest.TestCase):
    def test_the_committed_art_is_in_aw2s_style(self):
        r = style.aw2_ranges()[0]
        for co in COS:
            pics, pal = I.read_art(co)
            rows, bad = style.lint(pics, pal, r)
            self.assertEqual(bad, [], co)

    def test_a_dark_painterly_picture_fails_the_style_lint(self):
        # the previous import (a faithful downscale of the painterly picture) is the example the user rejected: dark and textured
        r = style.aw2_ranges()[0]
        cos, _ = data.load_all()
        im = I.import_co({"source": cos["aurelia"]["portrait"]["source"]}, painterly=True)
        pics = {"large": im.large, "face_normal": im.faces["normal"]}
        rows, bad = style.lint(pics, im.palette, r)
        self.assertTrue(bad, "the painterly import should be out of AW2's range somewhere")

    def test_aw2s_own_art_passes_its_own_lint(self):
        r, figs, faces = style.aw2_ranges()
        n, idx, pal = style.aw2_figures()[1]            # Andy
        f = style.aw2_faces()[1]
        rows, bad = style.lint({"large": idx, "face_normal": f[1]}, pal, r)
        self.assertEqual(bad, [])


class Steps(unittest.TestCase):
    def test_background_is_cut_by_a_flood_from_the_top(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "x.jpg"
            im = np.full((80, 60, 3), (6, 10, 18), np.uint8)
            im[30:80, 15:45] = (200, 160, 120)          # a figure
            im[40:44, 25:29] = (6, 10, 18)              # a hole inside it of the background's colour: not the background
            Image.fromarray(im).save(p, quality=100)
            src = I.Source(p)
            self.assertFalse(src.alpha[5, 5])
            self.assertTrue(src.alpha[60, 30])
            self.assertTrue(src.alpha[42, 27], "a dark hole inside the figure must stay")

    def test_the_outline_goes_round_the_silhouette_but_not_the_cut_bottom(self):
        a = np.zeros((20, 20), np.uint8)
        a[5:20, 5:15] = 3
        o = I.outline(a)
        self.assertEqual(o[4, 8], 15)
        self.assertEqual(o[10, 4], 15)
        self.assertEqual(o[19, 8], 3)

    def test_isolated_pixels_are_removed_but_detail_stays(self):
        a = np.full((9, 9), 4, np.uint8)
        a[4, 4] = 7
        self.assertEqual(I.despeckle(a)[4, 4], 4)
        b = np.full((9, 9), 4, np.uint8)
        b[4, 3:6] = 7
        self.assertEqual(I.despeckle(b)[4, 4], 7)


if __name__ == "__main__":
    unittest.main()
