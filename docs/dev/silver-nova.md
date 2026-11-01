# Silver Nova's COs: Tabitha, Lili and Caulder (design note)

The user redesigned the custom army Emerald Sun as **Silver Nova** (the army's colours, HQ and name are another branch's work, `army_skin.rs`, `skins/*.toml`). This branch (`sn-cos`) deletes the five Roman COs
(Klaus, Aurelia, Cassius, Livia, Varro) and adds three, **Tabitha**, **Lili** and **Caulder**, and recasts everything that used the old five. Code: `src/es_co.rs` (numbers, texts, Enigma), `es_cos.rs` (art and texts from
the data files), `co_powers.rs` (Firestorm), `co_roster.rs` (the CO table rows), `ds_weather.rs` / `sandstorm.rs` (immunity); data `cos/{tabitha,lili,caulder}.toml`, `cos/tags.toml`; art `art/cos/<id>/` from
`art-src/cos/<id>_v1.jpg` (+ `.toml` framing); tests: `aw2dev co verify`, `tests/test_es_powers.py`, `test_es_cos.py`. Check: `aw2dev co check | portrait lint | verify`.

## The family (the owner's CO pages, used as written)
Caulder is the head of Silver Nova (bio "He seeks a world where he is free to carry out his terrible experiments", Hit: Unrestricted experiments, Miss: Ethics, quote "Fascinating..."). Lili is the youngest child of Dr. Caulder
(mind shattered by experiments; Hit: Mr. Bear, Miss: Broken "toys"; "Tee hee! Let's go, Mr. Bear!"). Tabitha is Caulder's daughter, extremely cruel and vindictive (Hit: Breakfast in bed, Miss: "Stupid Weak People"; "Stupid weak people!").
Caulder is the leader and the final boss; his daughters serve under him. The quote is each CO's signature line (power quotes, Tag quote, dialogue).

## Slots (save compatibility)
CO ids and rows are fixed in the ROM-side tables, War Room records, suspend saves and online games. The simplest safe route is **reuse**: 86 (Klaus) = Tabitha, 87 (Aurelia) = Lili, 88 (Cassius) = Caulder (Caulder was not Varro's slot
so that the three stay contiguous and the boss is not in the retired range). Slots **89 (Livia) and 90 (Varro) are retired**: `es_co::canon` maps them to Lili and Caulder, their rows are still built (art, text, numbers, power
functions are those copies, so a stray old save never reads an empty row) but `co_new::listed` keeps them out of every list and `es_co::ALL` (the three) is what the lists, the data files and the pairs use; `es_co::ROWS` (five) is
what the CO table builds. The Emerald Sun Campaign's roster is now four (Tabitha, Lili, Colin, Kanbei): the unlock bits of Colin and Kanbei move from 4, 5 to 2, 3 (a save made between M3 and M6 may show Colin one mission early).
`SIM_VERSION` 42.

## The numbers (the engine adds every power's own +10% firepower and +10% defence)
| | Day to day | CO Power | Super CO Power |
|---|---|---|---|
| **Tabitha** | Mega Boost: +18% attack and defence | none (0 stars) | **Firestorm**, 9 stars: 8 HP to every unit of other teams within 2 (13 cells) of the richest site, cannot kill (never below 1 HP), no stun |
| **Lili** | Lullaby: +10% attack and defence | **Enigma**, 3 stars: sand, snow or rain at random for two days; her units ignore weather and move +1 | none (0 stars, no menu entry) |
| **Caulder** | Hypothesis: +18% attack and defence; Sturm's movement | none (0 stars) | **Cataclysm**, 4 stars: heal 5 HP, +25% attack and defence more |
Caulder's `[scop] mods` are +15 / +15: with the day-to-day 18 and the power's own 10 a unit totals +43% (the user's "+25% more" counts the game's own +10). Tag Powers: Tabitha + Lili Two Hands 120% 2 stars, Tabitha + Caulder
Family Ties 108% 1, Lili + Caulder Bedtime Story 115% 2, Tabitha + Kanbei Iron Pact 120% 2, Lili + Colin Toy Market 116% 2; every other pair is 95.

