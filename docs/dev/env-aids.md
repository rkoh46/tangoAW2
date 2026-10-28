# Environment variables

Every `TANGOAW2_*` and `AW2_*` variable read by the repository, found by scanning every tracked file (the scan: any token `TANGOAW2_*` / `AW2_*` on a line that reads the environment; tokens that are only Rust constants, pack keys or Python names were excluded, e.g. `AW2_COS`, `AW2_TABLE`, `AW2_SHEET`, `AW2_METATILES`, `AW2_ARROWS`). Unless said otherwise a variable counts as set when it exists (`var_os(..).is_some()`); "= 1" means the code compares to the string `1`.

Naming: `TANGOAW2_*` are read by the app or the game-support library; `AW2_*` are read by the offline examples (harness binaries), and a few debug logs in `tango-gamesupport-aw2/src` and `tango-backend-mgba`. A third family, `AW2TEST_*`, belongs to the Python harness `tools/aw2test` (paths, opt-in test sets); it is documented in `tools/aw2test/README.md` (`AW2TEST_ROM`, `AW2TEST_BASE_SAVE`, `AW2TEST_OUT`, `AW2TEST_RUNNER_DIR`, `AW2TEST_COMPARE_RUNNER`, `AW2TEST_BH_*`, `AW2TEST_CPUAI_*`, `AW2TEST_OBJ_SURVEY`, ...); list them with `grep -rhoE 'AW2TEST_[A-Z_]+' tools | sort -u`.

Pass variables to a Simulator app as `SIMCTL_CHILD_<name>` (`ios/README.md`).

## 1. Profile and run

| Name | What it does | Read in | Values |
|---|---|---|---|
| `TANGOAW2_PROFILE` | Puts config, cache and a fresh install's data under `<dir>` instead of the platform dirs, so two copies run on one machine as two players | `tango/src/config.rs` (`profile_dir`, `config_dir`) | directory path |
| `TANGOAW2_AUTOSTART` | After the library loads: `offline` presses Play offline; `settings`, `settings:graphics`, `replays` open that tab; `link:<code>` (or `link:/host`, `link:/connect <addr>`) fills the link code and presses Fight, then the lobby readies itself 3 s after it settles. An UNRANKED match the app crashed out of takes precedence unless the value is `offline` | `tango/src/app/library.rs`, `tango/src/app/lobby.rs` (auto ready) | see left |
| `TANGOAW2_BOOT_LOBBY` | With `TANGOAW2_AUTOSTART=offline`: the console walks to the ONLINE LOBBY menu by itself (`online::boot_to_lobby`) | `tango/src/app/library.rs` | `1` |
| `TANGOAW2_ONLINE_CODE` | Fixes the room code when this client hosts (instead of a random `mailbox::new_code`) | `tango/src/app/online.rs` (`online_request`, two sites) | code string |
| `TANGOAW2_TYPE_CODE` | Types the code (then Enter) into the lobby's code page when the page level is 3 (a client that joins) | `tango/src/app/online.rs` | code string |
| `TANGOAW2_JOIN` | iOS only: stands in for the `join <link code>` command | `tango/src/main.rs` | link code |
| `TANGOAW2_NO_CONTENT` | Pretends this client has no shared Dual Strike content: `lobby_pack()` is false and the lobby settings carry `content: false` (the shared-content bit is then not set by the room; tests the mixed-room path) | `tango/src/app/online.rs` (`lobby_pack`, settings build) | any (is_err check: set = off) |
| `TANGOAW2_PICK_SECONDS` | Shortens the UNRANKED map-pick timer (default 120 s) for tests; must be equal on every client | `tango-gamesupport-aw2/src/unranked.rs` (`pick_frames`) | integer seconds |
| `TANGOAW2_DS_ROM` | Path of a Dual Strike `.nds` (or a saved import) used as the pack/art source when the ROMs folder scan has none. Also the switch the examples and `tools/aw2test` use to run "with the pack" | `ds_pack.rs` `pack`, `ds_art.rs` `art`, `ds_*`, `survival_maps.rs`, `onyx.rs`, `ally_posture.rs` and every example; Python: `tools/aw2test/aw2test/paths.py` | file path |
| `TANGOAW2_AW2_ROM` | Path of the AW2 ROM for `#[ignore]` tests and DS art checks (`ds_unit_art`, `ds_co_art`, `co_new`, `tag_extras`, `bh_act2/3/5b` tests) | `tango-gamesupport-aw2/src/*` (tests) | file path |
| `TANGOAW2_OLD_PACK` | A pack saved by an older tangoAW2 (magic `TAW2DSPK`), for the pack-update test | `tango-library/tests/ds_pack_common/mod.rs` | file path |
| `TANGOAW2_ORIENTATION` | iOS Simulator: `landscape` or `portrait` | `tango/src/platform/ios/bridge.m` | `landscape`, `portrait` |
| `TANGOAW2_TOUCH_SCRIPT` | iOS Simulator: reads touches from a file (`tap X Y`, `down N X Y`, `up N X Y`, `wait MS`, in points) | `ios/touch_mouse.rs` | file path |
| `TANGOAW2_BUILD` | COMPILE-TIME, not a run-time variable: `build.rs` sets it to the short git SHA, plus `+changes` when the tree is dirty; logged at start and written into `meta_s<k>.json` | `tango/build.rs`, `tango/src/main.rs`, `debug_aids.rs` | set by cargo |

