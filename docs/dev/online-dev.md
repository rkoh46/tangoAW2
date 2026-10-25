# Developing and debugging the online side

Tools: `aw2dev net sim|repeat|matrix|desync|trace|relays|soak` (devkit/aw2/net.py), the local signalling mock (devkit/aw2/signal_mock.py),
and the app's test aids. Architecture: docs/dev/architecture-online.md. Env aids: docs/dev/env-aids.md.

## Politeness first
The app depends on free public services: the Tango matchmaking/signalling server, public STUN servers, Cloudflare TURN (credentials
only from the signalling server) and Nostr relays for the lobby list. Never hammer them (rules in `tango-net/src/endpoints.rs`:
5 s..10 min backoff, 1 h block on "rate limited", one STUN binding request per probe, no probes within 5 min).
- `net sim`, `net matrix` and `net soak` run a LOCAL signalling mock and set `TANGOAW2_BLOCK_ENDPOINTS` to every public STUN, Nostr and
  signalling host plus `TANGOAW2_LOBBY_RELAYS=ws://127.0.0.1:9`, so nothing leaves the Mac. Peers connect over loopback with host
  candidates.
- `--public` opts back into the real server (one run, a handful of connections). Relay-only (`TANGOAW2_FORCE_RELAY=1`) needs it,
  because TURN credentials come only from the real server's `Hello`.
- `aw2dev live ...` (plain, no `net`) still uses the real matchmaking server: use sparingly.
- `net relays` is the only tool that probes public endpoints, with the app's own caps, and remembers probes in `~/.aw2dev/relay_probe.json`.

## `net sim`
```
aw2dev net sim moveview --level mild                      # 30 ms +-10 ms, 1 % loss each way
aw2dev net sim lobby --players 4 --latency 80 --jitter 40 --reorder
aw2dev net sim hq3 --players 3 --event 20:stop:1:10       # freeze seat 1 (SIGSTOP) 20 s in, for 10 s
aw2dev net sim lobby --players 3 --event t900:kill:2 --event t900:relaunch:2   # kill at tick 900, A on the rejoin box
```
Impairment is `TANGOAW2_NET_IMPAIR=latency_ms,jitter_ms,loss_pct` (tango-net/src/impair.rs), applied to what each peer SENDS (round trip
= 2x latency); loss only on the unreliable in-match channel; jitter reorders it. `--impair 2=200,80,10` targets one seat. Events:
`AT:ACTION:SEAT[:ARG]`, AT in seconds, `tN` (seat 0's console ticks) or `@MARKER` (a text a pad script has logged; scenarios log `AFTER_TURN_<r>` after turn r of the global list, which is the quiet moment to freeze: `--event @AFTER_TURN_0:stop:1:10`); actions kill, stop (ARG seconds, then SIGCONT), cont, relaunch (the rejoin box: A).
Not offered because they need root (`dnctl`/`pfctl`): bandwidth caps and NAT-type emulation; relay-only needs `--public`.
Output: a run dir (see devkit/aw2/live.py docstring) and a verdict: stall, hash, leak, result. Scripted `--event`s for 2P scenarios
reuse scen kinds (`--kill`/`--stop` of `aw2dev live` also exist: `SEATS:WHEN`, `eliminated`, `armyN`, `log:TEXT`).

## `net repeat` (a desync that shows on some runs only)
```
aw2dev net repeat                         # 2P Unranked with the Emerald Sun seat, 8 runs (the default story)
aw2dev net repeat unranked --runs 12 --no-skin
aw2dev net repeat asuka --no-skin           # both armies are Asuka (CO byte poked, scenarios.py s_asuka), her CO Power day 1 and Super Power day 2 with units of every HP: 8 runs, equal hashes
aw2dev net repeat moveview --runs 6 --level mild --fog off
```
`net sim` N times in a row on local signalling (the same options: `--level/--latency/--jitter/--loss/--event/--dump-frame/--fog/--players`), then
`N of N runs with equal hashes`. Exit 0 only if every run passes (stall, hash, leak, result). Failing runs are kept (`aw2dev net desync <run>`),
passing ones deleted unless `--keep`. A race between peers (state that depends on cycle timing, what a waiting seat's picture does to its
console) fails on a fraction of runs, so one passing run proves nothing: this is the regression for it. History: with the waiting picture made
on the match's console, about half of the 2P Unranked runs diverged at frame 1684 in the IWRAM stack block (architecture-online.md 6.1);
`net repeat` is what showed it reliably (v0.8.6 and the Emerald Sun branch alike) and what shows it fixed. `AW2DEV_SKIN=1` is what makes seat 0 pick
Emerald Sun on the army page; `--no-skin` plays the plain army. Each run is about a minute.

## `net matrix`
`aw2dev net matrix --players 2,3,4 --fog on,off --levels none,mild,bad` runs each cell as a live run (2P: the scenario, larger rooms: the
lobby flow) and prints a table with columns stall / hash / leak / result and a verdict, also saved as `devkit/work/matrix/*.md`.
Each cell is a few minutes; the default grid is small (2,3 players x fog x none,mild). `--route relay` needs `--public`.

## `net desync <run>` (a diverged run)
1. first frame where the seats' `hash` lines differ after having agreed (the console's FNV hash every 60 frames);
2. with `TANGOAW2_HASH_PARTS` (set by `net sim`): which 4 KB blocks differ (IWRAM 0x03000000.., EWRAM 0x02000000..);
3. RAM diff of the two consoles if dumped for that frame: re-run with `--dump-frame F` (`TANGOAW2_DUMP_FRAME`, writes `ram_s<seat>_<F>_i|e.bin`); `--dump-frame A-B` hashes and dumps every frame of a range, so the first differing frame is exact (60-frame hashes only say "between two grid frames");
   address ranges are named from `docs/dev/ram-map.md` (add the address there if it prints "unnamed");
