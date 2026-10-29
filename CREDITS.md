# Credits

## tangoAW2

- Emerald Sun's four COs (Klaus, Aurelia, Cassius, Livia): portrait art provided by the project owner (`art-src/cos/`, converted to the game's formats in `tango-gamesupport-aw2/art/cos/`).
- Asuka (Sonja after she defects to Black Hole): portrait art provided by the project owner (`art-src/cos/asuka_v2.png`, upscaled pixel art on white, imported by `aw2dev co portrait import` with the pixel-art mode: native grid, background and light fringe cut, one palette keeping her uniform's dark shades, facing right like AW2's COs; nothing redrawn. `asuka_v1.jpg`, the first illustration, stays as the illustration importer's test input). Her theme "Iron Verdict" (`music/es/asuka.m4t`, a guitar-driven rock song; "Defector's March" and two heavier / more melodic takes are in `music/es/alt/`) is an original composition of tangoAW2 (notes written for this project, played with Advance Wars 2's own instrument samples read from the player's ROM; it quotes no song of Advance Wars 2, and `aw2dev sound similar` checks that none of its melodies match Sonja's or Sturm's).
- Aria (Nell's sister, Commander of the New Accord): portrait art provided by the project owner (`art-src/cos/aria_v1.jpg`, pixel art whose "transparent" background is a checkerboard baked into the JPEG; imported by `aw2dev co portrait import` with the pixel-art mode: native grid, checkerboard removed, one palette, facing right as supplied; nothing redrawn). Her theme is Nell's song for now; her own, "Last Accord", is on the `bh2music` branch.
  The name graphics are set in letters drawn for this project (`devkit/aw2/colib/namefont.py`).
- Palette replacement (aw2dev art repal) follows the method of PalReplacer by Hendrik Iben (2012, MIT): weighted nearest-colour mapping onto a fixed palette in slot order.
  Nothing of the jar is copied (`devkit/aw2/artlib/repal.py` is our own code).

- Advance Wars 2 RAM and ROM research: Xenesis and the
  [Wars World News](https://www.warsworldnews.com) hacking community, the
  [aw2bhr decompilation](https://github.com/Eebit/aw2bhr) (Eebit, npiriou,
  Mad-Man-Dan, Veslyquix and contributors; used as a map of the game's code,
  none of it is copied), and the [libretro cheat database](https://github.com/libretro/libretro-database)
  for the Advance Wars 2 CodeBreaker list.
- Advance Wars: Dual Strike research: sturmds' [Advance Wars: Dual Strike decompilation](https://github.com/sturmds/advance-wars-dual-strike-decomp)
  (CC0), the reference for Dual Strike's battle rules, computer player, maps, History, scores and Design Room
  generator as ported in 0.7.0; tangoAW2 reads Dual Strike's data from the player's own ROM and ships none of it.
- Emulation: [endrift](https://twitter.com/endrift) (mGBA), [Arisotura](https://github.com/Arisotura) (melonDS).
- Emerald Sun, tangoAW2's sixth army, is inspired by the Jade Sun army of [Advance Wars By Web](https://awbw.amarriner.com) (AWBW) and its community artists: the idea of a Roman-themed army with red-crested legionaries, a pale domed HQ and a sun for its emblem. The palette and the pixel art are drawn for tangoAW2 and are original work under the repository's licence; no AWBW image or data is used or distributed.

Advance Wars is a trademark of Nintendo. tangoAW2 is not affiliated with
Nintendo or Intelligent Systems.

## Tango

tangoAW2 is built on [Tango](https://github.com/tangobattle/tango), which
would not be a reality without the work of these people.

### Development

- Emulation: [endrift](https://twitter.com/endrift) (mGBA)
- Reverse engineering: [pnw_ssbmars](https://twitter.com/pnw_ssbmars), [XKirby](https://github.com/XKirby), [luckytyphlosion](https://github.com/luckytyphlosion), [LanHikari22](https://github.com/LanHikari22), [GreigaMaster](https://twitter.com/GreigaMaster), [Prof. 9](https://twitter.com/Prof9), [National Security Agency](https://www.nsa.gov) (Ghidra), [aldelaro5](https://twitter.com/aldelaro5) (Ghidra)
- Saves: [ore4545](https://github.com/ore4545)
- Porting: [ubergeek77](https://github.com/ubergeek77) (Linux), [Akatsuki](https://github.com/Akatsuki) (macOS)
- Game support and engine: [weenie](https://github.com/bigfarts), [GreigaMaster](https://twitter.com/GreigaMaster)
- Odds and ends: [zachristmas](https://github.com/zachristmas), [Akatsuki](https://github.com/Akatsuki), [sailormoon](https://github.com/sailormoon), [Shiz](https://twitter.com/dev_console), [Karate_Bugman](https://twitter.com/Karate_Bugman)
- [Countless open source projects](https://tango.n1gp.net/licenses)

### Translation

- Japanese: [weenie](https://github.com/bigfarts), [Nonstopmop](https://twitter.com/seventhfonist42), [dhenva](https://twitch.tv/dhenva)
- Mandarin (mainland China): [weenie](https://github.com/bigfarts)
- Mandarin (Taiwan): [weenie](https://github.com/bigfarts)
- Spanish (Latin America): [Karate_Bugman](https://twitter.com/Karate_Bugman)
- Portuguese (Brazil): [Darkgaia](https://ayo.so/darkgaiagames), [mushiguchi](https://twitter.com/mushiguchi)
- French (France): [Sheriel Phoenix](https://twitter.com/Sheriel_Phoenix), [Justplay](https://twitter.com/justplayfly)
- German (Germany): [KenDeep](https://twitch.tv/kendeep_fgc), [ChinaTV](https://twitter.com/ChinaTV9)
- Vietnamese: [ExeDesmond](https://twitter.com/exedesmond), [ShironaNep](https://www.youtube.com/user/minhduc1411vip)
- Russian (Russia): Passbyword, [Sest0E1emento5](https://www.youtube.com/channel/UCwpjuY9bYqNzsUG1QP50PLQ)
- Dutch (Netherlands): [Virillion](https://twitter.com/Virillion)

### Special thanks

- Playtesting: [N1GP](https://n1gp.net)
- #1 fan: [playerzero](https://twitter.com/Playerzero_exe)
