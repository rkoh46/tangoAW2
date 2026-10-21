---
name: aw2-live-debug
description: Reproduce a tangoAW2 online bug live on real app clients, then read logs, the hash diff and sheets. Use when a bug needs the real app (UI, timing, rooms), not just the harness.
---

1. Reproduce offline first if possible: `./aw2dev harness <script> --seats N --dump` (docs/dev/pad-scripts.md).
2. Live: `./aw2dev build` then `./aw2dev live <scenario> --fog on|off --players N --local --hz 2` (scenarios: `aw2dev live --list`; `lobby` = plain N-seat flow;
   `--kill 1:eliminated`, `--stop 1:30:10`, `--hz 15..60` for walk/camera analysis). One run at a time (lock in `~/.aw2dev`).
3. Verdict: `./aw2dev check <run>` (hash, leak, mover, cam, hud, black; JSON in `<run>/check.json`). A run that gave up is a FAIL.
4. Read: `<run>/tango_s<k>.log` (pad script lines show the last cue reached), `state_s<k>.jsonl` (acts, hash, keys), `summary.json`;
   `./aw2dev net trace <run>` merges peers; hashes differ: `./aw2dev net desync <run>`.
5. Look: `./aw2dev sheet <run> --around N --kind move [--strip]`, `--events`, or contact sheets; view the PNGs yourself and report any bug you see.
6. Fix, rebuild (same build for both fog modes), rerun from the stuck step, not from the beginning when you can.
7. Other drivers: `aw2dev live rejoin <unr-guest|lobby-host|...>` (kill -9 + relaunch + hash check), `aw2dev live ios-gate --kinds mac,iphone` (Simulator peer; `aw2dev build --sim` first),
   `rules-lobby`, `rules-unranked`, `browse`, `solo` (one offline window); freeze a peer with `aw2dev net sim ... --event @AFTER_TURN_0:stop:1:10` (docs/dev/online-dev.md).
8. Clean up: `./aw2dev clean --runs --yes` when reviewed.
