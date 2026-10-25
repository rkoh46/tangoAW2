# Testing: what to run for which change

All commands are `aw2dev <cmd>` (repo root shim, `devkit/aw2dev`). Paths and ROMs come from `devkit/config.toml` (override with
`devkit/config.local.toml` or `AW2DEV_*` env). Run output lives in the git-ignored `devkit/work/`.

| You changed | Run | Pass means |
|---|---|---|
| Rust logic in `tango-gamesupport-aw2`, `tango-session`, `tango-match` | `aw2dev test` | lib tests green |
| `fog_view.rs`, `pvp.rs` (`watching`, `view_as`), `result_view.rs`, anything the waiting windows draw | `aw2dev build --all`, `aw2dev suite` (about 10 min), then `aw2dev live moveview --fog on` and `--fog off` + `aw2dev check latest` + `aw2dev sheet latest --around 0 --kind move --strip` and LOOK | suite prints `suite done bad=0`; checks PASS; strips look right |
| a new scene/menu the mover sees (waiting-view allowlist) | skill `aw2-waiting-view`: harness leak scripts (`aw2dev harness aw2_waiting_leak_3p --leak`), suite, `aw2dev check --leak` | no leaked UI on waiting windows |
| graphics: tiles, fonts, palettes, text drawn by hooks | `aw2dev gfx check` (catalogue in devkit/gfx/catalogue.toml; also run by the suite), `aw2dev check RUN --gfx`; skill `aw2-gfx-debug` | no findings |
| a new screen / text | skill `aw2-ui-screen`: `aw2dev audit text` and look at the BMPs | `done: 0 problems` and it looks like AW2 |
| maps / the map list / `five_map.rs` | `aw2dev live big5 --local` (5 seats propose Pentagon Atoll in the `5P Predeploy` tab and play two rounds: the regression for the list-loop bound), plus the rows below |
| maps (`five/maps.txt`, `online_maps.rs`, `five_map.rs`) | `aw2dev test python` (map pipeline), `aw2dev audit maps` (also `--ds`), `cargo test -p tango-gamesupport-aw2 --lib five_map` | audit exit 0 |
| the waiting picture (`shared.rs` `scratch_frame`), anything that loads or ticks the match's console outside the simulation, snapshots/rollback, an army skin online | `cargo test -p tango-backend-mgba --lib`, then `aw2dev net repeat` (8 runs of 2P Unranked with the Emerald Sun seat; also `--no-skin`) | `8 of 8 runs with equal hashes` (a timing race passes single runs by chance); `aw2dev net desync <run>` explains a failing one |
| session, lobby, rooms, rejoin, host migration, `tango-net` | `aw2dev net sim ...` / `aw2dev net matrix` (see online-dev.md); `aw2dev live lobby --players 3` | hashes equal, no stall, results right |
| save format, game rules, DS content | `python3 tools/aw2test/run.py` (see `tools/aw2test/README.md`); `tools/mixed_pack_check.sh` for pack-vs-no-pack rooms | all tests pass |
| army skins (`army_skin.rs`, `skins/*.toml`, a palette table, a trap) | `cargo test -p tango-gamesupport-aw2 --lib army_skin`, `aw2dev armyskin check --live`, `aw2dev armyskin sources`, `aw2dev test`, then `aw2dev net repeat` (2P Unranked, Emerald Sun, 8 runs), `AW2DEV_SKIN=1 aw2dev live moveview --local` and `lobby --players 3 --local`; look at `aw2dev armyskin scenario NAME` (docs/dev/army-packs.md) | check bad=0, sources prints nothing, hashes agree |
| the Emerald Sun themes (`music/es/*.m4t`, `es_music.rs`, `ds_music.rs`' table, a CO's song) | `aw2dev sound compose`, `aw2dev sound render` (listen, look at the pictures), `aw2dev test`, `aw2dev suite --only es_music`, then `aw2dev net repeat` (docs/dev/music-kit.md) | rules kept, `es_themes_are_registered` and `es_theme_plays_on_the_cos_turn_and_loops` pass, `8 of 8 runs with equal hashes` |
| a release | `aw2dev release <ver> --notes FILE --dry-run`, then docs/dev/release.md | |

A small fix the user will playtest: build, `aw2dev install-mac`, let them test. Do NOT run suites while they are playtesting (their rule).

## False-pass lessons (each one cost a day)
- **Look at the images.** A checker that passes on black frames or the wrong screen proves nothing. After `check`, open a `sheet` of the
  moment you changed.
- **Stale binaries.** aw2dev refuses to run a `target/release/tango` or example older than the newest source (`AW2DEV_ALLOW_STALE=1` to
  override). After a merge always rebuild: a whole regression once ran on a stale `aw2_script`.
- **Build stamps.** Each live run records `build` in `meta.json` (git sha, `+dirty`, binary hash) and the app logs it. Compare runs only
  when stamps match; run BOTH fog modes from the SAME build.
- **Hash lines differ before the battle** (menu phase) and agree in battle; `check --hash` judges only from the first agreement on.
- **Scenario/state cues, not fixed waits.** Pad scripts use `until COND` (docs/dev/pad-scripts.md); a fixed `wait` that is long enough on
  an idle Mac fails on a loaded one.
- **Resume, don't restart.** After a stall fix the step and continue from the stuck step; stall reports name the last passed step and the
  stuck one. (Checkpoints are planned; see the aidebug work.)
- A run that `gave_up` or never reached `SCRIPT END` is a FAIL even if the checkers on the partial frames pass (`aw2dev check` includes
  the run's `summary.json`).

## Politeness rules
- One live run at a time on this Mac: `aw2dev live` holds `~/.aw2dev/live.lock` (shared by all worktrees); a second run waits.
- Capture game windows only (the app writes its own screenshots through `TANGOAW2_RUN_DIR`; never `screencapture` the screen).
- Never close the player's running TangoAW2 (`install-mac` swaps the binary and leaves the running app open). Kill only processes under
  `devkit/work/testapp/`; `aw2dev live` does exactly that.
- Never touch `~/Documents/TangoAW2` (ROMs are copied into `devkit/work/profiles/*/data/roms`, saves/logs of the player are never read or
  written by tests).
- Public services (matchmaking, STUN, Nostr): network tools use a local signalling mock and block public endpoints; see online-dev.md.
  Plain `aw2dev live` still uses the real matchmaking server unless `--local` is on `net sim`.
- Disk: `aw2dev clean` (dry run by default), keep only ~/tangoAW2 and ~/tangoAW2-hires checked out, delete `target/` of your worktree
  when you are done, delete captures once reviewed. Nothing from the games is ever committed.
- Sound: test profiles start with volume 0.
