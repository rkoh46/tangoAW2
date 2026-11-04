---
name: aw2-ui-screen
description: Build a new tangoAW2 screen, box or status line in Advance Wars 2's own style (plates, windows, font), then run the text audit.
---

Rule: it must read as part of AW2. No plain black/dark bars with text, nothing debug-looking. Reuse native screens when possible.
1. Find the nearest existing example: `unranked.rs` (picking plate, Rules-page plate), `online.rs` (`Canvas::window`, `Canvas::plate`, `Canvas::text`, `text_width`),
   `online_menu.rs`, `result_view.rs`. Copy their helpers; do not draw custom rectangles or fonts.
2. Put drawing in the screen's `apply`/`draw` over the game's own picture; state in registered EWRAM (`ram_map.rs`, docs/dev/ram-map.md);
   presentation only unless both peers must agree (then see architecture-online.md sim_version rules).
3. Add the page to `examples/aw2_online_text_audit.rs` at its LONGEST strings; `./aw2dev build --all`; `./aw2dev audit text` must say `done: 0 problems`.
4. View the BMPs in `devkit/work/audit/text/` (and a live frame: `./aw2dev live lobby --players 2 --local`, `./aw2dev sheet latest`).
5. If another seat can see the screen while not its mover, apply skill aw2-waiting-view.
6. Show the user the sheets before release.

## Screens that show COs (the Gauntlet's army screen is the model)
- `./aw2dev gauntlet army-sheet [--map NN ...]`: the army screen in three states (as it opens, CO changed, R pressed) and three looks (AW2, DS + tilt, DS flat) as one sheet; look at colours, faces, whole names, the tag sprites.
- `./aw2dev gauntlet faces [--map NN ...]`: each CO's dialogue-box face beside the same CO on the army screen: the faces must match in direction and colours.
- Scenes on a five-army battle: `./aw2dev campaign scene-check` (BG palette 9 is shared by the moved-unit grey and dialogue faces).
