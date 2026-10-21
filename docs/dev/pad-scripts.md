# Pad scripts, test-poke rules and the offline harness script

Three scripting languages drive the game without a person. All are test aids, off unless asked for.

| Language | Driver | Runs against | Defined in |
|---|---|---|---|
| Pad script (`TANGOAW2_PAD_SCRIPT=<file>`) | the real app, one window = one seat | a live session (offline or netplay) | `tango/src/app/debug_aids.rs` (`parse_script`, `expand_macros`, `DebugAids::pad_keys`); conditions in `tango-gamesupport-aw2/src/online.rs` (`mailbox::condition`, `probe::store`) |
| Test-poke rules (`TANGOAW2_TEST_POKE=<file>`) | the match engine, every simulated tick | the console of every peer | `tango-gamesupport-aw2/src/test_aid.rs` (`parse`, `apply`, `run`) |
| Harness script (`aw2_room_teams <rom> <out-dir> <script>`) | an offline N-seat console, no network | `SharedLink` on one process | `tango-gamesupport-aw2/examples/aw2_room_teams.rs` (the `match p[0]` in `main`) |

`aw2_script.rs` and `aw2_netplay_script.rs` (same directory) have their own, smaller languages; the header comment of each file is their reference. `tools/aw2test` (Python) is a fourth way to drive the console; see `tools/aw2test/README.md`.

---

## 1. Pad script (`TANGOAW2_PAD_SCRIPT`)

### How it runs

