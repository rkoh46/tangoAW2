//! Dual Strike's History: a lifetime record of what the player did, with medals (docs/AW2.md "History"), with the
//! pack.
//!
//! **Dual Strike, as found** (USA ROM). `gPlayRecords` keeps 104 counters from +0x37C (`data_02290a94`): play time
//! in frames (0), turns (1), points earned (2), campaigns cleared on Normal and Hard (3, 4), battles by rank S..C
//! (5..8), CO, Super and Tag Powers used (9..11), direct and indirect attacks (12, 13: the attacker's minimum range
//! 1 or more), captures begun and completed (14, 15), the COs' ranks added up (16), funds spent and damage (17, 18,
//! capped at 999999999; the rest at 999999), silos (19), ambushes (20), structure shots taken (21), spaces moved
//! (22), Black Cannons, minicannons, Black Obelisks, Black Crystals, pipe seams destroyed (23..27), supplies and
//! repairs (28), deletes (29), joins, loads, unloads (30..32), units moved (33), CO swaps (34), wins by HQ capture
//! and by rout (35, 36), defeats (37), units sent to the other front (38), Survival runs cleared and maps won by
//! kind (39..44: Time, Turn, Money), Combat mode's (45..49), units bought by type (50 + type) and enemy units
//! destroyed by type (77 + type), Dual Strike's unit types. Only human armies count. The History screen
//! (`HistoryScreen_Init`) lists them in four tabs from the table `0x0215D6C4` (4 x 44 entries of 0x30 bytes: the
//! label's text, the counter's index (0x68 ends a tab), three medal thresholds, the value's getter
//! (`TabList_GetCounter` rec[i], `TabList_GetUnitBought` rec[50 + i], `TabList_GetUnitStatB` rec[77 + i]), its
//! drawer, the help texts of the row and of its three medals); a medal is earned when the value reaches its
//! threshold (`TabList_CountMedals`).
//!
//! **Here.** The same 104 counters at [`RECORD`] after a magic word, so the table's indexes read them directly,
//! saved in Flash slot 15 after the CO skills' data (crate::ds_campaign's record) and loaded with it. Each counter
//! is counted where AW2 does the thing (the hooks below, and crate::co_powers, crate::tag, crate::com_tower,
//! crate::unit_actions, crate::two_front, crate::co_skills, crate::survival, crate::ds_campaign, crate::battle_points
//! call in); a battle's end marks the data to be written with the next profile write. Not counted (left at 0):
//! ambushes (AW2's fog trap was not found), deletes and Combat mode (AW2 has neither: their rows are hidden).
//! Funds spent are the units bought; spaces moved are the straight distance of each move. Everything is in EWRAM,
//! the same on both netplay peers (a netplay match never saves).

use mgba::core::Core;
use std::sync::OnceLock;

use crate::ds_weather::is_on;

// --- RAM (tangoAW2's 0x0203C190..0x0203C333) ---------------------------------------

/// The record: a magic word, then [`COUNTERS`] u32s (Dual Strike's `gPlayRecords` + 0x37C layout).
pub const RECORD: u32 = 0x0203_C190;
const MAGIC: u32 = 0x3154_5348; // "HST1"
pub const COUNTERS: u32 = 104;
/// The record's bytes as saved.
pub const SAVED_LEN: u32 = 4 + 4 * COUNTERS;

