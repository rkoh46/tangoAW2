//! The map list of a room's match (crate::online): AW2's own SELECT MAP, filled for the room.
//!
//! On the netplay console of a room's match the game's own Versus SELECT MAP is played by the seats in turn
//! ([`crate::unranked`]; its tabs, list, picture, size and property boxes as offline), but its list holds only the maps
//! for as many armies as the room has players, in two tabs: every frame [`retab`] puts each map's header tab (+0x1A,
//! what the list builder sorts maps into tabs by) on the Classic tab (2) or the Pre-Deployed tab (4), and maps for
//! another count on a tab no list shows ([`HIDE`]). A map is Pre-Deployed when its unit list places units
//! ([`predeployed`]). The tabs read "3P" and "3P Predeploy" for a room of 3 ([`tab_titles`]); a tab with no map is
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
        let pre = predeployed(core, core.raw_read_32(h + 0x34, -1));
        found.push((tab, id as u8, pre));
    }
    found.sort();
    let pick = |pre: bool| found.iter().filter(|f| f.2 == pre).map(|f| f.1).collect();
    (pick(false), pick(true))
}

/// A map starts with units placed (its unit list has units, not only the armies' empty headers).
fn predeployed(core: &Core, units: u32) -> bool {
    rom(units) && core.raw_read_8(units, -1) == 0xFE && unit_owners(core, units).1 > 0
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
    let (mut props, mut bases, mut owners, mut hqs) = (0u16, 0u16, 0u8, 0u8);
    let cells = (0..w as usize * ht as usize)
        .map(|i| {
            let t = u16::from_le_bytes([raw[2 + 2 * i], raw[3 + 2 * i]]) as usize;
            let class = classes.get(t).copied().unwrap_or(0);
            let (kind, owner) = (class & 0x1F, class >> 5);
            match kind {
                6 | 8 | 10 | 11 | 14 | 20 => {
                    props += 1;
                    bases += (kind == 14) as u16;
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
    let info = Arc::new(Info { name: name_of(core, text), w, h: ht, props, bases, owners, hqs, cells });
    caches().lock().unwrap().insert(key, info.clone());
    Some(info)
}

/// One row of the map audit: a map of the online pool with its armies counted from its data.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AuditRow {
    pub id: u8,
    pub name: String,
    /// "AW2", "Dual Strike" or "tangoAW2".
    pub source: &'static str,
    pub w: u8,
    pub h: u8,
    /// The armies the data has: the owners of properties and of pre-placed units.
    pub armies: u8,
    /// Of them, the armies with an HQ.
    pub hqs: u8,
    pub predeployed: bool,
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
        let units = core.raw_read_32(h + 0x34, -1);
        let (umask, placed) = if rom(units) && core.raw_read_8(units, -1) == 0xFE { unit_owners(core, units) } else { (0, 0) };
        let predeployed = placed > 0;
        let all = i.owners | umask;
        let source = if crate::five_map::map_of(id as u8).is_some() {
            "tangoAW2"
        } else if table == crate::ds_versus::TABLE {
            "Dual Strike"
        } else {
            "AW2"
        };
        rows.push(AuditRow {
            id: id as u8,
            name: i.name.clone(),
            source,
            w: i.w,
            h: i.h,
            armies: all.count_ones() as u8,
            hqs: i.hqs.count_ones() as u8,
            predeployed,
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
            if predeployed(core, core.raw_read_32(h + 0x34, -1)) {
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

/// A room's match is on this console (its SELECT MAP lists only the room's maps, so none is skipped or refused).
pub fn owns(core: &Core) -> bool {
    crate::online::in_room_match(core)
}

#[cfg(test)]
mod tests {
    use super::*;

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
