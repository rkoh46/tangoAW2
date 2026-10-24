# Emerald Sun maps: authoring brief

You author the Emerald Sun Campaign's battle maps as small Python specs. One spec = one mission's map, its units and its named places. You do NOT write Rust, dialogue or mission logic: the lead wires
the mission to your map from the notes you leave in the spec. Read first: `docs/ES_CAMPAIGN.md` (sections 1, 4, 6, 8), `docs/dev/maps.md` sections 1 and 2 (legend, unit types), `docs/dev/map-lint.md`,
the docstring of `devkit/aw2/esmaplib/__init__.py` (the painting API), and the finished example `tango-gamesupport-aw2/five/es/spec/es01.py`. Look at two BH maps for scale and feel
(`tango-gamesupport-aw2/five/bh/bh03.txt` naval, `bh12.txt`, `bh16.txt`).

## Your loop
1. Write `tango-gamesupport-aw2/five/es/spec/esNN.py` (copy the header of es01.py: the `sys.path` line and `from aw2.esmaplib import *`; `def build(): m = Canvas("esNN", W, H); ...; return m`).
2. `cd /Users/danielc/tangoAW2-esmissions && ./aw2dev maps gen --no-build --map esNN` (writes `five/es/esNN.txt`; always `--no-build`, never run cargo or `maps gen` without `--no-build`).
3. `./aw2dev maps lint --source es --map esNN --warn`: it prints one line per problem and writes a picture `devkit/work/maps/lint/es/esNN.png` (look at it with the Read tool: terrain, properties,
   units as letters, problems marked). Iterate until the map is `clean` (0 errors) and every warning is either fixed or really intended.
4. Quick preview as text: `python3 -c "import sys;sys.path.insert(0,'devkit');from aw2.esmaplib import *;m=load_spec('tango-gamesupport-aw2/five/es/spec/esNN.py');print(m.preview())"`.
Only edit your own spec files (and generated txt). Do not commit. Do not touch Rust, other specs, docs, `es_map_data.rs`.

## Rules every map follows (the BH Campaign's, `docs/ES_CAMPAIGN.md` section 8)
- **Answer to every enemy threat.** If the enemy brings aircraft, the player has Anti-Air / Missiles / Fighters or can build them; heavy indirect fire has an answer (range, Recon to find it, Bombers); battleships have Bombers/subs;
  and so on. List the threat-to-answer pairs in the spec's `comment`.
- **Deployed units start with full ammo and fuel** (the default: never set `hp=` unless told).
- **Beaches are generous on naval maps**: a shoal strip (`,`, one cell wide: the game's maps never draw a second row of shoal) along a straight coast, 3 to 5 spare sand cells behind each landing, ports on both sides; every Lander must have a
  beach or port to load and unload at (lint RC04).
- **Forced routes come from rivers, pipes, mountains**, never from decorative walls; bridges end on ground (lint BR rules); a river runs from a mountain/edge to the sea (RV rules); no puddles (SE01).
- **No decorative filler**: every wood, mountain, road and river is there for a reason (cover, a route, a choke, a defensive ring). Roads connect properties. Do not scatter noise.
- **Distinct territories for multi-army maps**; big maps; each army's HQ with production around it.
- Exactly one HQ `1`..`N` per army (even in escort or defence missions). Properties `B C A P` belong to the army whose HQ is nearest (use `m.header(owners=[..])` / `split` to change that, see `five/bhmap.py` docstring);
  neutral properties are lowercase `b c a p`. A port needs sea beside it, an HQ/base/airport needs ground beside it (RC03).
- No Black Hole inventions (`S N W E L v n F D X O #` and `M` silos) EXCEPT in the two missions that fight Black Hole (M9 and M13; use `m.header(blackhole=True)`; at most one Deathray, at the top edge; use them sensibly).
- Sizes: width <= 64, height <= 40, width x height <= 1288. The outline's sizes are guides (+- 2 is fine; bigger for more room).
- Unit lines: `m.unit(army, kind, x, y, hold=?, name=?)`. Army 1 is the player. `hold=True` marks a defender that stays in place (garrison, gate holders); units without it advance on the player (the mission code
  gives their orders by kind). Ships and Landers on sea or shoal; aircraft on any ground (they start parked next to an airport or in the open); a unit needs a free neighbour.
- Colours in `m.header(colours=(...))`: 1 Orange Star (red), 2 Blue Moon, 3 Green Earth, 4 Yellow Comet, 5 Black Hole. The player (Emerald Sun, drawn on a colour the mission picks) is army 1 with colour 5 unless the
  enemy list below says otherwise. `teams=(..)` through `m.header(team=[1,2,2])`.
- Name every place the mission code needs with `m.note("key", x, y, "text")` (printed with the map and kept as a comment): HQs, ports, bridges, signal posts, the convoy's start and end, reinforcement cells
  (free ground / shoal / sea cells, one cell per reinforcing unit), trigger rectangles' corners, ridge lines, anything a scene or a rule names. Reinforcement cells must be free of units and legal for the unit.
- Balance guide (the lead tunes with a simulator later, so give the numbers honestly): the player's start force and the enemy's are in the brief; the enemy's value is about 1.0 to 1.5 times the player's early on, the player has
  terrain, a better CO and production to win with. List both start forces in the spec's `comment`.
- Unit kinds: INF MECH MDT (Md Tank) MEGA (Megatank) TANK RECON APC NEO (Neotank) ART ROCK AA MIS (Missiles) FTR BMB BCO (B Copter) TCO (T Copter) BS (Battleship) CR (Cruiser) LAN (Lander) SUB CARR (Carrier) STEALTH.
- A map that the picture shows as plain, empty or implausible is not finished: a good map has a story: where each army starts, what it must cross, where it can hold, where the player is tempted.

## When you finish
Reply with a short report per map: size, the army list and colours, both start forces (unit counts by kind), the named places (key, x, y), the forced routes, the threat/answer table, any lint warning you kept and why,
and anything the mission code must know (e.g. "reinforcements for army 2 arrive at the east edge cells ...", "the HQ at (x, y) is the objective", "the day-4 scene triggers when a unit enters the rectangle ...").
