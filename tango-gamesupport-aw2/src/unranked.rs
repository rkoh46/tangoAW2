//! The map proposals of every online match, and UNRANKED (a match against a random opponent, made by the app's
//! pool: [`crate::online`], `tango_lobby::room`).
//!
//! The netplay console of a match walks to Versus' SELECT MAP (the game's mode wheel is never played), and there
//! every player proposes a map in turn ([`active`]: rooms and UNRANKED alike; the room's players are 2..5). In an
//! UNRANKED match ([`crate::online::UNRANKED_MATCH`] in its subtype, [`on`]) the rules are the standard ones as well;
//! in a room the host plays the Rules screen. The steps:
//!
//! 1. **Picks.** The game's own SELECT MAP (its tabs for the room's count, "3P" and "3P Predeploy", the list, the
//!    picture and the counters: [`crate::online_maps`] shows only the maps for as many armies as there are players)
//!    is played by the players one after the other: seat 0 first, then seat 1 and so on. While a seat picks, only its
//!    keys reach the game ([`merge`]; A, B and START are kept from it: A is the pick, recorded by [`tick`] from the
//!    map under the cursor) and the others watch the same screen with "Waiting for the others..." in the bar.
//! 2. **The draw.** When every seat has picked, one of the maps is the match's: the seat is drawn from a free-running
//!    frame counter at the last pick (the console is the same on every peer, so the draw is too, also in a replay and
//!    a rollback). The map is then walked to in the game's list by pressing for the players ([`drive`]) and chosen
//!    with A; the bar says whose map is played.
//! 3. **Armies.** Versus' Teams screen is the room's usual one ([`crate::online_teams`]): CO and a colour no other
//!    army has, no partner (tag pairs are off).
//! 4. **Rules.** UNRANKED: the Rules screen is not played, [`rules`] writes the standard rules into its rows and
//!    presses A ([`RULES`] says which). A room's host plays it.
//! 5. **Battle**, then the results, and the match ends back at SELECT MAP ([`crate::online::match_over`]; UNRANKED
//!    logs `unranked: the match ended`). A room goes on to propose again.
//!
//! The state is in EWRAM ([`STATE`]) so that rollback and replays carry it.

use crate::online::{KEY_A, KEY_B, KEY_DOWN, KEY_RIGHT, KEY_UP};
use mgba::core::Core;

pub const STATE: u32 = 0x0203_D600;
pub const STATE_LEN: u32 = 0x100;
/// 1 in an UNRANKED match.
const FLAG: u32 = STATE;
/// The seat whose proposal is the match's map (drawn when the last seat has picked).
const PICK: u32 = STATE + 1;
/// 0 picking (the seats in turn, [`PICKS`]), 1 walking to the chosen map, 2 the map is chosen (the game goes on to the armies and the rules),
/// 3 the walk failed (the host picks with the game's list).
const PHASE: u32 = STATE + 2;
const CHOSEN: u32 = STATE + 3;
/// How many seats have picked (the next to pick is seat [`PICKS`]).
const PICKS: u32 = STATE + 4;
/// 1 in every online match: the seats propose maps.
const PROPOSE: u32 = STATE + 0x0C;
/// Free-running frame counter while picking (u16, even address): the draw.
const DRAW_T: u32 = STATE + 0x0E;
/// Frames of the walk (u16, even address).
const WALK_T: u32 = STATE + 6;
/// Frames on the Rules screen.
const RULES_T: u32 = STATE + 8;
/// 1 once a battle has been played.
const BATTLED: u32 = STATE + 9;
/// Frames settled on the chosen map in the list (u8).
const SETTLED: u32 = STATE + 0x0A;
/// Test aid: a bit for each Rules row that was not the standard value when the screen came up.
const CHANGED: u32 = STATE + 0x0B;
const SEATS: u32 = STATE + 0x10;
const SEAT_SIZE: u32 = 8;
/// The most seats of a room.
const MAX_SEATS: usize = 5;
// A seat: +0 the map it picked (an id), +2 previous keys (u16).
const S_MAP: u32 = 0;
const S_PREV: u32 = 2;

/// The standard rules, written into the Rules screen's rows (see [`rules`]).
pub const RULES: &str = "Fog of war off, weather clear, funds 1000 per property, no turn limit, no capture limit, \
CO powers on, CO skills off, tag pairs off";

