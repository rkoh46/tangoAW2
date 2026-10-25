//! Emerald Sun's four COs, Klaus, Aurelia, Cassius and Livia (`docs/ES_CAMPAIGN.md`), as far as **art and texts** go: their pictures are the project owner's own art
//! ("portrait art provided by the project owner", `CREDITS.md`) converted by `aw2dev co portrait import` into indexed PNGs (`art/cos/<id>/`: the 128 x 160 figure, four 48 x 48
//! expression faces, the Teams mini, the HUD face, the name set in our own letters), and their names, pages and quotes are written in `cos/<id>.toml`.
//!
//! Their powers and numbers are `crate::es_co` (this campaign's); the page texts it writes come from `es_co::text_of` (the owner's words, our numbers). Always in the game
//! (Versus lists them only with `TANGOAW2_ES_VERSUS`).
//!
//! Ids: 86..=89 (after the face-only portraits 83..=85; [`crate::co_new::ES_FIRST`]).

use std::sync::OnceLock;

use crate::crumb_art::{body_files, decode, Px};
use crate::ds_co_art::CoArt;

/// The five with the owner's portraits: (CO id, file name). Asuka (92) is not Emerald Sun's: a Black Hole CO in every list (`crate::asuka`).
const IDS: [(u8, &str); 5] = [(86, "klaus"), (87, "aurelia"), (88, "cassius"), (89, "livia"), (92, "asuka")];

macro_rules! pics {
    ($co:literal) => {
        Pics {
            large: include_bytes!(concat!("../art/cos/", $co, "/large.png")),
            faces: [
                include_bytes!(concat!("../art/cos/", $co, "/face_normal.png")),
                include_bytes!(concat!("../art/cos/", $co, "/face_happy.png")),
                include_bytes!(concat!("../art/cos/", $co, "/face_sad.png")),
                include_bytes!(concat!("../art/cos/", $co, "/face_angry.png")),
            ],
            mini: include_bytes!(concat!("../art/cos/", $co, "/mini.png")),
            hud: include_bytes!(concat!("../art/cos/", $co, "/hud.png")),
            name: include_bytes!(concat!("../art/cos/", $co, "/name.png")),
            data: include_str!(concat!("../cos/", $co, ".toml")),
            crop: include_str!(concat!("../art/cos/", $co, "/crop.toml")),
        }
    };
}

struct Pics {
    large: &'static [u8],
    /// normal, happy, sad, angry
    faces: [&'static [u8]; 4],
    mini: &'static [u8],
    hud: &'static [u8],
    name: &'static [u8],
    data: &'static str,
    crop: &'static str,
}

fn all() -> [Pics; 5] {
    [pics!("klaus"), pics!("aurelia"), pics!("cassius"), pics!("livia"), pics!("asuka")]
}

/// The data files of the five, in [`IDS`]' order.
const DATA: [&str; 5] = [
    include_str!("../cos/klaus.toml"),
    include_str!("../cos/aurelia.toml"),
    include_str!("../cos/cassius.toml"),
    include_str!("../cos/livia.toml"),
    include_str!("../cos/asuka.toml"),
];

/// A CO's place among the five (0 Klaus .. 3 Livia, 4 Asuka).
pub fn index(co: u8) -> Option<usize> {
    IDS.iter().position(|i| i.0 == co)
}

/// The data file of CO `k` parsed.
fn data(k: usize) -> Option<&'static toml::Value> {
    static D: OnceLock<Vec<toml::Value>> = OnceLock::new();
    D.get_or_init(|| DATA.iter().map(|d| toml::from_str(d).expect("a CO data file")).collect()).get(k)
}

fn s(v: &toml::Value, path: &[&str]) -> Option<String> {
    let mut v = v;
    for p in path {
        v = v.get(p)?;
    }
    v.as_str().map(str::to_string)
}

fn quote(v: &toml::Value, path: &[&str]) -> Option<String> {
    let mut v = v;
    for p in path {
        v = v.get(p)?;
    }
    let lines: Vec<String> = v.as_array()?.iter().filter_map(|l| l.as_str().map(str::to_string)).collect();
    Some(lines.join("\r"))
}

/// The CO page's bio: the data file's, its Hit and Miss on lines of their own.
fn bio(v: &toml::Value) -> Option<String> {
    Some(s(v, &["bio"])?.replace(" Hit:", "\rHit:").replace(" Miss:", "\rMiss:"))
}

pub fn name(co: u8) -> Option<Vec<u8>> {
    s(data(index(co)?)?, &["name"]).map(String::into_bytes)
}

