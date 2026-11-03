//! The Gauntlet's two choosing screens (docs/dev/gauntlet-mode.md "The flow"): the **map selector** that opens when GAUNTLET is picked on Select Mode and, after it, the one **army
//! screen**: the player's card (any CO, a colour the map leaves free) and the enemies' cards.
//!
//! The map selector is the game's own: the War Room's SELECT MAP (`ProcScr_PreviewMap`, `0x08616C54`: the map list, the map's picture, the enemy's face, the record box on R), run as a
//! child of the Gauntlet's start proc exactly as the War Room's flow runs it ([`crate::ds_campaign`]'s `gauntlet_start_script`). Its list is a tab of the map table
//! ([`crate::survival`]'s larger copy, as Survival's): one table entry per Gauntlet map ([`id_of`]: the mission's compiled header, its name, its tiles for the picture, its first enemy
//! CO for the face), shown on Survival's tab while the screen is up ([`TAB`], the War Room's tab byte `0x08090EF2`) with the game mode set to the War Room's (the list builder and the
//! screen read it) and put back when the screen ends ([`chosen`]). The record box reads War Room record rows, here a block of ours filled from the Gauntlet's records ([`rows`]).
//! A (the game's own handler) writes the map's id into the play state, B zeroes it: [`chosen`] reads which, as the War Room's flow does (`0x0803BD6D`).
//!
//! The army screen is Versus' Teams screen laid out for one player against the map's CPUs, drawn over the finished picture ([`draw`], through `ds_coselect::apply` like the Teams cards):
//! the cards, windows and help plate of AW2's Teams screen ([`crate::army_cards`], the page online and offline Versus share, in every look: with the pack Versus' Teams screen is this page
//! whatever the map graphics), read from the ROM at run time, nothing committed. The game's own Teams screen is a whole Versus flow (rules, the map's players) and is not run: the game underneath is a proc of the start script that waits (a flow function that answers 1 while the step is up), so this
//! module owns the pad while the screen is up ([`tick`] takes every key) and says which button ended it ([`ANSWER`]). UP and DOWN choose the CO, R and L the colour, A starts, B goes back;
//! the enemies' cards are not editable (LEFT and RIGHT do nothing: there is no other army to move to).
//!
//! The maps and their enemies come from [`crate::gauntlet_mode::entries`] (a new map's mission lists itself), the colours from [`crate::gauntlet_mode::Entry::free`] (the five minus the
//! enemies' fixed ones, plus Silver Nova), the COs from [`crate::gauntlet_mode::ROSTER`] (all 35). The colour is an army code of the Teams screen (1..5, or `army_skin::SKIN + i` for a
//! skin); [`crate::gauntlet::keep_colour`] puts it on the player's army when the battle starts, and the CO goes to the armies as AW2's CO screen gives it ([`apply`]).
//!
//! State: [`STATE`] in EWRAM (`ram_map`): the step, the answer, the cursors, and the last colour worn on each map.

use mgba::core::Core;

use crate::gauntlet_mode::{self as gm, Entry};
use crate::online::{self, Rgba, W};

pub const STATE: u32 = 0x0203_D080;
pub const STATE_LEN: u32 = 0x60;
/// 0 nothing up, 1 the map selector, 2 the army screen.
pub const STEP: u32 = STATE;
/// How the last step ended: 1 A (on to the next), 0 B (back).
pub const ANSWER: u32 = STATE + 1;
/// The selector's cursor: the mission under the list's cursor (read from the game's list each frame).
const MAP_CURSOR: u32 = STATE + 2;
/// The map picked.
const MAP: u32 = STATE + 3;
/// The army screen's colour cursor (an index into the map's free colours).
const COLOUR_CURSOR: u32 = STATE + 4;
/// The army screen's CO cursor (an index into [`gm::ROSTER`]; it keeps its place between visits) and the CO it is on (an AW2 CO id, for the tests).
const CO_CURSOR: u32 = STATE + 5;
pub const CO_PICK: u32 = STATE + 7;
/// How long UP or DOWN has been held (frames) and which: AW2's cursor repeat.
const HELD: u32 = STATE + 8;
const HELD_DIR: u32 = STATE + 9;
/// AW2's cursor repeat: frames from the press to the second step, and between the following ones.
const REPEAT_DELAY: u8 = 10;
const REPEAT_RATE: u8 = 4;
/// The play state's game mode as it was before the selector set the War Room's.
const SAVED_MODE: u32 = STATE + 6;
/// The last choice on each map (an army code, 0 none), [`MAX_MAPS`] maps, by mission.
const LAST: u32 = STATE + 0x40;
/// The most maps the Gauntlet can list: the campaign engine's mission limit ([`crate::campaign_model::MAX_MISSIONS`]: the record words by mission, the cropped pictures in free ROM) and the
/// map-table ids a list can walk ([`SLOT_IDS`]: 51) both allow 32. A new map beyond that needs both raised (docs/dev/gauntlet-mode.md, "Adding a map").
pub const MAX_MAPS: usize = 32;
/// The War Room record rows the record box reads ([`crate::gauntlet::ROWS`]: the Gauntlet's own record block, not Survival's).
const ROWS: u32 = crate::gauntlet::ROWS;
const ROW: u32 = crate::gauntlet::ROW;

