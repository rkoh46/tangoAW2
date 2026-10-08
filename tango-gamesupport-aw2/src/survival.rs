//! Survival, Dual Strike's mode of eleven maps fought in a row against the
//! computer on one budget, with the Dual Strike pack.
//!
//! Dual Strike (as read from its code, see [`crate::survival_maps`] for the
//! data): three kinds, each a fixed run of eleven of its own Survival maps.
//! **Money**: 500,000 G for the whole run and no income (properties, joins,
//! Colin's and Sasha's powers earn nothing); the run is lost the moment the
//! funds reach 0 (`sub_020EA944`). **Turn**: 99 days for the whole run; each
//! cleared map costs its days less one (`sub_020EA87C`), and a map is lost
//! when its day passes what is left. **Time**: 25 minutes, counted only on
//! the player's own turns (whole seconds are taken off per map). Points are
//! the battles' scores added up (at most 9999), plus a bonus for what is
//! left at the end (`sub_020EB024`); the final rank is S/A/B/C by what is
//! left (`sub_020EAD98`); the best leftover per kind is kept with its COs
//! (`sub_020EAE84`). The COs are picked once and kept for the whole run
//! (the survival state's CO pair is copied into the player at every map
//! start, `sub_020EACC4`). Each map brings its own fog, weather and look,
//! and the computer's CO.
//!
//! Here: a "Survival" entry on the Select Mode wheel ([`crate::mode_menu`])
//! opens the War Room's own screens with Survival's maps: SELECT MAP lists
//! Money, Turn and Time Survival and is drawn as Dual Strike's course screen
//! ([`crate::survival_ui`]), then the War Room's CO screen, the battle, the
//! War Room's results and save; back on SELECT MAP the next map of the run is
//! the only one listed (its CO screen offers only the run's CO), until the
//! run is cleared or lost and its results are shown there. In battle the
//! budget left is shown at the top of the screen. AW2 has no tag battles:
//! the run keeps one CO.
//!
//! - Maps: ids 0xC9..0xCB are the three runs' entries (the first map of
//!   each, named after the kind), 0xCC.. the 33 maps; their headers are in
//!   a copy of the map table with room for 0x100 ids ([`TABLE`]; with the
//!   pack the game reads it instead of [`crate::five_map`]'s), listed on a
//!   tab of their own ([`TAB`]) that the War Room shows while Survival is
//!   on (the War Room's tab byte, `0x08090EF2`).
//! - The War Room keeps its records by `id - 0x6C`; while Survival is on its
//!   record readers and writer look at a zeroed block of ours ([`ROWS`]).
//! - State: [`STATE`] in EWRAM; records in the profile the game saves
//!   (`0x0200C435..0x0200C43F`, eleven bytes no code of the game touches:
//!   see [`Records`]).
//! - The Champion courses (Dual Strike's kinds 3..5): the same three lists
//!   of eleven maps, endless (the list starts over after the eleventh map),
//!   on a larger budget (30:00, 600,000 G, 120 days), over when the budget
//!   is out or a map is lost; their record is the maps cleared, their rank
//!   goes by that count too (`sub_020EAD98`), their bonus is
//!   [`maps::champion_bonus`]. Dual Strike sells them in its shop (1000
//!   medals each once the basic course is cleared); tangoAW2 has no shop, so
//!   a Champion course is open once its basic course has been cleared (a
//!   record of the basic course exists). Each is a list entry of its own
//!   ([`CHAMPION_IDS`]) after the three basic ones, shown only when open.

use mgba::core::Core;
use std::sync::OnceLock;

use crate::survival_maps::{self as maps, Kind, MAPS_PER_RUN};

// --- Where things are ------------------------------------------------------

/// tangoAW2's copy of the map table (0x100 ids) and the Survival maps.
pub const TABLE: u32 = 0x08E0_0000;
#[cfg(test)]
const TABLE_IDS: u32 = 0x100;
const MAP_DATA: u32 = 0x08E0_8000;
const MAP_DATA_SIZE: u32 = 0x800;
const STRINGS: u32 = 0x08E3_0000;
const STRING_SIZE: u32 = 0x40;
const SENTINEL: u32 = 0x08E0_7FFC;
const MAGIC: u32 = 0x3256_5344; // "DSV2": headers with the structures' pictures

/// Map ids: the three entries (Money, Turn, Time), then the maps.
pub const FIRST_ID: u8 = 0xC9;
const ENTRY_IDS: [u8; 3] = [0xC9, 0xCA, 0xCB];
/// The Champion courses' entries (Money, Turn, Time), listed after the
/// three basic ones once the basic course has been cleared. 0xF0 and up
/// belong to the campaigns' maps ([`crate::campaign_model::MAP_ID`]).
pub const CHAMPION_IDS: [u8; 3] = [0xED, 0xEE, 0xEF];
const MAPS_FROM: u8 = 0xCC;
/// The tab Survival's maps are listed on.
pub const TAB: u16 = 0x0A;
/// The War Room's tab in the mode -> tab table (`BuildMapListForMode`).
const WAR_ROOM_TAB: u32 = 0x0809_0EF2;
const WAR_ROOM_TAB_GAME: u8 = 7;

/// Text ids from 0x7172 read their pointer from 0x0862D000 (free ROM, past
/// [`crate::co_new`]'s); see [`crate::five_map`] for why that works.
const TEXT_TABLE: u32 = 0x0861_0A38;
pub const TEXT_BASE: u16 = 0x7172;
pub const T_HELP: u16 = 0;
const T_KINDS: u16 = 1; // three
// 4: spare
const T_MAPS: u16 = 5; // 33
const T_CHAMPIONS: u16 = 38; // three

/// The War Room record table (`id - 0x6C` rows of 0x14) and the
/// literal-pool words of its readers and writer.
const RECORDS: u32 = 0x0200_C078;
const RECORD_POOLS: [u32; 5] = [0x0808_759C, 0x0808_7664, 0x0808_7B18, 0x0808_7C6C, 0x0801_77E4];

// --- RAM ---------------------------------------------------------------------

