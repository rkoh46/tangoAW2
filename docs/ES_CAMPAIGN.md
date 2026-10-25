# The Emerald Sun Campaign: design (phase 1, for approval)

Sixteen missions played as **Emerald Sun**, tangoAW2's sixth army (Roman-themed, inspired by AWBW's Jade Sun; every picture of it is original or composed from AW2 / Dual Strike parts at run time,
`docs/dev/army-packs.md`), with four new Roman COs. It is the second custom campaign on the BH Campaign's data-driven engine (`docs/AW2.md` "BH Campaign", `docs/dev/campaign-scenes.md`) and the
Campaign sub-menu already has its entry (opens "Coming soon" until phase 2) and the BH2 placeholder above it.

Status: **phase 2 built, awaiting approval** (branch `esmissions`, behind the development flag `TANGOAW2_ES_CAMPAIGN`; see section 11 for what was built and where it differs from this outline). Phase 1 gave the menu, the CO data files and portrait options
(`tango-gamesupport-aw2/cos/`, `aw2dev co ...`, `docs/dev/co-kit.md`) and this outline. Everything marked "proposal" still waits for the user.

Contents: 1 Premise and story spine - 2 The four COs (numbers, balance note, Tag Powers) - 3 Who joins when - 4 The sixteen missions - 5 Scenes and how much is said - 6 Variety, threats and answers -
7 Music plan - 8 Rules carried over from the BH Campaign - 9 Building it (phase 2 plan) - 10 Open questions.

## 1. Premise and story spine

**Who they are.** The **Imperium of Aurea**: a southern sea-state that has kept to itself behind the Mare Nostrum for two hundred years, ruled by a Senate and defended by its legions. Its banner is a
green sun on white, its soldiers wear the red-plumed galea and its engineers build the roads that the rest of the world later calls obvious. Nobody in Wars World has seen the flag. The Aureans
say of themselves that they march *because the bread stopped*.

**A campaign of conquest.** The legion is not defending anything: it is invading. Landings, marches into the Accord's lands, sieges, cities and HQs taken, border forts and provinces falling one by one, the frontier
pushed outward from Green Earth's south coast to the Accord's heart. Missions favour capture and rout over holdouts; only Testudo (M2) and the Treasure Train escort (M11) are defensive by design. Underneath the conquest runs
the inquiry: Klaus conquers because the trail of the HOBB grain leads through the Accord's archives, and he will not be told "no" by a closed gate.

**Why they march.** Three summers running the Aurean harvest came up grey: ash on the wind from somewhere to the north, and the granaries emptied. Relief grain arrived at once, cheap and on time, from a freight
house called **HOBB Grain & Freight**: no office, no owner, a stencil on every crate and a creditor's stamp on every bill. The Senate is now in debt to a name. Quaestor **Livia** found the pattern in the
ledgers (the line has no harbour of its own and no registered captain); Consul **Varro** read it as an opportunity (hungry people will follow a war); Legate **Klaus** read it as a crime scene.
So the Senate split its orders: *"find who feeds us, and if there is nobody, take the north's granaries."* Klaus got the first half in writing and the legions; his rival **Cassius**, the Senate's
favourite, got the second half in a sealed letter and the cavalry.

