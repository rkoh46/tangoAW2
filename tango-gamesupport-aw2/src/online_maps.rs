//! The map list of a room's match (crate::online): AW2's own SELECT MAP, filled for the room.
//!
//! On the netplay console of a room's match the game's own Versus SELECT MAP is played by the seats in turn
//! ([`crate::unranked`]; its tabs, list, picture, size and property boxes as offline), but its list holds only the maps
//! for as many armies as the room has players, in two tabs: every frame [`retab`] puts each map's header tab (+0x1A,
//! what the list builder sorts maps into tabs by) on the Classic tab (2) or the Pre-Deployed tab (4), and maps for
//! another count on a tab no list shows ([`HIDE`]). A map is Pre-Deployed when it starts with units placed and has no
//! base, airport or port ([`Info::predeployed`]). The tabs read "3P" and "3P Predeploy" for a room of 3 ([`tab_titles`]); a tab with no map is
//! skipped by the list (the 5P rooms have one tab). Offline Versus is not touched (nothing here runs outside a room's
//! match).
//!
//! [`list`], [`preview`] and [`draw_preview`] are independent of that (the UNRANKED proposals use them: maps for a
//! count, each with its name, size, properties and a picture drawn from its tiles).
//!
//! Maps: the game's own map table ([`crate::five_map::table`]: AW2's, or with the Dual Strike pack in use
//! [`crate::ds_versus`]'s). Design Room maps are hidden (their tiles are in the save, not the ROM).

use crate::online::{Rgb, Rgba};
use mgba::core::Core;
use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock};

const TERRAIN_CLASSES: u32 = 0x080C_1BC4;

/// The Versus tabs of the game's list (header +0x1A): Classic .. 5P Maps. Others are not listed in Versus.
const TABS: std::ops::RangeInclusive<u16> = 2..=9;
/// A tab no map list shows (the game's own hidden tab is 0x7F, which [`crate::five_map::show_maps`] uses).
pub const HIDE: u16 = 0x7E;

/// A map for the lists and the UNRANKED proposals.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MapEntry {
    pub id: u8,
    pub name: String,
    pub w: u8,
    pub h: u8,
    /// Properties (HQs, cities, bases, airports, ports, labs) in all.
    pub props: u16,
    /// Of them, the bases (factories).
    pub bases: u16,
    pub armies: u8,
    pub predeployed: bool,
}

// --- The maps ----------------------------------------------------------------------------------

fn rom(at: u32) -> bool {
    (0x0800_0000..0x0A00_0000).contains(&at)
}

/// The id of the last map header to look at in the table in use.
fn last_id(table: u32) -> u32 {
    if table == crate::ds_versus::TABLE {
        0xFF
    } else {
        crate::five_map::MAP_IDS - 1
    }
}

/// How many armies a map has (a 5-army map says 4 in its header: the fifth is tangoAW2's).
fn armies_of(core: &Core, table: u32, id: u32) -> u8 {
    let n = core.raw_read_8(table + 0x5C * id + 0x18, -1);
    let ours = id < 0x100 && crate::five_map::is_five_map(id as u8) && !(table == crate::ds_versus::TABLE && crate::ds_versus::replaced(id as u8));
    if ours {
        5
    } else {
        n
    }
}

/// The ids on the Versus tabs for `armies` players: (maps, Pre-Deployed maps), each in the game's order (tab, id).
fn scan(core: &Core, armies: usize) -> (Vec<u8>, Vec<u8>) {
    let table = crate::five_map::table(core);
    let mut found: Vec<(u16, u8, bool)> = Vec::new();
    for id in 0..=last_id(table) {
        let h = table + 0x5C * id;
        if !rom(core.raw_read_32(h, -1)) {
            continue;
        }
        let tab = core.raw_read_16(h + 0x1A, -1);
        if !(TABS.contains(&tab) || tab == HIDE) || armies_of(core, table, id) as usize != armies {
            continue;
        }
        let pre = info(core, id as u8).is_some_and(|i| i.predeployed());
        found.push((tab, id as u8, pre));
    }
    found.sort();
    let pick = |pre: bool| found.iter().filter(|f| f.2 == pre).map(|f| f.1).collect();
    (pick(false), pick(true))
}

