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

    def halo_figure(self):
        nat = np.zeros((30, 20, 3)) + 255                 # white background
        nat[6:24, 6:14] = (30, 24, 34)                    # a dark figure
        nat[5, 6:14] = (200, 200, 198)                    # a light grey halo cell row above it, one blended cell on its left side
        nat[6:24, 5] = (120, 118, 116)
        nat[10:12, 8:10] = (250, 250, 250)                # an eye white inside, ringed by dark cells
        nat[18:20, 6:8] = (245, 245, 243)                 # a light cell on the figure's edge column, behind the halo: not reachable once the dark ring exists
        nat[18:20, 5] = (30, 24, 34)
        return nat

    def test_a_white_halo_goes_and_the_figures_own_light_cells_stay(self):
        from . import pixelart as P
        nat = self.halo_figure()
        plain, _ = P.cut_background(nat, tol=9.0)
        self.assertTrue(plain[5, 6:14].all() and plain[6:18, 5].all())        # without the option the halo is kept
        fg, _ = P.cut_background(nat, tol=9.0, fringe_mode="light", light_l=45.0)
        self.assertFalse(fg[5, 6:14].any())
        self.assertFalse(fg[6:18, 5].any())
        self.assertTrue(fg[10:12, 8:10].all())                                # the eye white is enclosed by dark: never reached
        self.assertTrue(fg[6:24, 6:14].sum() >= 8 * 18 - 4 and fg[7:23, 8:13].all())

    def test_the_halo_lint_catches_a_light_edge_pixel_and_honours_the_protect_list(self):
        pal = [(0, 0, 0), (200, 200, 198), (30, 24, 34)] + [(30, 24, 34)] * 12 + [(0, 0, 0)]
        a = np.zeros((10, 10), np.uint8)
        a[2:8, 2:8] = 2
        a[1, 2:8] = a[8, 2:8] = a[2:8, 1] = a[2:8, 8] = 15
        a[2, 4] = 1                                   # a light pixel right inside the outline
        pics = {"large": a, "face_normal": a.copy()}
        pics["face_normal"][2, 4] = 2
        old = I._framing
        try:
            I._framing = lambda co: {"fringe": "light"}
            self.assertTrue(any("white halo" in b for b in I.fringe_problems("x", pics, pal)))
            I._framing = lambda co: {"fringe": "light", "edge_protect": [[4, 2]]}
            self.assertEqual(I.fringe_problems("x", pics, pal), [])
            I._framing = lambda co: {}
            self.assertEqual(I.fringe_problems("x", pics, pal), [])
        finally:
            I._framing = old

    def ramp_picture(self):
        rng = np.random.default_rng(2)
        tones = [(4, 4, 4), (20, 20, 20), (30, 30, 30), (44, 44, 46), (60, 60, 60)]
        counts = [3000, 600, 200, 80, 40]                      # near-black dominates; the highlights are few
        px = np.concatenate([np.tile(t, (n, 1)) for t, n in zip(tones, counts)]).astype(float)
        cols = [(255, 214, 173), (247, 247, 247), (148, 25, 33), (123, 123, 132), (214, 173, 107)]
        extra = [(165, 99, 66), (107, 74, 49), (90, 8, 16), (189, 140, 107), (230, 189, 148), (82, 100, 160)]
        px = np.concatenate([px, np.array([c for c in cols + extra for _ in range(300)], float)])
        return px, cols

    def test_a_dark_ramp_keeps_the_uniforms_shades(self):
        from . import pixelart as P
        px, cols = self.ramp_picture()
        w = np.ones(len(px))
        pal = P.palette_for(px, w, outline=(0, 0, 0), protect=[np.array(c, float) for c in cols], dark_k=5)
        dark = [c for c in pal[:14] if max(c) < 70]
        self.assertGreaterEqual(len(set(dark)), 4, dark)

    def test_the_ramp_lint_counts_the_shades_of_the_uniform(self):
        px, _ = self.ramp_picture()
        src = px[:3920].reshape(40, 98, 3)
        pal = [(0, 0, 0)] * 16
        out = np.ones((40, 98), np.uint8)                        # one entry for the whole uniform: merged
        have, got = I.ramp_shades(src, out, pal)
        self.assertGreaterEqual(have, 4)
        self.assertEqual(got, 1)
        out2 = np.digitize(src[..., 0], [10, 25, 37, 52]).astype(np.uint8) + 1
        self.assertEqual(I.ramp_shades(src, out2, pal)[1], 5)

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


