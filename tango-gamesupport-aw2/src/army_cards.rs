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
use crate::online_teams::{co_label, compact_team, draw_card_face, draw_portrait_part, fit_arrows};
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
    /// The card's tag ("1P", "CP"): the game's own tag sprite drawn by us, for a screen whose frame is not the game's own Teams screen (the Gauntlet's: [`teams_frame`] and no tag to sample
    /// from it). Such a screen (every seat tagged) also centres three cards and shows every CO name whole (two lines, no arrows, when the card is narrow). `None`: the game's tag is taken
    /// from the frame as before.
    pub tag: Option<&'static str>,
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
    // (the game's tag row: 39 with the partner boxes, 55 without; any other row is a frame of the screen on its way)
    (matches!(row, 39 | 55) && tags.iter().any(|t| !t.is_empty())).then_some(tags)
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

pub(crate) fn emblem(core: &Core, cv: &mut Rgba<'_>, colour: u8, x: i32, y: i32) {
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

/// The Teams screen's ground (BG3: the world map the missions are played over, its tiles, map and palettes are the cartridge's: read once, as seen through the screen's scroll) and its title
/// banner (the title font's glyphs as 16 x 32 sprites in the banner's palette), for a screen of ours that has the Teams look without the game's own Teams screen under it.
const GROUND_TILES: u32 = 0x0822_FEF0;
const GROUND_MAP: u32 = 0x0822_F9AC;
const GROUND_PALETTES: u32 = 0x0823_44AC;
/// BG3's scroll on the Teams screen.
const GROUND_SCROLL: (usize, usize) = (281 % 256, 231);
const BANNER_PALETTE: u32 = 0x080F_6164;
/// The sprite ids of the card tags (the game's 1P and CP) and their place from the card's left edge (the tag is 16 wide: it stands out of a card that has room beside it).
const TAG_1P: u32 = 74;
const TAG_CP: u32 = 78;

fn ground_picture(core: &Core) -> Option<&'static Vec<Rgb>> {
    static G: OnceLock<Option<Vec<Rgb>>> = OnceLock::new();
    G.get_or_init(|| {
        let rd = |at: u32, n: usize| {
            let mut b = vec![0u8; n];
            core.raw_read_range(at, -1, &mut b);
            b
        };
        let tiles = crate::ds_art::lz10(&rd(GROUND_TILES, 0x6000))?;
        let map = crate::ds_art::lz10(&rd(GROUND_MAP, 0x900))?;
        let pal = rd(GROUND_PALETTES, 0xC0);
        if tiles.len() < 0x5800 || map.len() < 0x800 {
            return None;
        }
        let mut full = vec![(0u8, 0u8, 0u8); 256 * 256];
        for ty in 0..32usize {
            for tx in 0..32usize {
                let e = u16::from_le_bytes([map[2 * (ty * 32 + tx)], map[2 * (ty * 32 + tx) + 1]]) as usize;
                let (t, hf, vf, bank) = (e & 0x3FF, e >> 10 & 1 == 1, e >> 11 & 1 == 1, e >> 12);
                for y in 0..8usize {
                    for x in 0..8usize {
                        let (sx, sy) = (if hf { 7 - x } else { x }, if vf { 7 - y } else { y });
                        let at = t * 32 + sy * 4 + sx / 2;
                        let v = tiles.get(at).map_or(0, |b| (b >> (4 * (sx & 1))) & 15) as usize;
                        if v != 0 && bank < 6 {
                            let c = u16::from_le_bytes([pal[32 * bank + 2 * v], pal[32 * bank + 2 * v + 1]]);
                            full[(ty * 8 + y) * 256 + tx * 8 + x] = online::bgr(c);
                        }
                    }
                }
            }
        }
        Some(
            (0..online::W * online::H)
                .map(|i| full[((i / online::W + GROUND_SCROLL.1) % 256) * 256 + (i % online::W + GROUND_SCROLL.0) % 256])
                .collect(),
        )
    })
    .as_ref()
}

