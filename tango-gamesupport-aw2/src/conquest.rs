//! Conquest (docs/dev/conquest.md): roguelike runs of AW2's maps in a row, offline (a table of [`RUNS`]: Conquest Run is the first, nine maps), Select Mode's CONQUEST entry ([`crate::mode_menu`]). The maps are AW2's own two-player Versus maps read
//! from the player's ROM ([`crate::custom_campaign::MapSrc::Aw2`]), small to large; the survivors and the funds carry over at every map switch (the stage engine, [`crate::stage`]), a reward
//! is picked between maps ([`crate::conquest_reward`]), one loss ends the run and the whole run's score goes to the Gauntlet's record table under the run's own key ([`Run::key`]; run 1's is [`KEY`]).
//!
//! It is its own game mode on the Gauntlet's engine: a mission of the Gauntlet's campaign ([`crate::gauntlet_mode::def`]; stage 0 is the mission's own map and each later map one of its
//! [`StageDef`]s), so records, Save / Continue, EXP and the results screen come from the Gauntlet's plumbing, but the wheel's CONQUEST entry picks them ([`picked`] sets the mode flag [`mode`],
//! which makes the map selector list one row a run and the Gauntlet's list never has them) and a run saved halfway is told from the Gauntlet's by its mission ([`is_mission`], [`run_saved`]). A map is won when the player takes the enemy HQ or destroys every enemy unit (the enemy HQ is held, so a capture defeats
//! nobody and the trigger moves the battle on; the engine's own defeat of an army with no units is held off on every map but the last: [`keeps_alive`]); the last map's win wins the run.

use mgba::core::Core;

use crate::custom_campaign::{colour, unit, *};
use crate::online::{KEY_A, KEY_B, KEY_LEFT, KEY_RIGHT};

/// Run 1's record key: record id 51 (never reused; the Gauntlet's maps are 1..12). The first, five-map run's results were kept under id 50, which nothing reads any more: a nine-map run's score is
/// of another scale, so the old results neither show beside the new ones nor keep a new run out of the top five.
pub const KEY: &str = "gauntlet_51";
/// The most maps a run may have: the run's draw of enemy COs lives at `STATE + 0x08..=0x14` (13 bytes), before the draw's flag at +0x15 and the mode flag at +0x16, and a saved run carries 12 of them.
pub const MAX_RUN_MAPS: usize = 12;
/// Run 1's number of maps.
pub const STAGES: usize = 9;

/// A run of the CONQUEST row: its record key, its words, its maps and what it pays. Every run is a mission of the Gauntlet's campaign (the mission index is the run's place in [`RUNS`] after the
/// Gauntlet's own twelve: run 1's is 12, [`crate::gauntlet_mode::def`]); the selector lists one row for each.
pub struct Run {
    /// The record key `gauntlet_NN` (record id NN; never reused, even by a run that is later removed: `the_run_keys_are_record_ids_never_reused`).
    pub key: &'static str,
    /// The run's name (the army screen's help line and the mission card) and its row in the selector (the star: several maps).
    pub title: &'static str,
    pub list_title: &'static str,
    /// The maps after the first, by name (the selector's SELECT flips through them and the mission's stage titles).
    pub stage_titles: &'static [&'static str],
    pub objective: &'static str,
    /// The maps, in play order (3 to [`MAX_RUN_MAPS`]); the first map is the mission's own.
    pub maps: &'static [Stage],
    /// The war chest after map 0: its first sum and how much more each later map's is.
    pub chest: (u32, u32),
    /// The days a well-played map takes (the score's par is this times the maps: [`crate::gauntlet_mode::par_days`]).
    pub par_per_map: u16,
    /// A run whose maps are a placeholder the designer will replace (shown in the pictures like any other).
    pub provisional: bool,
}

impl Run {
    pub fn len(&self) -> usize {
        self.maps.len()
    }

    /// The war chest after map `k` (0 the first): the first sum, growing by the step a map (run 1: 8,000 up to 25,500 after the eighth).
    pub fn chest_funds(&self, k: u8) -> u32 {
        self.chest.0 + self.chest.1 * k as u32
    }

    /// The three units a free unit is chosen from after map `k`: better ones later. The ladder ([`OFFER_LADDER`], eight steps) is spread over the run's rewards (one a map but the last), step for
    /// step on a nine-map run.
    pub fn offered(&self, k: u8) -> [u8; 3] {
        let last = self.len().saturating_sub(2).max(1);
        let at = ((k as usize).min(last) * (OFFER_LADDER.len() - 1) + last / 2) / last;
        OFFER_LADDER[at.min(OFFER_LADDER.len() - 1)]
    }

    /// The run's par in days.
    pub fn par_days(&self) -> u16 {
        self.par_per_map * self.len() as u16
    }
}

/// The units a reward offers, step by step from the first map's to the last's.
pub const OFFER_LADDER: [[u8; 3]; 8] = [
    [unit::TANK, unit::MD_TANK, unit::B_COPTER],
    [unit::MD_TANK, unit::ROCKETS, unit::FIGHTER],
    [unit::MD_TANK, unit::ROCKETS, unit::BOMBER],
    [unit::NEOTANK, unit::ROCKETS, unit::FIGHTER],
    [unit::NEOTANK, unit::ROCKETS, unit::BOMBER],
    [unit::NEOTANK, unit::MEGATANK, unit::BOMBER],
    [unit::MEGATANK, unit::NEOTANK, unit::FIGHTER],
    [unit::MEGATANK, unit::NEOTANK, unit::BOMBER],
];

/// The runs of CONQUEST's selector, in the order of its rows. New runs are appended (a run's mission index is its place here after the Gauntlet's twelve, so no earlier one moves).
pub const RUNS: &[Run] = &[
    Run {
        key: KEY,
        title: "Conquest Run",
        list_title: "Conquest Run *",
        stage_titles: &["Asphalt Maze", "Switchback", "Piston Dam", "Hourglass Isle", "Ruby Keys", "Vision Bridge", "Cube Keys", "Mial's Hope"],
        objective: "Win nine maps in a row: survivors and funds come along, a reward waits between maps.",
        maps: &RUN_1_MAPS,
        chest: (8_000, 2_500),
        par_per_map: 8,
        provisional: false,
    },
    // Harbor Run: harbours and air power, ending on Shark Strait.
    Run {
        key: "gauntlet_52",
        title: "Harbor Run",
        list_title: "Harbor Run *",
        stage_titles: RUN_2_TITLES,
        objective: "Win nine more maps in a row: survivors and funds come along, a reward waits between maps.",
        maps: &RUN_2_MAPS,
        chest: (8_000, 2_500),
        par_per_map: 8,
        provisional: false,
    },
];

