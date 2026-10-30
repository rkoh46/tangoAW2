//! The army screen of Versus, drawn from AW2's own Teams screen (presentation only): online (`online_teams`, every
//! seat choosing at once) and offline with the pack (`ds_coselect::apply`, the game's own screen running underneath
//! and one pad driving it).
//!
//! The picture is AW2's Teams screen as the game drew it (the world-map ground, the TEAMS title, the PRESS A tag: the
//! frame this is drawn over is kept), and what the game puts there is put there again for every seat, where the game
//! puts it: a card per army (the CO's Teams portrait, the army's emblem in its lower left corner, the green frame,
//! the yellow 1P/2P/CP tag sampled from the game's own frame), and under it the seat's window (AW2's window: gamertag,
//! CO, team, and the partner box that holds the partner's small face); the help box is the game's pink plate with its
//! own font. The game's own cards show the Teams record's choices as the game last drew them, which online are not
//! the seats' current ones, so the card band is redrawn whole.

use crate::online::{self, Rgb, Rgba, BLUE, CREAM, GRAY_INK, INK, LIGHT_GRAY, SHADE, WHITE, YELLOW};
use crate::online_teams::{co_label, compact_team, draw_card_face, draw_face, fit_arrows, team_letter};
use mgba::core::Core;
use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

/// "No partner" in a seat's partner byte.
pub const NONE: u8 = 0xFF;

/// What a seat's window has selected (its cursor is on it).
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Field {
    Co,
    Colour,
    Team,
    Partner,
    Ready,
    /// The card's 1P / CP tag (offline: human or computer).
    Controller,
}

pub struct Seat {
    pub name: String,
    pub co: Option<u8>,
    /// A colour choice (1..5, or an army skin's code).
    pub colour: u8,
    /// The team's letter place (already counted over the teams in use); `None`: the seat has no team to show.
    pub team: Option<u8>,
    pub partner: u8,
    pub ready: bool,
    /// The seat of the player looking (its window is cream).
    pub mine: bool,
    pub field: Option<Field>,
}

/// The game's card: 48 x 48 with a green frame, at y 36; the first card's left edge and the pitch by the number of cards
/// (read from the game's own Teams screen).
const CARD_Y: i32 = 36;
const CARD: i32 = 48;
const FRAME: Rgb = (0, 41, 0);

fn layout(n: usize) -> (i32, i32) {
    match n {
        2 => (46, 96),
        3 => (22, 72),
        4 => (8, 58),
        _ => (0, 48),
    }
}

type Tag = Vec<(i32, i32, Rgb)>;

/// The tags seen so far, a card's each (x from the tag's left edge, y from the tag row): a frame that has none (the game's
/// screen changing stage) draws the last ones seen.
fn tag_cache() -> &'static Mutex<Vec<Tag>> {
    static C: OnceLock<Mutex<Vec<Tag>>> = OnceLock::new();
    C.get_or_init(Default::default)
}

/// Where a card's tag starts, from the card's left edge (the five-card layout's cards are narrower).
fn tag_x(n: usize, left: i32) -> i32 {
    left + if n >= 5 { 33 } else { 41 }
}

fn px(rgba: &[u8], x: i32, y: i32) -> Rgb {
    let o = 4 * (online::W * y as usize + x as usize);
    (rgba[o], rgba[o + 1], rgba[o + 2])
}

fn yellow(c: Rgb) -> bool {
    c.0 > 230 && c.1 > 230 && c.2 < 110
}

fn bright(c: Rgb) -> bool {
    yellow(c) || (c.0.min(c.1).min(c.2) > 200)
}

/// The game's 1P / 2P / CP tags from its frame, one per card (a yellow 1P, a white CP): the bright letters and their dark edge
/// at the place the game puts them (the yellow ones give the row), moved to the cards' tag row. A card whose tag is not there
/// (the game's screen fading or changing stage) has an empty one; `None` when no card has any.
fn sample_tags(rgba: &[u8], n: usize) -> Option<Vec<Tag>> {
    let row = (24..130)
        .find(|&y| (0..online::W as i32).any(|x| yellow(px(rgba, x, y))))
        .unwrap_or(CARD_Y + 3);
    let (first, pitch) = layout(n);
    let inside = |x: i32, y: i32| (0..online::W as i32).contains(&x) && (0..160).contains(&y);
    let mut tags = Vec::new();
    for s in 0..n {
        let ox = tag_x(n, first + pitch * s as i32);
        let mut t = Tag::new();
        for y in row - 1..row + 11 {
            for x in ox - 1..ox + 14 {
                if !inside(x, y) {
                    continue;
                }
                let c = px(rgba, x, y);
                let near_bright = |dist: i32| {
                    (-dist..=dist).any(|dy| {
                        (-dist..=dist).any(|dx| {
                            inside(x + dx, y + dy)
                                && (ox - 1..ox + 14).contains(&(x + dx))
                                && bright(px(rgba, x + dx, y + dy))
                        })
                    })
                };
                let dark = (c.0 as u32 + c.1 as u32 + c.2 as u32) < 120;
                if bright(c) || (dark && near_bright(1)) {
                    t.push((x - ox, y - row + CARD_Y + 3, c));
                }
            }
        }
        // (a tag is letters: a face's stray white pixels are fewer)
        if t.iter().filter(|p| bright(p.2)).count() < 12 {
            t.clear();
        }
        tags.push(t);
    }
    tags.iter().any(|t| !t.is_empty()).then_some(tags)
}

