# BH Campaign dialogue: writers' bible (Phase 2)

You are rewriting the BH Campaign's dialogue so it feels like the real Advance Wars games at their
best: characters who actually talk to each other, speeches that run across 2 to 4 boxes, reactions,
interruptions, humour, menace, grief, stakes explained in character. The user's complaint, verbatim:
"make sure all dialogues aren't just 1 sentences actually talk damnit have some soul". The user has
approved the style of `~/tangoAW2-bhdesign/docs/BH_DIALOGUE_SAMPLES.md` (read it first: the prologue,
M1, M14, M27 and the two epilogues are the bar). Match its length, warmth and menace.

All dialogue also has to explain the story: why Black Hole is fighting, what each nation wants, what is
at stake, where the plot goes next. A player who reads only the scenes must understand the arc.

## Where things are (your worktree: `~/tangoAW2-bhdialog`, branch `bh-dialogue`)

- Text files: `tango-gamesupport-aw2/src/bh_text/*.txt`, format in `bh_text/README.txt`. One row = one dialogue box.
  You write ONLY your own file(s). Lint with `python3 tools/bhtext/lint.py <file>` (checks the grammar and that every
  box fits two lines of 176 pixels in AW2's font, and warns about voice slips) until it prints 0 errors; also
  `--counts` for the boxes per scene.
- Rust: the missions are in `tango-gamesupport-aw2/src/bh_act*.rs`, the old dialogue is inline there (and for
  M23 to M28 and M31 in `bh_act5b_text.rs`). The old design text is `~/tangoAW2-bhdesign/docs/BH_CAMPAIGN.md` section 4.
- Voice guide: `~/tangoAW2-bhdesign/docs/BH_VOICE_REVIEW.md` (Part 1 especially). Follow it.
- DO NOT run cargo, the python tests or anything that builds: the lead builds and tests after all writers are done, and a
  half-edited tree would break everybody. You only edit your text file(s) and your Rust file's scene sites (below).

## What you must do for your missions

1. For every scene of your missions (intro = PRE, victory = POST, `after` = MAP, every trigger's `Action::Scene`,
   `front2_victory`): write a new scene in your text file and replace the Rust scene with
   `crate::bh_text::scene("key")` (or `crate::bh_text::lines("key")` when you must combine/extend lines in Rust, e.g.
   `m.after = Scene::new({ let mut v = crate::bh_text::lines("m27_map"); v.extend(crate::bh_text::lines("m28_pre_map")); v })`).
   Delete helper functions and variables that become unused (`others`, `each`, `troop`, `say`, `ALL_COS`, ... if nothing
   uses them any more; leave the file free of unused warnings where you can). Do not touch triggers' conditions,
   actions, units, maps, `bh_map_data.rs` or anything that is not dialogue or the CO changes in section "CO matrix".
2. Scene keys: `m<NN>_pre`, `m<NN>_post`, `m<NN>_map`, `m<NN>_day<D>` (a turn-start scene on day D), `m<NN>_front2_post`,
   and a short descriptive suffix for other triggers (`m09_all_home`, `m21_supply_cut`, `m30_duel_clone`, ...). Existing
   Rust scene functions with names like `m01_pre()` in act1 show the pattern; keep one key per scene.
   A key defined in a text file must be used by the code and vice versa (the lint cross-checks when you run it without arguments;
   other writers' files may still be empty then, so only fix your own keys).
3. Keep every gating mechanism, expressed in the text file:
   `[CO]` rows, `@IF NAME[, NAME]`, `@OTHER`, `@WITH NAME`, `@PARTNER NAME`, `[CO2]` (see the README). In Rust the old
   `.only/.with/.only_partner`, `others()`, `each()` all become these. In a FREE mission (below) the dialogue must read well
   for ANY CO the player may lead, including the late recruits (Clone Andy, Crumb as a CO after M28, Sonja after M31 in
   Free Play replays). The default pool is the whole 12-CO roster: STURM, VON BOLT, HAWKE, KOAL, KINDLE, JUGGER, FLAK, LASH,
   ADDER, CLONE ANDY, SONJA, CRUMB CO. A scene whose mission has a `m.pool` restriction declares it: `== m12_pre | STURM, VON BOLT, HAWKE`.
   `@OTHER` covers every pool CO not named by an `@IF` of the same scene, so an OTHER group is always complete.
   `[CO]` rows must be voice-neutral (every CO can say them in character): no contractions needed, no catchphrases;
   give the COs whose voice would break (Jugger in capitals, Flak, Lash, Kindle, Adder, Clone Andy, Crumb) their own
   `@IF` rows when a line matters. Do not make a line assume a specific player CO unless it is gated.
   Sturm may speak ungated in a FREE mission as the commander on the radio (he is Black Hole's lord whoever the player leads);
   his own personal beats go in `@IF STURM`.
4. Apply the CO matrix for your missions in the Rust (`ArmyDef` `CoSpec`s, `m.pool`) and any code that depended on a
   free pick there (a bond trigger that checked `PlayerCo(...)`: a fixed CO makes the bond automatic). Say in your report
   exactly what you changed.
5. Explain the story and plant/pay off the threads listed below, in your missions.
6. Report at the end (plain text): per scene the box counts (`--counts`), the Rust edits (functions removed, CoSpec changes), anything
   odd you found, and the lines you consider the best three of each mission.

## Format rules

- One row is one box: `SPEAKER(expression): first line / second line`. Each line at most 176 px (about 26 to 33
  characters; the lint measures). At most two lines. Longer speech = more rows by the same speaker (the compiler merges
  runs by one speaker into one text, so it costs no more than one id, and the player taps through the boxes).
- Names of the trooper faces: CRUMB, MORTAR (Sgt. Mortar, grump, "Crumb." as a full sentence), WICK (Pvt. Wick, the worrier)
  and SOLDIER all use the Black Hole trooper's face, so make the line say who is speaking (a name in the address,
  "Sergeant!", a verbal tic). Crumb is "CRUMB" (trooper face); "CRUMB CO" is the CO portrait (only after his promotion at the end of M28).
- Expression (h) happy, (s) sad on CO or trooper rows. Use them where the feeling is real.
- ASCII only. Apostrophes and `...` are fine. No `[` or `]` in text. `{p}` is a pause inside a line.
- Targets (boxes; these are floors, not ceilings, when the scene has something to say): PRE 20 to 32, POST 18 to 30,
  recruit POST 25 to 40, MAP 10 to 16, mid-battle triggers 3 to 8 each (they may stay short: a day-5 jab is fine). Big beats
  (M1, M14, M27, M28, M30, M31, Sonja's defection) 35 to 55 for the main scenes. The campaign's budget is 3,072 text ids;
  merging and sharing keep you far under it, so write what the scene needs and do not pad.
- Real back-and-forth: no more than 3 consecutive boxes by the same speaker unless it is a deliberate speech; let others
  interrupt, react, mishear, joke, push back. Show feelings through what people do and say, not narration. Narration only for
  place and time cards and rare beats.

## Voice (short; the guide has the rest)

- STURM: ruthless conqueror; cold, few words but heavy ones, contemptuous, possessive ("mine", "kneel"), no contractions, no `!`,
  never warm, never jokey, never concedes pity, thanks, fear or affection. Menace in what he implies. He may give a long speech when
  threatening or claiming. Others may read kindness into him; he never confirms it. He rescues Crumb because Crumb is his property.
- VON BOLT: ancient, creaking, gleeful, greedy; prices everything; "Kehh-heh!", mid-sentence "Kehh..." wheezes; "when I was young the sea was a puddle" (used once, in M1: do not reuse); calls Sturm "little storm", later "Sturm"; "boot boy" for Crumb; Hawke is "Marshal".
- HAWKE: cool, courteous, precise, quietly arrogant; flatters before he cuts; chess/tempo/board words; black coffee; no contractions; "Interesting." at most twice per act (and not more than once per scene).
- KOAL: road obsessive, flat, exact (surface, shoulder, camber, lane); "Mind the lane."; never "path/trail/track".
- KINDLE: haughty, theatrical, "darling(s)", "peasants", "Ahaha!", stage/light/fire; loves to burn things.
- JUGGER: ALL CAPS, labelled fields (STATUS:, ODDS:), AFFIRMATIVE / NEGATIVE / QUERY, no contractions, "HUMOR: NOT FOUND."; never says NOTED (Sturm's); says LOGGED.
- FLAK: brutish, very short sentences, loud, hungry, says "Flak" for himself, calls the player "boss", "smash".
- LASH: giggly mad-genius child; "Heehee!", "ooh, ooh", names every gadget; never warns sincerely or apologises.
- ADDER: vain, silk with a coil of menace; angles, lighting, his profile and cape; compliments that turn into insults.
- CLONE ANDY: Andy's cheer with a crack; starts a catchphrase and stops ("I can fix any--"); "Okay. Okay!"; "Sir?"; contractions.
- CRUMB: earnest, brave in small ways, funny without being a joke; talks to Gerald the biscuit; "sir/ma'am"; contractions.
- Allied COs: canon (voice guide Part 1). Contractions for Andy, Max, Sami, Jake, Grit, Grimm, Drake, Eagle, Hachi, Nell (lightly),
  Rachel (lightly), Colin; none for Kanbei, Sasha, Javier, Hawke, Sturm. Sonja: calm, analytic, ledgers and odds, a small black book, signs "S.", never "dear". Kanbei: third person ("Kanbei leads!"), honour, formal, warm and foolish about Sonja. Javier: archaic knight of the towers ("Hark!", "by my honour", "I, Javier"). Sensei: wry old trooper ("youngsters", "back in my day"). Grimm: wild bursts ("Har!", "pencil neck"). Max loud and grinning ("Big man!"), Sami clipped soldier ("Roger!", "grunts"), Grit drawl ("reckon", "Ayup", "shucks"). Olaf blustering braggart, Colin timid ("um", "I-I", calls Sasha "Sis"), Sasha polite steel and money. Eagle cocky ("Death from above!"), Drake laid-back sailor ("dude"), Jess brusque tank queen (never apologises), Nell warm and steady ("boys", luck as faith, never cruel), Andy cheerful mechanic, Rachel earnest by-the-book.
- One metaphor family per CO (voice guide). Do not reuse another CO's tic. Do not use game catchphrases word for word.
- Tics are rationed. Across the whole campaign: Hawke "Interesting." twice per act at most; Sturm "Noted." three times per act at most.

## The story (approved spine)

Thirty years ago Black Hole fell. Four nations signed the **Allied Accord**, fenced the Cinder Coast (the Black Hole continent) and split
its crystal, iron and salvage between them, and called it peace. Green Earth's wardens guard the fence. Sturm, who "comes from where the map
ends", calls the fence a claim and answers it nation by nation. What the nations want: Green Earth, the sea lanes and the salvage rights; Yellow
Comet, sealed borders and the crystal claims; Blue Moon, the iron trade and a quiet market; Orange Star (Nell, who chairs the Accord), the Accord
itself, kept by a family of soldiers. Everyone is protecting what they took.

Recruits (each wants one thing their nation refused): Von Bolt, the biggest account in the world (M1); Hawke, a stage worth commanding and
the doctrine (M4); Koal, a road with no border (M12); Kindle, an audience that never leaves (M13); Jugger, a directive that never expires
(M17); Flak, a boss who pays in fights and food (M18); Lash, a lab with no ethics board (M23); Adder, a stage in the sky and a cape (M24);
Clone Andy, a name of his own (M27). Crumb becomes a CO at the end of M28.

Threads to plant, advance and pay off (BH2 will pick them up; keep them mysterious, never explained):
- **The humming crate / HOBB.** The Obelisk and the Black Crystals hum in Sturm's pitch (M1 Von Bolt hears it). A crate on the last shelf of Von Bolt's vault is stencilled "HOBB, P." and a symbol no map has; it hums at Sturm's voice. Gerald the biscuit carries the same symbol as a maker's mark ("older than the Obelisk": Mortar, M1). Von Bolt half-remembers the name Hobb from an old ledger (M1). Sonja sees Gerald's mark and has seen it on a shipping line that does not exist (M14). Jugger may log it, Lash may want to take Gerald apart and find the mark is a keyhole, Hawke's files may show no birth record for a Pip Hobb (M28 promotion). Never solve it.
  Nell half-recognises the name Hobb (M29, when Crumb as a CO apologises to her: "I know that name from somewhere. I can't think where."). Keep it: it is a BH2 thread. Who knew the name Hobb so far: Von Bolt (a ledger, M1), Nell (M29), Hawke (no registry entry, M28), Sonja (the shipping line, M14 and M31). Nobody may say where from.
- **The Obelisk.** Dark thirty years; it lights the night the fourth flag falls (epilogue). Sturm: "Mine." Hints in the Onyx mission (M28).
- **Sonja's real agenda.** Yellow Comet's cool intelligence officer, Kanbei's daughter. Act III cameos (M12 toll hut lady writing in a small black book signed "S."; M13 a girl in the rafters taking notes; M14 she sets the trap and tests Sturm; M15 she asks her father which part of his code gives way when two parts collide; M16 she gives Von Bolt a sealed note "for the day your vault is empty"). She follows a shipping line that does not exist: the HOBB consignee. M31 is her audition. Keep it ominous.
- **Kanbei's heartbreak** (M31 letter): honour has no manual for this.
- **Hawke's ambitions.** He writes Black Hole's doctrine (chapter one "Patience"; chapter two "Succession", which he keeps for whoever stands when the storm rests). He tidies, plans, loves a worthy opponent, and is loyal to the plan, not to Sturm.
- **Crumb's origin hint.** See the crate. Nobody left him behind; he keeps count.
- **Orange Star and the Allied Nations regrouping.** Nell holds the Accord together; Andy is restless; the last train from the Rail Yard (M30) carries more than civilians; Andy's voice calls all colours east in the secret epilogue; the fence is down and a new one is being drawn.
- **What Sturm's victory woke.** The Obelisk glows. Sturm: "It is mine." The voice in the crate: "The storm was only the first knock."
- Closure vs hook: the normal epilogue closes the war and Crumb's promotion and leaves ONE thread open (the crate); the secret epilogue opens them all.

Recurring jokes (keep each to a few uses across the campaign, evolve them): Crumb's boots; Gerald (the biscuit, a geological specimen; "Gerald says ..."); Dennis the first tank; Interest, Von Bolt's rooster; Von Bolt's "second pick"; green tanks (Von Bolt will not pay to repaint); Wick's "Is it all right if..."; Mortar's "Crumb."; Koal "I like him." about Crumb (once).

## CO matrix (player CO / enemy COs per mission). FIXED = the player's CO(s) are set (no [CO], no @IF needed for the player); FREE = any recruited CO or pair

| M | Mission | Player | Enemy |
|---|---|---|---|
| 1 | Storm Landing | STURM (fixed) | Von Bolt |
| 2 | The Sleeping Foundry | FREE, pool STURM, VON BOLT | Jess |
| 3 | Blockade Runner | STURM + VON BOLT (fixed pair) | Drake + Eagle |
| 4 | Marshal in Green | STURM (fixed; he recruits Hawke himself) | Hawke |
| 5 | Night Raid | FREE | Javier |
| 6 | Stepping Stones | FREE | Drake |
| 7 | Greenhaven Arsenal | HAWKE (fixed). They hate each other: Hawke burned Green Earth's skies; Eagle wants him grounded for good | Eagle |
| 8 | The Twin Gates | FREE (+ second-front partner) | Jess (and Javier on the second front) |
| 9 | The Loot Train | VON BOLT (fixed): the old miser against the chivalrous knight over a train of gold | Javier + Drake |
| 10 | Evergreen Citadel | STURM + HAWKE (fixed pair). Eagle's line to Hawke always plays: a real rivalry scene | Eagle + Jess |
| 11 | Ashfall Pass | VON BOLT + HAWKE (fixed pair). Two old men trade barbs (Von Bolt vs Sensei); Javier's honour vs Hawke's cold calculation | Javier (Green Earth) + Sensei (Yellow Comet) |
| 12 | Highway to the Horizon | FREE PAIR (PickPair), pool STURM, VON BOLT, HAWKE | Koal + GRIMM (Grimm hired Koal for Yellow Comet's roads) |
| 13 | Festival of Flame | FREE, pool STURM, VON BOLT, HAWKE, KOAL | Kindle |
| 14 | No Soldier Left Behind | FREE | Sonja |
| 15 | The Skybridge | FREE, pool STURM, VON BOLT, HAWKE, KINDLE, KOAL (+ second-front partner) | Kanbei (Grimm on the second front) |
| 16 | Comet Keep | KOAL + KINDLE (fixed pair): Yellow Comet's former hires turn on Yellow Comet's capital | Kanbei + Sensei |
| 17 | Cold Iron | FREE PAIR (PickPair) | Jugger + GRIT (the sniper babysits Blue Moon's robot mercenary) |
| 18 | The Pit | FREE | Flak |
| 19 | The Assembly Line | FREE | Sasha |
| 20 | Moonlit Harbours | FREE (+ second-front partner) | Olaf (Colin on the second front) |
| 21 | Running Dry | FREE | Max (Orange Star) and Grit (Blue Moon), allied |
| 22 | Whiteout | JUGGER + FLAK (fixed pair): Blue Moon's former mercenaries take Blue Moon's capital; Olaf is outraged | Olaf + Sasha |
| 23 | Laboratory 7 | FREE PAIR (PickPair) | Lash + MAX (Max guards Orange Star's lab and hates "egghead weapons") |
| 24 | Sky Gala | FREE PAIR (PickPair) | Adder + SAMI (Sami's commandos run security at the Sky Gala) |
| 25 | Twin Harbours | FREE (+ second-front partner) | Sami (Hachi on the second front) |
| 26 | The Last Alliance | FREE pair | Jake, Colin, Grimm (three armies) |
| 27 | Echo | LASH (fixed): her lab made him | Clone Andy + Andy |
| 28 | Home Is Where The Black Is | STURM + CLONE ANDY (pair), with allies Rachel, Olaf, Eagle, Kanbei (five armies) | the rest |
| 29 | The Orange Gate | FREE | Nell + Max |
| 30 | Nell's Stand | STURM + a free partner (Clone Andy as partner gives the duel) | Nell, then Andy takes over |
| 31 | The Colonel's Vault (secret) | FREE | Sonja |

FREE PAIR missions (M12, M17, M23, M24; `CoSpec::PickPair`, change it in the Rust): the player leads a tag pair of any two recruited COs, so the dialogue must be pair-aware: `@IF` keys on the lead CO, `@WITH` on a CO anywhere in the pair, `@PARTNER` on the partner, `[CO]` is the lead, `[CO2]` the partner (a `[CO2]` row outside a group is said by the partner whoever it is). Give both COs of a pair something to say in the big scenes. The recruit's bond used to need a particular CO leading (`PlayerCo`); with pairs it should be met by a CO anywhere in the pair (`Cond::PlayerHas`): update the bond triggers of those missions accordingly.

Recruit partners (Koal+Grimm, Jugger+Grit, Lash+Max, Adder+Sami) need real lines throughout and a reaction when the recruit defects.
Max, Sami, Grit, Sensei, Grimm and Javier have been too absent: give them real presence wherever the matrix puts them, and in the war rooms.

## Allied war-room scenes (one per act, at the end of the MAP scene of the act's last mission: M3, M10, M16, M22, M29)

A short Allied Accord council (key `m<NN>_warroom`): framed as Black Hole's intercept (Hawke's listening post, or Crumb the runner overhearing
a relay). The Allied COs, including Max, Sami, Grit, Sensei, Grimm and Javier, argue about how to stop Black Hole: real conversation,
personalities, the plot moving. The Accord is fraying (who pays, who guards the fence, who blames whom); Nell holds it together; Andy is
restless and wants to go to the front; Sonja is silent and writes in her small black book. It fills in the story spine and plants the BH2 regroup thread.
10 to 16 boxes. Append it to the act's last MAP scene in Rust (`lines("mNN_map")` extended by `lines("mNN_warroom")`), or make it part of `mNN_map`
in the text file if simpler.

## Continuity between writers

Other writers are writing the neighbouring missions at the same time. Do not invent facts that contradict this bible. If you need a fact
from outside your missions, use only what is in this bible, the voice guide, the samples file, and the old text of that mission in
`BH_CAMPAIGN.md`. Established inside the samples (treat as canon): M1 sets the Accord, the green tanks and the paint, Mortar's "Gerald is older than the Obelisk", Von Bolt's "Hobb... that name is in a ledger", Wick noticing Gerald's stamp "like a keyhole", Crumb's four spare pairs of boots; M14 sets Sonja's trap, Kanbei's open-line scene, Sonja's "Page one", Sturm's "A crowd can be bought. A crowd can be sold.", Sonja seeing Gerald's mark; M27 sets Clone Andy's drawer in Lab 7 ("I have a cot, a mug, and a drawer"), "Pick one you would answer to at three in the morning", the "I can fix any--" joke being a line Lash wrote and got bored of.

## Later additions (after the first Phase 2)

- **Faces.** NARRATION is a blank portrait (the box with no face); CRUMB and SOLDIER use the Black Hole trooper's face; MORTAR (olive green) and WICK (amber) have their own palette-swapped trooper faces, so who is talking is visible. Consecutive boxes by different faces are different texts: the budget counts them.
- **Pairs.** On a free pair the FIRST pick leads and the second is the partner ([CO] is the lead, [CO2] the partner; `@IF` keys on the lead, `@PARTNER` on the partner, `@WITH` on either). On a fixed pair the first CO named leads (M10 Sturm+Hawke, M11 Von Bolt+Hawke, M16 Koal+Kindle, M22 Jugger+Flak). `@WITHOUT CO` shows rows only when that CO is in neither seat (M28 uses it for pairs without Clone Andy).
- **M28 is a free pair** (the player picks any two recruited COs; Hawke only suggests Sturm and Clone Andy). Sturm speaks there as Black Hole's lord, ungated; Clone Andy's own lines are `@WITH CLONE ANDY`.
- **M31 opens only after M30 is won and all nine recruit bonds are earned**, and plays "after the war": the Rail Yard's last train and the Allied regroup have happened.
- **Rationing groups.** Per-CO `@IF`/`@WITH`/`@PARTNER` groups exist only for COs the player can lead at that mission in a first playthrough (recruited by an earlier mission: Crumb from M29, Clone Andy from M28, ...). Anyone else (Free Play replays) gets the neutral `@OTHER` rows. This keeps the text ids under budget (about 2,940 of 3,072 in game, the engine keeps about 30).
