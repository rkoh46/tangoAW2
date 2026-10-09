//! The BH Campaign's dialogue, as text files in the design's box format
//! (`src/bh_text/*.txt`; the format is described in `src/bh_text/README.txt`).
//!
//! A scene is a key (`m14_pre`) and rows; a row is one dialogue box: a speaker, an
//! optional expression, a colon, then up to two lines of at most 176 pixels in AW2's font,
//! separated by ` / `. The files are parsed once, at first use, into [`Line`]s: the groups
//! (`@IF`, `@OTHER`, `@WITH`, `@PARTNER`) become `.only`, `.with` and `.only_partner` lines,
//! and `[CO]` rows are spoken by whichever CO the player leads. The compiler merges runs of
//! boxes by one speaker into one text and shares equal texts ([`crate::custom_campaign`]),
//! so a long speech or a line that every CO says costs few of the campaign's text ids.

use std::collections::{HashMap, HashSet};
use std::sync::{Mutex, OnceLock};

use crate::bh_campaign::{BONDS, ROSTER};
use crate::custom_campaign::{co, colour, Line, Mood, Page, Scene, Speaker};

/// The text files, in the order they are read.
const FILES: [(&str, &str); 10] = [
    ("act1", include_str!("bh_text/act1.txt")),
    ("act2a", include_str!("bh_text/act2a.txt")),
    ("act2b", include_str!("bh_text/act2b.txt")),
    ("act3", include_str!("bh_text/act3.txt")),
    ("act4a", include_str!("bh_text/act4a.txt")),
    ("act4b", include_str!("bh_text/act4b.txt")),
    ("act5", include_str!("bh_text/act5.txt")),
    ("act5ba", include_str!("bh_text/act5ba.txt")),
    ("act5bb", include_str!("bh_text/act5bb.txt")),
    ("story", include_str!("bh_text/story.txt")),
];

/// The black-hole trooper's face (Crumb, Mortar, Wick): AW2's soldier portraits are faces 19..23.
const TROOPER: u8 = 23;

struct Book {
    scenes: HashMap<String, Vec<Line>>,
    /// The page texts of the scenes of narration (the prologue): the rows as written.
    pages: HashMap<String, Vec<Vec<&'static str>>>,
}

fn book() -> &'static Book {
    static BOOK: OnceLock<Book> = OnceLock::new();
    BOOK.get_or_init(|| {
        let mut b = Book { scenes: HashMap::new(), pages: HashMap::new() };
        for (name, src) in FILES {
            if let Err(e) = parse_into(&mut b, name, src) {
                panic!("bh_text/{name}.txt: {e}");
            }
        }
        b
    })
}

fn used() -> &'static Mutex<HashSet<String>> {
    static USED: OnceLock<Mutex<HashSet<String>>> = OnceLock::new();
    USED.get_or_init(|| Mutex::new(HashSet::new()))
}

/// The scene with this key (panics with the key when there is none: a missing scene is a bug the tests find).
pub fn scene(key: &str) -> Scene {
    Scene::new(lines(key))
}

/// The lines of the scene with this key.
pub fn lines(key: &str) -> Vec<Line> {
    used().lock().unwrap().insert(key.to_string());
    match book().scenes.get(key) {
        Some(l) => l.clone(),
        None => panic!("bh_text: no scene {key:?}"),
    }
}

/// The pages of a scene of narration (the prologue), one per row, as the world map shows them.
pub fn pages(key: &str) -> Vec<Page> {
    used().lock().unwrap().insert(key.to_string());
    let Some(rows) = book().pages.get(key) else { panic!("bh_text: no scene {key:?}") };
    rows.iter().map(|r| Page { text: r[0], picture: None, who: Some(Speaker::Narrator) }).collect()
}

/// Every key the files define.
pub fn keys() -> Vec<String> {
    let mut v: Vec<String> = book().scenes.keys().cloned().collect();
    v.sort();
    v
}

