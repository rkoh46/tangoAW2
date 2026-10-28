//! Dual Strike's COs, with the Dual Strike pack.
//!
//! AW2's CO table (`CoData`, 19 rows of 0x104 bytes at [`AW2_TABLE`]) is
//! full: the movement charts follow it. With the pack the game reads
//! tangoAW2's copy at [`TABLE`] instead (every literal-pool word holding
//! its address is switched, [`POOL`]), which has room for [`ROOM`] COs, so
//! COs can be added after AW2's 19 and after the trooper faces (ids 19..71
//! are Andy's row, never shown; see `ds3/aw2_cos.md` s1.3 for why new COs
//! start at 72).
//!
//! In the copy, AW2's COs take Dual Strike's numbers: power stars, vision,
//! luck, bad luck, counter, unit cost and capture per power level. Sturm is
//! not in Dual Strike and keeps AW2's. Everything Dual Strike works out per
//! unit comes from the pack when it is needed:
//! - firepower, defence, move and range: [`stat`], in place of AW2's four
//!   per-unit CO functions. Dual Strike adds a value for the unit's class
//!   (foot, direct vehicle, indirect vehicle, plane, copter, navy) and one
//!   for its kind of combat (direct, indirect, transport, Black Bomb), and
//!   every power adds 10% firepower (AW2's powers already add the 10%
//!   defence, player +0x28);
//! - firepower on each terrain (Koal's roads, Jake's plains, Kindle's
//!   cities) and the enemy's lost terrain stars (Sonja): in the damage
//!   formula;
//! - the Com Tower bonus per tower, attack and defence (Javier's is
//!   higher): [`tower_attack`], [`tower_defence`].

use mgba::core::Core;
use std::sync::OnceLock;

use crate::ds_weather::is_on;

pub const AW2_TABLE: u32 = 0x085D_3DD0;
pub const ROW: u32 = 0x104;
pub const AW2_COS: u8 = 19;
/// Rows in tangoAW2's copy: CO ids are one byte, face ids `co + 24 * face`
/// reach `co + 48`, so new COs fit in 72..95.
pub const ROOM: u32 = 96;
pub const TABLE: u32 = 0x086A_0000; // ROOM rows: to +0x6180
const SENTINEL: u32 = 0x086A_FFFC;
const MAGIC: u32 = 0x3543_5344; // "DSC5"
/// AW2's "no CO" row, which the unused ids copy.
const ANDY: u8 = 1;

/// Every ROM word holding the table's address, with the offset it adds
/// (a full-ROM scan finds these 48 and no others).
const POOL: [(u32, u32); 48] = [
    (0x0800_0A38, 0x0),
    (0x0800_8A5C, 0x0),
    (0x0800_8C20, 0x0),
    (0x0801_F8E4, 0x0),
    (0x0803_8834, 0x50),
    (0x0803_88E0, 0x0),
    (0x0803_8E64, 0x0),
    (0x0803_990C, 0x0),
    (0x0803_9980, 0x0),
    (0x0803_9F50, 0x0),
    (0x0804_1F24, 0x0),
    (0x0804_2DDC, 0x0),
    (0x0804_2E28, 0x0),
    (0x0804_2E58, 0x0),
    (0x0804_2EB0, 0x0),
    (0x0804_2F08, 0x0),
    (0x0804_2F54, 0x0),
    (0x0804_2F9C, 0x0),
    (0x0804_2FF0, 0x0),
    (0x0804_3044, 0x0),
    (0x0804_30F4, 0x0),
    (0x0804_30FC, 0x5C),
    (0x0804_3164, 0x0),
    (0x0804_316C, 0x5C),
    (0x0804_31D4, 0x0),
    (0x0804_31DC, 0x5C),
    (0x0804_3244, 0x0),
    (0x0804_324C, 0x5C),
    (0x0804_329C, 0x0),
    (0x0804_32D4, 0x0),
    (0x0804_3DA4, 0x0),
    (0x0804_4200, 0x0),
    (0x0804_4234, 0x0),
    (0x0804_4B94, 0x0),
    (0x0804_6854, 0x50),
    (0x0804_6864, 0x0),
    (0x0804_6C3C, 0x0),
    (0x0805_BB80, 0x0),
    (0x0805_BC68, 0x0),
    (0x0805_BDC8, 0x0),
    (0x0805_DBD8, 0x0),
    (0x0805_DC98, 0x0),
    (0x0806_876C, 0x0),
    (0x0806_88A4, 0x0),
    (0x0807_A85C, 0x0),
    (0x0807_FAD0, 0x0),
    (0x0808_06A0, 0x0),
    (0x0808_53AC, 0x0),
];

