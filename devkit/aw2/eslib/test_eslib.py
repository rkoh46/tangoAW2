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