pub const STATE: u32 = 0x0203_FA00;
const ON: u32 = STATE; // 1 while Survival's War Room is open
const KIND: u32 = STATE + 1;
/// 1 on a Champion course (the kind byte stays the basic course's kind).
pub(crate) const CHAMPION: u32 = STATE + 0x21;
pub(crate) const STAGE: u32 = STATE + 2; // maps cleared
pub(crate) const PHASE: u32 = STATE + 3;
pub(crate) const LEFT: u32 = STATE + 4;
const BUDGET: u32 = STATE + 8;
pub(crate) const POINTS: u32 = STATE + 0x0C;
const TIME: u32 = STATE + 0x10; // frames of the player's turns on this map
const FUNDS_CAP: u32 = STATE + 0x14;
const CO: u32 = STATE + 0x18;
pub(crate) const MENU_PICKED: u32 = STATE + 0x19;
pub(crate) const BONUS: u32 = STATE + 0x1C;
pub(crate) const RANK: u32 = STATE + 0x20;
const LAST_SCORE: u32 = STATE + 0x22;
const OUT_SET: u32 = STATE + 0x24;
/// A zeroed block the War Room's record code reads while Survival is on:
/// rows for ids FIRST_ID..=0xEC.
const ROWS: u32 = STATE + 0x40;
const ROW: u32 = 0x14;
const ROWS_LEN: u32 = ROW * 0x24;

/// PHASE: choosing a kind; between maps; in a battle; cleared; lost.
pub(crate) const CHOOSING: u8 = 0;
pub(crate) const BETWEEN: u8 = 1;
pub(crate) const PLAYING: u8 = 2;
pub(crate) const CLEARED: u8 = 3;
pub(crate) const LOST: u8 = 4;

/// Records, in the profile the game saves (see [`Records`]): the eleven
/// bytes `0x0200C435..=0x0200C43F`.
pub(crate) const PROFILE_RECORDS: u32 = 0x0200_C435;
pub(crate) const PROFILE_RECORDS_LEN: usize = 11;
/// The first byte of the first layout (0.5.0..0.5.2): three bytes per kind
/// (Time, Money, Turn), 10 bytes in all.
const MAGIC_V1: u8 = 0xD5;
/// The first byte of the layout with the Champion courses.
const MAGIC_V2: u8 = 0xD6;

// --- The game ------------------------------------------------------------

const PLAYST: u32 = 0x0300_3FC0;
const MAP_ID: u32 = PLAYST + 0x02;
const PROPERTY_FUNDS: u32 = PLAYST + 0x28;
const WEATHER: u32 = PLAYST + 0x2C;
const WEATHER_MODE: u32 = PLAYST + 0x2D;
const NEXT_WEATHER: u32 = PLAYST + 0x2E;
const DEFAULT_WEATHER: u32 = PLAYST + 0x2F;
const PLAYST_CO: u32 = PLAYST + 0x3D;
const FOG: u32 = PLAYST + 0x0D;
const DAY: u32 = 0x0300_4080;
const CURRENT_ARMY: u32 = 0x0300_33EC;
const MAIN_CALLBACK: u32 = 0x0300_0000;
const MAP_CALLBACK: u32 = 0x0802_2049;
const BATTLE_SCENE: u32 = 0x0300_0004;
/// Player blocks: funds +0, spent +4, defeated +0x14, CO +0x1D, yielded
/// +0x31, total score +0x38.
const P_FUNDS: u32 = 0x00;
const P_DEFEATED: u32 = 0x14;
const P_CO: u32 = 0x1D;
const P_YIELD: u32 = 0x31;
const P_SCORE: u32 = 0x38;

const PROCS: u32 = 0x0200_D610;
const PROCS_END: u32 = 0x0200_E418;
const PROC_SIZE: u32 = 0x6C;
/// `ProcScr_MainMenu` (the Select Mode wheel) and the War Room's SELECT
/// MAP (`PreviewMap`) and CO screen (`WarRoomMapSelected`).
/// The wheel's proc (`ProcScr_MainMenuC1`), running while Select Mode is up.
const MAIN_MENU: u32 = 0x0861_6990;
const SELECT_MAP: u32 = 0x0861_6C54;

fn running(core: &Core, script: u32) -> bool {
    (PROCS..PROCS_END)
        .step_by(PROC_SIZE as usize)
        .any(|p| core.raw_read_32(p, -1) == script)
}

/// Survival's War Room is open (a run being played).
pub fn on(core: &Core) -> bool {
    core.raw_read_8(ON, -1) == 1
}

fn player(core: &Core, army: u32) -> u32 {
    crate::five::players(core) + 0x3C * army
}

// --- The maps in the ROM image --------------------------------------------

struct Built {
    writes: Vec<(u32, Vec<u8>)>,
    /// Header address per id, for the per-frame tab and name fields.
    names: Vec<(u8, u16)>,
}

static BUILT: OnceLock<Option<Built>> = OnceLock::new();

fn text_slot(k: u16) -> u32 {
    TEXT_TABLE + 4 * (TEXT_BASE + k) as u32
}

fn string_at(k: u16) -> u32 {
    STRINGS + STRING_SIZE * k as u32
}

fn put_text(w: &mut Vec<(u32, Vec<u8>)>, k: u16, s: &str) {
    let mut b = s.as_bytes().to_vec();
    b.truncate(STRING_SIZE as usize - 1);
    b.push(0);
    w.push((string_at(k), b));
    w.push((text_slot(k), string_at(k).to_le_bytes().to_vec()));
}

fn header(map: &maps::Map, tiles: u32, units: u32, name: u16) -> [u8; 0x5C] {
    let mut h = [0u8; 0x5C];
    let w32 = |h: &mut [u8], at: usize, v: u32| h[at..at + 4].copy_from_slice(&v.to_le_bytes());
    let w16 = |h: &mut [u8], at: usize, v: u16| h[at..at + 2].copy_from_slice(&v.to_le_bytes());
    w32(&mut h, 0x00, tiles);
    // The 4x4 structure's picture (none: the game would load nothing and
    // draw whatever OBJ VRAM holds there).
    w32(&mut h, 0x10, map.structure.map_or(0, |s| s.aw2_picture()));
    w16(&mut h, 0x14, TEXT_BASE + name);
    h[0x16] = 1;
    h[0x17] = map.fog as u8;
    h[0x18] = map.armies;
    w16(&mut h, 0x1A, crate::five_map::HIDDEN_TAB);
    w16(&mut h, 0x1C, 1);
    w16(&mut h, 0x1E, 1);
    w16(&mut h, 0x20, map.speed_days);
    w16(&mut h, 0x22, map.speed_days);
    h[0x26] = 0xFF;
    w32(&mut h, 0x2C, tiles);
    w32(&mut h, 0x34, units);
    h[0x3C] = 0xFF;
    for k in 0..3 {
        h[0x3D + k] = if (k as u8) + 2 <= map.armies {
            map.cos[k].unwrap_or(1)
        } else {
            0
        };
    }
    h[0x40..0x44].copy_from_slice(&map.colours);
    h[0x44..0x48].copy_from_slice(&[1, 2, 3, 4]);
    for i in 0..4 {
        h[0x48 + 4 * i..0x4C + 4 * i].copy_from_slice(&[0xFF, 0xFF, 0, 0]);
    }
    h
}