/// Dual Strike's id for each AW2 CO (Sturm has none).
const DS_IDS: [Option<u8>; AW2_COS as usize] = [
    Some(1),  // Nell
    Some(2),  // Andy
    Some(3),  // Max
    Some(4),  // Olaf
    Some(5),  // Sami
    Some(6),  // Grit
    Some(7),  // Kanbei
    Some(8),  // Sonja
    Some(9),  // Eagle
    Some(10), // Drake
    None,     // Sturm
    Some(26), // Flak
    Some(13), // Lash
    Some(27), // Adder
    Some(15), // Hawke
    Some(16), // Hachi
    Some(17), // Colin
    Some(18), // Jess
    Some(19), // Sensei
];

pub fn ds_co(co: u8) -> Option<u8> {
    DS_IDS
        .get(co as usize)
        .copied()
        .flatten()
        .or_else(|| crate::co_new::ds_id(co))
        .or_else(|| (co == crate::co_new::ASUKA).then_some(crate::asuka::SONJA_DS))
}

/// The Dual Strike record a CO's table row is filled from (Crumb's: Andy's,
/// for what his own numbers do not set).
fn row_base(co: u8) -> Option<u8> {
    ds_co(co).or_else(|| crate::co_new::all().find(|n| n.0 == co).map(|n| n.1))
}

// --- Dual Strike's CO records (arm9) ---------------------------------------

const DS_RECORDS: u32 = 0x0215_360C;
const DS_RECORD: u32 = 0x220;
const DS_BLOCKS: u32 = 0xA0;
const DS_BLOCK: u32 = 0x80;
/// The class-stat pointer that means "no change".
const DS_NO_STAT: u32 = 0x0216_E03C;
const DS_OVERLAY_BASE: u32 = 0x022A_D560;

fn record(ds: u8) -> Option<&'static [u8]> {
    crate::ds_pack::pack()?.arm9_at(DS_RECORDS + DS_RECORD * ds as u32, DS_RECORD as usize)
}

/// A power level's block (0 day to day, 1 COP, 2 SCOP).
fn block(ds: u8, mode: u8) -> Option<&'static [u8]> {
    let o = (DS_BLOCKS + DS_BLOCK * mode.min(2) as u32) as usize;
    record(ds)?.get(o..o + DS_BLOCK as usize)
}

fn u32_at(b: &[u8], o: usize) -> u32 {
    u32::from_le_bytes(b[o..o + 4].try_into().unwrap())
}

fn i16_at(b: &[u8], o: usize) -> i16 {
    i16::from_le_bytes([b[o], b[o + 1]])
}

/// One of a block's 11 class stats: {firepower %, defence %, move, range}.
fn class_stat(b: &[u8], k: usize) -> [i16; 4] {
    let p = u32_at(b, 0x54 + 4 * k);
    if p == DS_NO_STAT {
        return [0; 4];
    }
    match crate::ds_pack::pack().and_then(|pk| pk.arm9_at(p, 8)) {
        Some(s) => [i16_at(s, 0), i16_at(s, 2), i16_at(s, 4), i16_at(s, 6)],
        None => [0; 4],
    }
}

/// Dual Strike's unit class (+0x1C) to a block's class stat: foot, direct
/// vehicle, indirect vehicle, plane, copter, navy, and 6 (Oozium's own
/// class, a slot every CO leaves empty).
const CLASS_SLOTS: u8 = 7;
/// Its kind of combat (+0x20) to the stat added on top.
fn combat_slot(combat: u8) -> Option<usize> {
    match combat {
        5 => Some(7),     // direct (not foot)
        4 => Some(8),     // indirect
        2 | 6 => Some(9), // transport
        7 => Some(10),    // Black Bomb
        _ => None,
    }
}

pub const FIREPOWER: usize = 0;
pub const DEFENCE: usize = 1;
pub const MOVE: usize = 2;
pub const RANGE: usize = 3;
/// What every power adds to firepower (Dual Strike's 0x020E23D8).
const POWER_FIREPOWER: i32 = 10;

