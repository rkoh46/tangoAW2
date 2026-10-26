"""Tests of the music kit (run by `aw2dev test python`): the M4A reader, the song converter's output read back by an independent decoder (needs the built example aw2_es_music,
skipped without), the audio analysis (pitch, loop seams, levels) on synthetic sound, the rules, the solo transform of `sound stems`."""
import json, subprocess, sys, tempfile, unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from aw2 import cfg, util                                   # noqa: E402
from aw2.musiclib import tools as sound_music               # noqa: E402
from aw2.musiclib import audio, m4a, pitch, similar                  # noqa: E402

try:
    EXE = util.example_bin("aw2_es_music")
    HAVE = EXE.exists()
except Exception:
    HAVE = False


def rom_with(blobs):
    """A fake ROM image with each (offset, bytes) placed from 0x08000000."""
    size = max(o + len(b) for o, b in blobs) + 16
    d = bytearray(size)
    for o, b in blobs:
        d[o:o + len(b)] = b
    return m4a.Rom(bytes(d))


class Reader(unittest.TestCase):
    def test_waits_notes_and_a_loop(self):
        # TEMPO 54, VOICE 3, W24, N12 C4 v100, W12, GOTO label(=0x08000004)
        label = 0x08000000 + 4
        t = bytes([0xBB, 54, 0xBD, 3, 0x80 + 24, 0xD0 + 11, 60, 100, 0x80 + 12, 0xB2]) + label.to_bytes(4, "little")
        rom = rom_with([(0, t)])
        ev, end, loop_tick, target = m4a.run(rom, 0x08000000)
        self.assertEqual(end, 36)
        self.assertEqual(loop_tick, 0)                       # the label sits after the first two commands, at tick 0
        self.assertIn((24, "NOTE", 60, 100, 12), ev)
        self.assertEqual([e[1] for e in ev if e[1] != "NOTE"], ["TEMPO", "VOICE"])

    def test_patterns_expand(self):
        # PATT to a pattern of one W24 then PEND, twice by REPT 2
        body = bytes([0x80 + 24, 0xB4])
        main = bytes([0xB5, 2]) + (0x08000100).to_bytes(4, "little") + bytes([0xB1])
        rom = rom_with([(0, main), (0x100, body)])
        ev, end, lt, tg = m4a.run(rom, 0x08000000)
        self.assertEqual(end, 48)

    def test_key_names_are_scientific(self):
        self.assertEqual(m4a.key_name(60), "C4")
        self.assertEqual(m4a.key_name(61), "C#4")