/// The keys asked for since the process began (the tests compare them with [`keys`]).
pub fn keys_used() -> HashSet<String> {
    used().lock().unwrap().clone()
}

/// The COs the player may lead by default: the whole roster.
fn all_cos() -> Vec<u8> {
    ROSTER.iter().map(|r| r.0).collect()
}

fn co_by_name(n: &str) -> Option<u8> {
    Some(match n {
        "STURM" => co::STURM,
        "VON BOLT" => co::VON_BOLT,
        "HAWKE" => co::HAWKE,
        "KOAL" => co::KOAL,
        "KINDLE" => co::KINDLE,
        "JUGGER" => co::JUGGER,
        "FLAK" => co::FLAK,
        "LASH" => co::LASH,
        "ADDER" => co::ADDER,
        "CLONE" | "CLONE ANDY" => co::CLONE_ANDY,
        "SONJA" => co::SONJA,
        "CRUMB CO" => co::CRUMB,
        "ANDY" => co::ANDY,
        "NELL" => co::NELL,
        "MAX" => co::MAX,
        "OLAF" => co::OLAF,
        "SAMI" => co::SAMI,
        "GRIT" => co::GRIT,
        "KANBEI" => co::KANBEI,
        "EAGLE" => co::EAGLE,
        "DRAKE" => co::DRAKE,
        "HACHI" => co::HACHI,
        "COLIN" => co::COLIN,
        "JESS" => co::JESS,
        "SENSEI" => co::SENSEI,
        "GRIMM" => co::GRIMM,
        "JAVIER" => co::JAVIER,
        "SASHA" => co::SASHA,
        "JAKE" => co::JAKE,
        "RACHEL" => co::RACHEL,
        _ => return None,
    })
}

/// Who a row's speaker name is: a CO, a soldier, or the narration.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Who {
    Co(u8),
    Trooper,
    Soldier(u8),
    Narrator,
    /// The player's CO / the player's tag partner.
    Player,
    Partner,
}

fn who_by_name(n: &str) -> Option<Who> {
    Some(match n {
        "NARRATION" => Who::Narrator,
        "CRUMB" | "MORTAR" | "WICK" | "SOLDIER" => Who::Trooper,
        "SOLDIER OS" => Who::Soldier(colour::ORANGE_STAR),
        "SOLDIER BM" => Who::Soldier(colour::BLUE_MOON),
        "SOLDIER GE" => Who::Soldier(colour::GREEN_EARTH),
        "SOLDIER YC" => Who::Soldier(colour::YELLOW_COMET),
        "[CO]" => Who::Player,
        "[CO2]" => Who::Partner,
        _ => Who::Co(co_by_name(n)?),
    })
}

/// The face of a CO or soldier in a mood, as a line.
fn line(who: Who, mood: Mood, text: &'static str, player: Option<u8>, partner: Option<u8>) -> Line {
    match who {
        Who::Co(c) => Line::feel(c, mood, text),
        Who::Trooper => Line::feel(TROOPER, mood, text),
        Who::Soldier(col) => Line::soldier(col, text),
        Who::Narrator => Line::narrate(text),
        Who::Player => Line::feel(player.expect("[CO] with no CO"), mood, text),
        Who::Partner => Line::feel(partner.expect("[CO2] with no CO"), mood, text),
    }
}

/// What a group of rows is shown for.
#[derive(Clone, PartialEq, Debug)]
enum Group {
    Always,
    If(Vec<u8>),
    Other,
    With(Vec<u8>),
    Partner(Vec<u8>),
    /// Shown when the bond of this recruit (an index of [`BONDS`]) is earned.
    Bond(Vec<u8>),
}

fn leak(s: String) -> &'static str {
    Box::leak(s.into_boxed_str())
}

struct Row {
    who: Who,
    mood: Mood,
    text: &'static str,
}

fn parse_cos(rest: &str) -> Result<Vec<u8>, String> {
    // Names are separated by commas ("@IF STURM, VON BOLT").
    rest.split(',').map(|n| co_by_name(n.trim()).ok_or(format!("unknown CO {:?}", n.trim()))).collect()
}