/// The Teams screen's frame with `word` in the banner: the ground and the title, nothing else (the cards, windows and plate are [`draw`]'s). The sea alone if the ground cannot be read.
pub(crate) fn teams_frame(core: &Core, cv: &mut Rgba<'_>, word: &str) {
    match ground_picture(core) {
        Some(g) => {
            for (i, c) in g.iter().enumerate() {
                cv.put((i % online::W) as i32, (i / online::W) as i32, *c);
            }
        }
        None => cv.rect(0, 0, online::W as i32, online::H as i32, (152, 224, 232)),
    }
    static F: OnceLock<Option<crate::online_art::TitleFont>> = OnceLock::new();
    let Some(font) = F.get_or_init(|| crate::online_art::TitleFont::load(core)).as_ref() else { return };
    let mut b = [0u8; 32];
    core.raw_read_range(BANNER_PALETTE, -1, &mut b);
    let pal: Vec<Rgb> = (0..16).map(|i| online::bgr(u16::from_le_bytes([b[2 * i], b[2 * i + 1]]))).collect();
    for (c, x) in font.layout(word, 4) {
        let Some(g) = crate::online_art::TitleFont::index(c) else { continue };
        let px = &font.px[g];
        for y in 0..px.h {
            for xx in 0..px.w {
                let v = px.get(xx, y) as usize;
                if v != 0 {
                    cv.put(x + xx as i32, y as i32, pal[v]);
                }
            }
        }
    }
}

/// A CO's name on `max` pixels: one line, or two broken at the space that leaves the shorter longest line (a single word stays whole).
fn name_lines(core: &Core, name: &str, max: i32) -> Vec<String> {
    let w = |t: &str| online::text_width(core, t);
    if w(name) <= max {
        return vec![name.to_string()];
    }
    let spaces: Vec<usize> = name.match_indices(' ').map(|(i, _)| i).collect();
    spaces
        .into_iter()
        .map(|i| vec![name[..i].to_string(), name[i + 1..].to_string()])
        .min_by_key(|l| l.iter().map(|t| w(t)).max().unwrap_or(0))
        .unwrap_or_else(|| vec![name.to_string()])
}

fn yellow_frame(cv: &mut Rgba<'_>, x: i32, y: i32, w: i32, h: i32) {
    cv.rect(x, y, w, h, YELLOW);
}

/// A game sprite (any id, in whatever group of the sprite table holds it) as pixels, read from the ROM: width, height, the pixels
/// (`None` clear). The group is the last whose first id is at most `id`.
pub fn team_sprite(core: &Core, id: u32) -> Option<(usize, usize, Vec<Option<Rgb>>)> {
    sprite_pixels(core, id, None)
}

/// [`team_sprite`] with the tiles laid out `cols` to a row (the game draws some pictures from pieces of other shapes than the table's).
fn sprite_pixels(core: &Core, id: u32, cols: Option<usize>) -> Option<(usize, usize, Vec<Option<Rgb>>)> {
    const SPRITE_SIZES: u32 = 0x0848_B780;
    const SPRITE_ROWS: u32 = 0x0848_B738;
    let (tw, th) = (
        core.raw_read_8(SPRITE_SIZES + id * 4, -1) as usize,
        core.raw_read_8(SPRITE_SIZES + id * 4 + 1, -1) as usize,
    );
    if tw == 0 || th == 0 || tw > 8 || th > 8 {
        return None;
    }
    let group = (0..64u32)
        .filter(|g| (core.raw_read_32(SPRITE_ROWS + g * 12 + 8, -1) & 0xFFFF) <= id)
        .max_by_key(|g| core.raw_read_32(SPRITE_ROWS + g * 12 + 8, -1) & 0xFFFF)?;
    let pal_at = core.raw_read_32(SPRITE_ROWS + group * 12 + 4, -1);
    if !(0x0800_0000..0x0A00_0000).contains(&pal_at) {
        return None;
    }
    let mut pal = [0u8; 32];
    core.raw_read_range(pal_at, -1, &mut pal);
    let src = crate::pvp::sprite_source(core, id, group);
    let mut tiles = vec![0u8; tw * th * 32];
    core.raw_read_range(src, -1, &mut tiles);
    let count = tw * th;
    let cols = cols.unwrap_or(tw);
    let rows = count.div_ceil(cols);
    let mut out = vec![None; cols * 8 * rows * 8];
    for t in 0..count {
        let (tx, ty) = (t % cols, t / cols);
        for y in 0..8 {
            for x in 0..8 {
                let b = tiles[t * 32 + y * 4 + x / 2];
                let v = ((b >> (4 * (x & 1))) & 15) as usize;
                if v != 0 {
                    out[(ty * 8 + y) * cols * 8 + tx * 8 + x] =
                        Some(online::bgr(u16::from_le_bytes([pal[2 * v], pal[2 * v + 1]])));
                }
            }
        }
    }
    Some((cols * 8, rows * 8, out))
}

