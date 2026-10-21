# AI debug channel

A way for an AI developer (or any tool) to **inspect and drive the running game** instead of pressing keys blind with a
pad script. It is part of every build and **off by default**.

* Enable: `TANGOAW2_AI_DEBUG=<port>` (`0` picks one) or `TANGOAW2_AI_DEBUG=<socket path>`; or the hidden `ai_debug` key
  of `config.json` (same values). The app logs `ai-debug: channel ON at ...` and prints `AI_DEBUG_LISTENING <addr>` on stdout.
* Off: nothing listens, no thread exists, the console's tick hook is one atomic load.
* Loopback only: TCP `127.0.0.1` or a Unix socket (mode 0600). Optional token: `TANGOAW2_AI_DEBUG_TOKEN`.
* Never draws anything for the players. It reads the console between ticks and changes nothing unless you act.
* Online: a press goes through the seat's normal input path, so a seat that is waiting still has its keys dropped by the
  console's merge. Online peers are otherwise **read-only**: `poke` is refused (a poke desyncs the peers) unless the app has
  `TANGOAW2_AI_DEBUG_WRITE=1` *and* the request has `"force_offline":true`; `checkpoint_load`/`start_offline` are refused.
* Other env: `TANGOAW2_AI_DEBUG_TEST=1` allows `inject` (network faults, see below; must be set at launch);
  `TANGOAW2_BOOT_CHECKPOINT=NAME` boots straight into a checkpoint (offline); `TANGOAW2_AUTOSTART=offline` starts the session.
* It shows the console's whole truth (fog included): a tool for the developer, not a player aid.

## Protocol

Line-delimited JSON. Request `{"id":1,"cmd":"state", ...}`; answer `{"id":1,"ok":true, ...}` or
`{"id":1,"ok":false,"error":"..."}`. With a token, send `{"cmd":"auth","token":"..."}` first (or put `token` in each request).
After `subscribe`, event lines (`{"event":"act", ..., "eid":17}`, no `id`) are interleaved with answers.