/// A map's tiles as the game loads them (LZ77 of width, height, tiles) and
/// its units (12-byte records; FE army, FF end).
/// Each pre-deployed unit's AI byte (record +9): 4, the one tangoAW2's
/// Versus maps use, under which the computer moves every unit (with 0, as
/// many campaign units have, it keeps some where they stand).
const AI: u8 = 4;

fn map_blobs(map: &maps::Map) -> (Vec<u8>, Vec<u8>) {
    let mut raw = vec![map.width, map.height];
    for t in &map.tiles {
        raw.extend_from_slice(&t.to_le_bytes());
    }
    let mut lz = crate::lz77::compress(&raw);
    while lz.len() % 4 != 0 {
        lz.push(0);
    }
    let mut units = Vec::new();
    for army in 1..=4u8 {
        let mine: Vec<&maps::Unit> = map.units.iter().filter(|u| u.army == army).collect();
        if mine.is_empty() {
            continue;
        }
        units.extend_from_slice(&[0xFE, army, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
        for u in mine {
            units.extend_from_slice(&[u.x, u.y, u.kind, 0, u.hp, u.ammo, u.fuel, 0, 0, AI, 0, 0]);
        }
    }
    units.extend_from_slice(&[0xFF; 1]);
    units.extend_from_slice(&[0; 11]);
    (lz, units)
}

fn build() -> Option<Built> {
    let s = maps::survival()?;
    let mut writes = Vec::new();
    let mut names = Vec::new();
    put_text(&mut writes, T_HELP, &s.help);
    for k in Kind::ALL {
        put_text(&mut writes, T_KINDS + entry_index(k) as u16, k.name());
        put_text(&mut writes, T_CHAMPIONS + entry_index(k) as u16, k.champion_name());
    }
    for (k, map) in s.maps.iter().enumerate() {
        put_text(&mut writes, T_MAPS + k as u16, &map.name);
        let (lz, units) = map_blobs(map);
        let at = MAP_DATA + MAP_DATA_SIZE * k as u32;
        assert!(lz.len() + units.len() <= MAP_DATA_SIZE as usize, "{}", map.name);
        let units_at = at + lz.len() as u32;
        let id = MAPS_FROM + k as u8;
        writes.push((TABLE + 0x5C * id as u32, header(map, at, units_at, T_MAPS + k as u16).to_vec()));
        writes.push((at, lz));
        writes.push((units_at, units));
        names.push((id, T_MAPS + k as u16));
    }
    for k in Kind::ALL {
        let first = s.run(k).maps[0];
        let id = ENTRY_IDS[entry_index(k)];
        let at = MAP_DATA + MAP_DATA_SIZE * first as u32;
        let (lz, _) = map_blobs(&s.maps[first]);
        let units_at = at + lz.len() as u32;
        let name = T_KINDS + entry_index(k) as u16;
        writes.push((TABLE + 0x5C * id as u32, header(&s.maps[first], at, units_at, name).to_vec()));
        names.push((id, name));
        // The Champion course starts on the same map.
        let id = CHAMPION_IDS[entry_index(k)];
        let name = T_CHAMPIONS + entry_index(k) as u16;
        writes.push((TABLE + 0x5C * id as u32, header(&s.maps[first], at, units_at, name).to_vec()));
        names.push((id, name));
    }
    Some(Built { writes, names })
}

/// Money, Turn, Time: the order of the entries in the list.
fn entry_index(k: Kind) -> usize {
    match k {
        Kind::Money => 0,
        Kind::Turn => 1,
        Kind::Time => 2,
    }
}

pub(crate) fn entry_kind_of(id: u8) -> Option<(Kind, bool)> {
    entry_kind(id)
}

/// The course an entry id starts: its kind and whether it is the Champion
/// course.
fn entry_kind(id: u8) -> Option<(Kind, bool)> {
    if let Some(i) = ENTRY_IDS.iter().position(|&e| e == id) {
        return Some((Kind::ALL[i], false));
    }
    CHAMPION_IDS.iter().position(|&e| e == id).map(|i| (Kind::ALL[i], true))
}

/// The last id the map list should walk to while Survival is on (the
/// Champion entries come after the maps).
pub fn last_listed_id(core: &Core) -> Option<u8> {
    let n = maps::survival()?.maps.len() as u8;
    (core.raw_read_8(ON, -1) == 1).then_some((MAPS_FROM + n - 1).max(CHAMPION_IDS[2]))
}

fn installed(core: &Core) -> bool {
    core.raw_read_32(SENTINEL, -1) == MAGIC
}

fn install(core: &mut Core) -> bool {
    let Some(built) = BUILT.get_or_init(build).as_ref() else { return false };
    if !installed(core) {
        // The map table as crate::five_map leaves it (ids 0..0xC8), with room.
        let mut table = vec![0u8; (crate::five_map::ENTRY * crate::five_map::MAP_IDS) as usize];
        core.raw_read_range(crate::five_map::MAP_TABLE, -1, &mut table);
        core.raw_write_range(TABLE, -1, &table);
        for (at, b) in &built.writes {
            core.raw_write_range(*at, -1, b);
        }
        core.raw_write_32(SENTINEL, -1, MAGIC);
    }
    true
}

/// Every frame, before [`crate::five_map::show_maps`]: with the pack the
/// game reads tangoAW2's larger map table, without it five_map's.
pub fn tick_tables(core: &mut Core, on: bool) {
    let on = on && install(core);
    if on {
        crate::five_map::use_table(core, TABLE);
    } else if installed(core) {
        crate::five_map::use_table(core, crate::five_map::MAP_TABLE);
    }
}

// --- Per frame ----------------------------------------------------------------

/// The run's kind.
pub(crate) fn kind_now(core: &Core) -> Kind {
    kind(core)
}

fn kind(core: &Core) -> Kind {
    Kind::from_u8(core.raw_read_8(KIND, -1)).unwrap_or(Kind::Money)
}

/// The run is on a Champion course.
pub(crate) fn champion_now(core: &Core) -> bool {
    core.raw_read_8(CHAMPION, -1) == 1
}

/// The map id of map `k` of the run (a Champion course's list starts over
/// after its eleventh map).
fn run_map_id(kind: Kind, champion: bool, k: usize) -> Option<u8> {
    let s = maps::survival()?;
    if k == 0 {
        let ids = if champion { &CHAMPION_IDS } else { &ENTRY_IDS };
        return Some(ids[entry_index(kind)]);
    }
    let k = if champion { k % MAPS_PER_RUN } else { k };
    Some(MAPS_FROM + *s.run(kind).maps.get(k)? as u8)
}

/// The run's map for map id `id`, if it is one of ours.
fn map_of(id: u8) -> Option<&'static maps::Map> {
    let s = maps::survival()?;
    if let Some((k, _)) = entry_kind(id) {
        return s.maps.get(s.run(k).maps[0]);
    }
    s.maps.get(id.checked_sub(MAPS_FROM)? as usize)
}

pub fn is_survival_map(id: u8) -> bool {
    id >= FIRST_ID && map_of(id).is_some()
}

fn set16(core: &mut Core, at: u32, v: u16) {
    if core.raw_read_16(at, -1) != v {
        core.raw_write_16(at, -1, v);
    }
}

fn set8(core: &mut Core, at: u32, v: u8) {
    if core.raw_read_8(at, -1) != v {
        core.raw_write_8(at, -1, v);
    }
}

/// The tabs and names of our maps, as the run stands.
fn list(core: &mut Core) {
    let Some(built) = BUILT.get().and_then(|b| b.as_ref()) else { return };
    let on = core.raw_read_8(ON, -1) == 1;
    let phase = core.raw_read_8(PHASE, -1);
    let stage = core.raw_read_8(STAGE, -1) as usize;
    let next = (on && (phase == BETWEEN || phase == PLAYING))
        .then(|| run_map_id(kind(core), champion_now(core), stage))
        .flatten();
    let records = read_records(core);
    for &(id, name) in &built.names {
        let shown = if !on {
            false
        } else if phase == CHOOSING || phase == CLEARED || phase == LOST {
            // A Champion course only once its basic course is cleared.
            entry_kind(id).is_some_and(|(k, champion)| !champion || records.basic[k as usize].is_some())
        } else {
            Some(id) == next
        };
        let h = TABLE + 0x5C * id as u32;
        set16(core, h + 0x1A, if shown { TAB } else { crate::five_map::HIDDEN_TAB });
        set16(core, h + 0x14, TEXT_BASE + name);
    }
}

/// Every frame with the pack on: Survival's state, the War Room switches,
/// the battle's budget. Returns the keys the game sees.
pub fn tick(core: &mut Core, ds: bool, keys: u32, prev: u32) -> u32 {
    let mut keys = keys;
    if !ds || !installed(core) {
        if core.raw_read_8(ON, -1) != 0 {
            core.raw_write_8(ON, -1, 0);
        }
        set8(core, WAR_ROOM_TAB, WAR_ROOM_TAB_GAME);
        return keys;
    }
    // Picked on Select Mode: Survival's War Room opens. Back on Select
    // Mode otherwise: it is closed (a run in progress is left).
    if running(core, MAIN_MENU) {
        if core.raw_read_8(MENU_PICKED, -1) != 0 {
            set8(core, ON, 1);
            set8(core, PHASE, CHOOSING);
            // SELECT MAP opens on its first row (the War Room's own row
            // may be past the end of Survival's three).
            core.raw_write_32(LIST_FIRST, -1, 0);
            core.raw_write_32(LIST_CURSOR, -1, 0);
        } else if core.raw_read_8(ON, -1) != 0 {
            core.raw_write_8(ON, -1, 0);
            core.raw_write_8(PHASE, -1, CHOOSING);
        }
    } else if core.raw_read_8(MENU_PICKED, -1) != 0 {
        core.raw_write_8(MENU_PICKED, -1, 0);
    }
    let on = core.raw_read_8(ON, -1) == 1;
    set8(core, WAR_ROOM_TAB, if on { TAB as u8 } else { WAR_ROOM_TAB_GAME });
    let rows = if on { ROWS.wrapping_sub(ROW * (FIRST_ID as u32 - 0x6C)) } else { RECORDS };
    for at in RECORD_POOLS {
        if core.raw_read_32(at, -1) != rows {
            core.raw_write_32(at, -1, rows);
        }
    }
    list(core);
    // SELECT MAP in Dual Strike's look (crate::survival_ui).
    keys = if on { crate::survival_ui::tick(core, keys, prev) } else { crate::survival_ui::off(core, keys) };
    if !on {
        return keys;
    }
    if core.raw_read_32(ROWS, -1) != 0 || core.raw_read_32(ROWS + ROW * 3, -1) != 0 {
        core.raw_write_range(ROWS, -1, &vec![0u8; ROWS_LEN as usize]);
    }
    let phase = core.raw_read_8(PHASE, -1);
    match phase {
        PLAYING => battle_frame(core),
        BETWEEN => {
            // The run's CO is kept: whatever the CO screen picks.
            let co = core.raw_read_8(CO, -1);
            set8(core, PLAYST_CO + 1, co);
        }
        CLEARED | LOST if running(core, SELECT_MAP) => {
            // The results panel: A or B closes it (and is not seen by the list).
            let pressed = keys & !prev;
            if pressed & 3 != 0 {
                core.raw_write_8(PHASE, -1, CHOOSING);
            }
            keys &= !3;
        }
        _ => {}
    }
    keys
}

fn battle_frame(core: &mut Core) {
    if core.raw_read_32(BATTLE_SCENE, -1) == 0 {
        return;
    }
    let p1 = player(core, 1);
    let left = core.raw_read_32(LEFT, -1);
    let out = match kind(core) {
        Kind::Money => {
            // No income: anything that adds funds is taken back.
            let funds = core.raw_read_32(p1 + P_FUNDS, -1);
            let cap = core.raw_read_32(FUNDS_CAP, -1);
            if funds > cap {
                core.raw_write_32(p1 + P_FUNDS, -1, cap);
            } else if funds < cap {
                core.raw_write_32(FUNDS_CAP, -1, funds);
            }
            set16(core, PROPERTY_FUNDS, 0);
            core.raw_read_32(p1 + P_FUNDS, -1) == 0
        }
        Kind::Turn => core.raw_read_16(DAY, -1) as u32 > left,
        Kind::Time => {
            if core.raw_read_8(CURRENT_ARMY, -1) == 1 {
                let t = core.raw_read_32(TIME, -1) + 1;
                core.raw_write_32(TIME, -1, t);
            }
            core.raw_read_32(TIME, -1) / 60 >= left / 60
        }
    };
    if out && core.raw_read_8(OUT_SET, -1) == 0 {
        // Out of budget: the player's army yields (defeated at the game's
        // next rules check, as Yield does).
        core.raw_write_8(OUT_SET, -1, 1);
        core.raw_write_8(p1 + P_YIELD, -1, 1);
    }
}

// --- Map start and end --------------------------------------------------------

/// At every map start ([`crate::sandstorm`]'s trap): a Survival map starts
/// the run (an entry) or its next map, with its own rules.
pub fn map_start(core: &mut Core) {
    if core.raw_read_8(ON, -1) != 1 || !crate::ds_weather::is_on(core) {
        return;
    }
    let id = core.raw_read_8(MAP_ID, -1);
    let Some(map) = map_of(id) else { return };
    let phase = core.raw_read_8(PHASE, -1);
    if let Some((k, champion)) = entry_kind(id) {
        if phase != CHOOSING && phase != CLEARED && phase != LOST {
            return;
        }
        let Some(s) = maps::survival() else { return };
        let budget = if champion { s.run(k).champion_budget } else { s.run(k).budget };
        core.raw_write_8(KIND, -1, k as u8);
        core.raw_write_8(CHAMPION, -1, champion as u8);
        core.raw_write_8(STAGE, -1, 0);
        core.raw_write_32(BUDGET, -1, budget);
        core.raw_write_32(LEFT, -1, budget);
        core.raw_write_32(POINTS, -1, 0);
        core.raw_write_8(CO, -1, core.raw_read_8(PLAYST_CO + 1, -1));
    } else if phase != BETWEEN
        || run_map_id(kind(core), champion_now(core), core.raw_read_8(STAGE, -1) as usize) != Some(id)
    {
        return;
    }
    core.raw_write_8(PHASE, -1, PLAYING);
    core.raw_write_32(TIME, -1, 0);
    core.raw_write_8(OUT_SET, -1, 0);
    // The run's CO.
    let co = core.raw_read_8(CO, -1);
    core.raw_write_8(PLAYST_CO + 1, -1, co);
    core.raw_write_8(player(core, 1) + P_CO, -1, co);
    // Weather: 0 clear, 1 snow, 2 rain, 3 sandstorm (fixed weather with
    // clear as the default, crate::sandstorm).
    let (mode, w) = match map.weather {
        1 => (3, 1),
        2 => (3, 2),
        3 => (3, 0),
        _ => (0, 0),
    };
    core.raw_write_8(WEATHER_MODE, -1, mode);
    core.raw_write_8(DEFAULT_WEATHER, -1, w);
    core.raw_write_8(WEATHER, -1, w);
    core.raw_write_8(NEXT_WEATHER, -1, w);
    // Fog: the War Room sets gPlaySt's fog from the header of the map it
    // started with (`sub_080346FC`, before a map is picked), so it is set here.
    core.raw_write_8(FOG, -1, map.fog as u8);
    // Dual Strike's look: Normal (AW2's), Snow, Desert or Wasteland.
    crate::wasteland::set_ds_look(core, map.look);
    if kind(core) == Kind::Money {
        let left = core.raw_read_32(LEFT, -1);
        core.raw_write_32(player(core, 1) + P_FUNDS, -1, left);
        core.raw_write_32(FUNDS_CAP, -1, left);
        core.raw_write_16(PROPERTY_FUNDS, -1, 0);
    }
}

/// `EndOfGame_Finish` (every battle's end, before the War Room's save
/// prompt): the run goes on, is cleared, or is lost.
pub const END_OF_GAME: u32 = 0x0803_832C;
fn end_of_game(core: &mut Core) {
    crate::co_skills::battle_end(core);
    if core.raw_read_8(ON, -1) != 1 || core.raw_read_8(PHASE, -1) != PLAYING {
        return;
    }
    let id = core.raw_read_8(MAP_ID, -1);
    if !is_survival_map(id) {
        return;
    }
    let p1 = player(core, 1);
    let won = core.raw_read_16(p1 + P_DEFEATED, -1) == 0 && core.raw_read_8(p1 + P_YIELD, -1) == 0;
    let k = kind(core);
    let champion = champion_now(core);
    let left = core.raw_read_32(LEFT, -1);
    if !won {
        core.raw_write_8(PHASE, -1, LOST);
        core.raw_write_32(LEFT, -1, 0);
        core.raw_write_32(BONUS, -1, 0);
        core.raw_write_8(RANK, -1, 0);
        if champion {
            // A Champion run only ends this way: its record, rank and bonus
            // are for the maps cleared (`sub_020D5E58` saves it as the run is
            // lost, `sub_020EB024` works the bonus out).
            let cleared = core.raw_read_8(STAGE, -1) as u32;
            let bonus = maps::champion_bonus(cleared);
            core.raw_write_32(BONUS, -1, bonus);
            let points = (core.raw_read_32(POINTS, -1) + bonus).min(maps::MAX_POINTS);
            core.raw_write_32(POINTS, -1, points);
            core.raw_write_8(RANK, -1, maps::champion_rank(cleared));
            save_champion(core, k, cleared);
        }
        return;
    }
    let cost = match k {
        Kind::Money => left.saturating_sub(core.raw_read_32(p1 + P_FUNDS, -1)),
        Kind::Turn => (core.raw_read_16(DAY, -1) as u32).saturating_sub(1),
        Kind::Time => core.raw_read_32(TIME, -1) / 60 * 60,
    };
    let left = left.saturating_sub(cost);
    core.raw_write_32(LEFT, -1, left);
    let score = core.raw_read_16(p1 + P_SCORE, -1) as u32;
    core.raw_write_16(LAST_SCORE, -1, score as u16);
    let points = (core.raw_read_32(POINTS, -1) + score).min(maps::MAX_POINTS);
    core.raw_write_32(POINTS, -1, points);
    let stage = core.raw_read_8(STAGE, -1).saturating_add(1);
    core.raw_write_8(STAGE, -1, stage);
    if !champion && stage as usize >= MAPS_PER_RUN {
        let bonus = maps::leftover_points(k, left);
        core.raw_write_32(BONUS, -1, bonus);
        core.raw_write_32(POINTS, -1, (points + bonus).min(maps::MAX_POINTS));
        let rank = maps::rank(k, left);
        core.raw_write_8(RANK, -1, rank);
        save_record(core, k, left);
        core.raw_write_8(PHASE, -1, CLEARED);
    } else {
        core.raw_write_8(PHASE, -1, BETWEEN);
    }
    // SELECT MAP lists only the next map now: its cursor starts at the top
    // (it keeps the row last picked, which may be past the end).
    core.raw_write_32(LIST_FIRST, -1, 0);
    core.raw_write_32(LIST_CURSOR, -1, 0);
}

/// `SetMapPlayed` (id r0): the "played" bits stop at id 0xBF; Survival's
/// ids keep out of the bytes after them.
const SET_MAP_PLAYED: u32 = 0x0803_CA28;
fn set_map_played(core: &mut Core) {
    let id = core.gba().cpu().gpr(0) as u32;
    // The played bits stop at 0xBF: Survival's maps and the DS Campaign's
    // (crate::ds_campaign) are left out.
    if id >= FIRST_ID as u32 && (core.raw_read_8(ON, -1) == 1 || crate::ds_campaign::active(core)) {
        let lr = core.gba().cpu().gpr(14) as u32;
        core.gba_mut().cpu_mut().set_thumb_pc(lr & !1);
    }
}

/// `DrawMapList(first, count, top)`: the War Room draws `count` rows
/// whatever the list holds (it always has more than seven maps); Survival's
/// list has fewer, so the rows past its end are left out, as Versus does.
const DRAW_MAP_LIST: u32 = 0x0808_6A58;
const MAP_LIST_LAST: u32 = 0x0202_7FAB;
fn draw_map_list(core: &mut Core) {
    if core.raw_read_8(ON, -1) != 1 {
        return;
    }
    let cpu = core.gba().cpu();
    let (first, count) = (cpu.gpr(0) as u32, cpu.gpr(1) as u32);
    let n = core.raw_read_8(MAP_LIST_LAST, -1) as u32 + 1;
    if first + count > n {
        core.gba_mut().cpu_mut().set_gpr(1, n.saturating_sub(first) as i32);
    }
}

/// `WarRoomMapSelected`'s first call (the CO screen starting; its CO list
/// is built by then): from the second map on, the run's CO is kept (Dual
/// Strike's COs are picked once a run), so the screen offers only that CO,
/// in its own army's group, as the Campaign's restricted CO screens do
/// (`AddCoSelectGroup*`: groups, their sizes and colours, the CO ids).
const CO_SCREEN: u32 = 0x0807_C588;
const CO_GROUPS: u32 = 0x0300_5944;
const CO_GROUP_SIZES: u32 = 0x0300_5948;
const CO_GROUP_COLOURS: u32 = 0x0300_5958;
const CO_LIST: u32 = 0x0300_58E0;
fn co_screen(core: &mut Core) {
    if core.raw_read_8(ON, -1) != 1 || core.raw_read_8(PHASE, -1) != BETWEEN || core.raw_read_8(STAGE, -1) == 0 {
        return;
    }
    let co = core.raw_read_8(CO, -1);
    let groups = core.raw_read_32(CO_GROUPS, -1).min(8);
    let mut at = 0;
    let mut colour = None;
    for g in 0..groups {
        let n = core.raw_read_8(CO_GROUP_SIZES + g, -1) as u32;
        if (0..n).any(|k| core.raw_read_8(CO_LIST + at + k, -1) == co) {
            colour = Some(core.raw_read_8(CO_GROUP_COLOURS + g, -1));
        }
        at += n;
    }
    let Some(colour) = colour else { return };
    core.raw_write_32(CO_GROUPS, -1, 1);
    core.raw_write_8(CO_GROUP_SIZES, -1, 1);
    core.raw_write_8(CO_GROUP_COLOURS, -1, colour);
    core.raw_write_8(CO_LIST, -1, co);
}

/// The map menu's Save test (`savingEnabled`, after its first load): a
/// Survival map hides Save, as linked play does (a suspended map would
/// come back without its run).
const SAVE_ITEM: u32 = 0x0802_C646;
fn save_item(core: &mut Core) {
    if core.raw_read_8(ON, -1) == 1 && core.raw_read_8(PHASE, -1) == PLAYING {
        let cpu = core.gba_mut().cpu_mut();
        cpu.set_gpr(0, 1);
        let lr = cpu.gpr(14) as u32;
        cpu.set_thumb_pc(lr & !1);
    }
}

/// The save prompt after a map (`sub_0803D73C(slot, then)`, past its
/// `adds r4, r0, #0`: r4 the slot): the War Room's end of map
/// (`sub_08038548`) asks with the War Room's suspend slot, 3, so the
/// prompt clears the profile's "War Room game saved" flag and, saving,
/// deletes slot 3 (`sub_08016C70`): the map just finished was the
/// suspended one, or a new one over it. A Survival map is neither (it has
/// no Save, and Survival never offers the War Room's Continue), so it asks
/// with slot 6 instead, the prompt's "profile only" (as `sub_0803D960`
/// starts it): the records are saved, a War Room game saved halfway is
/// kept.
const SAVE_PROMPT_SLOT: u32 = 0x0803_D746;
const SAVE_PROMPT_START: u32 = 0x0803_D754;
const WAR_ROOM_SLOT: u32 = 3;
const PROFILE_ONLY: u32 = 6;
fn save_prompt_slot(core: &mut Core) {
    if core.raw_read_8(ON, -1) != 1 || !is_survival_map(core.raw_read_8(MAP_ID, -1)) {
        return;
    }
    let cpu = core.gba_mut().cpu_mut();
    if cpu.gpr(4) as u32 == WAR_ROOM_SLOT {
        cpu.set_gpr(4, PROFILE_ONLY as i32);
        cpu.set_thumb_pc(SAVE_PROMPT_START);
    }
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![
        (CO_SCREEN, Box::new(co_screen)),
        (SAVE_ITEM, Box::new(save_item)),
        (SAVE_PROMPT_SLOT, Box::new(save_prompt_slot)),
        (DRAW_MAP_LIST, Box::new(draw_map_list)),
        (END_OF_GAME, Box::new(end_of_game)),
        (SET_MAP_PLAYED, Box::new(set_map_played)),
    ]
}

// --- Records -------------------------------------------------------------------

/// What the profile keeps of Survival: each basic course's best clear and
/// each Champion course's best run.
///
/// The profile is AW2's, saved with its checksum; its options block
/// (`0x0200C420`, 0xE0 bytes) has eleven bytes no code of the game reads or
/// writes, `+0x15..=+0x1F`. They hold, from the first byte:
///
/// - [`MAGIC_V2`] (`0xD6`; `0xD5` is the first layout, three bytes a kind,
///   which is read and rewritten as this one at the next record),
/// - then 76 bits, least significant bit first, the bytes in order:
///   Time, Money, Turn: the best clear's CO (7 bits, 0 for none) and what
///   was left (11 bits of seconds, 13 of hundreds of G, 7 of days: the
///   budgets' own limits); then the maps cleared on the Champion course of
///   Time, Money, Turn (8 bits each, 0 for none).
///
/// The rank is not stored: it is worked out from what was left. A Champion
/// course is open when its basic course has a record (a basic course can
/// only be cleared once for that), so it needs no bit of its own.
#[derive(Clone, Copy, Default, PartialEq, Eq, Debug)]
pub(crate) struct Records {
    /// By [`Kind`] as a number (Time 0, Money 1, Turn 2): (CO, what was left
    /// in the kind's unit, [`record_unit`]).
    pub basic: [Option<(u8, u32)>; 3],
    /// The maps cleared on each Champion course.
    pub champion: [u8; 3],
}

/// The bits of each basic course's "left" field (Time, Money, Turn).
const LEFT_BITS: [usize; 3] = [11, 13, 7];

struct BitStream<'a> {
    bytes: &'a mut [u8],
    at: usize,
}