/// The game's team letter picture for team `team` (0 = A .. 3 = D from the "A Team".."D Team" sprites 0xBD..0xC0 the Teams screen's
/// alliance stop draws; 4 = E from tangoAW2's own "E Team" tiles, which the game does not have): the coloured letter with its outline,
/// cut from the left of the picture. Width, height, pixels.
pub fn team_glyph(core: &Core, team: u8) -> Option<(usize, usize, Vec<Option<Rgb>>)> {
    let (w, _, px) = if team < 4 {
        sprite_pixels(core, 0xBD + team as u32, Some(4))?
    } else {
        // (E is drawn in D's shape with D's palette: its tiles through that palette)
        let (_, _, d) = sprite_pixels(core, 0xC0, Some(4))?;
        let _ = d;
        return e_glyph(core);
    };
    Some(crop_letter(w, &px))
}

fn crop_letter(w: usize, px: &[Option<Rgb>]) -> (usize, usize, Vec<Option<Rgb>>) {
    // The letter lies in the picture's first two rows of tiles, left of the word's "Te": columns up to 21.
    let (cw, chh) = (21usize, 24usize);
    let mut x0 = cw;
    let (mut x1, mut y0, mut y1) = (0usize, chh, 0usize);
    for y in 0..chh {
        for x in 0..cw {
            if px[y * w + x].is_some() {
                x0 = x0.min(x);
                x1 = x1.max(x);
                y0 = y0.min(y);
                y1 = y1.max(y);
            }
        }
    }
    if x1 < x0 {
        return (0, 0, Vec::new());
    }
    let (gw, gh) = (x1 - x0 + 1, y1 - y0 + 1);
    let mut out = Vec::with_capacity(gw * gh);
    for y in y0..=y1 {
        for x in x0..=x1 {
            out.push(px[y * w + x]);
        }
    }
    (gw, gh, out)
}

fn e_glyph(core: &Core) -> Option<(usize, usize, Vec<Option<Rgb>>)> {
    // palette of the D Team sprite's group
    const SPRITE_ROWS: u32 = 0x0848_B738;
    let group = (0..64u32)
        .filter(|g| (core.raw_read_32(SPRITE_ROWS + g * 12 + 8, -1) & 0xFFFF) <= 0xC0)
        .max_by_key(|g| core.raw_read_32(SPRITE_ROWS + g * 12 + 8, -1) & 0xFFFF)?;
    let pal_at = core.raw_read_32(SPRITE_ROWS + group * 12 + 4, -1);
    let mut pal = [0u8; 32];
    core.raw_read_range(pal_at, -1, &mut pal);
    let tiles = &crate::five_art::E_TEAM;
    let mut out = vec![None; 4 * 8 * 6 * 8];
    for t in 0..24usize {
        let (tx, ty) = (t % 4, t / 4);
        for y in 0..8 {
            for x in 0..8 {
                let b = tiles[t * 32 + y * 4 + x / 2];
                let v = ((b >> (4 * (x & 1))) & 15) as usize;
                if v != 0 {
                    out[(ty * 8 + y) * 32 + tx * 8 + x] =
                        Some(online::bgr(u16::from_le_bytes([pal[2 * v], pal[2 * v + 1]])));
                }
            }
        }
    }
    Some(crop_letter(32, &out))
}

