# Palette replacement (`aw2dev art repal`)

Puts pictures onto a **fixed palette in its slot order**: a recolour onto an army's row, a CO picture onto a CO's 16 colours, a sprite sheet onto a `.gpl` an artist
handed over. Code: `devkit/aw2/artlib/repal.py` (the method, palette readers and writers), `devkit/aw2/commands/art.py` (the CLI); tests
`devkit/aw2/artlib/test_repal.py` (run by `aw2dev test`); skill `aw2-art-repal`.

## The method
Every opaque pixel goes to the palette entry with the **smallest weighted absolute RGB difference**, `wr |dr| + wg |dg| + wb |db|`, with the luma weights
30 / 59 / 11 by default (`--weights rgb` = 1 / 1 / 1, or any `a,b,c`); a tie goes to the lower slot; no dithering (`--dither none`, the only mode: pixel art keeps
its flat areas). The transparent slot is index 0 (`--alpha-last`: the palette's last entry, the Mugen convention; `--opaque`: none); it is never used for an opaque
pixel, and pixels with alpha below 128 go to it. The output is an indexed PNG whose palette is exactly the source palette in slot order (4-bit when it has at most 16
entries; written without Pillow's `optimize`, which would drop and reorder unused entries). `--keep-index` swaps only the palette of an already indexed picture.
The method follows PalReplacer by Hendrik Iben (2012, MIT; `CREDITS.md`); this is our own code, nothing of it is copied.

## Palette sources (`--palette`, `extract`)
| Source | What |
|---|---|
| `file.gpl` | a GIMP palette, in its order |
| `file.pal` | raw 16-bit entries, little-endian, GBA order (`0bbbbbgggggrrrrr`); JASC-PAL text and RIFF PAL are read too |
| `picture.png` | an indexed PNG's palette in slot order (trailing unused black entries trimmed); an RGB picture's unique colours in the order they first appear (at most 256) |
| `co:<id>` | a custom CO's committed palette (`tango-gamesupport-aw2/art/cos/<id>/large.png`, 16 entries, 0 transparent); a recolour-based CO (Clone Andy) wears its donor's and has none |
| `skin:<id>` | an army skin's map-unit palette as `Skin::unit_row` builds it (`armyskinlib.options.unit_palette` on the player's AW2 ROM) |
| `army:os` `bm` `ge` `yc` `bh` | AW2's own map-unit palette row of that army (`UNIT_PAL` `0x0810E6E0` + 32 per colour, read from the ROM; docs/dev/army-packs.md) |

The ROM is only read; nothing from it is written into the repo (the outputs go where `-o` says: keep game-derived pictures under `devkit/work/`).

## Commands
| Command | What |
|---|---|
| `aw2dev art repal apply --palette SRC [--weights luma] [--dither none] [--keep-index] [--alpha-last] [--opaque] IMAGES... -o DIR` | indexed PNGs `DIR/<name>.png`, with the slots used |
| `aw2dev art repal extract SRC -o FILE.gpl` or `.pal` | any source written as a palette file |
| `aw2dev art repal convert FILE.pal -o FILE.gpl` | palette file to palette file |
| `aw2dev art repal preview IMAGE --palette SRC [--out PNG]` | before and after side by side, the palette's slots numbered (transparent slot framed red); default `devkit/work/repal/<name>_preview.png` |
| `aw2dev art repal importsheet [CO ...]` | the CO importer's `match` rules side by side (below), `devkit/work/repal/<co>_match.png` |

Pass is exit 0; a picture that cannot be mapped (`--keep-index` past the palette's end, transparent pixels with `--opaque`) is reported and makes the exit 1.

## The CO importer's `match` key
The pixel-art importer's last step (`colib/pixelart.py` `quantise`, marked "art repal hook") maps every native cell to the CO's 14 colours. The framing file
(`art-src/cos/<id>_v5.toml`) chooses the rule with `match = "luma" | "rgb" | "lab"`: **default `luma`** (the weighted rule above) for a new CO; `lab` is the Lab
distance the approved COs were imported with. A caller that passes no `match` (the illustration importer) keeps `lab`.

Compared on the approved art (`aw2dev art repal importsheet`; numbers over the figure's cells of the large art, "dark" = source luma below 90):

| CO | rule | luma error all / dark | Lab error all / dark | cells changed from lab |
|---|---|---|---|---|
| Klaus | lab / luma | 10.3 / 9.7 vs 8.0 / 7.4 | 7.6 / 8.0 vs 9.1 / 9.0 | 543 |
| Aurelia | lab / luma | 10.3 / 10.8 vs 7.1 / 8.7 | 6.9 / 7.2 vs 10.2 / 11.3 | 1013 |
| Cassius | lab / luma | 7.1 / 6.9 vs 4.3 / 3.7 | 4.8 / 4.6 vs 5.6 / 5.5 | 909 |
| Livia | lab / luma | 9.1 / 8.5 vs 7.0 / 7.3 | 6.2 / 6.4 vs 7.8 / 7.4 | 681 |

Luma matching keeps the brightness of the dark areas closer (lower luma error) but it ignores hue almost entirely for blue and little for red, so on these pictures it
moved cells to colours of the wrong hue: Klaus's white shirt and his face get peach and grey specks, Aurelia's dark-brown hair turns red in places, Cassius's navy-black
coat turns brown-black. The dark areas gain no shading steps (the same number of tones; Livia's one fewer). So the four approved COs pin `match = "lab"` and their committed art is
unchanged (`aw2dev co portrait import --check`). Asuka (illustration importer, branch `asuka`) compared the same way: 623 pixels change, the uniform's shading is the same and the
book gets dark blotches, so she stays on `lab` too (the illustration importer calls `quantise` without `match`). Luma is the default for a new picture; look at
`importsheet` before keeping it.

## Limits
No dithering and no palette generation (the palette is given; the CO importer makes its own with k-means). Weighted absolute RGB is not perceptual: for art with
strong hues next to similar-brightness neutrals, `--weights rgb` or the importer's `lab` can be the better choice; look at `preview`.