class Illustration(unittest.TestCase):
    """The illustration route (`illustration.py`, Asuka's picture): a clean drawing on white is cut from its background, downscaled and quantised to one palette, never redrawn."""

    @staticmethod
    def drawing(w=360, h=560):
        im = np.full((h, w, 3), 255, np.uint8)
        im[40:520, 100:260] = (30, 26, 28)               # black cloth
        im[60:150, 120:240] = (245, 205, 175)            # a head
        im[90:100, 150:162] = (250, 248, 244)            # an off-white eye white inside the face: stays
        im[200:300, 100:130] = 255                       # a gap of pure white enclosed by cloth (between an arm and the body)
        im[200:300, 100:104] = (30, 26, 28)
        im[380:420, 60:100] = (170, 40, 40)              # a red cuff at the side
        return im

    def spec(self, **kw):
        return {"illustration": True, "scale": 0.25, "frame": [30, 20], "mug": [100, 50, 160], "eyes": [150, 100, 200, 100], **kw}

    def run_import(self, im, **kw):
        from . import illustration
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "d.png"
            Image.fromarray(im).save(p)
            return illustration.styled(self.spec(**kw), p)

    def test_background_and_enclosed_white_gaps_go_but_off_white_detail_stays(self):
        from . import illustration as L
        im = self.drawing().astype(np.float32)
        fg, bg = L.cut_background(im)
        self.assertFalse(fg[5, 5])
        self.assertTrue(fg[300, 200])
        self.assertFalse(fg[250, 115], "the enclosed pure-white gap is background")
        self.assertTrue(fg[95, 155], "the off-white eye white inside the face stays")
        self.assertTrue(fg[60:150, 120:240].all())

    def test_the_sizes_the_palette_and_the_outline(self):
        im = self.run_import(self.drawing())
        self.assertEqual(im.large.shape, (160, 128))
        self.assertEqual(im.faces["normal"].shape, (48, 48))
        self.assertEqual(im.mini.shape, (16, 48))
        self.assertEqual(im.hud.shape, (16, 32))
        self.assertEqual(len(im.palette), 16)
        for kind in ("happy", "sad", "angry"):
            self.assertTrue(np.array_equal(im.faces[kind], im.faces["normal"]), "no drawn expressions: the neutral face")
        # an outline round the silhouette, and no coloured pixel against transparency
        self.assertIn(15, set(np.unique(im.large)))
        t = im.large == 0
        near = np.zeros_like(t)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            near |= I.shift(t, dx, dy)
        self.assertFalse((near & ~t & (im.large != 15)).any())

    def test_the_white_halo_does_not_bleed_into_the_figures_colour(self):
        d = self.drawing()
        d[90:100, 150:162] = (245, 205, 175)                  # (no off-white eye white in this one)
        im = self.run_import(d)
        cols = [im.palette[v] for v in np.unique(im.large) if v]
        self.assertFalse(any(min(c) > 230 for c in cols if c != (0, 0, 0)), f"no white in a figure with no white on it ({cols})")

    def test_it_is_deterministic_and_flip_mirrors(self):
        a, b = self.run_import(self.drawing()), self.run_import(self.drawing())
        self.assertTrue(np.array_equal(a.large, b.large) and a.palette == b.palette)
        one = self.drawing()
        one[200:230, 240:260] = (40, 200, 60)                # a mark on the right edge
        r = self.run_import(one)
        m = self.run_import(one[:, ::-1].copy(), flip=True)
        # flipping a mirrored picture gives the original back (the whole framing is mirrored with it)
        self.assertEqual(r.large.shape, m.large.shape)
        self.assertGreater(np.mean(r.large == m.large), 0.9)

    def test_asuka_is_what_her_picture_gives_and_passes_the_lint(self):
        cos, _ = data.load_all()
        co = "asuka"
        self.assertEqual(I.lint_art(co), [])
        im = I.import_co({"source": cos[co]["portrait"]["source"]})
        I.all_expressions(im, im.spec)
        old, _pal = I.read_art(co)
        for name, idx in I.pictures(im).items():
            self.assertTrue(np.array_equal(old[name], idx), f"{co} {name}: `aw2dev co portrait import` and commit")

    def test_asuka_is_a_black_hole_co_with_her_pairs_and_a_name_graphic(self):
        cos, tags = data.load_all()
        a = cos["asuka"]
        self.assertEqual((a["army"], a["stars"]), ("black_hole", {"cop": 4, "scop": 8}))        # the normal cost
        self.assertEqual((a["luck"], a["bad_luck"]), ([20, 20, 20], [0, 0, 0]))                # Nell's day-to-day luck, no bad luck
        partners = {(p["b"] if p["a"] == "asuka" else p["a"]) for p in tags["pair"] if "asuka" in (p["a"], p["b"])}
        self.assertTrue({"ds:vonbolt", "aw2:hawke", "aw2:sturm"} <= partners, partners)
        g = namefont.name_grid("Asuka")
        self.assertEqual(g.shape, (16, 48))
        self.assertTrue((g[:, 0] == 0).all() and (g[:, 47] == 0).all())


