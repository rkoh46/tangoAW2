# devkit

`aw2dev` is the one developer CLI of tangoAW2 (repo-root shim `./aw2dev`). Python 3.11+ (stdlib, Pillow, numpy). Documentation:
`docs/dev/README.md`. Config: `config.toml` (+ git-ignored `config.local.toml`). All output goes to the git-ignored `work/`
(run dirs, test profiles with copies of the ROM, the test app bundle, audit/suite output); the live lock is `~/.aw2dev/live.lock`.
Nothing from the games is ever stored in git.

## The kit must grow with the game (standing rule)
Every new feature or content type adds, in the same work: (1) its `aw2dev` subcommand, scenario or checker, (2) a `docs/dev` entry, (3) a `.claude/skills`
skill or an update to one, (4) a regression test in the suite. A task is not done until that is in and `aw2dev kit check` is clean. How: `CONTRIBUTING-KIT.md`
(templates for a command module in `aw2/commands/`, a live scenario, a checker, a suite entry, a skill), `aw2dev kit new-command <name>`,
`aw2dev kit new-skill <name>`, `aw2dev kit check`.