impl Info {
    /// Pre-deployed: it starts with units placed and nobody can build more, because it has no production property (a
    /// base, airport or port, owned or neutral: a neutral one can be captured). Units placed and a base: a plain map.
    fn predeployed(&self) -> bool {
        self.placed > 0 && self.bases + self.airports + self.ports == 0
    }
}

/// What a map is made of, decoded once.
struct Info {
    name: String,
    w: u8,
    h: u8,
    props: u16,
    bases: u16,
    /// Bit k: army slot k owns a property / an HQ on the map.
    owners: u8,
    hqs: u8,
    /// Production properties, owned or neutral (they can be captured): bases, airports, ports.
    airports: u16,
    ports: u16,
    /// Units placed at the start, and bit k: army slot k has some.
    placed: u32,
    unit_owners: u8,
    /// Per tile, row by row: a kind (`K_*`).
    cells: Vec<u8>,
}

// The picture's kinds of tile: terrain, then property owners.
const K_SEA: u8 = 0;
const K_PLAIN: u8 = 1;
const K_WOOD: u8 = 2;
const K_MOUNTAIN: u8 = 3;
const K_ROAD: u8 = 4;
const K_SAND: u8 = 5;
const K_OTHER: u8 = 6;
const K_NEUTRAL: u8 = 7;
/// 8 + the army's colour - 1.
const K_ARMY: u8 = 8;
const KINDS: usize = 13;

fn kind_rgb(k: u8) -> Rgb {
    match k {
        K_SEA => (44, 92, 176),
        K_PLAIN => (152, 208, 104),
        K_WOOD => (56, 140, 72),
        K_MOUNTAIN => (168, 124, 76),
        K_ROAD => (184, 184, 188),
        K_SAND => (236, 212, 132),
        K_OTHER => (124, 104, 168),
        K_NEUTRAL => (250, 250, 250),
        _ => colour_rgb(k - K_ARMY + 1),
    }
}

/// The five armies' colours (1 Orange Star, 2 Blue Moon, 3 Green Earth, 4 Yellow Comet, 5 Black Hole).
fn colour_rgb(c: u8) -> Rgb {
    match c {
        1 => (240, 48, 36),
        2 => (96, 160, 255),
        3 => (32, 200, 72),
        4 => (255, 224, 32),
        _ => (40, 28, 56),
    }
}

type InfoKey = (u32, u32, u32);
fn caches() -> &'static Mutex<HashMap<InfoKey, Arc<Info>>> {
    static C: OnceLock<Mutex<HashMap<InfoKey, Arc<Info>>>> = OnceLock::new();
    C.get_or_init(Default::default)
}

fn name_of(core: &Core, text: u32) -> String {
    let p = core.raw_read_32(0x0861_0A38 + 4 * text, -1);
    let mut name = String::new();
    if rom(p) {
        for k in 0..32 {
            let c = core.raw_read_8(p + k, -1);
            if c == 0 {
                break;
            }
            // (tangoAW2's own maps' names have the apostrophe at `~`)
            name.push(if c == b'~' { '\'' } else { c as char });
        }
    }
    name
}

