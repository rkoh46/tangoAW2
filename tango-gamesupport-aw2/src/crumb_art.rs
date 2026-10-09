//! Crumb's pictures, converted at run time from Advance Wars 2's own Black
//! Hole trooper (CO presentation row 23: the face used for the soldiers'
//! lines in the campaigns) and the letters of AW2's own name graphics. No
//! art is stored: every picture is cut from the ROM the player owns when the
//! game starts, as the Dual Strike COs' are ([`crate::ds_co_art`]).
//!
//! What AW2 has for the trooper (row 23 of the presentation table, 0x44 a
//! row): three 48x48 faces (alike), a 32x24 mini portrait and a palette; no
//! HUD face, no full body and no name. What each CO graphic is made of:
//!
//! | Graphic | Made of |
//! |---|---|
//! | CO select face (3, as the game has them) | the trooper's face, as it is |
//! | Teams portrait (mini) | the trooper's own mini portrait |
//! | HUD face (32x16, the eyes) | a 32x16 cut of the face round the red lens, 1:1 |
//! | CO page figure (128x160) | the face grown with nearest-neighbour, framed |
//! | Power and tag screen figures | the same figure (AW2's own path for a CO without a Dual Strike figure) |
//! | Name "Crumb" (48x16) | C of "Colin", u, r, m of "Sturm", b of "Kanbei", set side by side as in a name |
//! | Palette | the trooper's, in all eight colour schemes |
//!
//! **The figure.** AW2 has no full body for a trooper, so the CO page's
//! 128x160 picture is composed: the face grown twice with nearest neighbour
//! (96 x 96), framed with a one-pixel outline in the palette's darkest colour
//! (corners cut) and centred. The two bottom rows stay empty: the tag screens
//! carry a figure's last row down to the screen's foot
//! ([`crate::tag_screens`]) and an outline there would become a bar.

use mgba::core::Core;

use crate::ds_art::lz10;
use crate::ds_co_art::CoArt;

const AW2_PRESENTATION: u32 = 0x084A_0090;
const ROW: u32 = 0x44;
/// AW2's face id of the Black Hole trooper.
const TROOPER: u32 = 23;
/// The name graphics' letters come from these COs (AW2 ids): Colin, Sturm,
/// Kanbei.
const COLIN: u32 = 16;
const STURM: u32 = 10;
const KANBEI: u32 = 6;
/// The palette index of the outline: the darkest colour of every CO palette.
const OUTLINE: u8 = 15;

/// The CO page's figure (also the power and tag screens'): the face twice as
/// large (96 x 96), framed (98 x 98) and centred. (The user chose this over
/// a three-times figure cut to 126 columns and a three-times head: the large
/// ones filled the figure area but read as a cropped block.)
/// A picture of palette indexes, 0 transparent.
#[derive(Clone)]
pub struct Px {
    pub w: usize,
    pub h: usize,
    pub v: Vec<u8>,
}

impl Px {
    pub fn new(w: usize, h: usize) -> Px {
        Px { w, h, v: vec![0; w * h] }
    }
    pub fn at(&self, x: usize, y: usize) -> u8 {
        self.v[y * self.w + x]
    }
    fn set(&mut self, x: usize, y: usize, c: u8) {
        self.v[y * self.w + x] = c;
    }
    /// `place(k)` is the (column, row) of tile `k` in an image `tw` x `th`
    /// tiles.
    pub fn from_tiles(t: &[u8], tw: usize, th: usize, place: impl Fn(usize) -> (usize, usize)) -> Px {
        let mut p = Px::new(tw * 8, th * 8);
        for k in 0..tw * th {
            let (cx, cy) = place(k);
            for y in 0..8 {
                for x in 0..8 {
                    let b = t[32 * k + 4 * y + x / 2];
                    p.set(8 * cx + x, 8 * cy + y, (b >> (4 * (x & 1))) & 15);
                }
            }
        }
        p
    }
    pub fn to_tiles(&self, tw: usize, th: usize, place: impl Fn(usize) -> (usize, usize)) -> Vec<u8> {
        let mut out = vec![0u8; tw * th * 32];
        for k in 0..tw * th {
            let (cx, cy) = place(k);
            for y in 0..8 {
                for x in (0..8).step_by(2) {
                    let (a, b) = (self.at(8 * cx + x, 8 * cy + y), self.at(8 * cx + x + 1, 8 * cy + y));
                    out[32 * k + 4 * y + x / 2] = a | b << 4;
                }
            }
        }
        out
    }
    /// Each pixel `k` times as large in both directions (nearest neighbour).
    pub fn grown(&self, k: usize) -> Px {
        let mut p = Px::new(self.w * k, self.h * k);
        for y in 0..p.h {
            for x in 0..p.w {
                p.set(x, y, self.at(x / k, y / k));
            }
        }
        p
    }
    pub fn cut(&self, x0: usize, y0: usize, w: usize, h: usize) -> Px {
        let mut p = Px::new(w, h);
        for y in 0..h {
            for x in 0..w {
                p.set(x, y, self.at(x0 + x, y0 + y));
            }
        }
        p
    }
    pub fn put(&mut self, src: &Px, x0: usize, y0: usize) {
        for y in 0..src.h {
            for x in 0..src.w {
                if x0 + x < self.w && y0 + y < self.h {
                    self.set(x0 + x, y0 + y, src.at(x, y));
                }
            }
        }
    }
    /// A one-pixel outline round the picture, its corners cut two pixels.
    pub fn framed(&self) -> Px {
        let (w, h) = (self.w + 2, self.h + 2);
        let mut p = Px::new(w, h);
        p.put(self, 1, 1);
        for x in 0..w {
            p.set(x, 0, OUTLINE);
            p.set(x, h - 1, OUTLINE);
        }
        for y in 0..h {
            p.set(0, y, OUTLINE);
            p.set(w - 1, y, OUTLINE);
        }
        for (cx, cy, dx, dy) in [(0, 0, 1i32, 1i32), (w - 1, 0, -1, 1), (0, h - 1, 1, -1), (w - 1, h - 1, -1, -1)] {
            for (i, len) in [2usize, 1].into_iter().enumerate() {
                for k in 0..len {
                    let (x, y) = ((cx as i32 + dx * k as i32) as usize, (cy as i32 + dy * i as i32) as usize);
                    p.set(x, y, 0);
                }
            }
        }
        p
    }
}

