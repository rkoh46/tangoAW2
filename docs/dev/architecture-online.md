# Online architecture (shared console, rooms, waiting views)

Facts verified against the tree at branch `devkit` (sim_version 25, app 0.8.5). Paths are relative to the repo root. Where a
doc and the code disagree, the code was followed. Companion files: `ram-map.md` (addresses), `rom-routines.md` (ROM procs and hooks).

## 1. The model in one paragraph

Advance Wars 2's multiplayer is hot-seat, so netplay is **one mGBA console that every peer simulates**, fed by one joypad word
per tick built from every seat's rollback-confirmed input (`tango-backend-mgba/src/shared.rs`, `SharedGame::merge`). A room has
2 to 5 players (`tango_match::MAX_SEATS = 5`, `tango-match/src/engine.rs`). Topology is a **star**: each guest has one link, to
the host (`tango-lobby/src/room.rs`, `serve_guest` / `guest_session`); guests never connect to each other. All game state
(including every online UI state) lives in console RAM so rollback, savestates, replays and rejoin carry it. Anything a player
sees that must differ per seat (fog, private map picks, DEFEAT vs VICTORY) is **presentation only**, made on a scratch copy
of the console after the tick (`Scratch` in `shared.rs`; `SharedGame::view_as`).

## 2. Crates and what they own