/// The most common colour of the map's ground (the sea) in the band the cards are drawn in.
fn sea(rgba: &[u8]) -> Rgb {
    let mut count: HashMap<Rgb, u32> = HashMap::new();
    for y in 20..130 {
        for x in 0..online::W as i32 {
            *count.entry(px(rgba, x, y)).or_default() += 1;
        }
    }
    count
        .into_iter()
        .max_by_key(|&(c, k)| (k, c))
        .map(|(c, _)| c)
        .unwrap_or((152, 224, 232))
}

fn emblem(core: &Core, cv: &mut Rgba<'_>, colour: u8, x: i32, y: i32) {
    let (w, pixels) = if colour >= crate::army_skin::SKIN {
        let n = crate::army_skin::skins().len().max(1);
        (
            16usize,
            crate::army_skin::emblem_pixels((colour - crate::army_skin::SKIN) as usize % n),
        )
    } else if let Some((w, _, p)) = crate::pvp::emblem_pixels(core, colour.clamp(1, 5) as u32) {
        (w, p)
    } else {
        return;
    };
    for (i, c) in pixels.iter().enumerate() {
        if let Some(c) = c {
            cv.put(x + (i % w) as i32, y + (i / w) as i32, *c);
        }
    }
}

/// The partner's box: AW2's grey slot with the partner's small face in it ("-" when there is none).
fn partner_box(core: &Core, cv: &mut Rgba<'_>, partner: u8, x: i32, y: i32) {
    cv.rect(x, y, 16, 16, GRAY_INK);
    cv.rect(x + 1, y + 1, 14, 14, LIGHT_GRAY);
    if partner == NONE {
        let w = online::text_width(core, "-");
        cv.text(core, x + 8 - w / 2, y + 2, "-", GRAY_INK, SHADE);
    } else {
        draw_face(core, cv, partner, x + 1, y + 1, 14);
    }
}

fn yellow_frame(cv: &mut Rgba<'_>, x: i32, y: i32, w: i32, h: i32) {
    cv.rect(x, y, w, h, YELLOW);
}

/// One line of help in the pink plate's text.
pub struct Help {
    pub lines: Vec<String>,
}

