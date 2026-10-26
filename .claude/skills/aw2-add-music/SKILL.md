---
name: aw2-add-music
description: Pick and wire music for scenes or battles (AW2 / Dual Strike songs, CO themes) and verify it plays with fades, or COMPOSE a new song of our own (text file -> AW2's sound engine, AW2's own instruments) with aw2dev sound compose / render / loopcheck / levels / stems / pitchcheck.
---

## A. Pick existing music for a scene or a battle
1. `./aw2dev sound list` (scene roles), `--source aw2` (AW2 ids with CO themes and event-script uses: the mood each is used for), `--source ds` (Dual Strike sequence names; only the pack's story songs, power themes and new COs' themes are converted: `ds_music.rs STORY_SONGS`).
2. A scene: `@SONG role | aw2:<id> | co:<name>` in `bh_text/*.txt` / `es_text/*.txt` (`co:klaus` .. `co:varro` are the Emerald Sun COs' own themes); a new role: `campaign_music.rs NAMED` (an AW2 stand-in below id 505 for packs without the song).
3. A battle's theme: `MissionDef::music`. Ops: 0x41 plays (crossfade), 0x42 fades out.
4. Verify: `./aw2dev campaign trace --mission N` (song per scene, silent samples), tests `-k story_trace`. Docs: docs/dev/campaign-scenes.md.

## B. Compose a song of our own (docs/dev/music-kit.md)
1. Study how AW2 writes its themes: `./aw2dev sound dump 211` (Kanbei), `./aw2dev sound levels --ref` (the loudness of ten of AW2's themes), `./aw2dev sound voices --group A [--sheet out.png]` (the instruments, with the `shift` each needs).
2. Copy `tango-gamesupport-aw2/music/es/<neighbour>.m4t`; write the song at the sounding pitch (format: header of `src/es_music.rs`, the doc). New song for a new CO: add it to `es_music::SOURCES` and `test_es_music.py COS`.
3. `./aw2dev sound compose --dir tango-gamesupport-aw2/music/es`: it must compile (a bar of the wrong length names its place) and keep the rules (loop 45..90 s, at most 8 notes at once, 8 tracks).
4. `./aw2dev sound render --song <name> --dir tango-gamesupport-aw2/music/es` (no rebuild: the game reads the folder): WAV in `devkit/work/music/`, a picture, the loop seams and the level next to AW2's themes. Look at the pictures, **listen to the WAV**.
   `./aw2dev sound stems <name>` for the mix (the lead 3 to 6 dB above the rest; set `gain=` on a track), `./aw2dev sound pitchcheck` after a new instrument (its `shift`).
5. `./aw2dev build --all`, `./aw2dev test`, `./aw2dev suite --only es_music` (registered, intact in ROM, plays through its loop), `./aw2dev net repeat` (equal hashes).
Never commit a WAV, a picture or anything from the ROMs; the songs are text.
6. **Quoting one of AW2's songs** (a CO theme that echoes another): **never write its notes into the repository**, not in an `.m4t`, a table, a document or a test (the repo is public and the music is Nintendo's). Use a `rom` line (docs/dev/music-kit.md, "Quoting AW2's songs"): `rom NAME song=ID track=T bars=A-B transpose= srcshift= lower= inst= peak=`, and `@rom:NAME` in a section's track line. `sound dump ID` shows the song so you can pick tracks and bars (look, do not copy); `sound voices` gives the source voice's `shift`. The game reads the events from the player's ROM when it builds the song: check with `aw2dev sound compose` (reads the ROM through `--rom`) and `sound render`, and add the source song to the `music` group of `test_sonja_untouched.py` so its row and bytes are proved unchanged.
