# tangoAW2: guide for AI sessions

tangoAW2 is an Advance Wars 2 (GBA) rollback-netplay app with optional Dual Strike content, built on Tango: Rust, mGBA. The game runs as
one shared mGBA console per peer; AW2's own screens are the UI. Read this file, then `docs/dev/README.md`. Use `./aw2dev` for every build,
test, live run and release (never ad-hoc scripts in a scratchpad: they vanish).

## Layout
| Path | What |
|---|---|
| `tango/` | the desktop app (iced UI, session wiring, `src/app/debug_aids.rs` = pad scripts and other test aids) |
| `tango-gamesupport-aw2/` | all AW2 logic: `pvp.rs` (netplay rules, waiting views), `fog_view.rs`, `online*.rs`, `unranked.rs`, `result_view.rs`, `five*.rs` (5-army support, maps in `five/maps.txt`), `army_skin.rs` + `skins/*.toml` (Emerald Sun, the sixth army: a data file on one of AW2's colours, docs/dev/army-packs.md), `ds_*.rs` (Dual Strike pack), `run_dump.rs` (test dumps), `examples/` (offline harness, audits) |
| `tango-session/`, `tango-match/`, `tango-net/`, `tango-lobby/`, `tango-backend-mgba/` | session drivers (`pvp/`), match engine, transport (`impair.rs`, `endpoints.rs`), lobby, mGBA shared console |
| `ios/`, `macos/`, `linux/`, `win/` | platform packaging (`ios/build.sh` builds the IPA) |
| `devkit/` | `aw2dev` CLI (`./aw2dev`), config, ported test drivers and checkers; output in git-ignored `devkit/work/` |
| `docs/dev/` | developer knowledge base (index: `docs/dev/README.md`) |
| `tools/` | older checkers (`cam_check.py`, `pic_check.py`, `hud_check.py`), `aw2test/` scripted battle tests, `maps_doc.py` |
| `.claude/skills/` | task skills: aw2-test, aw2-live-debug, aw2-release, aw2-add-map, aw2-add-army, aw2-ui-screen, aw2-waiting-view, aw2-online-debug, aw2-gfx-debug (+ content-kit placeholders) |
| `ARCHITECTURE.md`, `docs/AW2.md`, `docs/MAPS.md` | long-form notes (parts of AW2.md are stale; docs/dev follows the code) |

## Rules that never change
- **Nothing from the games is ever committed or pushed**: no ROMs, saves, game screenshots (only `docs/screenshots/` for README art),
  no `tools/aw2test/out*`, no devkit run dirs. Tables are read from the user's ROMs at run time. `aw2dev release` scans for it.
- **Releases need the user's explicit approval each time.** Never push or tag on your own. `aw2dev release` refuses to push without
  `--yes`. Show new visuals (sheets) and get approval before any release. Exception the user gave: the iOS IPA may go out as soon as it builds.
- **Never close the user's running TangoAW2.** Install with `aw2dev install-mac` (swaps the binary, ad-hoc signs; tell them to reopen).
  Kill only your own test processes (`aw2dev live` does this by path). Never touch `~/Documents/TangoAW2` (ROMs/saves/logs are the
  player's). Capture game windows only, never the full screen (the app's `TANGOAW2_RUN_DIR` screenshots do this).
- **UI = Advance Wars 2's own design.** Every new menu, overlay, status line, timer or notice uses AW2's windows, plates, list pages,
  font and palette (`Canvas::window`, `Canvas::plate`, `Canvas::text` in `online.rs`); reuse native screens. No plain dark/black bars with
  text, nothing that looks like a debug menu. Show sheets before release.
- **Online behaviour = offline AW2.** Netplay must look and play like the same game offline: same screens, same animations, same
  rules, with the waiting windows showing what a spectator of that seat should see. Do not invent online-only rules.
- **Tests, drivers and checkers go in `devkit/` (or the repo's `tools/`, `examples/`), never only in a scratchpad.** A scratchpad vanishes; anything you wrote to
  test, drive, analyse or release must be committed as an `aw2dev` command, scenario or checker (docs/dev/README.md "Adding to the devkit").
- **The kit grows with the game.** Every new feature or content type adds, in the same work: its `aw2dev` subcommand, scenario or checker; a `docs/dev` entry;
  a `.claude/skills` skill (or an update to one); a regression test in the suite. Not done until `aw2dev kit check` is clean (templates: `devkit/CONTRIBUTING-KIT.md`;
  `aw2dev kit new-command|new-skill`).
- Keep every player-visible string about Advance Wars 2 / tangoAW2 (no Battle Network or Tango branding).
- Wire format and `sim_version` rules: see docs/dev/architecture-online.md before touching anything both peers must agree on; bump
  `sim_version` when the shared console's behaviour changes.
- Register new emulated-RAM state in `ram_map.rs` (overlap test) and docs/dev/ram-map.md.

## Branches and release
- `hirestilt` is the development branch (worktree `~/tangoAW2-hires`); `~/tangoAW2` is the main checkout. Releases push `hirestilt`
  plus `HEAD:main HEAD:v030 HEAD:aw2 HEAD:ds-campaign2` and the tag `v<version>` to `origin` (rkoh46/tangoAW2), all fast-forward.
- Bump `tango/Cargo.toml` (+ `Cargo.lock`) every release; version shows on the title screen. Changelog = annotated tag message
  (release notes), never the README. Every release builds the IPA `tangoaw2-<ver>-ios.ipa` and copies it to `~/Downloads`; mac is
  Apple Silicon only. Checklist and command: docs/dev/release.md.
- Commits author `rkoh`; end with the Co-Authored-By line the session requires. Small playtest fixes: fix, `aw2dev build --release`,
  `aw2dev install-mac`, let the user test (no regression runs while they playtest).
- Keep disk lean: only `~/tangoAW2` and `~/tangoAW2-hires` checked out long-term; remove merged agent worktrees; delete your `target/`
  and captures when done (`aw2dev clean`, dry run by default; `df -h ~` before big jobs).

## Toolchain
- Cargo is not on PATH: aw2dev sets `PATH=$HOME/.rustup/toolchains/stable-aarch64-apple-darwin/bin:$PATH`. Use `aw2dev build`
  (`--release` = release-dist, `--ios` = `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer ./ios/build.sh`, `--sim`).
- After a merge or pull, rebuild before trusting any test (aw2dev refuses stale binaries).
- ROMs: `~/Documents/TangoAW2/roms` (AW2 USA CRC32 5AD0E571; Dual Strike USA `.nds` for DS reference; pack files). All DS references
  and captures come from the clean USA `.nds`, never fan hacks. `TANGOAW2_PROFILE=<dir>` isolates an instance's config/data.
- Dual Strike decomposition (CC0): `~/advance-wars-dual-strike-decomp`, see docs/dev/decomp.md.
- Verify before claiming done: look at the pictures (sheets), same build for both fog modes, suite `bad=0` for waiting-view changes.

## Where to look
- Debug / test / release: `docs/dev/testing.md`, `online-dev.md`, `release.md`; skills `aw2-test`, `aw2-live-debug`, `aw2-online-debug`, `aw2-gfx-debug` (garbled graphics: `docs/dev/graphics.md`).
- How things work: `architecture-online.md`, `ram-map.md`, `rom-routines.md`, `maps.md`, `ds-pack.md`; test aids: `pad-scripts.md`, `env-aids.md`.
- The player's logs: `~/Documents/TangoAW2/logs/tango.log` (+ `.1`..`.5`, F8 report marks with `report-<stamp>.png`): read the latest log and any
  `report-*.png` first when the user reports a bug.
- Music: the Emerald Sun COs' own themes (`music/es/*.m4t`, `aw2dev sound compose|render|...`, docs/dev/music-kit.md, skill `aw2-add-music`).
- Content kits (COs, units, terrain, weather, music, campaigns, modes) are planned but not built: the skills `aw2-add-*` are
  placeholders; the army kit exists (`aw2dev armyskin`, skill `aw2-add-army`), and the CO data kit (`aw2dev co`, skill `aw2-add-co`, docs/dev/co-kit.md: data files, portraits composed from the ROMs' parts, balance, Tag Powers). Art composed from AW2/DS assets is read from the user's ROMs at runtime and never committed; an army skin's own colours and pixel art (original work, `skins/*.toml`) are committed data applied on top of it. Keep the campaign
  engine data-driven. AI debug channel and checkpoints are being built in the `aidebug` branch (`~/tangoAW2-aidebug`).
