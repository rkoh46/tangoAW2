//! Conquest Run (docs/dev/conquest.md): a roguelike run of five maps in a row, offline, Select Mode's CONQUEST entry ([`crate::mode_menu`]). The maps are AW2's own two-player Versus maps read
//! from the player's ROM ([`crate::custom_campaign::MapSrc::Aw2`]), small to large; the survivors and the funds carry over at every map switch (the stage engine, [`crate::stage`]), a reward
//! is picked between maps ([`crate::conquest_reward`]), one loss ends the run and the whole run's score goes to the Gauntlet's record table under the key [`KEY`].
//!
//! It is its own game mode on the Gauntlet's engine: a mission of the Gauntlet's campaign ([`crate::gauntlet_mode::def`]; stage 0 is the mission's own map and each later map one of its
//! [`StageDef`]s), so records, Save / Continue, EXP and the results screen come from the Gauntlet's plumbing, but the wheel's CONQUEST entry picks it ([`picked`] sets the mode flag [`mode`],
//! which makes the map selector list this one row and the Gauntlet's list never has it) and a run saved halfway is told from the Gauntlet's by its mission ([`is_mission`], [`run_saved`]). A map is won when the player takes the enemy HQ or destroys every enemy unit (the enemy HQ is held, so a capture defeats
//! nobody and the trigger moves the battle on; the engine's own defeat of an army with no units is held off on every map but the last: [`keeps_alive`]); the last map's win wins the run.

use mgba::core::Core;

use crate::custom_campaign::{colour, unit, *};
use crate::online::{KEY_A, KEY_B, KEY_LEFT, KEY_RIGHT};

/// The run's record key: record id 50 (never reused; the Gauntlet's maps are 1..12).
pub const KEY: &str = "gauntlet_50";
/// The maps of a run.
pub const STAGES: usize = 5;

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