/// What the step shows (for the tests, which cannot read the picture's words): +0 the maps listed, +1 how many enemies the highlighted map has, +2.. their (CO, colour) in the order they
/// come (6 at most), +0x0E how many colours are free to wear on the map picked, +0x0F.. those army codes (8 at most).
pub const SHOWN: u32 = STATE + 0x20;

/// The CO screen's picks (`gUnknown_030058D4`): the list `SetArmyCoIdsFromList` gives to the armies, the player's CO the first.
const CO_PICKS: u32 = 0x0300_58D4;
/// `SetArmyCoIdsFromList(list)`: what AW2's CO screen calls with its picks.
const SET_ARMY_CO_IDS: u32 = 0x0803_BCDC;

/// The play state's game mode (the War Room's is 2) and map id.
const PLAY_MODE: u32 = 0x0300_3FC1;
const PLAY_MAP: u32 = 0x0300_3FC2;
const WAR_ROOM_MODE: u8 = 2;
/// The War Room's tab byte in the mode -> tab table ([`crate::survival`] sets it for its own list).
const WAR_ROOM_TAB: u32 = 0x0809_0EF2;
/// SELECT MAP's list: the first row shown, the cursor's row (words), the ids ([`crate::five_map::LIST_IDS`]).
const LIST_FIRST: u32 = 0x0300_5900;
const LIST_CURSOR: u32 = 0x0300_5930;
/// The map-table ids a Gauntlet list may use, ascending (the game lists the table in id order, so the list's order is the ids' order): the free ones past the campaigns' (0xF2..=0xFD: the table walk's
/// last id with the pack is 0xFD, 0xFE is `ds_versus::BATTLE_ID`) and, below them, Survival's entries (0xC9..=0xEF). Survival's entries are borrowed only by a list of more than twelve maps, and given back
/// whole when the selector closes ([`crate::survival::restore_entry`]): Survival and the Gauntlet are never open together. A list of n maps takes the **last** n of them, so the first twelve maps use
/// the free ids and touch nothing of Survival's. An id is a slot in the list, not a map's identity (that is its record key `gauntlet_NN`, [`crate::gauntlet::record_id`]).
pub const SLOT_IDS: [u8; 51] = {
    let mut v = [0u8; 51];
    let mut i = 0;
    while i < 39 {
        v[i] = 0xC9 + i as u8;
        i += 1;
    }
    while i < 51 {
        v[i] = 0xF2 + (i - 39) as u8;
        i += 1;
    }
    v
};
/// The lowest id a full list ([`MAX_MAPS`]) uses: where the record rows start.
pub const ROW_BASE: u8 = SLOT_IDS[SLOT_IDS.len() - MAX_MAPS];

/// The ids of a list of `n` maps, ascending (the last `n` of [`SLOT_IDS`]).
pub fn ids_for(n: usize) -> &'static [u8] {
    &SLOT_IDS[SLOT_IDS.len() - n.min(MAX_MAPS)..]
}

