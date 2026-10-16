//! UNRANKED: a match against a random opponent, made by the app's pool ([`crate::online`], `tango_lobby::room`).
//!
//! The netplay console of an UNRANKED match ([`crate::online::UNRANKED_MATCH`] in its subtype) walks to Versus'
//! SELECT MAP as any room's does, and from there the players do not play the game's menus:
//!
//! 1. **Proposals.** Each player moves a selector of their own through the 2-army maps of the Versus tabs Classic,
//!    Vs. Maps and Pre-Deployed ([`candidates`]) and confirms with A (B takes it back); the page shows both players'
//!    proposals and gamertags live. The game's own list waits underneath, given no keys.
//! 2. **The draw.** When both have confirmed, one of the two proposals is the match's map: the seat chosen by
//!    [`crate::online::UNRANKED_PICK_GUEST`] (a bit of the match subtype, drawn by the room's host from the match seed, so
//!    it is the same on both peers and in a replay). The map is then walked to in the game's list by pressing for the
//!    players ([`drive`]) and chosen with A.
//! 3. **Armies.** Versus' Teams screen is the room's usual one ([`crate::online_teams`]): CO and a colour no other
//!    army has, no partner (tag pairs are off).
//! 4. **Rules.** The Rules screen is not played: [`rules`] writes the standard rules into its rows and presses A.
//!    [`RULES`] says which.
//! 5. **Battle**, then the results (both players' buttons), and the match ends back at SELECT MAP
//!    ([`crate::online::match_over`]); the app logs `unranked: the match ended`.
//!
//! The state is in EWRAM ([`STATE`]) so that rollback and replays carry it.

use crate::online::{KEY_A, KEY_B, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_UP};
use mgba::core::Core;

pub const STATE: u32 = 0x0203_D600;
pub const STATE_LEN: u32 = 0x100;
/// 1 in an UNRANKED match.
const FLAG: u32 = STATE;
/// 1: the guest's proposal is the match's map.
const PICK: u32 = STATE + 1;
/// 0 proposing, 1 walking to the chosen map, 2 the map is chosen (the game goes on to the armies and the rules),
/// 3 the walk failed (the host picks with the game's list).
const PHASE: u32 = STATE + 2;
const CHOSEN: u32 = STATE + 3;
const NCAND: u32 = STATE + 4;
/// 1 once the candidates are listed.
const LISTED: u32 = STATE + 5;
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
// A seat: +0 its proposal (an index into the candidates), +1 confirmed, +2 previous keys (u16), +4 frames the
// direction has been held.
const S_CURSOR: u32 = 0;
const S_OK: u32 = 1;
const S_PREV: u32 = 2;
const S_HELD: u32 = 4;
const CAND: u32 = STATE + 0x20;
const MAX_CAND: usize = 0xE0;

/// The standard rules, written into the Rules screen's rows (see [`rules`]).
pub const RULES: &str = "Fog of war off, weather clear, funds 1000 per property, no turn limit, no capture limit, \
CO powers on, CO skills off, tag pairs off";

/// The Versus tabs whose 2-army maps are offered: Classic, Vs. Maps, Pre-Deployed.
const TABS: [u16; 3] = [2, 3, 4];

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
    if subtype & crate::online::UNRANKED_MATCH != 0 {
        core.raw_write_8(FLAG, -1, 1);
        core.raw_write_8(PICK, -1, (subtype & crate::online::UNRANKED_PICK_GUEST != 0) as u8);
    }
}

/// Test aid (the text audit): both seats' proposals (indexes of the candidates) and whether they are confirmed.
pub fn set_proposals(core: &mut Core, cursors: [u8; 2], ok: [bool; 2], phase: u8, pick: u8) {
    core.raw_write_8(PHASE, -1, phase);
    core.raw_write_8(PICK, -1, pick);
    for s in 0..2 {
        core.raw_write_8(seat(s) + S_CURSOR, -1, cursors[s]);
        core.raw_write_8(seat(s) + S_OK, -1, ok[s] as u8);
    }
}

pub fn candidates_len(core: &Core) -> usize {
    n_candidates(core)
}

pub fn on(core: &Core) -> bool {
    core.raw_read_8(FLAG, -1) == 1
}

fn phase(core: &Core) -> u8 {
    core.raw_read_8(PHASE, -1)
}

fn seat(s: usize) -> u32 {
    SEATS + SEAT_SIZE * s as u32
}

fn candidate(core: &Core, i: usize) -> u8 {
    core.raw_read_8(CAND + i as u32, -1)
}