fn info(core: &Core, id: u8) -> Option<Arc<Info>> {
    let table = crate::five_map::table(core);
    let h = table + 0x5C * id as u32;
    let tiles = core.raw_read_32(h, -1);
    if !rom(tiles) {
        return None;
    }
    let text = core.raw_read_16(h + 0x14, -1) as u32;
    let key = (table, id as u32, tiles ^ (text << 20));
    if let Some(i) = caches().lock().unwrap().get(&key) {
        return Some(i.clone());
    }
    let raw = crate::invention_art::lz77(core, tiles);
    if raw.len() < 2 {
        return None;
    }
    let (w, ht) = (raw[0], raw[1]);
    if w == 0 || ht == 0 || raw.len() < 2 + 2 * w as usize * ht as usize {
        return None;
    }
    let mut classes = vec![0u8; 0x400];
    core.raw_read_range(TERRAIN_CLASSES, -1, &mut classes);
    // The armies' colours by slot (the header's +0x40..).
    let colour = |slot: u8| -> u8 {
        let c = if slot <= 4 { core.raw_read_8(h + 0x40 + slot as u32 - 1, -1) } else { 5 };
        if (1..=5).contains(&c) {
            c
        } else {
            slot.min(5)
        }
    };
    let (mut props, mut bases, mut owners, mut hqs, mut airports, mut ports) = (0u16, 0u16, 0u8, 0u8, 0u16, 0u16);
    let cells = (0..w as usize * ht as usize)
        .map(|i| {
            let t = u16::from_le_bytes([raw[2 + 2 * i], raw[3 + 2 * i]]) as usize;
            let class = classes.get(t).copied().unwrap_or(0);
            let (kind, owner) = (class & 0x1F, class >> 5);
            match kind {
                6 | 8 | 10 | 11 | 14 | 20 => {
                    props += 1;
                    bases += (kind == 14) as u16;
                    airports += (kind == 10) as u16;
                    ports += (kind == 11) as u16;
                    if (1..=5).contains(&owner) {
                        owners |= 1 << owner;
                        if kind == 8 {
                            hqs |= 1 << owner;
                        }
                    }
                    if (1..=5).contains(&owner) {
                        K_ARMY + colour(owner) - 1
                    } else {
                        K_NEUTRAL
                    }
                }
                1 => K_PLAIN,
                2 | 13 => K_SAND,
                3 => K_MOUNTAIN,
                4 => K_WOOD,
                5 | 12 => K_ROAD,
                7 | 19 => K_SEA,
                15 => K_OTHER,
                _ => K_ROAD,
            }
        })
        .collect();
    let units = core.raw_read_32(h + 0x34, -1);
    let (unit_owners, placed) = if rom(units) && core.raw_read_8(units, -1) == 0xFE { unit_owners(core, units) } else { (0, 0) };
    let info = Arc::new(Info { name: name_of(core, text), w, h: ht, props, bases, owners, hqs, airports, ports, placed, unit_owners, cells });
    caches().lock().unwrap().insert(key, info.clone());
    Some(info)
}

/// One row of the map audit: a map of the online pool with its armies counted from its data.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AuditRow {
    pub id: u8,
    pub name: String,
    /// "AW2 Classic" .. "AW2 War Room" (the tab AW2 lists it on), "DS Versus", "DS War Room" or "tangoAW2".
    pub source: &'static str,
    pub w: u8,
    pub h: u8,
    /// The armies the data has: the owners of properties and of pre-placed units.
    pub armies: u8,
    /// Of them, the armies with an HQ.
    pub hqs: u8,
    pub predeployed: bool,
    /// Production properties, owned or neutral.
    pub bases: u16,
    pub airports: u16,
    pub ports: u16,
    /// Units placed at the start.
    pub placed: u32,
    /// Needs the Dual Strike pack: its art (Black Crystal, Black Obelisk), terrain, units (Megatank, Stealth ...), or it is
    /// Dual Strike's own map. Listed only with the pack (online: when every peer has it).
    pub needs_pack: bool,
    /// The armies the map's header says (what the game's own lists trust).
    pub header: u8,
}

/// The armies with pre-placed units in a unit list (a mask of army slots), and the units placed.
fn unit_owners(core: &Core, units: u32) -> (u8, u32) {
    let (mut mask, mut n, mut army) = (0u8, 0u32, 0u8);
    for k in 0..512 {
        let at = units + 12 * k;
        match core.raw_read_8(at, -1) {
            0xFF => break,
            0xFE => army = core.raw_read_8(at + 1, -1),
            _ => {
                n += 1;
                if (1..=5).contains(&army) {
                    mask |= 1 << army;
                }
            }
        }
    }
    (mask, n)
}