/// Draw the screen over the game's own Teams frame in `rgba` (a 240 x 160 RGBA frame).
pub fn draw(core: &Core, rgba: &mut [u8], seats: &[Seat], tag_pairs: bool, help: &Help) {
    let n = seats.len().clamp(2, 5);
    if rgba.len() != online::W * online::H * 4 || seats.len() < 2 {
        return;
    }
    // The game's tags, from this frame, or the last frame that had them.
    let tags = match sample_tags(rgba, n) {
        Some(t) => {
            let mut c = tag_cache().lock().unwrap();
            for (k, tag) in t.iter().enumerate() {
                if tag.is_empty() {
                    continue;
                }
                if k < c.len() {
                    c[k] = tag.clone();
                } else {
                    c.resize(k + 1, Vec::new());
                    c[k] = tag.clone();
                }
            }
            c.clone()
        }
        None => tag_cache().lock().unwrap().clone(),
    };
    let ground = sea(rgba);
    let mut canvas = Rgba(rgba);
    let cv = &mut canvas;
    cv.rect(0, CARD_Y - 3, online::W as i32, 134 - (CARD_Y - 3), ground);
    let (first, pitch) = layout(n);
    for (s, seat) in seats.iter().take(n).enumerate() {
        let left = first + pitch * s as i32;
        // The card: the CO's portrait, the army's emblem, the frame, the game's tag.
        cv.rect(left, CARD_Y, CARD, CARD, ground);
        if let Some(co) = seat.co {
            draw_card_face(core, cv, co, left + 1, CARD_Y + 1);
        }
        for (x, y) in [(left, CARD_Y), (left + CARD - 1, CARD_Y)] {
            cv.rect(x, y, 1, CARD, FRAME);
        }
        for y in [CARD_Y, CARD_Y + CARD - 1] {
            cv.rect(left, y, CARD, 1, FRAME);
        }
        if seat.field == Some(Field::Colour) {
            yellow_frame(cv, left + 1, CARD_Y + 27, 20, 20);
        }
        emblem(core, cv, seat.colour, left + 3, CARD_Y + 29);
        if let Some(t) = tags.get(s) {
            let ox = tag_x(n, left);
            if seat.field == Some(Field::Controller) {
                if let (Some(x0), Some(x1)) = (t.iter().map(|p| p.0).min(), t.iter().map(|p| p.0).max()) {
                    yellow_frame(cv, ox + x0 - 2, CARD_Y + 1, x1 - x0 + 5, 12);
                }
            }
            for &(x, y, c) in t {
                cv.put(ox + x, y, c);
            }
        }
        // The seat's window under the card.
        let w = (pitch - 2).min(if n <= 3 { 84 } else { 46 }).max(46);
        let wx = left + CARD / 2 - w / 2;
        let wy = 85;
        let wh = 44;
        cv.window(wx, wy, w, wh);
        let body = if seat.ready {
            BLUE
        } else if seat.field == Some(Field::Ready) {
            YELLOW
        } else if seat.mine {
            CREAM
        } else {
            WHITE
        };
        cv.rect(wx + 2, wy + 2, w - 4, wh - 4, body);
        online::audit::window(wx + 2, wy + 2, w - 4, wh - 4);
        let name = online::fit(core, &seat.name.chars().take(10).collect::<String>(), w - 6);
        let name_ink = if seat.ready {
            WHITE
        } else if seat.field == Some(Field::Ready) {
            INK
        } else if seat.mine {
            BLUE
        } else {
            INK
        };
        cv.text(core, wx + 3, wy + 2, &name, name_ink, SHADE);
        let co_name = seat.co.map(|c| co_label(core, c)).unwrap_or_default();
        if seat.ready {
            let l = "READY";
            let lw = online::text_width(core, l);
            cv.text(core, wx + (w - lw) / 2, wy + 13, l, WHITE, BLUE);
        } else {
            let on = seat.field == Some(Field::Co);
            let text = fit_arrows(core, &co_name, on, w - 9);
            let tw = online::text_width(core, &text);
            if on {
                yellow_frame(cv, wx + 2, wy + 13, tw + 3, 11);
            }
            cv.text(core, wx + 3, wy + 13, &text, INK, SHADE);
        }
        // Team and partner box.
        let ry = wy + 24;
        let mut x = wx + 3;
        if let Some(team) = seat.team {
            let on = seat.field == Some(Field::Team);
            if on {
                yellow_frame(cv, x - 1, ry, 24, 16);
                cv.text(core, x, ry + 2, "<", INK, SHADE);
                cv.text(core, x + 17, ry + 2, ">", INK, SHADE);
            }
            let px_ = x + if on { 5 } else { 1 };
            cv.rect(px_, ry + 1, 14, 14, INK);
            cv.rect(px_ + 1, ry + 2, 12, 12, BLUE);
            let l = team_letter(team).to_string();
            let lw = online::text_width(core, &l);
            cv.text(core, px_ + 1 + (12 - lw) / 2, ry + 2, &l, WHITE, BLUE);
            x += 26;
        }
        if tag_pairs {
            let on = seat.field == Some(Field::Partner);
            if on {
                yellow_frame(cv, x - 2, ry - 1, 20, 18);
            }
            partner_box(core, cv, seat.partner, x, ry);
        }
    }
    // The help box: the game's pink plate.
    cv.plate(2, 133, 236, 25);
    let k = help.lines.len().min(2) as i32;
    for (i, l) in help.lines.iter().take(2).enumerate() {
        let l = online::fit(core, l, 228);
        let w = online::text_width(core, &l);
        let y = 133 + (25 - 11 * k) / 2 + 11 * i as i32 - 1;
        cv.text(
            core,
            (online::W as i32 - w) / 2,
            y,
            &l,
            online::PLATE_INK,
            online::PLATE_GREY,
        );
    }
}

/// Team letters as the pages show them: the teams in use counted from A.
pub fn letters(teams: &[u8]) -> Vec<u8> {
    teams.iter().map(|&t| compact_team(teams, t)).collect()
}