class AriaArt(unittest.TestCase):
    """Aria (cos/aria.toml, art-src/cos/aria_v1.*): the owner's pixel art on a baked-in checkerboard, a direct import."""

    def test_aria_is_what_her_picture_gives_and_passes_the_lint(self):
        cos, _ = data.load_all()
        co = "aria"
        self.assertEqual(I.lint_art(co), [])
        im = I.import_co({"source": cos[co]["portrait"]["source"], **{k: v for k, v in cos[co]["portrait"].items() if k != "source"}})
        I.all_expressions(im, im.spec)
        old, _pal = I.read_art(co)
        for name, idx in I.pictures(im).items():
            self.assertTrue(np.array_equal(old[name], idx), f"{co} {name}: `aw2dev co portrait import` and commit")
        pics, pal = I.read_art(co)
        self.assertEqual(I.lightness_problems(co, pics, pal), [])
        self.assertEqual(I.fringe_problems(co, pics, pal), [])

    def test_the_checkerboard_is_gone_and_her_colours_are_kept(self):
        pics, pal = I.read_art("aria")
        pal = [tuple(c) for c in pal]
        large = pics["large"]
        lab = I.to_lab(np.array(pal, float))
        # no pixel but the outline is a light, colourless checkerboard grey or white next to transparency (the lint's rule), and the blue irises, the eye whites, two skin tones and the white shirt are in the palette
        blues = [i for i, c in enumerate(pal) if c[2] > c[0] + 40]
        self.assertTrue(blues, "a blue entry for the irises")
        self.assertTrue(any(np.isin(pics["face_normal"], blues).ravel()), "blue in the face")
        whites = [i for i, c in enumerate(pal) if min(c) > 235]
        self.assertTrue(whites, "an eye-white / shirt-white entry")
        skins = [i for i, c in enumerate(pal) if c[0] > 200 and 120 < c[1] < 220 and 80 < c[2] < 190 and c[0] - c[2] > 30]
        self.assertGreaterEqual(len(skins), 2, "two or more skin tones")
        oranges = [i for i, c in enumerate(pal) if c[0] > 180 and 70 < c[1] < 140 and c[2] < 60]
        used = {i for i in oranges if (large == i).sum() > 100}
        self.assertGreaterEqual(len(used), 3, "the coat keeps a ramp of at least three oranges")

    def test_the_checker_flatten_makes_the_background_one_colour(self):
        from . import pixelart as P
        img = np.full((60, 60, 3), 255, np.uint8)
        img[::2, ::2] = 233
        img[20:40, 20:40] = (200, 100, 30)
        img[28:32, 28:32] = (255, 255, 255)          # a white spot inside the figure: never reached
        out = P.flatten_checker(img)
        self.assertTrue((out[0:10, 0:10] == 255).all())
        self.assertTrue((out[20:40, 20:40][:8, :8] == (200, 100, 30)).all())
        self.assertTrue((out[28:32, 28:32] == 255).all())
        # an enclosed pocket of checker is flooded from its seed
        img2 = img.copy()
        img2[10:18, 10:18] = (200, 100, 30)
        img2[12:16, 12:16] = 233                      # an enclosed pocket
        self.assertTrue((P.flatten_checker(img2)[12:16, 12:16] == 233).all())
        self.assertTrue((P.flatten_checker(img2, seeds=[[13, 13]])[12:16, 12:16] == 255).all())

    def test_aria_is_an_orange_star_co_with_only_a_super_power(self):
        cos, tags = data.load_all()
        a = cos["aria"]
        self.assertEqual((a["army"], a["stars"], a["hq"]), ("orange_star", {"cop": 0, "scop": 7}, "default"))
        self.assertEqual(a["d2d"]["vengeance"], {"hp": 8, "percent": [25, 30, 35, 40, 45, 50, 75, 85]})
        self.assertEqual(a["d2d"]["mods"], [])
        self.assertEqual(a["scop"]["mods"], [{"units": "all", "attack": 20}])
        self.assertEqual(a["scop"]["heal"], 3)
        self.assertNotIn("movement", a)
        self.assertNotIn("quote", a["cop"], "no CO Power, no quote set for it")
        self.assertEqual([m for m in data.problems(cos, tags) if m.startswith("aria")], [])
        pair = next(p for p in tags["pair"] if "aria" in (p["a"], p["b"]))
        self.assertEqual((pair["name"], pair["compat"], pair["stars"]), ("Sisters' Accord", 115, 2))
        bad = copy.deepcopy(a)
        del bad["scop"]
        self.assertIn("aria: missing scop", " ".join(data.problems({**cos, "aria": bad}, tags)))
        g = namefont.name_grid("Aria")
        self.assertEqual(g.shape, (16, 48))


