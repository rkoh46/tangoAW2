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
//! Dev aid: with `TANGOAW2_ES_MUSIC=<dir>` the songs are read from `<dir>/<name>.m4t` instead of the built-in text (so a song can be rewritten and heard
//! without a rebuild; both peers of a match must not differ, as with the other `TANGOAW2_ES_*` aids).

use std::borrow::Cow;
use std::collections::{BTreeMap, HashMap};

use crate::ds_music::{note, waits, BEND, BENDR, EOT, GOTO, KEYSH, LFODL, LFOS, MOD, PAN, TEMPO, TIE, VOICE, VOL};

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
/// The default key range of a note.
const LOW: i32 = 12;

/// A song of the Emerald Sun CO `co` (its id from [`crate::co_new`]).
#[derive(Clone, Copy)]
pub struct Source {
    pub co: u8,
    pub name: &'static str,
    pub text: &'static str,
}

pub const SOURCES: [Source; 5] = [
    Source { co: 86, name: "klaus", text: include_str!("../music/es/klaus.m4t") },
    Source { co: 87, name: "aurelia", text: include_str!("../music/es/aurelia.m4t") },
    Source { co: 88, name: "cassius", text: include_str!("../music/es/cassius.m4t") },
    Source { co: 89, name: "livia", text: include_str!("../music/es/livia.m4t") },
    Source { co: 90, name: "varro", text: include_str!("../music/es/varro.m4t") },
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
}

impl Compiled {
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
}

fn err<T>(line: usize, msg: impl std::fmt::Display) -> Result<T, String> {
    Err(format!("line {line}: {msg}"))
}

fn parse_int(s: &str, line: usize, what: &str) -> Result<i32, String> {
    let t = s.trim();
    let v = if let Some(h) = t.strip_prefix("0x") { i64::from_str_radix(h, 16).ok() } else { t.parse::<i64>().ok() };
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
                    return err(ln, "tempo must be an even number of beats a minute, 40 to 250 (the engine stores half)");
                }
            }
            "meter" => {
                let (a, b) = rest.first().and_then(|m| m.split_once('/')).ok_or(format!("line {ln}: meter wants n/d"))?;
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
                p.insts.push((name.trim().to_string(), VoiceRef { group, index: index as u8 }, shift));
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
                let mut s = TrackSpec { n, inst: String::new(), vol: 100, pan: 0, vel: 100, gate: 90, bendr: 2, modd: 0, lfos: 22, lfodl: 0, trans: 0, gain: 1.0 };
                for kv in &rest[1..] {
                    let (k, v) = kv.split_once('=').ok_or(format!("line {ln}: track options are key=value"))?;
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
                        "gain" => s.gain = v.parse::<f64>().map_err(|_| format!("line {ln}: gain: '{v}' is not a number"))?,
                        _ => return err(ln, format!("unknown track option '{k}'")),
                    }
                }
                if p.tracks.iter().any(|t| t.n == n) {
                    return err(ln, format!("track {n} twice"));
                }
                p.tracks.push(s);
            }
            "def" => {
                let name = rest.first().map(|s| s.trim_end_matches(':').to_string()).ok_or(format!("line {ln}: def NAME:"))?;
                mode = Mode::Def(name, String::new());
            }
            "section" => {
                let name = rest.first().ok_or(format!("line {ln}: section NAME [bars=N]"))?.to_string();
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
        Eval { p, track, first, evs: Vec::new(), tick: start, bar_start: start, bars: 0, vel: track.vel, gate: track.gate, dur: 24, shift }
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
                    return Err(format!("bar {} is {} ticks, a bar is {}", self.bars + 1, len, self.p.bar_ticks));
                }
                self.bars += 1;
                self.bar_start = self.tick;
            }
            return Ok(());
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
            inner.split_whitespace().map(|k| self.hit_or_pitch(k, trans)).collect::<Result<_, _>>()?
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
                let slot = self.p.insts.iter().position(|(n, _, _)| n == arg).ok_or(format!("no inst '{arg}'"))?;
                self.shift = self.p.insts[slot].2;
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
                self.evs.push((self.tick + (d as u32 * k as u32) / steps as u32, Ev::Ctl(ctl, if ctl == Ctl::Vol { scale(v) } else { (v + off).clamp(0, 127) })));
            }
        } else {
            self.evs.push((self.tick, Ev::Ctl(ctl, if ctl == Ctl::Vol { scale(num(arg)?) } else { (num(arg)? + off).clamp(0, 127) })));
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

fn write_track(spec: &TrackSpec, slot: i32, first: bool, bpm: u32, evs: &[(u32, Ev)], loop_tick: u32, end: u32) -> Result<TrackBytes, String> {
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
            return Err(format!("track {}: an event at tick {t} lies past the end ({end})", spec.n));
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
    Ok(TrackBytes { bytes: out, label: label.unwrap(), goto })
}

/// Compile a song file's text.
pub fn compile(text: &str) -> Result<Compiled, String> {
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
        let sec = p.sections.get(n).ok_or(format!("form names the section '{n}' but there is none"))?;
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
    for (ti, spec) in p.tracks.iter().enumerate() {
        let slot = if spec.inst.is_empty() {
            0
        } else {
            p.insts.iter().position(|(n, _, _)| *n == spec.inst).ok_or(format!("track {}: no inst '{}'", spec.n, spec.inst))? as i32
        };
        let mut evs: Vec<(u32, Ev)> = Vec::new();
        for (name, start, len) in &starts {
            let sec = &p.sections[name];
            let Some(text) = sec.lines.get(&spec.n) else { continue };
            let mut ev = Eval::new(&p, spec, ti == 0, *start);
            ev.run(text, 0, 0).map_err(|e| format!("section {name} (tick {start}), track {}: {e}", spec.n))?;
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
            evs.extend(ev.evs);
        }
        for (t, e) in &evs {
            if let Ev::Note { len, .. } = e {
                notes += 1;
                all_notes.push((*t, t + len));
            }
        }
        compiled_tracks.push(write_track(spec, slot, ti == 0, p.bpm, &evs, loop_tick, end)?);
    }
    // Voices actually in the group: every inst is a slot.
    let voices: Vec<VoiceRef> = p.insts.iter().map(|(_, v, _)| *v).collect();
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
    };
    if c.bytes() > MAX_BYTES {
        return Err(format!("{} bytes of tracks (at most {MAX_BYTES})", c.bytes()));
    }
    Ok(c)
}

