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

/// The five armies' colour codes in the order the pick starts with; a seat's colour field holds its choice (those five, then the
/// army skins' codes, [`crate::army_skin::order`]), and the game's colour is made of the choices when the seats are READY
/// ([`write_choices`]).
const COLOURS: [u8; 5] = [1, 2, 4, 3, 5];

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

pub(crate) struct Record {
    pub controller: u32,
    pub colour: u32,
    pub team: u32,
    pub co: u32,
    pub armies: u32,
}

pub(crate) fn record(core: &Core) -> Record {
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

/// The Teams record's controller byte of each army (1 = human, 0 = the computer), for the test log.
pub fn controller_bytes(core: &Core) -> Vec<u8> {
    let rec = record(core);
    (0..rec.armies.min(5))
        .map(|a| core.raw_read_8(rec.controller + a, -1))
        .collect()
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
    crate::army_skin::step_choice(current, &taken, step)
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
            core.raw_write_8(
                seat(s) + S_COLOUR,
                -1,
                if (1..=5).contains(&colour) {
                    colour
                } else {
                    COLOURS[s % 5]
                },
            );
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
                let free = COLOURS
                    .iter()
                    .copied()
                    .find(|c| !(0..s).any(|o| core.raw_read_8(seat(o) + S_COLOUR, -1) == *c));
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
        // (two armies are always two teams: no TEAM field)
        let mut rows: Vec<u8> = vec![F_CO, F_COLOUR, F_TEAM, F_PARTNER, F_READY];
        rows.retain(|&f| (tag_on || f != F_PARTNER) && (n > 2 || f != F_TEAM));
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
                    let who = if s == 0 {
                        core.raw_read_8(seat(0) + S_TARGET, -1) as usize % n
                    } else {
                        s
                    };
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
            .map(|s| {
                (
                    core.raw_read_8(block(s + 1) + BLOCK_TEAM, -1),
                    core.raw_read_8(block(s + 1) + BLOCK_COLOUR, -1),
                )
            })
            .collect();
        crate::online::set_picks(picks);
    }
}

/// Whether the seats' teams make a battle: at least two different ones.
fn teams_ok(core: &Core, n: usize) -> bool {
    if n == 2 {
        return true;
    }
    let first = core.raw_read_8(seat(0) + S_TEAM, -1);
    (1..n).any(|s| core.raw_read_8(seat(s) + S_TEAM, -1) != first)
}

