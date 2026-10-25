"""Recolour-based COs in `aw2dev co portrait import` (colib/recolour.py): the import and `--check` with no CO names skip the picture step for Clone Andy (no
`portrait.source`, which raised a KeyError) and check his recolour instead. Run by `aw2dev test`."""
import argparse
import copy
import unittest
from .. import cfg
from . import data, recolour, roms


def donor(body_indexes=range(16)):
    body = [[i for i in body_indexes] for _ in range(4)]
    pal = [[0x0400 + i for i in range(16)] for _ in range(8)]
    return roms.Portrait("ds", "Andy", body, [], [], [], pal)


class Recolour(unittest.TestCase):
    def setUp(self):
        cos, _ = data.load_all()
        self.c = copy.deepcopy(cos["cloneandy"])

    def test_selection_has_only_cos_with_a_picture(self):
        from ..commands import co
        sel, cos = co._cos([])
        self.assertIn("klaus", sel)
        for k in ("cloneandy", "crumb", "varro"):
            self.assertIn(k, cos)
            self.assertNotIn(k, sel)
        self.assertEqual(list(co._cos(["klaus"])[0]), ["klaus"])

    def test_import_check_without_names_does_not_crash(self):
        from ..commands import co
        self.assertEqual(co.pimport(argparse.Namespace(co=[], check=True, pixelart=False)), 0)
        self.assertEqual(co.pimport(argparse.Namespace(co=["cloneandy"], check=True, pixelart=False)), 0)

    def test_the_recolour_output_on_a_donor(self):
        probs, summary = recolour.check("cloneandy", self.c, donor())
        self.assertEqual(probs, [])
        tab = recolour.table(self.c)
        out = recolour.apply(donor().palettes, tab)
        self.assertEqual(out[3][2], 0xBE >> 3 | (0xD7 >> 3) << 5 | (0xFF >> 3) << 10)       # "BED7FF" the way ds_co_art::Recolour::parse converts it, in every scheme
        self.assertEqual(out[5][7], 0x0407)                                               # hair: Andy's own
        # an entry the figure never draws, and an entry that is the donor's own colour, are caught
        probs, _ = recolour.check("cloneandy", self.c, donor(i for i in range(16) if i != 9))
        self.assertIn("entry 9 is not drawn", " ".join(probs))
        d = donor()
        for p in d.palettes:
            p[12] = tab[12]
        self.assertIn("entry 12", " ".join(recolour.check("cloneandy", self.c, d)[0]))
        bad = copy.deepcopy(self.c)
        bad["portrait"]["recolour"]["16"] = "FFFFFF"
        self.assertTrue(recolour.check("cloneandy", bad, donor())[0])

    def test_clone_andy_on_the_real_andy(self):
        if not cfg.ds_rom().exists():
            self.skipTest("no Dual Strike ROM")
        self.assertEqual(recolour.check("cloneandy", self.c)[0], [])


if __name__ == "__main__":
    unittest.main()
