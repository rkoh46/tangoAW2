"""Tests of `aw2dev art repal` (docs/dev/art-repal.md): palette files round trip, the slot order is kept, luma and rgb pick their own nearest colour,
the transparent slot's position, a CO palette extract, and the CO importer's `match` hook. Run by `aw2dev test`."""
import tempfile
import tomllib
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from .. import cfg
from . import repal


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_gpl_round_trip(self):
        pal = [(0, 0, 0), (255, 255, 255), (12, 200, 7), (99, 1, 250)]
        repal.write_gpl(pal, self.tmp / "a.gpl")
        self.assertEqual(repal.read_gpl(self.tmp / "a.gpl"), pal)
        self.assertTrue((self.tmp / "a.gpl").read_text().startswith("GIMP Palette\n"))

    def test_pal_round_trip_gba_order(self):
        pal = [repal.from555(v) for v in (0x0000, 0x001F, 0x03E0, 0x7C00, 0x7FFF, 0x1234)]
        repal.write_pal(pal, self.tmp / "a.pal")
        b = (self.tmp / "a.pal").read_bytes()
        self.assertEqual(b[2:4], b"\x1f\x00")          # red is the low 5 bits, little-endian
        self.assertEqual(b[6:8], b"\x00\x7c")          # blue the high ones
        self.assertEqual(repal.read_pal(self.tmp / "a.pal"), pal)
        repal.write_gpl(pal, self.tmp / "b.gpl")
        self.assertEqual(repal.load_palette(self.tmp / "b.gpl"), pal)

    def test_png_palette_sources(self):
        idx = np.array([[0, 3], [1, 2]], np.uint8)
        pal = [(9, 9, 9), (200, 0, 0), (0, 200, 0), (0, 0, 200)]
        repal.save_png(idx, pal, self.tmp / "i.png")
        self.assertEqual(repal.load_palette(self.tmp / "i.png"), pal)
        rgb = Image.fromarray(np.array([[[5, 5, 5], [7, 7, 7]], [[5, 5, 5], [1, 2, 3]]], np.uint8))
        rgb.save(self.tmp / "r.png")
        self.assertEqual(repal.load_palette(self.tmp / "r.png"), [(5, 5, 5), (7, 7, 7), (1, 2, 3)])