/// The choices into the game's Teams record.
fn write_choices(core: &mut Core, n: usize) {
    let rec = record(core);
    let tag_on = tags(core);
    // (the game's colours of the choices, and the colour the skin sits on)
    let choices: Vec<u8> = (0..n).map(|s| core.raw_read_8(seat(s) + S_COLOUR, -1)).collect();
    let (values, hosts) = crate::army_skin::assign(&choices);
    for (i, h) in hosts.iter().enumerate() {
        if crate::army_skin::host_of(core, i) != *h {
            crate::army_skin::set_host_of(core, i, *h);
        }
    }
    for s in 0..n.min(rec.armies as usize).max(n.min(5)) {
        let a = s as u32;
        core.raw_write_8(rec.controller + a, -1, 1);
        let co = core.raw_read_8(seat(s) + S_CO, -1);
        let colour = values[s];
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

/// Face cache: CO -> (tiles, palette, from the CO screens' mug). A face drawn from the fallback is redone once the pack
/// is there, so an early draw never leaves a wrong picture behind.
type FaceCache = std::collections::HashMap<u8, (Vec<u8>, [u8; 32], bool)>;

fn faces() -> &'static std::sync::Mutex<FaceCache> {
    static F: std::sync::OnceLock<std::sync::Mutex<FaceCache>> = std::sync::OnceLock::new();
    F.get_or_init(Default::default)
}

/// A CO's name as the game writes it.
pub fn co_label(core: &Core, co: u8) -> String {
    let name = crate::co_new::ds_name(co)
        .filter(|n| !n.is_empty())
        .unwrap_or_else(|| crate::tag_extras::co_name(core, co));
    name.iter()
        .filter(|&&c| (0x20..0x7F).contains(&c))
        .map(|&c| c as char)
        .collect()
}

/// `text` with selection arrows, cut down so it (and the highlight round it) never passes `max_w` pixels: "< text >",
/// else "<text>", else the text shortened with the arrows kept.
pub(crate) fn fit_arrows(core: &Core, text: &str, on: bool, max_w: i32) -> String {
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

/// A CO's Teams card portrait as the game's own card draws it (its presentation row's 48 x 48 face, [`crate::tag_ui::portrait48`]),
/// inside the card's frame: 46 x 46 pixels one to one at (x, y).
pub(crate) fn draw_card_face(core: &Core, cv: &mut crate::online::Rgba<'_>, co: u8, x: i32, y: i32) {
    let (px, pal) = crate::tag_ui::portrait48_raw(core, co);
    for yy in 0..46usize {
        for xx in 0..46usize {
            let (sx, sy) = (xx + 1, yy + 1);
            let t = 6 * (sy / 8) + sx / 8;
            let b = px.get(32 * t + 4 * (sy % 8) + (sx % 8) / 2).copied().unwrap_or(0);
            let v = ((b >> (4 * (sx & 1))) & 15) as usize;
            if v != 0 {
                let c = u16::from_le_bytes([pal[2 * v], pal[2 * v + 1]]);
                cv.put(x + xx as i32, y + yy as i32, crate::online::bgr(c));
            }
        }
    }
}

/// A CO's portrait scaled to `sz` pixels square at (x, y).
pub(crate) fn draw_face(core: &Core, cv: &mut crate::online::Rgba<'_>, co: u8, x: i32, y: i32, sz: i32) {
    let mut f = faces().lock().unwrap();
    if f.get(&co).is_none_or(|e| !e.2 && crate::ds_pack::pack().is_some()) {
        let e = match crate::ds_coselect::mug_for_face(core, co) {
            Some((t, p)) => (t, p, true),
            None => {
                let (t, p) = crate::tag_ui::portrait48(core, co);
                (t, p, false)
            }
        };
        f.insert(co, e);
    }
    let (px, pal, _) = &f[&co];
    // Sturm's mug is mostly armour: at this size only the cap, visor and eyes read, so those are what is shown.
    let (x0, y0, span) = if co == crate::sturm_pairs::STURM {
        (6usize, 0usize, 36i32)
    } else if crate::tag::ds_id(co) == Some(crate::ds_coselect::VON_BOLT_DS) {
        // Von Bolt: the old man in his machine's dome, without the strip above and the floor below.
        (0, 10, 36)
    } else {
        (0, 0, 48)
    };
    for yy in 0..sz {
        for xx in 0..sz {
            let (sx, sy) = (x0 + (xx * span / sz) as usize, y0 + (yy * span / sz) as usize);
            let t = 6 * (sy / 8) + sx / 8;
            let b = px.get(32 * t + 4 * (sy % 8) + (sx % 8) / 2).copied().unwrap_or(0);
            let v = ((b >> (4 * (sx & 1))) & 15) as usize;
            let c = u16::from_le_bytes([pal[2 * v], pal[2 * v + 1]]);
            cv.put(x + xx, y + yy, crate::online::bgr(c));
        }
    }
}

/// `team`'s place among the teams in use (`teams` holds every seat's): for display, so that A, A, C, C reads A, A, B, B.
pub fn compact_team(teams: &[u8], team: u8) -> u8 {
    let mut used: Vec<u8> = teams.to_vec();
    used.sort_unstable();
    used.dedup();
    used.iter().position(|&t| t == team).unwrap_or(team as usize) as u8
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
    Some(
        (0..players(core))
            .map(|s| core.raw_read_8(seat(s) + S_TEAM, -1))
            .collect(),
    )
}

/// The seats' (team, colour) while the choices are being made.
pub fn seat_picks(core: &Core) -> Option<Vec<(u8, u8)>> {
    seat_teams(core).map(|t| {
        // (the game's colours of the choices: the skin's seat has the colour the skin sits on)
        let choices: Vec<u8> = (0..t.len()).map(|s| core.raw_read_8(seat(s) + S_COLOUR, -1)).collect();
        let (values, hosts) = crate::army_skin::assign(&choices);
        crate::army_skin::present(hosts);
        t.into_iter().enumerate().map(|(s, t)| (t, values[s])).collect()
    })
}

/// (Once everyone is READY the page stays up while the game's own Teams stages go by (its Choose-a-CO and alliance
/// pictures would show the screen's old picks for a moment), until the page's state is cleared as the Rules come up.)
///
/// The page is AW2's own Teams screen ([`crate::army_cards`]): the frame the game drew is kept and the seats' cards,
/// windows and the help box are drawn over it.
pub fn draw(core: &Core, rgba: &mut [u8]) {
    if rgba.len() != crate::online::W * crate::online::H * 4 || (!active(core) && !done(core)) {
        return;
    }
    use crate::army_cards::{Field, Help, Seat};
    let n = players(core);
    let list = crate::tag_ui::teams_list(core);
    let tag_on = tags(core);
    let local = crate::online::room_local_seat();
    let teams: Vec<u8> = (0..n).map(|s| core.raw_read_8(seat(s) + S_TEAM, -1)).collect();
    let letters = crate::army_cards::letters(&teams);
    // The host on the TEAM field changes the team of the seat it has picked (its own at first).
    let host_field = core.raw_read_8(seat(0) + S_FIELD, -1);
    let host_ready = core.raw_read_8(seat(0) + S_READY, -1) == 1;
    let target = core.raw_read_8(seat(0) + S_TARGET, -1) as usize % n;
    let seats: Vec<Seat> = (0..n)
        .map(|s| {
            let ready = core.raw_read_8(seat(s) + S_READY, -1) == 1;
            let mine = s == local;
            let f = core.raw_read_8(seat(s) + S_FIELD, -1);
            let mut field = if mine && !ready {
                Some(match f {
                    F_CO => Field::Co,
                    F_COLOUR => Field::Colour,
                    F_TEAM => Field::Team,
                    F_PARTNER => Field::Partner,
                    _ => Field::Ready,
                })
            } else {
                None
            };
            // (the host's TEAM field is on the seat it picked, wherever that is)
            if n > 2 && local == 0 {
                field = if host_field == F_TEAM && !host_ready && target == s {
                    Some(Field::Team)
                } else if mine && f == F_TEAM {
                    None
                } else {
                    field
                };
            }
            Seat {
                name: crate::online::room_name(s),
                co: list.get(core.raw_read_8(seat(s) + S_CO, -1) as usize).copied(),
                colour: core.raw_read_8(seat(s) + S_COLOUR, -1),
                team: (n > 2).then(|| {
                    // (the team being changed shows its own letter)
                    if field == Some(Field::Team) {
                        teams[s]
                    } else {
                        letters[s]
                    }
                }),
                partner: core.raw_read_8(seat(s) + S_PARTNER, -1),
                ready,
                mine,
                field,
            }
        })
        .collect();
    let me = local.min(n - 1);
    let my_field = core.raw_read_8(seat(me) + S_FIELD, -1);
    let my_ready = core.raw_read_8(seat(me) + S_READY, -1) == 1;
    let fits = |t: &str| crate::online::text_width(core, t) <= 228;
    let mut lines: Vec<String> = Vec::new();
    if done(core) {
        lines.push("Everyone is ready!".into());
    } else if core.raw_read_8(NOTE, -1) > 0 {
        lines.push("Pick at least two different teams.".into());
    } else if my_ready {
        lines.push("Waiting for the others...".into());
        lines.push("B: Change".into());
    } else {
        // (what the field is, and the keys)
        let partner = core.raw_read_8(seat(me) + S_PARTNER, -1);
        let co = list.get(core.raw_read_8(seat(me) + S_CO, -1) as usize).copied();
        lines.push(match my_field {
            F_CO => "Choose a CO.".to_string(),
            F_COLOUR => "Choose an army colour.".to_string(),
            F_TEAM if me == 0 && n > 2 => "Choose a team. L R: another seat's.".to_string(),
            F_TEAM => "Choose a team.".to_string(),
            F_PARTNER if partner == NONE => "Partner: none. Choose a partner CO.".to_string(),
            F_PARTNER => match co {
                Some(co) => format!(
                    "Partner: {} ({}%)",
                    co_label(core, partner),
                    crate::tag::compatibility(co, partner)
                ),
                None => format!("Partner: {}", co_label(core, partner)),
            },
            _ => "Everyone ready? Press A.".to_string(),
        });
        let cands = [
            "Up Down: Field  Left Right: Change  A: READY",
            "Up Down: Field  Left Right: Change",
            "A: READY",
        ];
        lines.push(cands.iter().find(|t| fits(t)).copied().unwrap_or("A: READY").into());
    }
    crate::army_cards::draw(core, rgba, &seats, tag_on, &Help { lines });
}