/// Every song of [`SOURCES`] compiled, in order.
pub fn compile_all() -> Result<Vec<(u8, Compiled)>, String> {
    SOURCES.iter().map(|s| compile(&text(s)).map(|c| (s.co, c)).map_err(|e| format!("{}: {e}", s.name))).collect()
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
        let e = compile(&TINY.replace("2: | kick/4 snare/4 kick/4 snare/4 | kick/2 r/2 |", "2: | kick/4 snare/4 kick/4 snare/4 |")).unwrap_err();
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
        let t = TINY.replace("1: @riff |", "1: @riff+2*2 |").replace("section A bars=2", "section A bars=3").replace("| kick/2 r/2 |", "| kick/2 r/2 | kick/1 |");
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
            assert!((45.0..=90.0).contains(&secs), "{}: the loop is {secs:.1} s, AW2's themes are 45 to 90 s", s.name);
            assert!(c.peak_voices <= MAX_VOICES, "{}: {} notes at once, AW2 mixes {MAX_VOICES}", s.name, c.peak_voices);
            assert!(c.bytes() <= MAX_BYTES);
            assert!(c.voices.len() <= 128);
            for t in &c.tracks {
                assert_eq!(t.bytes[t.goto - 1], GOTO);
            }
        }
    }

    #[test]
    fn songs_are_the_five_new_cos_and_distinct() {
        let cos: Vec<u8> = SOURCES.iter().map(|s| s.co).collect();
        assert_eq!(cos, vec![86, 87, 88, 89, 90]);
        let all: Vec<Vec<u8>> = SOURCES.iter().map(|s| compile(s.text).unwrap().tracks.iter().flat_map(|t| t.bytes.clone()).collect()).collect();
        for i in 0..all.len() {
            for j in i + 1..all.len() {
                assert_ne!(all[i], all[j]);
            }
        }
    }
}