/// How many maps the list's ids are laid out for: the number of maps, or (`TANGOAW2_GAUNTLET_SLOTS`, a test aid: the harness borrows Survival's ids with the maps there are) more. The ids of the
/// first n of the last `span` are used.
fn span() -> usize {
    static S: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
    *S.get_or_init(|| {
        let n = gm::entries().len().min(MAX_MAPS);
        std::env::var("TANGOAW2_GAUNTLET_SLOTS").ok().and_then(|v| v.parse::<usize>().ok()).map_or(n, |v| v.clamp(n, MAX_MAPS))
    })
}

/// The first map-table id the list uses now.
pub fn first_id() -> u8 {
    ids_for(span())[0]
}

pub const SELECT: u8 = 1;
pub const ARMY: u8 = 2;

use crate::online::{KEY_A, KEY_B, KEY_DOWN, KEY_L, KEY_R, KEY_UP};

pub fn step(core: &Core) -> u8 {
    core.raw_read_8(STEP, -1)
}

/// A step is up (the start script waits for it).
pub fn up(core: &Core) -> bool {
    step(core) != 0
}

/// The start script's call: the map selector opens (the War Room's SELECT MAP follows as a child proc).
pub fn begin_select(core: &mut Core) {
    core.raw_write_8(ANSWER, -1, 0);
    core.raw_write_8(STEP, -1, SELECT);
    core.raw_write_8(MAP_CURSOR, -1, 0);
    // (the screen opens on the first map; it records its pick in the play state's map id, 0 until A)
    core.raw_write_32(LIST_FIRST, -1, 0);
    core.raw_write_32(LIST_CURSOR, -1, 0);
    core.raw_write_8(PLAY_MAP, -1, 0);
    core.raw_write_8(SAVED_MODE, -1, core.raw_read_8(PLAY_MODE, -1));
    frame(core);
}

/// The map-table id of the Gauntlet's mission `m` (one entry each, past the Versus maps' and Survival's): the list shows the ids in order, so a map's id is the first plus its place in the
/// selector's order ([`gm::order`]: by the number of enemy COs); the mission stays the map's identity everywhere else.
pub fn id_of(mission: usize) -> u8 {
    ids_for(span())[gm::rank_of(mission).min(gm::entries().len().min(MAX_MAPS) - 1)]
}

/// The mission of a map-table id of ours.
fn mission_of(id: u8) -> Option<usize> {
    let rank = ids_for(span()).iter().position(|&i| i == id)?;
    (rank < gm::entries().len().min(MAX_MAPS)).then(|| gm::order()[rank])
}

/// Each frame the selector is up: what the game's list builder and SELECT MAP read is as the Gauntlet wants it. The game mode is the War Room's (the builder lists a tab only for Versus' and the
/// War Room's), the War Room's tab is ours, our maps' entries are in the table on that tab, and the record rows are ours.
fn frame(core: &mut Core) {
    set8(core, PLAY_MODE, WAR_ROOM_MODE);
    set8(core, WAR_ROOM_TAB, crate::survival::TAB as u8);
    entries_in_table(core, true);
    rows(core);
    let rows = ROWS.wrapping_sub(ROW * (ROW_BASE as u32 - 0x6C));
    for at in crate::survival::RECORD_POOLS.into_iter().chain([crate::ds_versus::INSERT_POOL]) {
        if core.raw_read_32(at, -1) != rows {
            core.raw_write_32(at, -1, rows);
        }
    }
}

fn set8(core: &mut Core, at: u32, v: u8) {
    if core.raw_read_8(at, -1) != v {
        core.raw_write_8(at, -1, v);
    }
}

/// The picture area of the screen holds a map of 32 x 22 cells (the largest of the War Room's); a bigger map (Iron Crown, 40 x 26) is shown by its middle part: the picture's tiles (header
/// +0x2C, the battle reads +0x00) are a cropped copy in free ROM past Survival's maps, [`PREVIEW_SIZE`] a mission. Without it the picture ran over the list.
const PREVIEW_ROM: u32 = 0x08E2_0000;
const PREVIEW_SIZE: u32 = 0x800;
const PREVIEW_CELLS: (usize, usize) = (32, 22);

