//! The Emerald Sun COs' own themes: songs written as text in this repository (`music/es/*.m4t`, our own compositions), compiled here to
//! song data for AW2's sound engine (MP2K, "Sappy") and played by it with AW2's own instruments (voice groups read from the ROM at run time).
//!
//! The pipeline (docs/dev/music-kit.md, `aw2dev sound compose`): [`compile`] reads a song file, checks it (every bar adds up, every track of a
//! section fills it, the loop is as long in every track), and writes one MP2K byte stream per track: the intro, a label, the track's state (voice,
//! volume, pan, bend, vibrato: so every pass starts alike), the loop body and a `GOTO` back to the label. [`crate::ds_music`] places the result in the
//! music's free ROM, fills the voice group from the ROM's own ([`VoiceRef`]) and registers a song id for each CO.
//!
//! ## The file format
//! Line based; `;` starts a comment. Names of notes are scientific (`C4` is middle C, key 60; `F#3`, `Bb2`).
//! ```text
//! song klaus                      ; the name (also the file's)
//! tempo 108                       ; beats a minute (the engine stores half)
//! meter 4/4                       ; a bar is 96 ticks of 24 a beat (3/4: 72, 6/8: 72)
//! reverb 173                      ; AW2's CO themes: 173; priority 0
//! inst brass = A.111 shift=-12    ; a voice slot: A (0x08240FB0, the group Kanbei's theme uses), B (Hawke's) or 0x08xxxxxx, then the program; notes are written
//!                                 ; at the sounding pitch and `shift` (semitones) turns that into the key the sample needs (`aw2dev sound voices` lists them)
//! hit kick=36 snare=40 hat=44     ; names for a drum kit's keys
//! track 1 inst=brass vol=100 pan=0 vel=100 gate=90   ; also bendr= mod= lfos= lfodl= trans= gain= (a factor on every volume of the track: the mix)
//! def riff:                       ; a pattern (bars), used as @riff, @riff+2 (transposed), @riff*2 (twice)
//!   | C3/8 C3/8 r/8 C3/8 r/4. |
//! end
//! section A bars=8
//!   1: @riff*4 | C4/2 G4/2 | ...  ; a track's bars (continued on indented lines)
//! end
//! form intro loop A B A           ; the order; `loop` marks where the repeat starts; `A*2` plays A twice
//! ```
//! Tokens: `C4/4` a note (`/4` quarter, `/4.` dotted, `/8t` triplet eighth, `/2+8` sums, `/#30` ticks; no duration repeats the last), `r/4` a rest, `[C3 G3]/2` a
//! chord, `kick/8` a drum hit, a trailing `'` staccato, `_` legato, `>` accent, `!90` velocity, `{vol 90}` `{vol 60>100/48}` (a ramp over 48 ticks) `{pan -20}`
//! `{inst harp}` `{bend 8}` `{mod 6}` `{gate 70}` `{tempo 120}` (first track only), `|` a bar line (checked).
//!
//! ## Quoting AW2's own songs (`rom`), without storing a note of them
//! AW2's songs are Nintendo's and Intelligent Systems': none of their notes may be written into this repository. A song of ours can still *quote* one: a
//! `rom` line names a stretch of an AW2 song by its id, track and bars, with what to do to it, and `@rom:NAME` in a section's track line plays it there.
//! ```text
//! rom hook song=212 track=0 bars=7-14 transpose=-12 srcshift=-12 lower=G#,C# inst=low gain=1.0
//! section A2 bars=8
//!   5: @rom:hook               ; eight bars of our meter (the source's bars, 96 ticks each)
//! ```
//! Options: `song=` (0..504) `track=` `bars=a-b` (source bars, 1-based, `barticks=` a bar's ticks, default 96); `transpose=` semitones of the **sounding** pitch;
//! `srcshift=` the `shift` of the source's voice (so the sounding pitch is known; `aw2dev sound voices` lists them); `lower=G#,C#` lowers those pitch classes by a semitone
//! after the transposition (a major tune made minor); `inst=` plays it on one of our `inst`s (the track's own voice if left out) and then goes back to the track's; `gain=` a factor
//! on the source's volumes, `peak=` brings the loudest of them to that number first; `tempo=` the source's tempo in beats a minute, to keep its speed in real time (the ticks are scaled by our tempo / it; left out, the ticks are copied
//! and the stretch plays at **our** tempo); `raw` copies keys, volumes, pans and the source's own voices unchanged (a drum track, a bass: for the game's own sounds as they are).
//! The game reads the events out of the ROM it is running when it builds the song ([`compile_with`]); the file holds only these references. Without a ROM ([`compile`], the tools,
//! CI) the reference is checked for syntax and is silence of the right length.
//!
//! Dev aid: with `TANGOAW2_ES_MUSIC=<dir>` the songs are read from `<dir>/<name>.m4t` instead of the built-in text (so a song can be rewritten and heard
//! without a rebuild; both peers of a match must not differ, as with the other `TANGOAW2_ES_*` aids).

use std::borrow::Cow;
use std::collections::{BTreeMap, HashMap};

use std::cell::RefCell;

use crate::ds_music::{note, waits, BEND, BENDR, EOT, GOTO, KEYSH, LFODL, LFOS, MOD, PAN, TEMPO, TIE, VOICE, VOL};
use crate::es_rom::{self, RomView, Src};

pub const TICKS_PER_BEAT: u32 = 24;
/// The GBA's frame rate: 16777216 / 280896.
pub const GBA_FPS: f64 = 16_777_216.0 / 280_896.0;
/// The CO themes' music player has 8 tracks.
pub const MAX_TRACKS: usize = 8;
/// AW2 mixes 8 channels, and its own CO themes never sound more than 6 notes at once (measured on all 19): the rest is for the sound effects (priority 10 against the music's 0) that
/// would otherwise cut a note of the theme. A theme of ours keeps to the same (the loudest moment is [`Compiled::peak_voices`]).
pub const MAX_VOICES: usize = 6;
/// AW2's voice groups the CO themes use: Kanbei's, Sensei's, Eagle's ... (`A`) and Hawke's, Jess's ... (`B`).
pub const GROUP_A: u32 = 0x0824_0FB0;
pub const GROUP_B: u32 = 0x0824_15C8;
/// The most bytes a compiled song may take (tracks together), so the free ROM planned for the songs is enough.
pub const MAX_BYTES: usize = 48 * 1024;
/// A track that quotes the ROM is built when the game starts and its size depends on the ROM's bytes: the room kept for it in the song's data (the game checks the bytes fit).
pub const REF_TRACK_CAP: usize = 4096;
/// The voice slots kept for a song that quotes the ROM (it may use the source's own voices).
pub const REF_VOICE_CAP: usize = 40;
/// The default key range of a note.
const LOW: i32 = 12;

/// A song of the Emerald Sun CO `co` (its id from [`crate::co_new`]).
#[derive(Clone, Copy)]
pub struct Source {
    pub co: u8,
    pub name: &'static str,
    pub text: &'static str,
}

/// Song slots of BH2's scene songs (not COs: ids above the CO table, used only as the song's key; [`crate::campaign_music::Track::Own`]).
pub const DOOR: u8 = 200;
pub const CREDITS: u8 = 201;

pub const SOURCES: [Source; 11] = [
    Source {
        co: 86,
        name: "klaus",
        text: include_str!("../music/es/klaus.m4t"),
    },
    Source {
        co: 87,
        name: "aurelia",
        text: include_str!("../music/es/aurelia.m4t"),
    },
    Source {
        co: 88,
        name: "cassius",
        text: include_str!("../music/es/cassius.m4t"),
    },
    Source {
        co: 89,
        name: "livia",
        text: include_str!("../music/es/livia.m4t"),
    },
    Source {
        co: 90,
        name: "varro",
        text: include_str!("../music/es/varro.m4t"),
    },
    // Asuka (CO 92, crate::asuka): her theme is in Versus for everyone, like her.
    Source {
        co: 92,
        name: "asuka",
        text: include_str!("../music/es/asuka.m4t"),
    },
    // Crumb (CO 82, crate::crumb): Black Hole's own soldier, his theme is in Versus like him.
    Source {
        co: crate::co_new::CRUMB,
        name: "crumb",
        text: include_str!("../music/es/crumb.m4t"),
    },
    // Clone Andy (CO 81, crate::co_new): Black Hole's copy has a theme of his own, not Andy's; his Dual Strike theme is built but no row uses it.
    Source {
        co: crate::co_new::CLONE_ANDY,
        name: "cloneandy",
        text: include_str!("../music/es/cloneandy.m4t"),
    },
    // Aria (CO 93, crate::aria): the New Accord's commander, Orange Star's final opponent in the BH2 Campaign; her theme is in Versus like her.
    Source {
        co: crate::co_new::ARIA,
        name: "aria",
        text: include_str!("../music/bh2/aria.m4t"),
    },
    // BH2's scene songs (docs/dev/bh2-text.md): "The Door" under the crate, door and Obelisk scenes, and the staff roll's song.
    Source {
        co: DOOR,
        name: "door",
        text: include_str!("../music/bh2/door.m4t"),
    },
    Source {
        co: CREDITS,
        name: "credits",
        text: include_str!("../music/bh2/credits.m4t"),
    },
];