/// One line of help in the pink plate's text.
pub struct Help {
    pub lines: Vec<String>,
}

/// Draw the screen over the game's own Teams frame in `rgba` (a 240 x 160 RGBA frame).
fn glyph(cv: &mut Rgba<'_>, g: &(usize, usize, Vec<Option<Rgb>>), x: i32, y: i32) {
    for (i, c) in g.2.iter().enumerate() {
        if let Some(c) = c {
            cv.put(x + (i % g.0) as i32, y + (i / g.0) as i32, *c);
        }
    }
}

/// `live_tags`: the game's own tags (offline: 1P / CP change with the player) are taken from every frame; online they are 1P..nP and
/// once seen they are kept, so a frame of the game's screen changing stage never redraws them.
pub fn draw(core: &Core, rgba: &mut [u8], seats: &[Seat], tag_pairs: bool, help: &Help, live_tags: bool) {
    let n = seats.len().clamp(2, 5);
    if rgba.len() != online::W * online::H * 4 || seats.len() < 2 {
        return;
    }
    // The game's tags, from this frame, or the last frame that had them (a screen that labels its cards itself has none to take).
    let labelled = seats.iter().take(n).all(|s| s.tag.is_some());
    let cached = tag_cache().lock().unwrap().clone();
    let complete = cached.len() >= n && cached.iter().take(n).all(|t| !t.is_empty());
    let sampled = if labelled || (!live_tags && complete) {
        None
    } else {
        sample_tags(rgba, n)
    };
    let tags = match sampled {
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
        None if labelled => Vec::new(),
        None => tag_cache().lock().unwrap().clone(),
    };
    let ground = sea(rgba);
    // (with partners the windows are tall: the partner's box is a second, smaller card; the help plate is one line)
    let wh = if tag_pairs { 56 } else { 44 };
    let one_line = tag_pairs;
    let plate_y = if one_line { 85 + wh + 3 } else { 133 };
    let mut canvas = Rgba(rgba);
    let cv = &mut canvas;
    cv.rect(0, CARD_Y - 3, online::W as i32, plate_y - 1 - (CARD_Y - 3), ground);
    let (first, pitch) = layout(n);
    // (a screen of ours centres three cards: the game's own 3-army page sits two pixels to the left)
    let first = if labelled && n == 3 { first + 2 } else { first };
    for (s, seat) in seats.iter().take(n).enumerate() {
        let left = first + pitch * s as i32;
        let partner_on = tag_pairs && seat.field == Some(Field::Partner);
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
        // The team: the game's own team letter on the card's upper left corner.
        if let Some(team) = seat.team {
            if let Some(g) = team_glyph_cached(core, team) {
                if seat.field == Some(Field::Team) {
                    yellow_frame(cv, left + 1, CARD_Y + 1, g.0 as i32 + 4, g.1 as i32 + 4);
                }
                glyph(cv, &g, left + 3, CARD_Y + 3);
            }
        }
        if let Some(label) = seat.tag {
            // (the game's tag sprite, at the card's upper right as its page puts it: a card with room beside it lets it stand out)
            let id = if label == "CP" { TAG_CP } else { TAG_1P };
            if let Some((tw, _, px)) = team_sprite(core, id) {
                let (tx, ty) = (left + if n >= 5 { 32 } else { 40 }, CARD_Y);
                for (i, c) in px.iter().enumerate() {
                    if let Some(c) = c {
                        cv.put(tx + (i % tw) as i32, ty + (i / tw) as i32, *c);
                    }
                }
            }
        } else if let Some(t) = tags.get(s) {
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
        // (a CPU seat of the Gauntlet's screen with no CO yet: Conquest Run draws its enemies when the run starts)
        let co_name = if co_name.is_empty() && seat.tag.is_some() && !seat.mine { "Random".to_string() } else { co_name };
        if seat.ready {
            let l = "READY";
            let lw = online::text_width(core, l);
            cv.text(core, wx + (w - lw) / 2, wy + 13, l, WHITE, BLUE);
        } else {
            let on = seat.field == Some(Field::Co);
            if labelled {
                // every name whole: with arrows when they fit beside it, else without, on two lines if the card is narrow
                let tw = |t: &str| online::text_width(core, t);
                let arrowed = format!("< {co_name} >");
                let lines = if on && tw(&arrowed) <= w - 9 { vec![arrowed] } else { name_lines(core, &co_name, w - 6) };
                let widest = lines.iter().map(|l| tw(l)).max().unwrap_or(0);
                online::audit::cut(widest, w - 6, &co_name);
                if on {
                    yellow_frame(cv, wx + 2, wy + 13, widest + 3, 11 * lines.len() as i32);
                }
                for (i, l) in lines.iter().enumerate() {
                    cv.text(core, wx + 3, wy + 13 + 11 * i as i32, l, INK, SHADE);
                }
            } else {
                let text = fit_arrows(core, &co_name, on, w - 9);
                let tw = online::text_width(core, &text);
                if on {
                    yellow_frame(cv, wx + 2, wy + 13, tw + 3, 11);
                }
                cv.text(core, wx + 3, wy + 13, &text, INK, SHADE);
            }
        }
        // The partner, in the window.
        let ry = wy + 24;
        if !tag_pairs {
            continue;
        }
        let ink = if seat.ready { WHITE } else { INK };
        let pname = if seat.partner == NONE {
            String::new()
        } else {
            co_label(core, seat.partner)
        };
        let compat = match (seat.co, seat.partner) {
            (Some(c), p) if p != NONE => Some(crate::tag::compatibility(c, p)),
            _ => None,
        };
        // The game's partner box: a second, smaller card under the CO's own.
        cv.rect(wx + 3, ry, 30, 28, GRAY_INK);
        cv.rect(wx + 4, ry + 1, 28, 26, LIGHT_GRAY);
        if partner_on {
            yellow_frame(cv, wx + 1, ry - 2, 34, 32);
            cv.rect(wx + 3, ry, 30, 28, GRAY_INK);
            cv.rect(wx + 4, ry + 1, 28, 26, LIGHT_GRAY);
        }
        if seat.partner == NONE {
            let w1 = online::text_width(core, "-");
            cv.text(core, wx + 18 - w1 / 2, ry + 9, "-", GRAY_INK, SHADE);
        } else {
            draw_portrait_part(core, cv, seat.partner, (wx + 4, ry + 1, 28, 26), (3, 1, 42, 40));
        }
        if w >= 56 {
            let room = w - 40;
            if seat.partner == NONE {
                cv.text(core, wx + 37, ry + 8, "None", GRAY_INK, SHADE);
            } else {
                cv.text(core, wx + 37, ry + 2, &online::fit(core, &pname, room), ink, SHADE);
                if let Some(c) = compat {
                    cv.text(core, wx + 37, ry + 14, &format!("{c}%"), ink, SHADE);
                }
            }
        }
    }
    // The help box: the game's pink plate (one line when the windows are tall).
    let plate_h = 158 - plate_y;
    cv.plate(2, plate_y, 236, plate_h);
    let lines = if one_line { 1 } else { help.lines.len().min(2) };
    for (i, l) in help.lines.iter().take(lines).enumerate() {
        let l = online::fit(core, l, 228);
        let w = online::text_width(core, &l);
        let y = plate_y + (plate_h - 11 * lines as i32) / 2 + 11 * i as i32 - 1;
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

fn team_glyph_cached(core: &Core, team: u8) -> Option<(usize, usize, Vec<Option<Rgb>>)> {
    static C: OnceLock<Mutex<HashMap<u8, (usize, usize, Vec<Option<Rgb>>)>>> = OnceLock::new();
    let mut c = C.get_or_init(Default::default).lock().unwrap();
    if let Some(g) = c.get(&team) {
        return Some(g.clone());
    }
    let g = team_glyph(core, team.min(4))?;
    c.insert(team, g.clone());
    Some(g)
}

/// Team letters as the pages show them: the teams in use counted from A.
pub fn letters(teams: &[u8]) -> Vec<u8> {
    teams.iter().map(|&t| compact_team(teams, t)).collect()
}