fn parse_row(l: &str) -> Result<Row, String> {
    let Some(i) = l.find(": ") else { return Err(format!("not a row: {l:?}")) };
    let (head, text) = (&l[..i], l[i + 2..].trim());
    let (name, mood) = match head.strip_suffix(')') {
        Some(h) => {
            let Some(j) = h.rfind('(') else { return Err(format!("bad expression: {l:?}")) };
            let m = match &h[j + 1..] {
                "h" => Mood::Happy,
                "s" => Mood::Sad,
                e => return Err(format!("unknown expression ({e}) in {l:?}")),
            };
            (&h[..j], m)
        }
        None => (head, Mood::Normal),
    };
    let who = who_by_name(name).ok_or(format!("unknown speaker {name:?} in {l:?}"))?;
    if text.is_empty() {
        return Err(format!("empty row: {l:?}"));
    }
    let text = text.replace(" / ", "\r").replace("{p}", "\x0e");
    Ok(Row { who, mood, text: leak(text) })
}

/// A scene's rows into lines: each group's rows once for each CO it is shown for.
fn build(rows: &[(Group, Row)], pool: &[u8]) -> Result<Vec<Line>, String> {
    let named: Vec<u8> = rows.iter().filter_map(|(g, _)| if let Group::If(v) = g { Some(v.clone()) } else { None }).flatten().collect();
    let mut out = Vec::new();
    let mut i = 0;
    while i < rows.len() {
        // A run of rows of one group is expanded group-major, so a CO's rows are adjacent (they merge).
        let g = rows[i].0.clone();
        let mut j = i;
        while j < rows.len() && rows[j].0 == g {
            j += 1;
        }
        let run = &rows[i..j];
        let one = |r: &Row, player: Option<u8>, partner: Option<u8>| line(r.who, r.mood, r.text, player, partner);
        match &g {
            Group::Always => {
                for (_, r) in run {
                    match r.who {
                        // [CO] outside a group: every CO of the pool says it, for its own player.
                        Who::Player => {
                            for &c in pool {
                                out.push(one(r, Some(c), None).only(c));
                            }
                        }
                        Who::Partner => {
                            for &c in pool {
                                out.push(one(r, None, Some(c)).only_partner(c));
                            }
                        }
                        _ => out.push(one(r, None, None)),
                    }
                }
            }
            Group::If(cos) => {
                for &c in cos {
                    for (_, r) in run {
                        out.push(one(r, Some(c), None).only(c));
                    }
                }
            }
            Group::Other => {
                for &c in pool.iter().filter(|c| !named.contains(c)) {
                    for (_, r) in run {
                        out.push(one(r, Some(c), None).only(c));
                    }
                }
            }
            Group::With(cos) => {
                for &c in cos {
                    for (_, r) in run {
                        out.push(one(r, Some(c), None).with(c));
                    }
                }
            }
            Group::Bond(ks) => {
                for &k in ks {
                    for (_, r) in run {
                        out.push(one(r, None, None).bond(k));
                    }
                }
            }
            Group::Partner(cos) => {
                for &c in cos {
                    for (_, r) in run {
                        out.push(one(r, None, Some(c)).only_partner(c));
                    }
                }
            }
        }
        i = j;
    }
    Ok(out)
}