- `DebugAids::from_env` reads the file, runs `expand_macros` then `parse_script`. A line that is not understood makes `parse_script` return `Err`; the app logs `pad script <path>: line N: ...: the script is not run` and runs nothing. An unreadable file is NOT logged (`read_to_string(..).ok()?`): no pad, no message.
- `app/mod.rs` subscribes a 16 ms timer (`Message::PadScriptTick`) only when a pad exists. `dispatch.rs` calls `pad_keys(session_install_seq, cond)` on each tick; the result goes to `session.set_scripted_keys`.
- Time base: wall clock x 60 frames per second (`pad.carry`). At most 30 frames are consumed per call. A press shorter than the gap between calls is kept: the keys of all frames consumed in one call are OR-ed together. When no frame is due, the previous keys are repeated (`pad.held`).
- The script starts when a session exists (`session: Option<u64>` is the session's install number). A new session number moves to the next part (`session` line, below).
- `cond` is `tango_library::online::condition` -> `tango_gamesupport_aw2::online::mailbox::condition`. It reads static probes (`probe::BITS`, `CUES`, `CURSOR_CELL`, `MAP_DEBUG`) that `probe::store(core)` refreshes on every console tick of any peer. The `read` closure only reaches a console in an offline (single-player) session; in a netplay session it is a no-op that returns zeros, so `level`, `status`, `players`, `ready` read 0 there. The other conditions use the probes and work in both.
- `cond` accepts `a|b`: `pad_keys` wraps it so that `a|b` holds if any part equals `always` or satisfies `cond` (`!` is handled inside `condition`: `!x` is `not x`).

### Key names

`A B SELECT START RIGHT LEFT UP DOWN R L`, joined with `+` for chords (`key_bits`; case-insensitive). Bits: A=1, B=2, SELECT=4, START=8, RIGHT=16, LEFT=32, UP=64, DOWN=128, R=256, L=512. An unknown key in `press`, `hold` or `seek` is a parse error.

### Ops (one per line; blank lines and lines starting with `#` are skipped)

Units are frames (60/s) unless noted. `SECONDS` are wall-clock seconds.

| Line | Behaviour | Default limit |
|---|---|---|
| `wait N` | no keys for N frames | |
| `press KEYS N` | hold KEYS N frames, then 6 idle frames (parsed as `Hold(N)` + `Wait(6)`) | |
| `hold KEYS N` | hold KEYS N frames, no trailing wait | |
| `until COND [SECONDS]` | idle (no keys) until COND holds. On timeout logs `pad script: gave up waiting for COND` and carries on; on success logs `pad script: reached COND` | 120 s |
| `seek KEYS COND [SECONDS]` | press KEYS 4 frames in every 12 until COND holds (`pad.done % 12 < 4`). Timeout: warn and carry on | 60 s |
| `label NAME` | marks a place for `jumpif` | |
| `jumpif COND NAME` | if COND holds, continue at the first `label NAME` (if no such label, falls through). Costs no frames; a loop of jumpif/press/wait is how a script reacts to state | |
| `goto X Y [SECONDS]` | walk the map cursor to cell (X,Y): left/right until `cx=X`, then up/down until `cy=Y`, direction chosen from `cxlt`/`cylt`; 4 frames pressed in 12. Needs the map cursor (battle map) | 40 s |
| `shot PATH` | save the window picture (read back from the GPU) as PNG; pushed on `script_shots`, taken by `dispatch.rs` | |
| `log TEXT` | logs `pad script: TEXT` at info | |
| `type TEXT` | type the characters into the in-game lobby typing page (`mailbox::type_chars`); `_` in TEXT becomes a space | |
| `session` | starts the script for the next session (a new install number moves `pad.part` on). Lines before the first `session` belong to the first session | |

A key-less wait (`until`, key mashing stopping) always releases the pad: while an `until` waits no key is held.

### Conditions (`CONDS` const and `mailbox::condition`)

`cond_ok` (parse time) accepts a name from `CONDS`; with `=value` the value must parse as an unsigned integer, otherwise the cond is rejected. Leading `!` is stripped before the name check (`trim_start_matches('!')`), so `!!x` also parses. `a|b` alternatives are split first and each part is checked.

Source of each one (all in `mailbox::condition`, `online.rs`; probe bits are written by `probe::store`):

| Cond | True when | Probe source |
|---|---|---|
| `always` | always (handled in `pad_keys`; `condition("always")` itself is false) | |
| `onmenu` | the ONLINE screen is up | `ONLINE_MENU` <- `online_menu::active` |
| `selectmode` | the mode-select screen is up | `SELECT_MODE` <- `campaign_menu::on_select_mode` |
| `selectmap` | SELECT MAP is up | `SELECTING` <- `survival_ui::selecting` |
| `teams` | the Teams / SELECT YOUR ARMY page is up | `TEAMS` <- `pvp::on_teams_screen` |
| `battle` | in a battle | `BATTLE` <- `pvp::in_battle` |
| `versus` | in Versus | `VERSUS` <- `pvp::in_versus` |
| `nav` | the console is walking the game's menus to the lobby / Versus SELECT MAP by itself (`NAV_GOAL` is lobby or versus and the step is not done) | `NAV` <- `navigating(core)` |
| `turnended` | the NEXT TURN screen is up (turn ended) | `TURN_ENDED` <- `pvp::turn_ended` |
| `myturn` | this window's seat has the turn (not ended) | `CUES` bit 0 |
| `banner` | NEXT TURN banner up for at least 20 ticks and this seat is the incoming mover (press A) | `CUES` bit 1 |
| `acting` | my turn, plain map, no menu/page/banner, steady for 30 ticks | `CUES` bit 2 (`fog_view::plain_map`) |
| `over` | the match is decided | `CUES` bit 3 (`result_view::decided`) |
| `mapup` | in a battle and the battle map is up (menu allowed): the opening pages are over | `CUES` bit 4 (`fog_view::phase == Map`) |
| `mypick` | map picking (UNRANKED), this seat has not picked, list up and still | `CUES` bit 5 |
| `chosen` | the map draw is made (bar shows the winner) | `CUES` bit 6 (`unranked::chosen`) |
| `rules` | the Rules screen is up after the map was chosen | `CUES` bit 7 (`unranked::rules_up`) |
| `pickturn=J` | map picking is in progress and exactly J seats have picked (`picks_made + 1` in `CUES` bits 8..11); J is a number | |
| `reconnect` | the reconnect box is showing | `hold_box::shown()` |
| `cursor=N` | the ONLINE screen's cursor is on item N (0..2) | `BITS` >> 8 (`online_menu::cursor`; 0xFF when none) |
| `level=N` | the lobby page level byte equals N (0 menu, 1 LOBBY, 2 room made, 3 typing a code, 4 room joined, 5 typing a password, 8 RESUME, 9 gamertag, 10 STATS, 11 Connection, 12 rejoin box, 13 CREATE name) | reads RAM `LEVEL` (online-session read) |
| `army=N` | the army whose turn it is is N | `BITS` >> 24 (`pvp::current_army`) |
| `maparmies=N` | the map under SELECT MAP's cursor has N armies (from the map table, 1..5) | `BITS` >> 32 (`map_armies`) |
| `status=N` | the room status byte equals N (0 none, 1 waiting, 2 connecting, 3 connected, 4 failed, 5 back) | reads RAM `STATUS` |
| `players=N` | N players on the room page | reads RAM |
| `ready=N` | N players ready | reads RAM |
| `menu=N` | the map menu's cursor byte (RAM 0x030014F0) equals N; the menu keeps its row between uses | `MAP_DEBUG` bits 40..47 |
| `onend` | the map menu's cursor is on its End item, whatever its row (cursor+1 equals the End row `pvp::END_ROW`, kept in RAM) | `MAP_DEBUG` bits 40..47 and 57..60 |
| `cx=N`, `cy=N` | the map cursor's cell x / y | `CURSOR_CELL` (RAM 0x030033E4/E6) |
| `cxlt=N`, `cxgt=N`, `cylt=N`, `cygt=N` | cursor x/y is below / above the value | same |
| `idle` | the map waits for the cursor, nothing running (`fog_view::phase == Map`) | `BITS` bit 63 |
| `!COND` | negation | |

`CONDS` lists `"!"` as a name for completeness; it is not a real cond. Gotchas: `players`, `ready`, `status`, `level` need an offline session to read (see above). `!always` is true (condition("always") is false, and `pad_keys` only special-cases the exact string `always`).

### Macros (`expand_macros`; whole line, trimmed)

| Macro | Expands to |
|---|---|
| `jump NAME` | `jumpif always NAME` |
| `onbanner` | `until banner 10` then `seek A !banner 8` (wait up to 10 s for this seat's NEXT TURN banner, press A until it is gone, up to 8 s) |
| `intro` | 15 repetitions of `jumpif mapup|over inN` / `press A 8` / `wait 50`, then `label inN` (the first turn's CO pages and DAY banner: one A a second until the map is up) |
| `endturn` | `press B 6` x2, `until acting 10`, then up to 3 tries of: `until acting 4`, `press A 8`, `wait 20`, `seek DOWN onend 6`, `press A 8`, `until !myturn 5`, `jumpif !myturn etN`, `press B 6` x3; then `label etN` |

N is a counter so labels are unique per use.

### Worked example (built from the macros above; the shipped `.txt` scripts target the harness, not this language)

Play one end-of-turn cycle in a live battle, with a picture before and after (constructed from the macro definitions; `git grep` finds the macro names only in `debug_aids.rs`; the live driver scripts that used them were kept outside the repo):

```
# wait for the battle, clear the first-turn pages, snap, end the turn
until battle 120
intro
until acting 30
shot /tmp/turn_start.png
endturn
# when it is this seat's turn again: its NEXT TURN banner (A dismisses it)
onbanner
until acting 60
shot /tmp/turn_back.png
log second turn reached
```

Typing: `type ABCD` goes through `mailbox::type_chars`, which returns false (nothing typed) when the lobby takes no typing; wait for a typing page first, e.g. `until level=3 30` in an offline session (the app itself does this with `TANGOAW2_TYPE_CODE` when `level == 3`). Two sessions in one file are separated by a bare `session` line.

---

## 2. Test-poke rules (`TANGOAW2_TEST_POKE=<file>`)

Every peer of a match must read the same file (a peer without it simulates a different match). `test_aid::apply(core, tick)` is called by the match engine through `tango_match::Link::test_aid` before each simulated tick's input (see `tango-match/src/link.rs`); on a rollback the tick is simulated again and the rule fires again. Rules are parsed once (`OnceLock`) and logged: `test-aid: N rules from <path>: this client simulates a scripted match; every peer needs the same file`.

### Line grammar (`parse`)

`#` starts a comment anywhere on the line. A line needs a literal ` do ` (with spaces); otherwise `test-aid: line N: no `do``. `WHEN do COMMAND`.

WHEN:

| Form | Fires |
|---|---|
| `at TICK` | on exactly that tick of the match (counted from the match's first tick; equal on all peers) |
| `when KEY=VALUE ...` | the first tick all keys hold, once. An unknown word logs an error but the rule is kept |

`when` keys: `army=N` (the army moving: byte 0x030033EC), `day=N` (u16 at 0x03004080), `idle` (map waits for the cursor: `fog_view::phase == Map`), `gap=N` (at least N ticks since the PREVIOUS rule in the file fired; ignored on the first rule), `tick>=N` (not before tick N). Fire-once state is kept in `FIRED`; ticks undone by a rollback are forgotten (`fired[i] >= tick` is cleared).

### Commands (`run`; numbers are decimal or `0x` hex via `num`; note `poke`'s ADDR must therefore be `0x...`)

| Command | Effect |
|---|---|
| `poke ADDR HEX` | raw bytes (hex string, 2 digits per byte) to console memory |
| `funds ARMY N` | the army's funds (`tag::player(core, army)` + write 32) |
| `meter ARMY PCT` | the army's CO meter as PCT of its CO Power price (100 = Power ready; above reaches the Super), via `bh_act5b::meter` |
| `unit ARMY KIND X Y [HP]` | a new READY unit at an empty cell. KIND is the game's number or: inf/infantry, mech, mdtank, tank, recon, apc, neotank, artillery/arty, rockets, antiair/aa, missiles, fighter, bomber, copter/bcopter, tcopter, battleship, cruiser, lander, sub (`kind_of`). HP 1..100, default 100. Slot ids: `(army-1)*stride + 1..stride-1`, stride 51 when `five::active` else 64; errors if the cell is occupied or the army has no free slot. Copies a same-kind unit's record (ammo, fuel) if one exists, else a foot-soldier-shaped default |
| `move X Y X2 Y2` | the unit at one cell to another empty cell, ready again |
| `ready X Y` | the unit at the cell may act again |
| `hp X Y N` | its hit points (clamped 1..100) |
| `kill X Y` | removes the unit (record zeroed, both unit planes cleared) |
| `capture X Y N` | the unit at the cell has N capture points (max 20) |
| `log TEXT` | a line in the log |

Every command logs `test-aid @TICK: ...`. Unknown command: `test-aid @TICK: unknown command`. Constants: map RAM base 0x0201E450, units pointer at 0x08499594, 12-byte unit records, unit planes at map +0x12 and +0x51A, row table at map +0x417A (`test_aid.rs` top).

Example (a 2-player test: give army 2 funds and a Cruiser at its turn, then ready Power for army 1):

```
at 600 do funds 2 9000
when army=2 day=1 idle gap=30 do unit 2 cruiser 3 24
when army=1 day=2 idle do meter 1 100
when army=2 tick>=5000 do log checkpoint
```

The same commands are available inside a harness script as `aid CMD...` (section 3).

---

## 3. Offline harness script (`aw2_room_teams`)

Usage: `target/release/examples/aw2_room_teams <rom> <out-dir> <script>` (build: `cargo build --release -p tango-gamesupport-aw2 --examples`). One console with N seats, no network. First non-comment line MUST be `n N` (3..5 in the header; 2 also works, see `aw2_waiting_*_2p.txt`). Blank lines and `#` lines are skipped; other lines are split on whitespace; an unknown command panics (`unknown command X`). Seats are numbered 0.. .

`TANGOAW2_DS_ROM=<nds>` boots with the Dual Strike pack; `AW2_PACK_ONLY=1` makes the match lack it (mixed-room test); see `env-aids.md` for all `AW2_*` switches.

Time is in console ticks (frames). `until` and `waitfor` take MAX in units of 10 ticks.

| Command | Behaviour |
|---|---|
| `n N` | first line: N seats (`set_players(N)`) |
| `wait N` | N ticks, nobody pressing (`keys` held by `mash` are zero by then) |
| `press SEAT KEYS [FRAMES]` | SEAT holds KEYS for FRAMES (default 4) ticks, then 6 idle ticks |
| `until COND MAX` | tick until `mailbox::condition(COND)` holds, at most MAX*10 ticks; prints `until COND @t: ok|TIMEOUT`. With `AW2_STRICT_UNTIL=1` a timeout fails the run (except `maparmies...`). Offline reads return zeros: `status/players/ready/level` are useless here; use `selectmap teams battle turnended army=N maparmies=N myturn...` |
| `shot NAME SEAT` | writes `NAME_sSEAT.bmp` (240x160 BMP) of that seat's own window and keeps it for `same`/`watch`/`region` |
| `shotall NAME` | the same for every seat |
| `phase NAME` | labels following samples (the black-run report uses it) |
| `same A B SEATS [TOL]` | the seats' pictures of shots A and B differ in at most TOL pixels (default 300). SEATS is `all` or a comma list. Failing sets the exit code to 1 at the end |
| `region A B SEATS X0 Y0 X1 Y1 [TOL]` | like `same` for a box of the 240x160 picture (default TOL 20) |
| `watch LABEL BASE TOL` / `unwatch` | from `watch` on, every tick the seats' pictures are compared with shotall BASE; `unwatch` prints the report (`AW2_DUMP` also writes the offending frames) |
| `consoleis SEATS [TOL]` | each listed seat's window shows the console's own picture (the mover's); default TOL 0 |
| `notconsole SEATS [TOL]` | none of the listed seats shows it (waiting seats never show the mover's cursor/menus) |
| `expect winner SEAT` | the seat shows the console's picture (<= 3000 px different) |
| `expect loser SEAT` | `result_view::loser` and its own DEFEAT, not the console's |
| `expect alive A,B,..` | exactly those armies remain (`result_view::alive_armies`) |
| `expect roster A,B,C` / `expect roster -` | the seats the console is played by, in order (`proxy_seat::seat_order`), match the page and room |
| `expect over` | `online::match_over` |
| `waitfor victory|over|armysel|selectmap MAX [pressA SEATS]` | tick (MAX*10 at most) until VICTORY!, match over, SELECT YOUR ARMY, or SELECT MAP; with `pressA 1,2` those seats press A 4 ticks in 60 while waiting; failing adds to the exit code |
| `goto SEAT X Y` | walk that seat's cursor to the cell: up to 40 steps of 4 pressed + 6 idle ticks; reads the cursor from RAM 0x030033E4 |
| `menuend SEAT [ITEM]` | with the map menu open: DOWN until the item at the cursor equals ITEM (default 6 = End; item numbers: CO 0, Intel 1, Options 4, Save 5, End 6 per the session notes), then A; at most 10 tries (`AW2_MENU_LOG` prints each) |
| `mash SEATS N` | for N ticks the listed seats press pseudo-random keys (new set every 3 ticks, seeded from the tick), others nothing |
| `aid CMD...` | a test-aid command on the console now (`unit`, `move`, `ready`, `hp`, `kill`, `funds`, `meter`, `capture`, `poke`, `log`; see section 2). Calls `test_aid::run` |
| `poke ADDR HEX` | 4 idle ticks, then writes bytes (ADDR is hex, `0x` optional) |
| `peek ADDR LEN` | prints LEN bytes (ADDR hex, LEN decimal) |
| `dump NAME` | writes IWRAM and EWRAM to `/tmp/dump_NAME_i.bin` and `_e.bin` |
| `vram NAME` | VRAM, palette and OAM to `<out>/NAME.vram` |
| `hash` | prints an FNV hash of EWRAM (compare two runs) |
| `fv` | prints the waiting-view state: who is watching, alive armies, decided, army, fog, main loop, phase, running procs, DISPCNT, menu |
| `status` | prints the probe bits and the army-select RAM |
| `sel` | per-seat army-select state: CO colour team partner field ready; plus the note byte |
| `rec` | the Teams record and the battle's player blocks (teams, colours, controllers) |
| `units` | every unit: id, army, kind, position, HP |
| `props ARMY` | that army's properties with their cells |
| `hq` | each army's HQ cell |
| `place ID X Y` | moves unit ID (both planes and record) to an empty cell (asserts it is empty) |
| `kill ID` | removes unit ID |
| `sprites [short]` | the sprite list the game copies to OAM and the cursor's pixel position |
| `consoleshot NAME N EVERY` | N console pictures, EVERY ticks apart, as `NAME_k.bmp` |
| `unitcolours X Y SEAT MIN_PERCENT` | the colours of the 16x16 cell (X,Y) in the console picture must appear on SEAT's window at least MIN_PERCENT as often as on the console (a moved unit is drawn in its owner's colours) |

The process exits 1 and prints `SAME CHECK FAILED` when any check failed. With `AW2_SAMPLE=N` it also prints the black-run report and exits 1 on `BLACK RUN OVER n TICKS`.

### Worked examples (from the shipped scripts)

1. Walk to the battle and check hand-off pictures, `aw2_banner_5p.txt` (excerpt; 5 seats pick maps, army, then start):

```
n 5
until maparmies=5 100          # SELECT MAP shows the 5-army map
wait 60
press 0 A
wait 20
press 1 A                      # ... seats 2,3,4 the same
until teams 100                # SELECT YOUR ARMY
wait 90
press 4 DOWN
press 4 DOWN
press 4 DOWN
press 4 A                      # each seat picks its row; then seat 0 starts
wait 300
press 0 A
until battle 300
until army=1 60
wait 400
fv
notconsole 1,2,3,4             # only seat 0 may show the console's picture
consoleis 0
```

2. A Power scene with a prepared meter, `aw2_waiting_power_2p.txt` (run with `AW2_LEAK_CHECK=1`; exit 1 if a waiting seat ever shows the mover's picture):

```
n 2
...same menu walk as above...
until army=1 60
wait 400
aid meter 1 100               # army 1's CO meter full
wait 5
press 0 B                     # clear the cursor
wait 20
press 0 A                     # map menu
wait 80
press 0 DOWN
wait 10
press 0 DOWN
wait 10
press 0 A                     # Power
wait 800
fv
```

3. Yield flow, `aw2_proxy_yield_3p.txt` (3 seats, fog on): after the battle starts, special key chords tell the console a player is gone, then `expect` checks the result:

```
until army=1 60
wait 400
press 0 UP+DOWN+LEFT+RIGHT+B 1    # seat 0 sends the YIELD word
press 1 UP+DOWN+LEFT+RIGHT+A 1    # seat 1 sends the HOST word
wait 20
wait 900
press 1 A
expect alive 2,3                  # army 1 yielded
until army=2 100
```

The shipped scripts all begin with the same prologue (`until maparmies=N 100`, an A per seat on SELECT MAP, `until teams 100`, rows picked with 3 x DOWN + A, `press 0 A` to start, `until battle 300`). Copy one and edit the tail.