pub const PLAY_FRAMES: u32 = 0;
pub const TURNS: u32 = 1;
pub const POINTS: u32 = 2;
pub const CAMPAIGN_CLEARS: u32 = 3;
pub const HARD_CLEARS: u32 = 4;
/// Battles by rank: S, A, B, C.
pub const RANKS: u32 = 5;
pub const CO_POWERS: u32 = 9;
pub const SUPER_POWERS: u32 = 10;
pub const TAG_POWERS: u32 = 11;
pub const DIRECT_ATTACKS: u32 = 12;
pub const INDIRECT_ATTACKS: u32 = 13;
pub const CAPTURES_BEGUN: u32 = 14;
pub const CAPTURES: u32 = 15;
pub const CO_RANKS: u32 = 16;
pub const FUNDS_SPENT: u32 = 17;
pub const DAMAGE: u32 = 18;
pub const SILOS: u32 = 19;
pub const AMBUSHES: u32 = 20;
pub const CANNON_HITS: u32 = 21;
pub const SPACES_MOVED: u32 = 22;
pub const BLACK_CANNONS: u32 = 23;
pub const MINICANNONS: u32 = 24;
pub const OBELISKS: u32 = 25;
pub const CRYSTALS: u32 = 26;
pub const PIPE_SEAMS: u32 = 27;
pub const SUPPLIES: u32 = 28;
pub const DELETES: u32 = 29;
pub const JOINS: u32 = 30;
pub const LOADS: u32 = 31;
pub const UNLOADS: u32 = 32;
pub const UNITS_MOVED: u32 = 33;
pub const SWAPS: u32 = 34;
pub const WINS_HQ: u32 = 35;
pub const WINS_ROUT: u32 = 36;
pub const DEFEATS: u32 = 37;
pub const SENT: u32 = 38;
/// Survival runs cleared (Time, Turn, Money), then maps won (Time, Turn, Money).
pub const SURVIVAL_CLEARS: u32 = 39;
pub const SURVIVAL_MAPS: u32 = 42;
pub const COMBAT: std::ops::Range<u32> = 45..50;
/// Units bought and enemy units destroyed, by Dual Strike's unit type.
pub const BOUGHT: u32 = 50;
pub const DESTROYED: u32 = 77;

const CAP: u32 = 999_999;
const BIG_CAP: u32 = 999_999_999;

fn cap(index: u32) -> u32 {
    match index {
        FUNDS_SPENT | DAMAGE | PLAY_FRAMES => BIG_CAP,
        _ => CAP,
    }
}

/// The record is in RAM (from Flash the first time it is needed: crate::ds_campaign's slot).
pub fn ensure(core: &mut Core) {
    if core.raw_read_32(RECORD, -1) != MAGIC {
        let saved = crate::ds_campaign::saved_history(core);
        load(core, saved.as_deref());
    }
}

/// The record from saved bytes (none, or a record saved before the History: every counter 0).
pub fn load(core: &mut Core, saved: Option<&[u8]>) {
    let mut b = vec![0u8; SAVED_LEN as usize];
    if let Some(s) = saved.filter(|s| s.len() >= 4 && u32::from_le_bytes(s[0..4].try_into().unwrap()) == MAGIC) {
        let n = s.len().min(b.len());
        b[..n].copy_from_slice(&s[..n]);
    }
    b[0..4].copy_from_slice(&MAGIC.to_le_bytes());
    core.raw_write_range(RECORD, -1, &b);
}

/// The record's bytes, as saved.
pub fn bytes(core: &mut Core) -> Vec<u8> {
    ensure(core);
    let mut b = vec![0u8; SAVED_LEN as usize];
    core.raw_read_range(RECORD, -1, &mut b);
    b
}

/// Counter `index`.
pub fn get(core: &Core, index: u32) -> u32 {
    if index >= COUNTERS || core.raw_read_32(RECORD, -1) != MAGIC {
        return 0;
    }
    core.raw_read_32(RECORD + 4 + 4 * index, -1)
}

/// Adds `n` to counter `index` (up to its cap), with the pack.
pub fn add(core: &mut Core, index: u32, n: u32) {
    if !is_on(core) || index >= COUNTERS || n == 0 {
        return;
    }
    ensure(core);
    let at = RECORD + 4 + 4 * index;
    let v = core.raw_read_32(at, -1);
    let c = cap(index);
    if v < c {
        core.raw_write_32(at, -1, v.saturating_add(n).min(c));
    }
}

fn set(core: &mut Core, index: u32, v: u32) {
    if is_on(core) && index < COUNTERS {
        ensure(core);
        core.raw_write_32(RECORD + 4 + 4 * index, -1, v.min(cap(index)));
    }
}

// --- The game ------------------------------------------------------------------------

const CURRENT_ARMY: u32 = 0x0300_33EC;
const SELECTED_UNIT: u32 = 0x0300_40D8;
/// The cell a move ends on (`gUnknown_03003100`: x, y as s16).
const DESTINATION: u32 = 0x0300_3100;
const UNIT_MIN_RANGE: u32 = 0x0E;
const UNIT_PRICE: u32 = 0x06;

fn human(core: &Core, army: u32) -> bool {
    crate::battle_points::human(core, army)
}

fn current_army(core: &Core) -> u32 {
    core.raw_read_16(CURRENT_ARMY, -1) as u32
}