impl BitStream<'_> {
    fn put(&mut self, v: u32, n: usize) {
        for i in 0..n {
            if (v >> i) & 1 == 1 {
                self.bytes[self.at / 8] |= 1 << (self.at % 8);
            }
            self.at += 1;
        }
    }
    fn get(&mut self, n: usize) -> u32 {
        let mut v = 0;
        for i in 0..n {
            v |= (((self.bytes[self.at / 8] >> (self.at % 8)) & 1) as u32) << i;
            self.at += 1;
        }
        v
    }
}

impl Records {
    pub fn decode(b: &[u8; PROFILE_RECORDS_LEN]) -> Records {
        let mut r = Records::default();
        match b[0] {
            MAGIC_V1 => {
                // rank (3 bits), CO (7), what was left (14), per kind; the
                // rank is 0 for none.
                for k in 0..3 {
                    let v = b[1 + 3 * k] as u32 | (b[2 + 3 * k] as u32) << 8 | (b[3 + 3 * k] as u32) << 16;
                    if v & 7 != 0 {
                        let co = ((v >> 3) & 0x7F) as u8;
                        r.basic[k] = Some((co.max(1), (v >> 10).min((1 << LEFT_BITS[k]) - 1)));
                    }
                }
            }
            MAGIC_V2 => {
                let mut bytes = [0u8; PROFILE_RECORDS_LEN - 1];
                bytes.copy_from_slice(&b[1..]);
                let mut s = BitStream { bytes: &mut bytes, at: 0 };
                for k in 0..3 {
                    let co = s.get(7) as u8;
                    let left = s.get(LEFT_BITS[k]);
                    if co != 0 {
                        r.basic[k] = Some((co, left));
                    }
                }
                for k in 0..3 {
                    r.champion[k] = s.get(8) as u8;
                }
            }
            _ => {}
        }
        r
    }