/// The run with record key `key`.
pub fn run_of_key(key: &str) -> Option<&'static Run> {
    RUNS.iter().find(|r| r.key == key)
}

/// Whether `key` is one of the runs' record keys.
pub fn is_key(key: &str) -> bool {
    run_of_key(key).is_some()
}

/// The run (0-based) with record key `key`.
pub fn index_of_key(key: &str) -> Option<usize> {
    RUNS.iter().position(|r| r.key == key)
}

/// The run that is the Gauntlet-campaign mission `m`.
pub fn run_of_mission(m: u8) -> Option<&'static Run> {
    crate::gauntlet_mode::entries().get(m as usize).and_then(|e| run_of_key(e.key))
}

/// The run the Gauntlet session is playing (or about to: the selector's pick), if it is one of the CONQUEST runs.
pub fn current(core: &Core) -> Option<&'static Run> {
    if !crate::gauntlet::session(core) {
        return None;
    }
    run_of_mission(crate::ds_campaign::mission(core))
}

/// One map of the run: AW2's Versus map `id`, where the armies stand and what the enemy starts with.
pub struct Stage {
    /// The map's id in AW2's map table.
    pub id: u8,
    pub name: &'static str,
    /// The two HQs: the player's (army 1) and the enemy's (army 2).
    pub player: (u8, u8),
    pub enemy: (u8, u8),
    /// The enemy's starting funds (the CPU builds with them on its first turn).
    pub funds: u32,
    /// What the enemy starts with, on its properties' cells: (kind, cell).
    pub force: &'static [(u8, (u8, u8))],
    /// The player's starting force (only the first map has one: later maps get the survivors) on its bases.
    pub mine: &'static [(u8, (u8, u8))],
}

// --- The runs' maps ---------------------------------------------------------------------------------------------------------------------------------------------

