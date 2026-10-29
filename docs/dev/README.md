# tangoAW2 developer knowledge base

For AI sessions (and people) who debug, test, release and extend the game. Start with `CLAUDE.md` at the repo root, then `aw2dev --help`.
Everything durable lives in `devkit/` (tools), `docs/dev/` (this folder), `.claude/skills/` and `CLAUDE.md`; nothing important belongs in a
session scratchpad.

## Quick start
```
./aw2dev build --all                 # tango + harness examples (PATH to cargo is set for you)
./aw2dev test                        # lib tests
./aw2dev ci                          # what the GitHub checks workflow runs: cargo machete, workspace conventions, rustfmt, the test steps
./aw2dev suite                       # offline waiting-view suite, must end `suite done bad=0`
./aw2dev net sim moveview            # 2 real clients, local signalling mock, verdict: stall / hash / leak / result
./aw2dev net repeat                  # 2P Unranked with Emerald Sun, 8 runs: `8 of 8 runs with equal hashes` (a timing race passes single runs by chance)
./aw2dev live lobby --players 3 --local
./aw2dev check latest                # pass/fail JSON report (check.json) of the newest live run
./aw2dev sheet latest --around 0 --kind move --strip     # then LOOK at the PNG
./aw2dev audit text | audit maps
./aw2dev install-mac                 # to /Applications/TangoAW2.app, never closes the running game
./aw2dev release 0.8.6 --notes notes.txt --dry-run       # never pushes without --yes (needs the user's approval)
./aw2dev clean                       # dry run: what would free disk
```
Config: `devkit/config.toml` (override in `devkit/config.local.toml` or `AW2DEV_<SECTION>_<KEY>`). ROMs are read from
`~/Documents/TangoAW2/roms` and only copied into `devkit/work/profiles/*`.