    pub fn encode(&self) -> [u8; PROFILE_RECORDS_LEN] {
        let mut out = [0u8; PROFILE_RECORDS_LEN];
        out[0] = MAGIC_V2;
        let mut s = BitStream { bytes: &mut out[1..], at: 0 };
        for k in 0..3 {
            let (co, left) = self.basic[k].unwrap_or((0, 0));
            s.put(co as u32 & 0x7F, 7);
            s.put(left.min((1 << LEFT_BITS[k]) - 1), LEFT_BITS[k]);
        }
        for k in 0..3 {
            s.put(self.champion[k] as u32, 8);
        }
        out
    }
}

fn read_records(core: &Core) -> Records {
    let mut b = [0u8; PROFILE_RECORDS_LEN];
    core.raw_read_range(PROFILE_RECORDS, -1, &mut b);
    Records::decode(&b)
}

fn write_records(core: &mut Core, r: &Records) {
    core.raw_write_range(PROFILE_RECORDS, -1, &r.encode());
}

/// What a kind's record counts in (seconds, hundreds of G, days).
fn record_unit(k: Kind) -> u32 {
    match k {
        Kind::Time => 60,
        Kind::Money => 100,
        Kind::Turn => 1,
    }
}

/// A kind's best clear: (rank, CO, what was left).
pub fn record(core: &Core, k: Kind) -> Option<(u8, u8, u32)> {
    let (co, units) = read_records(core).basic[k as usize]?;
    let left = units * record_unit(k);
    Some((maps::rank(k, left), co, left))
}

