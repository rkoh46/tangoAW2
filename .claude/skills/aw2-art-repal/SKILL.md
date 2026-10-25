---
name: aw2-art-repal
description: Put pictures onto a fixed palette in its slot order (aw2dev art repal): recolour art onto a CO's, a skin's or an AW2 army's palette, read and write .gpl / .pal palettes, preview before and after, and choose the CO importer's colour-matching rule (match = luma | rgb | lab).
---

Read docs/dev/art-repal.md first. Code: `devkit/aw2/artlib/repal.py`, `devkit/aw2/commands/art.py`; tests `devkit/aw2/artlib/test_repal.py`.
1. Find or make the palette: `aw2dev art repal extract co:klaus -o devkit/work/repal/klaus.gpl` (also `skin:emerald_sun`, `army:os|bm|ge|yc|bh` from the ROM, a PNG,
   a `.pal`); `aw2dev art repal convert FILE.pal -o FILE.gpl` between formats. The slot order is the palette's: index 0 is the transparent slot (`--alpha-last` for the last).
2. Look first: `aw2dev art repal preview PICTURE --palette SRC` writes before and after side by side with the slots numbered (under `devkit/work/repal/`). Try
   `--weights rgb` when hues matter more than brightness.
3. Apply: `aw2dev art repal apply --palette SRC PICTURES... -o devkit/work/repal/out` (indexed PNGs, palette exactly the source in slot order; `--keep-index` for a
   pure palette swap of an indexed picture). Keep anything made from the games under `devkit/work/` (never committed).
4. CO imports: the framing file's `match` picks the importer's rule (default `luma`; the approved COs pin `lab`). Before changing it for a CO run
   `aw2dev art repal importsheet <id>` and LOOK at `<id>_match.png`; then `aw2dev co portrait import <id>` and `aw2dev co portrait sheet <id>`, and get the owner's approval for changed art.
5. `aw2dev test` (runs `aw2.artlib.test_repal`) and `aw2dev kit check`.
