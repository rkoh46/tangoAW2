//! The game's state, decoded from the console's RAM into plain data: what the AI debug channel
//! ([`crate::ai_debug`]) answers `state` with, and what its events are made from.
//!
//! Everything here only reads the console (`&Core`), never writes it, and costs nothing unless the channel is on
//! (the channel's tick hook is the only caller). The decoders are the ones the rest of the crate already has (the
//! battle's map, unit and player layouts of [`crate::ds_ai::Board`], the screens' probes of [`crate::online`], the
//! test aids of [`crate::test_aid`] and [`crate::run_dump`]); this module puts them in one place and names the fields.
//!
//! Layouts used (AW2's, see docs/AW2.md):
//! - gMap `0x0201E450`: width and height (halfwords), camera in pixels at +4/+6, unit-id plane at +0x12 (and +0x51A),
//!   terrain classes at +0x1432 (low 5 bits the class, top 3 the owner army of a property), the displayed vision plane
//!   at +0x234A, each row's offset at +0x417A.
//! - The unit table (`[0x08499594]`): 12-byte records by unit id, 64 ids an army (51 in a five-army game): +0 type
//!   (0 free), +1 flags (0x01 moved, 0x08 carried, 0x20 hidden), +2 x, +3 y, +4 halfword hit points (low 7 bits), ammo
//!   (bits 7..10) and capture points (bits 11..15), +6 fuel.
//! - The player blocks (`crate::five::players`, 0x3C bytes an army): +0 funds, +0x1A colour, +0x1B controller (0 none,
//!   1 human, 2 CPU), +0x1D CO, +0x1E power mode (0 none, 1 CO Power, 2 Super), +0x20 power meter, +0x25 powers used,
//!   +0x2A team.

use mgba::core::Core;
use serde_json::{json, Map, Value};
use std::collections::BTreeMap;

pub const MAP: u32 = 0x0201_E450;
const ROWS: u32 = MAP + 0x417A;
const TERRAIN: u32 = MAP + 0x1432;
const UNIT_PLANE: u32 = MAP + 0x12;
const UNITS_POINTER: u32 = 0x0849_9594;
const UNIT: u32 = 12;
const MAIN_LOOP: u32 = 0x0300_0000;
const CURSOR: u32 = 0x0300_33E4;
const DAY: u32 = 0x0300_4080;
const PLAY_ST: u32 = 0x0300_3FC0;
const MAP_SELECTED: u32 = 0x0300_3FC2;
const MAP_MENU_STATE: u32 = 0x0300_14E2;
const MAP_MENU_CURSOR: u32 = 0x0300_14F0;
const MAP_MENU_ITEMS: u32 = 0x0300_14A1;
const SELECTED_UNIT: u32 = 0x0300_40D8;

/// The online protocol version the shared console speaks (`SharedGame::sim_version`): peers with another do not match.
pub const SIM_VERSION: u16 = 31;

pub const MOVED: u8 = 0x01;
pub const CARRIED: u8 = 0x08;
pub const HIDDEN: u8 = 0x20;

/// Unit type names by the game's type number.
pub fn unit_name(kind: u8) -> &'static str {
    crate::bh_smart::NAMES.get(kind as usize).copied().unwrap_or("?")
}

/// A terrain class's name when it is a property.
pub fn property_name(class: u8) -> Option<&'static str> {
    match class {
        6 => Some("city"),
        8 => Some("hq"),
        10 => Some("airport"),
        11 => Some("port"),
        14 => Some("base"),
        20 => Some("lab"),
        _ => None,
    }
}

