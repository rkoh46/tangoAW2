"""Tests of the online tools (run by `aw2dev test`): `net desync` on synthetic runs, `net repeat`'s arguments. No ROM, no live run."""
import argparse, contextlib, io, json, tempfile, unittest
from pathlib import Path
from . import cli, net

BLOCKS = 8 + 64          # 4 KB blocks of IWRAM (8) then EWRAM (64), as run_dump.rs writes them


def parts(differ=()):
    return "".join(("beef" if i in differ else "0123") for i in range(BLOCKS))


def make_run(root, per_seat_frames):
    """per_seat_frames[seat] = {frame: (hash, parts)}: a run dir with only what `net desync` reads."""
    d = Path(root)
    for seat, frames in enumerate(per_seat_frames):
        (d / f"shots_s{seat}.jsonl").write_text("")
        with open(d / f"state_s{seat}.jsonl", "w") as f:
            for n, (fr, (h, p)) in enumerate(sorted(frames.items())):
                f.write(json.dumps({"ms": n, "tick": n * 60, "k": "hash", "frame": fr, "h": h, "parts": p}) + "\n")
    return d


def desync(d):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = net.cmd_desync(argparse.Namespace(run=str(d), seats=None, window=20))
    return rc, out.getvalue()


class Desync(unittest.TestCase):
    def frames(self, seat1_differ, from_frame=180):
        a = {f: ("a" * 16, parts()) for f in range(60, 361, 60)}
        b = {f: (("a" if f < from_frame else "b") * 16, parts(seat1_differ if f >= from_frame else ())) for f in range(60, 361, 60)}
        return [a, b]

    def test_a_stack_only_divergence_is_named_as_timing_skew_not_game_state(self):
        with tempfile.TemporaryDirectory() as t:
            rc, text = desync(make_run(t, self.frames({7})))
        self.assertEqual(rc, 1, "a diverged run still fails: the hash is the canary")
        self.assertIn("first diverged frame: 180", text)
        self.assertIn("0x03007000-0x03007fff", text)
        self.assertIn("EWRAM (units, funds, map, RNG, menus) stays equal", text)
        self.assertIn("timing skew", text)

    def test_a_change_in_ewram_is_never_called_timing(self):
        # the same stack block, and later a block of EWRAM (a unit table, say): real state differs, so no excuse is printed
        a = {f: ("a" * 16, parts()) for f in range(60, 361, 60)}
        b = {f: (("a" if f < 180 else "b") * 16, parts({7} if f < 300 else {7, 10})) for f in range(60, 361, 60)}
        with tempfile.TemporaryDirectory() as t:
            rc, text = desync(make_run(t, [a, b]))
        self.assertEqual(rc, 1)
        self.assertIn("EWRAM (units, funds, map, RNG, menus) differs in 0x02002000", text)
        self.assertNotIn("timing skew", text)

    def test_ewram_alone_diverging_is_real(self):
        with tempfile.TemporaryDirectory() as t:
            rc, text = desync(make_run(t, self.frames({9})))
        self.assertEqual(rc, 1)
        self.assertNotIn("timing skew", text)
        self.assertIn("differs in 0x02001000", text)

    def test_equal_runs_are_no_desync(self):
        a = {f: ("a" * 16, parts()) for f in range(60, 361, 60)}
        with tempfile.TemporaryDirectory() as t:
            rc, text = desync(make_run(t, [a, dict(a)]))
        self.assertEqual(rc, 0)
        self.assertIn("NO DESYNC", text)


class Repeat(unittest.TestCase):
    def test_the_command_is_registered_with_the_emerald_sun_unranked_default(self):
        p = cli.build_parser()
        a = p.parse_args(["net", "repeat"])
        self.assertEqual((a.scenario, a.runs, a.skin), ("unranked", 8, True))
        self.assertFalse(p.parse_args(["net", "repeat", "--no-skin"]).skin)


if __name__ == "__main__":
    unittest.main()


class QuietWindows(unittest.TestCase):
    def test_a_powers_quote_box_before_the_act_is_not_a_leak(self):
        from . import check
        w = check.quiet_windows([{"what": "power", "ms": 100_000}, {"what": "attack", "ms": 50_000}, {"what": "build", "ms": 10_000}])
        self.assertIn((100_000 - check.POWER_QUOTE_MS, 102_500), w)
        self.assertIn((47_500, 52_500), w)
        self.assertEqual(len(w), 2, "building is not allowed on a waiting window")
