# Growing the kit

**Standing rule.** Every new feature or content type (a CO, army, unit, terrain, weather, music, campaign, mode, online change, UI screen...) adds, in the
SAME work: (1) its `aw2dev` subcommand, scenario or checker; (2) a `docs/dev` entry; (3) a `.claude/skills` skill, or an update to one; (4) a regression
test in the suite. A task is not done until all four are in and `aw2dev kit check` is clean. Tests and drivers live in the repo, never only in a scratchpad.

Helpers: `aw2dev kit new-command <name>` (skeleton command + doc), `aw2dev kit new-skill <name>`, `aw2dev kit check` (lists docs, skills and tests that
point at commands, files or scenarios that do not exist; `aw2dev test` runs it too).

## 1. A command (plugin module)
Every module in `devkit/aw2/commands/` that defines `register(sub)` is discovered by the CLI at start-up (`cli.discover`). `aw2dev kit new-command thing` writes:
```python
"""aw2dev thing: what it does (docs/dev/thing.md)."""
from .. import cfg, util          # cfg: paths/config, util: run(), say(), die(), LiveLock, df()

def register(sub):
    p = sub.add_parser("thing", help="one line")
    p.add_argument("--option")
    p.set_defaults(fn=run)

def run(args):
    ...
    return 0                      # 0 pass, 1 fail (the CLI exits with it)
```
Rules: paths from `cfg` (never hard-coded), output under `cfg.work(...)` (git-ignored), only READ the ROMs, never touch ~/Documents/TangoAW2, hold
`util.LiveLock()` while real clients run, stdlib + Pillow + numpy only. Older built-in commands are still in `cli.py`; new ones go in `commands/`.

## 2. A live scenario
In `devkit/aw2/scenarios.py` add `def s_name(fog): return pokes, turns` (pokes = TANGOAW2_TEST_POKE lines, turns = `[(seat, ops)]`; ops from the helpers
`goto`, `A`, `sel_move`, `build`, `capq`, `yield_`), register it in `SCEN` and its seat count in `SEATS` if not 2. Use cues (`until ...`), never fixed waits only;
every seat proposes the same map unless you pass `--picks`. A flow that is not a turn list (own state machine) is a module that uses `session.Session`
(see `rejoin.py`, `ios.py`). Run: `aw2dev live name --local`, then `aw2dev check latest`.

## 3. A checker
In `devkit/aw2/check.py` add `def c_name(run, **kw)` returning `{"pass": True|False|None, "detail": "..."}` (None = not applicable), register it in `CHECKS`
and `ALL`. Use `runlib.Run` (shots, states, acts, hashes, mover). Make the heuristic strict enough to FAIL on a real example (test it on a run that is wrong,
as `check.py`'s leak check was tested on the reconnect box) and quiet on a good run.

## 4. A suite entry (the regression test)
- Offline, no network: write `tango-gamesupport-aw2/examples/aw2_<thing>_<n>p.txt` (see docs/dev/pad-scripts.md) that exits 1 on failure (`expect ...`,
  `until ... TIMEOUT` counts), and add its name to `PLAIN` (or `LEAK` / `CAM`) in `devkit/aw2/suite.py`.
- Live: add the scenario to `aw2dev net matrix` defaults or document the exact `aw2dev live ...` + `aw2dev check` line in the skill and in docs/dev/testing.md.
- Pure logic: a Rust test in the module (`cargo test -p tango-gamesupport-aw2 --lib`), or a Python test next to the tool (`five/test_five.py` style, run by `aw2dev test`).
- Register any new EWRAM in `ram_map.rs` (overlap test) and bump `sim_version` when both peers must agree on new behaviour.

## 5. A skill
`aw2dev kit new-skill aw2-thing` creates `.claude/skills/aw2-thing/SKILL.md` with `name:` (= folder) and `description:` frontmatter and numbered steps that call `aw2dev`.
Update an existing skill instead when the new feature is a variation of it (e.g. a new map: `aw2-add-map`). Placeholder content kits (`aw2-add-co`, ...) are
filled in by the first real feature of their kind.

## 6. The docs entry
One file or a section of an existing file in `docs/dev/`, listed in `docs/dev/README.md`: what it is, the code (file + function), how to run it, what pass
means, limits. Facts only; cite files and functions.

## Done checklist
`aw2dev kit check` clean - `aw2dev test` green - suite `bad=0` if the waiting view or online code changed - the new scenario/check run once and looked at - committed.