/// Dual Strike's `field` for unit type `t` under CO `co` at power `mode`,
/// or `None` for a CO Dual Strike does not have.
pub fn stat(co: u8, mode: u8, t: u8, field: usize) -> Option<i32> {
    // No CO changes an Oozium (Dual Strike's 0x020E5678, 0x020E57AC,
    // 0x020E5A58, 0x020E5C40, 0x020E5D8C return 0 for its class, 6; see
    // [`crate::oozium`]), Sturm included.
    if t == crate::roster::OOZIUM {
        return Some(0);
    }
    let mut v = 0i32;
    if co == crate::co_new::CRUMB {
        // His numbers are his own (crate::crumb): no Dual Strike block.
        v += crate::crumb::bonus(mode, t, field);
    } else if crate::es_co::is_es(co) {
        v += crate::es_co::bonus(co, mode, t, field);
    } else if co == crate::co_new::ARIA {
        // Her numbers are her own (crate::aria): no Dual Strike block.
        v += crate::aria::bonus(mode, field);
    } else if co == crate::co_new::CLONE_ANDY {
        // His numbers are his own (crate::co_new::clone_andy_bonus), not Andy's block.
        v += crate::co_new::clone_andy_bonus(mode, field);
    } else {
        let b = block(ds_co(co)?, mode)?;
        let unit = crate::roster::ds_record(t)?;
        let (class, combat) = (unit[0x1C], unit[0x20]);
        if class < CLASS_SLOTS {
            v += class_stat(b, class as usize)[field] as i32;
        }
        if let Some(k) = combat_slot(combat) {
            v += class_stat(b, k)[field] as i32;
        }
    }
    if field == FIREPOWER && mode > 0 {
        v += POWER_FIREPOWER;
    }
    if co == crate::co_new::ASUKA && matches!(field, FIREPOWER | DEFENCE) {
        // her day to day: all her units +5% attack and +5% defence, on top of every power's numbers
        v += crate::asuka::DAY_BONUS;
    }
    Some(v)
}

// --- Players ----------------------------------------------------------------

const PLAYERS_POINTER: u32 = 0x0849_9598;
const PLAYER: u32 = 0x3C;
const CO_ABILITIES: u32 = 0x0300_3FC8;

/// An army's (CO, power level).
pub fn army_co(core: &Core, army: u32) -> (u8, u8) {
    let p = core.raw_read_32(PLAYERS_POINTER, -1) + PLAYER * army;
    (core.raw_read_8(p + 0x1D, -1), core.raw_read_8(p + 0x1E, -1))
}

fn abilities_on(core: &Core) -> bool {
    core.raw_read_8(CO_ABILITIES, -1) != 0
}

/// A block's i16 for an army's CO, or `default` (Sturm, no pack).
fn army_field(core: &Core, army: u32, o: usize, default: i32) -> i32 {
    let (co, mode) = army_co(core, army);
    ds_co(co)
        .and_then(|ds| block(ds, mode))
        .map(|b| i16_at(b, o) as i32)
        .unwrap_or(default)
}

/// Firepower % per Com Tower the army owns.
pub fn tower_attack(core: &Core, army: u32) -> i32 {
    army_field(core, army, 0x26, 10)
}

/// Defence % per Com Tower the army owns.
pub fn tower_defence(core: &Core, army: u32) -> i32 {
    army_field(core, army, 0x28, 0)
}

/// Firepower % for a unit of this army on `terrain`.
pub fn terrain_firepower(core: &Core, army: u32, terrain: u8) -> i32 {
    let (co, mode) = army_co(core, army);
    let Some(b) = ds_co(co).and_then(|ds| block(ds, mode)) else {
        return 0;
    };
    let list = u32_at(b, 0x2C);
    crate::ds_pack::pack()
        .and_then(|p| p.overlay_at(0, DS_OVERLAY_BASE, list, 32))
        .map(|l| l[(terrain & 0x1F) as usize] as i8 as i32)
        .unwrap_or(0)
}

/// HP a property's daily repair adds for the army's CO (Dual Strike's
/// `Player_GetCoRepairBonus`: its power block's `repairBonus`, +0x1A;
/// Rachel's 1), with CO abilities on.
pub fn repair_bonus(core: &Core, army: u32) -> i32 {
    if abilities_on(core) {
        army_field(core, army, 0x1A, 0)
    } else {
        0
    }
}

/// Terrain stars the army's enemies lose (Sonja).
pub fn enemy_terrain_cut(core: &Core, army: u32) -> i32 {
    army_field(core, army, 0x2A, 0).max(0)
}

/// Whether an army's CO has Dual Strike skill `bit` of its power block's
/// skill byte `byte` (+0x08 + byte; [`SKILLS`]), with CO abilities on.
pub fn has_ds_skill(core: &Core, army: u32, byte: usize, bit: u8) -> bool {
    let (co, mode) = army_co(core, army);
    abilities_on(core)
        && ds_co(co)
            .and_then(|ds| block(ds, mode))
            .is_some_and(|b| b[0x08 + byte] & bit != 0)
}