@unittest.skipUnless(HAVE, "needs the built aw2_es_music (aw2dev build --examples)")
class Converter(unittest.TestCase):
    """The Rust compiler's bytes, decoded again by this reader: the same ticks, the same number of notes, a GOTO to the label."""

    def test_every_song_reads_back(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([str(EXE), "--dump", d], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            songs = [json.loads(l) for l in r.stdout.splitlines()]
            self.assertGreaterEqual(len(songs), 5)
            for j in songs:
                notes = 0
                for t, tr in enumerate(j["tracks"]):
                    b = bytearray((Path(d) / f"{j['name']}.{t}.bin").read_bytes())
                    self.assertEqual(len(b), tr["bytes"])
                    b[-4:] = (0x08000000 + tr["label"]).to_bytes(4, "little")
                    rom = rom_with([(0, bytes(b))])
                    ev, end, loop_tick, target = m4a.run(rom, 0x08000000)
                    self.assertEqual(end, j["intro_ticks"] + j["loop_ticks"], f"{j['name']} track {t}: every track is as long as the song")
                    self.assertEqual(target, 0x08000000 + tr["label"])
                    self.assertEqual(loop_tick, j["intro_ticks"], f"{j['name']} track {t}: the loop starts where the intro ends")
                    notes += sum(1 for e in ev if e[1] == "NOTE")
                    tempos = [e[2] * 2 for e in ev if e[1] == "TEMPO"]
                    if t == 0:
                        self.assertEqual(tempos[0], j["bpm"])
                    self.assertEqual(ev[0][1] if ev[0][1] != "TEMPO" else ev[1][1], "VOICE")
                self.assertEqual(notes, j["notes"], f"{j['name']}: the notes read back")


class Similar(unittest.TestCase):
    """`aw2dev sound similar`: the originality check (made-up melodies only; no note of AW2's songs is written here)."""
    A = [60, 63, 67, 65, 62, 70, 58, 61, 66]
    B = [60, 61, 69, 64, 71, 59, 66, 57, 68]

    def ln(self, keys, gap=12, shift=0):
        return similar.line([(i * gap, k + shift) for i, k in enumerate(keys)])

    def test_a_transposed_copy_fails_on_the_interval_run(self):
        s = similar.compare(self.ln(self.A, 12, 7), self.ln([50] + self.A + [52], 6))
        self.assertGreaterEqual(s["run"], similar.RUN_NOTES)
        self.assertTrue(similar.verdict(s))

    def test_the_same_rhythm_and_contour_with_other_intervals_fails_on_contour(self):
        steps = [1, 2, -1, 3, -2, 1, 1, -3, 2, 1, -1]
        gaps = [6, 12, 6, 6, 12, 6, 18, 6, 12, 6, 6, 12]
        def build(mult):
            t, k, out = 0, 60, [(0, 60)]
            for st, g in zip(steps, gaps):
                t += g
                k += st * mult
                out.append((t, k))
            return similar.line(out)
        s = similar.compare(build(1), build(2))
        self.assertGreaterEqual(s["contour"], similar.CONTOUR_NOTES)
        self.assertEqual(s["run"], 0)

    def test_different_melodies_and_a_rattle_pass(self):
        s = similar.compare(self.ln(self.A), self.ln(self.B))
        self.assertEqual(similar.verdict(s), [])
        rattle = similar.line([(i * 6, 40) for i in range(40)])
        self.assertEqual(similar.verdict(similar.compare(rattle, rattle)), [])      # a repeated note is in every song

    def test_whole_bars_that_match_fail(self):
        bar = [(0, 60), (12, 63), (24, 67), (36, 62), (48, 70)]
        ours = similar.line([(b * 96 + t, k) for b in range(4) for t, k in bar])
        theirs = similar.line([(b * 96 + t, k + 5) for b in range(4) for t, k in bar])
        self.assertEqual(similar.bar_share(ours, theirs), 1.0)
        self.assertTrue(similar.verdict(similar.compare(ours, theirs)))


class Rules(unittest.TestCase):
    def test_a_short_loop_and_too_many_voices_are_reported(self):
        j = dict(loop_s=20.0, peak_voices=8, peak_at=96, tracks=[1] * 9, bytes=100)
        bad = sound_music.broken_rules(j)
        self.assertEqual(len(bad), 3)
        j = dict(loop_s=60.0, peak_voices=6, tracks=[1] * 8, bytes=100)
        self.assertEqual(sound_music.broken_rules(j), [])

    def test_solo_keeps_only_the_named_tracks(self):
        text = "song x\ntrack 1 inst=a\ntrack 2 inst=b\nsection A bars=1\n  1: | C4/1 |\n  2: | D4/1 |\n     | E4/1 |\nend\nform A\n"
        out = sound_music.solo_text(text, {2})
        self.assertIn("2: | D4/1 |", out)
        self.assertIn("| E4/1 |", out)                      # the continuation line stays with track 2
        self.assertNotIn("C4", out)
        self.assertIn("track 1", out)                       # declarations stay


class Audio(unittest.TestCase):
    rate = 32768

    def tone(self, hz, secs, amp=0.3):
        t = np.arange(int(self.rate * secs)) / self.rate
        return amp * (np.sin(2 * np.pi * hz * t) + 0.5 * np.sin(4 * np.pi * hz * t))

    def test_pitch_of_a_tone_and_of_a_weak_fundamental(self):
        for hz in (65.4, 130.8, 261.6, 523.3):
            f, c = pitch.f0(self.tone(hz, 0.4), self.rate)
            self.assertAlmostEqual(f / hz, 1.0, delta=0.01, msg=hz)
        t = np.arange(self.rate // 2) / self.rate
        weak = 0.05 * np.sin(2 * np.pi * 110 * t) + 0.3 * np.sin(2 * np.pi * 220 * t) + 0.2 * np.sin(2 * np.pi * 330 * t)
        f, _ = pitch.f0(weak, self.rate)
        self.assertAlmostEqual(f, 110.0, delta=1.5)          # the missing fundamental is not read an octave up
        self.assertEqual(pitch.f0(np.zeros(8192), self.rate), (0.0, 0.0))

    def test_levels(self):
        x = self.tone(440, 3.0, 0.5)
        lv = audio.levels(x, self.rate)
        self.assertAlmostEqual(lv["rms_db"], 20 * np.log10(np.sqrt(np.mean(x ** 2))), delta=0.01)
        self.assertLess(lv["peak_db"], 0)

    def test_grit_tells_a_clean_tone_from_a_crunchy_one_and_clipping_is_counted(self):
        rng = np.random.default_rng(1)
        clean = self.tone(165.0, 3.0)
        crunchy = clean + rng.normal(0, 0.12, len(clean))
        self.assertGreater(audio.grit(clean, self.rate), 20)
        self.assertLess(audio.grit(crunchy, self.rate), 10)
        self.assertIsNone(audio.grit(np.zeros(self.rate), self.rate))
        self.assertEqual(audio.levels(clean, self.rate)["clipped"], 0)
        self.assertGreater(audio.levels(np.clip(clean * 4, -1, 1), self.rate)["clipped"], 100)

    def seamed(self, click=False, gap=False):
        """A repeating 4 s pattern (a loop) of beats, three passes after a 2 s intro."""
        r = self.rate
        beat = np.concatenate([self.tone(220, 0.15, 0.4), np.zeros(int(r * 0.35))])
        loop = np.tile(beat, 8)                              # 4 s
        x = np.concatenate([np.zeros(r * 2), loop, loop, loop])
        if gap:
            x[2 * r + 4 * r - 3000: 2 * r + 4 * r + 3000] = 0
        if click:
            x[2 * r + 4 * r] += 0.9
        return x

    def test_a_clean_loop_has_no_click_or_gap_and_repeats(self):
        x = self.seamed()
        s = audio.loop_seams(x + 0.001 * np.random.RandomState(1).randn(len(x)), self.rate, 2.0, 4.0)
        self.assertGreater(s["repeat_corr"], 0.95)
        self.assertEqual(abs(s["period_err_ms"]) <= 20, True)
        for seam in s["seams"]:
            self.assertLess(seam["click"], 3.0)

    def test_a_click_at_the_seam_is_found(self):
        s = audio.loop_seams(self.seamed(click=True), self.rate, 2.0, 4.0)
        self.assertGreater(max(x["click"] for x in s["seams"]), 5.0)

    def test_resampling_keeps_pitch_and_level(self):
        x = self.tone(440, 1.0, 0.4)
        st = np.stack([x, x], 1).astype(np.float32)
        y = audio.resample(st, self.rate, 44100)
        self.assertEqual(y.shape[0], 44100)
        spec = np.abs(np.fft.rfft(y[:, 0]))
        self.assertAlmostEqual(float(spec.argmax()), 440.0, delta=1.0)
        self.assertAlmostEqual(float(np.sqrt(np.mean(y[:, 0] ** 2))), float(np.sqrt(np.mean(x ** 2))), delta=0.01)

    def test_the_picture_and_the_strip_are_written(self):
        x = self.seamed()
        with tempfile.TemporaryDirectory() as d:
            audio.picture(x, self.rate, Path(d) / "a.png", marks=[2.0])
            audio.seam_picture(x, self.rate, [6.0], Path(d) / "b.png")
            self.assertTrue((Path(d) / "a.png").stat().st_size > 1000)
            self.assertTrue((Path(d) / "b.png").stat().st_size > 500)


if __name__ == "__main__":
    unittest.main()
