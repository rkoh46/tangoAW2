"""aw2dev worldmap's tests (no ROM): python -m unittest aw2.worldmaplib.test_worldmap (from devkit/)."""
import unittest

import numpy as np

from . import binfmt, convert, tool


class WorldMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.map, cls.cfg = tool.load("bh2")

    def test_check_is_clean(self):
        # budgets, coverage of the land, flag places, and the checked-in file is what the conversion makes now
        self.assertEqual(tool.check("bh2"), [])

    def test_budgets(self):
        for label, used, limit in tool.budgets(self.map):
            self.assertLessEqual(used, limit, label)

    def test_conversion_is_stable(self):
        a = binfmt.pack(convert.convert(tool.config_path("bh2")))
        b = binfmt.pack(convert.convert(tool.config_path("bh2")))
        self.assertEqual(a, b)

    def test_pack_roundtrip(self):
        m = binfmt.unpack(binfmt.pack(self.map), self.map.region_names)
        self.assertTrue((m.cells == self.map.cells).all() and (m.mask == self.map.mask).all() and (m.tiles == self.map.tiles).all())
        self.assertEqual(m.slots, self.map.slots)

    def test_conquest_changes_only_the_nation(self):
        base = convert.render(self.map)
        os_ = convert.render(self.map, (1,))
        diff = (base != os_).any(-1)
        # the pixels that changed lie in Orange Star (a few of the coast rim may sit in a palette shared with the sea)
        inside = (self.map.mask[diff] == 1).mean()
        self.assertGreater(inside, 0.95)
        self.assertGreater(diff.sum(), 5000)

    def test_render_is_close_to_the_picture(self):
        ref, _ = convert.resample(self.cfg)
        err = ((convert.render(self.map).astype(float) - ref) ** 2).mean()
        self.assertLess(err, 40.0)       # PSNR above ~32 dB

    def test_three_flag_places_per_need(self):
        self.assertGreaterEqual(len(self.map.slots), 31)
        for r, x, y in self.map.slots:
            self.assertEqual(self.map.mask[y, x], r)


if __name__ == "__main__":
    unittest.main()