/// Lash's day to day (Dual Strike's `SKILL_TERRAIN_FIREPOWER`, block +0x09
/// bit 0x80) and her Super Power (`SKILL_DOUBLE_TERRAIN_STARS`, +0x08 bit
/// 0x10).
pub fn terrain_firepower_skill(core: &Core, army: u32) -> bool {
    has_ds_skill(core, army, 1, 0x80)
}
fn double_terrain_stars(core: &Core, army: u32) -> bool {
    has_ds_skill(core, army, 0, 0x10)
}

/// Army `a` is still in the game: it has a controller (+0x1B) and is not
/// defeated (+0x14).
pub(crate) fn in_game(core: &Core, a: u32) -> bool {
    let p = core.raw_read_32(PLAYERS_POINTER, -1) + PLAYER * a;
    core.raw_read_8(p + 0x1B, -1) != 0 && core.raw_read_16(p + 0x14, -1) == 0
}

/// Terrain defence (10 a star) army `army`'s units lose: every enemy in
/// the game (another team) cuts its CO's stars at its power level
/// (Dual Strike's `MovementCost`, `player.terrainDefense` negated).
pub fn terrain_cut_against(core: &Core, army: u32) -> i32 {
    let p = core.raw_read_32(PLAYERS_POINTER, -1);
    let team = |a: u32| core.raw_read_8(p + PLAYER * a + 0x2A, -1);
    (1..=5u32)
        .filter(|&e| e != army && in_game(core, e) && team(e) != team(army))
        .map(|e| 10 * enemy_terrain_cut(core, e))
        .sum()
}

/// Dual Strike's `DoubleTerrainStars` for army `army`'s unit whose
/// terrain gives `raw` (stars x 10, 0 for an air unit: a battle unit's
/// +0x06 as `sub_08024A2C` sets it): less the enemies' cuts, not below 0,
/// then doubled in Lash's Super Power. The cuts count with CO abilities on.
pub fn ds_terrain_stars(core: &Core, army: u32, raw: i32) -> i32 {
    let cut = if abilities_on(core) {
        terrain_cut_against(core, army)
    } else {
        0
    };
    let d = (raw - cut).max(0);
    if double_terrain_stars(core, army) {
        2 * d
    } else {
        d
    }
}

// --- The table ----------------------------------------------------------------

/// tangoAW2's table: AW2's rows with Dual Strike's numbers, then Andy's
/// row for every id up to [`ROOM`].
fn build(core: &Core) -> Option<Vec<u8>> {
    crate::ds_pack::pack()?;
    let mut rows = Vec::new();
    for co in 0..AW2_COS {
        let mut row = vec![0u8; ROW as usize];
        core.raw_read_range(AW2_TABLE + ROW * co as u32, -1, &mut row);
        for mode in 0..3usize {
            let charts = 0x38 + 0x44 * mode + 0x18;
            let clear = crate::roster::moved_chart(u32_at(&row, charts));
            for w in 0..3 {
                row[charts + 4 * w..charts + 4 * w + 4].copy_from_slice(&clear.to_le_bytes());
            }
        }
        if let Some(ds) = ds_co(co) {
            let r = record(ds)?;
            row[0x0C..0x10].copy_from_slice(&(r[0x1C] as u32).to_le_bytes());
            row[0x10..0x14].copy_from_slice(&(r[0x20] as u32).to_le_bytes());
            for mode in 0..3u8 {
                let b = block(ds, mode)?;
                let at = 0x38 + 0x44 * mode as usize;
                // vision, luck, bad luck, counter, cost, capture
                for (aw2, dso) in [
                    (0x0C, 0x18),
                    (0x0E, 0x1C),
                    (0x10, 0x1E),
                    (0x12, 0x20),
                    (0x14, 0x22),
                    (0x16, 0x24),
                ] {
                    row[at + aw2..at + aw2 + 2].copy_from_slice(&b[dso..dso + 2]);
                }
            }
        }
        rows.push(row);
    }
    let andy = rows[ANDY as usize].clone();
    let mut out: Vec<u8> = rows.concat();
    for co in AW2_COS as u32..ROOM {
        let co = co as u8;
        match row_base(co) {
            Some(ds) if crate::co_new::is_new(co) => out.extend_from_slice(&new_row(&rows, &andy, co, ds)?),
            _ => out.extend_from_slice(&andy),
        }
    }
    Some(out)
}

