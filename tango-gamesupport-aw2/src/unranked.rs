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
//!    is played by every player at the same time, each in private (see below); A picks the map under the cursor.
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
//! **Private picks** (0.8.5). Every seat picks at the same time and in private: each window runs a SELECT MAP of its own ([`private_view`]: a
//! console of its own, kept between two frames, started from the shared console's state), driven by the keys of its own seat only, so
//! that nobody sees another's cursor, tab or pick; the windows show only the plate with the picks made and who is waited for. The shared
//! console idles on SELECT MAP. Only the final pick, the map's id, reaches it: two pad words in the seat's own input stream
//! (`tango_match::keys::command::pick_words`, read by [`pick_word`]), so rollback, replays and every peer see the same. Each client picks
//! the map under its own cursor when the time is up; a seat whose client never answers is given the list's first map a few seconds
//! later by the simulation itself ([`GRACE_SECONDS`]).
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
/// Frames on the Rules screen (u16, even address: see [`RULES_SHOW`]).
const RULES_T: u32 = STATE + 0xE0;
/// How long an UNRANKED match's standard rules are shown on the Rules screen before it goes on by itself (frames, 3 seconds).
pub const RULES_SHOW: u16 = 180;
/// 1 once a battle has been played.
const BATTLED: u32 = STATE + 9;
/// Frames settled on the chosen map in the list (u8).
const SETTLED: u32 = STATE + 0x0A;
/// Test aid: a bit for each Rules row that was not the standard value when the screen came up.
const CHANGED: u32 = STATE + 0x0B;
/// Roulette (see [`mask`]): frames of the reveal cycle (u16, even address; 0 until the walk has settled), frames held on
/// the revealed map (u16), the host pressed A to go on (u8), the direction of the last cursor step (u8).
const CYC_T: u32 = STATE + 0x40;
const HOLD_T: u32 = STATE + 0x42;
const SKIP: u32 = STATE + 0x44;
const STEP_DIR: u32 = STATE + 0x45;
/// The time each player has to pick a map, in console frames (60 a second): then the map under their cursor is their pick.
/// (`TANGOAW2_PICK_SECONDS` shortens it for a test, on every client alike.)
pub const PICK_SECONDS: u32 = 120;
/// How long the drawn map is shown before the game goes on by itself (the host's A goes on at once).
pub const REVEAL_SECONDS: u32 = 9;
const PICK_FRAMES: u32 = PICK_SECONDS * 60;
const REVEAL_FRAMES: u16 = (REVEAL_SECONDS * 60) as u16;
/// Frames the game's cursor sits on the drawn map, after the cycle, before the map is shown: the game's own picture of the map (the counters
/// header and the preview) takes about that long to follow its cursor, and the reveal shows them uncovered.
const REVEAL_SETTLE: u8 = 45;
/// Frames the game's cursor sits on the drawn map before the game is told to choose it.
const REVEAL_AFTER: u8 = 10;
/// Frames the maps have been picked for (u16, even address): the time everyone has.
const PICK_T: u32 = STATE + 0x46;
/// The seats that have picked (a bit each, the console's seat order), and which round of picks this is (counts up when the seats
/// propose again; it is not cleared by [`restart`]).
const PICKED: u32 = STATE + 0x4C;
const ROUND: u32 = STATE + 0x4D;
/// 1 in a window's private console once the seat has picked, before the shared console says so (presentation only).
const LOCAL_PICKED: u32 = STATE + 0x4E;
/// The first half of a pick each seat has sent, plus one (0 none; the physical seats).
const HALF: u32 = STATE + 0x50;
/// How long past the time a seat whose client has not picked is waited for; then the simulation picks the list's first map for it.
pub const GRACE_SECONDS: u32 = 15;

fn pick_frames() -> u32 {
    static F: std::sync::OnceLock<u32> = std::sync::OnceLock::new();
    *F.get_or_init(|| {
        std::env::var("TANGOAW2_PICK_SECONDS")
            .ok()
            .and_then(|v| v.parse::<u32>().ok())
            .map_or(PICK_FRAMES, |s| s * 60)
    })
}
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
const VALUES: [(usize, u8); 7] = [
    (R_FOG, 1),
    (R_WEATHER, 1),
    (R_FUNDS, 0),
    (R_TURN, 0),
    (R_CAPT, 0),
    (R_POWER, 0),
    (R_VISUALS, 0),
];
const RULES_RECORD: u32 = 0x0201_7C50;
const RULES_RECORD_FIVE: u32 = 0x0203_0300;
const ITEM_VALUE: u32 = 0x48;
const ITEM_FN: u32 = 0x4C;
const ITEM_FNS: [u32; 6] = [
    0x0806_4739,
    0x0806_4775,
    0x0806_47BD,
    0x0806_486D,
    0x0806_4919,
    0x0806_49D1,
];
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
    core.raw_write_8(PICKED, -1, ((1u16 << picks) - 1) as u8);
    core.raw_write_8(CHOSEN, -1, maps[pick as usize % 2]);
    for s in 0..2 {
        core.raw_write_8(seat(s) + S_MAP, -1, maps[s]);
    }
}

