"""Tests of the CO kit (run by `aw2dev test`): the data files are valid, the committed art is what the supplied pictures give and passes the lint, the lint catches bad art, the importer's
steps (background cut, palette, outline, neutral expression faces) behave, the names fit. No ROM is needed."""
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

    def test_clone_andy_is_a_recolour_of_andy(self):
        cos, _ = data.load_all()
        c = cos["cloneandy"]
        self.assertEqual(c["portrait"]["base"], "andy")
        rc = c["portrait"]["recolour"]
        self.assertEqual(sorted(int(k) for k in rc), [2, 3, 4, 5, 6, 9, 10, 12])      # skin ramp (5 tones), jacket, its shade, shirt: nothing else (hair, rim, buckle, star, outline are Andy's)
        self.assertEqual(data.problems({"cloneandy": c}, {}), [])
        bad = copy.deepcopy(c)
        bad["portrait"]["recolour"]["0"] = "FFFFFF"
        self.assertIn("want an index 1..15", " ".join(data.problems({"cloneandy": bad}, {})))

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


class Pixelart(unittest.TestCase):
    """The pixel-art route: a small sprite upscaled by a fractional factor and saved as a JPEG is found again on its native grid and imported cell for cell."""

    @staticmethod
    def sprite(scale, w=40, h=56, seed=2):
        rng = np.random.default_rng(seed)
        pal = np.array([(230, 220, 210), (200, 150, 60), (150, 30, 40), (60, 70, 120), (240, 190, 150), (90, 60, 40)], float)
        nat = np.zeros((h, w, 3))
        nat[:] = (8, 8, 14)
        fg = np.zeros((h, w), bool)
        fg[6:52, 10:30] = True
        fg[10:14, 4:10] = True
        cols = rng.integers(0, len(pal), (h, w))
        nat[fg] = pal[cols[fg]]
        big = Image.fromarray(nat.astype(np.uint8)).resize((round(w * scale), round(h * scale)), Image.NEAREST)
        return nat.astype(np.uint8), fg, big

    def test_the_grid_and_the_native_cells_are_recovered_from_a_jpeg(self):
        from . import pixelart as P
        for scale in (4.0, 5.333):
            nat, fg, big = self.sprite(scale)
            with tempfile.TemporaryDirectory() as t:
                path = Path(t) / "s.jpg"
                big.save(path, quality=88)
                img = np.array(Image.open(path).convert("RGB"))
            px, ox, py, oy = P.detect_grid(img)
            self.assertAlmostEqual(px, scale, delta=0.06)
            self.assertAlmostEqual(py, scale, delta=0.06)
            got = P.native(img, (px, ox, py, oy))
            # the cell centres match the original cells (JPEG noise is a few levels; a phase error would show as a neighbour's colour); the first cell may be one off the sprite's own first cell
            best = 1.0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    g, n0 = got[max(dy, 0):, max(dx, 0):], nat[max(-dy, 0):, max(-dx, 0):]
                    h, w = min(g.shape[0], n0.shape[0]), min(g.shape[1], n0.shape[1])
                    best = min(best, np.mean(np.abs(g[:h, :w] - n0[:h, :w]).max(2) > 20))
            self.assertLess(best, 0.03, scale)

    def test_the_background_is_cut_by_the_flood_and_the_dark_figure_stays(self):
        from . import pixelart as P
        nat = np.zeros((30, 20, 3))
        nat[:] = (12, 10, 16)
        nat[5:25, 6:14] = (30, 30, 44)               # a near-black uniform, barely lighter than the background
        nat[12:14, 8:10] = (14, 12, 18)              # a dark pocket inside the figure, not connected to the border
        fg, bg = P.cut_background(nat, tol=9.0)
        self.assertTrue(fg[5:25, 6:14].sum() >= 8 * 20 - 4)
        self.assertFalse(fg[:4].any())
        self.assertFalse(fg[:, :4].any())

    def test_the_import_is_cell_for_cell_at_2x_with_an_outline(self):
        from . import pixelart as P
        nat, fg, big = self.sprite(4.0)
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "s.png"
            big.save(path)
            spec = {"pixelart": True, "flip": False, "frame": [2, 2], "mug": [8, 8], "eyes": [14, 14, 20, 14], "mouth": [17, 20]}
            im = P.styled(spec, path)
        self.assertEqual(im.large.shape, (160, 128))
        self.assertEqual(im.faces["normal"].shape, (48, 48))
        for kind in ("happy", "sad", "angry"):
            # no drawn or edited expressions: the neutral face is every expression slot's face
            self.assertTrue(np.array_equal(im.faces[kind], im.faces["normal"]), kind)
        self.assertEqual(len(im.palette), 16)
        # every native cell is a 2 x 2 block (no blurry resampling)
        blocks = im.large.reshape(80, 2, 64, 2)
        self.assertTrue((blocks == blocks[:, :1, :, :1]).all())
        # the outline is index 15 against the cut background
        self.assertIn(15, set(np.unique(im.large)))

    def test_a_real_expression_picture_is_used_when_the_owner_supplies_one(self):
        from . import pixelart as P
        nat, fg, big = self.sprite(4.0)
        alt = nat.copy()
        alt[18:22, 12:20] = (250, 60, 60)
        bigalt = Image.fromarray(alt.astype(np.uint8)).resize(big.size, Image.NEAREST)
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "x_v5.png"
            big.save(path)
            bigalt.save(Path(t) / "x_happy.png")
            spec = {"pixelart": True, "flip": False, "frame": [2, 2], "mug": [8, 8], "eyes": [14, 14, 20, 14]}
            im = P.styled(spec, path)
        self.assertTrue(np.array_equal(im.faces["sad"], im.faces["normal"]))
        self.assertFalse(np.array_equal(im.faces["happy"], im.faces["normal"]))