fn read(core: &Core, at: u32, n: usize) -> Vec<u8> {
    let mut b = vec![0u8; n];
    core.raw_read_range(at, -1, &mut b);
    b
}

fn word(core: &Core, at: u32) -> u32 {
    core.raw_read_32(at, -1)
}

fn face_place(k: usize) -> (usize, usize) {
    (k % 6, k / 6)
}

/// The 12 tiles of a mini portrait: two columns of 2x3 tiles.
pub fn mini_place(k: usize) -> (usize, usize) {
    (k / 6 * 2 + k % 6 % 2, k % 6 / 2)
}

fn name_place(k: usize) -> (usize, usize) {
    (k / 2, k % 2)
}

/// AW2's name graphic of CO `co` as 48 x 16 indexes.
fn name_of(core: &Core, co: u32) -> Option<Px> {
    let row = AW2_PRESENTATION + ROW * co;
    let raw = read(core, word(core, row + 4), 0x300);
    Some(Px::from_tiles(&lz10(&raw)?, 6, 2, name_place))
}

/// A name graphic's letters: the columns of each letter's fill (palette
/// index 1), (first, last); a letter's outline is the column either side,
/// shared with its neighbour.
fn letters(p: &Px) -> Vec<(usize, usize)> {
    let fill: Vec<bool> = (0..p.w).map(|x| (0..p.h).any(|y| p.at(x, y) == 1)).collect();
    let mut out = Vec::new();
    let mut start = None;
    for x in 0..=p.w {
        let on = x < p.w && fill[x];
        match (on, start) {
            (true, None) => start = Some(x),
            (false, Some(s)) => {
                out.push((s, x - 1));
                start = None;
            }
            _ => {}
        }
    }
    out
}

/// "Crumb" in the style of the game's names (**tangoAW2's own composition**,
/// no new art): the letters (CO, letter index) set side by side, each
/// letter's outline column shared with the next (the taller showing),
/// centred in the six sprites.
pub fn name(core: &Core) -> Option<Vec<u8>> {
    let pick = [(COLIN, 0usize), (STURM, 3), (STURM, 2), (STURM, 4), (KANBEI, 3)];
    let imgs: Vec<(Px, usize)> = pick.iter().map(|&(co, k)| Some((name_of(core, co)?, k))).collect::<Option<_>>()?;
    let column = |img: &Px, x: usize| -> Vec<u8> { (0..16).map(|y| img.at(x, y)).collect() };
    let mut cols: Vec<Vec<u8>> = Vec::new();
    let first = letters(&imgs[0].0).get(imgs[0].1).copied()?;
    cols.push(column(&imgs[0].0, first.0.checked_sub(1)?));
    for (i, (img, k)) in imgs.iter().enumerate() {
        let (s, e) = letters(img).get(*k).copied()?;
        for x in s..=e {
            cols.push(column(img, x));
        }
        let mut sep = column(img, e + 1);
        if let Some((next, nk)) = imgs.get(i + 1) {
            let (ns, _) = letters(next).get(*nk).copied()?;
            let other = column(next, ns - 1);
            for y in 0..16 {
                if sep[y] == 0 {
                    sep[y] = other[y];
                }
            }
        }
        cols.push(sep);
    }
    if cols.len() > 48 {
        return None;
    }
    let mut out = Px::new(48, 16);
    let x0 = (48 - cols.len()) / 2;
    for (i, c) in cols.iter().enumerate() {
        for y in 0..16 {
            out.set(x0 + i, y, c[y]);
        }
    }
    Some(out.to_tiles(6, 2, name_place))
}