/// The most maps a Champion course has been taken through (None: not yet).
pub fn champion_record(core: &Core, k: Kind) -> Option<u32> {
    let n = read_records(core).champion[k as usize];
    (n != 0).then_some(n as u32)
}

/// A Champion course is open once its basic course has been cleared (Dual
/// Strike: once it has, the shop sells the Champion course).
pub fn champion_open(core: &Core, k: Kind) -> bool {
    read_records(core).basic[k as usize].is_some()
}

fn save_record(core: &mut Core, k: Kind, left: u32) {
    let mut r = read_records(core);
    let units = left / record_unit(k);
    if let Some((_, best)) = r.basic[k as usize] {
        if best >= units {
            return;
        }
    }
    // A CO of 0 would read as no record.
    let co = (core.raw_read_8(CO, -1) & 0x7F).max(1);
    r.basic[k as usize] = Some((co, units));
    write_records(core, &r);
}

fn save_champion(core: &mut Core, k: Kind, maps_cleared: u32) {
    let n = maps_cleared.min(255) as u8;
    let mut r = read_records(core);
    if n == 0 || n <= r.champion[k as usize] {
        return;
    }
    r.champion[k as usize] = n;
    write_records(core, &r);
}

// --- The budget in battle ------------------------------------------------------------

fn clock(frames: u32) -> String {
    let s = frames / 60;
    format!("{}:{:02}", s / 60, s % 60)
}

