---
name: aw2-conquest
description: Work on Conquest Run, the Gauntlet's five-map roguelike run (AW2 Versus maps, carry-over, a reward between maps, a random enemy CO a map, Save / Continue); change a map, a reward or the enemy draw, and check it
---

Read docs/dev/conquest.md first (the wiring, the state bytes, the tests). Code: `tango-gamesupport-aw2/src/conquest.rs` (maps, mission, draw, reward logic), `conquest_reward.rs` (the page), the stage engine's `Stub::Reward` in `stage.rs`.

1. Build (`./aw2dev build --examples`), then `./aw2dev conquest maps`: the five maps read from the ROM against the constants in `conquest.rs` (exit 1 on a mismatch). `./aw2dev conquest maps --all` lists every two-player Versus map with its HQ distance and bases to choose from (keep HQs 20+ cells apart, equal bases, no sea to cross).
2. Run it: `./aw2dev conquest start [--co N]` (a picture of each screen, fails if one is missing) and `./aw2dev conquest sheet` (the reward page, the unit page and the five first turns in the three looks, one PNG: look at it).
3. Tests: `./aw2dev conquest test` (`-k conquest`), then `python3 tools/aw2test/run.py -k conquest,gauntlet_mode --mode ds -j 6` (the selector's row order is the Gauntlet's: Conquest Run is always the first row, its mission is always the last of `def()`).
4. A new reward or a changed text: `conquest_reward.rs` draws with AW2's windows and plate only; run `./aw2dev audit text` (the `conquest_*` pages) and `./aw2dev gfx audit --modes conquest` and look at the sheets in all three looks (AW2, Dual Strike + tilt, Dual Strike flat).
5. New EWRAM goes in `ram_map.rs` (the overlap test), nothing of a Versus / online battle's simulation may change (no `SIM_VERSION` bump: the mode is offline).