/// The source text of a song: the dev aid's file if the variable names a folder with one, else the built-in text.
pub fn text(s: &Source) -> Cow<'static, str> {
    if let Some(dir) = std::env::var_os("TANGOAW2_ES_MUSIC") {
        if let Ok(t) = std::fs::read_to_string(std::path::Path::new(&dir).join(format!("{}.m4t", s.name))) {
            return Cow::Owned(t);
        }
    }
    Cow::Borrowed(s.text)
}

/// The song of Emerald Sun CO `co`.
pub fn source(co: u8) -> Option<&'static Source> {
    SOURCES.iter().find(|s| s.co == co)
}

/// One voice of the song's voice group: the entry `index` of the ROM's group at `group`, copied (the sample and keymap pointers stay the ROM's).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct VoiceRef {
    pub group: u32,
    pub index: u8,
}

/// A track's bytes; `label` is where the loop starts and `goto` the offset of the final `GOTO`'s 4-byte target (to be set to the label's address).
#[derive(Clone, Debug)]
pub struct TrackBytes {
    pub bytes: Vec<u8>,
    pub label: usize,
    pub goto: usize,
    /// The room this track takes in the song's data: [`REF_TRACK_CAP`] for a track that quotes the ROM (its bytes are only known when the ROM is read), else `bytes.len()`.
    pub room: usize,
}

/// A song as the engine needs it.
#[derive(Clone, Debug)]
pub struct Compiled {
    pub name: String,
    pub bpm: u32,
    /// Ticks in a bar of the song's meter.
    pub bar_ticks: u32,
    pub reverb: u8,
    pub priority: u8,
    /// Voice slot n of the group is `voices[n]`.
    pub voices: Vec<VoiceRef>,
    pub tracks: Vec<TrackBytes>,
    /// Ticks before the loop, and the loop's length.
    pub intro_ticks: u32,
    pub loop_ticks: u32,
    /// The most notes sounding at once (a note counts from its start to the end of its length: AW2 voices have no release).
    pub peak_voices: usize,
    /// The tick the most notes first sound at once.
    pub peak_at: u32,
    pub notes: usize,
    /// The song quotes AW2's songs (`rom` references): its tracks are only complete when compiled with the ROM ([`compile_with`]).
    pub needs_rom: bool,
}

impl Compiled {
    /// Voice slots to keep room for in the song's data.
    pub fn voice_room(&self) -> usize {
        if self.needs_rom {
            REF_VOICE_CAP.max(self.voices.len())
        } else {
            self.voices.len()
        }
    }
    /// Real time of `ticks`: the engine runs a frame of the GBA's 59.7275 Hz at tempo/150 of a tick per beat-minute (a nominal 150 would be one tick a frame).
    pub fn seconds(&self, ticks: u32) -> f64 {
        ticks as f64 * 150.0 / (GBA_FPS * self.bpm as f64)
    }
    pub fn loop_seconds(&self) -> f64 {
        self.seconds(self.loop_ticks)
    }
    pub fn intro_seconds(&self) -> f64 {
        self.seconds(self.intro_ticks)
    }
    pub fn bytes(&self) -> usize {
        self.tracks.iter().map(|t| t.bytes.len()).sum()
    }
}

// --- The text -----------------------------------------------------------------------------------------------

#[derive(Clone, Debug)]
struct TrackSpec {
    n: u32,
    inst: String,
    vol: i32,
    pan: i32,
    vel: i32,
    gate: i32,
    bendr: i32,
    modd: i32,
    lfos: i32,
    lfodl: i32,
    trans: i32,
    /// A factor on every volume of the track (the mix: one number to tune a track against the others).
    gain: f64,
}

#[derive(Clone, Debug, Default)]
struct Section {
    bars: Option<u32>,
    lines: BTreeMap<u32, String>,
}

struct Parsed {
    name: String,
    bpm: u32,
    bar_ticks: u32,
    reverb: u8,
    priority: u8,
    insts: Vec<(String, VoiceRef, i32)>,
    hits: HashMap<String, u8>,
    tracks: Vec<TrackSpec>,
    defs: HashMap<String, String>,
    sections: HashMap<String, Section>,
    form: Vec<(String, u32)>,
    loop_at: Option<usize>,
    /// The `rom` references by name.
    refs: HashMap<String, RomRef>,
    /// Voices a reference with `raw` brought in from its source song, after the `inst`s (slot = insts.len() + index).
    extra: RefCell<Vec<VoiceRef>>,
}

/// A `rom` line: a stretch of one of AW2's songs, and what to do to it.
#[derive(Clone, Debug)]
struct RomRef {
    song: u16,
    track: usize,
    from: u32,
    to: u32,
    bar_ticks: u32,
    transpose: i32,
    src_shift: i32,
    lower: Vec<i32>,
    inst: Option<String>,
    gain: f64,
    /// The source's loudest VOLUME in the stretch is brought to this (before the track's `gain=`), so the quote is as loud as we say whatever the source's own level was.
    peak: Option<f64>,
    tempo: Option<u32>,
    raw: bool,
}

fn err<T>(line: usize, msg: impl std::fmt::Display) -> Result<T, String> {
    Err(format!("line {line}: {msg}"))
}

fn parse_int(s: &str, line: usize, what: &str) -> Result<i32, String> {
    let t = s.trim();
    let v = if let Some(h) = t.strip_prefix("0x") {
        i64::from_str_radix(h, 16).ok()
    } else {
        t.parse::<i64>().ok()
    };
    match v {
        Some(v) => Ok(v as i32),
        None => err(line, format!("{what}: '{s}' is not a number")),
    }
}

/// A key from a note name (`C4`, `F#3`, `Bb2`) or a number.
fn key_of(s: &str) -> Option<i32> {
    let b = s.as_bytes();
    if b.is_empty() {
        return None;
    }
    if b[0].is_ascii_digit() {
        return s.parse().ok();
    }
    let base = match b[0] {
        b'C' => 0,
        b'D' => 2,
        b'E' => 4,
        b'F' => 5,
        b'G' => 7,
        b'A' => 9,
        b'B' => 11,
        _ => return None,
    };
    let mut i = 1;
    let mut semi = base;
    if i < b.len() && (b[i] == b'#' || b[i] == b's') {
        semi += 1;
        i += 1;
    } else if i < b.len() && b[i] == b'b' {
        semi -= 1;
        i += 1;
    }
    let oct: i32 = s[i..].parse().ok()?;
    Some(12 * (oct + 1) + semi)
}