/// The budget at the top of the battle map: the map's number and what is
/// left, in Dual Strike's words (Funds left, Turns left, Time left) and
/// AW2's own font, white outlined in black (crate::survival_ui::hud).
fn hud(core: &mut Core, at: u32, end: u32) -> u32 {
    if core.raw_read_32(MAIN_CALLBACK, -1) != MAP_CALLBACK {
        return at;
    }
    let k = kind(core);
    let left = core.raw_read_32(LEFT, -1);
    let now = match k {
        Kind::Money => core.raw_read_32(player(core, 1) + P_FUNDS, -1),
        // Today included: a map won on day d costs d - 1.
        Kind::Turn => (left + 1).saturating_sub(core.raw_read_16(DAY, -1) as u32),
        Kind::Time => left.saturating_sub(core.raw_read_32(TIME, -1)),
    };
    let stage = core.raw_read_8(STAGE, -1) as u32 + 1;
    let label = match k {
        Kind::Money => "Funds left",
        Kind::Turn => "Turns left",
        Kind::Time => "Time left",
    };
    let value = match k {
        Kind::Money => format!("{} G", now),
        Kind::Turn => format!("{}", now),
        Kind::Time => clock(now),
    };
    // A Champion course has no last map: the count only.
    let first = if champion_now(core) { format!("Map {}", stage) } else { format!("Map {}/{}", stage, MAPS_PER_RUN) };
    let lines = [first, format!("{} {}", label, value)];
    crate::survival_ui::hud(core, at, end, &lines)
}

