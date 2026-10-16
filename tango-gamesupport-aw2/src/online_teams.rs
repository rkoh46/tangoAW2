//! Choosing armies in a room (crate::online): every player their own CO, colour and partner, all at the same time.
//!
//! On the netplay console of a room's match, Versus' Teams screen is not played: the game's own screen waits
//! underneath, given no keys, while this page is drawn over it. Each seat has a selector of its own in EWRAM
//! ([`SEL`]: its choices, which field it is on, whether it is READY), moved only by that seat's keys, which
//! [`tick`] reads from the netplay input stream every frame (so both peers, and a replay, apply the same keys and
//! stay the same). When every seat is READY the choices are written into the game's Teams record (each army's
//! controller is a human's, never the computer's) and the game's screen is told to go on to the Rules.
//!
//! Teams: every seat has a TEAM (A..E, as the game's own Teams page names them), its own to set; the host can set any
//! seat's (L and R pick the seat on the TEAM field, LEFT and RIGHT change it). Everyone starts on the team the game's
//! record gave them (every army its own: a free-for-all). READY needs at least two different teams. The teams go to
//! the Teams record's team bytes with the other choices, so the game's own rules apply: allies cannot attack each
//! other, a team wins when every enemy team is beaten, allies share their vision in fog.
//!
//! Colours are distinct (a colour another player has is skipped; Black Hole is one of the five). The partner row
//! shows with Dual Strike's tag pairs.

use crate::online::{KEY_A, KEY_B, KEY_DOWN, KEY_L, KEY_LEFT, KEY_R, KEY_RIGHT, KEY_START, KEY_UP};
use mgba::core::Core;

/// tangoAW2's EWRAM for it (0x0203CB00..0x0203CBFF).
pub const SEL: u32 = 0x0203_CB00;
pub const SEL_LEN: u32 = 0x100;
/// 1 while the page runs on this Teams screen.
const INIT: u32 = SEL;
/// 1 once every seat is READY: the choices are written and the game's screen is told to go on.
const DONE: u32 = SEL + 1;
/// How many seats the room has (set from the inputs, every tick).
const PLAYERS: u32 = SEL + 2;
/// Frames since [`DONE`].
const PULSE: u32 = SEL + 3;
/// Frames left of the "pick two teams" note.
const NOTE: u32 = SEL + 4;
/// Frames the game's Teams screen has been away since the choices were made.
const OFF: u32 = SEL + 5;
const SEATS: u32 = SEL + 0x10;
const SEAT_SIZE: u32 = 0x10;
// A seat: +0 CO (index into the Teams list), +1 colour, +2 partner CO (0xFF none), +3 field, +4 READY, +6 the
// previous keys (u16, on an even address: the GBA's halfword accesses are aligned), +8 frames the direction has
// been held, +9 the direction held.
const S_CO: u32 = 0;
const S_COLOUR: u32 = 1;
const S_PARTNER: u32 = 2;
const S_FIELD: u32 = 3;
const S_READY: u32 = 4;
const S_TEAM: u32 = 5;
const S_PREV: u32 = 6;
const S_HELD: u32 = 8;
const S_DIR: u32 = 9;
/// (Seat 0, the host) the seat whose team LEFT and RIGHT change on the TEAM field.
const S_TARGET: u32 = 10;

const NONE: u8 = 0xFF;
/// The fields, top to bottom: CO, colour, team, partner (with tag pairs), READY.
const F_CO: u8 = 0;
const F_COLOUR: u8 = 1;
const F_TEAM: u8 = 2;
const F_PARTNER: u8 = 3;
const F_READY: u8 = 4;
/// How many teams the letters run to (A..E).
const TEAMS: u8 = 5;

/// The five armies' colour codes in the order the pick cycles through them.
const COLOURS: [u8; 5] = [1, 2, 4, 3, 5];
const COLOUR_NAMES: [&str; 6] = ["", "Orange Star", "Blue Moon", "Green Earth", "Yellow Comet", "Black Hole"];