**How it ties to the world.** The campaign runs in the year the Cinder Coast fence fell: the Allied Accord (Orange Star, Blue Moon, Green Earth, Yellow Comet) is stretched thin and jumpy, and a green fleet nobody
expected lands on Green Earth's southern coast. Everyone assumes it is Black Hole's next trick. The four nations are the people Klaus must be *understood* by, one mission at a time; Black Hole shows only
as the freight-handlers on the trail of HOBB, an enemy army in M9 and M13 (no BH Campaign event referred to or spoiled). Two threads are planted for BH2 and left unsolved: the **HOBB stencil** (the same
mark as the humming crate and Gerald's maker's mark in the BH Campaign; Livia recognises the symbol from a bill, never says from where) and the **black light on the northern horizon** the night the
campaign ends (the Obelisk's; nobody in this story knows what it is).

**Antagonists.**
- **Consul Gaius Varro**, the Senate's war-hawk and Klaus's old patron. He is no villain at first: he found money for the legions when nobody else would, and he does not ask where it came from. His
  fleet crosses the sea to arrest Klaus and finish the conquest his own way (grain first, answers never). **His arc ends in M14**, where the legion storms his camp, Cassius turns, and Varro falls, exposed as the
  man who took HOBB's money without asking. He has no later mission.
- **HOBB**, an account, never a face. Mortar-and-ledger menace: it is always paid in advance.
- **Cassius** is the antagonist of M4 only, then a rival who becomes an ally in his own time (M8 reluctantly, M14 by choice).

**The Allies.** Each nation misreads the Aureans in its own way and is answered in its own terms: Green Earth (coast wardens: Jess, Eagle, Drake, Javier) fights them as invaders and ends as the first
to hear Klaus out; Yellow Comet (Grimm, Sensei, Kanbei, Sonja) meets them at a border pass where Kanbei and Klaus recognise each other's honour; Blue Moon (Colin, Sasha, Olaf, Grit) thinks Aurean coin is
counterfeit and is out-banked by Livia; Orange Star (Max, Jake, Sami, Nell) meets them last, at a border fort, and Nell, who chairs the Accord, offers them the Accord's table.

**Arc in four acts.**
- **Act I, The Landing (M1-M4).** The legion lands, holds the beach, takes its first wall, and meets its own rival in the fog.
- **Act II, The Road North (M5-M8).** Cavalry, coin, sea and the first Tag Power. Every nation sees the legion once; none of them yet believes the grain story.
- **Act III, The Trail (M9-M12).** Air and ledger: the trail of HOBB leads through an air depot, a mountain pass, a convoy and a bastion. Klaus wins two friends (Kanbei, Nell) and Cassius begins to doubt his letter.
- **Act IV, Pax (M13-M16).** The Free Port where everyone fights everyone; the storming of Varro's camp (his fall); the Strait of Elms, where the Accord's fleet bars the way; and the last stand at the Allied
  stronghold of Stormhold, where Green Earth's Eagle and Orange Star's Hachi hold the gate against the legions. Epilogue: a black light in the north.

**Voice** (BH Campaign rules: real back-and-forth, 10 to 25 boxes a scene, no one-liners): Klaus is stern, fair and dry (never contractions in his orders; one joke a mission, and it is Livia's);
Aurelia thinks in loads, angles and what the wall will do; Cassius is loud, quick and funny and hates being right about anything unwelcome; Livia is polite, exact and a little frightening about money.
Sample (M1, the first eleven boxes, to approve the tone):

```
NARRATION: Cape Astra, Green Earth. / Forty days out of Aurelium.
LIVIA: The sea is flat, Legate. / That is the only good news.
KLAUS: Then take it. We will have / little enough of the other kind.
AURELIA: Beach shelves at two fathoms. / Barges ground at forty paces.
KLAUS: Then forty paces it is. / Cassius is not here to complain?
CASSIUS: Not yet! My horses are still / being sick in the third hold.
LIVIA: He is on the radio. / Pretend not to hear him.
CASSIUS(h): I heard that. Klaus, one day / you will say "well done, Cassius."
KLAUS: When I do, I will mean / it. Aurelia, signal the ramps.
AURELIA: Ramps down. May the sun / be kind to the first man ashore.
KLAUS: The sun is not who I worry / about. That is a wall. Move.
```

## 2. The four COs

Data: `tango-gamesupport-aw2/cos/<id>.toml` (format: `docs/dev/co-kit.md`), Tag Powers: `cos/tags.toml`. Portrait options: A to F each, **sheets** `co_klaus.png`, `co_aurelia.png`, `co_cassius.png`,
`co_livia.png` (large portrait, three faces, small face, HUD face, one line each). The chosen letters are decided by the user; until then `[portrait] chosen` is unset.
Klaus was **Marcus** in the first proposal; he is Klaus everywhere now and a much stronger commander.

### 2.1 What they do (proposal)

| CO | Role | Day to day | CO Power | Super CO Power | Stars (CO / Super in all) |
|---|---|---|---|---|---|
| **Klaus** | the Legate, chief commander | **Imperium:** all units +10% attack and defence; Infantry and Mech +10% more of both (+20% total) | **Testudo:** all units +20% defence (on top); Infantry and Mech +1 move; enemy counterattacks against his attacks do 25% less | **Legio Aeterna:** all units heal 3 HP, +1 move, +20% attack; Infantry and Mech +40% attack and defence on top | **4 / 8** |
| **Aurelia** | siege engineer | **Ballistics:** Artillery and Rockets +1 range; indirect units +10% attack; tanks and other vehicles -10% attack | **Ballista:** indirect units +1 range more and +30% attack | **Onager:** indirect units +1 range and +30% attack; each indirect hit also costs enemy units next to the target 1 HP (never below 1 HP) | **3 / 7** |
| **Cassius** | cavalry commander, a reckless rival | **Impetus:** vehicles +1 move and +10% attack, -10% defence | **Charge:** vehicles +1 move more and +30% attack | **Triumph:** vehicles +1 move more and +40% attack, and a vehicle that has attacked may move once more | **3 / 7** |
| **Livia** | senator and treasurer | **Ledger:** properties yield +25% funds; units cost +10% | **Tribute:** collects 200 funds for each property she owns | **Mare Nostrum:** naval units +2 move and +30% attack; collects 100 funds per property | **3 / 6** |

Changes from the first proposal (all are suggestions, reasons in 2.2): Klaus much stronger (the user's brief); Aurelia gets Grit's own pattern (a firepower bonus on indirect and a penalty on vehicles) and
a bigger COP; Cassius gets +10% attack at day to day and +30% / +40% in his powers (the first proposal's +20% was weaker than Jess's, AW2's vehicle CO); Livia's income is +25% instead of +10% (see below).
"Vehicles" means ground vehicles (Recon, APC, Tank, Md. Tank, Neotank, Anti-Air) and not artillery or the indirect group; "foot" is Infantry and Mech; "indirect" is Artillery, Rockets, Missiles and the
Battleship; "naval" is every ship.

### 2.2 Balance sanity note (against AW2's own COs)

`aw2dev co balance klaus aurelia cassius livia` prints the table; the Dual Strike COs' numbers are read from the .nds (the game itself uses them with the pack). Method: each power level averaged over a typical
army (foot 30%, direct vehicles 27%, indirect 12%, planes 9%, copters 5%, ships 17%), the power's +10% firepower included. AW2's stars (CO Power / Super Power in all): Andy 3/6, Max 3/6, Sami 3/8, Grit 3/6, Kanbei 4/7,
Eagle 3/9, **Hawke 5/9**, Drake 4/7, Colin 2/6, Jess 3/6, Sturm 0/10 (a Super Power only).

| CO | stars | day to day (fp / def) | CO Power (fp / def, move) | Super Power (fp / def, move) |
|---|---|---|---|---|
| Kanbei | 4/7 | +20 / +20 (units 20% dearer) | +60 / +20 | +60 / +50 |
| Hawke | 5/9 | +10 / 0 | +20 / 0 (heals) | +20 / 0 (heals) |
| Jess | 3/6 | +5 / 0 | +23 / 0, +0.4 | +30 / 0, +0.8 |
| Grit | 3/6 | -6 / 0, range +0.1 | +8 / 0, range +0.2 | +8 / 0, range +0.4 |
| Colin | 2/6 | -10 / 0 (units 20% cheaper) | 0 | 0 |
| **Klaus** | **4/8** | +13 / +13 | +23 / +33, +0.3 | +55 / +25, +1.0 (heals 3) |
| **Aurelia** | **3/7** | -1.5 / 0, range +0.1 | +12 / 0, range +0.2 | +12 / 0, range +0.2 (splash) |
| **Cassius** | **3/7** | +3 / -3, +0.3 | +21 / -3, +0.5 | +24 / -3, +0.5 (move after attack) |
| **Livia** | **3/6** | 0 / 0 (+25% income, +10% cost) | +10 (funds) | +15, +0.3 (funds) |

- **Klaus** is the strongest day-to-day CO on the list after Kanbei (+13/+13 over the whole army, +20/+20 on foot, with no drawback: Kanbei pays 20% dearer units). He sits above Hawke's +10/0, which fits
  "Hawke and Sturm-lite" (Sturm's Super Power is 10 stars; Klaus's is 8). His Super Power is about Max's ceiling in firepower on foot (+90% on foot units against Max's +90% on direct vehicles) with +1 move and a 3 HP
  heal on top, so 8 stars is the honest price and 7 would be Kanbei's; **the first thing to cut if playtests find him too strong is the heal (3 to 2), then the foot bonus (+40 to +30), then the cost (8 to 9)**.
  His Power is a defensive one (average defence +33): 4 stars, Kanbei's price, though it is much milder than Kanbei's +60 attack.
- **Aurelia** is Grit's cousin and stays just under him in raw power on purpose: the same +1 range and a firepower bonus on indirect units, a penalty on vehicles (Grit's -20% is on direct non-foot units; hers is
  -10% on vehicles only, so her Infantry and Mech are not penalised), and a Super Power that trades Grit's third range point (+3) for +2 range and splash. 7 stars is Olaf's / Kanbei's price; Grit is 6 for less
  splash. Risk: indirect-heavy armies are brutal vs. AI: a siege mission must give the AI answers (fast units, bombers).
- **Cassius** is Jess's rival in design: her vehicles are +20/+40/+60% with +1/+2 move at 3/6 stars and no drawback; his are lower in attack but have the move at day to day, the -10% defence drawback and a
  Super Power that no AW2 CO has (attack, then move on) at 7. If `move again after attacking` proves too strong the fallback is 8 stars or +1 move less.
- **Livia** is Colin's cousin. **Arithmetic the first proposal got wrong:** +10% income and +10% unit cost buys exactly as many units as before (1.10 / 1.10); at +25% / +10% she buys 14% more (Colin's -20% cost
  buys 25% more but costs him 10% firepower). Her powers are funds, not stats: Tribute at 3 stars is 200 funds a property (about 3,000 funds on an average map, about two Tanks);
  Mare Nostrum is deliberately a sea specialist's Super Power and is why it is 6 stars, and not 7, and why it still pays funds on a land map. The campaign's economy mission is her showcase.
- Check that stays green: no CO above Kanbei's day-to-day total and Super Power total (`aw2dev co check` fails above 40 and 120 points of firepower plus defence).

### 2.3 Tag Powers (Dual Strike's tag table)

A pair's Tag Power fires both Super Powers; its **compatibility** is the firepower bonus in percent while it lasts (Dual Strike: a byte of 65 to 130 per pair; every other pair is 95), its **stars** the pair's rating (as in
Sturm's own table, `sturm_pairs.rs`: 110 is 1 star, 115 to 120 is 2, 125 is 3). Data: `cos/tags.toml`; the check fails if a pair of the four is missing or a rating does not match its compatibility.

| Pair | Tag Power | Compat | Stars | Why (ratings follow the story) |
|---|---|---|---|---|
| Klaus + Livia | **Pax Romana** | 125% | 3 | old friends, the sword and the purse: the army's two pillars |
| Klaus + Aurelia | **Siege of Iron** | 120% | 2 | teacher and engineer: his line holds, her engines walk the wall down |
| Aurelia + Livia | **Aqueduct** | 118% | 2 | engineering paid in full and on time |
| Aurelia + Cassius | **Triumphal Road** | 115% | 2 | her roads and bridges under his wheels |
| Cassius + Livia | **Gilded Chariot** | 110% | 1 | she funds his recklessness and audits every denarius of it |
| Klaus + Cassius | **Hammer and Anvil** | 108% | 1 | rivals: the textbook tactic, performed with ill grace (the pair that learns to trust each other: a hidden bond can raise it to 118% / 2 stars, a late-campaign reward) |
| Klaus + Kanbei | **Two Banners** | 120% | 2 | cross-army: two old commanders who read each other's honour at once (unlocked after M10) |
| Livia + Colin | **Merchant Princes** | 116% | 2 | cross-army: two treasurers comparing ledgers (unlocked after M6) |

Each pair also needs its four victory lines and two Tag-in lines like Sturm's pairs have (phase 2, written in the BH voice). Tag Power names: Roman-flavoured, 20 letters at most.

### 2.4 Portraits: the owner's pixel art, imported faithfully

The four portraits are **the project owner's art** ("portrait art provided by the project owner", `CREDITS.md`): `art-src/cos/<co>_v5.jpg` (784 x 1168 full-body pixel art on a near-black background), mapped one data
line a CO (`[portrait] source` in `cos/<id>.toml`; the best guess: Klaus the grey-haired man with the moustache and the navy coat, Aurelia the woman with the tiara and the white tunic, Cassius the young man in the
black uniform with gold pauldrons, Livia the woman in the white robe with the red sash; the two women may be swapped). They are imported **faithfully** (`aw2dev co portrait import --pixelart`, `docs/dev/co-kit.md`): the
native pixel grid is found, the picture is resampled on the cell centres, the figure is framed waist-up like AW2's COs and scaled 2x by whole cells (facing right: Cassius and Klaus are mirrored), the palette is
the picture's own 14 colours + the outline, and the mugs are the heads at 2x. The sheet is `co_portraits_v5.png` (source, the large art 1x and 2x beside Hawke, Kanbei and Sonja, the faces with expressions, the CO select
row and the game's own screens). **In the game** with `TANGOAW2_ES_VERSUS=1` (the four are ids 86..89 with this campaign's powers): the CO select card, the HUD face, the Power's dialogue box and its cut-in (the large
figure), and the CO page show them. The happy, sad and angry slots show the neutral face unedited (the edited faces were rejected); expression pictures from the owner (`art-src/cos/<id>_<expression>.*`) are used if they exist.