/// Where a map comes from: AW2's own (by the tab AW2 lists it on), Dual Strike's (Versus or War Room) or tangoAW2's.
fn source_of(core: &Core, table: u32, id: u8) -> &'static str {
    let dual = table == crate::ds_versus::TABLE;
    if crate::five_map::map_of(id).is_some() && !(dual && crate::ds_versus::replaced(id)) {
        return "tangoAW2";
    }
    if dual {
        return match crate::ds_versus::map_of(core, id) {
            Some(e) if e.case == crate::ds_maps::CASE_WAR_ROOM || e.case == crate::ds_maps::CASE_WAR_ROOM_SECOND => "DS War Room",
            _ => "DS Versus",
        };
    }
    // (AW2's own table in the ROM is untouched: the tab AW2 lists the map on)
    match core.raw_read_16(0x085C_77A0 + 0x5C * id as u32 + 0x1A, -1) {
        2 => "AW2 Classic",
        3 => "AW2 Vs. Maps",
        4 => "AW2 Pre-Deployed",
        5 => "AW2 3P Maps",
        6 => "AW2 4P Maps",
        7 => "AW2 War Room",
        _ => "AW2",
    }
}

/// Every map the online lists can show (Design Room maps and unlisted ids left out), counted from the data.
pub fn audit(core: &Core) -> Vec<AuditRow> {
    let table = crate::five_map::table(core);
    let mut rows = Vec::new();
    for id in 0..=last_id(table) {
        let h = table + 0x5C * id;
        if (0xB4..=0xB7).contains(&id) || !rom(core.raw_read_32(h, -1)) {
            continue;
        }
        let tab = core.raw_read_16(h + 0x1A, -1);
        if !(TABS.contains(&tab) || tab == HIDE) {
            continue;
        }
        let Some(i) = info(core, id as u8) else { continue };
        let predeployed = i.predeployed();
        let all = i.owners | i.unit_owners;
        let source = source_of(core, table, id as u8);
        rows.push(AuditRow {
            id: id as u8,
            name: i.name.clone(),
            source,
            w: i.w,
            h: i.h,
            armies: all.count_ones() as u8,
            hqs: i.hqs.count_ones() as u8,
            predeployed,
            bases: i.bases,
            airports: i.airports,
            ports: i.ports,
            placed: i.placed,
            needs_pack: source.starts_with("DS ") || crate::five_map::map_of(id as u8).is_some_and(|m| source == "tangoAW2" && crate::five_map::needs_pack(m)),
            header: armies_of(core, table, id),
        });
    }
    rows
}

/// The maps a room of `armies` players can play, the Pre-Deployed ones or the others, in the game's order.
pub fn list(core: &Core, armies: usize, predeployed: bool) -> Vec<MapEntry> {
    let (plain, pre) = scan(core, armies);
    let ids = if predeployed { pre } else { plain };
    ids.into_iter()
        .filter_map(|id| {
            let i = info(core, id)?;
            Some(MapEntry { id, name: i.name.clone(), w: i.w, h: i.h, props: i.props, bases: i.bases, armies: armies as u8, predeployed })
        })
        .collect()
}

/// A map's picture: `w` x `h` pixels, row by row.
pub struct Preview {
    pub w: usize,
    pub h: usize,
    pub pixels: Vec<Rgb>,
}

type PreviewKey = (u32, u32, u32, usize, usize);
fn previews() -> &'static Mutex<HashMap<PreviewKey, Arc<Preview>>> {
    static C: OnceLock<Mutex<HashMap<PreviewKey, Arc<Preview>>>> = OnceLock::new();
    C.get_or_init(Default::default)
}

/// A map's size in tiles.
pub fn dims(core: &Core, id: u8) -> Option<(u8, u8)> {
    info(core, id).map(|i| (i.w, i.h))
}