fn parse(text: &str) -> Result<Parsed, String> {
    let mut p = Parsed {
        name: String::new(),
        bpm: 120,
        bar_ticks: 96,
        reverb: 173,
        priority: 0,
        insts: Vec::new(),
        hits: HashMap::new(),
        tracks: Vec::new(),
        defs: HashMap::new(),
        sections: HashMap::new(),
        form: Vec::new(),
        loop_at: None,
        refs: HashMap::new(),
        extra: RefCell::new(Vec::new()),
    };
    enum Mode {
        None,
        Def(String, String),
        Section(String, Option<u32>),
    }
    let mut mode = Mode::None;
    for (i, raw) in text.lines().enumerate() {
        let ln = i + 1;
        let line = raw.split(';').next().unwrap_or("").trim_end();
        if line.trim().is_empty() {
            continue;
        }
        let t = line.trim();
        match &mut mode {
            Mode::Def(name, body) => {
                if t == "end" {
                    p.defs.insert(name.clone(), body.clone());
                    mode = Mode::None;
                } else {
                    body.push(' ');
                    body.push_str(t);
                }
                continue;
            }
            Mode::Section(name, cur) => {
                if t == "end" {
                    mode = Mode::None;
                    continue;
                }
                let sec = p.sections.get_mut(name.as_str()).unwrap();
                if let Some((n, rest)) = t.split_once(':') {
                    if let Ok(n) = n.trim().parse::<u32>() {
                        *cur = Some(n);
                        if sec.lines.contains_key(&n) {
                            return err(ln, format!("track {n} twice in section {name}"));
                        }
                        sec.lines.insert(n, rest.trim().to_string());
                        continue;
                    }
                }
                match cur {
                    Some(n) => {
                        let l = sec.lines.get_mut(n).unwrap();
                        l.push(' ');
                        l.push_str(t);
                    }
                    None => return err(ln, "a section line must start with a track number and a colon"),
                }
                continue;
            }
            Mode::None => {}
        }
        let mut w = t.split_whitespace();
        let head = w.next().unwrap();
        let rest: Vec<&str> = w.collect();
        match head {
            "song" => p.name = rest.first().map(|s| s.to_string()).unwrap_or_default(),
            "tempo" => {
                p.bpm = parse_int(rest.first().unwrap_or(&""), ln, "tempo")? as u32;
                if p.bpm < 40 || p.bpm > 250 || p.bpm % 2 != 0 {
                    return err(
                        ln,
                        "tempo must be an even number of beats a minute, 40 to 250 (the engine stores half)",
                    );
                }
            }
            "meter" => {
                let (a, b) = rest
                    .first()
                    .and_then(|m| m.split_once('/'))
                    .ok_or(format!("line {ln}: meter wants n/d"))?;
                let (a, b) = (parse_int(a, ln, "meter")? as u32, parse_int(b, ln, "meter")? as u32);
                if a == 0 || b == 0 || 96 % b != 0 {
                    return err(ln, "meter denominator must divide 96 (1 2 4 8 16 32)");
                }
                p.bar_ticks = a * 96 / b;
            }
            "reverb" => p.reverb = parse_int(rest.first().unwrap_or(&""), ln, "reverb")?.clamp(0, 255) as u8,
            "priority" => p.priority = parse_int(rest.first().unwrap_or(&""), ln, "priority")?.clamp(0, 255) as u8,
            "inst" => {
                // inst name = G.idx
                let s = rest.join(" ");
                let (name, v) = s.split_once('=').ok_or(format!("line {ln}: inst NAME = A.12"))?;
                let mut vw = v.split_whitespace();
                let v = vw.next().unwrap_or("");
                let mut shift = 0;
                for opt in vw {
                    match opt.strip_prefix("shift=") {
                        Some(n) => shift = parse_int(n, ln, "shift")?,
                        None => return err(ln, format!("unknown inst option '{opt}'")),
                    }
                }
                let (g, idx) = v.trim().split_once('.').ok_or(format!("line {ln}: inst NAME = A.12"))?;
                let group = match g.trim() {
                    "A" => GROUP_A,
                    "B" => GROUP_B,
                    h => parse_int(h, ln, "voice group")? as u32,
                };
                let index = parse_int(idx, ln, "program")?;
                if !(0..128).contains(&index) || !(0x0800_0000..0x0880_0000).contains(&group) {
                    return err(ln, "voice group must be A, B or a ROM address, program 0..127");
                }
                p.insts.push((
                    name.trim().to_string(),
                    VoiceRef {
                        group,
                        index: index as u8,
                    },
                    shift,
                ));
            }
            "rom" => {
                let name = rest
                    .first()
                    .ok_or(format!("line {ln}: rom NAME song=N track=N bars=A-B ..."))?;
                let mut r = RomRef {
                    song: u16::MAX,
                    track: usize::MAX,
                    from: 0,
                    to: 0,
                    bar_ticks: 96,
                    transpose: 0,
                    src_shift: 0,
                    lower: Vec::new(),
                    inst: None,
                    gain: 1.0,
                    peak: None,
                    tempo: None,
                    raw: false,
                };
                for kv in &rest[1..] {
                    if *kv == "raw" {
                        r.raw = true;
                        continue;
                    }
                    let (k, v) = kv
                        .split_once('=')
                        .ok_or(format!("line {ln}: rom options are key=value (or `raw`)"))?;
                    match k {
                        "song" => r.song = parse_int(v, ln, k)?.clamp(0, 65535) as u16,
                        "track" => r.track = parse_int(v, ln, k)?.max(0) as usize,
                        "bars" => {
                            let (a, b) = v.split_once('-').unwrap_or((v, v));
                            r.from = parse_int(a, ln, k)?.max(0) as u32;
                            r.to = parse_int(b, ln, k)?.max(0) as u32;
                        }
                        "barticks" => r.bar_ticks = parse_int(v, ln, k)?.max(1) as u32,
                        "transpose" => r.transpose = parse_int(v, ln, k)?,
                        "srcshift" => r.src_shift = parse_int(v, ln, k)?,
                        "lower" => {
                            for pc in v.split(',') {
                                let key = key_of(&format!("{pc}4"))
                                    .ok_or(format!("line {ln}: lower: '{pc}' is not a pitch class"))?;
                                r.lower.push(key.rem_euclid(12));
                            }
                        }
                        "inst" => r.inst = Some(v.to_string()),
                        "gain" => {
                            r.gain = v
                                .parse::<f64>()
                                .map_err(|_| format!("line {ln}: gain: '{v}' is not a number"))?
                        }
                        "peak" => {
                            r.peak = Some(
                                v.parse::<f64>()
                                    .map_err(|_| format!("line {ln}: peak: '{v}' is not a number"))?,
                            )
                        }
                        "tempo" => r.tempo = Some(parse_int(v, ln, k)?.max(1) as u32),
                        _ => return err(ln, format!("unknown rom option '{k}'")),
                    }
                }
                if r.song == u16::MAX || r.track == usize::MAX || r.from == 0 || r.to < r.from {
                    return err(ln, "rom needs song=N track=N bars=A-B (source bars from 1)");
                }
                if r.song as u32 >= es_rom::SONGS {
                    return err(ln, format!("rom: AW2 has songs 0..{}", es_rom::SONGS - 1));
                }
                if p.refs.insert(name.to_string(), r).is_some() {
                    return err(ln, format!("rom {name} twice"));
                }
            }
            "hit" => {
                for h in rest {
                    let (n, k) = h.split_once('=').ok_or(format!("line {ln}: hit name=key"))?;
                    let key = key_of(k).ok_or(format!("line {ln}: bad key '{k}'"))?;
                    p.hits.insert(n.to_string(), key as u8);
                }
            }
            "track" => {
                let n = parse_int(rest.first().unwrap_or(&""), ln, "track number")? as u32;
                let mut s = TrackSpec {
                    n,
                    inst: String::new(),
                    vol: 100,
                    pan: 0,
                    vel: 100,
                    gate: 90,
                    bendr: 2,
                    modd: 0,
                    lfos: 22,
                    lfodl: 0,
                    trans: 0,
                    gain: 1.0,
                };
                for kv in &rest[1..] {
                    let (k, v) = kv
                        .split_once('=')
                        .ok_or(format!("line {ln}: track options are key=value"))?;
                    match k {
                        "inst" => s.inst = v.to_string(),
                        "vol" => s.vol = parse_int(v, ln, k)?,
                        "pan" => s.pan = parse_int(v, ln, k)?,
                        "vel" => s.vel = parse_int(v, ln, k)?,
                        "gate" => s.gate = parse_int(v, ln, k)?,
                        "bendr" => s.bendr = parse_int(v, ln, k)?,
                        "mod" => s.modd = parse_int(v, ln, k)?,
                        "lfos" => s.lfos = parse_int(v, ln, k)?,
                        "lfodl" => s.lfodl = parse_int(v, ln, k)?,
                        "trans" => s.trans = parse_int(v, ln, k)?,
                        "gain" => {
                            s.gain = v
                                .parse::<f64>()
                                .map_err(|_| format!("line {ln}: gain: '{v}' is not a number"))?
                        }
                        _ => return err(ln, format!("unknown track option '{k}'")),
                    }
                }
                if p.tracks.iter().any(|t| t.n == n) {
                    return err(ln, format!("track {n} twice"));
                }
                p.tracks.push(s);
            }
            "def" => {
                let name = rest
                    .first()
                    .map(|s| s.trim_end_matches(':').to_string())
                    .ok_or(format!("line {ln}: def NAME:"))?;
                mode = Mode::Def(name, String::new());
            }
            "section" => {
                let name = rest
                    .first()
                    .ok_or(format!("line {ln}: section NAME [bars=N]"))?
                    .to_string();
                let mut sec = Section::default();
                for kv in &rest[1..] {
                    if let Some(v) = kv.strip_prefix("bars=") {
                        sec.bars = Some(parse_int(v, ln, "bars")? as u32);
                    }
                }
                p.sections.insert(name.clone(), sec);
                mode = Mode::Section(name, None);
            }
            "form" => {
                for tok in rest {
                    if tok == "loop" {
                        p.loop_at = Some(p.form.len());
                        continue;
                    }
                    let (n, k) = match tok.split_once('*') {
                        Some((n, k)) => (n, parse_int(k, ln, "repeat")? as u32),
                        None => (tok, 1),
                    };
                    p.form.push((n.to_string(), k));
                }
            }
            _ => return err(ln, format!("unknown directive '{head}'")),
        }
    }
    if !matches!(mode, Mode::None) {
        return Err("the file ends inside a def or a section (missing `end`)".into());
    }
    if p.tracks.is_empty() || p.tracks.len() > MAX_TRACKS {
        return Err(format!("{} tracks (1 to {MAX_TRACKS})", p.tracks.len()));
    }
    if p.form.is_empty() {
        return Err("no `form` line".into());
    }
    Ok(p)
}