/// The cropped picture's blob for `mission` (LZ77 of width, height, tiles), or None when the whole map fits.
fn preview_blob(e: &Entry) -> Option<&'static Vec<u8>> {
    static B: std::sync::OnceLock<Vec<Option<Vec<u8>>>> = std::sync::OnceLock::new();
    B.get_or_init(|| {
        gm::entries()
            .iter()
            .map(|e| {
                let m = crate::custom_campaign::built_map(e.key)?;
                let (w, h) = (m.width as usize, m.height as usize);
                if w <= PREVIEW_CELLS.0 && h <= PREVIEW_CELLS.1 {
                    return None;
                }
                let (cw, ch) = (w.min(PREVIEW_CELLS.0), h.min(PREVIEW_CELLS.1));
                let (x0, y0) = ((w - cw) / 2, (h - ch) / 2);
                let mut raw = vec![cw as u8, ch as u8];
                for y in 0..ch {
                    for x in 0..cw {
                        raw.extend_from_slice(&m.tiles[(y0 + y) * w + x0 + x].to_le_bytes());
                    }
                }
                let mut lz = crate::lz77::compress(&raw);
                while lz.len() % 4 != 0 {
                    lz.push(0);
                }
                assert!(lz.len() <= PREVIEW_SIZE as usize);
                Some(lz)
            })
            .collect()
    })
    .get(e.mission)?
    .as_ref()
}

/// The Gauntlet's map entries in the map table: each mission's compiled header with the tab the list shows ([`TAB`] while the selector is up, a tab no list shows otherwise).
fn entries_in_table(core: &mut Core, shown: bool) {
    let Some(table) = crate::ds_campaign::selector_table(core) else { return };
    for e in gm::entries().iter().take(MAX_MAPS) {
        let id = id_of(e.mission);
        if !shown && id <= 0xEF {
            // (a borrowed Survival entry goes back whole)
            crate::survival::restore_entry(core, id);
            continue;
        }
        let Some(mut h) = crate::ds_campaign::mission_header(core, e.mission) else { continue };
        let tab = if shown { crate::survival::TAB } else { crate::five_map::HIDDEN_TAB };
        h[0x1A..0x1C].copy_from_slice(&tab.to_le_bytes());
        // (the list's own form of a War Room map: the player's slot, then the enemies' COs in the order they come, as many as the screen has faces for)
        h[0x16] = 1;
        h[0x3C] = 0xFF;
        for k in 0..3 {
            h[0x3D + k] = e.enemies.get(k).map_or(0, |en| en.0);
        }
        if let Some(blob) = preview_blob(e) {
            let rom = PREVIEW_ROM + PREVIEW_SIZE * e.mission as u32;
            let mut have = vec![0u8; blob.len()];
            core.raw_read_range(rom, -1, &mut have);
            if &have != blob {
                core.raw_write_range(rom, -1, blob);
            }
            h[0x2C..0x30].copy_from_slice(&rom.to_le_bytes());
        }
        let at = table + crate::five_map::ENTRY * id as u32;
        let mut now = [0u8; 0x5C];
        core.raw_read_range(at, -1, &mut now);
        if now != h {
            core.raw_write_range(at, -1, &h);
        }
    }
}

/// The War Room's record rows for our maps (five records of four bytes, in the layout the Gauntlet's own record has: AW2's `CO | days << 8 | score << 20`), the first the Gauntlet's best on the map.
fn rows(core: &mut Core) {
    let mut b = vec![0u8; crate::gauntlet::ROWS_LEN as usize];
    for e in gm::entries().iter().take(MAX_MAPS) {
        // (the map's five results as the War Room keeps them: best first, one word each)
        // (the game reads the row of the map-table id it lists the map by: the map's place in the selector's order, not its mission; the results themselves are the map's record id's)
        let at = ROW as usize * (id_of(e.mission) - ROW_BASE) as usize;
        for (k, w) in crate::gauntlet::results_of(core, e.mission).iter().enumerate() {
            b[at + 4 * k..at + 4 * k + 4].copy_from_slice(&w.to_le_bytes());
        }
    }
    let mut now = vec![0u8; b.len()];
    core.raw_read_range(ROWS, -1, &mut now);
    if now != b {
        core.raw_write_range(ROWS, -1, &b);
    }
}