/// Test aid (the text audit): the seats are picking, `mask` have picked (as the shared console has it), this seat has (in its own console)
/// or not, and `left` seconds of the time are left.
pub fn set_picking(core: &mut Core, mask: u8, local_picked: bool, left: u32) {
    core.raw_write_range(STATE, -1, &[0u8; STATE_LEN as usize]);
    core.raw_write_8(PROPOSE, -1, 1);
    core.raw_write_8(PHASE, -1, 0);
    core.raw_write_8(PICKED, -1, mask);
    core.raw_write_8(PICKS, -1, mask.count_ones() as u8);
    core.raw_write_8(LOCAL_PICKED, -1, local_picked as u8);
    core.raw_write_16(PICK_T, -1, (pick_frames() - left * 60) as u16);
}

/// An UNRANKED match (standard rules, the match ends after one battle).
pub fn on(core: &Core) -> bool {
    core.raw_read_8(FLAG, -1) == 1
}

/// The seats propose maps (every online match).
pub fn active(core: &Core) -> bool {
    core.raw_read_8(PROPOSE, -1) == 1
}

/// The seats are picking their maps (SELECT MAP is up, the draw not made): every window works in private ([`private_view`]).
pub fn picking(core: &Core) -> bool {
    active(core) && !crate::proxy_seat::alone(core) && phase(core) == 0 && crate::survival_ui::selecting(core)
}

/// The seats that have picked (a bit each, the console's seat order).
pub fn picked_mask(core: &Core) -> u8 {
    core.raw_read_8(PICKED, -1)
}

/// How many seats have picked.
pub fn picks_made(core: &Core) -> usize {
    core.raw_read_8(PICKS, -1) as usize
}

