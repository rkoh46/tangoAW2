# The gauntlet engine (`crate::custom_campaign`: `MissionDef::hidden`, `sleepers`, `cut_off`)

A gauntlet is one battle against several armies that come one after another: only the first line is on the battlefield; each later line comes when the
lines before it fall. BH2's M31 The Last Accord uses it (Nell, then Olaf, Kanbei and Eagle; then the stage switch to Aria's Citadel, docs/dev/stages.md).
It is data on a mission, so a game mode of its own can reuse it.

| Piece | What it does |
|---|---|
| `MissionDef::hidden: Vec<Hidden { army, hq, zone }>` | The hidden lines: off the battlefield while they sleep: their HQ cell is plain on the map (the map header's `hidden 2 3 4` lets the map have no HQ for them), no units, controller 0 (AW2 gives them no turn), funds 0 |
| `MissionDef::sleepers: Vec<(army, Vec<hq>)>` | When each line wakes: the HQs that must have fallen first. A sleeping army is never defeated (`DefeatArmy` skipped) and is counted alive by AW2's end-of-battle check (`sub_08028BAC`, trap at `0x08028C0A`), so destroying the line on the field does not end the battle |
| `Cond::LineFallen { x, y }` | A line has fallen: the player holds its HQ, or its army was destroyed (the HQ turned a neutral property). A plain cell (a hidden HQ not built yet) has not |
| `Action::Reveal(army)` | The line comes: its HQ is built on its cell (under a unit standing there, if any), every property of its zone becomes its own (towers included, and the player's: a base raided before it came is taken back; HQs stay whose they are), its record gets its HQ cell, property counts and income, AW2's `RecountArmyProperties` (`0x080219AC`) runs, the screen is redrawn (`wasteland::render_map`), and it plays (the computer). Put `Spawn` (its wave) and its funds in the same trigger |
| `MissionDef::cut_off: Vec<(army, hq)>` | A fallen line keeps fighting with what is on the field but earns nothing (`cut_funds`, at each army's turn start after its income) |
| Its wave (`Action::Spawn`) | A unit whose landing cell is taken lands on the nearest free cell it can enter within 4 (`landing`; every mission's spawns) |
| A rout | When a line's last unit dies, `DefeatArmy` turns its HQ neutral and the next line's controller is set at once (`wake_after_rout`); the wake trigger then runs after the next action |

M31's wiring (`bh2_campaign::bh2_31`): `wake(hq, before, army, chest, wave, scene)` = `AfterAction` on all of `fell(..)`: the scene, `Reveal`, the war chest
(25,000 and the savings, `war_chest`), the wave. Tests: `bh2_m31_hidden_lines_are_off_the_battlefield` (absent, the turn goes Nell -> player, the reveal),
`bh2_m31_nell_routed_before_her_hq_falls` (a rout), `bh2_m31_gauntlet_suspend_and_resume` (byte for byte after each reveal), `bh2_m31_progression`,
`bh2_m31_sleeping_nations_earn_nothing`. Pictures of every wave: `aw2dev campaign playthrough bh2 31 --player bot --god --waves --advance 6` (docs/dev/playthrough.md).
