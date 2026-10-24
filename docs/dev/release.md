# Releasing

`aw2dev release <version> --notes FILE [--dry-run] [--yes]` runs the checklist (devkit/aw2/release.py). **Pushing needs the user's approval
each time**: without `--yes` the command does everything local and refuses at the push step. Get a clear yes from the user first (and
their approval of any new visuals; show sheets before release).

## Rules
- Branch `hirestilt` is the development branch; releases go from it. Pushed refs: `hirestilt`, `HEAD:main`, `HEAD:v030`, `HEAD:aw2`,
  `HEAD:ds-campaign2`, and the tag `v<version>`. All must be fast-forwards (preflight checks).
- The version lives in `tango/Cargo.toml` (and the `tango` entry of `Cargo.lock`); it shows on the title screen. Bump it every release.
- The changelog goes in the annotated tag message (the release workflow uses it as the body); README and forum link Releases/latest.
  Notes file = the tag message.
- Nothing from the games in commits (preflight scans new commits for gba/nds/sav/srl, PNGs outside `docs/screenshots/`,
  `tools/aw2test/out*`; allowlist legit art in `devkit/release_allow.txt`).
- Every release includes the IPA of the same version: `tangoaw2-<version>-ios.ipa` (built with `DEVELOPER_DIR` Xcode, copied to
  `~/Downloads`). The release workflow also builds mac (Apple Silicon only), Windows, Linux and iOS assets.
- Install on the user's Mac with `aw2dev install-mac` (never closes their running app; tell them to reopen it).
- Small playtest fixes need no regression; broad merges get the suite and `net matrix`.

## Steps `aw2dev release` performs
1. preflight (branch, clean tree, fast-forwards, game-file scan, tag free, version greater, notes present, `gh`)
2. bump version, commit `Version X`
3. `cargo build --profile release-dist --bin tango`
4. `cargo test --lib` (gamesupport, session, match)
5. `install-mac`
6. IPA, copied to Downloads
7. annotated tag from the notes
8. push (`--yes` only)
9. watch the `release.yaml` run (`gh run watch`), rerun failed jobs once, list assets
Expect assets: macOS dmg, Windows exe + pdb, Linux AppImage + debug, iOS ipa. Use `--skip build tests ipa ...` to leave steps out,
`--dry-run` to only list them.

## Playtest bundle (`aw2dev playtest-app`)
`aw2dev playtest-app` builds `dist/TangoAW2-Playtest.app` (release-dist, cargo feature `playtest`, into `target/playtest`): this checkout with the Emerald Sun Campaign (`es_campaign::dev_flag`) and its
COs in Versus (`es_co::in_versus`) **on by default, no environment variables**, the self-updater off, and everything of its own so it installs beside the real app: bundle id `net.n1gp.TangoAW2Playtest`,
name "TangoAW2 Playtest", settings under `net.n1gp.tangoaw2-playtest`, data under `~/Documents/TangoAW2-Playtest` (a fresh install: point it at your ROMs once, in its Settings). It installs nothing
and never touches `/Applications/TangoAW2.app` or its settings, ROMs and saves. The campaign's save slot (Flash slot 11) lives in the playtest's own saves.