## 2. Test drivers

| Name | What it does | Read in | Values |
|---|---|---|---|
| `TANGOAW2_PAD_SCRIPT` | Pad script played into the session (see `pad-scripts.md`) | `tango/src/app/debug_aids.rs` (`from_env`) | file path |
| `TANGOAW2_SCREENSHOTS` | Saves the window picture (GPU read-back, no screen-recording permission) at times after launch | `debug_aids.rs` | `seconds:path,seconds:path` |
| `TANGOAW2_SCREENSHOT_EXIT` | Quit after the last scheduled screenshot | `debug_aids.rs` | `1` |
| `TANGOAW2_RUN_DIR` | Enables the run dump: `meta_s<k>.json` (build stamp, start on the wall clock, pid), steady frames `s<k>_<NNNN>.png` with `shots_s<k>.jsonl` sidecar (file, ms, console tick), and `state_s<k>.jsonl` (10 Hz state, `act` events, `hash` lines, `keys` lines). Use a fresh directory per run | `debug_aids.rs` (`run_from_env`), `tango-gamesupport-aw2/src/run_dump.rs` | directory |
| `TANGOAW2_RUN_SEAT` | The seat number k in the file names (default 0) | `debug_aids.rs`, `run_dump.rs` | integer |
| `TANGOAW2_RUN_SHOT_HZ` | Steady-frame rate (default 1; above 1 Hz a dedicated timer fires every half period) | `debug_aids.rs` | number |
| `TANGOAW2_DUMP_FRAME` | Keeps the console's IWRAM/EWRAM at that frame as `ram_s<k>_<frame>_i.bin` / `_e.bin` in the run dir (needs `TANGOAW2_RUN_DIR` and `TANGOAW2_RUN_SEAT`); frames are the hash frames (multiples of 60), or any frame when it is a range `A-B`: then every frame of the range is hashed (with `TANGOAW2_HASH_PARTS`) and dumped, the way to find the first frame a divergence starts at | `run_dump.rs` | frame number or `A-B` |
| `TANGOAW2_HASH_PARTS` | Adds `parts` to each `hash` line: a 16-bit hash of every 4 KiB of IWRAM then EWRAM, to find where two peers differ | `run_dump.rs` | any (set) |
| `TANGOAW2_TEST_POKE` | Rule file applied to every peer's simulation (see `pad-scripts.md` section 2) | `tango-gamesupport-aw2/src/test_aid.rs` | file path |
| `TANGOAW2_BH_WORLDMAP` | The BH Campaign plays on a picture world map (`WorldArt::Picture`) in place of AW2's: `bh2` = the BH2 picture, each mission's flag on the picture's dummy flag places in order (Orange Star 7, Blue Moon 7, Green Earth 10, Yellow Comet 5, Ashen Shelf 2); a nation turns Black Hole's colours when all missions placed in it are won. Dev only, until the BH2 Campaign has missions. Harness: `tools/aw2test` `-k bh_picture_map` | `campaign_model.rs` `dev_picture` | `bh2` |
| `TANGOAW2_BH_FEATURES` | Plays a test campaign instead of the BH Campaign: `inventions` = the CPU-vs-human-inventions mission, any other value = `features_def` (exercises the format's fields). Not shipped content | `bh_campaign.rs` `load` | `inventions` or any |
| `TANGOAW2_BH_ROLE` | Forces the AI role byte of every non-player unit in BH act 5b missions | `bh_act5b.rs` | integer (u8) |
| `TANGOAW2_BH_STILL` | The computer's armies hold and have no funds (review pictures show the deployment as designed) | `bh_act5b.rs` (`still`) | any (set) |
| `TANGOAW2_FAKE_HOLD` | Shows the reconnect/hold box without a match; the seconds count down | `hold_box.rs` | `<name>:<seconds>` |
| `TANGOAW2_FAKE_MIGRATION` | Shows the host-migration box; `You` = this player | `hold_box.rs` | gamertag |
| `TANGOAW2_PRIMING_DEBUG` | Holds a "priming" notice over any session (screenshots) | `tango/src/session/view/priming.rs` | `match`, `peer`, `replay`, `failed` |
| `TANGOAW2_MENU_OUT` | A test writes the DS map menu rows as raw RGBA to this file | `ds_menus.rs` (test) | file path |

## 3. Logging

| Name | What it does | Read in | Values |
|---|---|---|---|
| `TANGOAW2_ONLINE_LOG` | Once a second while a PvpSession runs logs `match state: probe <bits> list <bits> map <bits>` (the `probe` statics) | `tango/src/app/online.rs` | `1` |
| `TANGOAW2_PACE_LOG` | Every 120 ticks logs the clock sync's inputs and result (`pace: tick .. skew .. balance .. slowdown ..`) | `tango-session/src/pvp/driver.rs` | `1` |
| `TANGOAW2_STATE_LOG` | Every 120 confirmed ticks logs FNV hashes of IWRAM and EWRAM, to compare peers | `tango-session/src/pvp/driver.rs` | `1` |
| `TANGOAW2_FPS_LOG` | Frame-rate counters (emulated frames, UI updates, redraws) every 5 s at info; on by default | `tango/src/perf.rs` | `0` silences |
| `TANGOAW2_INPUT_LOG` | Logs the keys of the seats whose input the merge drops, and the cursor/owned cells (`fog_view::log_cells`) | `online.rs` (`input_log_on`), `fog_view.rs` | `1` |
| `TANGOAW2_BATTLE_LOG` | `eprintln` for every block of a DS battle picture that did not fit (tests count them) | `ds_battle.rs` (`dropped`) | any (set) |
| `TANGOAW2_CO_PAGE_LOG` | Appends what the DS CO page lists to this file | `ds_co_page.rs` | file path |
| `TANGOAW2_BH_LOG` | File the Black Hole factory's decisions are appended to (`.bhlog` in `tools/aw2test`) | `bh_factory.rs` | file path |
| `TANGOAW2_BH_LOG_ALL` | With `TANGOAW2_BH_LOG`: also every candidate unit with its value and reason | `bh_factory.rs` | any (set) |
| `AW2_BUSY_LOG` | Each distinct set of running procs that makes the waiting view's phase Busy, once | `fog_view.rs` `log_busy` | `1`/set |
| `AW2_PROC_LOG` | Prints the running procs whenever they change (phase decision) | `fog_view.rs` | set |
| `AW2_CONSOLE_PROCS` | The console's own running procs whenever they change (`pvp.rs`; harness also) | `pvp.rs`, `examples/aw2_room_teams.rs` | set |
| `AW2_CAM_LOG` | Waiting-view camera lines (`cam seat`, `camend`); the harness adds `concam tick .. px (x, y)` (the console's own camera) and, with the value `ticks`, `tickmark N` lines. `tools/cam_check.py` reads the log | `fog_view.rs`, `aw2_room_teams.rs` | set; `ticks` |
| `AW2_PAL_DEBUG` | Palette bank diffs of the waiting view's refresh | `fog_view.rs` | set |
| `AW2_VIEW_DEBUG` | Waiting windows log what they are made from (twice a second), plus view errors | `tango-backend-mgba/src/shared.rs`, `fog_view.rs` | set |
| `AW2_PRIVATE_LOG` | Per-seat state of the private SELECT MAP view | `unranked.rs` `private_view` | set |
| `AW2_PROXY_LOG` | Logs each key tap the proxy seat (yielding seat) injects with cursor and menu state | `proxy_seat.rs` | set |
| `AW2_TRAP_LOG` | Logs calls of candidate camera routines (find who scrolls the map) | `pvp.rs` `traps` | set |
| `AW2_FIVE_LOG` | Logs every five-army hook hit (address, r0-r2, lr) | `five.rs` `run` | set |
| `TANGOAW2_TILT_LOG` | File that DS-tilt check output (`dbg_line`) is appended to (also stderr); `aw2_script.rs` also writes to it | `ds_tilt.rs`, `examples/aw2_script.rs` | file path |
| `TANGOAW2_TILT_CAM_LOG` | Tilt scroll registers per frame | `ds_tilt.rs` | set |
| `TANGOAW2_TILT_SKIP_LOG` | Logs when BG3 is parked away from the camera | `ds_tilt.rs` | set |
| `TANGOAW2_TILT_PLAN_LOG` | Logs per-object lines while the tilt renderer builds its object plan | `ds_tilt.rs` | set |
| `TANGOAW2_TILT_NO_GROUNDCHECK` | Tilt even where the RAM-drawn ground differs from BG3 (a test boot from a checkpoint: the sea's palette is not the live one); the ground's colours may be off, the units and buildings are what is looked at | `ds_tilt.rs` | `1` |
| `TANGOAW2_TILT_BOARD_LOG` | Logs board-sprite white pixel counts | `ds_tilt.rs` | set |
| `TANGOAW2_TILT_LEAK_LOG` | Logs pixels the console picture keeps (HUD) although an effect blends over the ground | `ds_tilt.rs` | set |
| `TANGOAW2_TILT_US_LOG` | Every tilted picture's time in microseconds | `ds_tilt.rs` | set |
| `AW2_LOG` | Log level of the stack's own logs in the two-peer network example (`error|warn|info|debug`, default warn) | `tango-session/examples/aw2_direct_netplay.rs` | level |

## 4. Harness (offline examples; `aw2_room_teams` unless noted)

| Name | What it does | Read in | Values |
|---|---|---|---|
| `AW2_SAMPLE` | Every N ticks every seat's window is sampled for blackness; at the end prints the longest black run per seat and phase and exits 1 if one exceeds `AW2_MAX_BLACK` ticks. Also enables the views that `tools/cam_check.py` and `pic_check.py` read | `aw2_room_teams.rs` | N (default off) |
| `AW2_MAX_BLACK` | The black-run limit in ticks (default 20) | same | integer |
| `AW2_DUMP` | Directory: every sampled frame as `t<TICK, 6 digits>_s<SEAT>.bmp` (`_BLACK` before `.bmp` on black ones) | same | directory |
| `AW2_DUMP_FROM`, `AW2_DUMP_TO` | Restrict the dump to ticks in `[from, to)` | same | tick numbers |
| `AW2_LEAK_CHECK` | Every tick no watching seat may show the console's (the mover's) picture; also checks the power cut-in and tag screens; prints `leak check: ..` and exits 1 on any leak | same | set |
| `AW2_STRICT_UNTIL` | An `until` that times out fails the run (except `maparmies`) | same | set |
| `AW2_PACK_ONLY` | The peer HAS the pack but the match does not (the `SHARED_ART` bit is cleared): a room with a player who has no pack. Used by `tools/mixed_pack_check.sh` | same | set |
| `AW2_HASH_LOG` | File: one line per tick of FNV hashes of IWRAM/EWRAM (and every 30 ticks ROM, VRAM, palette, OAM); diff a pack run against a no-pack run, they must be equal | same, `tools/mixed_pack_check.sh` | file path |
| `AW2_RAM_DUMP`, `AW2_RAM_DIR` | At that tick, write ROM, VRAM, palette, OAM, IWRAM, EWRAM as `<name>_<tick>.bin` into the dir | same | tick; directory |
| `AW2_MEMSCAN` | `from-to`: IWRAM and EWRAM every tick in the range to `/tmp/memscan/i<t>.bin`, `e<t>.bin` | same | `A-B` |
| `AW2_WATCH_LOG` | `from-to`: what the game says about the waiting seats' pictures, per tick | same | `A-B` |
| `AW2_VRAMDIFF` | `A-B`: VRAM tiles and palette entries that changed since the previous tick | same | `A-B` |
| `AW2_TRACE` | In `aw2_room_teams`: `A-B` tick range, prints a state line per tick (army, menu, keys, main loop, phase, display registers, procs). In `aw2_script` / `tools/aw2test`: a FILE of ROM addresses; each time the game reaches one it prints a `trap` line | `aw2_room_teams.rs`, `aw2_script.rs`, `tools/aw2test/aw2test/emu.py` | range / file |
| `AW2_MERGE_CHECK` | Prints which seat's keys the console would take now (`online::merge`) | `aw2_room_teams.rs` | set |
| `AW2_MENU_LOG` | `menuend` prints each menu cursor and item list | same | set |
| `AW2_RESTORE_BANKS` | Comma list of palette banks (default 8..15, the unit banks) the waiting view puts back from the console | `fog_view.rs` `banks_env` | `8,9,..` |
| `AW2_DS` | Listed in the usage text of `aw2_room_teams`; the code uses `TANGOAW2_DS_ROM` | `aw2_room_teams.rs` (comment) | n/a |
| `AW2_DS_PACK` | Loads the pack (`ds_pack::pack()`) before the run | `examples/aw2_offline_tabs.rs` | set |
| `AW2_SHARED_ART` | Boots the match with the `SHARED_ART` bit: both peers have the pack | `aw2_offline_tabs`, `aw2_mapsel_preview`, `aw2_netplay_script`, `aw2_waiting_view`; `tools/aw2test/aw2test/harness.py` | set |
| `AW2_ONLINE` | `aw2_netplay_script`: a match made in the in-game lobby (boots to Versus SELECT MAP; sets `ONLINE_MATCH`) | `aw2_netplay_script.rs`, `tools/aw2test/turn_lock/run.sh`, `yield/run.sh` | `1` |
| `AW2_UNRANKED` | `aw2_netplay_script`: UNRANKED match (implies `AW2_ONLINE`); the value `guest` plays the guest's proposed map, anything else the host's | `aw2_netplay_script.rs` | `host`, `guest` |
| `AW2_NET_DELAY` | `aw2_netplay_script`: the fake wire's one-way delay `base,spread` in ticks (default 7,4) | same | `B,S` |
| `AW2_TILT` | `aw2_netplay_script`, `aw2_waiting_view`: switch the DS tilt on (needs the pack) | same | `1` |
| `AW2_TIMELINE` | `aw2_netplay_script`: file for the resolved script (one line per tick with both seats' keys, `# shot` marks) for `aw2_direct_netplay --timeline` | same | file path |
| `AW2_BOOT_LOBBY` | `aw2_script`: console boots to the ONLINE LOBBY menu | `aw2_script.rs` | `1` |
| `AW2_LIST` | `aw2_mapsel_preview`: prints `online_maps::list(core, n, pre)` for 2..5 players, plain and pre-deployed | `aw2_mapsel_preview.rs` | set |

## 5. Rendering (DS tilt and graphics)

| Name | What it does | Read in | Values |
|---|---|---|---|
| `TANGOAW2_DS_GRAPHICS` | Turns the DS graphics (unit art, HUD, power scenes) on for tests that have no settings (`preview_env`) | `ds_graphics.rs` | `1` |
| `TANGOAW2_TILT` | Turns the DS tilted map on (`ds_tilt::enabled`) for the test runner | `ds_tilt.rs` | `1` |
| `TANGOAW2_TILT_SCALE` | Fixes the tilted picture's scale (clamped 1..8) instead of the host/adaptive one | `ds_tilt.rs` `hires_scale`, `adaptive_scale` | 1..8 |
| `TANGOAW2_TILT_ADAPT` | With `TANGOAW2_TILT_SCALE`: keep adaptive scaling on (otherwise the scale is fixed) | `ds_tilt.rs` | `1` |
| `TANGOAW2_TILT_CAM` | Camera parameters: comma list `focal,pitch,height,cx,cy,bias_x,bias_y,foot_drop,terrain_drop,prop_drop` (empty field keeps the default) | `ds_tilt.rs` `cp` | floats |
| `TANGOAW2_TILT_SNAP` | Camera follows without easing | `ds_tilt.rs` | `1` |
| `TANGOAW2_TILT_TIME` | Times each tilted picture; logs a `ds_tilt:` line with mean and worst every 120 pictures | `ds_tilt.rs` | `1` |
| `TANGOAW2_TILT_THREADS` | Worker threads of the tilt pool (default 3; 0 = none) | `ds_tilt.rs` `run_in_pool` | integer |
| `TANGOAW2_TILT_NO_RAM_MOVER` | Do not find the moving unit from RAM | `ds_tilt.rs` | `1` |
| `TANGOAW2_TILT_CONSOLE_UNITS` | Units in the console's window are drawn from its plane (old rule), debug | `ds_tilt.rs` | `1` |
| `TANGOAW2_TILT_CHECK` | Enables the tilt's debug self-checks (unit mirroring, sprite plan checks), reported through `dbg_line` | `ds_tilt.rs` | `1` |
| `TANGOAW2_TILT_OWNER_DUMP` | File: PPM of the pixels the console picture keeps, written each frame | `ds_tilt.rs` | file path |

## 6. Network

| Name | What it does | Read in | Values |
|---|---|---|---|
| `TANGOAW2_FORCE_RELAY` | `1` sends every connection through the TURN relay, `0` forbids the relay, whatever the setting says | `tango/src/config.rs` `RelayMode::use_relay` | `1`, `0` |
| `TANGOAW2_NET_IMPAIR` | Injects latency, jitter and loss into the data path (read once; logged as a warning) | `tango-net/src/impair.rs` `Impairment::from_env` | `latency_ms,jitter_ms,loss_pct` |
| `TANGOAW2_BLOCK_ENDPOINTS` | Any signaling/STUN/TURN/Nostr endpoint containing one of these substrings fails at once | `tango-net/src/endpoints.rs` `test_blocked` | `a,b` |
| `TANGOAW2_EXTRA_SIGNALING`, `_STUN`, `_TURN`, `_NOSTR` | Extra endpoints appended to the pools (hidden) | `tango-net/src/endpoints.rs` (`with_extra`, `env_list`) | comma lists |
| `TANGOAW2_LOBBY_RELAYS` | Relays used by the lobby list instead of the built-in `netplay::browse::RELAYS` | `tango/src/app/online.rs` `lobby_relays` | comma list |

## Typical combinations

- Two local players: two terminals, `TANGOAW2_PROFILE=/tmp/p1` and `/tmp/p2`; host `TANGOAW2_AUTOSTART=link:/host`, other `TANGOAW2_AUTOSTART=link:/connect 127.0.0.1` (ios README), or `TANGOAW2_ONLINE_CODE` on the host with `TANGOAW2_TYPE_CODE` on the guest.
- A recorded live run: `TANGOAW2_RUN_DIR=<fresh>`, `TANGOAW2_RUN_SEAT=<k>`, `TANGOAW2_RUN_SHOT_HZ=2`, plus a `TANGOAW2_PAD_SCRIPT` and, for setups, the same `TANGOAW2_TEST_POKE` file on every client; rebuild first so build stamps match across clients.
- Desync hunt: `TANGOAW2_RUN_DIR` + `TANGOAW2_HASH_PARTS=1` on both peers, compare the `hash` lines of `state_s<k>.jsonl` (`parts` shows which 4 KiB differ), `TANGOAW2_DUMP_FRAME=<frame>` (or a range `A-B`) for the RAM; or `TANGOAW2_STATE_LOG=1`.
- Black-frame / leak regression (harness): `AW2_SAMPLE=1 AW2_LEAK_CHECK=1 aw2_room_teams <rom> <out> <script>`; add `AW2_DUMP=<dir>` to keep frames for `tools/pic_check.py` and `tools/hud_check.py`.
- Mixed pack room: `tools/mixed_pack_check.sh <aw2.gba> <ds.nds> <script> [out]` (sets `AW2_PACK_ONLY`, `AW2_HASH_LOG`, `TANGOAW2_DS_ROM`).

## Army skins

| Aid | Effect |
|---|---|
| `AW2_LZ_LOG=1` | logs every LZ77 decompression the game starts (`lz src ... dst ... lr ...`; `army_skin::traps`): where its sheets and pictures come from (the battle figures were found with it) |
| `AW2_PAL_LOG=1` | logs every palette the game loads (`palload src ... off ... size ... lr ...`; `army_skin::traps`): where an army's colours come from (`aw2dev armyskin sources` automates it) |
| `AW2DEV_SKIN=1` | `aw2dev live ...`: seat 0 picks Emerald Sun on the army page (docs/dev/army-packs.md) |
| `aid done X Y` | test aid (`TANGOAW2_TEST_POKE` / harness `aid`): the unit at the cell has acted (greyed) |
| harness `cos` | prints the Teams screen's CO list (index: id name), for poking a seat's CO |

- `TANGOAW2_ES_MUSIC=<dir>`: reads the Emerald Sun themes from `<dir>/<name>.m4t` (klaus, aurelia, cassius, livia, varro) instead of the text built into the app, so a song can be rewritten and heard without a rebuild (`aw2dev sound render --dir`, docs/dev/music-kit.md). A test aid: both peers of a match must agree (or not set it).
- `TANGOAW2_ES_VARRO=1`: lists Varro (id 90, the Emerald Sun boss, on no list otherwise) in Versus for the CO checkers (`co_new::listed`); both peers must agree.
- `TANGOAW2_ES_VERSUS=1`: puts Emerald Sun's four COs (Klaus, Aurelia, Cassius, Livia: ids 86..89, `es_cos.rs`) in the game with the Dual Strike pack: Andy's numbers under their names, their own art, name, texts and quotes. Now a no-op: the four are always in Versus (0.8.8; Varro, the boss with a placeholder face, stays out); kept so older scripts still run. `aw2dev co portrait ingame` sets it.
