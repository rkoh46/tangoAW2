---
name: aw2-gfx-debug
description: Detect and debug garbled or wrong graphics in tangoAW2 (broken text, clobbered font tiles, wrong palettes, stray tiles, frozen or black frames) with aw2dev gfx, and turn each fix into a regression screen.
---

1. Build the examples (`./aw2dev build --examples`). First time: `./aw2dev gfx golden` from a build you trust (it renders from your ROM into ~/.aw2dev/golden; never commit it).
2. Detect: `./aw2dev gfx check` (all catalogued screens) or `--screen banner_5p`; for a live run `./aw2dev check <run> --gfx --black`. Open the PNGs it names (heat-maps, same-region sheets).
3. Understand: `./aw2dev gfx explain <shot.bmp> --region x,y,w,h` (OAM entries, BG tiles, palette banks, tile sheets); `./aw2dev gfx blame --screen S --dump NAME` for the first tick a guarded tile range changes and the procs then.
4. Find the commit: `./aw2dev gfx bisect --screen S --good C --bad HEAD` (the screen's script must exist in those commits).
5. Fix, then add or extend a screen in `devkit/gfx/catalogue.toml` (script or aw2_offline_tabs tokens, variants, detectors). PROVE it: it must fail on the broken build (`--binary-dir` of a worktree with the fix reverted, or `--env` for an env switch) and pass on the fixed one.
6. Update docs/dev/graphics.md (the past-bugs table) and run `./aw2dev suite --only <screen>` and `./aw2dev kit check`.
Look at the pictures yourself; a detector pass is not proof, and a golden made from a broken build blesses the bug.