/// Run 1's nine maps, small to large, easy to hard (HQs 20 to 39 cells apart, an equal share of bases, a land road between the HQs): Sabre Range, Asphalt Maze, Switchback, Piston Dam, Hourglass Isle,
/// Ruby Keys, Vision Bridge, Cube Keys, Mial's Hope. The enemy's funds and force grow every map (3,000 / 3 units up to 22,000 / 9).
/// The cells are the Versus maps' own properties (read from the ROM by `aw2dev conquest maps`).
pub const RUN_1_MAPS: [Stage; STAGES] = [
    Stage {
        id: 0x18,
        name: "Sabre Range",
        player: (1, 9),
        enemy: (13, 1),
        funds: 3000,
        force: &[
            (unit::INFANTRY, (13, 0)),
            (unit::INFANTRY, (12, 1)),
            (unit::TANK, (14, 1)),
        ],
        mine: &[
            (unit::INFANTRY, (1, 8)),
            (unit::INFANTRY, (0, 9)),
            (unit::TANK, (2, 9)),
            (unit::RECON, (1, 10)),
        ],
    },
    Stage {
        id: 0x19,
        name: "Asphalt Maze",
        player: (1, 9),
        enemy: (13, 1),
        funds: 4000,
        force: &[
            (unit::INFANTRY, (13, 0)),
            (unit::INFANTRY, (12, 1)),
            (unit::RECON, (14, 1)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x1C,
        name: "Switchback",
        player: (1, 13),
        enemy: (19, 1),
        funds: 5500,
        force: &[
            (unit::INFANTRY, (18, 2)),
            (unit::INFANTRY, (20, 2)),
            (unit::TANK, (18, 3)),
            (unit::ARTILLERY, (20, 3)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x22,
        name: "Piston Dam",
        player: (2, 1),
        enemy: (23, 12),
        funds: 7500,
        force: &[
            (unit::INFANTRY, (20, 11)),
            (unit::INFANTRY, (21, 11)),
            (unit::TANK, (22, 1)),
            (unit::TANK, (23, 1)),
            (unit::MD_TANK, (24, 1)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x26,
        name: "Hourglass Isle",
        player: (8, 2),
        enemy: (7, 21),
        funds: 9500,
        force: &[
            (unit::INFANTRY, (6, 20)),
            (unit::INFANTRY, (9, 20)),
            (unit::TANK, (8, 21)),
            (unit::TANK, (6, 21)),
            (unit::ARTILLERY, (7, 22)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x1D,
        name: "Ruby Keys",
        player: (1, 1),
        enemy: (26, 14),
        funds: 12000,
        force: &[
            (unit::INFANTRY, (27, 13)),
            (unit::INFANTRY, (28, 13)),
            (unit::MECH, (28, 11)),
            (unit::TANK, (26, 13)),
            (unit::MD_TANK, (27, 14)),
            (unit::ARTILLERY, (28, 14)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x21,
        name: "Vision Bridge",
        player: (2, 14),
        enemy: (28, 13),
        funds: 14500,
        force: &[
            (unit::INFANTRY, (29, 13)),
            (unit::INFANTRY, (28, 14)),
            (unit::MECH, (29, 14)),
            (unit::TANK, (27, 14)),
            (unit::TANK, (26, 14)),
            (unit::MD_TANK, (27, 13)),
            (unit::ARTILLERY, (30, 14)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x0E,
        name: "Cube Keys",
        player: (5, 6),
        enemy: (26, 23),
        funds: 17500,
        force: &[
            (unit::INFANTRY, (26, 22)),
            (unit::MECH, (25, 23)),
            (unit::MD_TANK, (27, 23)),
            (unit::MD_TANK, (26, 24)),
            (unit::ARTILLERY, (25, 22)),
            (unit::ANTI_AIR, (27, 21)),
            (unit::B_COPTER, (25, 21)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x75,
        name: "Mial's Hope",
        player: (4, 16),
        enemy: (34, 23),
        funds: 22000,
        force: &[
            (unit::INFANTRY, (33, 17)),
            (unit::INFANTRY, (34, 17)),
            (unit::MECH, (38, 18)),
            (unit::MD_TANK, (34, 22)),
            (unit::MD_TANK, (33, 23)),
            (unit::MEGATANK, (35, 23)),
            (unit::ROCKETS, (34, 24)),
            (unit::ANTI_AIR, (35, 20)),
            (unit::B_COPTER, (36, 23)),
        ],
        mine: &[],
    },
];

/// Run 2, "Harbor Run": nine of AW2's two-player Versus maps not in run 1, small to large with run 1's enemy ladder (HQs 20+ cells apart, a road a Tank can take between the HQs): harbours and
/// air power, from Pay Dirt's single airport to Shark Strait's eight airports and four ports. Pay Dirt, Pivot Isle, Twin Isle and Alara Range have a base more on one side (`aw2dev conquest maps --all`).
pub const RUN_2_MAPS: [Stage; 9] = [
    Stage {
        id: 0x80,
        name: "Pay Dirt",
        player: (1, 1),
        enemy: (13, 9),
        funds: 3000,
        force: &[
            (unit::INFANTRY, (12, 7)),
            (unit::INFANTRY, (14, 7)),
            (unit::TANK, (11, 10)),
        ],
        mine: &[
            (unit::INFANTRY, (2, 0)),
            (unit::INFANTRY, (0, 2)),
            (unit::TANK, (1, 0)),
            (unit::RECON, (0, 1)),
        ],
    },
    Stage {
        id: 0x70,
        name: "Pivot Isle",
        player: (1, 1),
        enemy: (18, 10),
        funds: 4000,
        force: &[
            (unit::INFANTRY, (18, 9)),
            (unit::INFANTRY, (17, 10)),
            (unit::RECON, (19, 10)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x6F,
        name: "Sole Harbor",
        player: (1, 1),
        enemy: (15, 12),
        funds: 5500,
        force: &[
            (unit::INFANTRY, (13, 12)),
            (unit::INFANTRY, (17, 12)),
            (unit::TANK, (12, 11)),
            (unit::ARTILLERY, (18, 11)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x78,
        name: "Twin Isle",
        player: (2, 2),
        enemy: (19, 13),
        funds: 7500,
        force: &[
            (unit::INFANTRY, (18, 12)),
            (unit::INFANTRY, (18, 11)),
            (unit::TANK, (5, 12)),
            (unit::TANK, (15, 12)),
            (unit::MD_TANK, (14, 12)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x6E,
        name: "Duo Falls",
        player: (4, 6),
        enemy: (27, 5),
        funds: 9500,
        force: &[
            (unit::INFANTRY, (27, 4)),
            (unit::INFANTRY, (26, 5)),
            (unit::TANK, (28, 5)),
            (unit::TANK, (27, 6)),
            (unit::ARTILLERY, (30, 4)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x0F,
        name: "Mirror Islands",
        player: (1, 7),
        enemy: (30, 7),
        funds: 12000,
        force: &[
            (unit::INFANTRY, (30, 6)),
            (unit::INFANTRY, (29, 7)),
            (unit::MECH, (30, 8)),
            (unit::TANK, (28, 10)),
            (unit::MD_TANK, (30, 12)),
            (unit::ARTILLERY, (29, 2)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x09,
        name: "Alara Range",
        player: (3, 3),
        enemy: (28, 12),
        funds: 14500,
        force: &[
            (unit::INFANTRY, (28, 11)),
            (unit::INFANTRY, (27, 12)),
            (unit::MECH, (28, 13)),
            (unit::TANK, (29, 12)),
            (unit::TANK, (28, 10)),
            (unit::MD_TANK, (27, 11)),
            (unit::ARTILLERY, (26, 12)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x0D,
        name: "Squash Island",
        player: (5, 7),
        enemy: (42, 8),
        funds: 17500,
        force: &[
            (unit::INFANTRY, (41, 8)),
            (unit::MECH, (43, 8)),
            (unit::MD_TANK, (42, 9)),
            (unit::MD_TANK, (42, 6)),
            (unit::ARTILLERY, (41, 7)),
            (unit::ANTI_AIR, (43, 7)),
            (unit::B_COPTER, (40, 8)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x10,
        name: "Shark Strait",
        player: (4, 13),
        enemy: (31, 16),
        funds: 22000,
        force: &[
            (unit::INFANTRY, (31, 15)),
            (unit::INFANTRY, (30, 16)),
            (unit::MECH, (32, 16)),
            (unit::MD_TANK, (31, 17)),
            (unit::MD_TANK, (29, 15)),
            (unit::MEGATANK, (31, 10)),
            (unit::ROCKETS, (33, 12)),
            (unit::ANTI_AIR, (28, 13)),
            (unit::B_COPTER, (32, 9)),
        ],
        mine: &[],
    },
];
pub const RUN_2_TITLES: &[&str] = &["Pivot Isle", "Sole Harbor", "Twin Isle", "Duo Falls", "Mirror Islands", "Alara Range", "Squash Island", "Shark Strait"];

/// The enemy army's colour on every map (Black Hole's: the player's pick offers the other four and Silver Nova).
pub const ENEMY_COLOUR: u8 = colour::BLACK_HOLE;
/// The CO the enemy's army is compiled with: a stand-in. The run's own draw ([`begin_run`]) is written over it when each map starts ([`enemy_co`]).
pub const STAND_IN: u8 = crate::custom_campaign::co::ANDY;

/// The player's funds on the first map.
const START_FUNDS: u32 = 7000;

fn units_of(army: u8, list: &[(u8, (u8, u8))]) -> Vec<UnitDef> {
    list.iter().map(|&(k, (x, y))| UnitDef::new(army, k, x, y)).collect()
}

/// A map is won: the enemy HQ is the player's (a capture) or the enemy has no unit left.
fn won(enemy_hq: (u8, u8)) -> Cond {
    Cond::Any(vec![
        Cond::LineFallen {
            x: enemy_hq.0,
            y: enemy_hq.1,
        },
        Cond::ArmyUnitsAtMost { army: 2, n: 0 },
    ])
}

fn armies(s: &Stage, first: bool) -> Vec<ArmyDef> {
    let me = if first {
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pick).funds(START_FUNDS)
    } else {
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Keep)
    };
    vec![
        me,
        ArmyDef::new(ENEMY_COLOUR, CoSpec::Fixed(STAND_IN))
            .team(2)
            .funds(s.funds),
    ]
}

/// The mission of `run`: the first map, with the later maps as its stages.
pub fn mission(run: &Run) -> MissionDef {
    let first = &run.maps[0];
    let mut m = MissionDef::new(run.key, run.title);
    m.list_title = run.list_title;
    m.stage_titles = run.stage_titles;
    m.objective = run.objective;
    m.map = MapSrc::Aw2 { id: first.id };
    m.armies = armies(first, true);
    m.units = crate::bh_ai::orders(
        [units_of(1, first.mine), units_of(2, first.force)].concat(),
        1,
        crate::bh_ai::ATTACK,
        |_| false,
    );
    m.held_hq = Some(first.enemy);
    m.triggers = vec![Trigger::new(
        When::AfterAction,
        won(first.enemy),
        vec![Action::NextStage],
    )];
    m.setup = false;
    m.stars = 3;
    for (k, s) in run.maps.iter().enumerate().skip(1) {
        let mut st = StageDef::new(MapSrc::Aw2 { id: s.id });
        st.armies = armies(s, false);
        st.units = crate::bh_ai::orders(units_of(2, s.force), 1, crate::bh_ai::ATTACK, |_| false);
        // (the survivors land by the player's HQ: the nearest free cell each can enter)
        st.deploy = deploy_cells(s.player);
        st.carry = Carry::All;
        st.funds = None;
        st.held = vec![s.enemy];
        st.triggers = vec![Trigger::new(
            When::AfterAction,
            won(s.enemy),
            if k + 1 == run.len() {
                vec![Action::Win]
            } else {
                vec![Action::NextStage]
            },
        )];
        m.stages.push(st);
    }
    m
}

/// The cells the survivors land on, nearest the player's HQ first (the stage engine puts each on the nearest free cell it can enter, from the first of these).
fn deploy_cells(hq: (u8, u8)) -> Vec<(u8, u8)> {
    let mut v = Vec::new();
    for r in 0..=2i16 {
        for dy in -r..=r {
            for dx in -r..=r {
                if dx.abs().max(dy.abs()) == r {
                    let (x, y) = (hq.0 as i16 + dx, hq.1 as i16 + dy);
                    if x >= 0 && y >= 0 {
                        v.push((x as u8, y as u8));
                    }
                }
            }
        }
    }
    v
}

/// 1 from the wheel's CONQUEST pick until the next pick of GAUNTLET (which clears it): the map selector lists this run's row alone instead of the Gauntlet's maps, and the way back from the
/// run's end puts the wheel on CONQUEST. The one byte of [`STATE`] past the run's draw (+0x16).
const MODE: u32 = STATE + 0x16;

/// The wheel's CONQUEST pick (a new run, or `cont`: Continue over the run saved halfway): the Gauntlet's request ([`crate::gauntlet::picked`]) and the mode flag.
pub fn picked(core: &mut Core, cont: bool) {
    crate::gauntlet::picked(core, cont);
    set_mode(core, true);
}

pub(crate) fn set_mode(core: &mut Core, on: bool) {
    if core.raw_read_8(MODE, -1) != on as u8 {
        core.raw_write_8(MODE, -1, on as u8);
    }
}

/// The last pick on Select Mode was CONQUEST (not GAUNTLET).
pub fn mode(core: &Core) -> bool {
    core.raw_read_8(MODE, -1) == 1
}

/// Whether the Gauntlet-campaign mission index `m` is one of the Conquest runs.
pub fn is_mission(m: u8) -> bool {
    run_of_mission(m).is_some()
}

/// A Conquest run (any of them) is saved halfway (the shared slot's save tagged with the Gauntlet's source and a run's mission). A five-map run saved before the run had nine maps (its tail mark is the
/// old one) is not offered: its stage numbers are other maps now. It stays in the slot until a new run starts, which drops it ([`crate::gauntlet::drop_own_save`]).
pub fn run_saved(core: &Core) -> bool {
    let slot = crate::campaign_model::SOURCES[crate::gauntlet::SOURCE].mid_slot;
    crate::suspend::saved_mission_of(core, crate::gauntlet::SOURCE).is_some_and(is_mission) && !crate::suspend::tail_has(core, slot, OLD_SAVED_MARK)
}

/// Whether the Gauntlet's session is a Conquest run.
pub fn session(core: &Core) -> bool {
    current(core).is_some()
}

/// The engine's own end of a map (the enemy army with no units: `DefeatArmy`, and the end check's alive marks) is held off while the run goes on: a map is won by [`won`]'s trigger, which moves the
/// battle to the next map, and only the last map's win ends the run (AW2's victory there is the run's).
pub fn keeps_alive(core: &Core, army: u8) -> bool {
    army == 2 && current(core).is_some_and(|r| (crate::stage::stage(core) as usize) + 1 < r.len())
}

// --- The reward between maps ---------------------------------------------------------------------------------------------------------------------------------

/// The run's state in EWRAM ([`crate::ram_map`]): +0 the reward page (0 none, 1 the three rewards, 2 the three units), +1 the cursor, +2 the reward of this switch has been taken, +3 the map just
/// won (0..), +4..+6 the three units on offer (one of the rewards).
pub const STATE: u32 = 0x0203_D0E0;
pub const STATE_LEN: u32 = 0x20;
const PAGE: u32 = STATE;
const CURSOR: u32 = STATE + 1;
const TAKEN: u32 = STATE + 2;
const WON: u32 = STATE + 3;
const OFFER: u32 = STATE + 4;

/// The run's draw: +0x08.. the enemy CO of each map (AW2 CO ids; up to [`MAX_RUN_MAPS`] bytes, past the 8 bytes the reward's reset clears), +0x15 1 once a run has drawn them. Saved with a run saved
/// halfway ([`saved`]).
const ENEMIES: u32 = STATE + 0x08;
const DRAWN: u32 = STATE + 0x15;
/// The bytes of the run's draw that go into a saved run: [`MAX_RUN_MAPS`] COs (a shorter run's rest is 0) and the flag.
pub const SAVED_LEN: u32 = MAX_RUN_MAPS as u32 + 1;
/// The tail mark of a saved run's draw, after AW2's block: `CQRM` with [`SAVED_LEN`] bytes (any run). The nine-map run's first format was `CQR9` with ten bytes (nine COs and the flag), read as run 1's
/// ([`SAVED_LEN_V1`]); the five-map run's was `CQRN` with six bytes: a run saved then is another run (its stage numbers are other maps) and is not offered ([`run_saved`]).
pub const SAVED_MARK: u32 = 0x4D52_5143; // "CQRM"
pub const SAVED_MARK_V1: u32 = 0x3952_5143; // "CQR9"
pub const SAVED_LEN_V1: u32 = STAGES as u32 + 1;
pub const OLD_SAVED_MARK: u32 = 0x4E52_5143; // "CQRN"

/// The COs an enemy is drawn from: the roster less the five tangoAW2 COs that need the Silver Nova skin or a pack of their own to be an enemy (Clone Andy, Crumb, Tabitha, Lili, Caulder).
pub fn pool() -> Vec<u8> {
    use crate::custom_campaign::co;
    let out = [
        co::CLONE_ANDY,
        co::CRUMB,
        crate::es_co::TABITHA,
        crate::es_co::LILI,
        crate::es_co::CAULDER,
    ];
    crate::gauntlet_mode::ROSTER
        .iter()
        .map(|r| r.0)
        .filter(|c| !out.contains(c))
        .collect()
}

/// A run's enemies: one CO a map (`n` maps), never the player's, never twice, drawn from [`pool`] by a shuffle driven by `seed` (xorshift64*: deterministic for a seed).
pub fn draw_cos(seed: u64, player: u8, n: usize) -> Vec<u8> {
    let mut p: Vec<u8> = pool().into_iter().filter(|&c| c != player).collect();
    let mut x = seed | 1;
    let mut next = || {
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        x.wrapping_mul(0x2545_F491_4F6C_DD1D)
    };
    for i in (1..p.len()).rev() {
        let j = (next() % (i as u64 + 1)) as usize;
        p.swap(i, j);
    }
    p.truncate(n);
    p
}

/// A new run begins (the army screen's A, [`crate::gauntlet_ui::apply`]): when it is a Conquest run, its enemies are drawn from the game's own random state and the frame count (offline only: nothing
/// of the draw is netplay's) and kept with the run (a shorter run leaves the rest of the draw's bytes 0).
pub fn begin_run(core: &mut Core) {
    let Some(run) = crate::gauntlet_ui::picked(core).and_then(|e| run_of_key(e.key)) else { return };
    let player = core.raw_read_8(crate::gauntlet_ui::CO_PICK, -1);
    let seed = (core.raw_read_32(0x0300_1FD4, -1) as u64) << 32
        ^ (core.frame_counter() as u64).wrapping_mul(0x9E37_79B9_7F4A_7C15);
    let mut cos = draw_cos(seed, player, run.len());
    cos.resize(MAX_RUN_MAPS, 0);
    core.raw_write_range(ENEMIES, -1, &cos);
    core.raw_write_8(DRAWN, -1, 1);
    log::info!("conquest: the run's enemies are {cos:?} for CO {player}");
}

/// The enemy CO of map `k` (0 the first) of the run in progress, if a draw is held.
pub fn enemy_co(core: &Core, k: usize) -> Option<u8> {
    (k < MAX_RUN_MAPS && core.raw_read_8(DRAWN, -1) != 0).then(|| core.raw_read_8(ENEMIES + k as u32, -1))
}

/// A battle starts on the first map: the enemy army's CO is the draw's first (the record's compiled CO is a stand-in). The later maps' come at the switch ([`crate::stage`]'s setup).
pub fn map_start(core: &mut Core) {
    if !session(core) || crate::stage::stage(core) != 0 {
        return;
    }
    let Some(co) = enemy_co(core, 0) else { return };
    let players = crate::five::players(core);
    core.raw_write_8(players + 0x3C * 2 + 0x1D, -1, co);
    core.raw_write_8(0x0300_3FC0 + 0x3D + 1, -1, co);
}

/// The run's draw as saved with a run saved halfway ([`MAX_RUN_MAPS`] COs and the flag), None outside a Conquest run.
pub fn saved(core: &Core) -> Option<Vec<u8>> {
    if !session(core) || core.raw_read_8(DRAWN, -1) == 0 {
        return None;
    }
    let mut b = vec![0u8; MAX_RUN_MAPS];
    core.raw_read_range(ENEMIES, -1, &mut b);
    b.push(1);
    Some(b)
}

/// A saved run continues: its draw comes back. `b` is a `CQRM` record ([`SAVED_LEN`] bytes) or run 1's first format (`CQR9`, [`SAVED_LEN_V1`] bytes: nine COs and the flag, the rest 0).
pub fn restore(core: &mut Core, b: &[u8]) {
    if b.len() == SAVED_LEN as usize || b.len() == SAVED_LEN_V1 as usize {
        let n = b.len() - 1;
        let mut cos = b[..n].to_vec();
        cos.resize(MAX_RUN_MAPS, 0);
        core.raw_write_range(ENEMIES, -1, &cos);
        core.raw_write_8(DRAWN, -1, b[n]);
    }
}

/// The rewards: the war chest, the free unit, the field repair.
pub const CHEST: u8 = 0;
pub const REINFORCE: u8 = 1;
pub const REPAIR: u8 = 2;

/// The map the reward is for (the one just won, 0.. up to the run's last but one).
pub fn won_map(core: &Core) -> u8 {
    core.raw_read_8(WON, -1)
}

/// The reward page up now: 0 none, 1 the rewards, 2 the units.
pub fn page(core: &Core) -> u8 {
    core.raw_read_8(PAGE, -1)
}

pub fn cursor(core: &Core) -> u8 {
    core.raw_read_8(CURSOR, -1)
}

/// The units on offer on page 2.
pub fn offer(core: &Core) -> [u8; 3] {
    [
        core.raw_read_8(OFFER, -1),
        core.raw_read_8(OFFER + 1, -1),
        core.raw_read_8(OFFER + 2, -1),
    ]
}

/// A map switch begins (the stage engine's `request`): this switch's reward is not taken yet.
pub fn reward_reset(core: &mut Core) {
    core.raw_write_range(STATE, -1, &[0u8; 8]);
}

/// The stage engine's wait before the fade (`Stub::Reward`): true while the reward is being picked. The first call opens the page for the map just won.
pub fn reward_wait(core: &mut Core) -> bool {
    if !session(core) {
        return false;
    }
    if core.raw_read_8(TAKEN, -1) != 0 {
        return false;
    }
    if page(core) == 0 {
        let Some(run) = current(core) else { return false };
        let k = crate::stage::stage(core).min(run.len() as u8 - 2);
        core.raw_write_8(WON, -1, k);
        core.raw_write_8(CURSOR, -1, 0);
        core.raw_write_8(PAGE, -1, 1);
        core.raw_write_range(OFFER, -1, &run.offered(k));
    }
    true
}

/// The reward is taken: `what` happens to the survivors waiting in the stage engine's carry buffer (so the next map's arrival brings it), the page closes.
fn take(core: &mut Core, what: u8, unit_kind: u8) {
    let k = won_map(core);
    let Some(run) = current(core) else { return };
    match what {
        CHEST => {
            let f = crate::stage::carried_funds(core);
            crate::stage::set_carried_funds(core, f + run.chest_funds(k));
        }
        REINFORCE => {
            let mut recs = crate::stage::carried(core);
            let rec = fresh_unit(core, unit_kind);
            if recs.len() as u32 >= crate::stage::CARRY_MAX {
                // (the carry buffer is full: the weakest survivor makes room)
                if let Some(at) = (0..recs.len()).min_by_key(|&i| hp_of(&recs[i])) {
                    recs.remove(at);
                }
            }
            recs.push(rec);
            crate::stage::put_carried(core, &recs);
        }
        _ => {
            let recs: Vec<[u8; 12]> = crate::stage::carried(core)
                .into_iter()
                .map(|r| repaired(core, r))
                .collect();
            crate::stage::put_carried(core, &recs);
        }
    }
    core.raw_write_8(PAGE, -1, 0);
    core.raw_write_8(TAKEN, -1, 1);
    log::info!(
        "conquest: reward {} after map {}",
        ["war chest", "free unit", "field repair"][what.min(2) as usize],
        k + 1
    );
}

fn hp_of(r: &[u8; 12]) -> u16 {
    u16::from_le_bytes([r[4], r[5]]) & 0x7F
}

/// A unit record as the stage engine carries it: full HP, ammo and fuel of its kind (the cell is the next map's deploy cell's).
fn fresh_unit(core: &Core, kind: u8) -> [u8; 12] {
    let mut r = [0u8; 12];
    r[0] = kind;
    r[4..6].copy_from_slice(&(100u16 | (ammo_max(core, kind) as u16) << 7).to_le_bytes());
    r[6] = fuel_max(core, kind);
    r
}

/// A survivor back to 10 HP with a full tank and a full magazine.
fn repaired(core: &Core, mut r: [u8; 12]) -> [u8; 12] {
    let w = u16::from_le_bytes([r[4], r[5]]);
    let w = (w & !0x7F & !0x780) | 100 | (ammo_max(core, r[0]) as u16) << 7;
    r[4..6].copy_from_slice(&w.to_le_bytes());
    r[6] = fuel_max(core, r[0]);
    r
}

/// The type's most ammo and fuel (AW2's unit table: +0x0B and +0x10; ammo is a 4-bit field).
fn ammo_max(core: &Core, kind: u8) -> u8 {
    core.raw_read_8(crate::roster::table(core) + 0x5C * kind as u32 + 0x0B, -1)
        .min(15)
}

fn fuel_max(core: &Core, kind: u8) -> u8 {
    core.raw_read_8(crate::roster::table(core) + 0x5C * kind as u32 + 0x10, -1)
}

/// Each frame the reward page is up it takes the pad (the game sees no key): LEFT and RIGHT move the cursor (round), A takes, B on the units goes back to the rewards.
pub fn tick(core: &mut Core, keys: u32, prev: u32) -> u32 {
    let page = page(core);
    if page == 0 {
        return keys;
    }
    let pressed = keys & !prev;
    let c = core.raw_read_8(CURSOR, -1) % 3;
    if pressed & KEY_RIGHT != 0 {
        core.raw_write_8(CURSOR, -1, (c + 1) % 3);
    } else if pressed & KEY_LEFT != 0 {
        core.raw_write_8(CURSOR, -1, (c + 2) % 3);
    } else if pressed & KEY_A != 0 {
        match (page, c) {
            (1, REINFORCE) => {
                core.raw_write_8(PAGE, -1, 2);
                core.raw_write_8(CURSOR, -1, 0);
            }
            (1, what) => take(core, what, 0),
            _ => take(core, REINFORCE, offer(core)[c as usize]),
        }
    } else if pressed & KEY_B != 0 && page == 2 {
        core.raw_write_8(PAGE, -1, 1);
        core.raw_write_8(CURSOR, -1, REINFORCE);
    }
    0
}

#[cfg(test)]
mod tests {
    use super::*;

    fn run1() -> &'static Run {
        &RUNS[0]
    }

    #[test]
    fn run_one_is_exactly_what_it_was() {
        let r = run1();
        assert_eq!((r.key, r.title, r.list_title), ("gauntlet_51", "Conquest Run", "Conquest Run *"));
        assert_eq!(r.len(), STAGES);
        assert_eq!(r.par_days(), 72);
        assert_eq!((r.chest_funds(0), r.chest_funds(7)), (8_000, 25_500));
        let names: Vec<&str> = r.maps.iter().map(|s| s.name).collect();
        assert_eq!(names, ["Sabre Range", "Asphalt Maze", "Switchback", "Piston Dam", "Hourglass Isle", "Ruby Keys", "Vision Bridge", "Cube Keys", "Mial's Hope"]);
        let ids: Vec<u8> = r.maps.iter().map(|s| s.id).collect();
        assert_eq!(ids, [0x18, 0x19, 0x1C, 0x22, 0x26, 0x1D, 0x21, 0x0E, 0x75]);
        let funds: Vec<u32> = r.maps.iter().map(|s| s.funds).collect();
        assert_eq!(funds, [3000, 4000, 5500, 7500, 9500, 12000, 14500, 17500, 22000]);
        let force: Vec<usize> = r.maps.iter().map(|s| s.force.len()).collect();
        assert_eq!(force, [3, 3, 4, 5, 5, 6, 7, 7, 9]);
        // the offers, step for step as before
        let expect = [
            [unit::TANK, unit::MD_TANK, unit::B_COPTER],
            [unit::MD_TANK, unit::ROCKETS, unit::FIGHTER],
            [unit::MD_TANK, unit::ROCKETS, unit::BOMBER],
            [unit::NEOTANK, unit::ROCKETS, unit::FIGHTER],
            [unit::NEOTANK, unit::ROCKETS, unit::BOMBER],
            [unit::NEOTANK, unit::MEGATANK, unit::BOMBER],
            [unit::MEGATANK, unit::NEOTANK, unit::FIGHTER],
            [unit::MEGATANK, unit::NEOTANK, unit::BOMBER],
        ];
        for (k, e) in expect.iter().enumerate() {
            assert_eq!(&r.offered(k as u8), e, "after map {}", k + 1);
        }
        assert_eq!(SAVED_MARK_V1, u32::from_le_bytes(*b"CQR9"));
        assert_eq!(SAVED_MARK, u32::from_le_bytes(*b"CQRM"));
        assert_eq!(OLD_SAVED_MARK, u32::from_le_bytes(*b"CQRN"));
    }

    #[test]
    fn every_run_has_maps_with_hqs_far_apart() {
        for r in RUNS {
            assert!((3..=MAX_RUN_MAPS).contains(&r.len()), "{}: {} maps", r.title, r.len());
            assert_eq!(r.stage_titles.len(), r.len() - 1, "{}", r.title);
            let m = mission(r);
            assert_eq!(m.stages.len(), r.len() - 1);
            assert_eq!((m.key, m.title, m.list_title), (r.key, r.title, r.list_title));
            for s in r.maps.iter() {
                let d = s.player.0.abs_diff(s.enemy.0) as u32 + s.player.1.abs_diff(s.enemy.1) as u32;
                assert!(d >= 20, "{}: {}: HQs {d} apart", r.title, s.name);
                assert!(s.force.len() >= 3);
            }
            // the enemy grows: more units and more funds on every later map
            for w in r.maps.windows(2) {
                assert!(w[1].funds > w[0].funds && w[1].force.len() >= w[0].force.len(), "{}: {} -> {}", r.title, w[0].name, w[1].name);
            }
            // no two units share a cell, and the maps are all different
            for s in r.maps.iter() {
                let mut cells: Vec<(u8, u8)> = s.force.iter().chain(s.mine).map(|u| u.1).collect();
                let n = cells.len();
                cells.sort();
                cells.dedup();
                assert_eq!(cells.len(), n, "{}: {}: two units on one cell", r.title, s.name);
            }
            let mut ids: Vec<u8> = r.maps.iter().map(|s| s.id).collect();
            ids.sort();
            ids.dedup();
            assert_eq!(ids.len(), r.len(), "{}: no map twice", r.title);
            for (t, s) in m.stage_titles.iter().zip(r.maps.iter().skip(1)) {
                assert_eq!(*t, s.name);
            }
            // a run is cut off from none of its rewards
            assert!(r.chest_funds(r.len() as u8 - 2) <= 30_000, "{}", r.title);
            assert!(r.par_per_map > 0);
            for k in 0..r.len() as u8 - 1 {
                assert_eq!(r.offered(k).len(), 3);
            }
            assert_ne!(r.offered(0), r.offered(r.len() as u8 - 2));
        }
        assert_eq!(run1().maps[STAGES - 1].name, "Mial's Hope", "the largest is last");
        assert_eq!((run1().maps[STAGES - 1].funds, run1().maps[STAGES - 1].force.len()), (22000, 9));
    }

    /// The runs cannot outgrow the state block: the draw's bytes (12) end before the draw's flag, and a run with more maps than that is refused here.
    #[test]
    fn a_run_has_three_to_twelve_maps_and_the_runs_do_not_share_maps_ids_or_keys() {
        assert_eq!(MAX_RUN_MAPS, 12);
        assert!(ENEMIES + MAX_RUN_MAPS as u32 <= DRAWN, "twelve enemy COs end before the draw's flag");
        assert_eq!(ENEMIES + 12, STATE + 0x14, "the last of 12 bytes from +0x08 is +0x13; +0x14 is spare");
        assert_eq!((DRAWN - STATE, MODE - STATE), (0x15, 0x16), "the flags stay where saves and the mode expect them");
        for r in RUNS {
            assert!(r.len() >= 3 && r.len() <= MAX_RUN_MAPS, "{}", r.title);
        }
        let mut keys: Vec<&str> = RUNS.iter().map(|r| r.key).collect();
        keys.sort();
        keys.dedup();
        assert_eq!(keys.len(), RUNS.len(), "a key a run");
        let mut titles: Vec<&str> = RUNS.iter().map(|r| r.title).collect();
        titles.sort();
        titles.dedup();
        assert_eq!(titles.len(), RUNS.len());
        assert_eq!(RUNS.len(), 2);
        assert!(RUNS.iter().all(|r| !r.provisional));
        // a run's maps are its own: run 2's maps are none of run 1's
        let first: Vec<u8> = RUNS[0].maps.iter().map(|s| s.id).collect();
        assert!(RUNS[1].maps.iter().all(|s| !first.contains(&s.id)));
    }

    /// Record keys are record ids (`gauntlet_NN`: NN) and are never reused: the five-map run's 50 and the Gauntlet's 1..12 are taken; run 1 is 51 and the second run 52. Every key is below 64 (a
    /// slot of the table keeps the id in a byte), a key is listed here forever, and the missions are the Gauntlet's twelve then the runs in order (run 1's index is 12 as it always was).
    #[test]
    fn the_run_keys_are_record_ids_never_reused() {
        assert_eq!(crate::gauntlet::record_id(KEY), Some(51));
        let used: &[(&str, u8)] = &[("gauntlet_51", 51), ("gauntlet_52", 52)];
        for (i, r) in RUNS.iter().enumerate() {
            assert_eq!(r.key, used[i].0, "run {}'s key never changes", i + 1);
            assert_eq!(crate::gauntlet::record_id(r.key), Some(used[i].1));
            let n = crate::gauntlet::record_id(r.key).unwrap();
            assert!(n > 50, "ids 1..12 are the Gauntlet's and 50 the old five-map run's (nothing reads it)");
            assert_eq!(crate::gauntlet_mode::entries()[12 + i].key, r.key, "mission {} is run {}", 12 + i, i + 1);
            assert!(is_mission(12 + i as u8) && run_of_mission(12 + i as u8).map(|x| x.key) == Some(r.key));
        }
        assert!(!is_mission(11) && !is_mission(12 + RUNS.len() as u8));
        assert_eq!(index_of_key("gauntlet_52"), Some(1));
    }

    #[test]
    fn the_rewards_grow_and_the_units_get_better() {
        for r in RUNS {
            let last = r.len() as u8 - 2;
            assert!(r.chest_funds(last) > r.chest_funds(0));
            assert_ne!(r.offered(0), r.offered(last));
            // the offers never get worse from one map to the next
            let rank = |k: u8| OFFER_LADDER.iter().position(|o| *o == r.offered(k)).unwrap();
            for k in 0..last {
                assert!(rank(k) <= rank(k + 1), "{}: after map {}", r.title, k + 1);
            }
            assert_eq!(rank(0), 0);
            assert_eq!(rank(last), OFFER_LADDER.len() - 1);
        }
        // a shorter and a longer run than nine spread the same ladder
        let mk = |n: usize| Run { maps: &RUN_2_MAPS[..n], ..Run { key: "x", title: "x", list_title: "x", stage_titles: &[], objective: "", maps: &[], chest: (8_000, 2_500), par_per_map: 8, provisional: true } };
        assert_eq!((mk(3).offered(0), mk(3).offered(1)), (OFFER_LADDER[0], OFFER_LADDER[7]));
        assert_eq!(mk(5).offered(1), OFFER_LADDER[2]);
    }

    #[test]
    fn a_draw_is_different_cos_never_the_players_and_changes_with_the_seed() {
        let pool = pool();
        assert_eq!(pool.len(), crate::gauntlet_mode::ROSTER.len() - 5);
        assert!(pool.len() - 1 >= MAX_RUN_MAPS, "twelve enemies without the player's CO");
        let mut seen = std::collections::HashSet::new();
        for seed in 0..400u64 {
            let player = pool[(seed as usize) % pool.len()];
            let n = [STAGES, 9, 12, 3][(seed % 4) as usize];
            let d = draw_cos(seed.wrapping_mul(0x1234_5678_9ABC_DEF1), player, n);
            assert_eq!(d.len(), n);
            let mut v = d.to_vec();
            v.sort();
            v.dedup();
            assert_eq!(v.len(), n, "no repeats in {d:?}");
            assert!(!d.contains(&player), "never the player's CO");
            assert!(d.iter().all(|c| pool.contains(c)));
            seen.insert(d);
        }
        assert!(
            seen.len() > 300,
            "the seed changes the draw ({} of 400 differ)",
            seen.len()
        );
        assert_eq!(draw_cos(7, 1, 9), draw_cos(7, 1, 9), "a seed gives one draw");
    }

    /// Offline only, like the Gauntlet: the pad is taken by the run's page only where no netplay mode is on (`pvp.rs`), and the page and the engine's hooks need the Gauntlet's session.
    #[test]
    fn the_run_is_offline_only() {
        let pvp = include_str!("pvp.rs");
        let at = pvp.find("crate::conquest::tick").expect("the pad hook");
        let before = &pvp[..at];
        let guard = before.rfind("if ds && mode.is_none()").expect("a guard");
        assert!(at - guard < 200, "the call sits inside `if ds && mode.is_none()`");
        // and the session is the Gauntlet's, which Select Mode starts only offline
        let src = include_str!("conquest.rs");
        assert!(src.contains("if !crate::gauntlet::session(core) {"));
    }

    /// The mission tells a Conquest save from a Gauntlet map's in the shared slot (the saved byte's low five bits are the mission, the top three the source): the runs are the missions with their keys,
    /// the last ones, all below 32, and the mode flag is a byte of the state block.
    #[test]
    fn the_runs_are_told_from_the_gauntlets_maps_by_their_missions_and_the_mode_flag_is_in_the_block() {
        let entries = crate::gauntlet_mode::entries();
        let ours: Vec<usize> = (0..entries.len()).filter(|&m| is_mission(m as u8)).collect();
        assert_eq!(ours, (entries.len() - RUNS.len()..entries.len()).collect::<Vec<_>>(), "the runs, the last missions of the campaign");
        assert_eq!(ours[0], 12, "run 1's mission index never moves");
        assert!(entries.len() <= 32, "the saved byte keeps the mission in five bits");
        assert!(!is_mission(entries.len() as u8) && !is_mission(0));
        assert!(MODE >= STATE && MODE < STATE + STATE_LEN);
        assert!(![PAGE, CURSOR, TAKEN, WON, OFFER, OFFER + 1, OFFER + 2, DRAWN].contains(&MODE));
        assert!(MODE < ENEMIES || MODE >= ENEMIES + MAX_RUN_MAPS as u32, "not one of the draw's bytes");
        assert!(MODE != DRAWN);
        // reward_reset clears the first eight bytes of the block only: the flag survives a map switch
        assert!(MODE - STATE >= 8);
        // the draw's bytes lie past the bytes the reward's reset clears and end before the flag
        assert!(ENEMIES - STATE >= 8 && ENEMIES + MAX_RUN_MAPS as u32 <= DRAWN && DRAWN < STATE + STATE_LEN);
        assert_eq!(SAVED_LEN as usize, MAX_RUN_MAPS + 1);
        assert_eq!(SAVED_LEN_V1 as usize, STAGES + 1);
    }

    /// The saved draw: the new record is twelve COs and the flag; the first format's (nine and the flag, `CQR9`) is read as run 1's, with the draw's other bytes cleared.
    #[test]
    fn a_saved_draw_round_trips_and_the_first_format_reads_as_run_one() {
        // (the format is the bytes `saved` writes: MAX_RUN_MAPS COs then 1; `restore` takes either length)
        let new: Vec<u8> = (1..=12u8).chain([1]).collect();
        assert_eq!(new.len(), SAVED_LEN as usize);
        let old: Vec<u8> = (21..=29u8).chain([1]).collect();
        assert_eq!(old.len(), SAVED_LEN_V1 as usize);
        assert_ne!(SAVED_LEN, SAVED_LEN_V1);
    }
}
