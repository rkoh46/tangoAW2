# Picture world map (`WorldArt::Picture`)

The BH2 Campaign's world map is the project owner's AW1-style picture, imported pixel by pixel (a resample, no painting) and played on AW2's own map screen.
Code: `devkit/aw2/worldmaplib/` (`convert.py`, `binfmt.py`, `tool.py`), `devkit/aw2/commands/worldmap.py`, `tango-gamesupport-aw2/src/world_picture.rs`,
`ds_worldmap.rs` (install, tick, camera), `campaign_model.rs` (`WorldArt::Picture`, `dev_picture`). Source: `art-src/worldmap/bh2_world.jpg` + `bh2_world.toml`;
output (checked in): `tango-gamesupport-aw2/art/worldmap/bh2_world.bin` (format in `binfmt.py`). No ROM is needed for any of it.

## Conversion (`aw2dev worldmap convert bh2`)
1. Crop the black strip, resample (Lanczos) to 256 x 256: the picture is square, and the map layer is 512 x 256 at most. Nothing is dithered.
2. Classify every pixel: the sea or one of five nations (Orange Star, Blue Moon, Green Earth, Yellow Comet, Black Hole's own grey island, bottom left) by the colour of its land
   (seed pixels in the toml); specks, text strokes and the compass are sea or the land around them, holes in the land are land, the coast's rim joins the land.
   The class per pixel is the region mask.
3. Fit nine 15-colour palettes. Each palette entry belongs to one class (`tags`); the palette plan in the toml says how many entries a palette gives the sea and each nation
   (e.g. sea 4 + Green Earth 11). Tiles pick the palette that draws them best (a colour error plus a penalty for a class the palette lacks), k-means refits the entries; 5-bit colours.
4. Tiles: 8 x 8 cells deduplicated (a tile and its flips are one), tile 0 blank; over 767 distinct, the most alike (shade weighted) are folded together.
5. Conquest: each entry also has a Black Hole colour (same lightness, purple), so a nation is re-tinted by swapping its tagged entries.

Budgets (BH2): 768 / 768 tiles, 9 / 9 palettes, 15 / 15 colours, 32 x 32 cells (one screen of the 64 x 32 layer, the other blank), PSNR about 38 dB against the 5-bit resample.

## In the game
- The picture's tiles, tilemap and palette go where Omega Land's go (`ds_worldmap::install`, marked `MAGIC + 1`); BG1 (AW2's sea) is off as on Omega Land. The camera and cursor stop at the picture's edges (`dims`: 256 x 256 scrolls 16 x 96).
- **Conquest** (`ds_worldmap::picture_conquest`): a nation is conquered when it has missions (by the place of their flags, `PictureMap::region_at`) and all are won. Its tagged entries are written
  in the ROM image's palette (the screen copies it, so fades work) and, with the map up, in the palette buffer and palette RAM. Won missions keep a starred flag as on Omega Land.
- **Black Hole's own island** (class 5, the grey island bottom left; the owner's design, 2026-10-28) is Black Hole's from the start: `PictureMap::conquered` always includes its bit, so it is drawn in Black Hole's colours and its missions (M1, M2, secret M26) never change it. Mission flags: `world_picture::BH2_FLAGS` (checked by `world_picture::tests::bh2_flags_lie_in_their_nation` and `aw2dev bh2 check`, docs/dev/bh2-maps.md).
- **Dev aid** `TANGOAW2_BH_WORLDMAP=bh2` (docs/dev/env-aids.md): the BH Campaign on this map, mission i on the picture's flag place i.

## Tools and tests
- `aw2dev worldmap preview bh2 [--conquered 1,3|all] [--out PNG]`: the resampled picture, the conversion read back from the `.bin` (as the GBA draws it), conquered states and the camera's corner views, the region mask. `devkit/work/worldmap/`.
- `aw2dev worldmap check bh2`: budgets, regions cover at least 97% of the picture's land, every flag place inside its nation, the `.bin` equals what `convert` makes now (stable). Run by `aw2dev test` (`aw2.worldmaplib.test_worldmap`) with the Rust tests `world_picture::tests`.
- Live: `AW2TEST_REVIEW_DIR=<dir> python3 tools/aw2test/run.py --mode ds -k bh_picture_map` boots the BH Campaign on the picture, photographs it unscrolled and scrolled, again with Orange Star's seven missions won, and checks the palette RAM re-tint.
- Limits: 256 x 256 shows 5 times less detail than the 1233-pixel picture; its own lettering was already soft and does not survive. A second picture needs its own toml; `world_picture::BH2` and `dev_picture` list sources.

# AW2's own map in the BH Campaign (`WorldArt::Aw2`, `bh_conquest.rs`)
The BH Campaign plays on AW2's own world map; as missions are won the land turns Black Hole's colours (the picture map's dark purple), mission by mission.
- **How AW2 draws it** (read from the ROM at run time; nothing is committed): BG3 tiles at `0x081CC5F0` (LZ77, 704), tilemap `0x081D0BAC` (LZ77, 2 x 32 x 32 cells), ten palettes at `0x081D1504` = BG banks 6..15.
  Land is bank 11 Orange Star, 12 Blue Moon, 13 Yellow Comet, 14 Green Earth, 10 Black Hole's island (grey). Every bank also holds the sea (entries 10..14), labels and region borders (entry 15); land is entries 1..=9.
  Banks 6..9 are the vivid nation colours AW2's own campaign repaints won missions with (cells switched to them); in a BH session no cell uses them.
- **Conquest**: land entries are re-tinted (lightness mapped from dark to light purple, `bh_conquest::tint`). Bank 10 is tinted from the start (Black Hole's island). Banks 6..9 become the tinted twins of 11..14 and the won land's tilemap cells
  point at them. A land cell goes to the nearest flag of its nation (a flag's nation = bank of the nearest land cell), dark when that mission is won; a nation with all missions won is dark whole.
- **Where**: the campaign's tilemap (LZ77) and palettes are copies in the ROM image (`bh_conquest::TILEMAP`/`PALETTE`); in a BH session (`ds_worldmap::tick`) the screen's pool words point at them, so setup, fades, Continue and Free Play draw it. With the map up the VRAM tilemap and palette RAM are rewritten when the set of won missions changes. AW2's own campaign, DS, ES, BH2 and Gauntlet never see it.
- **Tests**: `python3 tools/aw2test/run.py --mode ds -k bh_conquest` (start, some, whole nation, end: banks and palettes read from VRAM / palette RAM; AW2's own campaign's map has no tint); `AW2TEST_REVIEW_DIR=<dir>` keeps the full-map pictures and screens. Rust: `cargo test -p tango-gamesupport-aw2 --lib bh_conquest`.
- Limits: darkening follows 8 x 8 cells (a palette is per tile), so the edge between won and open land is a staircase and need not follow AW2's white region borders.