/// The army whose turn it is is a human's.
fn humans_turn(core: &Core) -> bool {
    human(core, current_army(core))
}

/// Dual Strike's unit type for AW2's (tangoAW2's types; the dived Sub's 25 has none).
pub fn ds_type(t: u8) -> Option<u8> {
    match t {
        1..=24 => Some(t),
        crate::roster::CARRIER => Some(25),
        crate::roster::OOZIUM => Some(26),
        _ => None,
    }
}

/// The counter of the human's turn: +1 (an action of the army whose turn it is).
fn count_turn(core: &mut Core, index: u32) {
    if is_on(core) && humans_turn(core) {
        add(core, index, 1);
    }
}

// --- Hooks of their own -----------------------------------------------------------------

/// `IncrementDayCount`: a day is over while a human army is still in the battle (Dual Strike counts the turn order
/// coming round to player 1 again).
const INCREMENT_DAY: u32 = 0x0801_76A8;
fn day_over(core: &mut Core) {
    if is_on(core) && (1..=5).any(|a| human(core, a) && !out(core, a)) {
        add(core, TURNS, 1);
    }
}

fn out(core: &Core, army: u32) -> bool {
    let p = crate::five::players(core) + 0x3C * army;
    core.raw_read_16(p + 0x14, -1) != 0 || core.raw_read_8(p + 0x31, -1) != 0
}

/// `BuyUnit` past its checks (the unit made, r4; its price r6, about to be paid by the army whose turn it is).
const BOUGHT_PAID: u32 = 0x0802_5E52;
fn bought(core: &mut Core) {
    if !is_on(core) || !humans_turn(core) {
        return;
    }
    let cpu = core.gba().cpu();
    let (unit, price) = (cpu.gpr(4) as u32, cpu.gpr(6) as u32);
    if let Some(t) = ds_type(core.raw_read_8(unit, -1)) {
        add(core, BOUGHT + t as u32, 1);
    }
    add(core, FUNDS_SPENT, price);
}

/// `DefeatArmy(army, code)`: on a human's turn another army is out: by its HQ (code 2) or with no units left
/// (codes 1 and 0x10; Dual Strike's `LinkPlayer_MarkDefeated`, the same codes).
const DEFEAT_ARMY: u32 = 0x0802_8894;
fn defeat_army(core: &mut Core) {
    if !is_on(core) || !humans_turn(core) {
        return;
    }
    let cpu = core.gba().cpu();
    let (army, code) = (cpu.gpr(0) as u32 & 0xFF, cpu.gpr(1) as u32);
    if army == current_army(core) {
        return;
    }
    if code & 0x11 != 0 {
        add(core, WINS_ROUT, 1);
    }
    if code & 2 != 0 {
        add(core, WINS_HQ, 1);
    }
}

/// `ApplyCaptureProgress`: a capture action.
const CAPTURE_STEP: u32 = 0x0804_2650;
/// `SiloFire_StartLaunch`: a silo's missile goes.
const SILO_LAUNCH: u32 = 0x0804_09B4;
/// `JoinUnits`, `LoadUnitIntoTransport`, `DropCargoUnit` (each unit dropped).
const JOIN: u32 = 0x0804_2998;
const LOAD: u32 = 0x0804_2864;
const DROP: u32 = 0x0804_28F0;