/// The map `id` drawn as large as fits in `max_w` x `max_h` pixels: whole pixels per tile when it can, else each
/// pixel shows what is most of its tiles (a property over anything).
pub fn preview(core: &Core, id: u8, max_w: usize, max_h: usize) -> Option<Arc<Preview>> {
    let i = info(core, id)?;
    let table = crate::five_map::table(core);
    let tiles = core.raw_read_32(table + 0x5C * id as u32, -1);
    let key = (table, id as u32, tiles, max_w, max_h);
    if let Some(p) = previews().lock().unwrap().get(&key) {
        return Some(p.clone());
    }
    let (w, h) = (i.w as usize, i.h as usize);
    let s = (max_w / w).min(max_h / h);
    let (ow, oh) = if s >= 1 {
        (w * s, h * s)
    } else {
        let f = (max_w as f32 / w as f32).min(max_h as f32 / h as f32);
        (((w as f32 * f) as usize).max(1), ((h as f32 * f) as usize).max(1))
    };
    let mut pixels = Vec::with_capacity(ow * oh);
    for py in 0..oh {
        for px in 0..ow {
            let (x0, x1) = (px * w / ow, ((px + 1) * w).div_ceil(ow).max(px * w / ow + 1).min(w));
            let (y0, y1) = (py * h / oh, ((py + 1) * h).div_ceil(oh).max(py * h / oh + 1).min(h));
            let mut count = [0u16; KINDS];
            for y in y0..y1 {
                for x in x0..x1 {
                    count[i.cells[y * w + x] as usize] += 1;
                }
            }
            let prop = (K_NEUTRAL as usize..KINDS).filter(|&k| count[k] > 0).max_by_key(|&k| count[k]);
            let k = prop.unwrap_or_else(|| (0..K_NEUTRAL as usize).max_by_key(|&k| (count[k], std::cmp::Reverse(k))).unwrap_or(0));
            pixels.push(kind_rgb(k as u8));
        }
    }
    let p = Arc::new(Preview { w: ow, h: oh, pixels });
    previews().lock().unwrap().insert(key, p.clone());
    Some(p)
}

/// The map's picture centred in the box (x, y, w, h) of the canvas.
#[allow(dead_code)]
pub(crate) fn draw_preview(core: &Core, cv: &mut Rgba<'_>, id: u8, x: i32, y: i32, w: i32, h: i32) {
    let Some(p) = preview(core, id, w.max(1) as usize, h.max(1) as usize) else { return };
    let (ox, oy) = (x + (w - p.w as i32) / 2, y + (h - p.h as i32) / 2);
    for py in 0..p.h {
        for px in 0..p.w {
            cv.put(ox + px as i32, oy + py as i32, p.pixels[py * p.w + px]);
        }
    }
}

// --- The game's list ---------------------------------------------------------------------------

/// The game's Versus tabs (header +0x1A) by number of armies: (a map's tab, a Pre-Deployed map's tab). Tab 2 is
/// "Classic", 4 "Pre-Deployed", 5 "3P Maps", 6 "4P Maps", 9 "5P Maps".
fn tabs_for(_armies: usize) -> (u16, u16) {
    (2, 4)
}

/// The tabs' titles for a room of `n`: "3P" and "3P Predeploy" ("3P - Predeploy" is two letters too wide for the
/// game's tab box; this fits with room to spare).
pub fn tab_titles(n: usize) -> (String, String) {
    (format!("{n}P"), format!("{n}P Predeploy"))
}

/// Whether the map `id` is one a room offers (it is on one of the room's two tabs: its count of armies, plain or pre-deployed): a
/// private pick is checked with this, since the shared console's list holds only the tab it is on.
pub fn offered(core: &Core, id: u8) -> bool {
    if !owns(core) {
        return false;
    }
    let n = crate::online_teams::players(core);
    let (plain, pre) = tabs_for(n);
    let table = crate::five_map::table(core);
    if id as u32 > last_id(table) {
        return false;
    }
    let h = table + 0x5C * id as u32;
    let tab = core.raw_read_16(h + 0x1A, -1);
    rom(core.raw_read_32(h, -1)) && (tab == plain || tab == pre)
}

/// A room's match: every frame (after [`crate::five_map::show_maps`]), every Versus map's tab for the room's count.
pub fn retab(core: &mut Core) {
    if !owns(core) {
        return;
    }
    let n = crate::online_teams::players(core);
    let (plain, pre) = tabs_for(n);
    let (a, b) = tab_titles(n);
    crate::five_map::name_room_tabs(core, n, &a, &b);
    let table = crate::five_map::table(core);
    for id in 0..=last_id(table) {
        let h = table + 0x5C * id;
        let at = h + 0x1A;
        let tab = core.raw_read_16(at, -1);
        let want = if (0xB4..=0xB7).contains(&id) {
            HIDE
        } else if !rom(core.raw_read_32(h, -1)) || !(TABS.contains(&tab) || tab == HIDE) {
            continue;
        } else if armies_of(core, table, id) as usize != n {
            HIDE
        } else {
            if info(core, id as u8).is_some_and(|i| i.predeployed()) {
                pre
            } else {
                plain
            }
        };
        if tab != want {
            core.raw_write_16(at, -1, want);
        }
    }
}

