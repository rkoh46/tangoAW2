"""Tests of the Emerald Sun difficulty score and campaign check (run by `aw2dev test python`; the report needs the built example aw2_es_report, skipped without)."""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aw2 import cfg, util                              # noqa: E402
from aw2.eslib import difficulty, report              # noqa: E402

try:
    EXE = util.example_bin("aw2_es_report")
    HAVE = EXE.exists() and cfg.aw2_rom().exists()
except Exception:
    HAVE = False


class Score(unittest.TestCase):
    def test_squash_is_monotone(self):
        self.assertLess(difficulty.squash(1.0), difficulty.squash(2.0))
        self.assertLess(difficulty.squash(2.0), 1.0)

    def test_dynamic_score_rewards_a_lost_or_slow_win(self):
        won = lambda d: {"player": "bot", "result": "won", "days": d}
        self.assertLess(difficulty.dynamic_score([won(5)]), difficulty.dynamic_score([won(18)]))
        self.assertEqual(difficulty.dynamic_score([{"player": "bot", "result": "lost", "days": 9}]), 100)
        cpu = lambda r: {"player": "cpu", "result": r, "days": 9}
        self.assertLess(difficulty.dynamic_score([cpu("won")]), difficulty.dynamic_score([cpu("lost")]))
        self.assertIsNone(difficulty.dynamic_score([]))
        # (a handicap run against a thinned enemy is not the mission's difficulty)
        self.assertIsNone(difficulty.dynamic_score([{"player": "bot", "result": "won", "days": 9, "scale": 60}]))
        # (a computer-vs-computer run that ends with no winner proves nothing about the player's side)
        self.assertIsNone(difficulty.dynamic_score([cpu("none")]))
        self.assertEqual(difficulty.dynamic_score([cpu("none"), cpu("won")]), difficulty.dynamic_score([cpu("won")]))

    def test_every_unit_has_a_price(self):
        for k in range(1, 28):
            if k in (25,):
                continue
            self.assertIn(k, report.COST, k)


@unittest.skipUnless(HAVE, "needs the built aw2_es_report and the AW2 ROM (aw2dev build --examples)")
class Campaign(unittest.TestCase):
    def test_the_final_mission_is_clearly_the_hardest(self):
        ms = report.missions()
        self.assertEqual(len(ms), 16)
        scores = {i: difficulty.static_score(difficulty.numbers(d)) for i, d in enumerate(ms.values(), 1)}
        top = max(scores, key=scores.get)
        self.assertEqual(top, 16, scores)
        second = max(v for k, v in scores.items() if k != 16)
        self.assertGreaterEqual(scores[16], second * 1.10, scores)

    def test_the_last_missions_ramp_up_to_the_final_one(self):
        """M13 < M14 < M15 < M16 in the static score, each step at least a point, and M16 more than any step."""
        ms = report.missions()
        sc = [difficulty.static_score(difficulty.numbers(d)) for d in ms.values()]
        m13, m14, m15, m16 = sc[12:16]
        self.assertLess(m13 + 1, m14, sc)
        self.assertLess(m14 + 1, m15, sc)
        self.assertGreater(m16 - m15, max(m14 - m13, m15 - m14), sc)

    def test_only_the_two_black_hole_missions_have_inventions(self):
        ms = report.missions()
        self.assertEqual([k for k, d in ms.items() if d["blackhole"]], ["es09", "es13"])


if __name__ == "__main__":
    unittest.main()


class WorldMap(unittest.TestCase):
    def test_the_shipped_flags_are_in_order_on_land_and_apart(self):
        from aw2.eslib import worldmap
        self.assertEqual(worldmap.problems(worldmap.nodes(), worldmap.picture(), worldmap.needs()), [])

    def test_bad_flags_are_caught(self):
        from aw2.eslib import worldmap
        pts = [(20 + 25 * k, 100) for k in range(16)]
        self.assertEqual(worldmap.problems(pts), [])
        self.assertTrue(any("outside" in b for b in worldmap.problems(pts[:15] + [(470, 100)])))
        self.assertTrue(any("apart" in b for b in worldmap.problems(pts[:15] + [(pts[14][0] + 5, 100)])))
        self.assertTrue(any("needs" in b for b in worldmap.problems(pts, needed={"es01": ["Start"], "es02": ["es01"], "es03": ["es01"]})))
        sea = [[(2, 10, 28)] * 480 for _ in range(240)]            # an all-blue picture
        self.assertTrue(any("sea" in b for b in worldmap.problems(pts, sea)))
        land = [[(28, 26, 12)] * 480 for _ in range(240)]
        self.assertEqual(worldmap.problems(pts, land), [])


class AsukaRule(unittest.TestCase):
    """`campaign check` fails when the Emerald Sun Campaign names Asuka (she is in Versus, not in that campaign)."""

    def test_the_real_campaign_does_not_name_her(self):
        from aw2.eslib import cli
        self.assertEqual(cli.asuka_rule(lambda ok, msg: None), 0)

    def test_a_mention_fails(self):
        import tempfile
        from aw2.eslib import cli
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "tango-gamesupport-aw2" / "src"
            (src / "es_text").mkdir(parents=True)
            (src / "es_act1.rs").write_text("let who = co_new::ASUKA;\n")
            (src / "es_text" / "act1.txt").write_text("KLAUS: Hello.\nASUKA: no.\n")
            (src / "es_cos.rs").write_text("(92, \"asuka\")\n")        # the portraits table may name her
            (src / "es_text.rs").write_text("")
            old, msgs = cli.cfg.REPO, []
            cli.cfg.REPO = Path(t)
            try:
                self.assertEqual(cli.asuka_rule(lambda ok, msg: msgs.append((ok, msg))), 1)
            finally:
                cli.cfg.REPO = old
            self.assertFalse(msgs[0][0])
            self.assertIn("es_act1.rs:1", msgs[0][1])