/// Whether seat `s` is READY on the army screen, read through a mailbox reader (the pad script's `teamready`).
pub fn seat_ready(read: &mut dyn FnMut(u32, &mut [u8]), s: usize) -> bool {
    let mut b = [0u8];
    read(seat(s) + S_READY, &mut b);
    b[0] == 1
}

pub fn players(core: &Core) -> usize {
    (core.raw_read_8(PLAYERS, -1) as usize).clamp(2, 5)
}

/// The page is up (the choices are being made).
pub fn active(core: &Core) -> bool {
    core.raw_read_8(INIT, -1) == 1 && core.raw_read_8(DONE, -1) == 0
}

/// Every seat is READY and the game's Teams screen is being sent on.
pub fn done(core: &Core) -> bool {
    core.raw_read_8(INIT, -1) == 1 && core.raw_read_8(DONE, -1) == 1
}

/// The keys the game gets while the page is up or finishing: none, then A's presses (the game's screen goes on to
/// the Rules on one). `None` when the page does not apply.
pub fn merge(core: &Core) -> Option<u32> {
    if active(core) {
        return Some(0);
    }
    if done(core) {
        // (A for 4 frames of 8, once the choices have been in a few frames)
        let t = core.raw_read_8(PULSE, -1);
        return Some(if t >= 6 && t % 8 < 4 { KEY_A } else { 0 });
    }
    None
}

fn seat(s: usize) -> u32 {
    SEATS + SEAT_SIZE * s as u32
}

struct Record {
    controller: u32,
    colour: u32,
    team: u32,
    co: u32,
    armies: u32,
}

fn record(core: &Core) -> Record {
    let rec = crate::tag_ui::record(core);
    let five = crate::five::active(core);
    Record {
        controller: rec + if five { 0x90 } else { 0x09 },
        colour: rec + if five { 0x98 } else { 0x0D },
        team: rec + if five { 0xA0 } else { 0x11 },
        co: rec + if five { 0xA8 } else { 0x1C },
        armies: crate::tag_ui::armies(core),
    }
}

fn tags(core: &Core) -> bool {
    // (UNRANKED has no tag pairs)
    crate::ds_weather::is_on(core) && !crate::unranked::on(core)
}

fn next_colour(core: &Core, n: usize, s: usize, step: isize) -> u8 {
    let current = core.raw_read_8(seat(s) + S_COLOUR, -1);
    let taken: Vec<u8> = (0..n)
        .filter(|&o| o != s)
        .map(|o| core.raw_read_8(seat(o) + S_COLOUR, -1))
        .collect();
    let start = COLOURS.iter().position(|&c| c == current).unwrap_or(0) as isize;
    (1..COLOURS.len() as isize)
        .map(|k| COLOURS[(start + step * k).rem_euclid(COLOURS.len() as isize) as usize])
        .find(|c| !taken.contains(c))
        .unwrap_or(current)
}

