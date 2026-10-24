//! The Emerald Sun Campaign's dialogue, as text files in the BH Campaign's box format ([`crate::bh_text`]; a copy with the
//! Emerald Sun cast: `src/es_text/*.txt`, format `src/es_text/README.txt`, voices `tools/estext/BIBLE.md`).
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

use crate::custom_campaign::Bond;
use crate::es_campaign::ROSTER;

/// (the Emerald Sun Campaign has no hidden bonds)
const BONDS: [Bond; 0] = [];
use crate::campaign_music::Track;
use crate::custom_campaign::{co, colour, Line, Mood, Page, Scene, Speaker};

/// The text files, in the order they are read.
const FILES: [(&str, &str); 4] = [
    ("act1", include_str!("es_text/act1.txt")),
    ("act2", include_str!("es_text/act2.txt")),
    ("act3", include_str!("es_text/act3.txt")),
    ("act4", include_str!("es_text/act4.txt")),
];

/// The black-hole trooper's face (Crumb, Mortar, Wick): AW2's soldier portraits are faces 19..23.
const TROOPER: u8 = 23;

struct Book {
    scenes: HashMap<String, Vec<Line>>,
    /// A scene's song (`@SONG name`, [`crate::campaign_music`]).
    songs: HashMap<String, Track>,
    /// The page texts of the scenes of narration (the prologue): the rows as written.
    pages: HashMap<String, Vec<Vec<&'static str>>>,
}

fn book() -> &'static Book {
    static BOOK: OnceLock<Book> = OnceLock::new();
    BOOK.get_or_init(|| {
        let mut b = Book { scenes: HashMap::new(), songs: HashMap::new(), pages: HashMap::new() };
        for (name, src) in FILES {
            if let Err(e) = parse_into(&mut b, name, src) {
                panic!("es_text/{name}.txt: {e}");
            }
        }
        b
    })
}

fn used() -> &'static Mutex<HashSet<String>> {
    static USED: OnceLock<Mutex<HashSet<String>>> = OnceLock::new();
    USED.get_or_init(|| Mutex::new(HashSet::new()))
}

/// The scene with this key and its song (panics with the key when there is none: a missing scene is a bug the tests find).
pub fn scene(key: &str) -> Scene {
    Scene::new(lines(key)).with_song(song(key))
}

/// The song a scene names with `@SONG`.
pub fn song(key: &str) -> Option<Track> {
    book().songs.get(key).copied()
}

/// The scenes one after the other in one script, each with its own song (a scene on the world map: the troops' talk, the Accord's council, Sturm's
/// briefing).
pub fn chain(keys: &[&str]) -> Scene {
    let mut it = keys.iter();
    let mut s = scene(it.next().expect("bh_text::chain: no scene"));
    for k in it {
        s = s.then(scene(k));
    }
    s
}

/// Every scene key that names a song (the tests and `aw2dev campaign scenes` read them).
pub fn songs() -> Vec<(String, Track)> {
    let mut v: Vec<(String, Track)> = book().songs.iter().map(|(k, t)| (k.clone(), *t)).collect();
    v.sort_by(|a, b| a.0.cmp(&b.0));
    v
}

/// The lines of the scene with this key.
pub fn lines(key: &str) -> Vec<Line> {
    used().lock().unwrap().insert(key.to_string());
    match book().scenes.get(key) {
        Some(l) => l.clone(),
        None => panic!("es_text: no scene {key:?}"),
    }
}

