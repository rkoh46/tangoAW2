---
name: aw2-online-debug
description: Debug and test tangoAW2 online play (rooms, rollback, rejoin, host migration, desyncs, network conditions) with aw2dev net, without hammering public services.
---

Read docs/dev/online-dev.md. Politeness: `net sim|matrix|soak` run a local signalling mock and block public endpoints; `--public` is the exception (needed for relay/TURN).
1. Reproduce: `./aw2dev net sim <scenario|lobby> --players N --level mild|bad|awful` (or `--latency/--jitter/--loss/--reorder`; `--event 30:stop:1:10`,
   `t900:kill:2`, `45:relaunch:2` for freezes, kills, rejoins). Verdict: stall, hash, leak, result.
2. Broad sweep: `./aw2dev net matrix --players 2,3,4 --fog on,off --levels none,mild,bad` (table in `devkit/work/matrix/`).
3. Diverged hashes: `./aw2dev net desync <run>` (first frame, differing 4 KB blocks, RAM diff, named addresses; rerun with `--dump-frame F` for the RAM bytes),
   then `./aw2dev net trace <run> --from-tick A --to-tick B` for inputs, rollbacks and link events across peers.
4. Services suspected: `./aw2dev net relays [--turn]` (polite, remembers probes). Do not loop it.
5. Long confidence run: `./aw2dev net soak --hours 2` (keeps only failing run dirs; log in `devkit/work/soak/`).
6. Fix the cause (usually state one peer reads and the other does not, or a missed sim_version bump), rebuild, rerun the same story, then the suite if fog_view/pvp changed.