/// Every tick (any console): the room's size, and on a room's Teams screen the seats' selectors.
pub fn tick(core: &mut Core, inputs: &[u32]) {
    let n = inputs.len().clamp(2, 5);
    if core.raw_read_8(PLAYERS, -1) != n as u8 {
        core.raw_write_8(PLAYERS, -1, n as u8);
    }
    let on = crate::online::in_room_match(core) && crate::pvp::in_versus(core) && crate::pvp::on_teams_screen(core);
    if !on {
        // (the game's screen goes from its CO stage to its team stage and on to the Rules with a moment between each
        // where its task is gone: the page keeps its state through those, and ends with a longer absence)
        if core.raw_read_8(INIT, -1) == 1 && core.raw_read_8(DONE, -1) == 1 && core.raw_read_8(OFF, -1) < 40 {
            core.raw_write_8(OFF, -1, core.raw_read_8(OFF, -1) + 1);
            return;
        }
        if core.raw_read_8(INIT, -1) != 0 {
            core.raw_write_range(SEL, -1, &[0u8; SEL_LEN as usize]);
            core.raw_write_8(PLAYERS, -1, n as u8);
        }
        return;
    }
    publish(core, n);
    let rec = record(core);
    if core.raw_read_8(INIT, -1) == 0 {
        // Start from what the game's screen holds.
        for s in 0..n {
            let a = s as u32;
            let co = core.raw_read_8(rec.co + a, -1);
            let colour = core.raw_read_8(rec.colour + a, -1);
            core.raw_write_8(seat(s) + S_CO, -1, co);
            core.raw_write_8(seat(s) + S_COLOUR, -1, if COLOURS.contains(&colour) { colour } else { COLOURS[s % 5] });
            core.raw_write_8(seat(s) + S_PARTNER, -1, NONE);
            // (every seat its own team: a free-for-all unless the players choose teams)
            core.raw_write_8(seat(s) + S_TEAM, -1, s as u8);
            core.raw_write_8(seat(s) + S_FIELD, -1, F_CO);
            core.raw_write_8(seat(s) + S_READY, -1, 0);
            core.raw_write_16(seat(s) + S_PREV, -1, inputs[s] as u16);
        }
        // (two armies that came with one colour: the later one takes the next free one)
        for s in 1..n {
            let c = core.raw_read_8(seat(s) + S_COLOUR, -1);
            if (0..s).any(|o| core.raw_read_8(seat(o) + S_COLOUR, -1) == c) {
                let free = COLOURS.iter().copied().find(|c| !(0..s).any(|o| core.raw_read_8(seat(o) + S_COLOUR, -1) == *c));
                if let Some(free) = free {
                    core.raw_write_8(seat(s) + S_COLOUR, -1, free);
                }
            }
        }
        core.raw_write_8(INIT, -1, 1);
        return;
    }
    if core.raw_read_8(DONE, -1) == 1 {
        core.raw_write_8(OFF, -1, 0);
        let t = core.raw_read_8(PULSE, -1);
        core.raw_write_8(PULSE, -1, t.saturating_add(1));
        write_choices(core, n);
        return;
    }
    let list = crate::tag_ui::teams_list(core);
    let tag_on = tags(core);
    let note = core.raw_read_8(NOTE, -1);
    if note > 0 {
        core.raw_write_8(NOTE, -1, note - 1);
    }
    for s in 0..n {
        let keys = inputs[s];
        let prev = core.raw_read_16(seat(s) + S_PREV, -1) as u32;
        core.raw_write_16(seat(s) + S_PREV, -1, keys as u16);
        let pressed = keys & !prev;
        // A held left or right goes on after a moment (AW2's own menus' repeat).
        let dir = if keys & KEY_LEFT != 0 {
            KEY_LEFT
        } else if keys & KEY_RIGHT != 0 {
            KEY_RIGHT
        } else {
            0
        };
        let mut step_dir = pressed & (KEY_LEFT | KEY_RIGHT);
        if dir == 0 || pressed & (KEY_LEFT | KEY_RIGHT) != 0 {
            core.raw_write_8(seat(s) + S_HELD, -1, 0);
        } else {
            let h = core.raw_read_8(seat(s) + S_HELD, -1).saturating_add(1);
            if h >= 18 && (h - 18) % 5 == 0 {
                step_dir = dir;
            }
            core.raw_write_8(seat(s) + S_HELD, -1, h);
        }
        core.raw_write_8(seat(s) + S_DIR, -1, dir as u8);
        let ready = core.raw_read_8(seat(s) + S_READY, -1) == 1;
        let mut field = core.raw_read_8(seat(s) + S_FIELD, -1);
        if ready {
            if pressed & KEY_B != 0 {
                core.raw_write_8(seat(s) + S_READY, -1, 0);
            }
            continue;
        }
        let rows: Vec<u8> = if tag_on {
            vec![F_CO, F_COLOUR, F_TEAM, F_PARTNER, F_READY]
        } else {
            vec![F_CO, F_COLOUR, F_TEAM, F_READY]
        };
        let at = rows.iter().position(|&f| f == field).unwrap_or(0);
        if pressed & KEY_DOWN != 0 {
            field = rows[(at + 1) % rows.len()];
        }
        if pressed & KEY_UP != 0 {
            field = rows[(at + rows.len() - 1) % rows.len()];
        }
        core.raw_write_8(seat(s) + S_FIELD, -1, field);
        // The host picks whose team LEFT and RIGHT change (L and R), on the TEAM field; anywhere else it is its own.
        if s == 0 {
            let mut target = core.raw_read_8(seat(0) + S_TARGET, -1) as usize % n;
            if field != F_TEAM {
                target = 0;
            } else if pressed & KEY_R != 0 {
                target = (target + 1) % n;
            } else if pressed & KEY_L != 0 {
                target = (target + n - 1) % n;
            }
            core.raw_write_8(seat(0) + S_TARGET, -1, target as u8);
        }
        let step: isize = if step_dir == KEY_RIGHT {
            1
        } else if step_dir == KEY_LEFT {
            -1
        } else {
            0
        };
        if step != 0 {
            match field {
                F_CO if !list.is_empty() => {
                    let cur = core.raw_read_8(seat(s) + S_CO, -1) as isize;
                    let n = list.len() as isize;
                    core.raw_write_8(seat(s) + S_CO, -1, (cur + step).rem_euclid(n) as u8);
                    // (a partner is another CO than the main one)
                    let main = list[(cur + step).rem_euclid(n) as usize];
                    if core.raw_read_8(seat(s) + S_PARTNER, -1) == main {
                        core.raw_write_8(seat(s) + S_PARTNER, -1, NONE);
                    }
                }
                F_COLOUR => {
                    let c = next_colour(core, n, s, step);
                    core.raw_write_8(seat(s) + S_COLOUR, -1, c);
                }
                F_TEAM => {
                    let who = if s == 0 { core.raw_read_8(seat(0) + S_TARGET, -1) as usize % n } else { s };
                    let cur = core.raw_read_8(seat(who) + S_TEAM, -1) as isize;
                    core.raw_write_8(seat(who) + S_TEAM, -1, (cur + step).rem_euclid(TEAMS as isize) as u8);
                    // (a seat whose team the host changed has to say READY again)
                    core.raw_write_8(seat(who) + S_READY, -1, 0);
                }
                F_PARTNER if !list.is_empty() => {
                    let main = list.get(core.raw_read_8(seat(s) + S_CO, -1) as usize).copied();
                    let mut options: Vec<u8> = vec![NONE];
                    options.extend(list.iter().copied().filter(|&c| Some(c) != main));
                    let cur = core.raw_read_8(seat(s) + S_PARTNER, -1);
                    let i = options.iter().position(|&c| c == cur).unwrap_or(0) as isize;
                    let k = options.len() as isize;
                    core.raw_write_8(seat(s) + S_PARTNER, -1, options[(i + step).rem_euclid(k) as usize]);
                }
                _ => {}
            }
        }
        if pressed & (KEY_A | KEY_START) != 0 {
            // (A is READY wherever the cursor is, as the legend says; Up and Down only choose what to change)
            if teams_ok(core, n) {
                core.raw_write_8(seat(s) + S_READY, -1, 1);
            } else {
                // (all on one team is no battle: say so)
                core.raw_write_8(NOTE, -1, 110);
            }
        }
    }
    if (0..n).all(|s| core.raw_read_8(seat(s) + S_READY, -1) == 1) {
        if !teams_ok(core, n) {
            for s in 0..n {
                core.raw_write_8(seat(s) + S_READY, -1, 0);
            }
            core.raw_write_8(NOTE, -1, 110);
            return;
        }
        core.raw_write_8(DONE, -1, 1);
        core.raw_write_8(PULSE, -1, 0);
        write_choices(core, n);
    }
}