fn n_candidates(core: &Core) -> usize {
    core.raw_read_8(NCAND, -1) as usize
}

/// The 2-army maps on the offered tabs, in id order, from the map table the game reads now.
pub fn list_candidates(core: &mut Core) {
    let table = crate::five_map::table(core);
    let mut n = 0;
    for id in 1..crate::five_map::MAP_IDS {
        let e = table + 0x5C * id;
        let tab = core.raw_read_16(e + 0x1A, -1);
        // (the Colonel's Vault is the BH Campaign's prize: not for a random match)
        if core.raw_read_8(e + 0x18, -1) == 2 && TABS.contains(&tab) && id != crate::five_map::VAULT_ID as u32 && n < MAX_CAND {
            core.raw_write_8(CAND + n as u32, -1, id as u8);
            n += 1;
        }
    }
    core.raw_write_8(NCAND, -1, n as u8);
    core.raw_write_8(LISTED, -1, 1);
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

fn tab_name(core: &Core, id: u8) -> &'static str {
    let table = crate::five_map::table(core);
    match core.raw_read_16(table + 0x5C * id as u32 + 0x1A, -1) {
        2 => "Classic",
        3 => "Vs. Maps",
        4 => "Pre-Deployed",
        _ => "",
    }
}

/// Every tick: the proposals' selectors, from each seat's own keys.
pub fn tick(core: &mut Core, inputs: &[u32]) {
    if !on(core) || inputs.len() < 2 {
        return;
    }
    if core.raw_read_8(BATTLED, -1) == 0 && crate::pvp::in_versus(core) && crate::pvp::in_battle(core) {
        core.raw_write_8(BATTLED, -1, 1);
    }
    // The game left the list on the chosen map: it goes on to the armies.
    if phase(core) == 1 && core.raw_read_8(SETTLED, -1) >= 10 && !crate::survival_ui::selecting(core) {
        core.raw_write_8(PHASE, -1, 2);
    }
    if phase(core) != 0 || !crate::survival_ui::idle(core) {
        return;
    }
    if core.raw_read_8(LISTED, -1) == 0 {
        list_candidates(core);
        for s in 0..2 {
            core.raw_write_16(seat(s) + S_PREV, -1, inputs[s] as u16);
        }
    }
    let n = n_candidates(core);
    if n == 0 {
        // (no map to propose: the host picks with the game's list)
        core.raw_write_8(PHASE, -1, 3);
        return;
    }
    for s in 0..2 {
        let keys = inputs[s];
        let prev = core.raw_read_16(seat(s) + S_PREV, -1) as u32;
        core.raw_write_16(seat(s) + S_PREV, -1, keys as u16);
        let pressed = keys & !prev;
        let ok = core.raw_read_8(seat(s) + S_OK, -1) == 1;
        if ok {
            if pressed & KEY_B != 0 {
                core.raw_write_8(seat(s) + S_OK, -1, 0);
            }
            continue;
        }
        // A held direction goes on after a moment.
        let dir = keys & (KEY_LEFT | KEY_RIGHT);
        let mut step_dir = pressed & (KEY_LEFT | KEY_RIGHT);
        if dir == 0 || step_dir != 0 {
            core.raw_write_8(seat(s) + S_HELD, -1, 0);
        } else {
            let h = core.raw_read_8(seat(s) + S_HELD, -1).saturating_add(1);
            if h >= 18 && (h - 18) % 4 == 0 {
                step_dir = dir;
            }
            core.raw_write_8(seat(s) + S_HELD, -1, h);
        }
        let cur = core.raw_read_8(seat(s) + S_CURSOR, -1) as isize;
        let mut step = 0isize;
        if step_dir & KEY_RIGHT != 0 {
            step = 1;
        } else if step_dir & KEY_LEFT != 0 {
            step = -1;
        } else if pressed & KEY_DOWN != 0 {
            step = 6;
        } else if pressed & KEY_UP != 0 {
            step = -6;
        }
        if step != 0 {
            core.raw_write_8(seat(s) + S_CURSOR, -1, (cur + step).rem_euclid(n as isize) as u8);
        }
        if pressed & KEY_A != 0 {
            core.raw_write_8(seat(s) + S_OK, -1, 1);
        }
    }
    if (0..2).all(|s| core.raw_read_8(seat(s) + S_OK, -1) == 1) {
        let who = core.raw_read_8(PICK, -1) as usize;
        let i = core.raw_read_8(seat(who) + S_CURSOR, -1) as usize;
        core.raw_write_8(CHOSEN, -1, candidate(core, i.min(n - 1)));
        core.raw_write_16(WALK_T, -1, 0);
        core.raw_write_8(PHASE, -1, 1);
    }
}