/// The selector's screen has ended (the start script's call): A put a map's id in the play state, B zeroed it. The game mode is put back; a map taken becomes the session's mission and the
/// army screen opens on it (the colour starts on the one last worn on the map).
pub fn chosen(core: &mut Core) {
    let id = core.raw_read_8(PLAY_MAP, -1);
    leave(core);
    match mission_of(id) {
        Some(m) => {
            core.raw_write_8(MAP, -1, m as u8);
            // (the battle is played on the campaign's own entry, [`crate::ds_campaign::choose_gauntlet_map`] fills it)
            core.raw_write_8(PLAY_MAP, -1, crate::campaign_model::MAP_ID);
            crate::ds_campaign::choose_gauntlet_map(core, m);
            begin_army(core, m);
        }
        None => core.raw_write_8(ANSWER, -1, 0),
    }
}

/// The selector is over (or the session is not): the game mode as it was, our entries off every list.
fn leave(core: &mut Core) {
    if step(core) == SELECT {
        let saved = core.raw_read_8(SAVED_MODE, -1);
        core.raw_write_8(PLAY_MODE, -1, saved);
    }
    entries_in_table(core, false);
    core.raw_write_8(STEP, -1, 0);
}

/// The map selector is up.
pub fn selecting(core: &Core) -> bool {
    step(core) == SELECT
}

/// The scroll bar's track is drawn with a sprite for every 8 pixels of a length worked out as the rows a page shows over the list's last row, a length meant for a list of dozens of
/// maps: a list of two is a track of ~100 sprites, which overflows the sprite buffer into the registers the frame is shown with. The track is at most its own full length (`0x70`),
/// the thumb the whole of it. (`0x0808731A`: the length, in r0 after its division.)
const SCROLL_TRACK: u32 = 0x0808_731A;

fn scroll_track(core: &mut Core) {
    if !selecting(core) {
        return;
    }
    let cpu = core.gba_mut().cpu_mut();
    if cpu.gpr(0) as u32 > 0x70 {
        cpu.set_gpr(0, 0x70);
    }
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![(SCROLL_TRACK, Box::new(scroll_track))]
}

/// The army screen opens for `mission`: the colour on the one last worn on the map (a map with one colour free just shows it), the CO where the cursor was.
fn begin_army(core: &mut Core, mission: usize) {
    let free = gm::entries().get(mission).map(Entry::free).unwrap_or_default();
    let last = last_choice(core, mission);
    let at = free.iter().position(|&c| c == last).unwrap_or(0);
    core.raw_write_8(COLOUR_CURSOR, -1, at as u8);
    let co = core.raw_read_8(CO_CURSOR, -1) as usize % gm::ROSTER.len();
    core.raw_write_8(CO_CURSOR, -1, co as u8);
    core.raw_write_8(CO_PICK, -1, gm::ROSTER[co].0);
    core.raw_write_8(HELD, -1, 0);
    core.raw_write_8(HELD_DIR, -1, 0);
    // (1 for the script's test of the selector's answer; the screen's own A and B set it when they end it)
    core.raw_write_8(ANSWER, -1, 1);
    core.raw_write_8(STEP, -1, ARMY);
}

/// The start script's call after the army screen's A: the picked CO goes to the armies as AW2's CO screen gives its picks, by `SetArmyCoIdsFromList` called here in the screen's place with the
/// list it reads. A jump to the function does not run the traps on it, so the one that matters here runs first: [`crate::tag::set_cos`] moves a five-army map's pick to the player's army (the
/// fifth; the first keeps its fixed CO). The Gauntlet has no two-front maps ([`crate::two_front`]'s trap there).
pub fn apply(core: &mut Core) {
    let co = core.raw_read_8(CO_PICK, -1);
    core.raw_write_8(CO_PICKS, -1, co);
    core.gba_mut().cpu_mut().set_gpr(0, CO_PICKS as i32);
    crate::tag::set_cos(core);
    core.gba_mut().cpu_mut().set_thumb_pc(SET_ARMY_CO_IDS);
}