/// A battle's player block field holding the army's team (the game's own copy of the Teams record's byte).
const BLOCK_TEAM: u32 = 0x2A;
const BLOCK_COLOUR: u32 = 0x1A;

/// The seats' (team, colour) for the status bar: the choices while they are made, the battle's player blocks after.
fn publish(core: &Core, n: usize) {
    if let Some(p) = seat_picks(core) {
        crate::online::set_picks(p);
    } else if crate::online::in_room_match(core) && crate::pvp::in_versus(core) && crate::pvp::in_battle(core) {
        let block = |a: u32| crate::five::players(core) + 0x3C * a;
        let picks = (0..n as u32)
            .map(|s| (core.raw_read_8(block(s + 1) + BLOCK_TEAM, -1), core.raw_read_8(block(s + 1) + BLOCK_COLOUR, -1)))
            .collect();
        crate::online::set_picks(picks);
    }
}

/// Whether the seats' teams make a battle: at least two different ones.
fn teams_ok(core: &Core, n: usize) -> bool {
    let first = core.raw_read_8(seat(0) + S_TEAM, -1);
    (1..n).any(|s| core.raw_read_8(seat(s) + S_TEAM, -1) != first)
}

/// The choices into the game's Teams record.
fn write_choices(core: &mut Core, n: usize) {
    let rec = record(core);
    let tag_on = tags(core);
    for s in 0..n.min(rec.armies as usize).max(n.min(5)) {
        let a = s as u32;
        core.raw_write_8(rec.controller + a, -1, 1);
        let co = core.raw_read_8(seat(s) + S_CO, -1);
        let colour = core.raw_read_8(seat(s) + S_COLOUR, -1);
        if core.raw_read_8(rec.co + a, -1) != co {
            core.raw_write_8(rec.co + a, -1, co);
        }
        if core.raw_read_8(rec.colour + a, -1) != colour {
            core.raw_write_8(rec.colour + a, -1, colour);
        }
        let team = core.raw_read_8(seat(s) + S_TEAM, -1);
        if core.raw_read_8(rec.team + a, -1) != team {
            core.raw_write_8(rec.team + a, -1, team);
        }
        if tag_on {
            let p = core.raw_read_8(seat(s) + S_PARTNER, -1);
            core.raw_write_8(crate::tag::TEAMS_PARTNER + a, -1, p);
        }
    }
}

