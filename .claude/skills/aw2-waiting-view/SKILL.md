---
name: aw2-waiting-view
description: Allowlist a new scene or screen in tangoAW2's waiting view (what non-mover windows see), then run the leak checks.
---

Waiting windows must show what a spectator of that seat sees (an unseen walk, mover UI, menus, cursor never). Background: docs/dev/architecture-online.md
("waiting view and allowlist"), code: `fog_view.rs` (`phase`, allowlist, scratch-call), `pvp.rs` (`watching`, `view_as`).
1. Identify the scene's proc/screen (`AW2_PROC_LOG=1`, `AW2_CONSOLE_PROCS=1`; docs/dev/rom-routines.md) and decide: shown to every window, shown only to seats that see the cell, or never.
2. Add it to the allowlist in `fog_view.rs` the way the existing entries (battle scene, CO power cut-in, narration `0x08013FF1`, results) are done.
3. Add or extend a harness script in `tango-gamesupport-aw2/examples/aw2_waiting_leak_*.txt` (2-5 seats, fog on and off) that reaches the scene.
4. `./aw2dev build --all`; `./aw2dev harness aw2_waiting_leak_3p --leak` (and the other counts), then `./aw2dev suite` (`bad=0`).
5. Live proof, same build for both fog modes: `./aw2dev live <scenario> --fog on --local`, `--fog off`; `./aw2dev check latest --leak --mover`; view `./aw2dev sheet latest --around N`.
6. If the scene changes the shared console, bump `sim_version` (see the architecture doc).