/// Rows of the Rules screen, in the order of its record's objects.
const R_FOG: usize = 0;
const R_WEATHER: usize = 1;
const R_FUNDS: usize = 2;
const R_TURN: usize = 3;
const R_CAPT: usize = 4;
const R_POWER: usize = 5;
const R_VISUALS: usize = 6;
/// The values the rows take (as the Rules screen's choices index them): fog off, weather clear, funds 1000 (the
/// first choice), no turn limit, no capture limit, powers on, no visuals.
const VALUES: [(usize, u8); 7] = [(R_FOG, 1), (R_WEATHER, 1), (R_FUNDS, 0), (R_TURN, 0), (R_CAPT, 0), (R_POWER, 0), (R_VISUALS, 0)];
const RULES_RECORD: u32 = 0x0201_7C50;
const RULES_RECORD_FIVE: u32 = 0x0203_0300;
const ITEM_VALUE: u32 = 0x48;
const ITEM_FN: u32 = 0x4C;
const ITEM_FNS: [u32; 6] = [0x0806_4739, 0x0806_4775, 0x0806_47BD, 0x0806_486D, 0x0806_4919, 0x0806_49D1];
const PROCS: (u32, u32) = (0x0300_1500, 0x0300_1F00);

/// Set up for an UNRANKED match (or not), once, when the console starts.
pub fn init(core: &mut Core, subtype: u8) {
    core.raw_write_range(STATE, -1, &[0u8; STATE_LEN as usize]);
    core.raw_write_8(PROPOSE, -1, 1);
    if subtype & crate::online::UNRANKED_MATCH != 0 {
        core.raw_write_8(FLAG, -1, 1);
    }
}

/// Test aid (the text audit): the picks made, both seats' maps, the phase and whose map is played.
pub fn set_state(core: &mut Core, picks: u8, maps: [u8; 2], phase: u8, pick: u8) {
    core.raw_write_8(FLAG, -1, 1);
    core.raw_write_8(PROPOSE, -1, 1);
    core.raw_write_8(PHASE, -1, phase);
    core.raw_write_8(PICK, -1, pick);
    core.raw_write_8(PICKS, -1, picks);
    core.raw_write_8(CHOSEN, -1, maps[pick as usize % 2]);
    for s in 0..2 {
        core.raw_write_8(seat(s) + S_MAP, -1, maps[s]);
    }
}

/// An UNRANKED match (standard rules, the match ends after one battle).
pub fn on(core: &Core) -> bool {
    core.raw_read_8(FLAG, -1) == 1
}

/// The seats propose maps (every online match).
pub fn active(core: &Core) -> bool {
    core.raw_read_8(PROPOSE, -1) == 1
}

/// The seat whose turn it is to propose a map (SELECT MAP is up and the seats are picking).
pub fn picking(core: &Core) -> Option<usize> {
    (active(core) && phase(core) == 0 && crate::survival_ui::selecting(core)).then(|| (core.raw_read_8(PICKS, -1) as usize).min(seats(core) - 1))
}

/// The map is drawn and SELECT MAP is still up (walking to it).
pub fn chosen(core: &Core) -> bool {
    active(core) && phase(core) == 1 && crate::survival_ui::selecting(core)
}

/// How many seats propose.
fn seats(core: &Core) -> usize {
    crate::online_teams::players(core).min(MAX_SEATS)
}

fn phase(core: &Core) -> u8 {
    core.raw_read_8(PHASE, -1)
}

fn seat(s: usize) -> u32 {
    SEATS + SEAT_SIZE * s as u32
}

/// A map's name as the game's text table has it.
pub fn map_name(core: &Core, id: u8) -> String {
    let table = crate::five_map::table(core);
    let text = core.raw_read_16(table + 0x5C * id as u32 + 0x14, -1) as u32;
    let at = core.raw_read_32(0x0861_0A38 + 4 * text, -1);
    if !(0x0800_0000..0x0A00_0000).contains(&at) {
        return format!("Map {id}");
    }
    (0..24)
        .map(|k| core.raw_read_8(at + k, -1))
        .take_while(|&c| c != 0)
        .map(|c| c as char)
        .filter(|c| (' '..='~').contains(c))
        .collect()
}