## Enigma (Lili): weather
The power function (`es_co::ENIGMA`, ROM) calls AW2's weather setter `sub_08035144(2)` and then AW2's usual power procedure. The trap on the setter (`ds_weather::power_weather` -> `es_co::weather_pick`) replaces the weather by a roll of the
game's own RNG (`sandstorm::next_random`, the same on every peer and every rollback): 1 snow, 2 rain, 3 sand. **Sand is a Dual Strike weather**: AW2 has no fourth weather, so the sandstorm is `sandstorm.rs`'s one-day state beside clear weather
(range -1 for ranged units, sand colours and grains). Every Silver Nova CO exists only with the Dual Strike features on, so the sandstorm is always there; the roll falls back to snow or rain only (`es_co::roll(r, false)`) if it is not.
Two days: snow and rain use the flag Olaf's snow uses (`POWER_SNOW`); the sandstorm is switched off by `es_co` after two of Lili's turn starts (the engine's own day count only runs in Random weather); a map whose weather is permanent keeps it.
The weather and the immunity do not carry over to a new map; the state (turn starts left, her army, the roll) rides in a suspended game's tag tail (`es_co::lili_state`). Immunity (no sandstorm range cut, no snow fuel doubling), +1
move and +1 vision in rain (rain's -1 is made up) last as long as the Enigma weather, both days (`es_co::enigma_on`; her CO Power itself ends at her next turn start, the table's +1 move covers day 1 and `co_roster::stat_function` adds it on day 2). The computer plays her power (`ds_ai_power.rs`).

## Firestorm (Tabitha)
`co_powers::FIRESTORM_FN`: the meteor strike (`strike_fn`) at 80 (8 HP) with Von Bolt's animation script (`power_anim::EXM_SCRIPT`, Dual Strike art) and AW2's meteor script without the pack's pictures. The site is the richest cluster by
funds (Dual Strike's funds score at 8 HP, her team's units not counted, `STRIKE_FIRESTORM`); her own team is spared; no unit dies (the strike leaves 1 HP); no stun (`strike_square` only stuns for Von Bolt).

## Cataclysm and Sturm's movement (Caulder)
Heal 5 is `es_co::HEAL5` (`RepairUnit(unit, 5, 0)`, free) as the presentation row's unit effect. His movement charts are Sturm's row's charts of each level (`co_roster::new_row`), as Asuka once had: Sturm's chart keeps the terrain that
is closed to a Tank (mountains, rivers); every passable terrain costs 1.

## Art
The owner's three pictures (`art-src/cos/*_v1.jpg`, pixel art with a baked-in checkerboard for Tabitha) are imported directly (`aw2dev co portrait import`): grid resample, background flood (the checkerboard flattened first, a pocket by
`hole_min`), palette, outline; faces stay as supplied (they all face as drawn: Caulder to the left, Lili slightly left, Tabitha front: no flip). Their heads are wider than AW2's 24-cell mug, so the large art is 1x (128 x 160 cells) and the faces `mug_scale = 1`.
Caulder and Tabitha keep the white hair, coat, blouse and gloves, so no `fringe` (it would eat them); Lili has `fringe = "light"` with her pale hair protected (`edge_protect`). The name graphic gains the letters T b d h t.

## Music
Each CO has her/his own full theme from the music branch: `music/sn/{tabitha,lili,caulder}.m4t` ("Stupid Weak People", "Carousel", "Claw"), registered for slots 86, 87, 88 in `es_music::SOURCES` (the retired slots 89 and 90 have no song: the CO table's like-CO song). The old Roman themes (music/es klaus, aurelia, varro, cassius, livia) are deleted.

## Casting
| Where | Old CO | New CO |
|---|---|---|
| ES M1, M2 | Klaus | Tabitha |
| ES M3 | Aurelia | Lili |
| ES M4 (enemy Second Corps; the player picks Tabitha or Lili) | Cassius | Caulder |
| ES M5 | Cassius | Lili |
| ES M6 | Livia | Lili |
| ES M7, M9, M10, M11, M13, M15 (free pick) | Klaus, Aurelia, Cassius, Livia | Tabitha, Lili |
| ES M8 and M12 (forced pair) | Klaus + Cassius / Klaus + Aurelia | Tabitha + Lili |
| ES M14 (boss, Fort Meridian) / the army that changes sides on day 4 | Varro / Cassius | Caulder / Lili |
| ES M16 (player lead + partner) | Klaus + a free partner | Tabitha + a free partner |
| BH2 M32 (secret; enemy pair, waves) | Klaus + Aurelia (waves by Cassius, Aurelia, Livia) | Caulder + Tabitha (waves by the vanguard, Lili, Lili) |
| Gauntlet roster (the free pick) | Klaus, Aurelia, Cassius, Livia (not Varro) | Tabitha, Lili, Caulder |
The Gauntlet's Iron Crown has no deleted CO among its enemies (the Emerald Sun *army* there is the other branch's). Asuka stays out of the Silver Nova Campaign.