/// The seat has picked, as the shared console has it.
pub fn has_picked(core: &Core, seat: usize) -> bool {
    seat < 8 && picked_mask(core) & (1 << seat) != 0
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

/// Every tick: the picking time runs, the host's A on the revealed map goes on, a round of picks that has run out of time is settled.
pub fn tick(core: &mut Core, inputs: &[u32]) {
    if !active(core) || inputs.len() < 2 {
        return;
    }
    let n = seats(core).min(inputs.len());
    if core.raw_read_8(BATTLED, -1) == 0 && crate::pvp::in_versus(core) && crate::pvp::in_battle(core) {
        core.raw_write_8(BATTLED, -1, 1);
    }
    // A room's battle is over and the game is back at SELECT MAP: the seats propose again.
    if !on(core)
        && core.raw_read_8(BATTLED, -1) == 1
        && !crate::pvp::in_battle(core)
        && crate::survival_ui::selecting(core)
    {
        restart(core);
    }
    // The game left the list on the chosen map: it goes on to the armies.
    if phase(core) == 1 && core.raw_read_8(SETTLED, -1) >= 10 && !crate::survival_ui::selecting(core) {
        core.raw_write_8(PHASE, -1, 2);
    }
    let was: Vec<u32> = (0..n).map(|s| core.raw_read_16(seat(s) + S_PREV, -1) as u32).collect();
    for s in 0..n {
        core.raw_write_16(seat(s) + S_PREV, -1, inputs[s] as u16);
    }
    // The host's A on the revealed map goes on to the armies.
    if phase(core) == 1 && revealed(core) && inputs[0] & !was[0] & KEY_A != 0 {
        core.raw_write_8(SKIP, -1, 1);
    }
    if phase(core) != 0 || !crate::survival_ui::idle(core) {
        return;
    }
    // (counts frames while picking: the draw's randomness, the same on every peer, and the time everyone has)
    let t = core.raw_read_16(DRAW_T, -1).wrapping_add(1);
    core.raw_write_16(DRAW_T, -1, t);
    let pt = (core.raw_read_16(PICK_T, -1) as u32 + 1).min(65535);
    core.raw_write_16(PICK_T, -1, pt as u16);
    // A seat whose window has not picked by the time (each window picks the map under its own cursor when the time is up, so this is
    // a client that is frozen or gone): the list's first map is its pick.
    if pt >= pick_frames() + GRACE_SECONDS * 60 {
        let first = core.raw_read_8(crate::online::LIST_IDS, -1);
        for who in 0..n {
            if !has_picked(core, who) {
                commit_pick(core, who, first);
            }
        }
    }
}

/// Whether `id` is a map the room offers (its tabs for the room's count; the shared console's list holds only the tab it is on).
fn in_list(core: &Core, id: u8) -> bool {
    crate::online_maps::offered(core, id)
}

/// The seat's pick is in: its map is noted, and with the last seat's the draw is made.
fn commit_pick(core: &mut Core, who: usize, id: u8) -> bool {
    let n = seats(core);
    if !picking(core) || who >= n || has_picked(core, who) || !in_list(core, id) {
        return false;
    }
    core.raw_write_8(seat(who) + S_MAP, -1, id);
    let mask = picked_mask(core) | 1 << who;
    core.raw_write_8(PICKED, -1, mask);
    let count = (0..n).filter(|&k| mask & (1 << k) != 0).count();
    core.raw_write_8(PICKS, -1, count as u8);
    if count == n {
        // (the frame counter and the maps proposed, mixed)
        let t = core.raw_read_16(DRAW_T, -1);
        let mix = (0..n).fold(t as usize, |a, k| {
            a.wrapping_mul(31)
                .wrapping_add(core.raw_read_8(seat(k) + S_MAP, -1) as usize)
        });
        let from = mix % n;
        core.raw_write_8(PICK, -1, from as u8);
        let map = core.raw_read_8(seat(from) + S_MAP, -1);
        core.raw_write_8(CHOSEN, -1, map);
        core.raw_write_8(SETTLED, -1, 0);
        core.raw_write_16(WALK_T, -1, 0);
        core.raw_write_16(CYC_T, -1, 0);
        core.raw_write_16(HOLD_T, -1, 0);
        core.raw_write_8(SKIP, -1, 0);
        core.raw_write_8(PHASE, -1, 1);
    }
    true
}

/// A pick word (half of a pick, five bits) from the physical seat `phys`: the two halves are the seat's own words on two ticks in a
/// row ([`pick_reset`] is the word between that is none). Called by [`crate::proxy_seat`] for every seat's word.
pub fn pick_word(core: &mut Core, phys: usize, half: u8) {
    if phys >= MAX_SEATS || !picking(core) {
        return;
    }
    let first = core.raw_read_8(HALF + phys as u32, -1);
    if first == 0 {
        core.raw_write_8(HALF + phys as u32, -1, half + 1);
        return;
    }
    core.raw_write_8(HALF + phys as u32, -1, 0);
    let id = (((first - 1) as u16) << 5) | half as u16;
    // (the seat as the console counts them, once players have left)
    let seat = match crate::proxy_seat::seat_order(core) {
        Some(order) => order.iter().position(|&p| p == phys),
        None => Some(phys),
    };
    if let (Some(seat), true) = (seat, id < 256) {
        commit_pick(core, seat, id as u8);
    }
}

/// A word that is not half of a pick: a half sent before it is none.
pub fn pick_reset(core: &mut Core, phys: usize) {
    if phys < MAX_SEATS && core.raw_read_8(HALF + phys as u32, -1) != 0 {
        core.raw_write_8(HALF + phys as u32, -1, 0);
    }
}

// --- The roulette -------------------------------------------------------------------------------------------

/// Steps of the highlight around the proposals (it lands on the drawn one on the last).
fn steps(n: usize) -> usize {
    (2 * n + 4).max(12)
}

/// Frames of step `i`: quick first, slower as it nears the end.
fn step_len(i: usize, k: usize) -> u16 {
    4 + (30 * i * i / (k * k)) as u16
}

/// The step the cycle is in `at` frames from its start, and the frame within it (`None` once it has landed).
fn step_at(n: usize, at: u16) -> Option<(usize, u16)> {
    let k = steps(n);
    let mut from = 0u16;
    for i in 0..k {
        let len = step_len(i, k);
        if at < from + len {
            return Some((i, at - from));
        }
        from += len;
    }
    None
}

/// Frames of the cycle: its steps, then a moment on the landed slot.
fn cycle_len(n: usize) -> u16 {
    let k = steps(n);
    (0..k).map(|i| step_len(i, k)).sum::<u16>() + 24 + 1
}

/// The slot the highlight is on at frame `at` of the cycle (the drawn seat's on the last step).
fn slot_at(n: usize, from: usize, at: u16) -> usize {
    let k = steps(n);
    match step_at(n, at) {
        Some((i, _)) => (from + i + 1 + n * k - k) % n,
        None => from,
    }
}

/// The drawn map is shown (the cycle is over and the game's cursor is on it): its name, picture and whose it is.
pub fn revealed(core: &Core) -> bool {
    phase(core) == 1
        && core.raw_read_16(CYC_T, -1) >= cycle_len(seats(core))
        && core.raw_read_8(SETTLED, -1) >= REVEAL_SETTLE
}

/// The map the match is played on, once it is drawn (the Armies and Rules pages name it).
pub fn map_played(core: &Core) -> Option<String> {
    (active(core) && phase(core) >= 2).then(|| map_name(core, core.raw_read_8(CHOSEN, -1)))
}

/// Which keys reach the game: the picking seat's while the maps are picked, none while the map is walked to, none on the Rules screen of
/// an UNRANKED match, and after the battle both players'.
pub fn merge(core: &Core, inputs: &[u32]) -> Option<u32> {
    if !active(core) {
        return None;
    }
    if phase(core) < 3 && crate::survival_ui::selecting(core) {
        // (the maps are picked in private on each window's own console, [`private_view`]: the shared one has no pad)
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
    let Some(cur) = crate::online::list_cursor(core).filter(|&c| c < crate::five_map::LIST_CAP) else {
        return 0;
    };
    // The list is the tab's maps: the first id's tab is the one shown.
    let list_tab = tab_of(core, core.raw_read_8(ids, -1));
    // The reveal cycle: the game's cursor steps up and down in the list (its own sound each step, the picture covered, see
    // [`mask`]), the net move none.
    let cyc = core.raw_read_16(CYC_T, -1);
    if cyc > 0 && cyc < cycle_len(seats(core)) {
        core.raw_write_16(CYC_T, -1, cyc + 1);
        if cyc + 1 >= cycle_len(seats(core)) {
            // (the settling of the game's cursor on the map starts over: see [`revealed`])
            core.raw_write_8(SETTLED, -1, 0);
        }
        return match step_at(seats(core), cyc - 1) {
            Some((i, off)) if off < 2 => {
                let mut len = 0;
                while len < crate::five_map::LIST_CAP && tab_of(core, core.raw_read_8(ids + len, -1)) == list_tab {
                    len += 1;
                }
                if len < 2 {
                    0
                } else if i % 2 == 0 {
                    // (down unless at the foot; the next step undoes it)
                    let down = cur + 1 < len;
                    core.raw_write_8(STEP_DIR, -1, down as u8);
                    if down {
                        KEY_DOWN
                    } else {
                        KEY_UP
                    }
                } else if core.raw_read_8(STEP_DIR, -1) == 1 {
                    KEY_UP
                } else {
                    KEY_DOWN
                }
            }
            _ => 0,
        };
    }
    // (the drawn map is shown for a while whatever the game's list is doing under it)
    if revealed(core) {
        core.raw_write_16(HOLD_T, -1, core.raw_read_16(HOLD_T, -1).saturating_add(1));
    }
    if core.raw_read_8(ids + cur, -1) == target {
        let settled = core.raw_read_8(SETTLED, -1).saturating_add(1);
        core.raw_write_8(SETTLED, -1, settled);
        if cyc > 0 && settled == REVEAL_SETTLE {
            // (the reveal: the game's "power meter charged" chime, played by the list proc's next frame)
            core.raw_write_8(SOUND_REQ, -1, SE_REVEAL);
        }
        if cyc == 0 {
            if settled >= 20 {
                core.raw_write_16(CYC_T, -1, 1);
            }
            return 0;
        }
        // (revealed: held, then A for 4 frames of 12 until the game leaves the list)
        if settled < REVEAL_AFTER {
            return 0;
        }
        let hold = core.raw_read_16(HOLD_T, -1);
        return if (hold >= REVEAL_FRAMES || core.raw_read_8(SKIP, -1) != 0) && hold % 12 < 4 {
            KEY_A
        } else {
            0
        };
    }
    core.raw_write_8(SETTLED, -1, 0);
    if tab_of(core, target) != list_tab {
        return if t % 30 < 4 { KEY_RIGHT } else { 0 };
    }
    let mut at = None;
    for i in 0..crate::five_map::LIST_CAP {
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
        || crate::online::battle_begun(core)
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
    ITEM_FNS
        .contains(&core.raw_read_32(rows[0] + ITEM_FN, -1))
        .then_some(rows)
}

/// The Rules screen is up after the map was chosen (a test cue).
pub fn rules_up(core: &Core) -> bool {
    active(core) && rules_rows(core).is_some()
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
    // (shown for the players to see, then A: the page is not skipped, see `paint_rules_banner`)
    if t >= RULES_SHOW && t % 12 < 4 {
        KEY_A
    } else {
        0
    }
}

/// A room's battle is played and the game is back at SELECT MAP: the seats propose again (the moment a room's roster may
/// change, see [`crate::proxy_seat`]).
pub fn back_from_battle(core: &Core) -> bool {
    active(core)
        && !on(core)
        && core.raw_read_8(BATTLED, -1) == 1
        && !crate::pvp::in_battle(core)
        && crate::survival_ui::selecting(core)
}

/// The seats propose maps again (a battle was played, or a player left): everything but the draw's counter starts over.
pub fn restart(core: &mut Core) {
    let round = core.raw_read_8(ROUND, -1).wrapping_add(1);
    for k in 0..STATE_LEN {
        if !(PROPOSE - STATE..PROPOSE - STATE + 1).contains(&k) && k != 0x0E && k != 0x0F {
            core.raw_write_8(STATE + k, -1, 0);
        }
    }
    core.raw_write_8(ROUND, -1, round);
}

/// A room's SELECT MAP is up and no battle is on (the roster may be made, see [`crate::proxy_seat`]).
pub fn setup_select(core: &Core) -> bool {
    active(core) && !on(core) && !crate::pvp::in_battle(core) && crate::survival_ui::selecting(core)
}

/// A room's map is drawn and the game has gone on to the armies or the rules, before the first battle of the match.
pub fn setup_past_select(core: &Core) -> bool {
    active(core)
        && !on(core)
        && core.raw_read_8(BATTLED, -1) == 0
        && phase(core) >= 2
        && !crate::pvp::in_battle(core)
        && !crate::survival_ui::selecting(core)
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
    let h = 7 + 12 * lines.len() as i32;
    let (x, w) = (x + 1, w - 3);
    cv.plate(x, 160 - h - 2, w, h);
    for (k, (t, ink)) in lines.iter().enumerate() {
        let tw = text_width(core, t);
        cv.text(core, x + (w - tw) / 2, 160 - h - 2 + 3 + 12 * k as i32, t, *ink, SHADE);
    }
}

/// A window's own SELECT MAP while the maps are picked (see the module's docs): the seat's console is kept between two frames
/// ([`Scratch::save_private`]), started from the shared console's state, and run with the seat's own keys: A picks the map under the
/// cursor (queued as the two words of its pick, [`tango_gamesupport::private::queue_pick`]), B and START do nothing, and
/// when the time is up the map under the cursor is the pick. Nothing of it reaches the shared console but that pick. What the shared console
/// knows (who has picked, the time) is copied into the private console's state each frame, for the plate that shows it.
pub fn private_view(scratch: &mut dyn tango_backend_mgba::Scratch, seat: usize) -> bool {
    use tango_gamesupport::private;
    let started = scratch.memory()[1] != 0;
    if std::env::var_os("AW2_PRIVATE_LOG").is_some() {
        let core = scratch.core();
        eprintln!(
            "private view seat {seat}: picking {} seats {} idle {} started {started}",
            picking(core),
            seats(core),
            crate::survival_ui::idle(core)
        );
    }
    let shared: Vec<u8> = {
        let core = scratch.core();
        // (the list is up and still before the window's console begins, from the shared console's state)
        if !picking(core) || seat >= seats(core) || (!crate::survival_ui::idle(core) && !started) {
            return false;
        }
        let mut b = vec![0u8; STATE_LEN as usize];
        core.raw_read_range(STATE, -1, &mut b);
        b
    };
    let at = |off: u32| shared[(off - STATE) as usize];
    let (round, mask, pick_t) = (
        at(ROUND),
        at(PICKED),
        u16::from_le_bytes([at(PICK_T), at(PICK_T + 1)]) as u32,
    );
    let phys = scratch.physical_seat();
    let now = scratch.console_tick();
    // (a new round of picks, the seats proposing again after a player left or a battle: start over)
    let mem = *scratch.memory();
    if mem[1] & 0xFF != round as i32 + 1 {
        scratch.drop_private();
        scratch.memory()[1] = round as i32 + 1;
        scratch.memory()[2] = 0;
    }
    let had = scratch.load_private();
    // (what the shared console knows, over the private console's own state of it)
    scratch.core_mut().raw_write_range(STATE, -1, &shared);
    let mem = *scratch.memory();
    let mut prev_a = mem[1] >> 8 & 1 != 0;
    let (mut picked, mut since) = (mem[2] & 1 != 0, (mem[2] >> 1 & 0x7FFF) as u32);
    let last = (mem[2] >> 16) as u16;
    let ticks = if had {
        (now as u16).wrapping_sub(last).clamp(1, 4) as usize
    } else {
        1
    };
    let (held, pressed) = private::take_keys(phys);
    for i in 0..ticks {
        let keys = if i == 0 { held | pressed } else { held };
        let a_edge = keys & KEY_A != 0 && !prev_a;
        prev_a = keys & KEY_A != 0;
        let core = scratch.core();
        let (idle, last_row) = (
            crate::survival_ui::idle(core),
            core.raw_read_8(crate::five_map::LIST_LAST, -1) as u32,
        );
        let cursor_id = crate::online::list_cursor(core)
            .filter(|&c| c < crate::five_map::LIST_CAP && c <= last_row)
            .map(|c| core.raw_read_8(crate::online::LIST_IDS + c, -1));
        let confirmed = mask & (1 << seat) != 0;
        if confirmed {
            picked = true;
        }
        let retry = picked && !confirmed && !private::pending(phys) && since > 180;
        if idle && !confirmed && (!picked && (a_edge || pick_t >= pick_frames()) || retry) {
            // (the map under the cursor; a cursor off the list is the list's first map, as the time running out has always been)
            let id = cursor_id.unwrap_or_else(|| core.raw_read_8(crate::online::LIST_IDS, -1));
            private::queue_pick(phys, tango_match::keys::command::pick_words(id as u16));
            picked = true;
            since = 0;
        }
        if picked && !confirmed {
            since = (since + 1).min(0x7FFF);
        }
        scratch.core_mut().raw_write_8(LOCAL_PICKED, -1, picked as u8);
        // (once picked there is no more browsing, and B and START are no way out of the picks)
        let keys = if picked {
            0
        } else {
            keys & !(KEY_A | KEY_B | crate::online::KEY_START)
        };
        scratch.tick(keys);
        scratch.core_mut().raw_write_range(STATE, -1, &shared);
        scratch.core_mut().raw_write_8(LOCAL_PICKED, -1, picked as u8);
    }
    scratch.save_private();
    scratch.keep_audio();
    scratch.memory()[1] = (round as i32 + 1) | (prev_a as i32) << 8;
    scratch.memory()[2] = picked as i32 | (since as i32) << 1 | (now as u16 as i32) << 16;
    true
}

/// A tick mark, 5 wide and 4 tall.
fn check(cv: &mut crate::online::Rgba<'_>, x: i32, y: i32, ink: crate::online::Rgb) {
    for (dx, dy) in [(0, 2), (1, 3), (2, 2), (3, 1), (4, 0)] {
        cv.rect(x + dx, y + dy, 1, 1, ink);
        cv.rect(x + dx, y + dy + 1, 1, 1, ink);
    }
}

/// The picking plate, where the title was (the mirror of the game's counters header; the map's picture can use everything under it and
/// down to the foot of the screen, so nothing is drawn over it): what to do or who is waited for, and the picks made and the time left.
/// Once the seat has picked, the list's column says who has picked too (a tick), never which map.
fn paint_picks(core: &Core, cv: &mut crate::online::Rgba<'_>) {
    use crate::online::*;
    let n = seats(core);
    let me = room_local_seat();
    let made = picks_made(core).min(n);
    let mine = has_picked(core, me) || core.raw_read_8(LOCAL_PICKED, -1) == 1;
    // (a seat whose pick is in the stream but not counted yet is shown as picked to itself)
    let made = (made + (mine && !has_picked(core, me)) as usize).min(n);
    let left = pick_frames()
        .saturating_sub(core.raw_read_16(PICK_T, -1) as u32)
        .div_ceil(60);
    let sea: Rgb = (139, 222, 230);
    // (the title's logo goes: the plate covers it, a margin of sea round the plate)
    cv.rect(0, 0, 140, 31, sea);
    let (red, pink, grey): (Rgb, Rgb, Rgb) = ((246, 82, 57), (255, 238, 238), (131, 123, 115));
    let (x, y, w, h) = (4, 2, 132, 27);
    audit::window(x, y, w, h);
    cv.rect(x - 1, y - 1, w + 2, h + 2, (0, 0, 0));
    cv.rect(x, y, w, h, red);
    cv.rect(x + 2, y + 2, w - 4, h - 4, pink);
    let waiting: Vec<String> = (0..n)
        .filter(|&k| !has_picked(core, k) && (k != me || !mine))
        .map(room_name)
        .collect();
    let line1 = if !mine {
        "Pick a map: press A".to_string()
    } else {
        match waiting.as_slice() {
            [] => "Everyone has picked".to_string(),
            [one] => fit(core, &format!("Waiting for {one}..."), w - 12),
            [one, more @ ..] => {
                let tail = format!(" +{}", more.len());
                format!(
                    "Waiting for {}{tail}",
                    fit(core, one, w - 12 - text_width(core, &format!("Waiting for ..{tail}")))
                )
            }
        }
    };
    let line2 = format!("Picks: {made} of {n}   {}:{:02}", left / 60, left % 60);
    let ink: Rgb = if left <= 10 { (200, 40, 24) } else { (88, 72, 150) };
    cv.text(core, x + (w - text_width(core, &line1)) / 2, y + 3, &line1, grey, SHADE);
    cv.text(core, x + (w - text_width(core, &line2)) / 2, y + 13, &line2, ink, SHADE);
    if mine {
        // The gamertags with a tick for each that has picked, over the list (the picker has no more use of it).
        let (bx, by, bw, rh) = (2, 34, 84, 12);
        let bh = 6 + rh * n as i32;
        audit::window(bx, by, bw, bh);
        cv.rect(bx, by, bw, 130, sea);
        cv.rect(bx - 1, by - 1, bw + 2, bh + 2, (0, 0, 0));
        cv.rect(bx, by, bw, bh, red);
        cv.rect(bx + 2, by + 2, bw - 4, bh - 4, pink);
        for k in 0..n {
            let ry = by + 3 + rh * k as i32;
            let done = has_picked(core, k) || (k == me && mine);
            cv.rect(bx + 4, ry + rh - 2, bw - 8, 1, (255, 230, 213));
            let name = fit(core, &room_name(k), bw - 26);
            cv.text(core, bx + 7, ry, &name, if done { (88, 72, 150) } else { grey }, SHADE);
            if done {
                check(cv, bx + bw - 14, ry + 3, (88, 72, 150));
            } else {
                cv.text(core, bx + bw - 15, ry, "..", grey, SHADE);
            }
        }
    }
}

/// The picture is fading to black (the notes would hang on the black).
fn dark(rgba: &[u8]) -> bool {
    let sum: u32 = (0..20)
        .map(|k| {
            let (x, y) = (12 + 11 * k, 20 + 7 * k);
            let o = 4 * (crate::online::W * y + x);
            rgba[o] as u32 + rgba[o + 1] as u32 + rgba[o + 2] as u32
        })
        .sum();
    sum / 60 < 60
}

/// The bar over SELECT MAP's own screen: whose turn it is to pick, then whose map is played.
pub fn draw(core: &Core, rgba: &mut [u8]) {
    if rgba.len() != crate::online::W * crate::online::H * 4 || !active(core) {
        return;
    }
    if dark(rgba) {
        return;
    }
    if rules_up(core) {
        // (not over the army page while it finishes: its own title already names the map; and not over the results after
        // the battle, where the Rules page's rows still stand in memory)
        if !crate::online_teams::done(core) && core.raw_read_8(BATTLED, -1) == 0 {
            paint_rules_name(core, rgba);
            paint_rules_banner(core, rgba);
        }
        return;
    }
    if phase(core) > 1 || !crate::survival_ui::selecting(core) {
        return;
    }
    paint_bar(core, rgba);
}

/// The Rules page names the map (a plate between its title and the PRESS A hint).
pub fn paint_rules_name(core: &Core, rgba: &mut [u8]) {
    use crate::online::*;
    let name = map_name(core, core.raw_read_8(CHOSEN, -1));
    let name = fit(core, &name, 112);
    let w = text_width(core, &name) + 10;
    let mut canvas = Rgba(rgba);
    let x = 130 - w / 2;
    canvas.plate(x, 2, w, 15);
    canvas.text(core, x + 5, 4, &name, PLATE_INK, SHADE);
}

/// The seconds the Rules page of an UNRANKED match still shows ("Starting in 3"), after `t` frames on it.
pub fn rules_countdown(t: u16) -> u16 {
    RULES_SHOW.saturating_sub(t).div_ceil(60).max(1)
}

/// The Rules page in a match the players do not set the rules of, over the game's help box: UNRANKED's standard rules, shown
/// for a moment before the match starts ("Unranked rules", "Starting in 3"), and in a room, on a guest's window, whose they are
/// ("<host> is setting the rules": the page is read-only there; the host's own window has the game's help line and PRESS A).
pub fn paint_rules_banner(core: &Core, rgba: &mut [u8]) {
    use crate::online::*;
    let lines: Vec<(String, Rgb)> = if on(core) {
        let left = rules_countdown(core.raw_read_16(RULES_T, -1));
        vec![
            ("Unranked rules".to_string(), PLATE_INK),
            (format!("Starting in {left}"), PLATE_GREY),
        ]
    } else {
        let n = room_players();
        let host = crate::proxy_seat::host_index(core, n);
        if room_local_seat() == host {
            return;
        }
        let who = fit(core, &room_name(host), 120);
        vec![
            (format!("{who} is setting the rules"), PLATE_INK),
            ("The match starts when they go on.".to_string(), PLATE_GREY),
        ]
    };
    let mut canvas = Rgba(rgba);
    let (x, y, w, h) = (4, 126, 232, 31);
    canvas.plate(x, y, w, h);
    for (k, (t, ink)) in lines.iter().enumerate() {
        let tw = text_width(core, t);
        canvas.text(core, x + (w - tw) / 2, y + 4 + 12 * k as i32, t, *ink, SHADE);
    }
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
    if phase(core) == 1 {
        mask(core, cv);
        return;
    }
    let pick = (core.raw_read_8(PICK, -1) as usize).min(seats(core) - 1);
    let map = map_name(core, core.raw_read_8(CHOSEN, -1));
    let who = room_name(pick);
    let from = [
        format!("from {who} is played"),
        format!("from {} is played", fit(core, &who, 70)),
        "is played".to_string(),
    ]
    .into_iter()
    .find(|t| text_width(core, t) <= 144)
    .unwrap_or_else(|| "is played".to_string());
    let mut lines = vec![(fit(core, &map, 144), PLATE_INK), (from, PLATE_GREY)];
    if crate::online::room_local_seat() == 0 {
        lines.push(("A: Go on".to_string(), PLATE_GREY));
    }
    paint_box(core, cv, &lines);
}

/// The roulette's picture: the game's own SELECT MAP is covered (its list would give the maps away) except the title, and a
/// window of the proposals (a "?????" for each) stands in the list's column: a highlight runs round them quickly, slows and
/// lands on the drawn one (the game's cursor steps under it, with its own sound). There the "?????" turns into the map's name
/// beside its owner's gamertag, and the right of the screen is the game's own: its counters header and its picture of the
/// map, uncovered (the console renders it, so it is the same on every peer). The title's place has the plate with the
/// seconds before the armies.
fn mask(core: &Core, cv: &mut crate::online::Rgba<'_>) {
    use crate::online::*;
    let n = seats(core);
    let sea: Rgb = (139, 222, 230);
    let shown = revealed(core);
    // (the list's column always; the counters header and the picture only once the map is shown: they would say which map)
    cv.rect(0, 30, 88, 130, sea);
    cv.rect(0, 0, 140, 31, sea);
    if !shown {
        cv.rect(88, 30, W as i32 - 88, 130, sea);
        cv.rect(134, 0, W as i32 - 134, 30, sea);
    }
    let cyc = core.raw_read_16(CYC_T, -1);
    let from = (core.raw_read_8(PICK, -1) as usize).min(n - 1);
    let lit = (cyc > 0).then(|| slot_at(n, from, cyc - 1));
    // (the game's own look: a black edge, a red frame, a pink page with a line under each row, a lavender highlight)
    let (red, pink, line, lav, grey): (Rgb, Rgb, Rgb, Rgb, Rgb) = (
        (246, 82, 57),
        (255, 238, 238),
        (255, 230, 213),
        (222, 205, 255),
        (131, 123, 115),
    );
    // The plate where the title was.
    let (px, py, pw, ph) = (4, 2, 132, 27);
    audit::window(px, py, pw, ph);
    cv.rect(px - 1, py - 1, pw + 2, ph + 2, (0, 0, 0));
    cv.rect(px, py, pw, ph, red);
    cv.rect(px + 2, py + 2, pw - 4, ph - 4, pink);
    let (l1, l2) = if shown {
        let left = (REVEAL_FRAMES.saturating_sub(core.raw_read_16(HOLD_T, -1)) as u32).div_ceil(60);
        (
            "The map is drawn".to_string(),
            if room_local_seat() == 0 {
                format!("A: Start now  ({left})")
            } else {
                format!("Starting in {left}")
            },
        )
    } else {
        ("Drawing the map...".to_string(), format!("{} proposals", n))
    };
    cv.text(core, px + (pw - text_width(core, &l1)) / 2, py + 2, &l1, grey, SHADE);
    cv.text(
        core,
        px + (pw - text_width(core, &l2)) / 2,
        py + 12,
        &l2,
        (88, 72, 150),
        SHADE,
    );
    // The proposals, two lines each (the gamertag, then the map).
    let (x, y, w, rh) = (2, 34, 84, 23);
    let h = 6 + rh * n as i32;
    audit::window(x, y, w, h);
    cv.rect(x - 1, y - 1, w + 2, h + 2, (0, 0, 0));
    cv.rect(x, y, w, h, red);
    cv.rect(x + 2, y + 2, w - 4, h - 4, pink);
    let map = core.raw_read_8(CHOSEN, -1);
    for k in 0..n {
        let ry = y + 3 + rh * k as i32;
        cv.rect(x + 4, ry + rh - 1, w - 8, 1, line);
        if lit == Some(k) {
            cv.rect(x + 3, ry, w - 6, rh - 1, lav);
        }
        let ink = if lit == Some(k) { (88, 72, 150) } else { grey };
        let who = fit(core, &room_name(k), w - 14);
        cv.text(core, x + 7, ry, &who, ink, SHADE);
        let t = if shown && lit == Some(k) {
            fit(core, &map_name(core, map), w - 14)
        } else {
            "?????".to_string()
        };
        cv.text(core, x + w - 7 - text_width(core, &t), ry + 11, &t, ink, SHADE);
    }
}

// --- Sounds ----------------------------------------------------------------------------------------------------

/// AW2's sound-effect call (`sub_0803B4DC(song)`: it keeps the game's sound setting) and the per-frame function SELECT MAP's list
/// proc runs (`sub_0808606C`, after its `push {r4, lr}` and `adds r4, r0, #0`: r0..r3 are free there).
const PLAY_SOUND: u32 = 0x0803_B4DC;
const LIST_FRAME: u32 = 0x0808_6070;
/// The sound asked for (0 none; u8), played by the next frame of the list's proc.
const SOUND_REQ: u32 = STATE + 0x48;
/// The reveal's chime: AW2's own "CO power meter charged" sound (`sub_080437xx` plays it when a meter fills up): two tracks, a quick rising
/// arpeggio. (The steps before it are the game's own list tick, `0x67`, which the cursor plays by moving.)
const SE_REVEAL: u8 = 0x75;

fn play_requested(core: &mut Core) {
    let id = core.raw_read_8(SOUND_REQ, -1);
    if id == 0 || !active(core) {
        return;
    }
    core.raw_write_8(SOUND_REQ, -1, 0);
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, id as i32);
    cpu.set_gpr(14, (LIST_FRAME | 1) as i32);
    cpu.set_thumb_pc(PLAY_SOUND);
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![(LIST_FRAME, Box::new(play_requested))]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_standard_rules_are_shown_for_three_seconds_before_the_match_goes_on() {
        assert_eq!(RULES_SHOW, 180);
        assert_eq!(rules_countdown(0), 3);
        assert_eq!(rules_countdown(59), 3);
        assert_eq!(rules_countdown(60), 2);
        assert_eq!(rules_countdown(119), 2);
        assert_eq!(rules_countdown(120), 1);
        assert_eq!(rules_countdown(179), 1);
        // (A is pressed from RULES_SHOW on: the count never says 0)
        assert_eq!(rules_countdown(180), 1);
        assert_eq!(rules_countdown(u16::MAX), 1);
    }
}
