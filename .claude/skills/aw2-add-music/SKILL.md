---
name: aw2-add-music
description: Pick and wire music for scenes or battles (AW2 / Dual Strike songs, CO themes) and verify it plays with fades, using aw2dev sound list and aw2dev campaign trace.
---

1. `./aw2dev sound list` (scene roles), `--source aw2` (AW2 ids with CO themes and event-script uses: the mood each is used for), `--source ds` (Dual Strike sequence names; only the pack's story songs, power themes and new COs' themes are converted: `ds_music.rs STORY_SONGS`).
2. A scene: `@SONG role | aw2:<id> | co:<name>` in `bh_text/*.txt`; a new role: `campaign_music.rs NAMED` (an AW2 stand-in below id 505 for packs without the song).
3. A battle's theme: `MissionDef::music`. Ops: 0x41 plays (crossfade), 0x42 fades out.
4. Verify: `./aw2dev campaign trace --mission N` (song per scene, silent samples), tests `-k story_trace`. Docs: docs/dev/campaign-scenes.md.