## 3. Who joins when

| After | Gained | Notes |
|---|---|---|
| start | **Klaus** (forced M1, M2) | the player starts as Klaus |
| M3 | **Aurelia** | introduced in M3 (forced); selectable from M4 |
| M4 | **Cassius** | the rival of M4 is beaten and joins; selectable from M5, forced M5 |
| M6 | **Livia** | she arrives in the middle of M6 (forced); selectable from M7; unlocks the Livia + Colin tag partner |
| M10 | **Kanbei** as a Tag partner (Two Banners) | only in missions where the player picks a partner (M13, M15, M16) |

Free pick means: the player picks any unlocked CO and the scene reads for that CO (`@IF` / `@OTHER` groups as in the BH Campaign). Forced picks only where the story needs the person: M1-M3 (the arrival),
M5, M6, M8, M12 and the final stretch's lead (Klaus in M14 to M16).

## 4. The sixteen missions

Maps are original (`five/es/*.txt`, to be written, all through `aw2dev maps lint`). "Beaches generous" = every landing gets a wide shoal and 2-3 spare tiles of sand around each ramp. Deployed units start with full
ammo and fuel. Day limits only where the clock is the mission.

| # | Title | Objective | Enemy (army: CO) | Player CO | Map concept | Day limit |
|---|---|---|---|---|---|---|
| 1 | **Landfall** | Land from the transports and capture the Cape Astra fort's HQ | Green Earth coast wardens: Jess (and Drake's two cruisers offshore, for the barges to dodge) | Klaus (forced) | 18x14 coast; surf, wide beach, a ridge fort with a sea-wall, one city; 3 Transports and a Lander at the south edge with Infantry, Mech, APCs, Recon; Anti-Air tank in the second wave | none |
| 2 | **Testudo** | Hold the Dune Road ridge until Aurelia's engineers finish the causeway | Green Earth: Eagle (air) and Jess (tanks); a relief army | Klaus (forced) | 16x12 dunes, three ridges, a causeway city to hold; all attackers come from the north and east; AA and Missiles are in the player's reinforcements | **8 days** (defeat if the ridge's HQ falls) |
| 3 | **The Wall** | Breach and take Javier's tower-fortress (the siege that teaches Aurelia) | Green Earth: Javier (Com Towers) and Drake's coast guns (Battleship) | Aurelia (forced) | 20x14 ring-wall of mountains and rocks with three gates, inner keep, Com Towers; the player starts with Artillery, Rockets, Recon and Infantry, and an Airport for the engineers' Bomber | none |
| 4 | **The Second Legion** | Rout Cassius's army (or capture its camp HQ) in the Mistvale | Cassius's Second Legion, in the red (Orange Star colour, because only one army wears the skin) | Klaus or Aurelia | 16x16 river valley under **fog**; marsh, woods and a ford; both camps have Recons; the dialogue stops the battle on day 5 for a scene and it goes on | none |
| 5 | **Dust and Wheels** | Capture the three Comet Road signal-posts before the bridges are blown | Yellow Comet border guard: Grimm and Sensei (Sensei's Copters and Paratroopers) | Cassius (forced) | 24x12 plains and roads, a river with three bridges, signal posts at the far end of each; all-vehicle start (Recon, Tanks, Md. Tanks, APCs, a few Mech); Anti-Air tank included for Sensei | **9 days** (the bridges blow on day 10) |
| 6 | **Tribute** | Own 14 properties at once at the end of any day by day 16 (capture, no holding out) | Blue Moon trade guild: Colin and Sasha (they out-produce you and call your coin counterfeit) | Livia (forced) | 18x18 market town: 16 properties around a central square, three factories, two airports, a river of docks; the player starts with half the properties and half the funds | **16 days** (the Senate's audit: not 14 properties by then is defeat) |
| 7 | **Mare Nostrum** | Sink the Warden flagship and capture the harbour of Isle Verdant | Green Earth fleet: Drake (ships) and Eagle (air from the island airport) | any (Livia recommended) | 22x16 sea with an island fortress and two small atolls; beaches generous; Lander + Cruiser + Battleship + Sub + Copters + Anti-Air Cruiser (Cruisers) answer Eagle's Fighters | none |
| 8 | **Hammer and Anvil** *(tag)* | Defeat the Orange Star border force at Ironhold | Orange Star: Max and Jake (as an enemy pair if the engine allows; else Max with Jake's units as a second army) | Klaus + Cassius (forced pair) | 20x14 stone fort on a plain, a canal and a causeway; the pair splits the line (Klaus holds the centre, Cassius flanks); the **first Tag Power is the tutorial**: a scene on day 3 teaches Tag and Change | none |
| 9 | **Grain Ships** *(air)* | Capture the Kite Hill air depot and destroy the three HOBB freight barges | Black Hole freight guard: Adder (Fighters, Bombers) and Flak | any | 20x16 plateau airfield and a harbour; the player has an Airport from the start with Fighters, Bombers, B-Copters, Anti-Air and Missiles on the ground; the enemy has Missiles and AA tanks; the answer to every air threat is on the map | **10 days** (the barges sail on day 11) |
| 10 | **The Quiet Pass** | Reach and hold the Comet Pass (summit HQ) | Yellow Comet: Kanbei and Sonja | any | 20x16 mountain pass under **fog**, three roads and a goat track, forests and rocks, Recons and Copters for sight; Kanbei's honour scene on day 4 pauses the battle; after the win Kanbei joins as a Tag partner | none |
| 11 | **The Treasure Train** | Escort Livia's APC convoy (4 APCs) from the harbour to the Senate's relay camp | Free-company marauders: Lash and Flak | any (Cassius recommended) | 26x12 long road crossing a forest, a river with one ford and a ruin; the convoy moves at fixed speed; Cassius's Recons and Tanks screen the road; Aurelia's Artillery can cover the ford | none (the convoy must arrive; it can not wait) |
| 12 | **Siege of Iron** *(tag)* | Take the Iron Bastion's HQ (the siege where Aurelia shines, with Klaus holding the line) | Blue Moon: Olaf and Grit (Grit's range, Olaf's snow) | Klaus + Aurelia (forced pair) | 22x16 snowfield around a fortress on a hill with three wall rings; Grit's Artillery and Rockets cover every approach, so the answers are Aurelia's +1 range and her Onager, Bombers and fast Recon to find the guns; **Tag Power teaches the siege** | none |
| 13 | **The Free Port** *(multi-army)* | Capture the Harbour Office (the HQ in the middle) and keep it for 3 days while four other armies fight everybody | Green Earth (Javier), Yellow Comet (Sonja), Blue Moon (Sasha), Black Hole freight guard (Kindle): five armies, no alliances | any (+ optional Tag partner) | 24x20 free port on a bay, five landing zones; HQs in each corner; the player starts at the south; everyone's AI fights everyone; the HOBB ledger is in the Harbour Office; **five-army map** | none |
| 14 | **Varro's Gambit** | Storm Castra Maxima: take the Consul's HQ (or rout his army); Cassius changes sides on day 4 | Varro and his Praetorians (Varro, Orange Star colours) | Klaus (forced) + free partner; Cassius fights as an ally (AI) from day 4 | big fortified seaside camp: a sea wall, a harbour, three lanes of attack (the coast road, the river valley, the ridge track), reserves arrive on days 5 and 8; **Varro falls here** | none |
| 15 | **Pax Romana** *(tag)* | Break the Accord's blockade of the Strait of Elms: sink the flagship and take the Strait Fort's harbour | The Accord's strait fleet: Drake (Green Earth, ships) and Sensei (Yellow Comet, air); Nell's call on day 6 offers the table but the fleet fights on | any pair (free pair, incl. Kanbei) | big straits with two islands and a fortified shore; naval and air; the player's pair uses the Tag Power on the AA / Cruiser screen | none |
| 16 | **Sol Invictus** | Break Stormhold: rout the Allied armies or take their HQs (final mission, the hardest by a clear margin) | **Eagle (Green Earth) and Hachi (Orange Star)**, allied and coordinated, each in his own nation's colours, real production and funds, strong units and their CO powers | Klaus (forced lead) + free partner | very big open battlefield in daylight (no fog): the Allied stronghold city on a plateau with three lanes of attack (the coast road, the river valley, the high pass), harbour and airfield, waves of reserves; **no Black Hole inventions** | none |

**Day limits** (only where the clock is the mission): M2 (hold 8 days), M5 (bridges on day 10), M6 (the 16-day audit), M9 (barges on day 11), M11 (the convoy). Nothing else has one.

**Naval and air.** M1 (landing), M7 (fleet), M15 (fleet and air), M9 (air), M13 (a harbour map with ships), M16 (harbour phase); fog M4, M10; siege M3, M12; cavalry M5 (and M11's escort screen); economy M6;
defensive testudo M2 (and M14's quay); tag M8, M12, M15 (and the partner picks of M13, M16); multi-army M13; final boss M16.

### 4.1 The world map: Dual Strike's Omega Land

The campaign's world map is **Dual Strike's overworld** (the DS Campaign's own, read from the player's .nds), not AW2's Wars World. The legion sails from **Aurea's home island** (the south-west island, off the
nodes), lands at Cape Astra and spreads over the map in story order; the finale is the plateau of **Stormhold** in the north. The nodes (map pixels on the 480 x 240 map, `es_campaign::region`):

| M | Node | | M | Node |
|---|---|---|---|---|
| 1 Landfall | (214, 176) south coast of the central island | | 9 Grain Ships | (340, 215) the eastern continent's south peninsula |
| 2 Testudo | (190, 163) the dune ridge | | 10 The Quiet Pass | (400, 100) Comet Pass, the northern mountains |
| 3 The Wall | (155, 135) inland west | | 11 The Treasure Train | (410, 135) the eastern road |
| 4 The Second Legion | (200, 108) the Mistvale | | 12 Siege of Iron | (445, 122) the snowfield bastion |
| 5 Dust and Wheels | (262, 112) the Comet border plains | | 13 The Free Port | (420, 178) the bay |
| 6 Tribute | (270, 155) the market coast | | 14 Varro's Gambit | (250, 22) Castra Maxima on the northern isle |
| 7 Mare Nostrum | (332, 137) Isle Verdant | | 15 Pax Romana | (181, 57) the straits' shore |
| 8 Hammer and Anvil | (385, 148) Ironhold | | 16 Sol Invictus | (150, 28) **Stormhold** (last-mission marker) |

The campaign is one chain (each mission opens the next); the outline has no choice of order, so the map has no branch. A won mission keeps a starred flag; a cleared one can be replayed. Dual Strike's map has no parts to
repaint in a nation's colour and no route lines, so the conquest shows as the string of starred flags spreading across the map. See `docs/dev/es-campaign.md` "The world map".


## 5. Scenes and how much is said

Per mission: a **pre** scene (the briefing and the stakes, 14 to 25 boxes), **mid-battle** scenes (3 to 8 boxes each), a **post** scene (14 to 25), and a **map** scene on the world map after the win (10 to 16).
Big beats (M1, M4, M10, M13, M14, M16, the epilogue): 30 to 50. A recruit's post scene is 25 to 40. The budget is the same 3,072 text ids as the BH Campaign (a second campaign has its own string region; phase 2 checks it).

| # | Pre | Mid | Post | Map | Beat |
|---|---|---|---|---|---|
| 1 | Cape Astra, the sample above; Klaus, Aurelia, Livia, Cassius on the radio | day 2: the wardens ask who they are, Jess answers in plain Green Earth | the fort is Klaus's; Jess's last words: "You came from the sea. So did the last invasion." | Cape Astra is ours; Klaus writes to the Senate | the arrival |
| 2 | the line is a dune; Klaus shows the testudo drill | day 4 (Eagle's wing): "Anti-air, form up!" | the causeway opens; Aurelia is promoted to chief engineer on the spot | Klaus meets his first Green Earth prisoner | holding the line |
| 3 | the wall; Aurelia's first scene as a CO | day 3: a gate breaks; Javier invokes "the oath of the towers" | Javier honourably yields; Klaus asks about the grey ash; he has seen it too | Aurelia and Livia compare notes on HOBB | the engineer |
| 4 | the fog; a rival legion's banner; Cassius's letter | day 5: the battle halts, a messenger from the Senate; both read | Cassius, beaten, shows his sealed letter to Klaus; they agree to a truce | the Legate and the cavalryman, the first quarrel | the rival |
| 5 | Cassius's own scene: the road and the clock | day 4: Sensei: "You ride like you were running away." | the bridges are saved; Cassius's first compliment from a stranger | Klaus reads the Senate's reply: Varro approves | the dash |
| 6 | Livia in her element; Colin and Sasha across a desk | day 6: a bank run on her bills (a scene on the funds) | Colin's offer; Livia's cool counter-offer; the Merchant Princes pair | Livia finds the HOBB stencil on a Blue Moon bill | the ledger |
| 7 | the strait; the fleet; the Green Earth flagship | day 5: Eagle's air wing, "Death from above!" | the harbour opens; Drake: "dude, you kept the lanes clean." | Nell's first radio call to Klaus | the sea |
| 8 | the first Tag: Klaus and Cassius, forced to share a plan | day 3: the Tag lesson, then the first Hammer and Anvil | Max respects the legion, Nell asks for terms | the Accord's invitation; Cassius is not impressed | Tag |
| 9 | the depot: Adder and Flak; Aurelia's "bombs have a trajectory too" | day 4: the barges turn their lights on | the HOBB cargo opens: not grain. Sealed jars of grey ash | Klaus and Livia stare at the stencil | the truth begins |
| 10 | Kanbei's pass; Sonja watching from a ridge | day 4: the duel of words; the battle pauses | Kanbei's honour; Sonja signs "S." under a note for Klaus | Two Banners; Sonja's black book | honour |
| 11 | the convoy; Livia in a truck | day 5: the ford; Cassius's choice (the shortcut or the road) | the camp; the convoy's chest: records of the grain contracts | Cassius reads his letter again | trust |
| 12 | the bastion; Olaf boasts, Grit drawls | day 5: Grit's guns; Aurelia's plan | the iron comes down; Olaf accepts defeat as a kindness | the Accord's council hears Klaus (Nell) | the siege |
| 13 | the Free Port; five flags; the Harbour Office | day 4: Kindle burns a dock; Sonja moves in | the ledger: the HOBB ledger, a hand that is not Varro's | the Allies decide: Emerald Sun is no invader | everyone at once |
| 14 | Varro's marines on the quay; Cassius's decision | day 4: Cassius changes sides on the radio | the breakout; Klaus's speech | the Senate's ships on the horizon | the betrayal |
| 15 | the straits; the Accord's fleet is on the radio | day 6: Nell's fleet arrives | the flagship burns; Varro's retreat to Port Aurelium | the last council before the citadel | Pax |
| 16 | Port Aurelium: Varro in the keep; the confrontation (40 boxes) | phase scenes: the harbour, the walls, the keep | Varro's last words; the Senate re-reads the letters; the sun sets | the epilogue: grain, peace, and a black light in the north (HOBB's stencil on the last crate) | the end |

## 6. Variety, threats and answers

| Threat | Where | The answer on the map |
|---|---|---|
| Air (Eagle's Fighters, Adder's Bombers, Sensei's Copters) | M2, M5, M7, M9, M13, M15 | Anti-Air tanks in M2 and M5; Missiles and an Anti-Air Cruiser in M7; Fighters and Missiles from the start in M9; the player's own AA in every later mission |
| Heavy indirect (Grit's Artillery and Rockets, Javier's towers) | M3, M12 | Aurelia's range; Recons and Bombers to find the guns; Aurelia's Onager |
| Naval gunnery (Battleships) | M3, M7, M16 | Bombers and Submarines; the Cruiser line; Aurelia's long-range indirect |
| Fog ambushes | M4, M10 | Recons and Copters in the start units; Anti-Air tank hidden in the woods |
| Economy pressure | M6 | the start funds and properties are set so a good opening (capture, Factory, Tribute on day 8) wins the race |
| Convoys that cannot wait | M11 | the Tanks and Recons to clear the road; Artillery at the ford |
| Final boss Super Power | M16 | the player can see Varro's meter in the HUD; the keep has a repair lane; the phase scenes warn |

Every mission's start list is checked by the BH Campaign's rule: the units deployed start with **full ammo and fuel**, and a naval mission's landing has generous beaches. Each map goes through `aw2dev maps lint`.
Forced picks only where the story needs them (M1-M3, M5, M6, M8, M12, M14-M16 lead).

## 7. Music plan (scene to track role)

Roles are those of `aw2dev campaign scenes` (`campaign_music.rs`): `opening enemy1 enemy2 ally1 ally2 entry pinch hagevolt red blue sturm doom final ending1 ending2`, `world_map`, or `co:<name>` (that CO's theme). A scene's last box
fades into the next song with op 0x41, the way the BH Campaign does. Each CO has a **theme of their own**, composed for the campaign and played by AW2's own sound engine (`docs/dev/music-kit.md`): Klaus a legion march, Aurelia an engine of plucks and brass, Cassius a cavalry gallop, Livia a waltz with a harp, Varro a slow dark imperial theme. They play on the CO's turn and as `co:klaus` ... `co:varro` in scenes.

| Scene | Track role |
|---|---|
| prologue (Aurea's grey harvest, the Senate's two letters) | `opening` |
| any Emerald Sun camp scene (Klaus and his officers) | `ally2` |
| the Senate and Varro's scenes | `enemy1` (cold), `enemy2` (when he gloats) |
| a new CO's introduction (Aurelia M3, Cassius M4, Livia M6) | `entry` |
| the Accord's council (M8 post, M12 map, M13 map, M15 map) | `ally1` |
| Green Earth, Yellow Comet, Blue Moon, Orange Star scenes | `ally1` (their own songs where AW2 has them: Green Earth 421, Yellow Comet 422, Blue Moon 423) |
| Kanbei's scene (M10) | `co:kanbei` |
| Sonja's cameos | `enemy2` |
| the HOBB ledger scenes (M6 map, M9 post, M13 post) | `hagevolt` (the ledger's old menace) |
| crises (M2 day 4, M14 day 4, M16 phase 3) | `pinch` |
| Black Hole freight guard (M9, M13) | `enemy1` |
| the world map after each win | `world_map` |
| Klaus + Cassius forced pair (M8 pre) | `ally1`, then Cassius's `co:cassius` |
| M16 pre and post, Varro's last words | `sturm` (his citadel), then `doom` |
| M16's battle | `final` over the CO theme; the keep phase |
| ending, epilogue | `ending1`; the black light on the horizon: `ending2` |

`aw2dev campaign scenes` and `aw2dev campaign trace --mission N` will list every scene with its song in phase 2; a story scene without a song fails the lint (`tools/bhtext/lint.py`, `every_story_scene_has_a_song`).

## 8. Rules carried over from the BH Campaign

- Dialogue has soul: real back-and-forth, **10 to 25 boxes** per scene, no one-liners (`tools/bhtext/BIBLE.md`'s voice rules; one voice file per speaker; a Roman voice guide goes with phase 2).
- Every enemy threat has an answer (section 6); deployed units start with full ammo and fuel; beaches are generous on naval maps.
- Map integrity passes `aw2dev maps lint` (the Emerald Sun maps go in a new source `es`, like `bh`).
- **Review pictures have "MISSION N - Title" burned in** (the `maps boot` photographs: the mission number and title in the picture's corner), like the BH review sheets.
- **No two-front missions** (the user's rule): every mission is a single battlefield. No split front, front swap or unit transfer between fronts (`two_front` is never used); M8's "split line" and M14's two phases (defend, then attack) are one map. Tag missions (CO pairs) are fine.
- **M16 (Sol Invictus) is the hardest mission by a clear margin** (the user's rule, as for every campaign): Varro's army is big with real production and funds (Neotanks or Megatanks, air and naval as the map allows, fortified positions), pressure comes from several attack lanes on one map and reinforcement waves, Varro's powers are boss-strong, and it stays winnable (an answer to every threat, no RNG-only wins). M14 and M15 ramp up towards it. The kit's mission check scores difficulty (`aw2dev campaign difficulty`: enemy/player value ratio, income ratio, CPU-vs-scripted win rate, days to win) and M16 must score highest.
- **Black Hole inventions only in the two Black Hole missions** (the user's rule): Emerald Sun fights Black Hole itself in exactly two missions, **M9 Grain Ships** (Adder and Flak) and **M13 The Free Port** (Kindle's army is Black Hole's, a real army with its own COs and properties). Only there may the map carry inventions (Black Cannons, Minicannons, Lasers, a Deathray, a Black Factory, Crystals, an Obelisk), used sensibly under the BH Campaign's map rules (at most one Deathray, at the top edge, and so on). Every other mission has none, M16 included: Varro is not Black Hole, and his toughness comes from army size, production, funds, unit quality, fortified terrain, reinforcement waves and his CO powers. The kit tags the two missions (`black_hole_enemy`), allows at most two in the campaign, and fails an invention tile on any other map (`aw2dev maps lint --source es`, rule ES01).
- **Why the green fleet meets Black Hole (kept clear of the BH Campaign's events, and of BH2):** HOBB's grain moves through freight yards that Black Hole's quartermasters run for whoever pays in advance. Black Hole is not at war with Aurea; it defends its cargo, its depots and its docks against what it reads as raiders, with its own officers and production. The Aureans learn only that the stencil on the crates is a customer's, and that Black Hole's yards are where the trail runs through; they learn nothing of who the customer is (the BH2 hook). M9 is Black Hole's air depot and barge basin (Minicannons and a Black Cannon on the plateau, an airfield), M13 its north dock of the Free Port (a Black Factory and Crystals as the guard's own works).
- Forced CO picks only where the story needs them; everything else is a free pick from the unlocked roster.
- One art rule: nothing from the games or from AWBW is committed; the portraits and army art are composed at run time or original.
- Variety is checked against the table in section 4 (every bullet of the brief appears at least once).

## 9. Building it (phase 2 plan, once this is approved)

1. The Emerald Sun is already a skin: `army_skin.rs` + `skins/emerald_sun.toml`. A mission needs its army on one of the five colours: **only one army wears it** (no Emerald Sun vs. Emerald Sun), so Cassius's Second
   Legion is red (Orange Star's colour). The campaign engine's `ArmyDef` needs an army-skin flag (a data field, not engine code, per `army-packs.md`).
2. The four COs go in as `co_new` ids after Crumb and the face-only ids, each with a `crumb.rs`-style module (powers, texts, quotes, `bonus`), its CO table row, its presentation row from the chosen portrait recipe
   (`crumb_art.rs` shows how a composed 128x160 figure becomes the CO page picture), Tag data in `sturm_pairs.rs`'s format, and a regression row in `tools/aw2test/tests/test_all_cos.py`.
3. Maps (`five/es/es01.txt` ...), `MissionDef`s (`es_act1.rs` ... ), dialogue (`es_text/*.txt`, `tools/bhtext/lint.py` generalised to a second text set), the world-map points (AW2's map as the BH Campaign uses it).
4. Tools: `aw2dev co ...` (done), `aw2dev campaign scenes --campaign es`, `aw2dev maps lint --source es`, `aw2dev maps boot --campaign es` with the "MISSION N - Title" caption, trace tests, and an `aw2-add-campaign` update.
5. The campaign's order of work: Act I (M1 to M4) with their maps, scenes and a boot checkpoint per mission; then the rest. Each act is approved before the next.

## 10. Open questions for the user

1. **Portraits:** is the picture-to-CO mapping right (Klaus / Aurelia / Cassius / Livia as in section 2.4)? Can the owner supply happy, sad and angry variants of each picture (the slots show the neutral face for now)?
2. **Klaus's stars:** 4 / 8 (the doc's recommendation) or 4 / 9 as in your proposal? (8 is Kanbei's price plus one; 9 is Hawke's.)
3. **Livia's income:** +25% (the doc's change; +10% with +10% unit cost buys nothing) or your +10% income?
4. **Varro:** the final boss needs a CO that is not one of the four. Options: (a) a fifth Emerald Sun CO, boss only, built with the same kit (portrait options like the others); (b) Varro as a story-only
   character fought with an existing CO's data (e.g. Javier's) wearing the Praetorian colours. The tables above write "Varro (boss)" and work with either.
5. **Black Hole** (M9, M13): decided (the user): a real enemy army with its own COs, properties and inventions in those two missions only; no other mission has inventions.
6. **Second skin colour for Cassius:** his Second Legion is red (Orange Star's colour). Fine, or would you rather have a second Emerald Sun variant (a crimson one) built as a second skin file?
7. **Tag missions:** three (M8, M12, M15); are the forced pairs right (Klaus + Cassius reluctantly, Klaus + Aurelia for the siege, a free pair at the end)?
8. **Names:** keep the full names (Klaus, Aurelia, Cassius, Livia) wherever they fit; the short forms ("Aurel", "Cass", `short` in the CO file) only on a plate that clips. `aw2dev co check` measures them in AW2's font against the widest plate (28 px, Von Bolt): Klaus 19, Livia 17, Aurelia 24, Cassius 27 all fit, so no plate needs the short form by that measure; the in-game check at 1x happens when the COs are built in.

## 11. As built (phase 2, `docs/dev/es-campaign.md`)

All sixteen missions are playable: maps (`five/es/spec/es01.py` .. `es16.py`), mission rules (`es_act1.rs` .. `es_act4.rs`), the prologue, 71 dialogue scenes and the epilogue, the five COs (`es_co.rs`), the eight Tag pairs,
the skin on the player's army, a record in Flash slot 11. Differences from the outline above, all by the user's later rules or by the engine:
- **No two-front engine**: M8's split line and M14's two phases are one map. **Black Hole inventions only in M9 and M13** (Black Hole is a real enemy army there); none in M16.
- **M13 has four armies** (the player, Javier, Sonja, Kindle's Black Hole): the fifth army slot is Black Hole's and the player's, so a five-army mission could not also have Black Hole as an enemy; Blue Moon (Sasha) is absent from the port.
- **M16 is the hardest** (Varro with 40,000 funds, 38 start units (an army stops at 50), two production armies, five reinforcement waves, a charged Super Power from day 6): `aw2dev campaign difficulty`.
- **Enemy pairs**: M2 Jess + Eagle, M5 Grimm + Sensei and M9 Adder + Flak are enemy tag pairs on one army; M6, M7, M8, M10, M11, M12 have two allied enemy armies; M15's Accord fleet is an allied army (Nell) with no units until day 6; Cassius's M14 army changes teams on day 4.
- **M11**: the four APCs are the player's own (the escort is a race with a day limit of 14, not a scripted march).
- **Powers built** (engine hooks in `es_co.rs`, docs/dev/es-campaign.md): Klaus's Testudo "counterattacks against his attacks do 25% less", Aurelia's Onager splash (1 HP to every enemy unit beside the target, never below 1 HP), Cassius's Triumph (a vehicle that attacked may move once more, not fire again; the computer's Cassius does not get it).
- Portraits: the four are the project owner's (branch `escampaign`, merged: `es_cos.rs`, `art/cos/`, `cos/*.toml`), always in the game; Varro keeps a Dual Strike face as a placeholder (he has one mission, M14).

## 12. Rework for the user's rules (conquest, room to fight, the new finale)
- **Colours fixed.** A mission in which the player picks a CO started with the game's own colours for that case (player Black Hole, the rest shuffled): Black Hole drew Orange Star red, and the skin landed on
  Black Hole's inventions. `es_campaign::sync_colours` now sets every army's colour to the mission's (test `es_colours_m1..16`, `campaign check`).
- **Conquest**, not holdouts: see section 1. M6 is capture only; M14 is an assault; M16 is the siege of the Allied stronghold. Varro's arc ends in M14.
- **Room to fight**: every map is rebuilt bigger with the design-quality lint (docs/dev/map-lint.md): density at most .17 units per walkable cell, frontage ratio at most 1.25, no straight rivers, no rectangle patches, no unit blocks.
- **Finale**: M16 is Eagle (Green Earth) and Hachi (Orange Star) as allied enemy armies in their own colours, the player on Blue Moon's colour with the Emerald Sun skin.

### Maps as rebuilt (sizes and what is where; the specs are `five/es/spec/esNN.py`, each with its design note; the principles: `docs/dev/map-design.md`)
| # | Size | The land and its lanes |
|---|---|---|
| 1 | 30x27 | Cape Astra: the fleet's sandbar (two ports), three beaches (west cove, Astra strand under the town, east cove at the river mouth), forward neutral bases in the beach towns, farm villages, the fort on the ridge |
| 2 | 28x19 | the Dune Road ridges: the north ridge (five gaps) and the legion's ridge (four), the farm track behind it, villages between, a neutral base in the middle, the Dune hills on the east flank |
| 3 | 32x24 | Muro Alto: a walled town with four gates and a keep with one, three towers, the town's houses, the Muro river bridged three times, the silo by the west road, Drake's battleship offshore |
| 4 | 32x22 (fog) | the Verna valley, point-symmetric: two camps, three bridges, forward neutral bases on each bank, 26 villages |
| 5 | 42x24 | the Sable (four bridges), three canyon roads to the posts, the Comet Pipe (two gates, a seam on the Crossways road), forward bases and the silo in the ruins |
| 6 | 40x32 | Aurelhaven: the square, four avenues, the Mill Water canal (seven bridges), the Guildhall and the Counting House quarters, 63 neutral houses; own 24 properties |
| 7 | 38x24 | Cape Fidelis, the Twin Sisters (neutral airports, the silo), Isle Verdant's harbour; villages on every island |
| 8 | 38x24 | Ironhold's crags ring (front and rear gates), the Brimwater canal (three crossings), Sasha's camp, forward neutral bases north and south |
| 9 | 34x22 | Kite Hill (the depot, minicannons), the Kite river (four bridges), the HOBB quay (factory and airfield on the lava bay), the walled freight yard (pipeline, seam), ruined hamlets |
| 10 | 34x26 (fog) | three pass roads and the goat track over the massif, the Quiet river (three bridges), alpine hamlets, a neutral base at the centre pass's foot, Sami's pocket |
| 11 | 40x22 | three roads east (north, the Marrow road, south) each with its bridge, the camp road, forward neutral bases at the south road and the ruin, airfields at the harbour |
| 12 | 42x30 (snow) | the Iron Bastion: the keep (four gates), the bastion town, the Iron Wall (a pipe ring, five gates, a seam), Andy's spur, forward neutral bases before the side gates |
| 13 | 38x33 | the Free Port: the Harbour Office's square, two rivers, four quarters with quay factories (no ports on lava), market houses, Kindle's dock and the Black Factory |
| 14 | 46x28 | Castra Maxima behind its moat river, three lanes and a farm road, valley villages and a neutral base, the legion's port on the open coast |
| 15 | 46x27 | the Strait of Elms: Elm Isle, Salt and Reed Isles (neutral ports), the Strait Fort's harbour; villages on both shores |
| 16 | 44x28 | Stormhold: the beachhead, the Salt Road, the Weir Valley (three bridges, the weir track), Needle Pass, Mount Sol below the west gate, neutral bases in the middle, the city on its plateau |

