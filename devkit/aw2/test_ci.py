"""Tests for `aw2dev ci` and the workspace conventions the GitHub checks workflow holds (no ROM, no cargo)."""
import importlib.util
import unittest

from . import cfg
from .commands import ci


class Workflow(unittest.TestCase):
    def test_every_command_of_the_workflow_is_found(self):
        got = [c for _, c in ci.steps((cfg.REPO / ".github" / "workflows" / "checks.yaml").read_text())]
        for want in ("cargo machete", "python3 tools/check_workspace.py", "cargo fmt --all -- --check", "python3 tools/check_workspace.py --resolved"):
            self.assertIn(want, got)
        tests = [c for c in got if c.startswith("cargo test")]
        self.assertGreaterEqual(len(tests), 5, tests)      # (the block of two lines is read as two steps)
        self.assertIn("cargo test --locked --no-default-features --lib -p tango-session", got)

    def test_a_block_and_a_single_line_run_are_read(self):
        text = "jobs:\n  a:\n    steps:\n      - run: echo one\n      - name: x\n        run: |\n          echo two\n          echo three\n  b:\n    steps:\n      - run: echo four\n"
        self.assertEqual(ci.steps(text), [("a", "echo one"), ("a", "echo two"), ("a", "echo three"), ("b", "echo four")])


class Conventions(unittest.TestCase):
    def test_the_workspace_keeps_the_conventions_checks_workflow_asks_for(self):
        """tools/check_workspace.py (the workflow's step): shared dependencies declared once in the workspace, layers, game features. It failed on `env_logger` and
        `tokio-tungstenite` used by two crates with their own versions."""
        spec = importlib.util.spec_from_file_location("check_workspace", cfg.REPO / "tools" / "check_workspace.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.check(mod.ROOT) + mod.check_boundaries(mod.ROOT), [])

    def test_the_library_builds_without_a_game_registered(self):
        """`cargo test --no-default-features -p tango-library` did not compile: `online.rs` named tango_gamesupport_aw2 in functions with no feature gate. Every
        such call needs a `#[cfg(feature = "gamesupport-aw2")]` and a fallback."""
        text = (cfg.REPO / "tango-library" / "src" / "online.rs").read_text()
        lines = text.splitlines()
        for i, l in enumerate(lines):
            if "tango_gamesupport_aw2::" in l and not l.lstrip().startswith(("//", "pub use")):
                j = i
                while j > 0 and not lines[j].startswith(("pub fn", "fn", "pub static", "static")):
                    j -= 1
                gated = lines[j - 1].strip() == '#[cfg(feature = "gamesupport-aw2")]' or lines[j - 2].strip() == '#[cfg(feature = "gamesupport-aw2")]'
                inner = any(x.strip() == '#[cfg(feature = "gamesupport-aw2")]' for x in lines[j:i])      # (a gated block inside the function)
                self.assertTrue(gated or inner, f"online.rs:{i + 1}: {lines[j]} uses the game crate with no feature gate")


if __name__ == "__main__":
    unittest.main()