/// `CommitUnitMove`, `CommitUnitMoveBare` (a unit's action is over) and `CommitUnitMoveForAttack` (an attack's
/// move, before its battle; `CommitUnitMove` follows the battle): the selected unit ends its move on
/// [`DESTINATION`] (its record still holds where it started): the spaces between; a unit moved, once an action.
const COMMIT_MOVE: [u32; 2] = [0x0804_24FC, 0x0804_256C];
const COMMIT_FOR_ATTACK: u32 = 0x0804_25B8;
fn moved(core: &mut Core, done: bool) {
    if !is_on(core) || !humans_turn(core) {
        return;
    }
    let u = core.raw_read_32(SELECTED_UNIT, -1);
    if !(0x0200_0000..0x0400_0000).contains(&u) {
        return;
    }
    let (x0, y0) = (core.raw_read_8(u + 2, -1) as i32, core.raw_read_8(u + 3, -1) as i32);
    let (x1, y1) = (
        core.raw_read_16(DESTINATION, -1) as i16 as i32,
        core.raw_read_16(DESTINATION + 2, -1) as i16 as i32,
    );
    if done {
        add(core, UNITS_MOVED, 1);
    }
    add(core, SPACES_MOVED, ((x1 - x0).abs() + (y1 - y0).abs()) as u32);
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    let mut t: Vec<(u32, Box<dyn Fn(&mut Core)>)> = vec![
        (INCREMENT_DAY, Box::new(day_over)),
        (BOUGHT_PAID, Box::new(bought)),
        (DEFEAT_ARMY, Box::new(defeat_army)),
        (
            CAPTURE_STEP,
            Box::new(|core: &mut Core| count_turn(core, CAPTURES_BEGUN)),
        ),
        (SILO_LAUNCH, Box::new(|core: &mut Core| count_turn(core, SILOS))),
        (JOIN, Box::new(|core: &mut Core| count_turn(core, JOINS))),
        (LOAD, Box::new(|core: &mut Core| count_turn(core, LOADS))),
        (DROP, Box::new(|core: &mut Core| count_turn(core, UNLOADS))),
    ];
    for at in COMMIT_MOVE {
        t.push((at, Box::new(|core: &mut Core| moved(core, true))));
    }
    t.push((COMMIT_FOR_ATTACK, Box::new(|core: &mut Core| moved(core, false))));
    t
}

// --- Called from other modules' hooks ----------------------------------------------------

/// Every frame offline (crate::pvp): play time.
pub fn frame(core: &mut Core, offline: bool) {
    if offline && is_on(core) {
        add(core, PLAY_FRAMES, 1);
    }
}

/// `ActivateCoPower(army, mode)` (crate::co_powers): a human's CO Power (1) or Super CO Power (2); the halves of a
/// Tag Power count as the Tag Power ([`tag_power`]).
pub fn power(core: &mut Core, army: u32, mode: u8) {
    if !is_on(core) || !human(core, army) || crate::tag::phase(core, army) != 0 {
        return;
    }
    match mode {
        1 => add(core, CO_POWERS, 1),
        2 => add(core, SUPER_POWERS, 1),
        _ => {}
    }
}

/// A human army's Tag Power or Change (crate::tag's menu actions).
pub fn tag_power(core: &mut Core, army: u32) {
    if human(core, army) {
        add(core, TAG_POWERS, 1);
    }
}
pub fn swap(core: &mut Core, army: u32) {
    if human(core, army) {
        add(core, SWAPS, 1);
    }
}

/// A capture is complete (crate::com_tower's trap), a Supply or Repair (crate::unit_actions), a unit sent to the
/// other front (crate::two_front): on the army whose turn it is.
pub fn captured(core: &mut Core) {
    count_turn(core, CAPTURES);
}
pub fn supplied(core: &mut Core) {
    count_turn(core, SUPPLIES);
}
pub fn sent(core: &mut Core) {
    count_turn(core, SENT);
}

/// A structure's shot (`kind` the shooter's: 1 Laser, 3 Black Cannon, 4 minicannon) hit army `army`'s unit
/// (crate::co_skills' trap).
pub fn shot_taken(core: &mut Core, army: u32, kind: u16) {
    if is_on(core) && matches!(kind, 1 | 3 | 4) && human(core, army) {
        add(core, CANNON_HITS, 1);
    }
}

/// The structure hit step's destroy branch (crate::factory_hp's trap): what the human's unit destroyed.
pub fn structure_destroyed(core: &mut Core) {
    if !is_on(core) || !humans_turn(core) {
        return;
    }
    let Some((kind, obelisk)) = crate::battle_points::destroyed_structure(core) else {
        return;
    };
    let index = match (kind, obelisk) {
        (_, true) => OBELISKS,
        (Some(crate::battle_points::CANNON), _) => BLACK_CANNONS,
        (Some(crate::battle_points::MINICANNON), _) => MINICANNONS,
        (Some(crate::battle_points::CRYSTAL), _) => CRYSTALS,
        (Some(crate::battle_points::PIPE_SEAM), _) => PIPE_SEAMS,
        _ => return,
    };
    add(core, index, 1);
}