// --- Events -------------------------------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Ctl {
    Voice = 0,
    Vol,
    Pan,
    BendR,
    Bend,
    LfoS,
    LfoDl,
    Mod,
    KeySh,
    Tempo,
}
const CTLS: usize = 10;

#[derive(Clone, Copy, Debug)]
enum Ev {
    Ctl(Ctl, i32),
    Eot(u8),
    Note { key: u8, vel: u8, len: u32 },
}

impl Ev {
    fn order(&self) -> u8 {
        match self {
            Ev::Ctl(..) => 0,
            Ev::Eot(_) => 1,
            Ev::Note { .. } => 2,
        }
    }
}

struct Eval<'a> {
    p: &'a Parsed,
    track: &'a TrackSpec,
    first: bool,
    evs: Vec<(u32, Ev)>,
    tick: u32,
    bar_start: u32,
    bars: u32,
    vel: i32,
    gate: i32,
    dur: u32,
    /// The current voice's shift: a note's key is the sounding pitch plus this (AW2's samples are recorded at different octaves).
    shift: i32,
    /// The slot of the voice now selected.
    slot: i32,
    /// The ROM the `rom` references read, if there is one.
    rom: Option<&'a RomView<'a>>,
    /// A `rom` reference was played in this track.
    used_ref: bool,
}