/// SELECT MAP's list: the first entry shown, the cursor's row, the ids.
const LIST_FIRST: u32 = 0x0300_5900;
const LIST_CURSOR: u32 = 0x0300_5930;

/// At the sprite flush ([`crate::branding::flush`]): the budget on the
/// battle map.
pub fn flush_sprites(core: &mut Core, at: u32, end: u32) -> u32 {
    if core.raw_read_8(ON, -1) != 1 || !crate::ds_weather::is_on(core) {
        return at;
    }
    let phase = core.raw_read_8(PHASE, -1);
    if phase == PLAYING && core.raw_read_32(BATTLE_SCENE, -1) != 0 {
        return hud(core, at, end);
    }
    at
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn layout() {
        assert!(ROWS + ROWS_LEN <= 0x0203_FD60, "rows end before cpu_tactics' RAM");
        assert_eq!(ENTRY_IDS[2] + 1, MAPS_FROM);
        assert!((MAPS_FROM as u32 + 33) <= TABLE_IDS);
        assert!(MAP_DATA + MAP_DATA_SIZE * 33 <= STRINGS);
        assert!(text_slot(T_MAPS + 33) < 0x0862_E000);
        assert!(text_slot(T_CHAMPIONS + 3) < 0x0862_E000);
        assert!(T_CHAMPIONS >= T_MAPS + 33);
        assert!(STRINGS + STRING_SIZE * (T_CHAMPIONS as u32 + 3) <= 0x08E4_0000, "strings end before the wheel's data");
        // The Champion entries sit after the 33 maps, below the campaigns'.
        assert_eq!(CHAMPION_IDS[0], MAPS_FROM + 33);
        assert_eq!(CHAMPION_IDS[2] + 1, crate::campaign_model::MAP_ID);
        assert!(CHAMPION > STATE + 0x20 && CHAMPION < STATE + 0x22);
        assert_eq!(clock(90000), "25:00");
    }

    #[test]
    fn entries_are_one_course_each() {
        for (i, &id) in ENTRY_IDS.iter().enumerate() {
            assert_eq!(entry_kind(id), Some((Kind::ALL[i], false)));
            assert_eq!(entry_kind(CHAMPION_IDS[i]), Some((Kind::ALL[i], true)));
        }
        assert_eq!(entry_kind(MAPS_FROM), None);
        assert_eq!(entry_kind(0xF0), None);
    }

    fn sample() -> Records {
        let mut r = Records::default();
        r.basic[Kind::Time as usize] = Some((73, 1499));
        r.basic[Kind::Money as usize] = Some((1, 4999));
        r.basic[Kind::Turn as usize] = Some((127, 99));
        r.champion = [255, 1, 22];
        r
    }

    #[test]
    fn records_round_trip() {
        let r = sample();
        let b = r.encode();
        assert_eq!(b[0], MAGIC_V2);
        assert_eq!(Records::decode(&b), r);
        // Nothing, and an empty profile.
        assert_eq!(Records::decode(&Records::default().encode()), Records::default());
        assert_eq!(Records::decode(&[0; PROFILE_RECORDS_LEN]), Records::default());
        // Too large a value is kept to its field, no field spills into another.
        let mut big = Records::default();
        big.basic[Kind::Turn as usize] = Some((5, 100_000));
        big.champion[0] = 9;
        let d = Records::decode(&big.encode());
        assert_eq!(d.basic[Kind::Turn as usize], Some((5, 127)));
        assert_eq!(d.champion, [9, 0, 0]);
        assert_eq!(d.basic[Kind::Time as usize], None);
    }

    #[test]
    fn the_first_layout_is_still_read() {
        // 0.5.0..0.5.2: [0xD5, 3 bytes per kind: rank 3 bits, CO 7, left 14].
        let mut b = [0u8; PROFILE_RECORDS_LEN];
        b[0] = MAGIC_V1;
        let v = |rank: u32, co: u32, left: u32| rank | co << 3 | left << 10;
        let put = |b: &mut [u8], k: usize, v: u32| b[1 + 3 * k..4 + 3 * k].copy_from_slice(&v.to_le_bytes()[..3]);
        put(&mut b, Kind::Time as usize, v(4, 73, 400));
        put(&mut b, Kind::Money as usize, v(5, 9, 1234));
        // Turn has no record (rank 0).
        let r = Records::decode(&b);
        assert_eq!(r.basic[Kind::Time as usize], Some((73, 400)));
        assert_eq!(r.basic[Kind::Money as usize], Some((9, 1234)));
        assert_eq!(r.basic[Kind::Turn as usize], None);
        assert_eq!(r.champion, [0; 3]);
        // Rewritten, it reads the same.
        assert_eq!(Records::decode(&r.encode()), r);
    }

    #[test]
    fn the_layout_uses_its_bytes_and_no_more() {
        // 8 magic bits + 76: the eleven free bytes of the profile's options.
        let widths: usize = (0..3).map(|k| 7 + LEFT_BITS[k]).sum::<usize>() + 3 * 8;
        assert_eq!(widths, 76);
        assert!(8 + widths <= 8 * PROFILE_RECORDS_LEN);
        // Each limit is the budget's own: 25 minutes, 500,000 G, 99 days.
        assert!(90000 / 60 < 1 << LEFT_BITS[Kind::Time as usize]);
        assert!(500000 / 100 < 1 << LEFT_BITS[Kind::Money as usize]);
        assert!(99 < 1 << LEFT_BITS[Kind::Turn as usize]);
    }
}