class Apply(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_luma_and_rgb_pick_their_own_nearest(self):
        pal = [(100, 100, 140), (100, 115, 100)]        # off in blue by 40 / off in green by 15
        px = np.array([[100, 100, 100]])
        self.assertEqual(int(repal.nearest(px, pal, repal.weights("luma"))[0]), 0)    # 11 * 40 < 59 * 15
        self.assertEqual(int(repal.nearest(px, pal, repal.weights("rgb"))[0]), 1)     # 15 < 40
        self.assertEqual(repal.weights("3,2,1"), (3, 2, 1))
        with self.assertRaises(ValueError):
            repal.weights("1,2")

    def test_tie_goes_to_the_lower_slot(self):
        pal = [(0, 0, 0), (10, 10, 10), (30, 30, 30)]
        self.assertEqual(int(repal.nearest(np.array([[20, 20, 20]]), pal)[0]), 1)

    def test_slot_order_is_kept(self):
        pal = [(0, 0, 0), (250, 250, 250), (0, 0, 255), (255, 0, 0), (0, 255, 0), (1, 1, 1)]     # deliberately not sorted, slot 5 unused
        img = Image.fromarray(np.array([[[240, 10, 10, 255], [10, 240, 10, 255], [10, 10, 240, 255], [255, 255, 255, 255]]], np.uint8), "RGBA")
        idx = repal.apply(img, pal)
        self.assertEqual(idx.tolist(), [[3, 4, 2, 1]])
        out = repal.save_png(idx, pal, self.tmp / "o.png")
        back = Image.open(out)
        flat = back.getpalette()
        self.assertEqual([tuple(flat[3 * i:3 * i + 3]) for i in range(len(pal))], pal)
        self.assertEqual(np.array(back).tolist(), [[3, 4, 2, 1]])

    def test_alpha_slot_position(self):
        pal = [(0, 0, 0), (200, 0, 0), (0, 0, 0)]       # slot 0 and slot 2 the same black: only the reserved one is skipped
        img = Image.fromarray(np.array([[[0, 0, 0, 255], [200, 0, 0, 255], [9, 9, 9, 0]]], np.uint8), "RGBA")
        first = repal.apply(img, pal)
        self.assertEqual(first.tolist(), [[2, 1, 0]])
        last = repal.apply(img, pal, alpha_last=True)
        self.assertEqual(last.tolist(), [[0, 1, 2]])
        self.assertEqual(Image.open(repal.save_png(last, pal, self.tmp / "l.png", tslot=2)).info.get("transparency"), 2)
        with self.assertRaises(ValueError):
            repal.apply(img, pal, opaque=True)

    def test_keep_index_swaps_the_palette_only(self):
        idx = np.array([[0, 1, 2, 1]], np.uint8)
        src = repal.indexed_png(idx, [(0, 0, 0), (1, 1, 1), (2, 2, 2)])
        self.assertEqual(repal.apply(src, [(0, 0, 0), (255, 0, 0), (0, 255, 0)], keep_index=True).tolist(), idx.tolist())
        with self.assertRaises(ValueError):
            repal.apply(src, [(0, 0, 0), (9, 9, 9)], keep_index=True)


class Kit(unittest.TestCase):
    def test_co_palette_extract(self):
        pal = repal.load_palette("co:klaus")
        flat = Image.open(cfg.REPO / "tango-gamesupport-aw2" / "art" / "cos" / "klaus" / "large.png").getpalette()
        self.assertEqual(len(pal), 16)
        self.assertEqual(pal, [tuple(flat[3 * i:3 * i + 3]) for i in range(16)])
        tmp = Path(tempfile.mkdtemp())
        repal.write_palette(pal, tmp / "k.gpl")
        self.assertEqual(repal.read_gpl(tmp / "k.gpl"), pal)
        # Klaus's own art put back on his own palette keeps every index
        art = Image.open(cfg.REPO / "tango-gamesupport-aw2" / "art" / "cos" / "klaus" / "large.png")
        self.assertTrue(np.array_equal(repal.apply(art, pal, keep_index=True), np.array(art)))

    def test_army_rows_from_the_rom(self):
        if not cfg.aw2_rom().exists():
            self.skipTest("no AW2 ROM")
        rows = [repal.load_palette(f"army:{a}") for a in repal.ARMIES]
        self.assertTrue(all(len(r) == 16 for r in rows))
        self.assertEqual(len({tuple(r[2:8]) for r in rows}), 5)          # five different army ramps

    def test_importer_match_hook(self):
        from ..colib import pixelart as P
        nat = np.array([[[100, 100, 100]]], float)
        fg = np.ones((1, 1), bool)
        pal = [(100, 100, 140), (100, 115, 100)]
        self.assertEqual(int(P.quantise(nat, fg, pal, "luma")[0, 0]), 1)       # indexes from 1: slot 0 is transparent
        self.assertEqual(int(P.quantise(nat, fg, pal, "rgb")[0, 0]), 2)
        self.assertIn(int(P.quantise(nat, fg, pal)[0, 0]), (1, 2))              # no `match`: the Lab rule (unchanged callers)
        # the approved COs pin the Lab rule their art was made with (luma shifted their hues: docs/dev/art-repal.md)
        for co in ("klaus", "aurelia", "cassius", "livia"):
            spec = tomllib.loads((cfg.REPO / "art-src" / "cos" / f"{co}_v5.toml").read_text())
            self.assertEqual(spec.get("match"), "lab", co)

    def test_command_registered(self):
        import argparse
        from ..commands import art
        ap = argparse.ArgumentParser()
        art.register(ap.add_subparsers())
        a = ap.parse_args(["art", "repal", "apply", "--palette", "co:klaus", "x.png", "-o", "d"])
        self.assertEqual((a.weights, a.dither, a.alpha_last), ("luma", "none", False))


if __name__ == "__main__":
    unittest.main()