/// The CO page's picture (128 x 160): the face grown twice, framed, centred.
pub fn figure(face: &Px) -> Px {
    let mut body = Px::new(128, 160);
    let f = face.grown(2).framed();
    body.put(&f, (128 - f.w) / 2, 24);
    body
}

/// The six sprites of a full body: (x, y, tiles across, tiles down), in the
/// order of the two body files ([`crate::ds_co_art`]).
const SPRITES: [(usize, usize, usize, usize); 6] = [(0, 0, 8, 8), (64, 0, 8, 8), (0, 64, 8, 8), (64, 64, 8, 8), (0, 128, 8, 4), (64, 128, 8, 4)];

/// A 128 x 160 picture as the body's two files (4096 and 6144 bytes).
pub fn body_files(body: &Px) -> (Vec<u8>, Vec<u8>) {
    let mut all = Vec::new();
    for (sx, sy, tw, th) in SPRITES {
        all.extend(body.cut(sx, sy, tw * 8, th * 8).to_tiles(tw, th, |k| (k % tw, k / tw)));
    }
    let bottom = all.split_off(crate::ds_co_art::BODY_TOP_LEN);
    (all, bottom)
}

/// The HUD face: 32 x 16 round the red lens, 1:1.
pub fn hud(face: &Px) -> Vec<u8> {
    face.cut(13, 17, 32, 16).to_tiles(4, 2, |k| (k % 4, k / 4))
}

/// Crumb's pictures in AW2's formats (all of them cut from the trooper's).
pub fn art(core: &Core) -> Option<CoArt> {
    let row = AW2_PRESENTATION + ROW * TROOPER;
    let face_tiles = |k: u32| lz10(&read(core, word(core, row + 0x0C + 4 * k), 0x600));
    let faces = [face_tiles(0)?, face_tiles(1)?, face_tiles(2)?];
    if faces.iter().any(|f| f.len() < crate::ds_co_art::FACE_LEN) {
        return None;
    }
    let face = Px::from_tiles(&faces[0], 6, 6, face_place);
    let mini = read(core, word(core, row + 0x18), crate::ds_co_art::MINI_LEN);
    let one = read(core, word(core, row + 0x08), 0x20);
    let mut palette = Vec::new();
    for _ in 0..8 {
        palette.extend_from_slice(&one);
    }
    let (body_top, body_bottom) = body_files(&figure(&face));
    Some(CoArt {
        face: [
            faces[0][..crate::ds_co_art::FACE_LEN].to_vec(),
            faces[1][..crate::ds_co_art::FACE_LEN].to_vec(),
            faces[2][..crate::ds_co_art::FACE_LEN].to_vec(),
        ],
        mini,
        hud: hud(&face),
        body_top,
        body_bottom,
        name: name(core)?,
        palette,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn framed_and_cut() {
        let mut p = Px::new(4, 4);
        p.v.fill(3);
        let f = p.framed();
        assert_eq!((f.w, f.h), (6, 6));
        assert_eq!(f.at(0, 0), 0, "corner cut");
        assert_eq!(f.at(2, 0), OUTLINE);
        assert_eq!(f.at(1, 1), 3);
    }

    #[test]
    fn body_files_sizes_and_roundtrip() {
        let mut face = Px::new(48, 48);
        for (i, v) in face.v.iter_mut().enumerate() {
            *v = (i * 7 % 15 + 1) as u8;
        }
        {
            let f = figure(&face);
            let (top, bottom) = body_files(&f);
            assert_eq!(top.len(), crate::ds_co_art::BODY_TOP_LEN);
            assert_eq!(bottom.len(), crate::ds_co_art::BODY_BOTTOM_LEN);
            // The last two rows are empty (the tag screens carry the last
            // row down).
            assert!((0..128).all(|x| f.at(x, 159) == 0 && f.at(x, 158) == 0), "the last rows");
        }
        let t = face.to_tiles(6, 6, face_place);
        assert_eq!(Px::from_tiles(&t, 6, 6, face_place).v, face.v);
    }
}