// --- Offline Versus: the same lists by player count, L+R for the game's own -------------------------------------

/// Offline Versus' SELECT MAP lists the maps by number of players, as a room does: "2P", "2P Predeploy", "3P" .. "5P
/// Predeploy" on the game's tab slots 2..9 (a tab with no map is skipped by the list). L and R together swap them for the game's
/// own lists (Classic, Vs. Maps, Pre-Deployed, the player-count tabs, War Room, Design Maps and tangoAW2's 5P Maps) and
/// back; the choice is kept for the session. The maps' header tabs are rewritten while Versus is the game's mode
/// and put back (from the copy kept at [`OFF_SHADOW`]) when it is not, so War Room and the other modes list as before.
const OFF: u32 = 0x0203_DB00;
/// 1 while the maps' tabs are rewritten (the copy at [`OFF_SHADOW`] is valid).
const OFF_ON: u32 = OFF;
/// The table the copy was taken from (u32).
const OFF_TABLE: u32 = OFF + 4;
/// The keys of last frame (u16).
const OFF_PREV: u32 = OFF + 8;
/// Frames a lone L or R is held back (a combo may follow), the frames it has been down, and whether a combo is held.
const LR_DELAY: u8 = 4;
const OFF_LR: u32 = OFF + 0x0A;
const OFF_COMBO: u32 = OFF + 0x0B;
const OFF_LR_KEY: u32 = OFF + 0x0C;
const OFF_TAP: u32 = OFF + 0x0D;
/// A map's own tab, by id.
const OFF_SHADOW: u32 = OFF + 0x10;
pub const OFF_LEN: u32 = 0x110;

/// The list by number of players (false) or the game's own (true): kept for the session.
static ORIGINAL_VIEW: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

pub fn original_view() -> bool {
    ORIGINAL_VIEW.load(std::sync::atomic::Ordering::Relaxed)
}

/// The tab of a map for `armies` players in the player-count view: 2P 2, 2P Predeploy 3, .. 5P Predeploy 9.
pub fn count_tab(armies: usize, predeployed: bool) -> u16 {
    (2 + 2 * (armies.clamp(2, 5) - 2) + predeployed as usize) as u16
}

/// Offline Versus' SELECT MAP is the screen to show (not a room's, which [`retab`] owns).
fn offline_versus(core: &Core) -> bool {
    !owns(core) && crate::pvp::in_versus(core)
}