/// Every tick: the seat whose turn it is to pick, from its own keys: A picks the map under the game's cursor.
pub fn tick(core: &mut Core, inputs: &[u32]) {
    if !active(core) || inputs.len() < 2 {
        return;
    }
    let n = seats(core).min(inputs.len());
    if core.raw_read_8(BATTLED, -1) == 0 && crate::pvp::in_versus(core) && crate::pvp::in_battle(core) {
        core.raw_write_8(BATTLED, -1, 1);
    }
    // A room's battle is over and the game is back at SELECT MAP: the seats propose again.
    if !on(core) && core.raw_read_8(BATTLED, -1) == 1 && !crate::pvp::in_battle(core) && crate::survival_ui::selecting(core) {
        for k in 0..STATE_LEN {
            if !(PROPOSE - STATE..PROPOSE - STATE + 1).contains(&k) && k != 0x0E && k != 0x0F {
                core.raw_write_8(STATE + k, -1, 0);
            }
        }
    }
    // The game left the list on the chosen map: it goes on to the armies.
    if phase(core) == 1 && core.raw_read_8(SETTLED, -1) >= 10 && !crate::survival_ui::selecting(core) {
        core.raw_write_8(PHASE, -1, 2);
    }
    let was: Vec<u32> = (0..n).map(|s| core.raw_read_16(seat(s) + S_PREV, -1) as u32).collect();
    for s in 0..n {
        core.raw_write_16(seat(s) + S_PREV, -1, inputs[s] as u16);
    }
    if phase(core) != 0 || !crate::survival_ui::idle(core) {
        return;
    }
    // (counts frames while picking: the draw's randomness, the same on every peer)
    let t = core.raw_read_16(DRAW_T, -1).wrapping_add(1);
    core.raw_write_16(DRAW_T, -1, t);
    let who = (core.raw_read_8(PICKS, -1) as usize).min(n - 1);
    if inputs[who] & !was[who] & KEY_A == 0 {
        return;
    }
    // The map under the cursor (the list holds only the room's count of armies here).
    let Some(cur) = crate::online::list_cursor(core).filter(|&c| c <= 0x31) else {
        return;
    };
    let id = core.raw_read_8(crate::online::LIST_IDS + cur, -1);
    // (id 0 is Five Seas, a map: it counts when the game lists it, on one of the room's tabs)
    if id == 0 && !matches!(core.raw_read_16(crate::five_map::table(core) + 0x1A, -1), 2 | 4) {
        return;
    }
    core.raw_write_8(seat(who) + S_MAP, -1, id);
    core.raw_write_8(PICKS, -1, who as u8 + 1);
    if who + 1 == n {
        // (the frame counter and the maps proposed, mixed)
        let mix = (0..n).fold(t as usize, |a, k| a.wrapping_mul(31).wrapping_add(core.raw_read_8(seat(k) + S_MAP, -1) as usize));
        let from = mix % n;
        core.raw_write_8(PICK, -1, from as u8);
        let map = core.raw_read_8(seat(from) + S_MAP, -1);
        core.raw_write_8(CHOSEN, -1, map);
        core.raw_write_8(SETTLED, -1, 0);
        core.raw_write_16(WALK_T, -1, 0);
        core.raw_write_8(PHASE, -1, 1);
    }
}

/// Which keys reach the game: the picking seat's while the maps are picked, none while the map is walked to, none on the Rules screen of
/// an UNRANKED match, and after the battle both players'.
pub fn merge(core: &Core, inputs: &[u32]) -> Option<u32> {
    if !active(core) {
        return None;
    }
    if phase(core) == 0 && crate::survival_ui::selecting(core) {
        // (the seat picking has the pad, but A, B and START: A is its pick, there is no way back from here)
        let who = (core.raw_read_8(PICKS, -1) as usize).min(seats(core).min(inputs.len()).max(1) - 1);
        return Some(inputs.get(who).copied().unwrap_or(0) & !(KEY_A | KEY_B | crate::online::KEY_START));
    }
    if phase(core) < 3 && crate::survival_ui::selecting(core) {
        return Some(0);
    }
    if on(core) && rules_rows(core).is_some() {
        return Some(0);
    }
    if on(core) && core.raw_read_8(BATTLED, -1) == 1 && !crate::pvp::in_battle(core) {
        return Some(inputs.iter().fold(0, |a, &b| a | b));
    }
    None
}