fn parse_into(b: &mut Book, file: &str, src: &str) -> Result<(), String> {
    let mut key: Option<(String, Vec<u8>, usize)> = None;
    let mut rows: Vec<(Group, Row)> = Vec::new();
    let mut group = Group::Always;
    let mut finish = |b: &mut Book, key: &mut Option<(String, Vec<u8>, usize)>, rows: &mut Vec<(Group, Row)>| -> Result<(), String> {
        if let Some((k, pool, _)) = key.take() {
            if b.scenes.contains_key(&k) {
                return Err(format!("scene {k:?} is defined twice"));
            }
            if rows.iter().all(|(g, r)| *g == Group::Always && r.who == Who::Narrator) && !rows.is_empty() {
                b.pages.insert(k.clone(), rows.iter().map(|(_, r)| vec![r.text]).collect());
            }
            let lines = build(rows, &pool).map_err(|e| format!("{k}: {e}"))?;
            b.scenes.insert(k, lines);
            rows.clear();
        }
        Ok(())
    };
    for (n, raw) in src.lines().enumerate() {
        let l = raw.trim();
        let at = |e: String| format!("line {}: {e}", n + 1);
        if l.is_empty() || l.starts_with('#') {
            continue;
        }
        if let Some(h) = l.strip_prefix("== ") {
            finish(b, &mut key, &mut rows).map_err(at)?;
            // "== key" or "== key | STURM, VON BOLT" (the COs the player may lead in the scene).
            let (k, pool) = match h.split_once('|') {
                Some((k, p)) => (k.trim(), parse_cos(p).map_err(at)?),
                None => (h.trim(), all_cos()),
            };
            key = Some((k.to_string(), pool, n + 1));
            group = Group::Always;
            continue;
        }
        if key.is_none() {
            return Err(at("a row before the first scene header".into()));
        }
        if let Some(d) = l.strip_prefix('@') {
            let (word, rest) = d.split_once(' ').unwrap_or((d, ""));
            group = match word {
                "IF" => Group::If(parse_cos(rest).map_err(at)?),
                "OTHER" => Group::Other,
                "WITH" => Group::With(parse_cos(rest).map_err(at)?),
                "PARTNER" => Group::Partner(parse_cos(rest).map_err(at)?),
                "BOND" => Group::Bond(parse_cos(rest).map_err(at)?.into_iter().map(|c| BONDS.iter().position(|b| b.co == c).map(|k| k as u8).ok_or(at(format!("{c} has no bond")))).collect::<Result<_, _>>()?),
                "END" => Group::Always,
                w => return Err(at(format!("unknown directive @{w}"))),
            };
            continue;
        }
        let row = parse_row(l).map_err(at)?;
        // [CO] in a group means the CO of the group; elsewhere it is expanded for the whole pool.
        rows.push((group.clone(), row));
    }
    finish(b, &mut key, &mut rows).map_err(|e| format!("{file}: {e}"))?;
    let _ = file;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_files_parse_and_every_scene_has_rows() {
        let b = book();
        for (k, v) in &b.scenes {
            assert!(!v.is_empty(), "{k} has no lines");
        }
    }

    #[test]
    fn groups_expand_to_the_pool() {
        let src = "== t | STURM, HAWKE, KOAL\nHAWKE: a / b\n@IF STURM\n[CO]: x\n@OTHER\n[CO]: y\n@END\nNARRATION: z\n";
        let mut b = Book { scenes: HashMap::new(), pages: HashMap::new() };
        parse_into(&mut b, "t", src).unwrap();
        let l = &b.scenes["t"];
        // Hawke's row, Sturm's x, Hawke's y and Koal's y, the narration.
        assert_eq!(l.len(), 5);
        assert_eq!(l[0].text, "a\rb");
        assert_eq!((l[1].only, l[1].who), (Some(co::STURM), Speaker::Co(co::STURM, Mood::Normal)));
        assert_eq!(l[2].only, Some(co::HAWKE));
        assert_eq!(l[3].only, Some(co::KOAL));
        assert_eq!(l[4].who, Speaker::Narrator);
    }

    #[test]
    fn bad_rows_are_errors() {
        let mut b = Book { scenes: HashMap::new(), pages: HashMap::new() };
        assert!(parse_into(&mut b, "t", "== t\nNOBODY: hi\n").is_err());
        assert!(parse_into(&mut b, "t", "== u\nSTURM(x): hi\n").is_err());
        assert!(parse_into(&mut b, "t", "STURM: hi\n").is_err());
    }
}