/// Every frame, offline, before the game runs: the tabs of the view in use, and L+R swaps the view (the game is
/// told RIGHT once, from the last tab, so that it rebuilds its list on the first tab of the other view). Returns the keys the game gets.
pub fn offline_before(core: &mut Core, keys: u32) -> u32 {
    use crate::online::{KEY_L, KEY_R, KEY_RIGHT};
    let table = crate::five_map::table(core);
    let on = core.raw_read_8(OFF_ON, -1) == 1;
    if on && core.raw_read_32(OFF_TABLE, -1) != table {
        // (another table is in use now: the copy is no good)
        core.raw_write_8(OFF_ON, -1, 0);
    }
    core.raw_write_16(OFF_PREV, -1, keys as u16);
    let mut keys = keys;
    if !offline_versus(core) {
        core.raw_write_8(OFF_LR, -1, 0);
        core.raw_write_8(OFF_COMBO, -1, 0);
        return keys;
    }
    // L and R together swap the views. L or R alone change the tab, as the game has them; so that a combo does not
    // also move a tab, a lone L or R is held back for a few frames (the other may join).
    let lr = keys & (KEY_L | KEY_R);
    let held = core.raw_read_8(OFF_LR, -1);
    if core.raw_read_8(OFF_COMBO, -1) != 0 {
        keys &= !(KEY_L | KEY_R);
        if lr == 0 {
            core.raw_write_8(OFF_COMBO, -1, 0);
            core.raw_write_8(OFF_LR, -1, 0);
        }
    } else if lr == KEY_L | KEY_R && crate::survival_ui::idle(core) {
        core.raw_write_8(OFF_COMBO, -1, 1);
        ORIGINAL_VIEW.fetch_xor(true, std::sync::atomic::Ordering::Relaxed);
        // (the game's tab cursor to the last tab, its memory of each tab's row cleared: RIGHT then wraps to the first non-empty tab)
        core.raw_write_16(TAB_VAR, -1, 9);
        for t in 0..10 {
            core.raw_write_8(TAB_ROWS + t, -1, 0);
        }
        keys = (keys & !(KEY_L | KEY_R)) | KEY_RIGHT;
    } else if lr != 0 {
        let n = held.saturating_add(1);
        core.raw_write_8(OFF_LR, -1, n);
        core.raw_write_8(OFF_LR_KEY, -1, (lr >> 8) as u8);
        if n <= LR_DELAY {
            keys &= !(KEY_L | KEY_R);
        }
    } else {
        // (a tap shorter than the delay is given to the game when it ends, for three frames)
        let mut replay = core.raw_read_8(OFF_TAP, -1);
        if held != 0 && held <= LR_DELAY {
            replay = 3;
        }
        if replay > 0 {
            keys |= (core.raw_read_8(OFF_LR_KEY, -1) as u32) << 8;
            replay -= 1;
        }
        core.raw_write_8(OFF_TAP, -1, replay);
        core.raw_write_8(OFF_LR, -1, 0);
    }
    keys
}

/// Every frame, offline (after [`crate::five_map::show_maps`]): the maps' tabs for the view in use, or the game's own
/// when Versus is not the mode.
pub fn offline_retab(core: &mut Core) {
    if owns(core) {
        return;
    }
    if crate::pvp::in_versus(core) {
        offline_apply(core);
    } else {
        offline_restore(core);
    }
}

/// The game's tab cursor (a halfword) and its memory of the row on each tab (a byte each), in IWRAM.
const TAB_VAR: u32 = 0x0300_596C;
const TAB_ROWS: u32 = 0x0300_5990;

/// The maps' tabs for the view in use.
fn offline_apply(core: &mut Core) {
    if original_view() {
        offline_restore(core);
        return;
    }
    let table = crate::five_map::table(core);
    if core.raw_read_8(OFF_ON, -1) != 1 {
        for id in 0..=0xFFu32 {
            let tab = if id <= last_id(table) { core.raw_read_16(table + 0x5C * id + 0x1A, -1) } else { 0x7F };
            core.raw_write_8(OFF_SHADOW + id, -1, tab.min(0xFF) as u8);
        }
        core.raw_write_32(OFF_TABLE, -1, table);
        core.raw_write_8(OFF_ON, -1, 1);
    }
    for id in 0..=last_id(table) {
        let h = table + 0x5C * id;
        let tab = core.raw_read_16(h + 0x1A, -1);
        // (a map the game or the pack keeps off the lists stays off; the Design Room's slots are not for this list)
        let want = if (0xB4..=0xB7).contains(&id) {
            HIDE
        } else if !rom(core.raw_read_32(h, -1)) || !(TABS.contains(&tab) || tab == HIDE) {
            continue;
        } else {
            let armies = armies_of(core, table, id) as usize;
            if !(2..=5).contains(&armies) {
                HIDE
            } else {
                count_tab(armies, info(core, id as u8).is_some_and(|i| i.predeployed()))
            }
        };
        if tab != want {
            core.raw_write_16(h + 0x1A, -1, want);
        }
    }
    for t in 2..=9u32 {
        let n = 2 + (t as usize - 2) / 2;
        let (plain, pre) = tab_titles(n);
        let k = (t as usize - 2) % 2;
        crate::five_map::name_tab(core, t, n, k, if k == 0 { &plain } else { &pre });
    }
}