/// The keys that walk SELECT MAP's list to the chosen map and choose it. Returns the keys the game gets.
pub fn drive(core: &mut Core, keys: u32) -> u32 {
    if !active(core) || phase(core) != 1 || !crate::survival_ui::idle(core) {
        return keys;
    }
    let t = core.raw_read_16(WALK_T, -1).wrapping_add(1);
    core.raw_write_16(WALK_T, -1, t);
    if t > 4000 {
        core.raw_write_8(PHASE, -1, 3);
        return keys;
    }
    let target = core.raw_read_8(CHOSEN, -1);
    let table = crate::five_map::table(core);
    let tab_of = |core: &Core, id: u8| core.raw_read_16(table + 0x5C * id as u32 + 0x1A, -1);
    let ids = crate::online::LIST_IDS;
    let Some(cur) = crate::online::list_cursor(core).filter(|&c| c <= 0x31) else {
        return 0;
    };
    // The list is the tab's maps: the first id's tab is the one shown.
    let list_tab = tab_of(core, core.raw_read_8(ids, -1));
    if core.raw_read_8(ids + cur, -1) == target {
        // (settled on it for a few frames, then A)
        let was = core.raw_read_8(SETTLED, -1);
        let settled = if was >= 200 { 34 } else { was + 1 };
        core.raw_write_8(SETTLED, -1, settled);
        // (A for 4 frames of 12, until the game leaves the list)
        return if settled >= 100 && settled % 12 < 4 { KEY_A } else { 0 };
    }
    core.raw_write_8(SETTLED, -1, 0);
    if tab_of(core, target) != list_tab {
        return if t % 30 < 4 { KEY_RIGHT } else { 0 };
    }
    let mut at = None;
    for i in 0..=0x31u32 {
        let id = core.raw_read_8(ids + i, -1);
        if tab_of(core, id) != list_tab {
            break;
        }
        if id == target {
            at = Some(i);
            break;
        }
    }
    match at {
        Some(i) if i > cur => {
            if t % 8 < 3 {
                KEY_DOWN
            } else {
                0
            }
        }
        Some(_) => {
            if t % 8 < 3 {
                KEY_UP
            } else {
                0
            }
        }
        None => {
            // (not in the list: another tab may have it)
            if t % 30 < 4 {
                KEY_RIGHT
            } else {
                0
            }
        }
    }
}

// --- The Rules screen --------------------------------------------------------------------------------------

fn record(core: &Core) -> u32 {
    if crate::five::active(core) {
        RULES_RECORD_FIVE
    } else {
        RULES_RECORD
    }
}

/// The Rules screen's rows (the record's objects), while that screen is up after the map was chosen.
fn rules_rows(core: &Core) -> Option<[u32; 7]> {
    if phase(core) != 2
        || !crate::pvp::in_versus(core)
        || crate::pvp::in_battle(core)
        || crate::survival_ui::selecting(core)
        || crate::online_teams::active(core)
    {
        return None;
    }
    let rec = record(core);
    let mut rows = [0u32; 7];
    for (k, row) in rows.iter_mut().enumerate() {
        let p = core.raw_read_32(rec + 0x54 + 4 * k as u32, -1);
        if !(PROCS.0..PROCS.1).contains(&p) {
            return None;
        }
        *row = p;
    }
    ITEM_FNS.contains(&core.raw_read_32(rows[0] + ITEM_FN, -1)).then_some(rows)
}

/// The standard rules, on the Rules screen: the rows' values written every frame, and A pressed once they have
/// shown for a moment. Returns the keys the game gets.
pub fn rules(core: &mut Core, keys: u32) -> u32 {
    if !on(core) {
        return keys;
    }
    let Some(rows) = rules_rows(core) else {
        return keys;
    };
    for (k, v) in VALUES {
        if core.raw_read_8(rows[k] + ITEM_VALUE, -1) != v {
            core.raw_write_8(rows[k] + ITEM_VALUE, -1, v);
            // (a test aid: which rows were not the standard ones, a bit each)
            let seen = core.raw_read_8(CHANGED, -1);
            core.raw_write_8(CHANGED, -1, seen | 1 << k);
        }
    }
    // (Dual Strike's Skills row, when the pack has it)
    if core.raw_read_8(crate::co_skills::VERSUS_RULE, -1) != 0 {
        core.raw_write_8(crate::co_skills::VERSUS_RULE, -1, 0);
    }
    let t = core.raw_read_16(RULES_T, -1).saturating_add(1);
    core.raw_write_16(RULES_T, -1, t);
    if t >= 40 && t % 12 < 4 {
        KEY_A
    } else {
        0
    }
}