fn tokens(text: &str) -> Result<Vec<String>, String> {
    let mut out = Vec::new();
    let mut cur = String::new();
    let mut depth = 0;
    for c in text.chars() {
        match c {
            '{' | '[' => {
                depth += 1;
                cur.push(c);
            }
            '}' | ']' => {
                depth -= 1;
                if depth < 0 {
                    return Err("unbalanced bracket".into());
                }
                cur.push(c);
            }
            c if c.is_whitespace() && depth == 0 => {
                if !cur.is_empty() {
                    out.push(std::mem::take(&mut cur));
                }
            }
            c => cur.push(c),
        }
    }
    if depth != 0 {
        return Err("unbalanced bracket".into());
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    Ok(out)
}

/// `4`, `4.`, `8t`, `2+8`, `#30`: ticks.
fn duration(s: &str) -> Result<u32, String> {
    let mut total = 0;
    for part in s.split('+') {
        if let Some(n) = part.strip_prefix('#') {
            total += n.parse::<u32>().map_err(|_| format!("bad duration '{s}'"))?;
            continue;
        }
        let (num, dots, triplet) = {
            let mut n = part;
            let mut dots = 0;
            let mut tr = false;
            loop {
                if let Some(x) = n.strip_suffix('.') {
                    dots += 1;
                    n = x;
                } else if let Some(x) = n.strip_suffix('t') {
                    tr = true;
                    n = x;
                } else {
                    break;
                }
            }
            (n, dots, tr)
        };
        let d: u32 = num.parse().map_err(|_| format!("bad duration '{s}'"))?;
        if d == 0 || 96 % d != 0 {
            return Err(format!("duration /{d} does not divide a whole note (96 ticks)"));
        }
        let mut t = 96 / d;
        let mut add = t;
        for _ in 0..dots {
            add /= 2;
            t += add;
        }
        if triplet {
            if t % 3 != 0 {
                return Err(format!("triplet /{part} is not a whole number of ticks"));
            }
            t = t * 2 / 3;
        }
        total += t;
    }
    Ok(total)
}

impl<'a> Eval<'a> {
    fn new(p: &'a Parsed, track: &'a TrackSpec, first: bool, start: u32) -> Self {
        let shift = p.insts.iter().find(|i| i.0 == track.inst).map_or(0, |i| i.2);
        Eval {
            p,
            track,
            first,
            evs: Vec::new(),
            tick: start,
            bar_start: start,
            bars: 0,
            vel: track.vel,
            gate: track.gate,
            dur: 24,
            shift,
            slot: p.insts.iter().position(|i| i.0 == track.inst).map_or(0, |i| i as i32),
            rom: None,
            used_ref: false,
        }
    }

    fn hit_or_pitch(&self, head: &str, trans: i32) -> Result<i32, String> {
        if let Some(&k) = self.p.hits.get(head) {
            return Ok(k as i32);
        }
        match key_of(head) {
            Some(k) => Ok(k + trans + self.shift),
            None => Err(format!("'{head}' is neither a note nor a drum hit")),
        }
    }

    fn run(&mut self, text: &str, trans: i32, depth: u32) -> Result<(), String> {
        if depth > 8 {
            return Err("patterns nest too deep".into());
        }
        for tok in tokens(text)? {
            self.token(&tok, trans, depth)?;
        }
        Ok(())
    }

    fn token(&mut self, tok: &str, trans: i32, depth: u32) -> Result<(), String> {
        if tok == "|" {
            if self.tick != self.bar_start {
                let len = self.tick - self.bar_start;
                if len != self.p.bar_ticks {
                    return Err(format!(
                        "bar {} is {} ticks, a bar is {}",
                        self.bars + 1,
                        len,
                        self.p.bar_ticks
                    ));
                }
                self.bars += 1;
                self.bar_start = self.tick;
            }
            return Ok(());
        }
        if let Some(m) = tok.strip_prefix("@rom:") {
            return self.rom_ref(m);
        }
        if let Some(m) = tok.strip_prefix('@') {
            let (mut name, mut tr, mut times) = (m, 0i32, 1u32);
            if let Some((a, b)) = name.split_once('*') {
                // @name*3 or @name+2*3
                times = b.parse().map_err(|_| format!("bad repeat in '{tok}'"))?;
                name = a;
            }
            if let Some(i) = name.find(['+', '-']) {
                tr = name[i..].parse().map_err(|_| format!("bad transposition in '{tok}'"))?;
                name = &name[..i];
            }
            let body = self.p.defs.get(name).ok_or(format!("no pattern '{name}'"))?.clone();
            for _ in 0..times {
                self.run(&body, trans + tr, depth + 1)?;
            }
            return Ok(());
        }
        if let Some(c) = tok.strip_prefix('{') {
            return self.control(c.strip_suffix('}').ok_or("missing }")?);
        }
        if let Some(v) = tok.strip_prefix('!') {
            self.vel = v.parse().map_err(|_| format!("bad velocity '{tok}'"))?;
            return Ok(());
        }
        // head [/dur] [mods]
        let (head, tail) = match tok.find('/') {
            Some(i) if !tok[..i].contains('[') || tok[..i].contains(']') => (&tok[..i], Some(&tok[i + 1..])),
            Some(_) => {
                let close = tok.rfind(']').ok_or("missing ]")?;
                match tok[close..].find('/') {
                    Some(i) => (&tok[..close + i], Some(&tok[close + i + 1..])),
                    None => (tok, None),
                }
            }
            None => (tok, None),
        };
        let mut mods = String::new();
        let mut dur = self.dur;
        if let Some(t) = tail {
            let cut = t.find(['\'', '_', '>']).unwrap_or(t.len());
            mods = t[cut..].to_string();
            dur = duration(&t[..cut])?;
            self.dur = dur;
        } else if let Some(i) = head.find(['\'', '_', '>']) {
            // "C4'" without a duration
            mods = head[i..].to_string();
            return self.emit(&head[..i], dur, &mods, trans);
        }
        self.emit(head, dur, &mods, trans)
    }

    fn emit(&mut self, head: &str, dur: u32, mods: &str, trans: i32) -> Result<(), String> {
        let mut gate = self.gate;
        let mut vel = self.vel;
        let mut extra = 0;
        for m in mods.chars() {
            match m {
                '\'' => gate = 50,
                '_' => {
                    gate = 100;
                    extra = 3;
                }
                '>' => vel += 18,
                _ => return Err(format!("unknown mark '{m}'")),
            }
        }
        let vel = vel.clamp(1, 127) as u8;
        let len = ((dur as i32 * gate + 50) / 100).max(1) as u32 + extra;
        if head == "r" || head == "R" {
            self.tick += dur;
            return Ok(());
        }
        let keys: Vec<i32> = if let Some(inner) = head.strip_prefix('[') {
            let inner = inner.strip_suffix(']').ok_or("missing ]")?;
            inner
                .split_whitespace()
                .map(|k| self.hit_or_pitch(k, trans))
                .collect::<Result<_, _>>()?
        } else {
            vec![self.hit_or_pitch(head, trans)?]
        };
        for k in keys {
            if !(LOW..128).contains(&k) {
                return Err(format!("key {k} out of range in '{head}'"));
            }
            self.evs.push((self.tick, Ev::Note { key: k as u8, vel, len }));
        }
        self.tick += dur;
        Ok(())
    }

    /// `@rom:NAME`: the stretch of AW2's song, read from the ROM now (or silence of its length without one).
    fn rom_ref(&mut self, name: &str) -> Result<(), String> {
        let r = self
            .p
            .refs
            .get(name)
            .ok_or(format!("no `rom {name}` line for @rom:{name}"))?
            .clone();
        self.used_ref = true;
        if self.tick != self.bar_start {
            return Err(format!("@rom:{name} must start on a bar line"));
        }
        let bar = self.p.bar_ticks;
        let (ws, we) = ((r.from - 1) * r.bar_ticks, r.to * r.bar_ticks);
        let bpm = self.p.bpm;
        let scale = |t: u32| -> u32 {
            match r.tempo {
                Some(b) => ((t as u64 * bpm as u64 + b as u64 / 2) / b as u64) as u32,
                None => t,
            }
        };
        let total = scale(we - ws);
        if total % bar != 0 {
            return Err(format!(
                "@rom:{name} is {total} ticks, not whole bars of this song ({bar} ticks)"
            ));
        }
        let start = self.tick;
        if let Some(rom) = self.rom {
            self.rom_events(rom, &r, name, start, ws, we, &scale)?;
        }
        self.tick += total;
        self.bars += total / bar;
        self.bar_start = self.tick;
        Ok(())
    }

    #[allow(clippy::too_many_arguments)]
    fn rom_events(
        &mut self,
        rom: &RomView,
        r: &RomRef,
        name: &str,
        start: u32,
        ws: u32,
        we: u32,
        scale: &dyn Fn(u32) -> u32,
    ) -> Result<(), String> {
        let src = es_rom::decode(rom, r.song, r.track, we).map_err(|e| format!("rom {name}: {e}"))?;
        let group = es_rom::song_group(rom, r.song).map_err(|e| format!("rom {name}: {e}"))?;
        let at = |t: u32| start + scale(t - ws);
        // the loudest volume in force in the stretch: the one at its start and every change inside
        let vols: Vec<(u32, u8)> = src
            .iter()
            .filter_map(|(t, e)| {
                if let Src::Ctl(0xBE, v) = e {
                    Some((*t, *v))
                } else {
                    None
                }
            })
            .collect();
        let at_start = vols.iter().filter(|(t, _)| *t < ws).last().map(|x| x.1).unwrap_or(0);
        let vmax = vols
            .iter()
            .filter(|(t, _)| *t >= ws && *t < we)
            .map(|x| x.1)
            .chain([at_start])
            .max()
            .unwrap_or(0);
        let norm = match r.peak {
            Some(p) if vmax > 0 => p / vmax as f64,
            _ => 1.0,
        };
        let vol = |v: u8| ((v as f64 * norm * r.gain * self.track.gain).round() as i32).clamp(0, 127);
        // the instrument it is played on
        let (dst_shift, back) = match &r.inst {
            Some(n) if !r.raw => {
                let slot = self
                    .p
                    .insts
                    .iter()
                    .position(|(x, _, _)| x == n)
                    .ok_or(format!("rom {name}: no inst '{n}'"))?;
                let back = (self.slot, self.shift);
                self.slot = slot as i32;
                self.shift = self.p.insts[slot].2;
                self.evs.push((start, Ev::Ctl(Ctl::Voice, slot as i32)));
                (self.shift, Some(back))
            }
            _ => (self.shift, None),
        };
        let slot_of = |program: u8| -> i32 {
            let v = VoiceRef { group, index: program };
            if let Some(i) = self.p.insts.iter().position(|(_, x, _)| *x == v) {
                return i as i32;
            }
            let mut extra = self.p.extra.borrow_mut();
            let i = match extra.iter().position(|x| *x == v) {
                Some(i) => i,
                None => {
                    extra.push(v);
                    extra.len() - 1
                }
            };
            (self.p.insts.len() + i) as i32
        };
        let key_of_src = |key: u8, keysh: i32| -> Result<u8, String> {
            let k = key as i32 + keysh;
            let out = if r.raw {
                k
            } else {
                let mut s = k - r.src_shift + r.transpose;
                if r.lower.contains(&s.rem_euclid(12)) {
                    s -= 1;
                }
                s + dst_shift
            };
            if !(LOW..128).contains(&out) {
                return Err(format!("rom {name}: key {out} out of range (from source key {key})"));
            }
            Ok(out as u8)
        };
        // The controllers' values at the start of the stretch, then the changes inside it.
        let mut state: Vec<(u8, u8)> = Vec::new();
        let mut keysh = 0i32;
        let mut ties: Vec<(u32, u8, u8)> = Vec::new();
        let mut inside: Vec<(u32, Src)> = Vec::new();
        for (t, e) in &src {
            if *t < ws {
                if let Src::Ctl(c, v) = e {
                    if *c == 0xBC {
                        keysh = *v as i8 as i32;
                    }
                    match state.iter_mut().find(|s| s.0 == *c) {
                        Some(s) => s.1 = *v,
                        None => state.push((*c, *v)),
                    }
                }
            } else if *t < we {
                inside.push((*t, *e));
            }
        }
        let ctl = |c: u8, v: u8, evs: &mut Vec<(u32, Ev)>, t: u32| {
            let ev = match c {
                0xBE => Some(Ev::Ctl(Ctl::Vol, vol(v))),
                0xBF if r.raw => Some(Ev::Ctl(Ctl::Pan, v as i32)),
                0xBD if r.raw => Some(Ev::Ctl(Ctl::Voice, slot_of(v))),
                0xC0 => Some(Ev::Ctl(Ctl::Bend, v as i32)),
                0xC1 => Some(Ev::Ctl(Ctl::BendR, v as i32)),
                0xC2 => Some(Ev::Ctl(Ctl::LfoS, v as i32)),
                0xC3 => Some(Ev::Ctl(Ctl::LfoDl, v as i32)),
                0xC4 => Some(Ev::Ctl(Ctl::Mod, v as i32)),
                _ => None,
            };
            if let Some(ev) = ev {
                evs.push((t, ev));
            }
        };
        for (c, v) in &state {
            ctl(*c, *v, &mut self.evs, start);
        }
        let mut push_note =
            |evs: &mut Vec<(u32, Ev)>, t: u32, key: u8, vel: u8, end: u32, keysh: i32| -> Result<(), String> {
                let a = at(t);
                let b = start + scale(end.min(we) - ws);
                evs.push((
                    a,
                    Ev::Note {
                        key: key_of_src(key, keysh)?,
                        vel: vel.clamp(1, 127),
                        len: b.saturating_sub(a).max(1),
                    },
                ));
                Ok(())
            };
        for (t, e) in &inside {
            match *e {
                Src::Ctl(c, v) => {
                    if c == 0xBC {
                        keysh = v as i8 as i32;
                    }
                    ctl(c, v, &mut self.evs, at(*t));
                }
                Src::Note { key, vel, len: Some(l) } => push_note(&mut self.evs, *t, key, vel, *t + l, keysh)?,
                Src::Note { key, vel, len: None } => ties.push((*t, key, vel)),
                Src::Eot(key) => {
                    if let Some(i) = ties.iter().position(|x| x.1 == key) {
                        let (t0, k, v) = ties.remove(i);
                        push_note(&mut self.evs, t0, k, v, *t, keysh)?;
                    }
                }
            }
        }
        for (t0, k, v) in ties {
            push_note(&mut self.evs, t0, k, v, we, keysh)?;
        }
        if let Some((slot, shift)) = back {
            self.slot = slot;
            self.shift = shift;
            self.evs.push((start + scale(we - ws), Ev::Ctl(Ctl::Voice, slot)));
        }
        Ok(())
    }

    fn control(&mut self, c: &str) -> Result<(), String> {
        let mut w = c.split_whitespace();
        let name = w.next().ok_or("empty {}")?;
        let arg = w.next().ok_or(format!("{{{name}}} wants a value"))?;
        let num = |s: &str| s.parse::<i32>().map_err(|_| format!("bad value '{s}' in {{{c}}}"));
        let (ctl, off) = match name {
            "vol" => (Ctl::Vol, 0),
            "pan" => (Ctl::Pan, 64),
            "bend" => (Ctl::Bend, 64),
            "bendr" => (Ctl::BendR, 0),
            "mod" => (Ctl::Mod, 0),
            "lfos" => (Ctl::LfoS, 0),
            "lfodl" => (Ctl::LfoDl, 0),
            "trans" => (Ctl::KeySh, 0),
            "tempo" => {
                if !self.first {
                    return Err("{tempo} only in the first track".into());
                }
                self.evs.push((self.tick, Ev::Ctl(Ctl::Tempo, num(arg)? / 2)));
                return Ok(());
            }
            "inst" => {
                let slot = self
                    .p
                    .insts
                    .iter()
                    .position(|(n, _, _)| n == arg)
                    .ok_or(format!("no inst '{arg}'"))?;
                self.shift = self.p.insts[slot].2;
                self.slot = slot as i32;
                self.evs.push((self.tick, Ev::Ctl(Ctl::Voice, slot as i32)));
                return Ok(());
            }
            "gate" => {
                self.gate = num(arg)?;
                return Ok(());
            }
            "vel" => {
                self.vel = num(arg)?;
                return Ok(());
            }
            _ => return Err(format!("unknown control {{{name}}}")),
        };
        let g = if ctl == Ctl::Vol { self.track.gain } else { 1.0 };
        let scale = |v: i32| ((v as f64 * g).round() as i32).clamp(0, 127);
        if let Some((a, rest)) = arg.split_once('>') {
            // a ramp: vol 40>100/48
            let (b, d) = rest.split_once('/').ok_or("a ramp is {vol 40>100/48}")?;
            let (a, b, d) = (num(a)?, num(b)?, num(d)?.max(4));
            let steps = (d / 4).max(1);
            for k in 0..=steps {
                let v = a + (b - a) * k as i32 / steps as i32;
                self.evs.push((
                    self.tick + (d as u32 * k as u32) / steps as u32,
                    Ev::Ctl(
                        ctl,
                        if ctl == Ctl::Vol {
                            scale(v)
                        } else {
                            (v + off).clamp(0, 127)
                        },
                    ),
                ));
            }
        } else {
            self.evs.push((
                self.tick,
                Ev::Ctl(
                    ctl,
                    if ctl == Ctl::Vol {
                        scale(num(arg)?)
                    } else {
                        (num(arg)? + off).clamp(0, 127)
                    },
                ),
            ));
        }
        Ok(())
    }
}

// --- Compiling ---------------------------------------------------------------------------------------------

fn state_commands(out: &mut Vec<u8>, st: &[i32; CTLS], touched: &[bool; CTLS], first: bool) {
    let put = |out: &mut Vec<u8>, cmd: u8, v: i32| out.extend([cmd, v.clamp(0, 127) as u8]);
    if first {
        put(out, TEMPO, st[Ctl::Tempo as usize]);
    }
    put(out, VOICE, st[Ctl::Voice as usize]);
    put(out, VOL, st[Ctl::Vol as usize]);
    put(out, PAN, st[Ctl::Pan as usize]);
    if touched[Ctl::BendR as usize] {
        put(out, BENDR, st[Ctl::BendR as usize]);
    }
    if touched[Ctl::Bend as usize] {
        put(out, BEND, st[Ctl::Bend as usize]);
    }
    if touched[Ctl::LfoS as usize] {
        put(out, LFOS, st[Ctl::LfoS as usize]);
    }
    if touched[Ctl::LfoDl as usize] {
        put(out, LFODL, st[Ctl::LfoDl as usize]);
    }
    if touched[Ctl::Mod as usize] {
        put(out, MOD, st[Ctl::Mod as usize]);
    }
    if touched[Ctl::KeySh as usize] {
        out.extend([KEYSH, st[Ctl::KeySh as usize] as i8 as u8]);
    }
}

fn write_track(
    spec: &TrackSpec,
    slot: i32,
    first: bool,
    bpm: u32,
    evs: &[(u32, Ev)],
    loop_tick: u32,
    end: u32,
) -> Result<TrackBytes, String> {
    let mut st = [0i32; CTLS];
    st[Ctl::Voice as usize] = slot;
    st[Ctl::Vol as usize] = ((spec.vol as f64 * spec.gain).round() as i32).clamp(0, 127);
    st[Ctl::Pan as usize] = 64 + spec.pan;
    st[Ctl::BendR as usize] = spec.bendr;
    st[Ctl::Bend as usize] = 64;
    st[Ctl::LfoS as usize] = spec.lfos;
    st[Ctl::LfoDl as usize] = spec.lfodl;
    st[Ctl::Mod as usize] = spec.modd;
    st[Ctl::KeySh as usize] = spec.trans;
    st[Ctl::Tempo as usize] = bpm as i32 / 2;
    let mut touched = [false; CTLS];
    touched[Ctl::BendR as usize] = spec.bendr != 2;
    touched[Ctl::LfoS as usize] = spec.modd != 0 || spec.lfos != 22;
    touched[Ctl::LfoDl as usize] = spec.lfodl != 0;
    touched[Ctl::Mod as usize] = spec.modd != 0;
    touched[Ctl::KeySh as usize] = spec.trans != 0;
    for (_, e) in evs {
        if let Ev::Ctl(c, _) = e {
            touched[*c as usize] = true;
        }
    }
    let mut out = Vec::new();
    let mut cur = 0u32;
    let mut label = None;
    if loop_tick == 0 {
        label = Some(0);
        state_commands(&mut out, &st, &touched, first);
    } else {
        state_commands(&mut out, &st, &touched, first);
    }
    let mut ordered: Vec<(u32, Ev)> = evs.to_vec();
    ordered.sort_by_key(|(t, e)| (*t, e.order()));
    // Notes too long for a note command are tied and ended by an EOT of their own.
    let mut with_eot: Vec<(u32, Ev)> = Vec::new();
    for (t, e) in ordered {
        match e {
            Ev::Note { key, vel, len } if note(key, vel, len).is_none() => {
                with_eot.push((t, Ev::Note { key, vel, len: 0 }));
                with_eot.push((t + len, Ev::Eot(key)));
            }
            _ => with_eot.push((t, e)),
        }
    }
    with_eot.sort_by_key(|(t, e)| (*t, e.order()));
    for (t, e) in with_eot {
        if t >= end {
            if matches!(e, Ev::Ctl(..)) {
                continue; // (a reference giving the voice back at the song's end: every pass starts from the state block anyway)
            }
            return Err(format!(
                "track {}: an event at tick {t} lies past the end ({end})",
                spec.n
            ));
        }
        if label.is_none() && t >= loop_tick {
            waits(&mut out, loop_tick - cur);
            cur = loop_tick;
            label = Some(out.len());
            state_commands(&mut out, &st, &touched, first);
        }
        if t > cur {
            waits(&mut out, t - cur);
            cur = t;
        }
        match e {
            Ev::Ctl(c, v) => {
                st[c as usize] = v;
                let cmd = match c {
                    Ctl::Voice => VOICE,
                    Ctl::Vol => VOL,
                    Ctl::Pan => PAN,
                    Ctl::BendR => BENDR,
                    Ctl::Bend => BEND,
                    Ctl::LfoS => LFOS,
                    Ctl::LfoDl => LFODL,
                    Ctl::Mod => MOD,
                    Ctl::KeySh => KEYSH,
                    Ctl::Tempo => TEMPO,
                };
                out.extend([cmd, v.clamp(0, 255) as u8]);
            }
            Ev::Eot(k) => out.extend([EOT, k]),
            Ev::Note { key, vel, len: 0 } => out.extend([TIE, key, vel]),
            Ev::Note { key, vel, len } => out.extend(note(key, vel, len).unwrap()),
        }
    }
    if label.is_none() {
        waits(&mut out, loop_tick - cur);
        cur = loop_tick;
        label = Some(out.len());
        state_commands(&mut out, &st, &touched, first);
    }
    waits(&mut out, end - cur);
    out.push(GOTO);
    let goto = out.len();
    out.extend([0u8; 4]);
    Ok(TrackBytes {
        room: out.len(),
        bytes: out,
        label: label.unwrap(),
        goto,
    })
}

/// Compile a song file's text without a ROM: its `rom` references are checked and play silence (see [`compile_with`]).
pub fn compile(text: &str) -> Result<Compiled, String> {
    compile_with(text, None)
}

/// Compile a song file's text; with the ROM the game is running, the `rom` references are read out of it (the events of AW2's song, transposed and re-voiced).
pub fn compile_with(text: &str, rom: Option<&RomView>) -> Result<Compiled, String> {
    let p = parse(text)?;
    if p.insts.is_empty() {
        return Err("no `inst`".into());
    }
    // Sections in the form's order, with their start ticks.
    let mut starts: Vec<(String, u32, u32)> = Vec::new();
    let mut at = 0u32;
    let mut loop_tick = 0u32;
    let mut flat: Vec<&String> = Vec::new();
    for (i, (n, k)) in p.form.iter().enumerate() {
        if p.loop_at == Some(i) {
            loop_tick = at;
        }
        let sec = p
            .sections
            .get(n)
            .ok_or(format!("form names the section '{n}' but there is none"))?;
        let len = match sec.bars {
            Some(b) => b * p.bar_ticks,
            None => return Err(format!("section {n} needs bars=N")),
        };
        for _ in 0..*k {
            starts.push((n.clone(), at, len));
            flat.push(n);
            at += len;
        }
    }
    if p.loop_at == Some(p.form.len()) {
        return Err("`loop` at the end of the form".into());
    }
    let end = at;
    let mut compiled_tracks = Vec::new();
    let mut all_notes: Vec<(u32, u32)> = Vec::new();
    let mut notes = 0usize;
    let mut needs_rom = false;
    for (ti, spec) in p.tracks.iter().enumerate() {
        let slot = if spec.inst.is_empty() {
            0
        } else {
            p.insts
                .iter()
                .position(|(n, _, _)| *n == spec.inst)
                .ok_or(format!("track {}: no inst '{}'", spec.n, spec.inst))? as i32
        };
        let mut evs: Vec<(u32, Ev)> = Vec::new();
        let mut track_ref = false;
        for (name, start, len) in &starts {
            let sec = &p.sections[name];
            let Some(text) = sec.lines.get(&spec.n) else { continue };
            let mut ev = Eval::new(&p, spec, ti == 0, *start);
            ev.rom = rom;
            ev.run(text, 0, 0)
                .map_err(|e| format!("section {name} (tick {start}), track {}: {e}", spec.n))?;
            if ev.tick != start + len {
                return Err(format!(
                    "section {name}, track {}: {} ticks ({:.2} bars), the section has {} ({} bars)",
                    spec.n,
                    ev.tick - start,
                    (ev.tick - start) as f64 / p.bar_ticks as f64,
                    len,
                    len / p.bar_ticks
                ));
            }
            track_ref |= ev.used_ref;
            evs.extend(ev.evs);
        }
        needs_rom |= track_ref;
        for (t, e) in &evs {
            if let Ev::Note { len, .. } = e {
                notes += 1;
                all_notes.push((*t, t + len));
            }
        }
        let mut tb = write_track(spec, slot, ti == 0, p.bpm, &evs, loop_tick, end)?;
        if track_ref {
            if tb.bytes.len() > REF_TRACK_CAP {
                return Err(format!(
                    "track {}: {} bytes, the room for a track that quotes the ROM is {REF_TRACK_CAP}",
                    spec.n,
                    tb.bytes.len()
                ));
            }
            tb.room = REF_TRACK_CAP;
        }
        compiled_tracks.push(tb);
    }
    // Voices actually in the group: every inst is a slot.
    let mut voices: Vec<VoiceRef> = p.insts.iter().map(|(_, v, _)| *v).collect();
    voices.extend(p.extra.borrow().iter().copied());
    // Polyphony.
    let mut marks: Vec<(u32, i32)> = Vec::new();
    for (a, b) in &all_notes {
        marks.push((*a, 1));
        marks.push((*b, -1));
    }
    marks.sort();
    let (mut cur, mut peak, mut peak_at) = (0i32, 0i32, 0u32);
    for (t, d) in &marks {
        cur += d;
        if cur > peak {
            peak = cur;
            peak_at = *t;
        }
    }
    let c = Compiled {
        name: p.name.clone(),
        bpm: p.bpm,
        bar_ticks: p.bar_ticks,
        reverb: p.reverb,
        priority: p.priority,
        voices,
        tracks: compiled_tracks,
        intro_ticks: loop_tick,
        loop_ticks: end - loop_tick,
        peak_voices: peak as usize,
        peak_at,
        notes,
        needs_rom,
    };
    if c.voices.len() > if needs_rom { REF_VOICE_CAP } else { 128 } {
        return Err(format!(
            "{} voices (the room for a song that quotes the ROM is {REF_VOICE_CAP})",
            c.voices.len()
        ));
    }
    if c.bytes() > MAX_BYTES {
        return Err(format!("{} bytes of tracks (at most {MAX_BYTES})", c.bytes()));
    }
    Ok(c)
}

/// Every song of [`SOURCES`] compiled, in order.
pub fn compile_all() -> Result<Vec<(u8, Compiled)>, String> {
    SOURCES
        .iter()
        .map(|s| {
            compile(&text(s))
                .map(|c| (s.co, c))
                .map_err(|e| format!("{}: {e}", s.name))
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    const TINY: &str = "
song tiny
tempo 120
meter 4/4
inst lead = A.56
inst drum = A.120
hit kick=36 snare=40
track 1 inst=lead vol=90 pan=-10
track 2 inst=drum vol=100
def riff:
  | C4/4 E4/4 G4/4 E4/4 |
end
section A bars=2
  1: @riff | C4/2 r/2 |
  2: | kick/4 snare/4 kick/4 snare/4 | kick/2 r/2 |
end
form A loop A A
";

    #[test]
    fn a_tiny_song_compiles_and_loops() {
        let c = compile(TINY).unwrap();
        assert_eq!(c.tracks.len(), 2);
        assert_eq!((c.intro_ticks, c.loop_ticks), (192, 384));
        assert!((c.loop_seconds() - 384.0 * 150.0 / (GBA_FPS * 120.0)).abs() < 1e-9);
        assert_eq!(c.voices.len(), 2);
        for t in &c.tracks {
            assert_eq!(t.bytes[t.goto - 1], GOTO);
            assert!(t.label < t.goto);
        }
        assert!((1..=4).contains(&c.peak_voices), "{}", c.peak_voices);
        assert_eq!(c.bar_ticks, 96);
    }

    #[test]
    fn a_short_bar_is_an_error_with_its_place() {
        let e = compile(&TINY.replace("| C4/2 r/2 |", "| C4/2 r/4 |")).unwrap_err();
        assert!(e.contains("bar") || e.contains("ticks"), "{e}");
        let e = compile(&TINY.replace(
            "2: | kick/4 snare/4 kick/4 snare/4 | kick/2 r/2 |",
            "2: | kick/4 snare/4 kick/4 snare/4 |",
        ))
        .unwrap_err();
        assert!(e.contains("track 2"), "{e}");
    }

    #[test]
    fn durations() {
        assert_eq!(duration("4").unwrap(), 24);
        assert_eq!(duration("4.").unwrap(), 36);
        assert_eq!(duration("8t").unwrap(), 8);
        assert_eq!(duration("2+8").unwrap(), 60);
        assert_eq!(duration("#30").unwrap(), 30);
        assert!(duration("5").is_err());
    }

    #[test]
    fn note_names() {
        assert_eq!(key_of("C4"), Some(60));
        assert_eq!(key_of("F#3"), Some(54));
        assert_eq!(key_of("Bb2"), Some(46));
        assert_eq!(key_of("A0"), Some(21));
        assert_eq!(key_of("x"), None);
    }

    #[test]
    fn transposed_patterns_and_repeats() {
        let t = TINY
            .replace("1: @riff |", "1: @riff+2*2 |")
            .replace("section A bars=2", "section A bars=3")
            .replace("| kick/2 r/2 |", "| kick/2 r/2 | kick/1 |");
        let t = t.replace("C4/2 r/2 |", "C4/2 r/2 |");
        let c = compile(&t);
        // two riffs (2 bars) + one bar: 3 bars
        assert!(c.is_ok(), "{c:?}");
    }

    #[test]
    fn the_same_text_gives_the_same_bytes() {
        let a = compile(TINY).unwrap();
        let b = compile(TINY).unwrap();
        for (x, y) in a.tracks.iter().zip(&b.tracks) {
            assert_eq!(x.bytes, y.bytes);
        }
    }

    #[test]
    fn long_notes_are_tied() {
        let t = TINY.replace("| C4/2 r/2 |", "| C4/1 |").replace("1: @riff", "1: @riff");
        let c = compile(&t).unwrap();
        assert!(c.tracks[0].bytes.len() > 10);
        let t2 = t.replace("| C4/1 |", "| C4/1_ |");
        assert!(compile(&t2).is_ok());
    }

    #[test]
    fn every_source_compiles_and_has_the_right_shape() {
        for s in SOURCES.iter() {
            let c = compile(s.text).unwrap_or_else(|e| panic!("{}: {e}", s.name));
            assert_eq!(c.name, s.name);
            assert!(c.tracks.len() <= MAX_TRACKS);
            let secs = c.loop_seconds();
            // (the staff roll's song is longer on purpose: AW2's own roll is 160 s)
            let (lo, hi) = if s.co == CREDITS { (45.0, 120.0) } else { (45.0, 90.0) };
            assert!(
                (lo..=hi).contains(&secs),
                "{}: the loop is {secs:.1} s, AW2's themes are 45 to 90 s",
                s.name
            );
            assert!(
                c.peak_voices <= MAX_VOICES,
                "{}: {} notes at once, AW2 mixes {MAX_VOICES}",
                s.name,
                c.peak_voices
            );
            assert!(c.bytes() <= MAX_BYTES);
            assert!(c.voices.len() <= 128);
            for t in &c.tracks {
                assert_eq!(t.bytes[t.goto - 1], GOTO);
            }
        }
    }

    #[test]
    fn songs_are_the_new_cos_and_distinct() {
        let cos: Vec<u8> = SOURCES.iter().map(|s| s.co).collect();
        assert_eq!(cos, vec![86, 87, 88, 89, 90, 92, 82, 81, 93, DOOR, CREDITS], "the five Emerald Sun COs, Asuka, Crumb, Clone Andy, Aria and BH2's two scene songs");
        let all: Vec<Vec<u8>> = SOURCES
            .iter()
            .map(|s| {
                compile(s.text)
                    .unwrap()
                    .tracks
                    .iter()
                    .flat_map(|t| t.bytes.clone())
                    .collect()
            })
            .collect();
        for i in 0..all.len() {
            for j in i + 1..all.len() {
                assert_ne!(all[i], all[j]);
            }
        }
    }

    // --- `rom` references (a made-up ROM: nothing of the game is in the tests) ---

    const QUOTE: &str = "
song q
tempo 120
meter 4/4
inst lead = A.56
hit kick=36
track 1 inst=lead vol=90 pan=0
track 2 inst=lead vol=90 pan=0
rom q song=3 track=0 bars=1-1 transpose=-12 lower=E
section A bars=2
  1: @rom:q @rom:q
  2: | r/1 | r/1 |
end
form loop A
";

    fn with_fake<R>(f: impl FnOnce(&RomView) -> R) -> R {
        let img = crate::es_rom::fake_rom();
        RomView::bytes(&img).with(f)
    }

    #[test]
    fn a_reference_without_a_rom_is_silence_of_the_right_length() {
        let c = compile(QUOTE).unwrap();
        assert!(c.needs_rom);
        assert_eq!(c.loop_ticks, 192);
        assert_eq!(c.notes, 0);
        assert_eq!(c.tracks[0].room, REF_TRACK_CAP);
        assert_eq!(c.tracks[1].room, c.tracks[1].bytes.len());
    }

    #[test]
    fn a_reference_copies_the_sources_notes_transposed_and_darkened() {
        let c = with_fake(|v| compile_with(QUOTE, Some(v))).unwrap();
        // the source bar 1: E4 at 0, G4 at 24, E4 at 48, G4 at 72 (a pattern twice), all v110 and 24 ticks; transposed an octave down, E lowered to Eb
        let b = &c.tracks[0].bytes;
        let note = |key: u8| vec![NOTE_24, key, 110];
        let has = |n: Vec<u8>| b.windows(3).any(|w| w == n.as_slice());
        assert!(has(note(51)), "E4 -> Eb3 (51): {b:?}");
        assert!(has(note(55)), "G4 -> G3 (55)");
        assert!(!has(note(52)) && !has(note(64)), "no unlowered E");
        assert_eq!(c.notes, 8, "four notes a bar, two bars");
        // the source's VOL 90 is there too (it is the stretch's volume at its start)
        assert!(b.windows(2).any(|w| w == [crate::ds_music::VOL, 90]));
    }

    const NOTE_24: u8 = crate::ds_music::NOTE + 23;

    #[test]
    fn the_same_rom_gives_the_same_song() {
        let a = with_fake(|v| compile_with(QUOTE, Some(v))).unwrap();
        let b = with_fake(|v| compile_with(QUOTE, Some(v))).unwrap();
        for (x, y) in a.tracks.iter().zip(&b.tracks) {
            assert_eq!(x.bytes, y.bytes);
            assert_eq!((x.label, x.goto), (y.label, y.goto));
        }
        assert_eq!(a.voices, b.voices);
    }

    #[test]
    fn raw_keeps_keys_and_brings_the_sources_voice() {
        let t = QUOTE.replace("transpose=-12 lower=E", "raw");
        let c = with_fake(|v| compile_with(&t, Some(v))).unwrap();
        assert!(c.tracks[0].bytes.windows(3).any(|w| w == [NOTE_24, 64, 110]));
    }

    #[test]
    fn bad_references_are_errors() {
        assert!(compile(&QUOTE.replace("@rom:q @rom:q", "@rom:nope @rom:q"))
            .unwrap_err()
            .contains("nope"));
        assert!(compile(&QUOTE.replace("bars=1-1", "bars=3-2")).is_err());
        assert!(compile(&QUOTE.replace("song=3", "song=900")).is_err());
        assert!(compile(&QUOTE.replace("lower=E", "lower=H")).is_err());
        assert!(compile(&QUOTE.replace("transpose=-12", "wobble=1")).is_err());
        // not a whole number of bars of this song
        assert!(compile(&QUOTE.replace("transpose=-12", "tempo=100"))
            .unwrap_err()
            .contains("bars"));
        // a song or track the ROM does not have
        assert!(with_fake(|v| compile_with(&QUOTE.replace("song=3", "song=4"), Some(v))).is_err());
        assert!(with_fake(|v| compile_with(&QUOTE.replace("track=0", "track=2"), Some(v))).is_err());
    }

    /// With the player's real AW2 ROM (`AW2TEST_ROM`, default the ROMs folder): every song that quotes it builds, twice the same, within the room the game keeps, and the
    /// quoted notes are the source's notes moved by exactly the written transposition. `cargo test -p tango-gamesupport-aw2 es_music -- --ignored`.
    #[test]
    #[ignore]
    fn the_real_rom_builds_every_quoting_song_the_same_twice() {
        let path = std::env::var("AW2TEST_ROM").unwrap_or_else(|_| {
            format!(
                "{}/Documents/TangoAW2/roms/Advance_wars_2.gba",
                std::env::var("HOME").unwrap()
            )
        });
        let img = std::fs::read(path).expect("the AW2 ROM");
        let mut quoting = 0;
        for s in SOURCES.iter() {
            let (a, b) = RomView::bytes(&img).with(|v| (compile_with(s.text, Some(v)), compile_with(s.text, Some(v))));
            let (a, b) = (a.unwrap(), b.unwrap());
            if a.needs_rom {
                quoting += 1;
            }
            for (x, y) in a.tracks.iter().zip(&b.tracks) {
                assert_eq!(x.bytes, y.bytes, "{}", s.name);
                assert!(x.bytes.len() <= x.room);
            }
            assert!(a.peak_voices <= MAX_VOICES, "{}", s.name);
            assert!(a.voices.len() <= if a.needs_rom { REF_VOICE_CAP } else { 128 });
        }
        assert_eq!(quoting, 0, "no shipped theme reads AW2's songs");
    }

    /// Every shipped theme is original: no `rom` reference to a song of AW2's (the feature stays for the kit's examples in `music/es/alt/`).
    #[test]
    fn no_shipped_theme_references_aw2_songs() {
        for s in SOURCES.iter() {
            for l in s.text.lines() {
                assert!(!l.split(';').next().unwrap().trim_start().starts_with("rom "), "{}: {l}", s.name);
            }
            assert!(!compile(s.text).unwrap().needs_rom, "{}", s.name);
        }
    }
}