/// Puts the game's own tabs (and their titles) back.
fn offline_restore(core: &mut Core) {
    if core.raw_read_8(OFF_ON, -1) != 1 {
        return;
    }
    let table = crate::five_map::table(core);
    for id in 0..=last_id(table) {
        let at = table + 0x5C * id + 0x1A;
        let own = core.raw_read_8(OFF_SHADOW + id, -1) as u16;
        if core.raw_read_16(at, -1) != own {
            core.raw_write_16(at, -1, own);
        }
    }
    for t in 2..=9u32 {
        crate::five_map::set_tab_title(core, t, crate::five_map::native_tab_title(t));
    }
    core.raw_write_8(OFF_ON, -1, 0);
}

/// The hints at the foot of offline Versus' SELECT MAP: what L+R does (and SELECT, on a Dual Strike 2P map).
pub fn draw_hint(core: &Core, rgba: &mut [u8]) {
    use crate::online::*;
    if rgba.len() != W * H * 4 || !offline_versus(core) || !crate::survival_ui::selecting(core) {
        return;
    }
    let mut lines = vec![if original_view() { "L+R: Filter by players" } else { "L+R: Show all lists" }];
    if crate::ds_versus::wants_select(core) {
        lines.insert(0, "SELECT: Second map");
    }
    let mut canvas = Rgba(rgba);
    for (k, t) in lines.iter().rev().enumerate() {
        let w = text_width(core, t) + 14;
        let x = W as i32 - w - 1;
        let y = 141 - 17 * k as i32;
        canvas.plate(x, y, w, 16);
        canvas.text(core, x + 6, y + 3, t, PLATE_GREY, SHADE);
    }
}

/// A room's match is on this console (its SELECT MAP lists only the room's maps, so none is skipped or refused).
pub fn owns(core: &Core) -> bool {
    crate::online::in_room_match(core)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn each_count_has_a_tab_of_its_own() {
        let mut seen = std::collections::BTreeSet::new();
        for n in 2..=5 {
            for pre in [false, true] {
                let t = count_tab(n, pre);
                assert!(TABS.contains(&t) && t <= crate::five_map::CATEGORY, "{n} {pre}: {t}");
                assert!(seen.insert(t), "tab {t} twice");
            }
        }
        assert_eq!(seen.len(), 8);
    }

    #[test]
    fn tabs_are_listable() {
        for n in 2..=5 {
            let (a, b) = tabs_for(n);
            assert!(TABS.contains(&a) && TABS.contains(&b));
        }
    }
}

/// SELECT MAP's list is up and takes the pad (test aid).
pub fn idle(core: &Core) -> bool {
    crate::survival_ui::idle(core)
}

/// Test aid (the offline tab check): the list on screen as text: the tab of its first map, the cursor and the ids.
pub fn probe(core: &Core) -> String {
    let ids: Vec<u8> = (0..0x100).map(|k| core.raw_read_8(crate::online::LIST_IDS + k, -1)).collect();
    let table = crate::five_map::table(core);
    format!("tab-of-first {} cursor {:?} ids {:?}", core.raw_read_16(table + 0x5C * ids[0] as u32 + 0x1A, -1), crate::online::list_cursor(core), ids)
}

/// Test aid: the ids of the rows of the list on screen, and the tab of the first.
pub fn list_rows(core: &Core) -> (u16, Vec<u8>) {
    let n = core.raw_read_8(crate::five_map::LIST_LAST, -1) as usize + 1;
    let ids: Vec<u8> = (0..n.min(crate::five_map::LIST_CAP as usize)).map(|k| core.raw_read_8(crate::five_map::LIST_IDS + k as u32, -1)).collect();
    let table = crate::five_map::table(core);
    let tab = ids.first().map_or(0, |&i| core.raw_read_16(table + 0x5C * i as u32 + 0x1A, -1));
    (tab, ids)
}

/// Test aid: every map the audit lists (not the Design Room's), by id.
pub fn audit_ids(core: &Core) -> Vec<u8> {
    audit(core).into_iter().map(|r| r.id).collect()
}
