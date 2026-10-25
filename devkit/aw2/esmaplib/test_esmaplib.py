"""Regression tests of the Emerald Sun map generator and its rules (run by `aw2dev test python`): the painting API, every committed text map equal to what its spec makes,
the invention rule ES01 (only the missions against Black Hole, at most two), every ES map lint-clean and within the unit caps. Needs the AW2 ROM for the lint ones."""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aw2 import cfg                                       # noqa: E402
from aw2.esmaplib import Canvas, load_spec, specs, ES_DIR, INF   # noqa: E402

HAVE = cfg.aw2_rom().exists()


class Paint(unittest.TestCase):
    def test_paths_are_straight_or_an_l(self):
        m = Canvas("t", 6, 6)
        self.assertEqual(m.path([(0, 0), (3, 0)]), [(0, 0), (1, 0), (2, 0), (3, 0)])
        self.assertEqual(m.path([(0, 0), (2, 2)]), [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)])

    def test_blobs_and_scatter_are_deterministic(self):
        a, b = Canvas("t", 12, 12), Canvas("t", 12, 12)
        for m in (a, b):
            m.blob("^", 6, 6, 4, 3, seed=5).scatter("f", (0, 0, 11, 11), 0.2, seed=9)
        self.assertEqual(a.rows(), b.rows())
        self.assertIn("^", "".join(a.rows()))

    def test_meander_is_one_connected_winding_line(self):
        m = Canvas("t", 30, 20)
        cells = m.meander("-", (0, 5), (29, 12), seed=3, amp=3)
        self.assertEqual(cells[0], (0, 5))
        self.assertEqual(cells[-1], (29, 12))
        self.assertTrue(all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip(cells, cells[1:])))
        self.assertGreater(sum(1 for a, b, c in zip(cells, cells[1:], cells[2:]) if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1])), 3)
        self.assertEqual(Canvas("t", 30, 20).meander("-", (0, 5), (29, 12), seed=3, amp=3), cells)

    def test_cluster_and_spread(self):
        m = Canvas("t", 30, 20)
        cells = m.cluster("^", 10, 10, 14, seed=1)
        self.assertTrue(10 <= len(cells) <= 14)
        placed = m.spread(1, {1: 4, 5: 3}, (2, 2, 12, 8), seed=2, gap=1)
        self.assertEqual(len(placed), 7)
        self.assertTrue(all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) >= 2 for i, a in enumerate(placed) for b in placed[i + 1:]))

    def test_text_has_header_units_and_rows(self):
        m = Canvas("t", 4, 3).header(armies=2, colours=(5, 3), objective=[1]).put("1", 0, 0).put("2", 3, 2)
        m.unit(1, INF, 1, 0, name="a").unit(2, INF, 2, 2, hold=True)
        t = m.text()
        self.assertIn("map t\narmies 2 3 5 3\n", t)
        self.assertIn("unit 1 1 1 0 name=a", t)
        self.assertIn("unit 2 1 2 2 hold", t)
        self.assertTrue(t.rstrip().endswith("..2"))

    def test_ascii_checks_the_size(self):
        m = Canvas("t", 4, 2).ascii(["1..c", "...2"])
        self.assertEqual(m.rows(), ["1..c", "...2"])
        with self.assertRaises(ValueError):
            Canvas("t", 4, 2).ascii(["1..", "...2"])

    def test_reserved_cells_stay_free(self):
        m = Canvas("t", 6, 3)
        m.reserve([(x, y) for x in range(5) for y in range(3)])
        placed = m.spread(1, {INF: 1}, (0, 0, 5, 2), seed=1, gap=0)
        self.assertEqual(placed[0][0], 5)

    def test_principles_while_drawing(self):
        sparse = Canvas("t", 15, 9).put("1", 0, 0).put("2", 14, 8)
        self.assertTrue(any(p.startswith("MD01") for p in sparse.principles()))
        sm = sparse.study()
        self.assertEqual((sm.g[0][0], sm.own[0][0], sm.own[8][14]), ("H", 1, 2))

    def test_off_the_map_is_refused(self):
        with self.assertRaises(ValueError):
            Canvas("t", 3, 3).put(".", 3, 0)
        with self.assertRaises(ValueError):
            Canvas("t", 3, 3).unit(1, INF, 0, 5)


class Committed(unittest.TestCase):
    def test_every_text_map_is_what_its_spec_makes(self):
        for p in specs():
            m = load_spec(p)
            f = ES_DIR / f"{m.name}.txt"
            self.assertTrue(f.exists(), f"{m.name}: no text map (aw2dev maps gen)")
            self.assertEqual(f.read_text(), m.text(), f"{m.name}: the text map differs from its spec (aw2dev maps gen)")

    def test_sixteen_maps_and_two_black_hole_missions(self):
        names = [load_spec(p).name for p in specs()]
        self.assertEqual(names, [f"es{n:02d}" for n in range(1, 17)])
        bh = [load_spec(p).name for p in specs() if load_spec(p).hdr["blackhole"]]
        self.assertEqual(bh, ["es09", "es13"])

    def test_the_maps_follow_the_design_principles(self):
        # (docs/dev/map-design.md: MD01..MD08; the lint fails them too, this keeps the specs honest without the ROM)
        for p in specs():
            m = load_spec(p)
            self.assertEqual(m.principles(), [], m.name)

    def test_mount_sol_and_its_eruption_ring(self):
        # M16's volcano (anchor (22,14), footprint x21..24, y12..15) sits in rock; the ring es_act4.rs erupts (19..26, 10..17) is open ground
        m = load_spec(ES_DIR / "spec" / "es16.py")
        self.assertEqual(m.get(22, 14), "V")
        ring = [(x, 10) for x in range(19, 27)] + [(x, 17) for x in range(19, 27)] + [(19, y) for y in range(11, 17)] + [(26, y) for y in range(11, 17)]
        self.assertTrue(all(m.get(x, y) not in "#V~" for x, y in ring))
        others = [load_spec(q) for q in specs() if q.stem != "es16"]
        self.assertFalse(any("V" in "".join(o.rows()) for o in others))

    def test_no_army_starts_over_the_cap(self):
        for p in specs():
            m = load_spec(p)
            for a in range(1, m.hdr["armies"] + 1):
                self.assertLessEqual(sum(1 for u in m.u if u["army"] == a), 40, f"{m.name} army {a}")


@unittest.skipUnless(HAVE, "needs the AW2 ROM")
class Lint(unittest.TestCase):
    def test_every_map_is_clean(self):
        from aw2.maplint import load, rules
        for m in load.es_maps():
            errs = [p for p in rules.lint(m) if p.level == "error"]
            self.assertEqual(errs, [], m.name)

    def test_inventions_need_the_blackhole_tag(self):
        from aw2.maplint import load, rules
        mappy, _, _ = load._five()
        rows = ["1" + "." * 9, "." * 10, "...S......", "." * 10, "." * 10, "." * 9 + "2"]      # a minicannon
        base = {"name": "t", "rows": rows, "armies": 2, "colours": [1, 2], "units": {}, "tab": 3, "wasteland": False}
        edge = mappy.sea_edges(load.rom_bytes())
        for tag in (False, True):
            meta = dict(base, blackhole=tag)
            m = load.MapData("t", "es", mappy.tiles(meta, edge), text=rows, meta=meta)
            got = {p.rule for p in rules.lint(m)}
            self.assertEqual("ES01" in got, not tag, f"blackhole={tag}: {got}")


if __name__ == "__main__":
    unittest.main()