pub fn weather_name(w: u8) -> &'static str {
    match w {
        0 => "clear",
        1 => "snow",
        2 => "rain",
        3 => "sandstorm",
        _ => "?",
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct UnitInfo {
    pub id: u32,
    pub owner: u8,
    pub kind: u8,
    pub x: i32,
    pub y: i32,
    pub hp: u32,
    pub fuel: u8,
    pub ammo: u8,
    pub flags: u8,
    pub capture: u8,
    /// The units this one carries (ids).
    pub cargo: Vec<u32>,
}

impl UnitInfo {
    pub fn moved(&self) -> bool {
        self.flags & MOVED != 0
    }
    pub fn carried(&self) -> bool {
        self.flags & CARRIED != 0
    }
    fn json(&self) -> Value {
        json!({
            "id": self.id, "owner": self.owner, "type": self.kind, "name": unit_name(self.kind),
            "x": self.x, "y": self.y, "hp": self.hp, "fuel": self.fuel, "ammo": self.ammo,
            "moved": self.moved(), "done": self.moved(), "carried": self.carried(), "hidden": self.flags & HIDDEN != 0,
            "flags": self.flags, "capture": self.capture, "cargo": self.cargo,
        })
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct ArmyInfo {
    pub army: u8,
    pub colour: u8,
    /// The army's name: the colour's, or an army skin's (Emerald Sun) where one sits on the colour.
    pub colour_name: String,
    pub controller: u8,
    pub co: u8,
    pub co_name: Option<String>,
    pub partner: Option<u8>,
    pub funds: u32,
    pub meter: u32,
    pub power_cost: u32,
    pub super_cost: u32,
    pub power_mode: u8,
    pub powers_used: u8,
    pub team: u8,
    pub alive: bool,
    pub seat: Option<usize>,
    pub units: u32,
    pub properties: u32,
}

#[derive(Clone, Debug, PartialEq)]
pub struct PropertyInfo {
    pub x: i32,
    pub y: i32,
    pub class: u8,
    pub owner: u8,
    /// Capture points of the unit standing on it (0 none).
    pub capture: u8,
}

/// The decoded state at one tick.
#[derive(Clone, Debug)]
pub struct Snapshot {
    pub frame: u32,
    pub online: bool,
    pub phase: &'static str,
    pub screen: &'static str,
    pub main_loop: u32,
    pub in_battle: bool,
    pub turn_ended: bool,
    pub decided: bool,
    pub winner: Option<u8>,
    pub active_army: u8,
    pub active_seat: Option<usize>,
    pub mine: bool,
    pub day: u16,
    pub fog: bool,
    pub weather: u8,
    pub powers_on: bool,
    pub abilities_on: bool,
    pub game_mode: u8,
    pub map_id: u8,
    pub map_name: Option<String>,
    pub width: u32,
    pub height: u32,
    pub cursor: (u16, u16),
    pub camera: (i16, i16),
    pub menu: Value,
    pub selected_unit: Option<u32>,
    pub armies: Vec<ArmyInfo>,
    pub units: Vec<UnitInfo>,
    pub properties: Vec<PropertyInfo>,
    pub flags: Value,
    pub online_info: Value,
    pub select_map: Value,
}

fn row_offsets(core: &Core, h: u32) -> Vec<u32> {
    (0..h).map(|y| core.raw_read_16(ROWS + 2 * y, -1) as u32).collect()
}

/// The coarse phase and the finer screen the console is at. Phases: `boot`, `title`-ish `menu`, `select_mode`,
/// `online_menu`, `room`, `select_map`, `army_select`, `rules`, `battle`, `results`.
pub fn classify(core: &Core, _online: bool) -> (&'static str, &'static str) {
    use crate::fog_view::Phase;
    let ml = core.raw_read_32(MAIN_LOOP, -1);
    if crate::pvp::in_battle(core) && (1..=5).contains(&crate::pvp::current_army(core)) {
        if crate::result_view::decided(core) {
            return ("results", "victory");
        }
        let screen = match crate::fog_view::phase(core) {
            Phase::Map => {
                if map_menu_items(core).is_some() {
                    "map_menu"
                } else if crate::tag_ui::build_menu_up(core) {
                    "build_menu"
                } else if !crate::fog_view::plain_map(core) && core.raw_read_8(MAP_MENU_STATE, -1) == 4 {
                    // (a unit's command menu, the Intel and Options lists, a target being chosen)
                    if menus(core).iter().any(|m| m["kind"] == "unit") {
                        "unit_menu"
                    } else {
                        "submenu"
                    }
                } else {
                    "map"
                }
            }
            Phase::HandOff => "hand_off",
            Phase::Busy => {
                if crate::pvp::chosen_main_item(core)
                    .is_some_and(|i| i == crate::pvp::MENU_POWER || i == crate::pvp::MENU_SUPER)
                {
                    "co_power"
                } else {
                    "animation"
                }
            }
            Phase::Page => "co_page",
            Phase::Scene => "battle_scene",
            Phase::Moving => "transition",
        };
        return ("battle", screen);
    }
    if crate::unranked::rules_up(core) {
        return ("rules", "rules");
    }
    if crate::pvp::on_teams_screen(core) {
        return if core.raw_read_8(rules_record(core) + 0x30, -1) == 0 {
            ("rules", "rules")
        } else {
            ("army_select", "army_select")
        };
    }
    if crate::survival_ui::selecting(core) {
        return ("select_map", "select_map");
    }
    let level = crate::online::level(core);
    if online_menu_pending(core) {
        return if level >= 2 {
            ("room", "room")
        } else {
            ("online_menu", "online_menu")
        };
    }
    if crate::branding::title_up(core) {
        return ("title", "title");
    }
    if crate::campaign_menu::on_select_mode(core) {
        return ("select_mode", "select_mode");
    }
    if ml == 0 {
        return ("boot", "between_screens");
    }
    ("menu", "other")
}

fn online_menu_pending(core: &Core) -> bool {
    crate::online_menu::menu_proc(core).is_some()
}

fn rules_record(core: &Core) -> u32 {
    if crate::five::active(core) {
        0x0203_0300
    } else {
        0x0201_7C50
    }
}

/// The menu list the game keeps while a menu is up (the map menu's, or a submenu's: the Intel and Options pages reuse it).
fn menu_list(core: &Core) -> Option<Vec<u8>> {
    if core.raw_read_8(MAP_MENU_STATE, -1) != 4 || core.raw_read_8(MAP_MENU_ITEMS - 1, -1) != 0xFF {
        return None;
    }
    let items: Vec<u8> = (0..8u32)
        .map(|r| core.raw_read_8(MAP_MENU_ITEMS + r, -1))
        .take_while(|&i| i != 0xFF)
        .collect();
    (!items.is_empty()).then_some(items)
}

/// The map menu's item ids (0 CO, 1 Intel, 2 Power, 3 Super, 4 Options, 5 Save, 6 End) while the main menu is up (the one
/// that has End: a submenu's list is not it).
pub fn map_menu_items(core: &Core) -> Option<Vec<u8>> {
    menu_list(core).filter(|items| items.contains(&6))
}

/// Every menu the game has up (its menu procs): the map menu, a unit's command menu, the Intel and Options lists. Rows are
/// `{id, text, enabled}` in the order shown; `cursor` is the row the hand is on.
pub fn menus(core: &Core) -> Vec<Value> {
    use crate::ds_menus as m;
    let mut out = Vec::new();
    for i in 0..m::SLOT_COUNT {
        let slot = m::SLOTS + m::SLOT_SIZE * i;
        if core.raw_read_32(slot, -1) != m::MENU_SCRIPT {
            continue;
        }
        let count = core.raw_read_8(slot + 0x41, -1) as usize;
        if count == 0 || count > 12 {
            continue;
        }
        let table = core.raw_read_32(slot + 0x20, -1);
        let kind = if table == core.raw_read_32(m::UNIT_MENU_POOL, -1) {
            "unit"
        } else if table == core.raw_read_32(m::MAP_MENU_POOL, -1) {
            "map"
        } else {
            "other"
        };
        let rows: Vec<Value> = (0..count as u32)
            .map(|k| {
                let idx = core.raw_read_8(slot + 0x31 + k, -1) as u32;
                let tid = core.raw_read_16(table + m::ENTRY * idx + 0x1C, -1);
                let (_, _, text) = m::parse_label(&m::label(core, tid));
                let flags = core.raw_read_8(slot + 0x24 + idx, -1);
                json!({"id": idx, "text": text, "enabled": flags & 2 == 0})
            })
            .collect();
        let cursor = (core.raw_read_8(slot + 0x42, -1) as usize).min(count - 1);
        out.push(json!({"kind": kind, "cursor": cursor, "item": rows[cursor]["text"], "rows": rows}));
    }
    out
}

/// The cursor's cell at the last look at the plain map (x, then y << 16), kept for the production menu.
static LAST_MAP_CURSOR: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);

/// The production menu (a base, airport or port), when it is up: the buildable units in the order shown, each with its price
/// and whether the active army can pay it (the game greys the rest), and the row the hand is on. The menu is a proc
/// (`0x0802DA19`) whose halfword at +0x20 indexes the game's full build list ([`crate::roster`]'s `BUILD_LIST_POINTER`); the rows are that
/// list's units whose domain the property builds (a base: ground; an airport: air; a port: sea).
pub fn build_menu(core: &Core) -> Option<Value> {
    const AREA: u32 = 0x0300_0C00;
    const LIST_POINTER: u32 = 0x0809_0C08;
    let mut b = vec![0u8; 0x1300];
    core.raw_read_range(AREA, -1, &mut b);
    let proc_at = (8..b.len() - 4).step_by(4).find(|&i| {
        let w = |o: usize| u32::from_le_bytes([b[o], b[o + 1], b[o + 2], b[o + 3]]);
        w(i) == 0x0802_DA19
            && (0x0840_0000..0x0870_0000).contains(&w(i - 8))
            && (0x0840_0000..0x0870_0000).contains(&w(i - 4))
    })?;
    let base = AREA + proc_at as u32 - 8;
    let index = core.raw_read_16(base + 0x20, -1) as usize;
    let list_ptr = core.raw_read_32(LIST_POINTER, -1);
    let list: Vec<u8> = (0..64u32)
        .map(|k| core.raw_read_8(list_ptr + k, -1))
        .take_while(|&t| t != 0xFF)
        .collect();
    // (the cell the cursor was last on while the plain map showed: the property the menu belongs to; the game parks the cursor
    // elsewhere while a menu is up)
    let at = LAST_MAP_CURSOR.load(std::sync::atomic::Ordering::Relaxed);
    let (cx, cy) = ((at & 0xFFFF) as i32, (at >> 16) as i32);
    let h = core.raw_read_16(MAP + 2, -1) as u32;
    let class = if cy >= 0 && (cy as u32) < h && cx >= 0 {
        core.raw_read_8(
            TERRAIN + core.raw_read_16(ROWS + 2 * cy as u32, -1) as u32 + cx as u32,
            -1,
        ) & 0x1F
    } else {
        0
    };
    let mask: u8 = match class {
        14 => 0x0F,
        10 => 0x10,
        11 => 0x20,
        _ => 0xFF,
    };
    let army = crate::pvp::current_army(core) as u32;
    let funds = if (1..=5).contains(&army) {
        core.raw_read_32(crate::tag::player(core, army), -1)
    } else {
        0
    };
    let table = crate::roster::table(core);
    let mut rows = Vec::new();
    let mut cursor = 0usize;
    for (i, &t) in list.iter().enumerate() {
        let domain = core.raw_read_8(table + 0x5C * t as u32 + 0x1A, -1);
        if domain & mask == 0 || (domain == 8 && !crate::cpu_tactics::next_to_pipes(core, cx, cy)) {
            continue;
        }
        if i <= index {
            cursor = rows.len();
        }
        let cost = core.raw_read_16(table + 0x5C * t as u32 + 6, -1) as u32 * 10;
        rows.push(json!({"id": t, "text": unit_name(t), "cost": cost, "enabled": funds >= cost}));
    }
    Some(
        json!({"kind": "build", "property": property_name(class), "cursor": cursor, "item": rows.get(cursor).map(|r| r["text"].clone()), "funds": funds, "rows": rows}),
    )
}

fn menu_item_name(id: u8) -> &'static str {
    match id {
        0 => "CO",
        1 => "Intel",
        2 => "Power",
        3 => "Super",
        4 => "Options",
        5 => "Save",
        6 => "End",
        _ => "?",
    }
}

/// Decodes the console. `online` is whether this is a netplay console (the room's metadata is then read).
pub fn snapshot(core: &Core, online: bool) -> Snapshot {
    let (phase, screen) = classify(core, online);
    let in_battle = crate::pvp::in_battle(core) && (1..=5).contains(&crate::pvp::current_army(core));
    let main_loop = core.raw_read_32(MAIN_LOOP, -1);
    if screen == "map" {
        LAST_MAP_CURSOR.store(
            core.raw_read_16(CURSOR, -1) as u32 | (core.raw_read_16(CURSOR + 2, -1) as u32) << 16,
            std::sync::atomic::Ordering::Relaxed,
        );
    }
    let mut s = Snapshot {
        frame: core.frame_counter(),
        online,
        phase,
        screen,
        main_loop,
        in_battle,
        turn_ended: false,
        decided: false,
        winner: None,
        active_army: 0,
        active_seat: None,
        mine: false,
        day: core.raw_read_16(DAY, -1),
        fog: core.raw_read_8(PLAY_ST + 0x0D, -1) != 0,
        weather: core.raw_read_8(crate::ds_weather::WEATHER, -1),
        powers_on: core.raw_read_8(PLAY_ST + 0x07, -1) != 0,
        abilities_on: core.raw_read_8(PLAY_ST + 0x08, -1) != 0,
        game_mode: core.raw_read_8(PLAY_ST + 0x01, -1),
        map_id: core.raw_read_8(MAP_SELECTED, -1),
        map_name: None,
        width: 0,
        height: 0,
        cursor: (core.raw_read_16(CURSOR, -1), core.raw_read_16(CURSOR + 2, -1)),
        camera: (
            core.raw_read_16(MAP + 4, -1) as i16,
            core.raw_read_16(MAP + 6, -1) as i16,
        ),
        menu: Value::Null,
        selected_unit: None,
        armies: Vec::new(),
        units: Vec::new(),
        properties: Vec::new(),
        flags: flags(core),
        online_info: Value::Null,
        select_map: Value::Null,
    };
    let players = crate::online::room_players();
    let me = crate::online::room_local_seat();
    if in_battle {
        let army = crate::pvp::current_army(core);
        s.active_army = army;
        s.turn_ended = crate::pvp::turn_ended(core);
        s.decided = crate::result_view::decided(core);
        s.winner = crate::result_view::winner(core).filter(|_| s.decided);
        let seat = if online {
            crate::pvp::seat_of_n(army, players)
        } else {
            0
        };
        s.active_seat = Some(seat);
        s.mine = !online || seat == me;
        s.menu = menu_json(core);
        s.map_name = Some(crate::unranked::map_name(core, s.map_id));
        let (w, h) = (core.raw_read_16(MAP, -1) as u32, core.raw_read_16(MAP + 2, -1) as u32);
        if (1..=64).contains(&w) && (1..=64).contains(&h) {
            s.width = w;
            s.height = h;
            read_board(core, &mut s, online, players);
        }
        let ptr = core.raw_read_32(SELECTED_UNIT, -1);
        let base = core.raw_read_32(UNITS_POINTER, -1);
        if ptr >= base && (ptr - base) % UNIT == 0 && ptr != base {
            let id = (ptr - base) / UNIT;
            if id < 320 && core.raw_read_8(ptr, -1) != 0 {
                s.selected_unit = Some(id);
            }
        }
    } else if phase == "select_mode" {
        let w = crate::campaign_menu::wheel_info(core);
        s.select_map = json!({"wheel_position": w.map(|w| w.0), "wheel_item": w.map(|w| w.1), "box_open": w.map(|w| w.2),
            "items": "item ids: 0 Campaign, 1 Versus, 2 Battle Maps, 3 Design Room, 4 Online, 5 War Room, 8 Survival"});
    } else if matches!(phase, "select_map" | "army_select" | "rules") {
        s.map_name = Some(crate::unranked::map_name(core, s.map_id));
        s.select_map = json!({
            "list_cursor": crate::online::probe::LIST_DEBUG.load(std::sync::atomic::Ordering::Relaxed) & 0xFF,
            "picking": crate::unranked::picking(core),
            "picks_made": crate::unranked::picks_made(core),
            "chosen": crate::unranked::chosen(core),
        });
    }
    s.online_info = online_json(core, online, players, me);
    s
}

fn flags(core: &Core) -> Value {
    json!({
        "online_menu": crate::online_menu::menu_proc(core).is_some(),
        "select_mode": crate::campaign_menu::on_select_mode(core),
        "selecting_map": crate::survival_ui::selecting(core),
        "teams_screen": crate::pvp::on_teams_screen(core),
        "versus": crate::pvp::in_versus(core),
        "rules_up": crate::unranked::rules_up(core),
        "map_idle": crate::survival_ui::idle(core),
        "plain_map": crate::fog_view::plain_map(core),
        "online_level": crate::online::level(core),
    })
}

fn menu_json(core: &Core) -> Value {
    let items = map_menu_items(core);
    let raw = menu_list(core);
    let cursor_row = core.raw_read_8(MAP_MENU_CURSOR, -1);
    let menus = menus(core);
    let build = build_menu(core);
    // The menu the player is in, in one shape: `kind` (map, unit, build, other), `rows` [{id, text, enabled, cost?}], `cursor`
    // (the row index), `item` (its text).
    let (kind, rows, cursor) = if let Some(b) = build.as_ref() {
        ("build", b["rows"].clone(), b["cursor"].clone())
    } else if let Some(m) = menus.iter().find(|m| m["kind"] == "unit") {
        ("unit", m["rows"].clone(), m["cursor"].clone())
    } else if let Some(v) = items.as_ref() {
        let rows: Vec<Value> = v
            .iter()
            .map(|&i| json!({"id": i, "text": menu_item_name(i), "enabled": true}))
            .collect();
        ("map", Value::Array(rows), json!(cursor_row))
    } else if let Some(m) = menus.first() {
        ("other", m["rows"].clone(), m["cursor"].clone())
    } else {
        ("", Value::Null, Value::Null)
    };
    let item = rows
        .get(cursor.as_u64().unwrap_or(u64::MAX) as usize)
        .map(|r| r["text"].clone())
        .unwrap_or(Value::Null);
    json!({
        "open": items.is_some(),
        "kind": if kind.is_empty() { Value::Null } else { json!(kind) },
        "rows": rows,
        "cursor": cursor,
        "state": core.raw_read_8(MAP_MENU_STATE, -1),
        "cursor_row": cursor_row,
        "items": items.as_ref().map(|v| v.iter().map(|&i| menu_item_name(i)).collect::<Vec<_>>()),
        "item_ids": items,
        "item": if items.is_some() { items.as_ref().and_then(|v| v.get(cursor_row as usize).map(|&i| json!(menu_item_name(i)))).unwrap_or(Value::Null) } else { item },
        "end_row": core.raw_read_8(crate::pvp::END_ROW, -1) & 0xF,
        "list_ids": raw,
        "menus": menus,
        "build": build,
    })
}

fn read_board(core: &Core, s: &mut Snapshot, online: bool, players: usize) {
    let (w, h) = (s.width, s.height);
    let rows = row_offsets(core, h);
    let five = crate::five::active(core);
    let army_of = |id: u32| if five { id / 51 + 1 } else { id / 64 + 1 };
    let base = core.raw_read_32(UNITS_POINTER, -1);
    let mut recs = vec![0u8; 320 * UNIT as usize];
    core.raw_read_range(base, -1, &mut recs);
    // terrain plane
    let mut owner_cells: Vec<(i32, i32, u8, u8)> = Vec::new();
    for y in 0..h {
        for x in 0..w {
            let t = core.raw_read_8(TERRAIN + rows[y as usize] + x, -1);
            let class = t & 0x1F;
            if property_name(class).is_some() {
                owner_cells.push((x as i32, y as i32, class, (t >> 5) % 6));
            }
        }
    }
    // units
    let mut by_cell: BTreeMap<(i32, i32), u32> = BTreeMap::new();
    for id in 1..256u32 {
        let r = &recs[(id * UNIT) as usize..((id + 1) * UNIT) as usize];
        if r[0] == 0 {
            continue;
        }
        let owner = army_of(id);
        if !(1..=5).contains(&owner) {
            continue;
        }
        let word = u16::from_le_bytes([r[4], r[5]]);
        let u = UnitInfo {
            id,
            owner: owner as u8,
            kind: r[0],
            x: r[2] as i32,
            y: r[3] as i32,
            hp: (word & 0x7F) as u32,
            fuel: r[6],
            ammo: ((word >> 7) & 0xF) as u8,
            flags: r[1],
            capture: ((word >> 11) & 0x1F) as u8,
            cargo: Vec::new(),
        };
        if !u.carried() {
            by_cell.insert((u.x, u.y), id);
        }
        s.units.push(u);
    }
    // cargo: a carried unit rides the transport on the cell it is recorded at
    let carried: Vec<(u32, i32, i32)> = s
        .units
        .iter()
        .filter(|u| u.carried())
        .map(|u| (u.id, u.x, u.y))
        .collect();
    for (id, x, y) in carried {
        if let Some(&t) = by_cell.get(&(x, y)) {
            if let Some(tu) = s.units.iter_mut().find(|u| u.id == t) {
                tu.cargo.push(id);
            }
        }
    }
    for (x, y, class, owner) in owner_cells {
        let capture = by_cell
            .get(&(x, y))
            .and_then(|id| s.units.iter().find(|u| u.id == *id))
            .map_or(0, |u| u.capture);
        s.properties.push(PropertyInfo {
            x,
            y,
            class,
            owner,
            capture,
        });
    }
    let n = crate::five::armies(core).clamp(2, 5);
    for a in 1..=n {
        let p = crate::tag::player(core, a as u32);
        let co = crate::tag::army_co_of(core, a as u32);
        let uses = core.raw_read_8(p + 0x25, -1);
        let (cop, scop) = (
            crate::tag::cop_cost(core, co, uses),
            crate::tag::scop_cost(core, co, uses),
        );
        s.armies.push(ArmyInfo {
            army: a,
            colour: core.raw_read_8(p + 0x1A, -1),
            colour_name: crate::army_skin::colour_name(core, core.raw_read_8(p + 0x1A, -1)).to_string(),
            controller: core.raw_read_8(p + 0x1B, -1),
            co,
            co_name: crate::co_new::ds_name(co).map(|t| {
                t.iter()
                    .filter(|c| (0x20..0x7F).contains(*c))
                    .map(|&c| c as char)
                    .collect()
            }),
            partner: crate::tag::partner(core, a as u32),
            funds: core.raw_read_32(p, -1),
            meter: core.raw_read_32(p + 0x20, -1),
            power_cost: cop,
            super_cost: scop,
            power_mode: core.raw_read_8(p + 0x1E, -1),
            powers_used: uses,
            team: core.raw_read_8(p + 0x2A, -1),
            alive: crate::result_view::alive(core, a),
            seat: online.then(|| crate::pvp::seat_of_n(a, players)),
            units: s.units.iter().filter(|u| u.owner == a && !u.carried()).count() as u32,
            properties: s.properties.iter().filter(|q| q.owner == a).count() as u32,
        });
    }
}

/// The in-game lobby's mailbox (the room page the app writes): its status byte, the players with their ready and flag bytes.
fn lobby_json(core: &Core) -> Value {
    let mut read = |a: u32, b: &mut [u8]| core.raw_read_range(a, -1, b);
    let status = crate::online::mailbox::status(&mut read);
    let players = crate::online::mailbox::players(&mut read);
    json!({
        "status": status, "status_names": "0 none, 1 waiting, 2 connecting, 3 connected, 4 failed, 5 back",
        "players": players.iter().map(|&(ready, flags)| json!({"ready": ready, "flags": flags, "host": flags & crate::online::HOST != 0, "you": flags & crate::online::YOU != 0})).collect::<Vec<_>>(),
        "menu_cursor": crate::online_menu::cursor(core),
        "message": lobby_message(core),
    })
}

fn lobby_message(core: &Core) -> String {
    (0..crate::online::MESSAGE_LEN)
        .map(|k| core.raw_read_8(crate::online::MESSAGE + k, -1))
        .take_while(|&c| c != 0)
        .filter(|c| (0x20..0x7F).contains(c))
        .map(|c| c as char)
        .collect()
}

/// The cues a pad script waits on (`TANGOAW2_PAD_SCRIPT`'s `until`), as booleans.
fn cues_json() -> Value {
    let c = crate::online::probe::CUES.load(std::sync::atomic::Ordering::Relaxed);
    let pick = (c >> 8) & 0xF;
    json!({
        "myturn": c & 1 != 0, "banner": c & 2 != 0, "acting": c & 4 != 0, "over": c & 8 != 0, "mapup": c & 16 != 0,
        "mypick": c & 32 != 0, "chosen": c & 64 != 0, "rules": c & 128 != 0,
        "picks_made": if pick > 0 { json!(pick - 1) } else { Value::Null },
    })
}

fn online_json(core: &Core, online: bool, players: usize, me: usize) -> Value {
    let named = crate::online::room_named();
    if !online && named == 0 {
        return json!({"room": false, "sim_version": SIM_VERSION, "level": crate::online::level(core), "lobby": lobby_json(core)});
    }
    let names: Vec<String> = (0..players).map(crate::online::room_name).collect();
    let picks = crate::online::room_picks();
    use tango_backend_mgba::SharedGame as _;
    let out = if crate::pvp::in_battle(core) {
        crate::pvp::AW2E.seats_out(core)
    } else {
        0
    };
    json!({
        "room": named > 0,
        "seats_out": (0..8).filter(|s| out & (1 << s) != 0).collect::<Vec<_>>(),
        "roster_order": crate::online::room_seats(),
        "players": players,
        "local_seat": me,
        "gamertags": names,
        "picks": picks.iter().map(|&(team, colour)| json!({"team": team, "colour": colour})).collect::<Vec<_>>(),
        "sim_version": SIM_VERSION,
        "level": crate::online::level(core),
        "lobby": lobby_json(core),
    })
}

impl Snapshot {
    /// The `state` answer's body.
    pub fn to_json(&self) -> Value {
        let mut m = Map::new();
        let mut put = |k: &str, v: Value| {
            m.insert(k.to_string(), v);
        };
        put("frame", json!(self.frame));
        put("mode", json!(if self.online { "online" } else { "offline" }));
        put("phase", json!(self.phase));
        put("screen", json!(self.screen));
        put("main_loop", json!(format!("0x{:08X}", self.main_loop)));
        put("in_battle", json!(self.in_battle));
        put("active_army", json!(self.active_army));
        put("active_seat", json!(self.active_seat));
        put("mine", json!(self.mine));
        put("day", json!(self.day));
        put("turn", json!(self.day));
        put("turn_ended", json!(self.turn_ended));
        put("decided", json!(self.decided));
        put("winner", json!(self.winner));
        put(
            "rules",
            json!({
                "fog": self.fog, "weather": weather_name(self.weather), "weather_id": self.weather,
                "powers": self.powers_on, "abilities": self.abilities_on, "game_mode": self.game_mode,
            }),
        );
        put(
            "map",
            json!({"id": self.map_id, "name": self.map_name, "w": self.width, "h": self.height}),
        );
        put("cursor", json!({"x": self.cursor.0, "y": self.cursor.1}));
        put("camera", json!({"px": self.camera.0, "py": self.camera.1}));
        put("menu", self.menu.clone());
        put("selected_unit", json!(self.selected_unit));
        put(
            "armies",
            Value::Array(
                self.armies
                    .iter()
                    .map(|a| {
                        json!({
                            "army": a.army, "colour": a.colour, "colour_name": a.colour_name, "controller": a.controller, "co": a.co, "co_name": a.co_name,
                            "partner": a.partner, "funds": a.funds, "power_meter": a.meter, "power_cost": a.power_cost,
                            "super_cost": a.super_cost, "power_mode": a.power_mode, "powers_used": a.powers_used,
                            "team": a.team, "alive": a.alive, "seat": a.seat, "units": a.units, "properties": a.properties,
                        })
                    })
                    .collect(),
            ),
        );
        put("units", Value::Array(self.units.iter().map(UnitInfo::json).collect()));
        put(
            "properties",
            Value::Array(
                self.properties
                    .iter()
                    .map(|p| {
                        json!({"x": p.x, "y": p.y, "type": p.class, "name": property_name(p.class), "owner": p.owner, "capture": p.capture})
                    })
                    .collect(),
            ),
        );
        put("flags", self.flags.clone());
        put("cues", cues_json());
        put("online", self.online_info.clone());
        put("screen_info", self.select_map.clone());
        Value::Object(m)
    }
}

/// The events between two looks at the console (ten times a second): the scene and turn changes and the acts, as
/// [`crate::run_dump`] reads them (a unit built, moved, hit, destroyed, loaded or unloaded; a property taken; a
/// power; an army out).
pub fn events(prev: &Snapshot, now: &Snapshot) -> Vec<Value> {
    let mut out = Vec::new();
    if prev.phase != now.phase || prev.screen != now.screen {
        out.push(json!({"event": "scene", "phase": now.phase, "screen": now.screen, "from_phase": prev.phase, "from_screen": prev.screen}));
    }
    if !(prev.in_battle && now.in_battle) {
        return out;
    }
    if prev.active_army != now.active_army || prev.day != now.day {
        out.push(json!({"event": "turn", "army": now.active_army, "seat": now.active_seat, "day": now.day}));
    }
    let old: BTreeMap<u32, &UnitInfo> = prev.units.iter().map(|u| (u.id, u)).collect();
    let new: BTreeMap<u32, &UnitInfo> = now.units.iter().map(|u| (u.id, u)).collect();
    let act = |what: &str, actor: u8, u: &UnitInfo, extra: Value| {
        let mut v = json!({"event": "act", "what": what, "actor": actor, "unit": u.kind, "name": unit_name(u.kind), "id": u.id, "owner": u.owner, "to": [u.x, u.y], "hp": u.hp});
        if let (Some(m), Some(e)) = (v.as_object_mut(), extra.as_object()) {
            for (k, x) in e {
                m.insert(k.clone(), x.clone());
            }
        }
        v
    };
    for (id, u) in &new {
        match old.get(id) {
            None if !u.carried() => out.push(act("build", u.owner, u, json!({}))),
            None => {}
            Some(o) => {
                if (o.x, o.y) != (u.x, u.y) && !u.carried() && !o.carried() {
                    out.push(act("move", u.owner, u, json!({"from": [o.x, o.y]})));
                } else if u.hp < o.hp {
                    out.push(act("attack", now.active_army, u, json!({"hp_before": o.hp})));
                }
                if u.carried() && !o.carried() {
                    out.push(act("load", u.owner, u, json!({})));
                }
                if !u.carried() && o.carried() {
                    out.push(act("unload", u.owner, u, json!({})));
                }
            }
        }
    }
    for (id, o) in &old {
        if !new.contains_key(id) {
            out.push(act("kill", now.active_army, o, json!({"hp_before": o.hp})));
        }
    }
    let owners = |s: &Snapshot| {
        s.properties
            .iter()
            .map(|p| ((p.x, p.y), p.owner))
            .collect::<BTreeMap<_, _>>()
    };
    let (po, pn) = (owners(prev), owners(now));
    for (cell, o) in &pn {
        if let Some(old) = po.get(cell) {
            if old != o {
                out.push(
                    json!({"event": "act", "what": "capture", "actor": o, "to": [cell.0, cell.1], "from_owner": old}),
                );
            }
        }
    }
    for (a, b) in prev.armies.iter().zip(now.armies.iter()) {
        if a.alive && !b.alive {
            out.push(json!({"event": "act", "what": "eliminated", "actor": b.army}));
        }
        if b.powers_used > a.powers_used || (b.power_mode != 0 && a.power_mode == 0) {
            out.push(
                json!({"event": "act", "what": "power", "actor": b.army, "count": b.powers_used, "mode": b.power_mode}),
            );
        }
    }
    out
}

/// The vision plane the game displays now (`1` seen, `0` fogged), row by row.
pub fn seen_plane(core: &Core, w: u32, h: u32) -> String {
    let rows = row_offsets(core, h);
    let mut out = String::with_capacity((w * h) as usize);
    for y in 0..h {
        for x in 0..w {
            out.push(if core.raw_read_8(MAP + 0x234A + rows[y as usize] + x, -1) != 0 {
                '1'
            } else {
                '0'
            });
        }
    }
    out
}

/// A short hash of the console's two RAMs (the same FNV-1a that [`crate::run_dump`] logs as `hash`).
pub fn ram_hash(core: &Core) -> u64 {
    let mut iw = vec![0u8; 0x8000];
    core.raw_read_range(0x0300_0000, -1, &mut iw);
    let mut ew = vec![0u8; 0x40000];
    core.raw_read_range(0x0200_0000, -1, &mut ew);
    let mut h: u64 = 0xcbf29ce484222325;
    for b in iw.iter().chain(ew.iter()) {
        h = (h ^ *b as u64).wrapping_mul(0x100000001b3);
    }
    h
}

#[cfg(test)]
mod tests {
    use super::*;

    fn snap(units: Vec<UnitInfo>) -> Snapshot {
        Snapshot {
            frame: 0,
            online: false,
            phase: "battle",
            screen: "map",
            main_loop: 0,
            in_battle: true,
            turn_ended: false,
            decided: false,
            winner: None,
            active_army: 1,
            active_seat: Some(0),
            mine: true,
            day: 1,
            fog: false,
            weather: 0,
            powers_on: true,
            abilities_on: true,
            game_mode: 3,
            map_id: 0,
            map_name: None,
            width: 10,
            height: 10,
            cursor: (0, 0),
            camera: (0, 0),
            menu: Value::Null,
            selected_unit: None,
            armies: Vec::new(),
            units,
            properties: Vec::new(),
            flags: Value::Null,
            online_info: Value::Null,
            select_map: Value::Null,
        }
    }

    fn unit(id: u32, x: i32, y: i32, hp: u32) -> UnitInfo {
        UnitInfo {
            id,
            owner: 1,
            kind: 1,
            x,
            y,
            hp,
            fuel: 99,
            ammo: 0,
            flags: 0,
            capture: 0,
            cargo: vec![],
        }
    }

    #[test]
    fn events_tell_a_move_a_hit_a_kill_and_a_build() {
        let a = snap(vec![unit(1, 0, 0, 100), unit(2, 3, 3, 100), unit(3, 5, 5, 100)]);
        let b = snap(vec![unit(1, 1, 0, 100), unit(2, 3, 3, 60), unit(4, 7, 7, 100)]);
        let ev = events(&a, &b);
        let what: Vec<&str> = ev.iter().filter_map(|e| e["what"].as_str()).collect();
        assert!(
            what.contains(&"move") && what.contains(&"attack") && what.contains(&"kill") && what.contains(&"build"),
            "{what:?}"
        );
    }

    #[test]
    fn a_scene_change_is_an_event() {
        let a = snap(vec![]);
        let mut b = snap(vec![]);
        b.screen = "map_menu";
        let ev = events(&a, &b);
        assert_eq!(ev[0]["event"], "scene");
        assert_eq!(ev[0]["screen"], "map_menu");
    }

    #[test]
    fn the_unit_list_is_json() {
        let s = snap(vec![unit(1, 2, 3, 80)]);
        let j = s.to_json();
        assert_eq!(j["units"][0]["x"], 2);
        assert_eq!(j["units"][0]["name"], "Infantry");
        assert_eq!(j["phase"], "battle");
    }
}
