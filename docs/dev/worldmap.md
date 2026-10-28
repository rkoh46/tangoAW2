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
- **Dev aid** `TANGOAW2_BH_WORLDMAP=bh2` (docs/dev/env-aids.md): the BH Campaign on this map, mission i on the picture's flag place i.

## Tools and tests
- `aw2dev worldmap preview bh2 [--conquered 1,3|all] [--out PNG]`: the resampled picture, the conversion read back from the `.bin` (as the GBA draws it), conquered states and the camera's corner views, the region mask. `devkit/work/worldmap/`.
- `aw2dev worldmap check bh2`: budgets, regions cover at least 97% of the picture's land, every flag place inside its nation, the `.bin` equals what `convert` makes now (stable). Run by `aw2dev test` (`aw2.worldmaplib.test_worldmap`) with the Rust tests `world_picture::tests`.
- Live: `AW2TEST_REVIEW_DIR=<dir> python3 tools/aw2test/run.py --mode ds -k bh_picture_map` boots the BH Campaign on the picture, photographs it unscrolled and scrolled, again with Orange Star's seven missions won, and checks the palette RAM re-tint.
- Limits: 256 x 256 shows 5 times less detail than the 1233-pixel picture; its own lettering was already soft and does not survive. A second picture needs its own toml; `world_picture::BH2` and `dev_picture` list sources.