/// Dual Strike's skills (block +0x08, +0x09) that are AW2 abilities
/// (`CoModeData.specialAbilities`): (byte, bit, AW2 bit).
const SKILLS: [(usize, u8, u32); 7] = [
    (0, 0x01, 0x01), // hidden HP
    (0, 0x02, 0x02), // deploys from cities
    (0, 0x04, 0x04), // strikes first when attacked
    (0, 0x08, 0x08), // sees into hiding places
    (0, 0x10, 0x20), // terrain stars doubled
    (0, 0x40, 0x80), // aircraft use less fuel
    (1, 0x80, 0x40), // terrain stars add firepower
];
const DEFAULT_POWER: u32 = 0x0804_43D9;
const CPU_POWER_THRESHOLD: u8 = 25;
const CPU_POWER_CHANCE: u8 = 95;
const AI_COND_START_OF_TURN: u32 = 0x0805_C1C5;

/// A new CO's row: its own music (or the CO it takes after's), the CPU's power
/// settings, Andy's movement and neutral stats, and the rest Dual Strike's.
fn new_row(rows: &[Vec<u8>], andy: &[u8], co: u8, ds: u8) -> Option<Vec<u8>> {
    use crate::co_new::*;
    let r = record(ds)?;
    let like = &rows[crate::co_new::like(co) as usize];
    let mut row = andy.to_vec();
    // Music: its own Dual Strike theme (crate::ds_music), or the like CO's.
    match crate::ds_music::song(co) {
        Some(song) => row[0x04..0x06].copy_from_slice(&song.to_le_bytes()),
        None => row[0x04..0x06].copy_from_slice(&like[0x04..0x06]),
    }
    row[0x06..0x0A].fill(0); // weather bringers
    row[0x00..0x04].copy_from_slice(&(text_id(co, T_NAME) as u32).to_le_bytes());
    row[0x0C..0x10].copy_from_slice(&(r[0x1C] as u32).to_le_bytes());
    row[0x10..0x14].copy_from_slice(&(r[0x20] as u32).to_le_bytes());
    row[0x14] = 1;
    row[0x15] = r[0x25].min(4); // property and unit style
    row[0x16] = r[0x26].clamp(1, 5); // army colour
    if crate::co_new::is_own(co) {
        // Black Hole's, not Andy's Orange Star.
        row[0x15] = 4;
        row[0x16] = 5;
    }
    if co == crate::co_new::ARIA {
        // ... except Aria: Orange Star's own colours, style and HQ (her row's country, like Nell's).
        row[0x15] = like[0x15];
        row[0x16] = like[0x16];
    }
    // The CPU's power settings: AW2's usual (a CO Power once the meter is
    // within 25% of it, 95% of the time), or none for a CO without one
    // (Von Bolt, as Sturm).
    if co == crate::co_new::ARIA {
        // (Aria has no CO Power: Sturm's settings, who has none either)
        let sturm = &rows[crate::aria::NO_COP_LIKE as usize];
        row[0x17..0x19].copy_from_slice(&sturm[0x17..0x19]);
    } else if r[0x1C] == 0 {
        row[0x17..0x19].copy_from_slice(&like[0x17..0x19]);
    } else {
        row[0x17] = CPU_POWER_THRESHOLD;
        row[0x18] = CPU_POWER_CHANCE;
    }
    row[0x1C..0x20].copy_from_slice(&AI_COND_START_OF_TURN.to_le_bytes());
    for q in 0..6u16 {
        let o = 0x20 + 2 * q as usize;
        row[o..o + 2].copy_from_slice(&text_id(co, T_QUOTES + q).to_le_bytes());
    }
    for (i, page) in [T_BIO, T_D2D, T_COP, T_SCOP].iter().enumerate() {
        row[0x2C + 2 * i..0x2E + 2 * i].copy_from_slice(&text_id(co, *page).to_le_bytes());
    }
    row[0x34..0x36].copy_from_slice(&text_id(co, T_VICTORY).to_le_bytes());
    let neutral_stats = andy[0x38 + 0x24..0x38 + 0x44].to_vec();
    let andy_charts = andy[0x38 + 0x18..0x38 + 0x24].to_vec();
    for mode in 0..3u8 {
        // Asuka's Black Insight: Sturm's movement, his row's three charts of each level as the pack has them (every terrain costs 1 for ground units, in every weather: the pack's
        // weather no longer slows anyone, `build`)
        let charts = if co == crate::co_new::ASUKA || co == crate::co_new::ARIA {
            let at = 0x38 + 0x44 * mode as usize + 0x18;
            rows[crate::asuka::MOVE_LIKE as usize][at..at + 12].to_vec()
        } else {
            andy_charts.clone()
        };
        let b = block(ds, mode)?;
        let at = 0x38 + 0x44 * mode as usize;
        let name = match mode {
            0 => 0,
            1 => text_id(co, T_COP_NAME) as u32,
            _ => text_id(co, T_SCOP_NAME) as u32,
        };
        row[at..at + 4].copy_from_slice(&name.to_le_bytes());
        // (Clone Andy's powers are Andy's: AW2's own Hyper Repair and Hyper
        // Upgrade, the row Dual Strike's record names for them)
        let power = if co == crate::co_new::CLONE_ANDY {
            u32::from_le_bytes(andy[at + 4..at + 8].try_into().unwrap())
        } else if co == crate::co_new::CRUMB || crate::es_co::is_es(co) || co == crate::co_new::ARIA {
            // (AW2's usual power procedure: the sparkle; the effect on the
            // units is the presentation row's, crate::crumb, crate::es_co)
            DEFAULT_POWER
        } else {
            crate::co_powers::power_assembly(co, mode).unwrap_or(DEFAULT_POWER)
        };
        row[at + 4..at + 8].copy_from_slice(&power.to_le_bytes());
        let mut abilities = 0u32;
        for (byte, bit, aw2) in SKILLS {
            if b[0x08 + byte] & bit != 0 {
                abilities |= aw2;
            }
        }
        row[at + 8..at + 12].copy_from_slice(&abilities.to_le_bytes());
        for (aw2, dso) in [
            (0x0C, 0x18),
            (0x0E, 0x1C),
            (0x10, 0x1E),
            (0x12, 0x20),
            (0x14, 0x22),
            (0x16, 0x24),
        ] {
            row[at + aw2..at + aw2 + 2].copy_from_slice(&b[dso..dso + 2]);
        }
        row[at + 0x18..at + 0x24].copy_from_slice(&charts);
        row[at + 0x24..at + 0x44].copy_from_slice(&neutral_stats);
        if co == crate::co_new::ASUKA || co == crate::co_new::ARIA {
            // Black Insight's (and Common Cause's) luck: Nell's day-to-day maximum roll in every level (her powers do not raise it further), no bad luck
            row[at + 0x0E..at + 0x10].copy_from_slice(&crate::asuka::LUCK.to_le_bytes());
            row[at + 0x10..at + 0x12].copy_from_slice(&0i16.to_le_bytes());
        }
        if co == crate::co_new::CRUMB {
            // His luck (Gerald's Blessing: up to 20%, no bad luck).
            row[at + 0x0E..at + 0x10].copy_from_slice(&crate::crumb::LUCK[mode as usize].to_le_bytes());
            row[at + 0x10..at + 0x12].copy_from_slice(&crate::crumb::BAD_LUCK[mode as usize].to_le_bytes());
        }
        if let Some(i) = crate::es_co::info(co) {
            // Luck, no bad luck, and the unit cost (Livia's +10%).
            row[at + 0x0E..at + 0x10].copy_from_slice(&i.luck[mode as usize].to_le_bytes());
            row[at + 0x10..at + 0x12].copy_from_slice(&0i16.to_le_bytes());
            row[at + 0x14..at + 0x16].copy_from_slice(&i.cost[mode as usize].to_le_bytes());
        }
    }
    if let Some(i) = crate::es_co::info(co) {
        row[0x0C..0x10].copy_from_slice(&i.stars.0.to_le_bytes());
        row[0x10..0x14].copy_from_slice(&i.stars.1.to_le_bytes());
    }
    if co == crate::co_new::ARIA {
        // No CO Power (0 stars, as Sturm's row), a Super Power of 7.
        row[0x0C..0x10].copy_from_slice(&crate::aria::STARS.0.to_le_bytes());
        row[0x10..0x14].copy_from_slice(&crate::aria::STARS.1.to_le_bytes());
    }
    if co == crate::co_new::ASUKA {
        row[0x0C..0x10].copy_from_slice(&crate::asuka::STARS.0.to_le_bytes());
        row[0x10..0x14].copy_from_slice(&crate::asuka::STARS.1.to_le_bytes());
    }
    if co == crate::co_new::CRUMB {
        // His meters: 3 stars for the CO Power, 6 in all for the Super Power.
        row[0x0C..0x10].copy_from_slice(&crate::crumb::STARS.0.to_le_bytes());
        row[0x10..0x14].copy_from_slice(&crate::crumb::STARS.1.to_le_bytes());
        // Black Hole's power usage by the CPU: AW2's usual.
    }
    Some(row)
}