/// A unit battle (crate::co_powers' trap where the meters are charged, the battle records holding what is left):
/// a human's attack, direct or indirect by the attacker's minimum range; the value of the HP each human side took
/// off the other (as War Bonds counts it); the enemy units a human side destroyed (and their cargo), by type.
pub fn battle_fought(core: &mut Core, attacker: u32, defender: u32) {
    if !is_on(core) {
        return;
    }
    let sides = crate::battle_points::fight(core, attacker, defender);
    let table = crate::roster::table(core);
    if human(core, sides[0].army) {
        let t = core.raw_read_8(sides[0].unit, -1) as u32;
        let indirect = core.raw_read_8(table + 0x5C * t + UNIT_MIN_RANGE, -1) > 1;
        add(core, if indirect { INDIRECT_ATTACKS } else { DIRECT_ATTACKS }, 1);
    }
    let bars = |hp: i32| if hp > 0 { (hp - 1) / 10 + 1 } else { 0 };
    for k in 0..2 {
        let (own, foe) = (sides[k], sides[1 - k]);
        if !human(core, own.army) {
            continue;
        }
        let t = core.raw_read_8(foe.unit, -1) as u32;
        let price = core.raw_read_16(table + 0x5C * t + UNIT_PRICE, -1) as u32 * 10;
        let before = bars(core.raw_read_8(foe.unit + 4, -1) as i32 & 0x7F);
        let lost = (before - bars(foe.hp_after)).max(0) as u32;
        add(core, DAMAGE, lost * price / 10);
        if foe.hp_after <= 0 {
            let units = core.raw_read_32(0x0849_9594, -1);
            let cargo = [core.raw_read_8(foe.unit + 7, -1), core.raw_read_8(foe.unit + 8, -1)];
            for u in std::iter::once(foe.unit).chain(cargo.iter().filter(|&&c| c != 0).map(|&c| units + 12 * c as u32))
            {
                if let Some(d) = ds_type(core.raw_read_8(u, -1)) {
                    add(core, DESTROYED + d as u32, 1);
                }
            }
        }
    }
}

/// A DS Campaign cleared (Means to an End won; crate::ds_campaign).
pub fn campaign_cleared(core: &mut Core, hard: bool) {
    add(core, if hard { HARD_CLEARS } else { CAMPAIGN_CLEARS }, 1);
}

/// A Survival map won, a run cleared (crate::survival; `kind` its Time 0, Money 1, Turn 2).
pub fn survival_map(core: &mut Core, kind: u8, cleared: bool) {
    let k = match kind {
        0 => 0,
        2 => 1,
        _ => 2,
    };
    add(core, SURVIVAL_MAPS + k, 1);
    if cleared {
        add(core, SURVIVAL_CLEARS + k, 1);
    }
}

/// The COs' ranks added up (Dual Strike's `PlayRecords_UpdateCoRankTotal`), after EXP changed.
pub fn co_ranks(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let total: u32 = (0..=18u8)
        .chain(72..=82)
        .map(|co| crate::co_skills::rank(core, co))
        .sum();
    set(core, CO_RANKS, total);
}

/// A battle's end (crate::battle_points::results, with the score of the results army, the battle's points and the
/// best taken off): points earned; the battle's rank (the campaigns and the War Room, Survival not); the human
/// armies defeated (Survival not); the COs' ranks. Then the data is to be written with the next profile write
/// unless `save` is false (AW2's own campaign before any skill is set: it saves nothing more).
pub fn battle_over(core: &mut Core, score: u32, total: u32, best: u32, survival: bool, save: bool) {
    if !is_on(core) {
        return;
    }
    add(core, POINTS, total.saturating_sub(best));
    let mode = core.raw_read_8(0x0300_3FC1, -1);
    if !survival && (mode == 1 || mode == 2) && human(core, 1) {
        // Dual Strike's `Score_ToRank_020e5428`: S from 280, A from 250, B from 200.
        let r = match score {
            280.. => 0,
            250.. => 1,
            200.. => 2,
            _ => 3,
        };
        add(core, RANKS + r, 1);
    }
    if !survival {
        for a in 1..=4u32 {
            if human(core, a) && out(core, a) {
                add(core, DEFEATS, 1);
            }
        }
    }
    co_ranks(core);
    if save {
        crate::co_skills::mark_dirty(core);
    }
}

// --- The table (Dual Strike's `data_0215d6c4`) -------------------------------------------