| Crate / file | Role online |
|---|---|
| `tango-gamesupport-aw2/src/pvp.rs` `impl SharedGame for Aw2` | Everything game-specific: `sim_version`, `merge`, `seat_keys`, `proxy_keys`, `before_tick`, `watching`, `view_as`, `seats_out`, `seat_order`, `overlay`, `boot_more`, `match_over`, `traps`, `describe`. |
| `tango-backend-mgba/src/shared.rs` | The shared-console engine: `SharedGame` trait, `Scratch` trait (scratch console, private consoles, kept console), `SharedBackend::sim_version` = `(SHARED_SIM_VERSION 0x5a00 << 16) | game.sim_version()`. |
| `tango-match` (`link.rs`, `engine.rs`, `lib.rs`, `suspend.rs`) | `Link` trait (`tick_n`, `snapshot`, `seats_out`, `peek`/`poke`), `Match` (getgud rollback; checkpoints every 30 ticks, 12 kept), `HostInput { keys, touch, extra: [u16;3] }` (the one remote input of a >2-player peer carries the other seats' words in `extra`; `engine::seat_inputs`), `keys::command` (command words), `SuspendedMatch`. |
| `tango-session/src/pvp/` | `setup.rs` builds the session (`players = room.players.len().clamp(2, MAX_SEATS)`); `driver.rs` boots, advances, `HostAgg`, `TickLog`, hold box, `suspend_if_cut_short`; `supervisor.rs` receive pump, reconnect, stall/silence trips, `seat_yields`, `tell_others`; `migrate.rs` host migration; `silence.rs` 5 s silence watch; `recording.rs` replay writer; `mod.rs` `EndState` (holds, gone, seats_out, rejoin flags), frame-delay rules. |
| `tango-net` | Transport: `open_channels`, `link.rs` (`Link::reconnect`, `RECONNECT_*` timeouts), `data.rs` (in-match unreliable channel, `Input { joyflags, touch, tick_advantage, extra, others }`, `RECONNECT_QUEUE_LENGTH`), `endpoints.rs` (signalling/STUN/TURN/Nostr relay lists, health table, backoff), `impair.rs` (debug latency/loss). |
| `tango-net-protocol` | Wire: `control.rs` (`RoomMsg`, `RoomJoin`, `RoomRoster`, `RoomStart`, `RoomMigrate*`, `GameInfo.sim_version`, `SHARED_CONTENT 0x80`, `ROOM_HOST 0x40`, `UNRANKED_PICK_GUEST 0x04`), `derive.rs` (`derive_reconnect_session_id`, `derive_migration_session_id`, `derive_rejoin_code`), `PROTOCOL_VERSION = 0x56`. |
| `tango-lobby` | `room.rs` (rooms of up to 5, `RoomMsg` conversation, `Room` handle polled by the app, `room_session` = `tangoaw2-room-<code lowercase>`), `unranked.rs` (pool pairing, `unranked_session(sim_version)` = `tangoaw2-unranked-v1-s<sim_version>`), `browse.rs` (public lobby list on Nostr relays, kind 30078, tag `tangoaw2-lobby-v1`, refresh 15 s, TTL 60 s, `MAX_LISTED 9`), `compat.rs` (`Verdict::{SimVersionTooOld, SimVersionTooNew, DifferentMatchTypes, ...}`), plus the generic Tango lobby state machine (`state.rs`, `handshake.rs`, `reconcile.rs`). |
| `tango/src/app/online.rs` | The app half of the in-game lobby: reads/writes the EWRAM mailbox every frame, makes/joins `Room`s, announces lobbies, builds the match (`online_build_match`), rejoin (`online_rejoin_tick`), stats (`online_record_battles`). Also `tango/src/unranked_live.rs`, `tango/src/suspended.rs`. |
| `tango-gamesupport/src/{hold,private}.rs` | Process statics for presentation only: the reconnect/migration box (`hold::set`, `set_migration`, `set_host_wait`, `set_unranked`) and the private-pick key/word queues (`private::set_keys`, `take_keys`, `queue_pick`, `next_word`). |

## 3. Seats, armies, and who has the pad

- Army `a` (1..5) belongs to physical seat `(a - 1) % players` (`pvp.rs` `seat_of_n`). A 2-player room on a 4-army map gives seat 0
  armies 1 and 3.
- Seat 0 is the room's host at start (`ROOM_HOST` bit in the match subtype gives the room's maker seat 0; `control.rs` `room_host_seat`). A resumed match seats players as saved (`RoomPlayer::seat`, `RoomMatch::host_seat`).
- `SharedGame::merge` -> `pvp.rs` `merge_keys` -> `online::merge` (`online.rs`):
  1. navigation walk (`navigating`): no keys;
  2. a player left after the map was drawn (`proxy_seat::backing_out`): B taps to back out to SELECT MAP;
  3. `unranked::merge` (map picks: the shared console idles);
  4. in a battle (`BATTLE == 1`): only the seat of `pad_army` (the army whose turn it is; from End to the next turn, the **incoming** alive army) reaches the pad, nobody else's keys are ORed in;
  5. Teams screen: `online_teams::merge` (the game's own Teams screen is not played);
  6. everything else (SELECT MAP result, Rules, results, save prompt): the **host's** word (`proxy_seat::host_index`).
  Outside a room (offline two-seat) `merge_keys` ORs inputs, and in a Versus battle gives the pad to the current army's seat.
- `strip_reset_chord` removes START+SELECT from any word holding A+B+START+SELECT (no seat may soft-reset the shared console).
- `seat_keys` (called every tick before `merge`) runs per-seat state machines that read every seat's keys: `online_teams::tick`, `unranked::tick`, battle bookkeeping (`BATTLE`, `OUT_T`, `ENDER`), `online_stats::track`.

## 4. HostAgg: how the star joins inputs (`tango-session/src/pvp/driver.rs`)

- A host peer's engine hears its guests as **one** remote input: `HostInput { keys: guest0 word, extra: [guest1, guest2, guest3] }`, built by `HostAgg::complete` once every living guest has a queued input for a tick. Each guest is sent one input per tick containing the **other seats' words in seat order, the host's included** (`guest_views`, `distribute`; `Input.others = guests`).
- `HostAgg::ingest` strips command shapes from guest words (`tango_match::keys::command::strip_unless_pick`): no real pad makes all four directions at once, so only the host's own joining can produce a command word. The one exception is the pick words (`PICK = BITS | SELECT`) which guests send themselves.
- `START_WAIT_TICKS = 180`: the host holds its first tick until every guest has sent a first input (else it runs ahead of guests for good).
- `set_gone(seats)`: marks guest seats whose player left. Their word becomes 0 (idle) from then on, their queue is cleared, nothing is sent to them, and one `command::YIELD` word is emitted once (`yield_pending`) so the console plays the seat out. `all_gone` -> the host makes rows itself (`alone_row`).
- `HostAgg::migrated(players, host_seat, gone, own)`: a successor host starts with `started = true`, `gone` seats re-marked and the YIELD command re-sent (harmless twice).
- Time sync: guests' `tick_advantage` is averaged into the row (`adv`).
- `TickLog` (600 ticks, `LOG_KEEP`) keeps what each peer sent and the stream rows received, for migration.

Command words (`tango-match/src/lib.rs` `keys::command`): all four directions down = command. `HOST = BITS|A` ("this seat is the room's host from now"), `YIELD = BITS|B` ("play this seat out: yield it"), `PICK = BITS|SELECT` plus 5 bits in A,B,START,R,L (a map id is sent as two such words, `pick_words`, high half first; ids < 1024). The console reads them in `proxy_seat::tick` (HOST/YIELD) and `unranked::pick_word` (picks).

## 5. The match flow inside the console (`online.rs`, `unranked.rs`, `online_maps.rs`, `online_teams.rs`)

Match subtype bits (`online.rs`): `ONLINE_MATCH 0x01`, `UNRANKED_MATCH 0x02`, `UNRANKED_PICK_GUEST 0x04` (same value as `control::UNRANKED_PICK_GUEST`; app checks), `ROOM_HOST 0x40` (lobby-only, dropped from terms), `SHARED_ART 0x80` (= `control::SHARED_CONTENT`).

1. **Boot walk.** `SharedGame::boot_more` -> `online::boot_more`; `online::before` presses title, wheel to Versus, New, until SELECT MAP's list takes the pad. Same on both peers and in a replay. It waits (`waiting_for_room`) until the session has told the console the room size (the list is built when the screen opens).
2. **SELECT MAP lists.** `online_maps::retab` (called every tick from `before_tick`) rewrites each Versus map's header tab (+0x1A) so that only the maps for the room's count show, in two tabs "NP" and "NP Predeploy" (tab ids 2..9; `HIDE = 0x7E` for everything else; game's own hidden tab is 0x7F, `five_map::show_maps`). Pre-deployed = units placed AND no base, airport or port (owned or neutral) (`Info::predeployed`). Empty tabs are skipped. The pool is audited by example `aw2_map_audit` and `docs/MAPS.md` (test `five_map::tests::every_map_has_the_armies_it_is_listed_for`). Offline Versus uses the same tabs (`offline_retab`, `OFF` block 0x0203DB00); L+R together swap to AW2's own lists.
3. **Simultaneous private picks** (`unranked.rs`, sim 25). Every seat runs a private SELECT MAP: `private_view(scratch, seat)` keeps a console per seat between frames (`Scratch::load_private/save_private/drop_private`), driven only by that seat's keys (`private::set_keys`/`take_keys`). A on a map queues two pick words (`private::queue_pick`); the driver puts them in the seat's own input on the next two ticks (`private::next_word`); the host lets them through (`strip_unless_pick`); the simulation reads them (`unranked::pick_word`, `commit_pick`, checks `online_maps::offered`) into `PICKED` mask / `PICKS` count. Timers: `PICK_SECONDS = 120` (each client picks the map under its cursor at zero), `GRACE_SECONDS = 15` (a seat whose client never answers gets the list's first map from the simulation). `ROUND` counts rounds so private views restart when seats propose again.
4. **Draw and roulette.** After the last pick the winning seat is drawn from a free-running frame counter (`DRAW_T`) mixed with the picks (identical on every peer). The map is walked to in the game's list by pressing for the players (`drive`), `PHASE` 0 picking, 1 walking, 2 chosen, 3 walk failed (host picks). Reveal: `REVEAL_SECONDS = 9` hold (host A skips), "?????" per gamertag cycling (`mask`, `CYC_T`, `HOLD_T`), reveal chime SE `0x75` through `SOUND_REQ` (see `rom-routines.md`).
5. **Army page** (`online_teams.rs`): the game's Teams screen waits underneath, never given keys; each seat has a selector block at `SEL + 0x10 + 0x10*seat` (CO, colour, partner, field, READY, TEAM A..E). Colours are distinct; READY needs at least two different teams; the host can set any seat's team (L/R pick seat on the TEAM field). On all READY the choices are written into the Teams record (`0x02017C50`, or the five-army copy `0x02030300`) and the game's screen is told to go on. The game's own rules then apply (allies cannot attack each other, team wins, shared fog vision).
6. **Rules.** UNRANKED: `unranked::rules` writes the standard rules (`RULES`, fog off, clear, funds 1000, no limits, powers on, Skills off, Visuals off) and presses A after `RULES_SHOW = 180` frames (3 s). A room: the host plays the screen; guests see it read-only.
7. **Battle** (`BATTLE` byte = 1), results, back to SELECT MAP; B on SELECT MAP -> Select Mode raises `online::match_over` (`OVER`), which the shared engine reports as the match's end on both peers on the same tick.

## 6. The waiting view (`fog_view.rs`, `pvp.rs` `watching` / `view_as`, `shared.rs`)

Why: the console draws the mover's picture (menus, cursor, with fog the mover's vision). Each waiting seat gets its own picture made on a **scratch copy**: `SharedSide::frame` snapshots the console, runs `SharedGame::view_as` (ticks with chosen keys, `before_tick` included, `in_scratch()` true), takes the picture through the overlays, loads the snapshot back, drops the scratch sound and restores frameskip. Nothing reaches the simulation. Waiting pictures are refreshed every `WATCH_EVERY = 2` ticks; a clean own-view picture is kept every `OWN_EVERY = 20` ticks.

`pvp.rs` `watching(core, seat)` (order matters):
1. `result_view::watching` (VICTORY! up and this seat is not on the winning team): true.
2. `unranked::picking`: true (private pick windows).
3. `result_view::decided`: false (the console's own picture for everything after the decision).
4. Not (in battle or `fog_view::between_screens_view`), or current army is the seat's own: false.
5. `fog_view::phase(core)`: `HandOff` false; `Busy` true (logs with `AW2_BUSY_LOG`); `Map | Page | Moving` true; `Scene` -> `fog(core)` (fog on: shown to seats that see attacker/target, others keep the last clean picture; fog off: the console's picture for all).

`view_as(scratch, seat)`: `unranked::private_view` while picking; `result_view::view` for a loser; else `fog_view::view` -> `view_inner`.

`fog_view::phase` is an **allowlist** keyed on running procs (`procs(core)` scans IWRAM `0x03000C00..` and the EWRAM pool `0x0200C000..` for records of two script pointers + a Thumb callback):
- `MAP_LOOP 0x08022049` main-loop callback + procs all in `UI_PROCS` (selection, command menu, menus' frame, build menu, info pages, Save question, overview, Intel; 17 entries) -> `Phase::Map`: the mover's UI is closed on the scratch with B (up to four times) and the picture is the seat's own.
- procs == exactly `[WALK_PROC 0x080363D1]` and the turn is not ended -> `Busy`: **a walking unit is shown to every window**, mover's cursor/menus/range never.
- `DIALOG_PROC 0x08013FF1` narration (not the Save question proc `0x080195F9`, and not while a map-menu item 0..5 is chosen) -> `Busy`: game narration ("The Green Earth Army has lost!") reaches every window; the mover's own questions (Yield, Save, End turn, Power) never.
- `CAPTURE_PROCS` `0x08040C89`/`0x08040AFD` -> `Busy`, shown to seats that see the cell.
- procs all in `ANIMATION_PROCS` (6) -> `Busy` (fog on: window holds its picture unless sprites are on seen cells; sprites on unseen cells are hidden at the sprite flush, `hide_fogged_sprites`).
- `CO_PAGE_LOOP 0x08043591` -> `Page` (never shown); `SCENE_PROC 0x080501DD` with loop 0 -> `Scene`; Rules-page procs `0x0806D000..0x0806E000`/`0x08065961` -> `Page`; wipes `0x080111AD`/`0x0802C451` and anything unlisted -> `Moving` (window holds its last clean picture).
- No procs and `turn_ended` -> `HandOff` (the "Next turn" screen, the same for everyone so the incoming player can press A), or `Moving` while the mover's last menu frame is still held.
- Power: a CO Power chosen (`power_chosen`: main-menu item 2 or 3) -> `Busy`; cut-in (`power_cutin`) and the Super's full-screen scene (`power_screen`) are shown to everyone. Tag CO SWAP / Tag Power screens (`tag_extras::screen_up`) are shown to everyone.

How the scratch map is made (fog on): `CURRENT_PLAYER` is set to the seat's army (`viewer_army`: first army of the seat after the current one in turn order) and the game's own routines run as a call on the emulated CPU at the sprite flush: `CALLS = 0x08020984, 0x0801A548, 0x0801A57C, 0x08043834, REFRESH 0x080258CC`; registers saved in EWRAM `CALL = 0x0203DF00` (+0 state 0 none/1 asked/2 running/3 done, +4 r0..r12, lr, pc); trap at padding `RETURN 0x08020EDA` returns to `fog_view::returned`. Camera: kept in pixels in the link memory (not console RAM), slides to the last seen action in 4 px steps (`CAMERA_STEP`), never follows the cursor; `PIN = CALL+0x40` (byte 1 pins `gMap` +4/+6/+8/+0xA each flush), `FAKE = PIN+6` (tells the game a far-walking unit is mid-window so its own scroll never takes the picture). HUD: the seat's own CO panel (`sub_08043834` called with the seat's army, unit palettes restored via `restore_unit_palettes` over BG banks 8..15); `hud_patch` paints the last plain-map panel over a walk's frames. Hand-off: fog on holds the last own frame until the banner, fog off holds the mover's-menu frame. Scratch state that must not follow the scratch console is kept via `scratch_stash/unstash` (`ds_hud::Stash`).

Known limits (HANDOFF): fog-on walks can still jump the camera up to ~28 px on the first entered cell; map-list scroll mid-frame can garble one waiting frame; 5P turn-change black is the console's own ~0.6 s wipe.

## 7. Results (`result_view.rs`)

The console shows one result screen: VICTORY! whenever a human army is alive. For a seat not on the winning team, `watching` is true while `victory_showing` (VICTORY! procs `0x08615CB0..0x08615E08`, fade script `0x08615E08` ends it), and `view` builds the game's DEFEAT on a **kept** console (`keep_for_view` -> `marked`: VICTORY! waiting at `0x08615CC8`; `Scratch::load_kept`) with `fog_view::call_program`: `CLEAR 0x0801237C/0x08012358`, `START_DEFEAT 0x08049F08(army, parent)`, `END_PROC 0x0801C9EC(master)`, then 150 ticks, every second picture kept (statics, presentation only); `serve` puts the right picture on the window from `Core::frame_counter`. Team awareness: `decided` = alive armies all share one `team_of` (player block `+0x2A`); `loser` = the seat has no army on the winner's team; `winner` = first alive army. Partners of the winner get VICTORY.

## 8. Drops, silence, timeouts

| Event | Rule | Where |
|---|---|---|
| Peer silent (no frame of the in-match channel, the 60 Hz heartbeat counts) | lost after `SILENT_AFTER = 5 s`; own process pauses > `OWN_PAUSE 1.5 s` reset the watch; after the box is up, frames get `RESUME_WINDOW 8 s` before the transport is rebuilt; poll 100 ms | `tango-session/src/pvp/silence.rs` (`SilenceWatch::lost`) |
| Input queue stalls | `RECONNECT_QUEUE_LENGTH = 180` frames; in a room a stall trips only the link silent >= `STALL_QUIET_HOST 3 s` (host side) / `STALL_QUIET_GUEST 7 s` (guest's link to host, so the host's `Hold` arrives first); `RECONNECT_DRAIN_GRACE 5 s` after a rebuild | `supervisor.rs`; `tango-net-protocol/src/data.rs` |
| Reconnect budget | matchmaking links `RECONNECT_MATCHMAKING_TIMEOUT = 60 s` (attempt cap 20 s); direct links 30 s (attempt 5 s); backoff 250 ms | `tango-net/src/link.rs` `reconnect_timeout` |
| Host waiting for a player | match paused (`Pauses`), `RoomMsg::Hold{seat,name,left_ms}` ~1/s to other guests, `Unhold`, `GiveUp`; box "Waiting for NAME to reconnect... NNs" | `supervisor.rs`, `driver.rs` `hold_box`, `hold_box.rs` |
| Rejoin extra | a returning player being let in is waited for up to `REJOIN_EXTRA = 25 s` past the window | `supervisor.rs` |
| Guest drops in a battle | 60 s window; if it runs out, `seat_yields` (`given_up`, `note_gone`, `Unhold` + `Gone` to others): host `set_gone` -> YIELD command -> the console yields its armies; no save, no end | `supervisor.rs`, `driver.rs` |
| Guest drops before a battle (map pick / army page / rules) | after 60 s removed from the room, console backs out to SELECT MAP (`proxy_seat::backing_out`), note says who left, maps proposed again for the new count | `proxy_seat.rs`, 0.8.1 notes |
| **Eliminated seat leaves** | `SharedGame::seats_out` (pvp.rs: in a battle, every army of the seat beaten/yielded; once `decided`, all seats) is published each tick (`driver.rs` -> `EndState.seats_out`); `is_benign_drop(is_host, seats_out, seat)`: on the host a drop of such a seat is benign: no pause, no countdown, no save; `HostAgg::set_gone` makes its word idle; others told `RoomMsg::Gone`. A living seat dropping keeps the 60 s + yield path. Tests: `a_gone_guest_is_idle_and_the_rest_go_on`, `only_a_host_lets_an_out_seat_leave` | `tango-session/src/pvp/mod.rs` `is_benign_drop`, `driver.rs`, `supervisor.rs` |
| Eliminated **host** quits | host migration (below) when it is out; a living host that is lost gets the 60 s window first | `supervisor.rs` (`host_out`), `migrate.rs` |
| Lobby (pre-match) | `GUEST_DEADLINE 25 s`, `FIRST_WORDS 8 s`, `LOAD_DEADLINE 40 s`, link `SILENCE 15 s`; UNRANKED search `SEARCH_DEADLINE 300 s` | `tango-lobby/src/room.rs`, `unranked.rs` |
| Peer end grace | `PEER_END_GRACE = 5 s` for the peer's EndOfMatch | `tango-session/src/pvp/mod.rs` |

## 9. Host migration (`tango-session/src/pvp/migrate.rs`, `proxy_seat.rs`)

- Trigger (guest side, host link trips `PeerQuit | Closed | Stalled | Silent`, match not ended): host is out of the match (`host_out`) or announced quit -> immediate; a living, simply lost host -> after the 60 s window.
- `successor_order(players, host_seat, seats_out, gone)`: remaining seats, those still in the match first, then those out, each by seat; never a `gone` seat. All peers compute the same order from console state. `RANKS = 2` candidates; `RANK_WINDOW = 10 s` before the next; `OUT_SEATS_GRACE = 1.5 s`; `FIRST_WORDS = 6 s`; `SERVE_TIMEOUT = 5 s`. A room of two whose host left: `plays_on_alone` (the guest plays on alone).
- Protocol: the drive thread stops at a tick boundary and publishes a `Snapshot` (rows taken, ticks played, last rows from `TickLog`). Rendezvous id `derive_migration_session_id(seed, rank)`; `RoomMsg::Migrate(RoomMigrate)` -> `plan` picks the longest stream -> `MigrateGo { catchup, start }`. Peers ahead give the others the rows they lack; peers that disagree about a settled tick fail the migration (then the match is saved for RESUME).
- Simulation side: the successor's first word is `command::HOST` (sets `proxy_seat::HOST_SEAT`, `0x0203C621`), so the screens outside a battle take the new host's pad; if the old host left while playing, `YIELD` follows.
- UI: `hold::set_migration`, box "Host left. NAME is hosting now...".
- Limits (docs/AW2.md): a guest that alone loses the host while the host is out finds nobody and ends with the match saved; a thawed old host sees its normal 60 s box and then the saved match.

## 10. Proxy seats, roster, forced yield (`proxy_seat.rs`, sim 22-25)

- State block `BASE = 0x0203C620` (len 0x20): seats under YIELD (bit each), host seat, tap state, roster.
- `tick(core, keys)` (`SharedGame::proxy_keys`, every tick): for each seat under YIELD whose army holds the pad, decides keys from what the console shows (a tap = 4 ticks down, 6 up): cell with nothing, A, Options, Yield, confirm. `force_yield` (sim 25): a yielded seat whose army does not hold the pad is yielded at once by writing what the game's own check would (`force_yield`: player block `+0x31` yielded = 1, `+0x13` reason = 8, `+0x14` defeated = current day; modelled on `0x08028AEC` -> `0x08028874(army, 8)`), and when that leaves one team the console ends the last army's turn itself (End from the map menu), which brings VICTORY.
- Roster: when SELECT MAP is back after a battle (`unranked::back_from_battle`), `make_roster` writes the seats still there (host first, others by seat, `roster_order`); `seat_order` is returned by `SharedGame::seat_order`; every hook then speaks the console's seat numbering (`online::room_seats`, `room_local_seat`, `room_players`). A room that falls to one player is over (`alone`).

## 11. Rejoin, suspended matches, UNRANKED

- **Suspended match (RESUME).** Every 30 ticks `Match` keeps a checkpoint (12 max, `tango-match/src/engine.rs` `World::step`); `Link::state_image` turns a settled one into bytes + digest. When a room match ends by a disconnect (`remote_disconnected`, not completed, not aborted, battle only) `PvpDriver::suspend_if_cut_short` hands the newest 3 settled checkpoints to the app's sink -> `<data>/suspended/<match id>.taw2s` (zstd bincode `SuspendedMatch`; `tango/src/suspended.rs`). ONLINE > LOBBY > RESUME lists them (`online::SAVED`, `0x0203D100`); resuming makes a room (`Request::Resume`, `RoomParams::resume`), seats as saved, start carries the host's save + state (`RoomStart::resume`), `Backend::start_resumed`. Not recorded; the save is deleted when it ends. The listing text comes from `resume_info::describe` (`SharedGame::describe`). Per the 0.8.1 notes, after a guest-drop or a host migration that succeeds nothing is saved; a failed host migration still saves, and a player who knows it was the one that dropped saves too (`suspend_if_cut_short` conditions).
- **Rejoin after an app crash.** `tango/src/unranked_live.rs`: `<data>/unranked_live.json` (`Live { version 2, match_id, code, seat, players, match_type, started_ms, touched_ms, room_name }`) is written when any room match starts, touched every `TOUCH_EVERY_MS = 4000`, removed when the match ends/leaves/gives up. At app start `Verdict::Rejoin{left_ms}` if within `GRACE_MS = 60000` else `Ended` (told once, file removed). Rejoin rendezvous code = `derive_rejoin_code(seed, match_id)`. In `App::online_rejoin_tick` the stayer with the lowest seat opens a room with its newest settled state (`ResumeParams`), other stayers join at once, the returning player joins from the new launch; when all are in every console continues from that state in a new session (`PvpSession::request_rejoin_state`, `rejoin_holds`, `set_swapped`). One player waited for at a time; with a seat that left earlier (`gone != 0`) nobody can rejoin. B on the rejoin box = give up (army yields). Box strings: `online::rejoin_page`.
- **UNRANKED.** App dials the pool session `unranked_session(sim_version)`; the server pairs the first two clients; both send `RoomMsg::Pool(u64)`, the lower hosts; a room of two with guest READY at once. Subtype `ONLINE_MATCH | UNRANKED_MATCH` (+`UNRANKED_PICK_GUEST` when `seed[0] & 1`). Different sim versions never meet (the id). A dropped player gets the 60 s window; then the army yields and the other wins; never saved for RESUME. The console's `unranked::on` reads the subtype copied to EWRAM by `unranked::init`.

## 12. sim_version: when it must change

Value: `u32 = (0x5a00 << 16) | 25` (`shared.rs` `SHARED_SIM_VERSION` | `pvp.rs` `Aw2::sim_version`). It is compared for **equality** by: the room (`tango-lobby/src/room.rs` `game_differs`: "Your tangoAW2 is older..."), the generic lobby (`compat.rs` `Verdict::SimVersionTooOld/TooNew`), the UNRANKED pool id, replay loading (`tango-library/src/game.rs` `find_for_replay_side`: old recordings are refused) and a saved match.

Bump the game half (`pvp.rs`) when the same inputs would give a different console state or a different rollback-visible behaviour. In practice, change it for any edit to:
- anything run inside the simulation: `before_tick` and every module it calls (patches, `tick` functions, `five::sync`, `online::before`, `unranked::tick`, `online_teams::tick`, `proxy_seat::tick`), `merge` / `seat_keys` / `proxy_keys`, `traps` (the closures write RAM/regs), ROM patches written into the image, boot walk timing (`boot_more`);
- EWRAM/IWRAM state layout carried by snapshots (adding/moving a state block; `ram_map.rs`);
- the wire meaning of pad words (command words, pick words) or room protocol semantics that change what is simulated;
- timings the console counts (e.g. v24 `RULES_SHOW` 3 s).
Do **not** need a bump: pure presentation (`overlay*`, `view_as` / `fog_view` pictures, `result_view`, `hold_box`, `hud_patch`, notices, text), app UI, lobby browsing (Nostr), logging, test aids that only read. Wire-format changes use `PROTOCOL_VERSION` (`tango-net-protocol/src/lib.rs`); replay container changes use `tango_replay::VERSION`; an emulator change bumps `SHARED_SIM_VERSION`.
Process: add a numbered comment line in `Aw2::sim_version` (history 14..25 is there), update docs, release notes say "Online peers must all run X" (notes081, 084, 085 did).

History (from the comment in `pvp.rs`): 14 rooms up to 5, per-player CO selectors, only the current army has the pad; 15 Black Cannon picture/font OBJ tile stash (`obelisk`); 17 UNRANKED; 18 room SELECT MAP tabs (`online_maps::retab`), rooms resumable (room wire changed); 19 TEAM per seat (`online_teams`); 20 hand-off told by the End item id; 21 a yielded army's turn also ends; 22 host seat can change, YIELD commands (`proxy_seat`); 23 seat that left yields whatever it was doing, next match played by the seats still there; 24 UNRANKED rules shown 3 s; 25 simultaneous private picks, out-of-turn forced yield.

## 13. Dual Strike pack gating online

- Each player's lobby settings say whether they can show Dual Strike content (`RoomJoin.content`, `RoomParams.content` from `App::lobby_pack`). In `tango-lobby/src/room.rs` start: `all_content = host.content && every peer.content` -> the match subtype gets `SHARED_CONTENT (0x80)`, else not. Resume refuses a player without the pack when the saved match had it (`resume_refusal`).
- In the console the pack is **never** read from the local player's files in a netplay match: `ds_art::features(mode)` and `ds_pack::features(mode)` return `subtype & SHARED_ART != 0` for `Some((_, subtype))`; only a console played alone (`mode == None`) asks `art()` / `pack()`. `pvp.rs` `before_tick` writes `ds_art::ART_ON` (`0x0203FFA5`) each frame from that bit; consumers use `ds_art::active(core)`. So a room mixing players with and without the pack plays one identical console (the Black Cannon sprite redirect, Obelisk/Crystal art, font swap all follow the match bit). Check tool: `tools/mixed_pack_check.sh`; test env `AW2_PACK_ONLY`, `AW2_HASH_LOG`, `AW2_RAM_DUMP`.
- Map lists: maps needing the pack (`five_map::needs_pack`, `online_maps::AuditRow.needs_pack`, `docs/MAPS.md` "Needs DS pack") are shown only when the match has the bit: `five_map::show_maps(core, ds_features, ds, ..)` (called from `before_tick` with the match-derived flags; line `on = !needs_pack(map) || (art && pack)`) puts the unavailable maps on the game's hidden tab before `online_maps::retab` sorts the rest; `offered` checks a private pick against the room's two tabs.
- Online keeps the pack's units, tag pairs, etc. only under the same bit; features that need offline-only state (`mode.is_none()`) such as the DS CO page, campaigns, Survival, tilt pickers are not run online.

## 14. Map proposals and teams: file map

- `unranked.rs`: pick state machine, draw, roulette, rules writer, private view, sounds (`SOUND_REQ` + trap at `LIST_FRAME 0x08086070`).
- `online_maps.rs`: map pool, tabs, previews (`list`, `preview`, `draw_preview`), `offered` (the id check for picks), offline tab view.
- `online_teams.rs`: army page, per-seat selector, TEAM bytes, publishes `room_picks` for the status bar.
- `five_map.rs` / `ds_versus.rs`: the map table in use (`five_map::table`: AW2's moved copy, or Dual Strike's).
- `result_view.rs`: team results (see 7). `online_stats.rs`: per-battle tracking (`track`, `battle_started`), `take_battles` for the app.

## 15. Test aids and harness

- Harness (no network): examples under `tango-gamesupport-aw2/examples/` (`aw2_room_teams <rom> <outdir> <script>` runs N seats on one console; scripts `aw2_*.txt` first line `n N`; `aw2_netplay_script`, `aw2_waiting_view`, `aw2_proxy_yield_*.txt`, `aw2_map_audit`).
- Env: `AW2_PROC_LOG` (map procs when they change), `AW2_CONSOLE_PROCS` (console's procs, loop, menu), `AW2_BUSY_LOG`, `AW2_VIEW_DEBUG`, `AW2_CAM_LOG`, `AW2_TRAP_LOG`, `AW2_MEMSCAN=a-b`, `AW2_DUMP`, `AW2_SAMPLE`, `TANGOAW2_INPUT_LOG=1` (input-drop / fog-phase / cursor / scene logs), `TANGOAW2_PAD_SCRIPT` (`tango/src/app/debug_aids.rs`), `TANGOAW2_PICK_SECONDS` (shortens the 120 s map-pick clock, `unranked.rs` `pick_frames`), `TANGOAW2_TEST_POKE`, `TANGOAW2_NET_IMPAIR=latency,jitter,loss%`, `TANGOAW2_FORCE_RELAY`, `TANGOAW2_BUILD`, `TANGOAW2_DUMP_FRAME`, `TANGOAW2_HASH_PARTS`.
- State hash (`run_dump.rs`): every 60 console frames `{"k":"hash","frame":F,"h":FNV-1a over IWRAM+EWRAM,"visuals":[b@0x0200C42E, b@0x02017C52, b@0x02017CDA]}`; a rolled-back frame is re-hashed (last line per frame wins). Hashes differ between peers before the battle starts (menu phase) and agree in battle.
- Checkers in `tools/`: `cam_check.py`, `pic_check.py`, `hud_check.py`, `mixed_pack_check.sh`, `check_workspace.py --resolved`.

## 16. Where to change what

| I want to change... | Edit | Also |
|---|---|---|
| Who may press what (pad ownership) | `online.rs` `merge`, `pad_army`; `pvp.rs` `merge_keys` | bump sim_version |
| Seat <-> army mapping | `pvp.rs` `seat_of_n` (and its users: `fog_view::viewer_army`, `result_view`, `seats_out`) | bump |
| Input joining / more than 5 seats | `driver.rs` `HostAgg`, `engine.rs` `MAX_SEATS`, `HostInput.extra`, `tango_net::data::Input` | protocol version |
| A command word (new host->console command) | `tango-match/src/lib.rs` `keys::command`, `HostAgg`, `proxy_seat::tick` | bump |
| What a waiting player may see | `fog_view.rs` `phase`, `UI_PROCS`, `ANIMATION_PROCS`, `DIALOG_PROC`, `CAPTURE_PROCS`, `view_inner`; `pvp.rs` `watching` | none (presentation); rerun waiting-view suite |
| Waiting camera / HUD | `fog_view.rs` `pin_camera`, `at_flush`, `hud_patch`, `settle_panel` | none |
| VICTORY / DEFEAT per seat, team results | `result_view.rs` `decided`, `loser`, `winner`, `make`, `serve` | none (sim reads only) |
| Map pool / tabs / pre-deployed rule | `online_maps.rs` (`scan`, `retab`, `predeployed`), `five_map.rs`, `docs/MAPS.md` via `tools/maps_doc.py` | bump if tab logic changes the list |
| Map picks, roulette, timers | `unranked.rs` (`PICK_SECONDS`, `REVEAL_SECONDS`, `GRACE_SECONDS`, `commit_pick`, `drive`, `mask`) | bump |
| Army page / teams | `online_teams.rs` | bump |
| UNRANKED rules or pairing | `unranked.rs` `RULES`; `tango-lobby/src/unranked.rs` | bump (rules); pool id changes with sim_version |
| Reconnect / silence / grace numbers | `silence.rs`, `supervisor.rs` (`STALL_QUIET_*`, `REJOIN_EXTRA`), `tango-net/src/link.rs` (`RECONNECT_*`) | none |
| What counts as a benign (no-pause) leave | `mod.rs` `is_benign_drop`, `pvp.rs` `seats_out` | none/bump if `seats_out` logic changes sim |
| Host migration order / timing | `migrate.rs` (`successor_order`, `RANK_WINDOW`, `plan`) | tests in `migrate.rs` |
| Forced yield behaviour | `proxy_seat.rs` (`force_yield`, `yield_keys`, `decide`) | bump |
| Rejoin / crash recovery | `tango/src/unranked_live.rs`, `app/online.rs` `online_rejoin_tick`, `PvpSession::rejoin_holds` | none |
| Suspended-match list text | `resume_info.rs`, `app/online.rs` `row_of` | none |
| Lobby list / rooms / passwords | `tango-lobby/src/{room,browse}.rs`; game side `online.rs`, `online_browse.rs` (EWRAM mailbox) | none; version-gate by `browse::TAG` |
| In-game lobby pages and mailbox | `online.rs` (`REQUEST`, `STATUS`, `PLAYERS`, ...), `online_menu.rs`, `online_art.rs`, `online_stats.rs`, `online_conn.rs` | ram-map.md; register new state in `ram_map.rs` |
| Pack-gated content online | `ds_art::features`, `ds_pack::features`, `room.rs` `all_content`, `SHARED_ART` | bump if the console reads a new gated bit |
| Reconnect / migration boxes | `hold_box.rs`, `tango-gamesupport/src/hold.rs`, `driver.rs` `hold_box` | none |
| Net endpoints (signalling, STUN, TURN, Nostr) | `tango-net/src/endpoints.rs` | none |
| New EWRAM state | `ram_map.rs` `REGIONS` (+ `TIME_SHARED` if time-shared), new module constants | bump |

## 17. Open items recorded in the session notes (not fixed in code)

- An **eliminated host** quitting still pauses/migrates rather than being benign (accepted for 0.8.0); a living seat dropping keeps 60 s + RESUME/yield.
- Visuals rule online: the three copies are shared (host sets them); the in-battle Options "Visual" change is not blocked online; the real gate that switches the battle scene off was never identified.
- `scen.py` 4P/5P scenarios (`hq4`/`hq5`) did not work (poke of `0x020232C0+0x3C*army+0x2A` had no effect); harness scripts stand in.
- Seat that left earlier blocks rejoin; savestate resume is not tick-for-tick identical to the original (audio FIFO/DMA detail lost) but peers agree.
- Unverified on real devices: iPhone-hosted RESUME, real background suspension, landscape, finger taps, 4-5 player rooms with iOS clients (IOS gate report).