| cmd | arguments | answer / effect |
|---|---|---|
| `hello` | | protocol, version, session kind, seat, flags, command list |
| `state` | `fields:[..]`, `fresh:true` | `state`: the decoded state (below) |
| `press` | `keys:"A"`/`"A+B"`/`["A","B"]`, `frames` (8), `seat`, `wait` (true) | holds the keys N frames then 6 released; `seat` must be this window's seat |
| `hold` / `release` | `keys` | held until released (`release` without keys: all, and drops queued presses) |
| `type` | `text` | characters into the in-game lobby's typing pages (offline session) |
| `goto` | `x`,`y`,`timeout` | walks the map cursor to the cell |
| `wait_until` | `cond`, `timeout` (30) | blocks until the state matches (language below) |
| `screenshot` | `raw`, `path` | PNG (`png_b64`, 240x160): the session's own window picture, the game frame only |
| `peek` / `poke` | `addr`, `len` / `hex` | console memory (`poke`: offline only, see above) |
| `hash` | | FNV-1a of IWRAM+EWRAM (the `hash` events' value) |
| `proc_list` | | the game's running procs and the main-loop callback |
| `log_tail` | `lines` | the app's last log lines |
| `checkpoint_save` / `checkpoint_load` / `checkpoint_list` | `name` | see Checkpoints |
| `start_offline` | | presses Play offline (no session running) |
| `inject` | `op`, ... | network faults, test mode only (below) |
| `net` | | `state.link`, `state.online`, `state.local` |
| `subscribe` / `unsubscribe` | `events:[kinds]`, `after` | the event stream |
| `events` | `after` | the events since an id, without subscribing |

Keys: `A B SELECT START RIGHT LEFT UP DOWN R L`.

### `state`

Top level: `frame` (console frame counter), `tick`, `seq`, `age_ms`, `mode` (`offline`/`online`), `phase`, `screen`,
`main_loop`, `in_battle`, `active_army`, `active_seat`, `mine` (this window's seat has the pad), `day`/`turn`,
`turn_ended`, `decided`, `winner`, `rules` {fog, weather, powers, abilities, game_mode}, `map` {id, name, w, h},
`cursor` {x,y}, `camera` {px,py}, `menu` (below), `selected_unit`,
`armies[]` {army, co, co_name, partner, funds, power_meter, power_cost, super_cost, power_mode, powers_used, team, alive,
controller, colour, seat, units, properties}, `units[]` {id, owner, type, name, x, y, hp, fuel, ammo, moved/done, carried,
hidden, capture, cargo[], flags}, `properties[]` {x, y, type, name, owner, capture}, `flags`, `cues`, `screen_info`,
`last_hash` {frame, h}, `local` {session: none/offline/online/other, seat}, `link`, `online`.

`phase` is the coarse place: `boot`, `title`, `select_mode`, `online_menu`, `room`, `select_map`, `army_select`, `rules`,
`battle`, `results`, `menu`. `screen` is finer; in a battle: `map`, `map_menu` (the map menu is open), `unit_menu` (a unit's
command menu), `build_menu` (the production menu), `submenu` (the Intel and Options lists, or a target being chosen), `hand_off` (NEXT TURN banner),
`co_power`, `co_page`, `battle_scene`, `animation`, `transition`, `victory`. `select_mode` has
`screen_info.wheel_item` (0 Campaign, 1 Versus, 2 Battle Maps, 3 Design Room, 4 Online, 5 War Room, 8 Survival).
Unit fields: `hp` 1..100, `fuel`, `ammo` (the game's counts), `moved` = the unit has acted this turn.
`property.capture` is the capture points of the unit standing on it (0: none). Army numbers 1..5; `seat` = army-1 mod players online.

`online`: `room`, `players`, `local_seat`, `gamertags[]`, `picks[]` {team, colour}, `sim_version`, `level` (the in-game lobby's
page), `lobby` {status, message (why a room failed), players[] {ready, host, you}, menu_cursor}, `seats_out[]`, `roster_order[]`,
`input` {offered_ticks[], dropped_ticks[]} (per seat: ticks it offered keys, and ticks the merge let none of them through;
console-side counts, rollback re-simulations included). `cues`: `myturn banner acting over mapup mypick chosen rules picks_made`
(the pad script's `until` words).

### `state.menu`

The menu the player is in, in one shape: `kind` (`map`, `unit`, `build`, `other`; null when none), `rows[]` {id, text, enabled, cost
(production only)}, `cursor` (index into `rows`), `item` (the cursor's text). `enabled:false` is a greyed row (a command the unit
cannot do now; a unit the army cannot pay for). `build` also has `property` and `funds` under `menu.build`, and the production rows are
the units the property builds in the game's order with the game's prices (the CPU's `roster` table). The raw views stay:
`open`/`items`/`item_ids`/`cursor_row` (the map menu's), `menus[]` (every menu proc the game has up: kind, cursor, rows), `list_ids`.

### `state.link` (netplay session; `null` offline)

`players`, `local_player`, `host_seat`, `is_host`, `migrations`, `migrating` {successor, is_me}, `waiting_for`,
`rejoin_holds[]` {seat, name, seconds_left}, `reconnecting`, `silence` (reconnecting or waiting for the peer),
`remote_disconnected`, `booting`, `waiting_for_peer`, `gone_seats[]`, `input_delay` (frames), `skew`, `lead` (local inputs
not yet confirmed), `rollback` {last_depth, count, ticks_resimulated}, `tps`, `fps_target`, `frames_sent`, `resends`,
`resend_ratio` (heartbeat re-sends per frame sent: a loss indicator), `links[]` {index, rtt_ms, rtt_median_ms, jitter_ms
(mean change between ping samples), health (`connected`/`reconnecting`/`dead`), give_up_in_s, given_up, path (`direct`/`relay`),
ice {local_type, remote_type (host/srflx/prflx/relay), local_candidates, remote_candidates (host/srflx/prflx/relay counts)}},
`faults` (what `inject` has set). A host has one link per guest (`index` in connection order). Types only, never an address.

### `wait_until` conditions

A JSON object, every key must hold: `{"phase":"battle","active_army":2}`. A key is a dotted path into the state
(`armies.1.funds`, `link.links.0.rtt_ms`, `cues.mapup`); a plain value means equal; an object of tests: `eq ne gt gte lt lte in nin
contains exists` (`{"day":{"gte":3}}`). `{"any":[..]}`, `{"all":[..]}`, `{"not":{..}}` combine; `{"unit_at":[x,y]}` /
`{"no_unit_at":[x,y]}` look at the units. On timeout the error says where the game is.

### Events (`subscribe`, kinds `scene turn act hash error rollback link migration rejoin`)

* `scene` {phase, screen, from_phase, from_screen}; `turn` {army, seat, day};
  `act` {what: build|move|attack|kill|capture|load|unload|power|eliminated, actor, unit, name, id, owner, to, from, hp, ...}
  (the same acts `TANGOAW2_RUN_DIR`'s `state_s<k>.jsonl` has); `hash` {frame, tick, h} every 60 console frames (peers that play the
  same match agree at the same frame; the room's pages before SELECT MAP run on each peer's own offline console, so compare only hash lines after `phase` reaches `select_map`); `error` {message} for every `log::error!`.
* `rollback` {max_depth, count, ticks_resimulated}: a rollback happened since the last look (16 ms; depth is the deepest).
* `link` {reconnecting, remote_disconnected, booting, waiting_for_peer, links[]}: a link's health or route changed.
* `migration` {host_seat, migrations, migrating}; `rejoin` {holds[]}: a seat the match waits for came or went.

### `inject` (network faults; `TANGOAW2_AI_DEBUG_TEST=1` at launch, else refused)

Affects what *this* peer sends (the other sees a slow, lossy or silent link), at runtime, no restart:
`{"cmd":"inject","op":"latency","latency_ms":80,"jitter_ms":20,"loss_pct":3}` (loss hits the unreliable in-match channel only),
`{"op":"drop","seconds":5}` (everything this side sends vanishes: a dead link; a long drop ends in the reconnect/rejoin path),
`{"op":"freeze","seconds":2}` (sent data is held and released together: a stall), `{"op":"clear"}`, `{"op":"status"}`.
Each use is logged. A runtime setting outranks `TANGOAW2_NET_IMPAIR`.

## Checkpoints

`checkpoint_save NAME` writes `<profile>/data/checkpoints/NAME.state` (the mGBA save state) and `NAME.json` (frame, RAM hash,
phase, map, rules, armies, and the setup flags a load must agree with: the Dual Strike pack features and the cartridge).
`checkpoint_load NAME` (offline only) loads it into the running console and answers the RAM hash next to the saved one
(`match`). `TANGOAW2_BOOT_CHECKPOINT=NAME` starts an offline session and loads it: tests resume instead of restarting.
Checkpoints never live in the repo. Boot the app the same way (same ROM, same DS pack) it was saved with.

**Online.** The console is shared: a checkpoint is only meaningful if *every* peer loads the same state at the same tick.
The app does not do that live. The supported scenarios: (1) the harness (`aw2_room_teams`, no network) has
`checkpoint save NAME` / `checkpoint load NAME` in the same file format, so a room scenario resumes from a state; (2) for live
peers, save with `checkpoint_save` on each peer at the same match moment (a `hash` event frame all peers share is the
moment; the files must have equal `ram_hash`), and use the room's own suspend/rejoin (the lobby's RESUME) to continue. A
`checkpoint_save` online is allowed (it only reads).

## Client

`tools/aidebug/client.py` (Python 3, stdlib only): a library and a CLI.

```
export TANGOAW2_AI_DEBUG_ADDR=127.0.0.1:47811
aidebug state --fields phase,screen        # python3 client.py ...
aidebug press A | goto 3 6 | wait-until phase=battle active_army=2 day\>=3
aidebug shot out.png | ckpt save x | ckpt load x | sub act turn | net | inject latency 80 10 2
```

Library: `d = AiDebug.connect(addr)`; `d.wait_until({"phase":"battle"})`, `d.press_until("START", {"phase":"select_mode"})`,
`d.state()`, `d.screenshot(path)`, `d.subscribe([...]); for e in d.events(): ...`. Examples: `examples/offline_versus.py`
(title to a Versus battle, move a unit, screenshot, checkpoint), `examples/online_2p.py` (two clients: room to battle, hashes).

## Limits

* One console frame is 1/60 s; `press` frames are wall-clock (like the pad script), a loaded machine can stretch them.
* `screenshot raw` is the same as the window picture (the shared console's raw frame is not exposed by the session).
* `state` is rebuilt every 3 ticks; use `fresh:true` for the very next tick.
* Online `dropped_ticks` counts include rollback re-simulations.


## Running the examples
The examples expect a clean test profile and no other tangoAW2 instance on the chosen port (a leftover test app can hold it: stop it first). `offline_versus.py` writes its screenshot to the current directory.