/// A mission is starting (`ResetRulesAfterCampaignMap`, [`crate::ds_campaign`]'s `mission_start`): a five-army map's player is its fifth army, whose CO the start has just put back to the
/// mission's own, none: the army screen's pick (kept by [`crate::tag::set_cos`] in army 5's CO byte before the start) is put there again.
pub fn keep_pick(core: &mut Core) {
    if !crate::gauntlet::session(core) || core.raw_read_8(crate::gauntlet::CONTINUING, -1) != 0 {
        return;
    }
    if crate::ds_campaign::mission_info(core).and_then(|m| m.native.as_ref()).is_some_and(|n| n.five_pick.is_some()) {
        crate::five::set_army5_co(core, core.raw_read_8(CO_PICK, -1));
    }
}

/// The map the selector picked.
pub fn picked(core: &Core) -> Option<&'static Entry> {
    gm::entries().get(core.raw_read_8(MAP, -1) as usize)
}

/// The selector's cursor and the colour pick's, for the tests.
pub fn cursors(core: &Core) -> (u8, u8) {
    (core.raw_read_8(MAP_CURSOR, -1), core.raw_read_8(COLOUR_CURSOR, -1))
}

fn last_choice(core: &Core, mission: usize) -> u8 {
    if mission < MAX_MAPS {
        core.raw_read_8(LAST + mission as u32, -1)
    } else {
        0
    }
}

/// Each frame: while a step is up it takes the pad (the game sees no key) and moves the cursor; A and B end the step.
pub fn tick(core: &mut Core, on: bool, keys: u32, prev: u32) -> u32 {
    let s = step(core);
    if s == 0 {
        return keys;
    }
    if !on || !crate::gauntlet::session(core) {
        leave(core);
        return keys;
    }
    let pressed = keys & !prev;
    if s != SELECT {
        mirror(core);
    }
    match s {
        SELECT => {
            // The game's own screen takes the pad (A and B end it); only what it reads is kept as the Gauntlet wants it.
            frame(core);
            let list_at = crate::five_map::LIST_IDS + (core.raw_read_32(LIST_FIRST, -1) + core.raw_read_32(LIST_CURSOR, -1)).min(crate::five_map::LIST_CAP - 1);
            if let Some(m) = mission_of(core.raw_read_8(list_at, -1)) {
                core.raw_write_8(MAP_CURSOR, -1, m as u8);
            }
            mirror(core);
            return keys;
        }
        _ => {
            let free = picked(core).map(Entry::free).unwrap_or_default();
            let n = free.len().max(1) as u8;
            let mut c = core.raw_read_8(COLOUR_CURSOR, -1) % n;
            if pressed & KEY_R != 0 {
                c = (c + 1) % n;
            }
            if pressed & KEY_L != 0 {
                c = (c + n - 1) % n;
            }
            core.raw_write_8(COLOUR_CURSOR, -1, c);
            // UP and DOWN walk the roster, a held key repeating as AW2's cursors do.
            let dir = if keys & KEY_DOWN != 0 { 1u8 } else if keys & KEY_UP != 0 { 2 } else { 0 };
            let (held, was) = (core.raw_read_8(HELD, -1), core.raw_read_8(HELD_DIR, -1));
            let held = if dir != was { 0 } else { held.saturating_add(1) };
            core.raw_write_8(HELD, -1, held);
            core.raw_write_8(HELD_DIR, -1, dir);
            if dir != 0 && (dir != was || (held >= REPEAT_DELAY && (held - REPEAT_DELAY) % REPEAT_RATE == 0)) {
                let len = gm::ROSTER.len();
                let at = core.raw_read_8(CO_CURSOR, -1) as usize % len;
                let at = if dir == 1 { (at + 1) % len } else { (at + len - 1) % len };
                core.raw_write_8(CO_CURSOR, -1, at as u8);
                core.raw_write_8(CO_PICK, -1, gm::ROSTER[at].0);
            }
            if pressed & KEY_A != 0 {
                let mission = picked(core).map_or(0, |e| e.mission);
                // (a map with no colour free keeps the map's own: 0)
                let code = free.get(c as usize).copied().unwrap_or(0);
                crate::ds_campaign::set_gauntlet_choice(core, code);
                if mission < MAX_MAPS {
                    core.raw_write_8(LAST + mission as u32, -1, code);
                }
                core.raw_write_8(ANSWER, -1, 1);
                core.raw_write_8(STEP, -1, 0);
            } else if pressed & KEY_B != 0 {
                core.raw_write_8(ANSWER, -1, 0);
                core.raw_write_8(STEP, -1, 0);
            }
        }
    }
    0
}