4. the joypad words each peer fed the console within `--window` ticks (`TANGOAW2_INPUT_LOG`, set by live runs) and log lines about
   rollbacks / input drops.
`net desync` also prints, for every later frame, which blocks ever differ and whether EWRAM (the game's variables) stays equal; when only IWRAM block 7
(`0x03007000..0x03007FFF`, the stacks) differs it says "timing skew": the two consoles ran a few cycles apart (architecture-online.md 6.1, ram-map.md 2.2), not a game-state desync, but still a defect.
Typical causes: state read by one peer and not the other (waiting-view code writing to the shared console), a console that loaded a savestate for presentation, a rule/pack difference (mixed pack room),
a non-deterministic read. Fix the cause, not the hash.

## `net trace <run>`
One timeline across peers: inputs, acts, hash lines, selected log lines (link, pvp, rollback, reconnect, rejoin, migration...), time
relative to the first event, tick of the seat. `--from-tick/--to-tick/--kinds input,act,hash,log,state`. Full output in `<run>/trace.txt`.

## `net relays`
`aw2dev net relays [--turn] [--all] [--force]`: the app's own learned health (`relay_health.txt` of the test profiles), a signalling
handshake, optionally one `Hello` (lists ICE/TURN hosts, never credentials), at most 3 STUN binding requests and 3 Nostr handshakes per call
(`--all` for every endpoint), skipping anything probed in the last 5 min or backing off.

## `net soak --hours H`
Random rooms (2-4 players, fog, impairment level, scenario, chance of a freeze or kill+rejoin) one after another on local signalling.
Failures (desync, stall, panic) are logged to `devkit/work/soak/<ts>/soak.jsonl` and their run dirs are kept; passing runs are deleted.
Reproduce a failure: `aw2dev net desync <run>`; the record has scenario/players/fog/impair/events.

## The local signalling mock
`python3 -m aw2.signal_mock --port N` (from `devkit/`), or in-process. Protocol: vendor/tango-signaling/src/proto/signaling.proto. Pairs
two connections with the same `session_id` (the first to send `Start` is the impolite side, the later one gets its `Offer`), relays
`Answer`/`IceCandidate`, echoes `Ping`, sends `Hello` without ICE servers. Profiles point at it through `matchmaking_endpoint`.

## Freezes and the pad scripts
A frozen peer shows AW2's reconnect box on the other seats after 5 s of silence (`pvp: nothing from ... for 5s`), the match goes on when the peer is heard again
(a longer outage reconnects the link or yields the army after the 60 s window). Scenario pad scripts are made freeze-safe (`scenarios.freeze_safe`): before every
step that waits for the game or presses a key they wait `until !reconnect 300` (cue `reconnect` = the box is up), and the app's macros `endturn`, `onbanner`,
`intro` (short built-in timeouts) are expanded with longer limits. Tested: a 10 s SIGSTOP on seat 1 after seat 0's turn, scripts ran to the end, hashes equal.
Limit: a key press that lands while the freeze is being detected (before the box appears) can be dropped by the game (an input-drop), leaving a menu open;
freeze inside a seat's own multi-step action is therefore unreliable. Freeze in a quiet moment (`@AFTER_TURN_0`) or accept a stall as the finding.

## Drivers (ports of the old scratchpad scripts)
| Command | What |
|---|---|
| `aw2dev live <scenario>` | 2P scenarios (`--list`), `lobby` (N seats, rounds of end-turn), `unranked`, `rules-lobby`, `rules-unranked`, `browse` (needs the PUBLIC lobby relays: no `--local`), `solo` (one offline window: `--entry selectmap\|lobby\|title --pad "wait 60;shot a;press A 8"`) |
| `aw2dev live rejoin <name>` | `unr-guest`, `unr-host`, `unr-guest-gone`, `unr-host-gone`, `unr-late`, `unr-giveup-guest`, `unr-giveup-host`, `unr-rejoin-gone`, `unr-hostrejoin-gone`, `lobby-guest`, `lobby-host`, `lobby-late`, `lobby-giveup`, `lobby-browse` (`--players N` for lobby): the victim is killed -9 six seconds after the battle is ready and relaunched after `REL_DELAY` (14 s; late 75); passes when everyone's script ends and the victim's hashes after the rejoin equal the survivor's from the frame it had reached. Verified: `unr-guest`, `lobby-host` (3P) |
| `aw2dev live ios-gate --kinds mac,iphone [--event 30:bg:1:10]` | a Simulator peer against Mac peers (`aw2dev build --sim` first); events kill / relaunch / bg / stop; hash check at the end. Verified: mac host + iPhone guest, 2 rounds |
| `--picks 0,3,5` | per-seat map pick (DOWN presses from the first row; `t1:2` = one RIGHT then two DOWN; negative = UP). Different picks make the draw random; scenarios default to every seat proposing the first 2P map |
Simulators are booted when needed and left running; only this app is terminated. UNRANKED and rejoin use the matchmaking pairing, which the local mock provides.