/// The five maps, small to large, easy to hard (HQs 20 to 39 cells apart, an equal share of bases, no sea to cross): Sabre Range, Switchback, Piston Dam, Cube Keys, Mial's Hope.
/// The cells are the Versus maps' own properties (read from the ROM by `aw2dev conquest maps`).
pub const MAPS: [Stage; STAGES] = [
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
        id: 0x1C,
        name: "Switchback",
        player: (1, 13),
        enemy: (19, 1),
        funds: 6000,
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
        funds: 10000,
        force: &[
            (unit::INFANTRY, (20, 11)),
            (unit::INFANTRY, (21, 11)),
            (unit::TANK, (22, 1)),
            (unit::TANK, (23, 1)),
            (unit::MD_TANK, (24, 1)),
            (unit::ARTILLERY, (20, 4)),
        ],
        mine: &[],
    },
    Stage {
        id: 0x0E,
        name: "Cube Keys",
        player: (5, 6),
        enemy: (26, 23),
        funds: 15000,
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

/// The enemy army's colour on every map (Black Hole's: the player's pick offers the other four and Silver Nova).
pub const ENEMY_COLOUR: u8 = colour::BLACK_HOLE;
/// The CO the enemy's army is compiled with: a stand-in. The run's own draw ([`begin_run`]) is written over it when each map starts ([`enemy_co`]).
pub const STAND_IN: u8 = crate::custom_campaign::co::ANDY;

/// The player's funds on the first map, and the days a well-played map takes (the score's par: [`crate::gauntlet_mode::par_days`]).
const START_FUNDS: u32 = 7000;
pub const PAR_PER_MAP: u16 = 8;

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

/// The mission: the first map, with the four later maps as its stages.
pub fn mission() -> MissionDef {
    let first = &MAPS[0];
    let mut m = MissionDef::new(KEY, "Conquest Run");
    m.list_title = "Conquest Run *";
    m.stage_titles = &["Switchback", "Piston Dam", "Cube Keys", "Mial's Hope"];
    m.objective = "Win five maps in a row: survivors and funds come along, a reward waits between maps.";
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
    for (k, s) in MAPS.iter().enumerate().skip(1) {
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
            if k + 1 == STAGES {
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

/// Whether the Gauntlet-campaign mission index `m` is the Conquest Run.
pub fn is_mission(m: u8) -> bool {
    crate::gauntlet_mode::entries().get(m as usize).is_some_and(|e| e.key == KEY)
}

/// A Conquest Run is saved halfway (the shared slot's save tagged with the Gauntlet's source and this mission).
pub fn run_saved(core: &Core) -> bool {
    crate::suspend::saved_mission_of(core, crate::gauntlet::SOURCE).is_some_and(is_mission)
}

/// Whether the Gauntlet's session is a Conquest Run.
pub fn session(core: &Core) -> bool {
    crate::gauntlet::session(core)
        && is_mission(crate::ds_campaign::mission(core))
}

/// The engine's own end of a map (the enemy army with no units: `DefeatArmy`, and the end check's alive marks) is held off while the run goes on: a map is won by [`won`]'s trigger, which moves the
/// battle to the next map, and only the last map's win ends the run (AW2's victory there is the run's).
pub fn keeps_alive(core: &Core, army: u8) -> bool {
    army == 2 && session(core) && (crate::stage::stage(core) as usize) + 1 < STAGES
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

/// The run's draw: +0x10..+0x14 the enemy CO of each map (AW2 CO ids), +0x15 1 once a run has drawn them. Saved with a run saved halfway ([`saved`]).
const ENEMIES: u32 = STATE + 0x10;
const DRAWN: u32 = STATE + 0x15;
/// The bytes of the run's draw that go into a saved run: the five COs and the flag.
pub const SAVED_LEN: u32 = 6;
/// The tail mark of a saved run's draw, after AW2's block.
pub const SAVED_MARK: u32 = 0x4E52_5143; // "CQRN"

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

/// A run's enemies: one CO a map, never the player's, never twice, drawn from [`pool`] by a shuffle driven by `seed` (xorshift64*: deterministic for a seed).
pub fn draw_cos(seed: u64, player: u8) -> [u8; STAGES] {
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
    let mut out = [0u8; STAGES];
    out.copy_from_slice(&p[..STAGES]);
    out
}

/// A new run begins (the army screen's A, [`crate::gauntlet_ui::apply`]): when it is a Conquest Run, its enemies are drawn from the game's own random state and the frame count (offline only: nothing
/// of the draw is netplay's) and kept with the run.
pub fn begin_run(core: &mut Core) {
    if !crate::gauntlet_ui::picked(core).is_some_and(|e| e.key == KEY) {
        return;
    }
    let player = core.raw_read_8(crate::gauntlet_ui::CO_PICK, -1);
    let seed = (core.raw_read_32(0x0300_1FD4, -1) as u64) << 32
        ^ (core.frame_counter() as u64).wrapping_mul(0x9E37_79B9_7F4A_7C15);
    let cos = draw_cos(seed, player);
    core.raw_write_range(ENEMIES, -1, &cos);
    core.raw_write_8(DRAWN, -1, 1);
    log::info!("conquest: the run's enemies are {cos:?} for CO {player}");
}

/// The enemy CO of map `k` (0 the first) of the run in progress, if a draw is held.
pub fn enemy_co(core: &Core, k: usize) -> Option<u8> {
    (k < STAGES && core.raw_read_8(DRAWN, -1) != 0).then(|| core.raw_read_8(ENEMIES + k as u32, -1))
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

/// The run's draw as saved with a run saved halfway (the five COs and the flag), None outside a Conquest Run.
pub fn saved(core: &Core) -> Option<Vec<u8>> {
    if !session(core) || core.raw_read_8(DRAWN, -1) == 0 {
        return None;
    }
    let mut b = vec![0u8; SAVED_LEN as usize];
    core.raw_read_range(ENEMIES, -1, &mut b);
    Some(b)
}

/// A saved run continues: its draw comes back.
pub fn restore(core: &mut Core, b: &[u8]) {
    if b.len() >= SAVED_LEN as usize {
        core.raw_write_range(ENEMIES, -1, &b[..SAVED_LEN as usize]);
    }
}

/// The rewards: the war chest, the free unit, the field repair.
pub const CHEST: u8 = 0;
pub const REINFORCE: u8 = 1;
pub const REPAIR: u8 = 2;

/// The war chest after map `k` (0 the first): 10,000, growing by 5,000 a map.
pub fn chest_funds(k: u8) -> u32 {
    10_000 + 5_000 * k as u32
}

/// The three units a free unit is chosen from after map `k`: better ones later.
pub fn offered(k: u8) -> [u8; 3] {
    match k {
        0 => [unit::TANK, unit::MD_TANK, unit::B_COPTER],
        1 => [unit::MD_TANK, unit::ROCKETS, unit::FIGHTER],
        2 => [unit::NEOTANK, unit::ROCKETS, unit::BOMBER],
        _ => [unit::MEGATANK, unit::NEOTANK, unit::BOMBER],
    }
}

/// The map the reward is for (the one just won, 0..=3).
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
        let k = crate::stage::stage(core).min(STAGES as u8 - 2);
        core.raw_write_8(WON, -1, k);
        core.raw_write_8(CURSOR, -1, 0);
        core.raw_write_8(PAGE, -1, 1);
        core.raw_write_range(OFFER, -1, &offered(k));
    }
    true
}

/// The reward is taken: `what` happens to the survivors waiting in the stage engine's carry buffer (so the next map's arrival brings it), the page closes.
fn take(core: &mut Core, what: u8, unit_kind: u8) {
    let k = won_map(core);
    match what {
        CHEST => {
            let f = crate::stage::carried_funds(core);
            crate::stage::set_carried_funds(core, f + chest_funds(k));
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

    #[test]
    fn the_run_has_five_maps_with_hqs_far_apart() {
        assert_eq!(MAPS.len(), STAGES);
        let m = mission();
        assert_eq!(m.stages.len(), STAGES - 1);
        for s in MAPS.iter() {
            let d = s.player.0.abs_diff(s.enemy.0) as u32 + s.player.1.abs_diff(s.enemy.1) as u32;
            assert!(d >= 20, "{}: HQs {d} apart", s.name);
            assert!(s.force.len() >= 3);
        }
        // the enemy grows: more units and more funds on every later map
        for w in MAPS.windows(2) {
            assert!(w[1].funds > w[0].funds && w[1].force.len() >= w[0].force.len());
        }
        assert_eq!(m.stage_titles.len(), STAGES - 1);
        for (t, s) in m.stage_titles.iter().zip(MAPS.iter().skip(1)) {
            assert_eq!(*t, s.name);
        }
    }

    #[test]
    fn the_rewards_grow_and_the_units_get_better() {
        assert_eq!((chest_funds(0), chest_funds(3)), (10_000, 25_000));
        assert_ne!(offered(0), offered(3));
        for k in 0..4 {
            assert_eq!(offered(k).len(), 3);
        }
    }

    #[test]
    fn a_draw_is_five_different_cos_never_the_players_and_changes_with_the_seed() {
        let pool = pool();
        assert_eq!(pool.len(), crate::gauntlet_mode::ROSTER.len() - 5);
        let mut seen = std::collections::HashSet::new();
        for seed in 0..400u64 {
            let player = pool[(seed as usize) % pool.len()];
            let d = draw_cos(seed.wrapping_mul(0x1234_5678_9ABC_DEF1), player);
            let mut v = d.to_vec();
            v.sort();
            v.dedup();
            assert_eq!(v.len(), STAGES, "no repeats in {d:?}");
            assert!(!d.contains(&player), "never the player's CO");
            assert!(d.iter().all(|c| pool.contains(c)));
            seen.insert(d);
        }
        assert!(
            seen.len() > 300,
            "the seed changes the draw ({} of 400 differ)",
            seen.len()
        );
        assert_eq!(draw_cos(7, 1), draw_cos(7, 1), "a seed gives one draw");
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
        assert!(src.contains("crate::gauntlet::session(core) &&"));
    }

    /// The mission tells a Conquest save from a Gauntlet map's in the shared slot (the saved byte's low five bits are the mission, the top three the source): Conquest's is the one mission with
    /// its key, below 32, and the mode flag is a byte of the state block.
    #[test]
    fn the_run_is_told_from_the_gauntlets_maps_by_its_mission_and_its_mode_flag_is_in_the_block() {
        let entries = crate::gauntlet_mode::entries();
        let ours: Vec<usize> = (0..entries.len()).filter(|&m| is_mission(m as u8)).collect();
        assert_eq!(ours, vec![entries.len() - 1], "one mission, the last of the campaign");
        assert!(entries.len() <= 32, "the saved byte keeps the mission in five bits");
        assert!(!is_mission(entries.len() as u8) && !is_mission(0));
        assert!(MODE >= STATE && MODE < STATE + STATE_LEN);
        assert!(![PAGE, CURSOR, TAKEN, WON, OFFER, OFFER + 1, OFFER + 2, DRAWN].contains(&MODE));
        assert!(MODE < ENEMIES || MODE > ENEMIES + STAGES as u32, "not one of the draw's bytes");
        assert!(MODE != DRAWN);
        // reward_reset clears the first eight bytes of the block only: the flag survives a map switch
        assert!(MODE - STATE >= 8);
    }

    #[test]
    fn the_key_is_a_record_id() {
        assert_eq!(crate::gauntlet::record_id(KEY), Some(50));
    }
}