class Verify(unittest.TestCase):
    """`co verify sonja`: the comparison finds any difference between two observation files."""

    def test_diff_finds_changes_additions_and_losses(self):
        from . import verify_sonja as verify
        ref = {"co_row": "a1", "texts": {"1": "aa", "2": "bb"}, "screens": {"x": "h1"}}
        self.assertEqual(verify.diff(ref, json_copy(ref)), [])
        now = json_copy(ref)
        now["texts"]["2"] = "bc"
        now["screens"]["y"] = "h2"
        del now["co_row"]
        out = " ".join(verify.diff(ref, now))
        for want in ("/texts/2", "/screens/y: only in this build", "/co_row: only in reference"):
            self.assertIn(want, out)


def json_copy(x):
    import json
    return json.loads(json.dumps(x))


class OutlineLint(unittest.TestCase):
    """The outline checks of an illustration import (importer.outline_problems): continuity in 8-connectivity, one pixel wide, no blending into the figure's darks."""

    @staticmethod
    def figure():
        a = np.zeros((16, 16), np.uint8)
        a[3:13, 3:13] = 3
        ring = np.zeros_like(a, bool)
        ring[2:14, 2:14] = True
        ring[3:13, 3:13] = False
        a[ring] = 15
        pal = [(0, 0, 0)] + [(200, 180, 170)] * 14 + [(32, 24, 32)]
        pal[3] = (90, 70, 60)
        return a, pal

    def test_a_clean_ring_passes(self):
        a, pal = self.figure()
        self.assertEqual(I.outline_problems("large", a, pal), [])

    def test_a_missing_corner_is_a_gap(self):
        a, pal = self.figure()
        a[2, 2] = 0
        a[3, 2] = 0                       # a hole in the ring: the figure's corner pixel now touches the empty side
        self.assertTrue(any("gaps" in b for b in I.outline_problems("large", a, pal)))

    def test_a_second_layer_is_too_wide(self):
        a, pal = self.figure()
        a[1, 1:15] = 15
        a[2, 1] = 15
        self.assertTrue(any("one pixel" in b for b in I.outline_problems("large", a, pal)))

    def test_a_dark_that_blends_into_the_outline_is_caught(self):
        a, pal = self.figure()
        pal[3] = (34, 26, 34)
        self.assertTrue(any("blends in" in b for b in I.outline_problems("large", a, pal)))

    def test_the_lightness_lint_catches_a_white_gone_dark(self):
        pics, pal = I.read_art("asuka")
        self.assertEqual(I.lightness_problems("asuka", pics, pal), [])
        pal = [tuple(c) for c in pal]
        pal[1] = (16, 16, 16)                    # the eye whites' entry (the lightest) darkened
        self.assertTrue(any("darker than" in b for b in I.lightness_problems("asuka", pics, pal)))

    def test_asuka_has_a_continuous_outline_apart_from_kanbeis_standard(self):
        self.assertEqual(I.lint_art("asuka"), [])