## Index
| File | What |
|---|---|
| [co-kit.md](co-kit.md) | custom COs as data files: `aw2dev co` (portraits composed from the ROMs' parts + our overlays, stars and powers checked against AW2's table, Tag Powers) |
| [art-repal.md](art-repal.md) | palette replacement: `aw2dev art repal apply / extract / convert / preview / importsheet` (pictures onto a fixed palette in slot order, luma-weighted nearest colour; .gpl / .pal / PNG / `co:` / `skin:` / `army:` palettes; the CO importer's `match` key) |
| [co-verify.md](co-verify.md) | `aw2dev co verify`: every ability of the custom COs (Klaus, Aurelia, Cassius, Livia, Varro, Crumb, Clone Andy) in real battles against the specification, pass / fail table, `co sheet powers` pictures |
| [testing.md](testing.md) | what to run for which change; false-pass lessons; politeness rules |
| [online-dev.md](online-dev.md) | `aw2dev net` tools, impairment, desync workflow, soak, the signalling mock, public-service politeness |
| [architecture-online.md](architecture-online.md) | shared console, star topology, HostAgg, waiting view and allowlist, migration, rejoin, UNRANKED, sim_version rules |
| [ram-map.md](ram-map.md) | EWRAM/IWRAM addresses and what they mean; the registration rule |
| [rom-routines.md](rom-routines.md) | ROM procs, hooks, menus, message boxes, sound ids |
| [pad-scripts.md](pad-scripts.md) | `TANGOAW2_PAD_SCRIPT` cues/ops, `TANGOAW2_TEST_POKE`, the harness script language |
| [env-aids.md](env-aids.md) | every `TANGOAW2_*` / `AW2_*` environment aid |
| [maps.md](maps.md) | map format and pipeline, ids and slots, the pre-deployed rule, how to add a map |
| [map-design.md](map-design.md) | `aw2dev maps study`: the map-design principles measured on AWBW's Hall of Fame against AW2, Dual Strike and our campaigns; the rules MD01..MD08 |
| [map-lint.md](map-lint.md) | `aw2dev maps lint`: rivers, bridges, puddles, joins, units, reachability; what AW2 and Dual Strike allow; before / after pictures |
| [stages.md](stages.md) | a custom campaign's mission that moves on, in the same battle, to another map (`Action::NextStage`, `MissionDef::stages`): carry-over, five-army, suspend, determinism; `aw2dev stage next / show` |
| [five-suspend.md](five-suspend.md) | a five-army battle saved from the map menu and continued: the record after AW2's block, the Flash and RAM cost; `aw2dev save inspect` |
| [playthrough.md](playthrough.md) | `aw2dev campaign playthrough bh2 N`: a mission played to its end in the harness, a report and a contact sheet |
| [bh2-maps.md](bh2-maps.md) | the BH2 Campaign's maps: specs, `aw2dev maps gen --campaign bh2`, lint (IV01: inventions are Black Hole's), pictures, feature coverage, world-map flags, Act I |
| [worldmap.md](worldmap.md) | `aw2dev worldmap convert / preview / check`: the picture world map (`WorldArt::Picture`): the owner's picture to GBA tiles, nine palettes, region masks per nation, conquest re-tint, budgets, the live harness test |
| [campaign-scenes.md](campaign-scenes.md) | `aw2dev campaign` / `aw2dev sound`: how AW2 presents story scenes, the BH Campaign's prologue card, songs per scene, Sturm's scenes |
| [es-campaign.md](es-campaign.md) | the Emerald Sun Campaign: files, rules, the kit (`maps gen`, `campaign sheets / sim / difficulty / check`, the dialogue lint), the five COs |
| [asuka.md](asuka.md) | Asuka, CO 92: Sonja's kit with Hawke's Black Wave / Black Storm, 4 / 8 stars, where she is (every Versus list, not the Emerald Sun Campaign), how she was verified |
| [music-kit.md](music-kit.md) | the Emerald Sun COs' own themes: songs as text compiled to AW2's sound engine, played with AW2's own voices; `aw2dev sound compose / render / loopcheck / levels / stems / pitchcheck / voices / dump` |
| [ds-pack.md](ds-pack.md) | how Dual Strike content is converted and gated |
| [army-packs.md](army-packs.md) | army skins: Emerald Sun, the sixth army (a data file on one of AW2's colours), what it patches, `aw2dev armyskin`, adding the next army |
| [decomp.md](decomp.md) | using ~/advance-wars-dual-strike-decomp (CC0) for DS rules |
| [graphics.md](graphics.md) | `aw2dev gfx`: detect and debug garbled graphics, the catalogue of screens, past bugs and the detector for each |
| [release.md](release.md) | the release checklist |
Older long-form notes: `ARCHITECTURE.md`, `docs/AW2.md` (parts are stale; the docs here follow the code), `docs/MAPS.md`,
`tools/aw2test/README.md`.

## Tool map (devkit/aw2/)
`cli.py` argument parsing; `live.py` live engine (Spec, run, events); `scenarios.py` the pad-op helpers and every scenario (`aw2dev live --list`);
`profiles.py` test profiles + test app bundle; `harness.py`, `suite.py` offline; `check.py`, `sheet.py`, `runlib.py` analysis of run dirs;
`net.py`, `signal_mock.py`, `wsmini.py`, `endpoints.py` online tools; `build.py`, `install.py`, `release.py`, `clean.py`, `audit.py`.
Checkers outside devkit that aw2dev calls: `tools/cam_check.py`, `pic_check.py`, `hud_check.py`, `tools/aw2test/`.

## Adding to the devkit
Standing rule: every new feature or content type adds its command/scenario/checker, a docs/dev entry, a skill (or an update) and a suite regression test in the same work; see `devkit/CONTRIBUTING-KIT.md`, `aw2dev kit new-command|new-skill|check`. Details:
New scenario = a function in `scenarios.py` (`SCEN`), nothing else. New checker = a function in `check.py` registered in `CHECKS`.
Keep Python 3 stdlib + Pillow (+ numpy, already used by the checkers). Never hard-code absolute paths; use `cfg.py`.
Scenarios coordinate on the first 2P map (Bean Island): every seat proposes it (`--picks` or `AW2DEV_PICK_DOWN` change that), because the draw between
proposals is random. `hq5` passes (5 seats; army 4 is eliminated by army 3's HQ capture, army 3 by army 1's; hash/leak/mover/cam/black PASS); `hq4` now runs to the end (every army takes its turn, 4P team poke removed) but its two scripted HQ captures do not happen (the Four Corners HQ cells in the poke are not the enemies': unresolved). `big5`
is blocked: a live 5P room's pick list shows 9 maps and no `5P Predeploy` tab, so Pentagon Atoll (audit: pack, pre-deployed) cannot be proposed (see online-dev.md).