// --- Drawing (presentation only) -----------------------------------------------------------------

type Rgb = (u8, u8, u8);

fn colour_rgb(c: u8) -> Rgb {
    match c {
        1 => (232, 56, 40),
        2 => (56, 96, 216),
        3 => (48, 168, 72),
        4 => (232, 192, 32),
        _ => (64, 52, 72),
    }
}

fn faces() -> &'static std::sync::Mutex<std::collections::HashMap<u8, (Vec<u8>, [u8; 32])>> {
    static F: std::sync::OnceLock<std::sync::Mutex<std::collections::HashMap<u8, (Vec<u8>, [u8; 32])>>> =
        std::sync::OnceLock::new();
    F.get_or_init(Default::default)
}

/// A CO's name as the game writes it.
pub fn co_label(core: &Core, co: u8) -> String {
    let name = crate::co_new::ds_name(co).filter(|n| !n.is_empty()).unwrap_or_else(|| crate::tag_extras::co_name(core, co));
    name.iter().filter(|&&c| (0x20..0x7F).contains(&c)).map(|&c| c as char).collect()
}

/// `text` with selection arrows, cut down so it (and the highlight round it) never passes `max_w` pixels: "< text >",
/// else "<text>", else the text shortened with the arrows kept.
fn fit_arrows(core: &Core, text: &str, on: bool, max_w: i32) -> String {
    let w = |t: &str| crate::online::text_width(core, t);
    if !on {
        return text.to_string();
    }
    for cand in [format!("< {text} >"), format!("<{text}>")] {
        if w(&cand) <= max_w {
            return cand;
        }
    }
    let mut t: String = text.to_string();
    while !t.is_empty() && w(&format!("<{t}>")) > max_w {
        t.pop();
    }
    format!("<{t}>")
}