const TABLE: u32 = 0x0215_D6C4;
const TABS: usize = 4;
const PER_TAB: u32 = 44;
const ENTRY: u32 = 0x30;
const END_MARK: u16 = 0x68;
const GET_COUNTER: u32 = 0x0207_244C;
const GET_BOUGHT: u32 = 0x0207_241C;
const GET_STAT_B: u32 = 0x0207_23EC;
const DRAW_TIME: u32 = 0x0207_2188;
/// The deletes' row and Combat mode's: AW2 has neither.
const HIDDEN: [u32; 6] = [DELETES, 45, 46, 47, 48, 49];

/// One row of the History.
#[derive(Clone, Debug)]
pub struct Entry {
    /// Dual Strike's text id of the label (`0x7A000000 | n`).
    pub text: u32,
    /// The counter shown.
    pub counter: u32,
    /// Bought or destroyed rows: Dual Strike's unit type.
    pub unit: Option<u8>,
    pub thresholds: [u32; 3],
    /// The row's help, then each medal's.
    pub help: [u32; 4],
    /// Shown as a time (frames).
    pub time: bool,
}

/// The four tabs (General, Built, Destroyed, Objects), read from the pack, AW2's missing rows left out.
pub fn tabs() -> Option<&'static [Vec<Entry>; TABS]> {
    static TABLE_ROWS: OnceLock<Option<[Vec<Entry>; TABS]>> = OnceLock::new();
    TABLE_ROWS
        .get_or_init(|| {
            let pack = crate::ds_pack::pack()?;
            let ds = crate::ds_campaign_data::Ds::from_pack(pack)?;
            let mut tabs: [Vec<Entry>; TABS] = Default::default();
            for (tab, rows) in tabs.iter_mut().enumerate() {
                for e in 0..PER_TAB {
                    let a = TABLE + (tab as u32 * PER_TAB + e) * ENTRY;
                    let index = ds.u16(a + 4)?;
                    if index == END_MARK {
                        break;
                    }
                    let index = index as u32;
                    let (counter, unit) = match ds.u32(a + 0x14)? {
                        GET_COUNTER => (index, None),
                        GET_BOUGHT => (BOUGHT + index, Some(index as u8)),
                        GET_STAT_B => (DESTROYED + index, Some(index as u8)),
                        _ => continue,
                    };
                    if counter >= COUNTERS || (unit.is_none() && HIDDEN.contains(&counter)) {
                        continue;
                    }
                    rows.push(Entry {
                        text: ds.u32(a)?,
                        counter,
                        unit,
                        thresholds: [ds.u32(a + 8)?, ds.u32(a + 12)?, ds.u32(a + 16)?],
                        help: [
                            ds.u32(a + 0x20)?,
                            ds.u32(a + 0x24)?,
                            ds.u32(a + 0x28)?,
                            ds.u32(a + 0x2C)?,
                        ],
                        time: ds.u32(a + 0x18)? == DRAW_TIME,
                    });
                }
            }
            Some(tabs)
        })
        .as_ref()
}

/// The medals row `e` has earned (0..3).
pub fn medals(core: &Core, e: &Entry) -> usize {
    let v = get(core, e.counter);
    e.thresholds.iter().filter(|&&t| v >= t).count()
}

/// Medals earned and medals there are, every tab (`TabList_CountMedals`).
pub fn medal_count(core: &Core) -> (u32, u32) {
    let Some(tabs) = tabs() else { return (0, 0) };
    let rows = tabs.iter().flatten();
    rows.fold((0, 0), |(n, t), e| (n + medals(core, e) as u32, t + 3))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn layout() {
        assert_eq!(SAVED_LEN, 0x1A4);
        assert_eq!(DESTROYED + 26, COUNTERS - 1, "the Oozium's is the last");
        assert_eq!(ds_type(crate::roster::CARRIER), Some(25));
        assert_eq!(ds_type(25), None);
    }

    /// With a Dual Strike ROM (TANGOAW2_DS_ROM): the table reads as Dual Strike has it, less AW2's missing rows.
    #[test]
    #[ignore]
    fn table_from_the_pack() {
        let t = tabs().expect("the pack");
        assert_eq!(t[0].len(), 43 - HIDDEN.len());
        assert_eq!((t[1].len(), t[2].len(), t[3].len()), (25, 25, 7));
        assert!(t[0][0].time && t[0][0].counter == PLAY_FRAMES);
        assert_eq!(t[3][5].counter, DESTROYED + 26, "Oozium destroyed");
    }
}