/// The pages of a scene of narration (the prologue), one per row, as the world map shows them.
pub fn pages(key: &str) -> Vec<Page> {
    used().lock().unwrap().insert(key.to_string());
    let Some(rows) = book().pages.get(key) else { panic!("es_text: no scene {key:?}") };
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
    use crate::es_co;
    Some(match n {
        "KLAUS" => es_co::KLAUS,
        "AURELIA" => es_co::AURELIA,
        "CASSIUS" => es_co::CASSIUS,
        "LIVIA" => es_co::LIVIA,
        "VARRO" => es_co::VARRO,
        "ANDY" => co::ANDY,
        "NELL" => co::NELL,
        "MAX" => co::MAX,
        "OLAF" => co::OLAF,
        "SAMI" => co::SAMI,
        "GRIT" => co::GRIT,
        "KANBEI" => co::KANBEI,
        "SONJA" => co::SONJA,
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
        "ADDER" => co::ADDER,
        "FLAK" => co::FLAK,
        "KINDLE" => co::KINDLE,
        "KOAL" => co::KOAL,
        "LASH" => co::LASH,
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
        "SOLDIER" => Who::Trooper,
        "LEGIONARY" => Who::Co(crate::es_co::LEGIONARY_FACE),
        "SOLDIER BH" => Who::Soldier(colour::BLACK_HOLE),
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
    /// Shown when this CO is not in the player's pair (`[CO]` and `[CO2]` are the pair's, as outside a group).
    Without(u8),
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
            Group::Without(c) => {
                for (_, r) in run {
                    match r.who {
                        Who::Player => {
                            for &p in pool {
                                out.push(one(r, Some(p), None).only(p).without(*c));
                            }
                        }
                        Who::Partner => {
                            for &p in pool {
                                out.push(one(r, None, Some(p)).only_partner(p).without(*c));
                            }
                        }
                        _ => out.push(one(r, None, None).without(*c)),
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
    let mut song: Option<Track> = None;
    let finish = |b: &mut Book, key: &mut Option<(String, Vec<u8>, usize)>, rows: &mut Vec<(Group, Row)>, song: &mut Option<Track>| -> Result<(), String> {
        if let Some((k, pool, _)) = key.take() {
            if let Some(t) = song.take() {
                b.songs.insert(k.clone(), t);
            }
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
            finish(b, &mut key, &mut rows, &mut song).map_err(at)?;
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
            if word == "SONG" {
                // (a scene's song: not a group of rows; at most one a scene)
                if song.is_some() {
                    return Err(at("a scene has one @SONG".into()));
                }
                song = Some(crate::campaign_music::parse(rest, co_by_name).ok_or_else(|| at(format!("unknown song {:?}", rest.trim())))?);
                continue;
            }
            group = match word {
                "IF" => Group::If(parse_cos(rest).map_err(at)?),
                "OTHER" => Group::Other,
                "WITH" => Group::With(parse_cos(rest).map_err(at)?),
                "PARTNER" => Group::Partner(parse_cos(rest).map_err(at)?),
                "WITHOUT" => {
                    let v = parse_cos(rest).map_err(at)?;
                    if v.len() != 1 {
                        return Err(at("@WITHOUT takes exactly one CO".into()));
                    }
                    Group::Without(v[0])
                }
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
    finish(b, &mut key, &mut rows, &mut song).map_err(|e| format!("{file}: {e}"))?;
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

    /// The story scenes (a mission's intro, victory, the scenes on the world map after it, the prologue) all name a song: AW2 plays one under every one of
    /// its own (docs/dev/campaign-scenes.md). The mid-battle day scenes keep the battle's music.
    #[test]
    fn every_story_scene_has_a_song() {
        let b = book();
        let needs = |k: &str| {
            k == "prologue"
                || k.split_once('_').is_some_and(|(m, rest)| {
                    m.len() == 3
                        && m.starts_with('m')
                        && ["pre", "post", "map", "epilogue", "epilogue2", "pre2", "post2", "map2"].contains(&rest)
                })
        };
        let missing: Vec<&String> = b.scenes.keys().filter(|k| needs(k) && !b.songs.contains_key(*k)).collect();
        assert!(missing.is_empty(), "scenes with no @SONG: {missing:?}");
        assert!(b.songs.keys().all(|k| b.scenes.contains_key(k)));
    }

    #[test]
    fn song_directive_parses_and_is_once_a_scene() {
        let mut b = Book { scenes: HashMap::new(), songs: HashMap::new(), pages: HashMap::new() };
        parse_into(&mut b, "t", "== a\n@SONG sturm\nKLAUS: x\n== b\n@SONG co:klaus\nKLAUS: y\n== c\nKLAUS: z\n").unwrap();
        assert_eq!(b.songs["a"], Track::Aw2(220));
        assert_eq!(b.songs["b"], Track::Co(crate::es_co::KLAUS));
        assert!(!b.songs.contains_key("c"));
        assert!(parse_into(&mut b, "t", "== d\n@SONG sturm\n@SONG enemy1\nKLAUS: x\n").is_err());
        assert!(parse_into(&mut b, "t", "== e\n@SONG nonsense\nKLAUS: x\n").is_err());
    }

    #[test]
    fn groups_expand_to_the_pool() {
        use crate::es_co::*;
        let src = "== t | KLAUS, AURELIA, CASSIUS\nAURELIA: a / b\n@IF KLAUS\n[CO]: x\n@OTHER\n[CO]: y\n@END\nNARRATION: z\n";
        let mut b = Book { scenes: HashMap::new(), songs: HashMap::new(), pages: HashMap::new() };
        parse_into(&mut b, "t", src).unwrap();
        let l = &b.scenes["t"];
        assert_eq!(l.len(), 5);
        assert_eq!(l[0].text, "a\rb");
        assert_eq!((l[1].only, l[1].who), (Some(KLAUS), Speaker::Co(KLAUS, Mood::Normal)));
        assert_eq!(l[2].only, Some(AURELIA));
        assert_eq!(l[3].only, Some(CASSIUS));
        assert_eq!(l[4].who, Speaker::Narrator);
    }

    #[test]
    fn bad_rows_are_errors() {
        let mut b = Book { scenes: HashMap::new(), songs: HashMap::new(), pages: HashMap::new() };
        assert!(parse_into(&mut b, "t", "== t\nNOBODY: hi\n").is_err());
        assert!(parse_into(&mut b, "t", "== u\nKLAUS(x): hi\n").is_err());
        assert!(parse_into(&mut b, "t", "KLAUS: hi\n").is_err());
    }
}