/// A CO's portrait scaled to `sz` pixels square at (x, y).
fn draw_face(core: &Core, cv: &mut crate::online::Rgba<'_>, co: u8, x: i32, y: i32, sz: i32) {
    let mut f = faces().lock().unwrap();
    let (px, pal) = f.entry(co).or_insert_with(|| {
        crate::ds_coselect::mug_for_face(core, co).unwrap_or_else(|| crate::tag_ui::portrait48(core, co))
    });
    for yy in 0..sz {
        for xx in 0..sz {
            let (sx, sy) = ((xx * 48 / sz) as usize, (yy * 48 / sz) as usize);
            let t = 6 * (sy / 8) + sx / 8;
            let b = px.get(32 * t + 4 * (sy % 8) + (sx % 8) / 2).copied().unwrap_or(0);
            let v = ((b >> (4 * (sx & 1))) & 15) as usize;
            let c = u16::from_le_bytes([pal[2 * v], pal[2 * v + 1]]);
            cv.put(x + xx, y + yy, crate::online::bgr(c));
        }
    }
}

/// A team's letter, as the game's Teams page names them.
pub fn team_letter(team: u8) -> char {
    (b'A' + team.min(TEAMS - 1)) as char
}

/// Each seat's team (0..=4) while the choices are being made, else `None`.
pub fn seat_teams(core: &Core) -> Option<Vec<u8>> {
    if !(active(core) || done(core)) {
        return None;
    }
    Some((0..players(core)).map(|s| core.raw_read_8(seat(s) + S_TEAM, -1)).collect())
}

/// The seats' (team, colour) while the choices are being made.
pub fn seat_picks(core: &Core) -> Option<Vec<(u8, u8)>> {
    seat_teams(core).map(|t| t.into_iter().enumerate().map(|(s, t)| (t, core.raw_read_8(seat(s) + S_COLOUR, -1))).collect())
}

