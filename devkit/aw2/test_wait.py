"""Tests for `aw2dev wait` (no ROM, no cargo)."""
import subprocess, sys, tempfile, unittest
from pathlib import Path

from .commands import wait


class Wait(unittest.TestCase):
    def test_a_pid_is_done_when_the_process_has_ended(self):
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            self.assertFalse(wait.done(str(p.pid)))
        finally:
            p.kill()
            p.wait()
        self.assertTrue(wait.done(str(p.pid)))

    def test_a_file_is_done_when_it_has_content_and_the_text(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "run.log"
            self.assertFalse(wait.done(str(f)))
            f.write_text("")
            self.assertFalse(wait.done(str(f)))
            f.write_text("PASS a\n")
            self.assertTrue(wait.done(str(f)))
            self.assertFalse(wait.done(str(f), "passed in"))
            f.write_text("PASS a\n1/1 passed in 3 s\n")
            self.assertTrue(wait.done(str(f), "passed in"))

    def test_the_wait_ends_and_times_out(self):
        class A:
            target, text, poll = "/nonexistent/aw2dev-wait-test", None, 0.01
            timeout = 0.05
        self.assertEqual(wait.run(A), 1)
        with tempfile.NamedTemporaryFile("w", suffix=".log") as f:
            f.write("x")
            f.flush()
            A.target = f.name
            self.assertEqual(wait.run(A), 0)
