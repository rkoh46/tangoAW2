# Emerald Sun Campaign dialogue: writers' bible

You are writing the Emerald Sun Campaign's dialogue (sixteen missions, a prologue and an epilogue) so that it reads like Advance Wars at its best:
people who actually talk to each other, speeches across 2 to 4 boxes, reactions, interruptions, one joke a mission, menace, grief, stakes explained in
character. The user's standing complaint about every campaign: "make sure all dialogues aren't just 1 sentences actually talk damnit have some soul".
The BH Campaign's text (`tango-gamesupport-aw2/src/bh_text/act1.txt` etc.) is the bar for length, warmth and menace: read two scenes of it first.
Story, cast and mission list: `docs/ES_CAMPAIGN.md` (read sections 1, 3, 4, 5 and 7). That outline is approved; where this bible differs from it, this bible is newer.

## Where things are
- Your files: `tango-gamesupport-aw2/src/es_text/<yours>.txt` (one row = one dialogue box; format in `src/es_text/README.txt`). Write ONLY your own file(s).
- Lint: `python3 tools/estext/lint.py <file>` until it prints `0 errors` (grammar, every box fits two lines of 176 px in AW2's font, voice warnings, songs).
  `--counts` prints boxes per scene. Warnings are not errors, but fix the ones that are real slips.
- DO NOT run cargo, `aw2dev build`, the tests or anything that builds or touches the emulator. Do not edit any file that is not yours.

## Format in one screen (full text: `es_text/README.txt`)
```
== m01_pre                          a scene (key); optional pool: == m07_pre | KLAUS, LIVIA
@SONG ally2                          every pre / post / map scene and the prologue and epilogue names ONE song (role names below, or co:klaus)
NARRATION: Cape Astra, Green Earth. / Forty days out of Aurelium.
LIVIA: The sea is flat, Legate. / That is the only good news.
CASSIUS(h): Not yet! My horses are / still being sick in the third hold.     (h) happy face, (s) sad face
```
A box is `SPEAKER: line one / line two`: at most two lines, each at most 176 pixels (about 26 to 33 characters; capitals and `m w` are wide, `i l ,` narrow).
`{p}` is a pause inside a line. ASCII only (no accents, no curly quotes, no dashes but `-`; write `...` for a trail-off). Runs of boxes by one speaker are merged by the
engine, so a long speech costs few text ids: write speeches as 2 to 4 boxes by the same speaker.

## Length (the rule that matters)
Pre and post scenes 10 to 25 boxes; mid-battle scenes 3 to 8; a mission's `map` scene (on the world map after the win) 10 to 16. Big beats (M1, M4, M10, M13, M14, M16 and the
epilogue) 30 to 50. A recruit's post scene 25 to 40. No one-liner scenes. A scene is a conversation: people answer each other, interrupt, misunderstand, tease; the stakes and the
plot are said in character, so that a player who reads only the scenes understands the war.