pub fn draw(core: &Core, rgba: &mut [u8]) {
    if rgba.len() != crate::online::W * crate::online::H * 4 || (!active(core) && !(done(core) && crate::pvp::on_teams_screen(core))) {
        return;
    }
    let n = players(core);
    let list = crate::tag_ui::teams_list(core);
    let tag_on = tags(core);
    let local = crate::online::room_local_seat();
    let mut canvas = crate::online::Rgba(rgba);
    let cv = &mut canvas;
    cv.rect(0, 0, crate::online::W as i32, 160, crate::online::LIGHT_GRAY);
    cv.rect(0, 0, crate::online::W as i32, 15, crate::online::BAR);
    let title = "SELECT YOUR ARMY";
    let w = crate::online::text_width(core, title);
    cv.text(core, (crate::online::W as i32 - w) / 2, 2, title, crate::online::WHITE, crate::online::GRAY_INK);
    // The column headings: a strip under the title, over the fields' boxes.
    let (colour_x, team_x, partner_x) = columns(tag_on);
    cv.rect(0, 15, crate::online::W as i32, 11, crate::online::LIGHT_GRAY);
    let heading = |cv: &mut crate::online::Rgba<'_>, x: i32, t: &str| {
        let w = crate::online::text_width(core, t);
        cv.text(core, x + 14 - w / 2, 15, t, crate::online::GRAY_INK, crate::online::SHADE);
    };
    cv.text(core, 8, 15, "Player", crate::online::GRAY_INK, crate::online::SHADE);
    heading(cv, colour_x, "Colour");
    heading(cv, team_x, "Team");
    if tag_on {
        heading(cv, partner_x, "Pair");
    }
    let top = 27;
    let rows_h = 143 - top;
    let rh = (rows_h / n as i32).min(46);
    for s in 0..n {
        draw_row(core, cv, s, top + rh * s as i32, rh, &list, tag_on, local, n);
    }
    let me = local.min(n - 1);
    let my_field = core.raw_read_8(seat(me) + S_FIELD, -1);
    let my_ready = core.raw_read_8(seat(me) + S_READY, -1) == 1;
    let fits = |t: &str| crate::online::text_width(core, t) <= 228;
    let text: String = if done(core) {
        "Everyone is ready!".into()
    } else if core.raw_read_8(NOTE, -1) > 0 {
        "Pick at least two different teams.".into()
    } else if my_ready {
        "B: Change   Waiting for the others...".into()
    } else {
        let mut cands = vec![];
        if me == 0 && my_field == F_TEAM {
            cands.push("L R: Seat  Left Right: Team  A: READY");
            cands.push("L R: Seat  Left Right: Team");
        }
        if my_field == F_TEAM {
            cands.push("Up Down: Field  Left Right: Team  A: READY");
        }
        cands.push("Up Down: Field  Left Right: Change  A: READY");
        cands.push("Up Down: Field  Left Right: Change");
        cands.into_iter().find(|t| fits(t)).unwrap_or("A: READY").into()
    };
    crate::online::bar(cv, core, &text);
    let _ = COLOUR_NAMES;
}

/// The fields' columns (the left edge of the colour, team and partner boxes).
fn columns(tag_on: bool) -> (i32, i32, i32) {
    if tag_on { (94, 124, 154) } else { (116, 148, 0) }
}

/// The width of a field's box (the choice between its two arrows).
const BOX_W: i32 = 28;

/// A field's box at x: its choice (drawn by `content` at x + 7), between arrows on yellow when it is being changed.
fn field_box(core: &Core, cv: &mut crate::online::Rgba<'_>, x: i32, y: i32, h: i32, on: bool, content: impl FnOnce(&mut crate::online::Rgba<'_>, i32)) {
    if on {
        cv.rect(x, y + 1, BOX_W, h - 2, crate::online::YELLOW);
        cv.text(core, x + 1, y + h / 2 - 5, "<", crate::online::INK, crate::online::SHADE);
        cv.text(core, x + BOX_W - 6, y + h / 2 - 5, ">", crate::online::INK, crate::online::SHADE);
    }
    content(cv, x + 7);
}