/// A text of a CO by [`crate::co_new`]'s slot (the page texts are wrapped by the caller).
pub fn text(co: u8, which: u16) -> Option<Vec<u8>> {
    use crate::co_new::*;
    let v = data(index(co)?)?;
    let t = match which {
        T_NAME => s(v, &["name"])?,
        T_BIO => bio(v)?,
        T_D2D => s(v, &["d2d", "text"])?,
        T_COP => s(v, &["cop", "text"])?,
        T_SCOP => s(v, &["scop", "text"])?,
        T_COP_NAME => s(v, &["cop", "name"])?,
        T_SCOP_NAME => s(v, &["scop", "name"])?,
        // the six power quotes: the CO Power's, the Super Power's and the Tag Power's, each twice
        w if (T_QUOTES..T_QUOTES + 6).contains(&w) => match (w - T_QUOTES) % 3 {
            0 => quote(v, &["cop", "quote"])?,
            1 => quote(v, &["scop", "quote"])?,
            _ => quote(v, &["lines", "tag_in"])?,
        },
        T_VICTORY => s(v, &["lines", "victory"])?,
        T_DEFEAT => s(v, &["lines", "defeat"])?,
        _ => return None,
    };
    Some(t.into_bytes())
}

/// (cell x, strip y) of a CO's select mug: where the 24-pixel cell of Versus' cards and the 16-row strip of the grid start so that the eyes show.
pub fn crop(co: u8) -> Option<(usize, usize)> {
    let p = all().into_iter().nth(index(co)?)?;
    let v: toml::Value = toml::from_str(p.crop).ok()?;
    Some((v.get("cell_x")?.as_integer()? as usize, v.get("strip_y")?.as_integer()? as usize))
}

fn px(bytes: &[u8]) -> Option<(Px, Vec<u16>)> {
    decode(bytes)
}

/// A CO's pictures in AW2's formats: the figure as the body's two files, the normal, happy and sad faces (the third slot of AW2's three is the defeat face; the angry
/// face is kept for dialogue), the mini (two columns of 2 x 3 tiles), the HUD face, the name, and the palette (one scheme, repeated for the eight colour schemes).
pub fn art(co: u8) -> Option<CoArt> {
    let p = all().into_iter().nth(index(co)?)?;
    let (large, pal) = px(p.large)?;
    if large.w != 128 || large.h != 160 || pal.len() > 16 {
        return None;
    }
    let face = |b: &[u8]| -> Option<Vec<u8>> {
        let (f, _) = px(b)?;
        (f.w == 48 && f.h == 48).then(|| f.to_tiles(6, 6, |k| (k % 6, k / 6)))
    };
    let (mini, _) = px(p.mini)?;
    if mini.w != 48 || mini.h != 16 {
        return None;
    }
    let (hud, _) = px(p.hud)?;
    let (name, _) = px(p.name)?;
    let (top, bottom) = body_files(&large);
    let mut palette = Vec::with_capacity(0x100);
    for _scheme in 0..8 {
        for i in 0..16 {
            palette.extend_from_slice(&pal.get(i).copied().unwrap_or(0).to_le_bytes());
        }
    }
    Some(CoArt {
        face: [face(p.faces[0])?, face(p.faces[1])?, face(p.faces[2])?],
        // the mini is a 48 x 16 strip: its 12 tiles are the left 32 x 16 in rows of four, then the right 16 x 16 in rows of two (the battle scene's header, AW2's own layout)
        mini: mini.to_tiles(6, 2, |k| if k < 8 { (k % 4, k / 4) } else { (4 + (k - 8) % 2, (k - 8) / 2) }),
        hud: hud.to_tiles(4, 2, |k| (k % 4, k / 4)),
        body_top: top,
        body_bottom: bottom,
        name: name.to_tiles(6, 2, |k| (k / 2, k % 2)),
        palette,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_five_have_art_texts_and_a_crop() {
        for &(co, id) in IDS.iter() {
            let a = art(co).unwrap_or_else(|| panic!("{id}: art"));
            assert_eq!(a.face[0].len(), crate::ds_co_art::FACE_LEN);
            assert_eq!(a.mini.len(), crate::ds_co_art::MINI_LEN);
            assert_eq!(a.hud.len(), crate::ds_co_art::HUD_LEN);
            assert_eq!(a.body_top.len(), crate::ds_co_art::BODY_TOP_LEN);
            assert_eq!(a.body_bottom.len(), crate::ds_co_art::BODY_BOTTOM_LEN);
            assert_eq!(a.name.len(), crate::ds_co_art::NAME_LEN);
            assert_eq!(a.palette.len(), crate::ds_co_art::PALETTE_LEN);
            for w in 0..=14u16 {
                assert!(text(co, w).is_some(), "{id}: text slot {w}");
            }
            assert!(crop(co).is_some(), "{id}: crop");
            assert!(name(co).is_some());
        }
        assert_eq!(name(crate::co_new::ES_FIRST), Some(b"Klaus".to_vec()));
    }
}