/// Writes [`SHOWN`]: what the selector lists for the map under the cursor and what the army screen offers for the map picked.
fn mirror(core: &mut Core) {
    let entries = gm::entries();
    let cursor = core.raw_read_8(MAP_CURSOR, -1) as usize;
    let mut b = [0u8; 0x17];
    b[0] = entries.len() as u8;
    let shown = if step(core) == SELECT { entries.get(cursor) } else { picked(core) };
    if let Some(e) = shown {
        b[1] = e.enemies.len().min(6) as u8;
        for (k, en) in e.enemies.iter().take(6).enumerate() {
            b[2 + 2 * k] = en.0;
            b[3 + 2 * k] = en.1;
        }
        let free = e.free();
        b[0x0E] = free.len().min(8) as u8;
        for (k, c) in free.iter().take(8).enumerate() {
            b[0x0F + k] = *c;
        }
    }
    core.raw_write_range(SHOWN, -1, &b);
}

// --- Drawing ------------------------------------------------------------------------------------------------------------------------------------------

/// The most enemy cards the screen shows: Versus' Teams screen has five armies, the player's the first. A map with more lines (Iron Crown's Asuka stage) shows the first four.
const MAX_ENEMIES: usize = 4;

/// The army screen's cards: (CO, army code) of the player first, then the enemies in the order they come.
fn cards(e: &Entry, co: u8, colour: u8) -> Vec<(u8, u8)> {
    std::iter::once((co, colour)).chain(e.enemies.iter().take(MAX_ENEMIES).map(|&(co, c)| (co, e.shown_colour(c)))).collect()
}

/// The army screen's picture for map `e` with CO `co` in army colour `colour` (also the text audit's page): the Teams screen's own frame (its ground, GAUNTLET in its title banner), the
/// cards, windows and help plate of AW2's Teams screen ([`crate::army_cards`]); the map's name leads the help plate.
pub fn paint_army(core: &Core, rgba: &mut [u8], e: &Entry, co: u8, colour: u8) {
    use crate::army_cards::{Field, Help, Seat};
    let cv = &mut Rgba(rgba);
    crate::army_cards::teams_frame(core, cv, "GAUNTLET");
    let seats: Vec<Seat> = cards(e, co, colour)
        .into_iter()
        .enumerate()
        .map(|(k, (co, colour))| Seat {
            name: if k == 0 { "Player 1".into() } else { "CPU".into() },
            co: Some(co),
            colour,
            team: None,
            partner: crate::army_cards::NONE,
            ready: false,
            mine: k == 0,
            field: (k == 0).then_some(Field::Co),
            tag: Some(if k == 0 { "1P" } else { "CP" }),
        })
        .collect();
    let full = format!("{}: choose your CO and colour.", e.title);
    let first = if online::text_width(core, &full) <= 228 { full } else { e.title.to_string() };
    let lines = vec![first, "Up Down: CO  R: Colour  A: Start  B: Back".to_string()];
    crate::army_cards::draw(core, cv.0, &seats, false, &Help { lines }, false);
}

