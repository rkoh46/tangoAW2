# devkit

`aw2dev` is the one developer CLI of tangoAW2 (repo-root shim `./aw2dev`). Python 3.11+ (stdlib, Pillow, numpy). Documentation:
`docs/dev/README.md`. Config: `config.toml` (+ git-ignored `config.local.toml`). All output goes to the git-ignored `work/`
(run dirs, test profiles with copies of the ROM, the test app bundle, audit/suite output); the live lock is `~/.aw2dev/live.lock`.
Nothing from the games is ever stored in git.
