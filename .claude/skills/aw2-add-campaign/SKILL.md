---
name: aw2-add-campaign
description: Add or extend a custom campaign (missions, scenes, songs, prologue) on the BH Campaign's data-driven engine; list and trace scenes and music with aw2dev campaign.
---

Read docs/dev/campaign-scenes.md and docs/AW2.md "BH Campaign".
1. Missions are `MissionDef`s (`bh_act*.rs`), maps `five/bh/*.txt` (`aw2dev maps lint`, skill aw2-map-lint), dialogue `src/bh_text/*.txt` (`tools/bhtext/lint.py`).
2. Every story scene (intro, victory, scenes on the map after a win, prologue) names a song: `@SONG role` (`aw2dev sound list`); chain scenes with `bh_text::chain`. A scene between missions is `mNN_sturm`-style: last in the `after` chain.
3. `./aw2dev build --examples`, `./aw2dev campaign scenes` (every scene with its song), `./aw2dev campaign trace --mission N` (no silent dialogue; fades), `./aw2dev gfx check`.
4. `aw2dev test`, `tools/aw2test` `-k bh_text_budget` (3,072 text ids), `./aw2dev suite`. Show the scene table and the new lines to the user before any release.