static BUILT: OnceLock<Option<Vec<u8>>> = OnceLock::new();

fn install(core: &mut Core) -> bool {
    if core.raw_read_32(SENTINEL, -1) == MAGIC {
        return true;
    }
    let Some(table) = BUILT.get_or_init(|| build(core)) else {
        return false;
    };
    core.raw_write_range(TABLE, -1, table);
    core.raw_write_32(SENTINEL, -1, MAGIC);
    true
}

fn switch32(core: &mut Core, at: u32, want: u32) {
    if core.raw_read_32(at, -1) != want {
        core.raw_write_32(at, -1, want);
    }
}

/// Every frame: the game reads tangoAW2's table with the pack on, AW2's
/// without (idempotent; the same on both netplay peers).
pub fn tick(core: &mut Core, on: bool) {
    let on = on && install(core);
    if !on && core.raw_read_32(SENTINEL, -1) != MAGIC {
        return;
    }
    let base = if on { TABLE } else { AW2_TABLE };
    for (at, off) in POOL {
        switch32(core, at, base + off);
    }
}

// --- Traps --------------------------------------------------------------------

/// `GetCoAttackBonus` / `Defence` / `Movement` / `Range` `(co, mode, type)`:
/// Dual Strike's value, returned at their entry.
const STAT_FUNCTIONS: [(u32, usize); 4] = [
    (0x0804_30B0, FIREPOWER),
    (0x0804_3120, DEFENCE),
    (0x0804_3190, MOVE),
    (0x0804_3200, RANGE),
];