/// One seat's row: face, gamertag over CO, then the colour chip, team letter, partner (with tag pairs) and the READY
/// badge, each in its own box (presentation only). The row of 2 or 3 seats is taller; the fields are the same.
#[allow(clippy::too_many_arguments)]
fn draw_row(core: &Core, cv: &mut crate::online::Rgba<'_>, s: usize, y: i32, rh: i32, list: &[u8], tag_on: bool, local: usize, n: usize) {
    let co = list.get(core.raw_read_8(seat(s) + S_CO, -1) as usize).copied();
    let colour = core.raw_read_8(seat(s) + S_COLOUR, -1);
    let team = core.raw_read_8(seat(s) + S_TEAM, -1);
    let partner = core.raw_read_8(seat(s) + S_PARTNER, -1);
    let field = core.raw_read_8(seat(s) + S_FIELD, -1);
    let ready = core.raw_read_8(seat(s) + S_READY, -1) == 1;
    let mine = s == local;
    let sel = |f: u8| mine && !ready && field == f;
    // The host on the TEAM field changes the team of the seat it has picked (its own at first).
    let host_field = core.raw_read_8(seat(0) + S_FIELD, -1);
    let host_ready = core.raw_read_8(seat(0) + S_READY, -1) == 1;
    let target = core.raw_read_8(seat(0) + S_TARGET, -1) as usize % n;
    let team_on = if local == 0 { host_field == F_TEAM && !host_ready && target == s } else { sel(F_TEAM) };
    let h = rh - 2;
    let ink = crate::online::INK;
    let shade = crate::online::SHADE;
    // The row's window: a thin frame, cream for the player's own.
    cv.rect(1, y - 1, 238, h + 2, ink);
    cv.rect(2, y, 236, h, if mine { crate::online::CREAM } else { crate::online::WHITE });
    cv.rect(2, y, 4, h, colour_rgb(colour));
    let big = n <= 3;
    let sz = (h - 2).min(if big { 32 } else { 24 });
    if let Some(co) = co {
        draw_face(core, cv, co, 8, y + (h - sz) / 2, sz);
    }
    let tx = 8 + sz + 3;
    let name: String = crate::online::room_name(s).chars().take(10).collect();
    let name_ink = if mine { crate::online::BLUE } else { ink };
    let (ny, cy) = if big { (y + 4, y + h - 15) } else { (y, y + h - 11) };
    cv.text(core, tx, ny, &name, name_ink, shade);
    let (colour_x, team_x, partner_x) = columns(tag_on);
    let co_name = co.map(|c| co_label(core, c)).unwrap_or_default();
    let co_text = fit_arrows(core, &co_name, sel(F_CO), colour_x - 3 - tx);
    let w = crate::online::text_width(core, &co_text);
    if sel(F_CO) {
        cv.rect(tx - 2, cy - 1, w + 4, 11, crate::online::YELLOW);
    }
    cv.text(core, tx, cy, &co_text, ink, shade);
    // Colour chip.
    let chip_h = (h - 8).min(20);
    field_box(core, cv, colour_x, y, h, sel(F_COLOUR), |cv, x| {
        cv.rect(x - 1, y + (h - chip_h) / 2 - 1, 16, chip_h + 2, ink);
        cv.rect(x, y + (h - chip_h) / 2, 14, chip_h, colour_rgb(colour));
    });
    // Team: its letter on a plate like READY's.
    field_box(core, cv, team_x, y, h, team_on, |cv, x| {
        let ph = (h - 8).min(16);
        let py = y + (h - ph) / 2;
        cv.rect(x - 1, py - 1, 16, ph + 2, ink);
        cv.rect(x, py, 14, ph, crate::online::BLUE);
        let l = team_letter(team).to_string();
        let lw = crate::online::text_width(core, &l);
        cv.text(core, x + (14 - lw) / 2, py + (ph - 11) / 2, &l, crate::online::WHITE, crate::online::BLUE);
    });
    // Partner: a small face, "-" for none.
    if tag_on {
        field_box(core, cv, partner_x, y, h, sel(F_PARTNER), |cv, x| {
            if partner == NONE {
                let w = crate::online::text_width(core, "-");
                cv.text(core, x + 7 - w / 2, y + h / 2 - 5, "-", crate::online::GRAY_INK, shade);
            } else {
                draw_face(core, cv, partner, x - 1, y + (h - 16) / 2, 16);
            }
        });
    }
    // READY badge.
    let (rx, rw) = (190, 46);
    let (label, plate, lab_ink) = if ready {
        ("READY", crate::online::BLUE, crate::online::WHITE)
    } else if sel(F_READY) {
        ("READY?", crate::online::YELLOW, ink)
    } else {
        ("...", crate::online::LIGHT_GRAY, crate::online::GRAY_INK)
    };
    cv.rect(rx - 1, y + 2, rw + 2, h - 4, ink);
    cv.rect(rx, y + 3, rw, h - 6, plate);
    let lw = crate::online::text_width(core, label);
    cv.text(core, rx + (rw - lw) / 2, y + h / 2 - 5, label, lab_ink, shade);
}