## Speakers
Playable / story COs: KLAUS, AURELIA, CASSIUS, LIVIA, VARRO. Nations' COs: JESS, EAGLE, DRAKE, JAVIER (Green Earth); GRIMM, SENSEI, KANBEI, SONJA (Yellow Comet); COLIN, SASHA, OLAF, GRIT
(Blue Moon); MAX, JAKE, SAMI, NELL, ANDY, HACHI, RACHEL (Orange Star); ADDER, FLAK, KINDLE, KOAL, LASH (Black Hole, hired or enemy).
Others: NARRATION (a box with no face), LEGIONARY (an Emerald Sun soldier: the lines say who he is), SOLDIER OS / BM / GE / YC (a nation's trooper), SOLDIER BH.
`[CO]` is the CO the player leads and `[CO2]` the player's tag partner (see `@IF` below) but you will almost never need them: **the officers are characters, not the player.**
Klaus, Aurelia, Cassius and Livia speak in camp scenes ungated whoever the player leads, once they have appeared in the story (below). Only a few lines need `@IF`.

### Who is in the story when (the player's roster is separate: a CO may be on the radio before she is playable)
- M1, M2: Klaus leads. Livia (the Quaestor, the treasurer) and Aurelia (the engineer) and Cassius (cavalry, on the radio from the third hold) are with the fleet.
- M3: Aurelia's first scene as a commander. M4: Cassius appears in person as the rival (the Second Legion) and joins in M4's post. M5: Cassius leads. M6: Livia leads.
- M7: any of the four. M8: Klaus + Cassius (forced pair, the first Tag). M9, M10, M11: any (the player's pick). M10's post: Kanbei becomes a Tag partner.
- M12: Klaus + Aurelia (forced pair). M13: any pair. M14: Klaus + a free partner. M15: any pair. M16: Klaus + a free partner.
- Varro appears by radio and letter from M5 on (the Senate's letters), on the radio in M14's briefing and in person in M14's post (he falls in M14: the legion storms his camp, Castra Maxima). **He never appears after M14**: not in M15, not in M16, not in the epilogue.
- Cassius changes sides on day 4 of M14 (after Livia's page of the Free Port book, with HOBB's stamp on Varro's gold, M13 post) and is Klaus's ally for good from then on.
- M15: Drake (Green Earth, ships) and Sensei (Yellow Comet, air) hold the Strait of Elms for the Accord; Nell calls on day 6. No Eagle, no Varro, no allied relief fleets. M16: Eagle (Green Earth) and Hachi (Orange Star) hold Stormhold; Nell arrives at the gate in the post scene.

## Voices (one file of rules per speaker; keep them distinct on the page)
- **KLAUS**, Legate, the player's chief commander: stern, fair, dry, a veteran. NEVER contractions in his speech, no exclamation marks, short orders, gives credit last. A man who reads a crime scene
  instead of a map. Calls people by rank or name; calls the campaign "the road". Rarely explains himself; when he does it lands. He does not joke (the one joke a mission is Livia's).
- **AURELIA**, siege engineer: sharp, quick, thinks in loads, angles, spans, what the wall will do and what it costs; impatient with ceremony; contractions fine; dry gallows humour about stone.
  Calls Klaus "Legate", calls Cassius "Prefect" when she is annoyed. Numbers in her mouth: paces, fathoms, tons.
- **CASSIUS**, cavalry commander, Klaus's rival, the Senate's favourite: loud, quick, funny, vain, brave, reckless; contractions, exclamations, boasts about his horses and his speed; hates being right
  about anything unwelcome. Calls Klaus "old man" and "Klaus". Under the vanity he is honest; his sealed letter (take the north's granaries) is what he is ashamed of from M8 on.
- **LIVIA**, Quaestor (treasurer): poised, polite, exact, calculating, a little frightening about money. NEVER contractions. Never raises her voice. Says "Legate", "Prefect", "Chief". Everything is
  a ledger, a due date, an interest rate; a threat is a statement of terms. The campaign's one joke a mission is hers, and it is dry as paper.
- **VARRO**, Consul, Klaus's old patron, the Senate's war-hawk, antagonist until M14 (then arrested; his last scene is a resigned "my boy"): smooth, paternal, senatorial periods; kind to everyone he is about to use; never shouts; says "my boy" to Klaus. Money for the legions came from him
  and he did not ask where it came from; he reads every hunger as an opportunity. Menace by courtesy.
- **HACHI**, Orange Star's veteran who runs the general store: a merchant-veteran, dry, practical, haggling talk, calls Klaus "customer" or "friend" sarcastically, hates waste, sold the whole army its nails, fights with cheap units and deep stores (Barter, Merchant Union). **EAGLE** is proud and cocky, "Death from above!", Green Earth does not kneel; the two talk to each other like an Advance Wars double act. They defend their homes: not villains.
- **Allies and others** are in their own Advance Wars voices (Jess plain-spoken and cheerful about the Green Earth coast; Eagle "Death from above!" cocky; Drake "dude" surfer calm; Javier chivalrous, oaths of
  the towers; Grimm loud; Sensei an old man who needles; Kanbei formal honour, no contractions; Sonja cool, mocks gently, keeps a black book signed "S."; Colin rich and brash; Sasha cold and clipped;
  Olaf booming optimist; Grit slow drawl, loves a long shot; Max blunt; Jake keen; Nell the diplomat who chairs the Accord; Adder flourishes his cape; Flak is simple, hungry and loyal to whoever pays;
  Kindle haughty, loves an audience). Each nation misreads the Aureans in its own way (outline section 1).
- **NARRATION** is spare: place and time, one or two images.

## The story rules (continuity, in short; the outline has the rest)
- **The theme is conquest.** The legion is invading: landings, marches, sieges, cities and HQs taken, provinces falling, the frontier moving outward from Green Earth's south coast to Stormhold. Say what falls, how far the frontier has
  moved, what the next gate is, how the locals and officers feel about being conquered or conquerors. Only M2 (hold the ridge) and M11 (the convoy) are defensive. Underneath runs the inquiry: Klaus conquers because the trail leads through
  the Accord's archives. M6 is capture-only (14 properties at once by day 16; the audit is day 17). M14 is an assault on Castra Maxima. Stormhold (M16) has the Salt Road (coast), the Weir Valley (river), Needle Pass (high pass),
  the Quay Ward, Falcon Field (the airfield), the Market Ward (Hachi's store), the Sunrise Gate, the Citadel and the Hall of Records (the archives).
- Aurea starves: three grey harvests, ash on the wind. The relief grain came from **HOBB Grain & Freight**: no office, no owner, a stencil on every crate, a creditor's stamp on every bill. The Senate split
  its orders: find who feeds us (Klaus, in writing) and, if there is nobody, take the north's granaries (Cassius, a sealed letter). **Never reveal who HOBB is.** The BH2 hooks are the **HOBB stencil** (Livia
  recognises the mark from a bill and never says where; the same mark is on Black Hole's crates) and the **black light on the northern horizon** the night the campaign ends (nobody knows what it is). Plant them; do not explain them.
- Black Hole is not at war with Aurea. In M9 and M13 Emerald Sun fights Black Hole because the trail of HOBB's freight runs through Black Hole's yards: its quartermasters run the freight for whoever pays in advance and defend their
  cargo against what they read as raiders. Adder and Flak (M9), Kindle (M13) are officers of the freight yards, with their own manners; no event of the BH Campaign is referred to, no spoilers for BH2.
- The Allies (Orange Star, Blue Moon, Green Earth, Yellow Comet) are jumpy after the Cinder Coast fence fell; everyone assumes the green fleet is Black Hole's next trick. Each nation's scene shows it misreading the legion,
  and Klaus, over the campaign, making himself understood.
- Cassius is the antagonist of M4 only; then a rival who becomes an ally in his own time (M8 reluctantly, M14 by choice, on day 4, for good).
- Klaus's tone about the grain: he has seen the ash too; "someone is feeding us on purpose."
- No scene may state an objective that the mission does not have. The objectives are in the table of outline section 4 (and the mission list below).

## Missions and scene keys (write every key listed for your missions; extra keys only if asked)
Every mission has `mNN_pre` (the briefing and the stakes), `mNN_post` (after the win), `mNN_map` (on the world map after the win; the Accord, the Senate, the camp), and one or more mid-battle scenes
(they play on the battle map when the day comes; keep the battle's music, no @SONG there). pre, post, map and prologue / epilogue each need an `@SONG`.

| # | Title | Enemy | Mid scenes (key: when) |
|---|---|---|---|
| 1 | Landfall | Green Earth: Jess (and Drake's cruisers) | `m01_day2`: the wardens ask who they are, Jess answers in plain Green Earth |
| 2 | Testudo | Green Earth: Eagle and Jess | `m02_day4`: Eagle's wing arrives, "Anti-air, form up!" |
| 3 | The Wall | Green Earth: Javier, Drake's coast guns | `m03_day3`: a gate breaks; Javier invokes the oath of the towers |
| 4 | The Second Legion | Cassius's army (red), under fog | `m04_day5`: the battle halts, a messenger from the Senate; both read their letters (the player may be Klaus or Aurelia) |
| 5 | Dust and Wheels | Yellow Comet: Grimm, Sensei | `m05_day4`: Sensei: "You ride like you were running away." |
| 6 | Tribute | Blue Moon: Colin, Sasha | `m06_day6`: a bank run on Livia's bills |
| 7 | Mare Nostrum | Green Earth: Drake, Eagle | `m07_day5`: Eagle's air wing, "Death from above!" |
| 8 | Hammer and Anvil (tag) | Orange Star: Max, Jake | `m08_day3`: the Tag lesson, then the first Hammer and Anvil |
| 9 | Grain Ships | Black Hole freight yards: Adder, Flak | `m09_day4`: the barges turn their lights on |
| 10 | The Quiet Pass | Yellow Comet: Kanbei, Sonja | `m10_day4`: the duel of words, the battle pauses |
| 11 | The Treasure Train | marauders: Lash, Flak | `m11_day5`: the ford; Cassius's choice, the shortcut or the road |
| 12 | Siege of Iron (tag) | Blue Moon: Olaf, Grit | `m12_day5`: Grit's guns; Aurelia's plan |
| 13 | The Free Port | Green Earth (Javier), Yellow Comet (Sonja), Black Hole (Kindle), four armies, no alliances | `m13_day4`: Kindle burns a dock; Sonja moves in |
| 14 | Varro's Gambit | Varro's Praetorians in Castra Maxima, their seaside camp (the legion storms it) | `m14_day4`: Cassius changes sides on the radio; `m14_post`: Varro falls |
| 15 | Pax Romana (tag) | the Accord's strait fleet: Drake (ships) and Sensei (air) | `m15_day6`: Nell offers the table; the fleet fights on |
| 16 | Sol Invictus | Eagle and Hachi, allied, at Stormhold | `m16_phase2` (the outer wards), `m16_phase3` (the Citadel), `m16_reserves` (day 6: the defenders unleash their reserves), then `m16_post`, `m16_post2` (the Hall of Records), `m16_map` (the Accord's table), `m16_epilogue`, `m16_epilogue2` |
Plus `prologue` (narration only, rows by NARRATION: the grey harvest, the Senate's two letters; 8 to 14 pages; song `opening`).

What each scene should do (beats in the outline's table of section 5, column by column): the **pre** gives place, danger, the plan and a relationship moment; the **post** closes the fight, reveals one
new fact about the grain trail or the war, and moves a relationship; the **map** is the quiet scene afterwards (the Accord, the Senate, the camp, a letter); mid scenes are quick and sharp.

## Music (`@SONG role`; `aw2dev sound list` has them all)
`opening enemy1 enemy2 ally1 ally2 entry pinch hagevolt red blue sturm doom final ending1 ending2`, `world_map`, `aw2:<id>`, `co:<name>` (that CO's theme). Plan (outline section 7):
camp scenes (Klaus and his officers) `ally2`; the Senate and Varro `enemy1` (cold) or `enemy2` (when he gloats); a new CO's introduction `entry`; the Accord's council `ally1`; a nation's scene `aw2:421` Green Earth,
`aw2:422` Yellow Comet, `aw2:423` Blue Moon, Orange Star `ally1`; Kanbei's scene `co:kanbei`; Sonja `enemy2`; the HOBB ledger scenes (M6 map, M9 post, M13 post) `hagevolt`; crises `pinch`; the Black Hole yards
(M9, M13) `enemy1`; M16 pre and post `sturm`, Varro's fall (M14 post) `doom`; the ending `ending1`, the black light on the horizon `ending2`. A scene on the world map after a win starts with the
song of its speakers; the engine puts the map's song after it.
In one file a `map` scene can be chained of several parts: write separate scenes `m06_map`, `m06_map2` ... each with its own @SONG; the code plays them one after another. Say in your report which keys you used.

## Do not
- spoil or explain the BH Campaign's events or the BH2 plot; state who HOBB is; give Black Hole a motive for the grain;
- write one-line scenes, or let everyone sound alike (swap speaker names on a line: if it still works, it is not in voice);
- use contractions for Klaus, Livia, Kanbei, Sasha, Javier; use exclamation marks for Klaus or Livia; let Aurelia be pompous; let Cassius be silent;
- repeat the same joke; put Livia's joke on anyone else;
- exceed the box: the lint is the judge.