/// The army screen's picture over the finished one. `true` when one is up.
pub fn draw(core: &Core, rgba: &mut [u8]) -> bool {
    if rgba.len() != W * online::H * 4 {
        return false;
    }
    let s = step(core);
    if s == 0 || !crate::gauntlet::session(core) {
        return false;
    }
    // (the map selector is the game's own screen: nothing is drawn over it)
    if s != ARMY {
        return false;
    }
    let Some(e) = picked(core) else { return false };
    let co = core.raw_read_8(CO_PICK, -1);
    let free = e.free();
    let colour = free.get(core.raw_read_8(COLOUR_CURSOR, -1) as usize).copied().unwrap_or(1);
    paint_army(core, rgba, e, co, colour);
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The list at its maximum: 32 maps get 32 ascending ids that avoid the campaigns' and the battle's (0xF0, 0xF1, 0xFE), the record rows cover every id, a map's identity (its record key) never moves when
    /// maps are added, and 32 maps' records keep their own top fives. The first twelve maps never touch Survival's entries.
    #[test]
    fn a_full_list_has_ids_rows_records_and_order_that_work() {
        for n in 1..=MAX_MAPS {
            let ids = ids_for(n);
            assert_eq!(ids.len(), n);
            assert!(ids.windows(2).all(|w| w[0] < w[1]), "ascending: the game lists the table in id order");
            assert_eq!(*ids.last().unwrap(), 0xFD, "the table walk's last id");
            assert!(ids.iter().all(|&i| i != 0xF0 && i != 0xF1 && i != 0xFE && i >= ROW_BASE));
            if n <= 12 {
                assert!(ids.iter().all(|&i| i >= 0xF2), "up to twelve maps use only the free ids: Survival's entries are untouched ({n})");
            }
        }
        assert_eq!(SLOT_IDS.len(), 51);
        assert!(SLOT_IDS.windows(2).all(|w| w[0] < w[1]));
        assert!(MAX_MAPS <= SLOT_IDS.len() && MAX_MAPS <= crate::campaign_model::MAX_MISSIONS, "the limit is the campaign's missions and the ids");
        assert_eq!(MAX_MAPS * 0x800, 0x10000, "the cropped pictures of 32 maps fit before Survival's strings (0x08E20000..0x08E30000)");
        // rows: every id of a full list has a row inside the Gauntlet's block, and the table follows the rows
        assert!(ids_for(MAX_MAPS).iter().all(|&i| ((i - ROW_BASE) as u32) < crate::gauntlet::ROW_COUNT));
        assert_eq!(crate::gauntlet::TABLE, crate::gauntlet::ROWS + crate::gauntlet::ROWS_LEN);
        assert!(crate::gauntlet::BLOCK + crate::gauntlet::BLOCK_LEN <= 0x0203_F100, "the block ends before the Rules screen's tiles");
        // order: thirty-two maps with enemy counts 2..5 in any definition order list fewest first, ties by definition
        let counts: Vec<usize> = (0..MAX_MAPS).map(|m| 2 + (m * 7 + m / 3) % 4).collect();
        let order = gm::order_of(&counts);
        assert!(order.windows(2).all(|w| counts[w[0]] < counts[w[1]] || (counts[w[0]] == counts[w[1]] && w[0] < w[1])));
        let mut sorted = order.clone();
        sorted.sort();
        assert_eq!(sorted, (0..MAX_MAPS).collect::<Vec<_>>());
        // records: 32 maps each keep their own five results by their record key, whatever the list's order
        let mut t = vec![0u8; crate::gauntlet::TABLE_LEN];
        for round in 0..5u32 {
            for k in 1..=MAX_MAPS as u8 {
                assert!(crate::gauntlet::insert(&mut t, k, k, 10 + round, 100 * k as u32 + round).is_some(), "map {k} round {round}");
            }
        }
        for k in 1..=MAX_MAPS as u8 {
            let w = crate::gauntlet::tops(&t, k);
            assert!(w.iter().all(|&x| x as u8 == k), "map {k}'s five are its own");
            assert_eq!(w.map(|x| x >> 20), [100 * k as u32 + 4, 100 * k as u32 + 3, 100 * k as u32 + 2, 100 * k as u32 + 1, 100 * k as u32]);
        }
        // keys: gauntlet_01..gauntlet_32 have record ids 1..32, so a map added later never moves another's
        for n in 1..=MAX_MAPS {
            assert_eq!(crate::gauntlet::record_id(&format!("gauntlet_{n:02}")), Some(n as u8));
        }
    }

    #[test]
    fn todays_maps_are_listed_with_ascending_ids_in_their_order() {
        assert!(gm::entries().len() <= MAX_MAPS);
        let ids: Vec<u8> = gm::order().iter().map(|&m| id_of(m)).collect();
        assert!(ids.windows(2).all(|w| w[0] < w[1]));
        for &m in gm::order() {
            assert_eq!(mission_of(id_of(m)), Some(m));
        }
        assert_eq!(first_id(), ids[0]);
    }
}
