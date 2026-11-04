"""Tests for `aw2dev gfx audit` (no ROM, no emulator): the detectors on made-up pictures and video dumps, the report, the exit code, `--reuse`."""
import json, struct, tempfile, unittest
from argparse import Namespace
from pathlib import Path

import numpy as np
from PIL import Image

from .gfxlib.audit import cli, detectors, runner


def png(path, fn):
    a = np.zeros((160, 240, 3), dtype=np.uint8)
    fn(a)
    Image.fromarray(a).save(path)


def healthy(a):
    for y in range(160):
        a[y, :, 0] = 40 + y
        a[y, :, 1] = 90 + (np.arange(240) // 3)
        a[y, :, 2] = 60 + ((np.arange(240) + y) % 50)


def striped(a):
    healthy(a)
    a[40:60, 100:140] = np.where((np.arange(40) % 2 == 0)[None, :, None], 255, 0)


def black_block(a):
    healthy(a)
    a[48:80, 64:96] = 0


def dump(path, grey_bank=None, zero_oam=False, obj_cost=False, layer=1):
    vram = bytearray(0x18000)
    pal = bytearray(0x400)
    oam = bytearray(0x400)
    for k in range(128):
        struct.pack_into("<HHH", oam, 8 * k, 0x0200, 0, 0)      # disabled
    io = bytearray(0x60)
    struct.pack_into("<H", io, 0, 0x1000 | (0x100 << layer))      # mode 0, the layer and OBJ on
    struct.pack_into("<H", io, 8 + 2 * layer, 4 << 8)           # the layer: char base 0, screen block 4 (0x2000)
    vram[32:64] = bytes([0x11] * 32)                            # BG tile 1 draws colour 1
    vram[0x10000:0x10020] = bytes([0x11] * 32)                  # OBJ tile 0 draws colour 1
    for k in range(32 * 32):
        struct.pack_into("<H", vram, 0x2000 + 2 * k, 1 | ((grey_bank if grey_bank is not None else 9) << 12))
    for b in range(16):
        for i in range(1, 16):
            if b == grey_bank:
                v = (i * 2) | (i * 2) << 5 | (i * 2) << 10
            else:
                v = (i * 2) | ((i * 3 + b) % 32) << 5 | ((i * 7) % 32) << 10
            struct.pack_into("<H", pal, 2 * (16 * b + i), v)
    if zero_oam:
        struct.pack_into("<HHH", oam, 0, 0, 0, 0)
    if obj_cost:
        for k in range(40):                                     # 40 sprites of 32 x 32 on the same rows: 1280 cycles on a line
            struct.pack_into("<HHH", oam, 8 * k, 20, 0x8000 | (k * 5), 0)
    Path(path).write_bytes(bytes(vram) + bytes(pal) + bytes(oam) + bytes(io))


def scene(out, mode, name, look, shots):
    d = Path(out) / mode / name / look
    d.mkdir(parents=True, exist_ok=True)
    man = {"mode": mode, "scene": name, "look": look, "shots": [], "facts": [], "notes": [], "error": None}
    for sname, fn, tags, dmp in shots:
        png(d / f"{sname}.png", fn)
        sh = {"name": sname, "png": f"{sname}.png", "vram": None, "tags": tags, "size": [240, 160], "frame": 1}
        if dmp is not None:
            dump(d / f"{sname}.vram", **dmp)
            sh["vram"] = f"{sname}.vram"
        man["shots"].append(sh)
    (d / "manifest.json").write_text(json.dumps(man))
    return d


class Detectors(unittest.TestCase):
    def shot(self, d, name, tags=(), look="aw2"):
        m = json.loads((d / "manifest.json").read_text())["shots"]
        sh = next(s for s in m if s["name"] == name)
        return detectors.Shot("t", "s", look, name, d / sh["png"], d / sh["vram"] if sh["vram"] else None, tags, sh)

    def test_each_detector_flags_its_bug_and_passes_a_healthy_picture(self):
        with tempfile.TemporaryDirectory() as t:
            d = scene(t, "t", "s", "aw2", [("ok", healthy, ["map"], {}), ("stripes", striped, ["map"], None), ("black", black_block, ["map"], None),
                                           ("grey", healthy, ["map"], {"grey_bank": 9}), ("zero", healthy, ["menu"], {"zero_oam": True}),
                                           ("busy", healthy, ["menu"], {"obj_cost": True})])
            names = lambda n, tags=(): {f["detector"] for f in detectors.judge(self.shot(d, n, tags))}
            self.assertEqual(names("ok", ["map"]), set())
            self.assertIn("stripes", names("stripes", ["map"]))
            self.assertIn("dark", names("black", ["map"]))
            self.assertIn("palette", names("grey", ["map"]))
            self.assertIn("sprites", names("zero", ["map"]))
            self.assertIn("sprites", names("busy", ["map"]))
            png(d / "blank.png", lambda a: None)
            self.assertIn("blank", {f["detector"] for f in detectors.judge(detectors.Shot("t", "s", "aw2", "blank", d / "blank.png", None, [], {}))})

    def test_washed_out_faces_bank_9_while_a_box_is_up(self):
        """A dialogue box (a near-white band at the screen's top) with BG palette bank 9 turned into one blue ramp is flagged; real face colours are not."""
        def boxed(a):
            a[:] = (30, 120, 60)
            a[2:46] = (250, 240, 240)
        with tempfile.TemporaryDirectory() as t:
            d = scene(t, "t", "s", "aw2", [("ok", boxed, ["dialogue"], {}), ("washed", boxed, ["dialogue"], {})])
            raw = bytearray((d / "washed.vram").read_bytes())
            for i in range(1, 16):                                  # bank 9: fifteen blues
                struct.pack_into("<H", raw, 0x18000 + 2 * (16 * 9 + i), (8 + i) | (14 + i) << 5 | (24 + i % 6) << 10)
            (d / "washed.vram").write_bytes(bytes(raw))
            raw = bytearray((d / "ok.vram").read_bytes())
            for i in range(1, 16):                                  # bank 9: skin, hair, eyes, clothes (hues all over)
                struct.pack_into("<H", raw, 0x18000 + 2 * (16 * 9 + i), ((i * 11) % 32) | ((i * 5) % 32) << 5 | ((i * 17) % 32) << 10)
            (d / "ok.vram").write_bytes(bytes(raw))
            self.assertEqual([f["detector"] for f in detectors.judge(self.shot(d, "washed", ["dialogue"]), ["palette"])], ["palette"])
            self.assertEqual(detectors.judge(self.shot(d, "ok", ["dialogue"]), ["palette"]), [])

    def test_a_fade_is_not_a_blank_frame(self):
        with tempfile.TemporaryDirectory() as t:
            d = scene(t, "t", "s", "aw2", [("b", lambda a: None, ["fade"], None)])
            self.assertEqual(detectors.judge(self.shot(d, "b", ["fade"])), [])


class Command(unittest.TestCase):
    def args(self, out, **kw):
        base = dict(modes=None, scenes=None, looks=None, list=False, jobs=1, out=None, reuse=str(out), only=None, binary_dir=None, timeout=10, strict=False, no_sheets=False)
        base.update(kw)
        return Namespace(**base)

    def test_findings_give_exit_1_a_report_and_sheets_and_a_clean_run_exits_0(self):
        with tempfile.TemporaryDirectory() as t:
            scene(t, "menus", "clean", "aw2", [("a", healthy, ["menu"], {})])
            self.assertEqual(cli.audit(self.args(t)), 0)
            scene(t, "versus", "bad", "ds_flat", [("stripes", striped, ["map"], None)])
            self.assertEqual(cli.audit(self.args(t)), 1)
            rep = json.loads((Path(t) / "report.json").read_text())
            self.assertEqual([f["detector"] for f in rep["findings"]], ["stripes"])
            self.assertTrue((Path(t) / "report.md").read_text().count("stripes") >= 1)
            self.assertTrue(rep["sheets"]["versus/ds_flat"] and Path(rep["sheets"]["versus/ds_flat"][0]).exists())
            self.assertEqual(cli.audit(self.args(t, modes="menus")), 0)           # (only the clean mode)
            self.assertEqual(cli.audit(self.args(t, only="blank")), 0)            # (only a detector that finds nothing)

    def test_a_scene_that_stopped_and_a_failed_fact_are_findings(self):
        with tempfile.TemporaryDirectory() as t:
            d = scene(t, "versus", "x", "aw2", [("a", healthy, ["menu"], {})])
            m = json.loads((d / "manifest.json").read_text())
            m["error"] = "Traceback\nNavError: the Teams screen did not open"
            m["facts"] = [{"ok": False, "msg": "the terrain panel draws Black Hole's HQ"}]
            (d / "manifest.json").write_text(json.dumps(m))
            self.assertEqual(cli.audit(self.args(t, no_sheets=True)), 1)
            kinds = {f["detector"] for f in json.loads((Path(t) / "report.json").read_text())["findings"]}
            self.assertEqual(kinds, {"scene", "facts"})

    def test_the_scene_list_names_every_mode_the_audit_covers(self):
        modes = {s["mode"] for s in runner.scene_list()}
        for want in ("menus", "versus", "war_room", "survival", "aw2_campaign", "ds_campaign", "bh_campaign", "bh2_campaign", "sn_campaign", "gauntlet", "cos", "online"):
            self.assertIn(want, modes)
        looks = {l for s in runner.scene_list() for l in s["looks"]}
        self.assertEqual(looks, {"aw2_nopack", "aw2", "ds_tilt", "ds_flat"})


if __name__ == "__main__":
    unittest.main()