/// Which keys reach the game: none while the map is proposed and walked to, none on the Rules screen, and after the
/// battle both players'.
pub fn merge(core: &Core, inputs: &[u32]) -> Option<u32> {
    if !on(core) {
        return None;
    }
    if phase(core) < 3 && crate::survival_ui::selecting(core) {
        return Some(0);
    }
    if rules_rows(core).is_some() {
        return Some(0);
    }
    if core.raw_read_8(BATTLED, -1) == 1 && !crate::pvp::in_battle(core) {
        return Some(inputs.iter().fold(0, |a, &b| a | b));
    }
    None
}

/// The keys that walk SELECT MAP's list to the chosen map and choose it. Returns the keys the game gets.
pub fn drive(core: &mut Core, keys: u32) -> u32 {
    if !on(core) || phase(core) != 1 || !crate::survival_ui::idle(core) {
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
        return if settled >= 10 && settled % 12 < 4 { KEY_A } else { 0 };
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

pub fn draw(core: &Core, rgba: &mut [u8]) {
    if rgba.len() != crate::online::W * crate::online::H * 4 || !on(core) || phase(core) > 2 || !crate::survival_ui::selecting(core) {
        return;
    }
    paint(core, rgba);
}

/// The proposals page (see [`draw`]; the text audit paints it without the game being on SELECT MAP).
pub fn paint(core: &Core, rgba: &mut [u8]) {
    use crate::online::*;
    let n = n_candidates(core);
    let mut canvas = Rgba(rgba);
    let cv = &mut canvas;
    cv.rect(0, 0, W as i32, 160, LIGHT_GRAY);
    cv.rect(0, 0, W as i32, 15, BAR);
    let title = "PROPOSE A MAP";
    cv.text(core, (W as i32 - text_width(core, title)) / 2, 2, title, WHITE, GRAY_INK);
    if n == 0 {
        bar(cv, core, "Getting the maps ready...");
        return;
    }
    let local = room_local_seat();
    let ph = phase(core);
    let pick = core.raw_read_8(PICK, -1) as usize;
    for s in 0..2usize {
        let y = 19 + 49 * s as i32;
        let h = 46;
        let mine = s == local;
        let ok = core.raw_read_8(seat(s) + S_OK, -1) == 1;
        let id = candidate(core, (core.raw_read_8(seat(s) + S_CURSOR, -1) as usize).min(n - 1));
        let chosen = ph >= 1 && s == pick;
        cv.rect(2, y, 236, h, if chosen { YELLOW } else if mine { CREAM } else { WHITE });
        cv.rect(2, y, 4, h, if s == 0 { RED } else { BLUE });
        audit::window(2, y, 236, h);
        audit::window(12, y, 190 - 12, 17);
        let name: String = fit(core, &room_name(s).chars().take(12).collect::<String>(), 190 - 12 - 4);
        cv.text(core, 12, y + 3, &name, if mine { BLUE } else { INK }, SHADE);
        let tag = if chosen {
            "CHOSEN"
        } else if ok {
            "READY"
        } else {
            "..."
        };
        let (plate, ink) = if chosen || ok { (BLUE, WHITE) } else { (LIGHT_GRAY, GRAY_INK) };
        cv.rect(190, y + 3, 44, 13, plate);
        cv.text(core, 190 + (44 - text_width(core, tag)) / 2, y + 4, tag, ink, SHADE);
        let map = map_name(core, id);
        let editing = mine && !ok && ph == 0;
        let line = if editing { format!("< {map} >") } else { map };
        let w = text_width(core, &line);
        if editing {
            cv.rect(10, y + 20, w + 4, 13, YELLOW);
        }
        cv.text(core, 12, y + 21, &line, INK, SHADE);
        cv.text(core, 12, y + 34, tab_name(core, id), GRAY_INK, SHADE);
    }
    let help = match ph {
        0 if core.raw_read_8(seat(local.min(1)) + S_OK, -1) == 1 => "B: Change   Waiting for the other player...".to_string(),
        0 => "Left Right: Map  Up Down: Faster  A: OK".to_string(),
        _ => format!("The map from {} is played.", room_name(pick)),
    };
    bar(cv, core, &help);
}