fn stat_function(core: &mut Core, field: usize) {
    if !is_on(core) || !abilities_on(core) {
        return;
    }
    let cpu = core.gba().cpu();
    let (co, mode, t, lr) = (cpu.gpr(0) as u8, cpu.gpr(1) as u8, cpu.gpr(2) as u8, cpu.gpr(14) as u32);
    if let Some(v) = stat(co, mode, t, field) {
        let cpu = core.gba_mut().cpu_mut();
        cpu.set_gpr(0, v);
        cpu.set_thumb_pc(lr & !1);
    }
}

/// `GetUnitDefenceWithCoBonus(army, type)` = 100 + the CO's defence: the
/// Com Towers' defence and Javier's against indirect attacks go on top
/// (the army kept from its entry), with CO abilities on.
const DEFENCE_ARMY: u32 = 0x0804_2CF8;
const DEFENCE_DONE: u32 = 0x0804_2D10;
const DEFENCE_SIDE: u32 = 0x0203_FFBA;
/// The unit type whose defence is being worked out (crate::co_skills).
const DEFENCE_TYPE: u32 = 0x0203_FFBB;

/// Bit 7 of [`DEFENCE_SIDE`]: the unit is an Oozium (no CO's defence).
const DEFENCE_OOZIUM: u8 = 0x80;

fn defence_army(core: &mut Core) {
    if is_on(core) {
        let cpu = core.gba().cpu();
        let (army, t) = (cpu.gpr(0) as u8, cpu.gpr(1) as u8);
        let v = if t == crate::roster::OOZIUM {
            army | DEFENCE_OOZIUM
        } else {
            army
        };
        core.raw_write_8(DEFENCE_SIDE, -1, v);
        core.raw_write_8(DEFENCE_TYPE, -1, t);
    }
}

fn defence_done(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let side = core.raw_read_8(DEFENCE_SIDE, -1);
    if side & DEFENCE_OOZIUM != 0 {
        return;
    }
    let army = side as u32;
    let mut add = 0;
    // (none with CO abilities off: Dual Strike's `Player_GetComTowerDefense`)
    if crate::com_tower::active(core) && abilities_on(core) {
        add += crate::com_tower::towers(core, army) as i32 * tower_defence(core, army);
    }
    if abilities_on(core) && core.raw_read_8(BATTLE_DISTANCE, -1) > 1 {
        add += crate::co_powers::indirect_defence(core, army);
    }
    let t = core.raw_read_8(DEFENCE_TYPE, -1);
    add += crate::co_skills::defence(core, army, t, core.raw_read_8(BATTLE_DISTANCE, -1));
    if add != 0 {
        let cpu = core.gba_mut().cpu_mut();
        let r0 = cpu.gpr(0);
        cpu.set_gpr(0, r0 + add);
    }
}

/// `sub_08024C58` storing a side's defence (terrain + 100 + CO bonuses +
/// its own) at 0x08024D12 (r1): Dual Strike caps it at 200 (0x020C34C8),
/// so no defence turns a hit into healing. AW2 has no cap and never gets
/// there; Javier's Tower of Power (+80 against indirects) does. An
/// Oozium's leaves out the power's +10 (the player's +0x28, in r8):
/// Dual Strike gives it no CO defence at all (0x020E5A58).
const DEFENCE_TOTAL: u32 = 0x0802_4D12;
const DEFENCE_CAP: i16 = 200;