/// The battle is played and the game is back in its menus: the match is over.
pub fn finished(core: &Core) -> bool {
    on(core)
        && core.raw_read_8(BATTLED, -1) == 1
        && !crate::pvp::in_battle(core)
        && (crate::survival_ui::selecting(core) || crate::campaign_menu::on_select_mode(core))
}

// --- Drawing (presentation only) ---------------------------------------------------------------------------

/// Lines of text in a box at the right foot of SELECT MAP, beside the list (the game's list can have its cursor
/// on any of its rows to the foot of the screen, so nothing covers it).
fn paint_box(core: &Core, cv: &mut crate::online::Rgba<'_>, lines: &[(String, crate::online::Rgb)]) {
    use crate::online::*;
    let (x, w) = (88, W as i32 - 88);
    let h = 5 + 12 * lines.len() as i32;
    cv.rect(x, 160 - h, w, h, BAR);
    for (k, (t, ink)) in lines.iter().enumerate() {
        let tw = text_width(core, t);
        cv.text(core, x + (w - tw) / 2, 160 - h + 3 + 12 * k as i32, t, *ink, GRAY_INK);
    }
}

/// The picking box: whose turn it is, and the picks so far.
fn paint_picks(core: &Core, cv: &mut crate::online::Rgba<'_>) {
    use crate::online::*;
    let n = seats(core);
    let who = (core.raw_read_8(PICKS, -1) as usize).min(n - 1);
    let me = room_local_seat();
    let fits = |t: &str| text_width(core, t) <= 144;
    let line1 = if who == me { "Pick a map  A: Choose".to_string() } else { fit(core, &format!("{} is picking...", room_name(who)), 144) };
    let picked = core.raw_read_8(PICKS, -1) as usize;
    let maps: Vec<String> = (0..picked.min(n)).map(|s| map_name(core, core.raw_read_8(seat(s) + S_MAP, -1))).collect();
    let mut lines = vec![(line1, WHITE)];
    if picked > 0 {
        let full = (0..maps.len()).map(|s| format!("{}: {}", room_name(s), maps[s])).collect::<Vec<_>>().join(", ");
        let count = format!("Picks: {picked} of {n}");
        lines.push((if fits(&full) { full } else { count.clone() }, YELLOW));
        if me < picked && lines[1].0 == count {
            lines.push((fit(core, &format!("Yours: {}", maps[me]), 144), YELLOW));
        }
    }
    paint_box(core, cv, &lines);
}

/// The bar over SELECT MAP's own screen: whose turn it is to pick, then whose map is played.
pub fn draw(core: &Core, rgba: &mut [u8]) {
    if rgba.len() != crate::online::W * crate::online::H * 4 || !active(core) || phase(core) > 1 || !crate::survival_ui::selecting(core) {
        return;
    }
    paint_bar(core, rgba);
}

/// The bar's text (see [`draw`]; the text audit paints it without the game being on SELECT MAP).
pub fn paint_bar(core: &Core, rgba: &mut [u8]) {
    use crate::online::*;
    let mut canvas = Rgba(rgba);
    let cv = &mut canvas;
    if phase(core) == 0 {
        paint_picks(core, cv);
        return;
    }
    let pick = (core.raw_read_8(PICK, -1) as usize).min(seats(core) - 1);
    let map = map_name(core, core.raw_read_8(CHOSEN, -1));
    let who = room_name(pick);
    let from = [format!("from {who} is played"), format!("from {} is played", fit(core, &who, 70)), "is played".to_string()]
        .into_iter()
        .find(|t| text_width(core, t) <= 144)
        .unwrap_or_else(|| "is played".to_string());
    paint_box(core, cv, &[(fit(core, &map, 144), WHITE), (from, YELLOW)]);
}