fn defence_total(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let unit = core.raw_read_32(core.gba().cpu().gpr(5) as u32, -1);
    if crate::oozium::immune(core, unit) {
        let cpu = core.gba_mut().cpu_mut();
        let (r1, power) = (cpu.gpr(1), cpu.gpr(8));
        cpu.set_gpr(1, r1.wrapping_sub(power));
    }
    let cpu = core.gba_mut().cpu_mut();
    if cpu.gpr(1) as u16 as i16 > DEFENCE_CAP {
        cpu.set_gpr(1, DEFENCE_CAP as i32);
    }
}

/// `CalcDamage(attacker, defender, distance, ...)`: the distance of the
/// strike being worked out, for defences against indirect attacks.
const CALC_DAMAGE: u32 = 0x0802_4ABC;
const BATTLE_DISTANCE: u32 = 0x0203_FE51;
fn calc_damage(core: &mut Core) {
    if is_on(core) {
        let d = core.gba().cpu().gpr(2).clamp(0, 255) as u8;
        core.raw_write_8(BATTLE_DISTANCE, -1, d);
    }
}

/// `sub_08024DDC(target, attacker)` applying a hit, about to scale the
/// attacker's damage before luck (+0x14, the number the battle forecast
/// shows; r5 the attacker's shown HP, r6 the target): Dual Strike's
/// `Combatant_TakeHit` scales it by the shown HP first and the target's
/// defence after (AW2 the other way round, which can be 1 off), and stops
/// it at 999. The rest of the function (0x08024E30, r7 its 200) is AW2's.
const PREVIEW_SCALED: u32 = 0x0802_4E00;
const PREVIEW_DONE: u32 = 0x0802_4E30;
fn preview_scaled(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let cpu = core.gba().cpu();
    let (target, attacker, shown) = (cpu.gpr(6) as u32, cpu.gpr(4) as u32, cpu.gpr(5));
    let defence = core.raw_read_16(target + 0x0E, -1) as i16 as i32;
    let v = core.raw_read_16(attacker + 0x14, -1) as i16 as i32 * shown / 10;
    let v = ((200 - defence) * v / 100).min(999);
    core.raw_write_16(attacker + 0x14, -1, v as u16);
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(7, 200);
    cpu.set_thumb_pc(PREVIEW_DONE);
}

/// `sub_08043304(battle unit)`, a side's terrain defence, at its return (r4
/// the battle unit, whose +0x06 still holds the stars x 10, 0 for an air
/// unit, until `sub_08024C58` stores this result there): Dual Strike's
/// `DoubleTerrainStars` ([`ds_terrain_stars`]): less every enemy's star cut
/// first, then doubled in Lash's Super Power (AW2 doubled first, and
/// tangoAW2 took off the battle opponent's cut alone after).
const TERRAIN_DEFENCE_DONE: u32 = 0x0804_3344;
const BATTLE_ATTACKER: u32 = 0x0300_13D0;
const BATTLE_DEFENDER: u32 = 0x0300_13B0;
const UNITS_POINTER: u32 = 0x0849_9594;
const UNIT: u32 = 12;

/// The army of the unit a battle unit stands for.
pub fn battle_army(core: &Core, bu: u32) -> u32 {
    let unit = core.raw_read_32(bu, -1);
    let units = core.raw_read_32(UNITS_POINTER, -1);
    crate::five::army_of_index(core, unit.wrapping_sub(units) / UNIT)
}

fn terrain_defence_done(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let bu = core.gba().cpu().gpr(4) as u32;
    if bu != BATTLE_ATTACKER && bu != BATTLE_DEFENDER {
        return;
    }
    let raw = core.raw_read_16(bu + 6, -1) as i16 as i32;
    let v = ds_terrain_stars(core, battle_army(core, bu), raw);
    core.gba_mut().cpu_mut().set_gpr(0, v);
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    let mut t: Vec<(u32, Box<dyn Fn(&mut Core)>)> = Vec::new();
    for (at, field) in STAT_FUNCTIONS {
        t.push((at, Box::new(move |core: &mut Core| stat_function(core, field))));
    }
    t.push((DEFENCE_ARMY, Box::new(defence_army)));
    t.push((DEFENCE_DONE, Box::new(defence_done)));
    t.push((TERRAIN_DEFENCE_DONE, Box::new(terrain_defence_done)));
    t.push((CALC_DAMAGE, Box::new(calc_damage)));
    t.push((DEFENCE_TOTAL, Box::new(defence_total)));
    t.push((PREVIEW_SCALED, Box::new(preview_scaled)));
    t
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn room() {
        assert!(TABLE + ROW * ROOM <= SENTINEL);
        assert_eq!(DS_IDS.iter().filter(|d| d.is_none()).count(), 1);
    }
}
