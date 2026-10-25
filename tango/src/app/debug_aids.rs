//! Test aids for driving the real app without a person: screenshots of its
//! own window at set times, and a pad script played into the session. Both
//! are off unless their environment variable is set.
//!
//! - `TANGOAW2_SCREENSHOTS=<seconds>:<path>,<seconds>:<path>` saves the
//!   window's picture (read back from the GPU, so no screen-recording
//!   permission is needed) at those times after launch;
//!   `TANGOAW2_SCREENSHOT_EXIT=1` quits after the last.
//! - `TANGOAW2_PAD_SCRIPT=<file>` presses the pad as the harness's
//!   `press KEYS N` / `hold KEYS N` / `wait N` lines say (60 a second, from
//!   the moment a session starts); `until COND [SECONDS]` idles until the
//!   console shows something (`onmenu`, `selectmode`, `selectmap`, `teams`,
//!   `battle`, `versus`, `nav`, `turnended`, `!COND`, `cursor=N`, `level=N`,
//!   `myturn` (this window's seat has the turn), `banner` (NEXT TURN is up and this seat is the incoming mover: press A), `acting` (my turn, plain map, waiting for the cursor), `over` (the match is decided), `army=N`, `menu=N` (the map menu's row), `onend` (the menu's cursor is on End, whatever its row), `cx=N`/`cy=N` (the map cursor's cell; `cxlt=N`, `cxgt=N`,
//!   `cylt=N`, `cygt=N`: left of, right of, above, below it), `idle` (the map waits for the cursor, nothing running),
//!   `maparmies=N`, `status=N`, `players=N`, `ready=N`), `seek KEYS COND` presses
//!   keys now and then until the console shows COND, `label NAME` / `jumpif COND NAME` carry on at the label when COND holds, `goto X Y [SECONDS]` walks the map cursor to the cell, `shot PATH` saves the
//!   window's picture, `log TEXT` writes to the log, `session` starts the part
//!   for the next session, `#` comments out a line.

use std::path::PathBuf;
use std::time::Instant;

pub struct DebugAids {
    start: Instant,
    shots: Vec<(f64, PathBuf, bool)>,
    pub exit_after: bool,
    pad: Option<Pad>,
    /// Screenshots a pad script asked for (`shot <path>`).
    script_shots: Vec<PathBuf>,
    /// Text a pad script typed (`type TEXT`), for the in-game lobby's typing pages.
    script_typed: Vec<String>,
    /// Test run directory (`TANGOAW2_RUN_DIR`, with `TANGOAW2_RUN_SEAT` and `TANGOAW2_RUN_SHOT_HZ`): the window's
    /// picture `s<seat>_<NNNN>.png` at a steady rate, beside the game state dump (tango-gamesupport-aw2 `run_dump`).
    run: Option<RunDir>,
}

/// A test run's output directory: frames on a steady clock.
struct RunDir {
    dir: PathBuf,
    seat: u32,
    every: f64,
    next: f64,
    n: u32,
}

/// One line of a pad script.
#[derive(Clone, Debug)]
enum Op {
    /// Keys held for this many frames.
    Hold(u32, usize),
    Wait(usize),
    /// Idle until the condition holds (or this many seconds pass).
    Until(String, f64),
    Shot(PathBuf),
    Log(String),
    /// Press the keys now and then (4 frames in 12) until the condition holds (or this many seconds pass).
    Seek(u32, String, f64),
    /// `label NAME` marks a place for `jumpif`.
    Label(String),
    /// `jumpif COND NAME`: carry on at the label when the console shows COND (a waiting seat's key mashing stops the
    /// moment its wait is over).
    JumpIf(String, String),
    /// Walk the map cursor to the cell (the keys are chosen from where it is), for this many seconds at most.
    Goto(u32, u32, f64),
    /// `type TEXT`: the characters go into the in-game lobby's typing page as the keyboard's would (an underscore is a space).
    Type(String),
}

struct Pad {
    /// The script of each session.
    parts: Vec<Vec<Op>>,
    part: usize,
    /// The session being played.
    session: Option<u64>,
    /// Where the script is: the op, the frames done in it, and when the op began and the clock was last read.
    at: usize,
    done: usize,
    op_started: Instant,
    last: Instant,
    carry: f64,
    /// The keys of the last frame consumed (held while no new frame is due).
    held: u32,
}

fn key_bits(s: &str) -> u32 {
    s.split('+')
        .map(|k| match k.to_ascii_uppercase().as_str() {
            "A" => 1,
            "B" => 1 << 1,
            "SELECT" => 1 << 2,
            "START" => 1 << 3,
            "RIGHT" => 1 << 4,
            "LEFT" => 1 << 5,
            "UP" => 1 << 6,
            "DOWN" => 1 << 7,
            "R" => 1 << 8,
            "L" => 1 << 9,
            _ => 0,
        })
        .fold(0, |a, b| a | b)
}

/// The names `until` and `seek` understand (`tango_library::online::condition`).
const CONDS: [&str; 36] = [
    "always",
    "mapup",
    "mypick",
    "chosen",
    "pickturn",
    "rules",
    "onmenu",
    "selectmode",
    "selectmap",
    "teams",
    "battle",
    "versus",
    "nav",
    "turnended",
    "myturn",
    "banner",
    "acting",
    "over",
    "reconnect",
    "cursor",
    "level",
    "army",
    "maparmies",
    "status",
    "players",
    "ready",
    "menu",
    "cx",
    "cy",
    "cxlt",
    "cxgt",
    "cylt",
    "cygt",
    "idle",
    "onend",
    "!",
];

fn cond_ok(c: &str) -> bool {
    // (`a|b` holds when either does)
    c.split('|').all(|c| {
        let c = c.trim_start_matches('!');
        let name = c
            .split_once('=')
            .map_or(c, |(n, v)| if v.parse::<u32>().is_ok() { n } else { "?" });
        CONDS.contains(&name)
    })
}

/// The script's macros, expanded into plain lines: state-driven steps that wait for the game and carry on at once.
/// - `jump NAME`: carry on at the label.
/// - `onbanner`: wait (10 s) until this seat's NEXT TURN banner is up, then press A (a tap every 12 frames) until it is gone (8 s).
/// - `intro`: the battle's first pages: A (once a second) until the battle map is up, at most 15 times.
/// - `endturn`: on my turn, on the plain map: clear with B, open the map menu with A, DOWN until the cursor is on End
///   (read from the game's RAM, never counted), A, and check that the turn ended (up to 3 tries).
fn expand_macros(text: &str) -> String {
    let mut out = String::new();
    let mut n = 0u32;
    for line in text.lines() {
        match line.trim() {
            l if l.starts_with("jump ") => {
                out.push_str(&format!("jumpif always {}\n", &l[5..]));
            }
            "onbanner" => {
                out.push_str("until banner 10\nseek A !banner 8\n");
            }
            "intro" => {
                // The first turn's pages (CO pages, the DAY banner): one A at a time until the map is plain on my turn.
                n += 1;
                for _ in 0..15 {
                    out.push_str(&format!("jumpif mapup|over in{n}\npress A 8\nwait 50\n"));
                }
                out.push_str(&format!("label in{n}\n"));
            }
            "endturn" => {
                n += 1;
                out.push_str("press B 6\npress B 6\nuntil acting 10\n");
                for k in 0..3 {
                    out.push_str(&format!(
                        "until acting 4\npress A 8\nwait 20\nseek DOWN onend 6\npress A 8\nuntil !myturn 5\njumpif !myturn et{n}\npress B 6\npress B 6\npress B 6\n"
                    ));
                    let _ = k;
                }
                out.push_str(&format!("label et{n}\n"));
            }
            l => {
                out.push_str(l);
                out.push('\n');
            }
        }
    }
    out
}

fn keys_ok(k: &str) -> bool {
    k.split('+').all(|k| {
        ["A", "B", "SELECT", "START", "RIGHT", "LEFT", "UP", "DOWN", "R", "L"]
            .contains(&k.to_ascii_uppercase().as_str())
    })
}

/// A script's parts (one per session), or the first line that is not understood: a test that silently skips a line
/// tests something else, so the caller stops the script with the error.
fn parse_script(text: &str) -> Result<Vec<Vec<Op>>, String> {
    let mut parts: Vec<Vec<Op>> = vec![Vec::new()];
    for (no, line) in text.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let bad = |why: &str| Err(format!("line {}: {why}: {line:?}", no + 1));
        let p: Vec<&str> = line.split_whitespace().collect();
        if p == ["session"] {
            parts.push(Vec::new());
            continue;
        }
        let ops = parts.last_mut().unwrap();
        if matches!(p.first(), Some(&("press" | "hold" | "seek"))) && !p.get(1).is_some_and(|k| keys_ok(k)) {
            return bad("unknown key");
        }
        match p.as_slice() {
            ["wait", n] => match n.parse() {
                Ok(n) => ops.push(Op::Wait(n)),
                Err(_) => return bad("wait needs a frame count"),
            },
            ["press", k, n] => match n.parse() {
                Ok(n) => {
                    ops.push(Op::Hold(key_bits(k), n));
                    ops.push(Op::Wait(6));
                }
                Err(_) => return bad("press needs a frame count"),
            },
            ["hold", k, n] => match n.parse() {
                Ok(n) => ops.push(Op::Hold(key_bits(k), n)),
                Err(_) => return bad("hold needs a frame count"),
            },
            ["until", cond, rest @ ..] if rest.len() <= 1 && cond_ok(cond) => {
                let secs = match rest.first().map(|s| s.parse::<f64>()) {
                    None => 120.0,
                    Some(Ok(v)) => v,
                    Some(Err(_)) => return bad("until's limit is a number of seconds"),
                };
                ops.push(Op::Until(cond.to_string(), secs));
            }
            ["seek", k, cond, rest @ ..] if rest.len() <= 1 && cond_ok(cond) => {
                let secs = match rest.first().map(|s| s.parse::<f64>()) {
                    None => 60.0,
                    Some(Ok(v)) => v,
                    Some(Err(_)) => return bad("seek's limit is a number of seconds"),
                };
                ops.push(Op::Seek(key_bits(k), cond.to_string(), secs));
            }
            ["label", name] => ops.push(Op::Label(name.to_string())),
            ["jumpif", cond, name] if cond_ok(cond) => ops.push(Op::JumpIf(cond.to_string(), name.to_string())),
            ["goto", x, y, rest @ ..] if rest.len() <= 1 => {
                match (x.parse(), y.parse(), rest.first().map(|s| s.parse::<f64>())) {
                    (Ok(x), Ok(y), None) => ops.push(Op::Goto(x, y, 40.0)),
                    (Ok(x), Ok(y), Some(Ok(secs))) => ops.push(Op::Goto(x, y, secs)),
                    _ => return bad("goto needs a cell and optionally seconds"),
                }
            }
            ["shot", path] => ops.push(Op::Shot(PathBuf::from(path))),
            ["log", rest @ ..] => ops.push(Op::Log(rest.join(" "))),
            ["type", text] => ops.push(Op::Type(text.replace('_', " "))),
            _ => return bad("unknown or malformed line"),
        }
    }
    Ok(parts)
}

impl DebugAids {
    pub fn from_env() -> Self {
        let shots = std::env::var("TANGOAW2_SCREENSHOTS")
            .map(|v| {
                v.split(',')
                    .filter_map(|e| {
                        let (t, p) = e.split_once(':')?;
                        Some((t.parse::<f64>().ok()?, PathBuf::from(p), false))
                    })
                    .collect()
            })
            .unwrap_or_default();
        let pad = std::env::var("TANGOAW2_PAD_SCRIPT").ok().and_then(|path| {
            let text = std::fs::read_to_string(&path).ok()?;
            let now = Instant::now();
            Some(Pad {
                parts: match parse_script(&expand_macros(&text)) {
                    Ok(parts) => parts,
                    Err(e) => {
                        log::error!("pad script {path}: {e}: the script is not run");
                        return None;
                    }
                },
                part: 0,
                session: None,
                at: 0,
                done: 0,
                op_started: now,
                last: now,
                carry: 0.0,
                held: 0,
            })
        });
        DebugAids {
            start: Instant::now(),
            shots,
            exit_after: std::env::var("TANGOAW2_SCREENSHOT_EXIT").is_ok_and(|v| v == "1"),
            pad,
            script_shots: Vec::new(),
            script_typed: Vec::new(),
            run: Self::run_from_env(),
        }
    }

    /// `TANGOAW2_RUN_DIR=<fresh dir>` (the runner makes one per run, never reused), `TANGOAW2_RUN_SEAT=<k>`,
    /// `TANGOAW2_RUN_SHOT_HZ=<n>` (default 1): writes `meta_s<k>.json` (the build stamp and this client's start on the
    /// shared wall clock) and enables the steady frames.
    fn run_from_env() -> Option<RunDir> {
        let dir = PathBuf::from(std::env::var("TANGOAW2_RUN_DIR").ok()?);
        let seat: u32 = std::env::var("TANGOAW2_RUN_SEAT")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(0);
        let hz: f64 = std::env::var("TANGOAW2_RUN_SHOT_HZ")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(1.0);
        let _ = std::fs::create_dir_all(&dir);
        let now_ms = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_or(0, |d| d.as_millis());
        let _ = std::fs::write(
            dir.join(format!("meta_s{seat}.json")),
            format!(
                "{{\"seat\":{seat},\"build\":\"{}\",\"version\":\"{}\",\"start_ms\":{now_ms},\"shot_hz\":{hz},\"pid\":{}}}\n",
                env!("TANGOAW2_BUILD"),
                env!("CARGO_PKG_VERSION"),
                std::process::id()
            ),
        );
        Some(RunDir {
            dir,
            seat,
            every: 1.0 / hz.max(0.1),
            next: 0.0,
            n: 0,
        })
    }

    /// How often a test run's steady frames are due, when they are asked for above 1 Hz (the 1 Hz Discord tick serves the rest).
    pub fn run_shot_every(&self) -> Option<std::time::Duration> {
        self.run
            .as_ref()
            .filter(|r| r.every < 0.99)
            .map(|r| std::time::Duration::from_secs_f64(r.every / 2.0))
    }

    pub fn has_pad(&self) -> bool {
        self.pad.is_some()
    }

    /// The next screenshot that is due, if any.
    pub fn due_shot(&mut self) -> Option<(PathBuf, bool)> {
        let now = self.start.elapsed().as_secs_f64();
        if let Some(r) = self.run.as_mut() {
            if now >= r.next {
                r.next = now + r.every;
                r.n += 1;
                // (the sidecar: each picture's wall clock and the console's tick, to line the windows up)
                let ms = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .map_or(0, |d| d.as_millis());
                let name = format!("s{}_{:04}.png", r.seat, r.n);
                if let Ok(mut f) = std::fs::OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(r.dir.join(format!("shots_s{}.jsonl", r.seat)))
                {
                    use std::io::Write;
                    let _ = writeln!(
                        f,
                        "{{\"file\":\"{name}\",\"ms\":{ms},\"tick\":{}}}",
                        tango_library::online::run_ticks()
                    );
                }
                return Some((r.dir.join(name), false));
            }
        }
        let i = self.shots.iter().position(|(t, _, done)| !*done && *t <= now)?;
        self.shots[i].2 = true;
        let last = self.shots.iter().all(|s| s.2);
        Some((self.shots[i].1.clone(), last && self.exit_after))
    }

    /// Text a pad script typed, if any is waiting.
    pub fn take_script_typed(&mut self) -> Option<String> {
        self.script_typed.pop()
    }

    /// A screenshot a pad script asked for, if one is waiting.
    pub fn take_script_shot(&mut self) -> Option<PathBuf> {
        self.script_shots.pop()
    }

    /// The pad word for now; `None` once the script is over (or none). `session` is the running session's install
    /// number; `cond` answers an `until` line's condition.
    pub fn pad_keys(&mut self, session: Option<u64>, cond: &mut dyn FnMut(&str) -> bool) -> Option<u32> {
        let mut any = |c: &str| c.split('|').any(|p| p == "always" || cond(p));
        let cond: &mut dyn FnMut(&str) -> bool = &mut any;
        let pad = self.pad.as_mut()?;
        let seq = session?;
        let now = Instant::now();
        match pad.session {
            Some(s) if s == seq => {}
            prev => {
                if prev.is_some() {
                    pad.part += 1;
                }
                pad.session = Some(seq);
                pad.at = 0;
                pad.done = 0;
                pad.op_started = now;
                pad.last = now;
                pad.carry = 0.0;
            }
        }
        // The frames since the last look (60 a second); a press shorter than the gap is never lost: the keys of
        // all of them are held together.
        pad.carry += now.duration_since(pad.last).as_secs_f64() * 60.0;
        pad.last = now;
        let mut frames = (pad.carry as usize).min(30);
        let had_frames = frames > 0;
        pad.carry -= pad.carry.floor();
        let mut keys = 0;
        let mut last_frame_keys = pad.held;
        let ops = pad.parts.get(pad.part)?;
        let mut guard = 0;
        loop {
            guard += 1;
            if guard > 10_000 {
                break;
            }
            let Some(op) = ops.get(pad.at) else { break };
            match op {
                Op::Hold(k, n) => {
                    if pad.done >= *n {
                        pad.at += 1;
                        pad.done = 0;
                    } else if frames == 0 {
                        break;
                    } else {
                        keys |= k;
                        last_frame_keys = *k;
                        pad.done += 1;
                        frames -= 1;
                    }
                }
                Op::Wait(n) => {
                    if pad.done >= *n {
                        pad.at += 1;
                        pad.done = 0;
                    } else if frames == 0 {
                        break;
                    } else {
                        last_frame_keys = 0;
                        pad.done += 1;
                        frames -= 1;
                    }
                }
                Op::Until(c, secs) => {
                    if pad.done == 0 {
                        pad.op_started = now;
                        pad.done = 1;
                    }
                    if cond(c) {
                        log::info!("pad script: reached {c}");
                        pad.at += 1;
                        pad.done = 0;
                    } else if now.duration_since(pad.op_started).as_secs_f64() > *secs {
                        log::warn!("pad script: gave up waiting for {c}");
                        pad.at += 1;
                        pad.done = 0;
                    } else {
                        // (waiting: no key is held, whatever the last press left)
                        last_frame_keys = 0;
                        break;
                    }
                }
                Op::Seek(k, c, secs) => {
                    if pad.done == 0 {
                        pad.op_started = now;
                    }
                    if cond(c) {
                        log::info!("pad script: found {c}");
                        pad.at += 1;
                        pad.done = 0;
                    } else if now.duration_since(pad.op_started).as_secs_f64() > *secs {
                        log::warn!("pad script: gave up seeking {c}");
                        pad.at += 1;
                        pad.done = 0;
                    } else if frames == 0 {
                        break;
                    } else {
                        // (one frame of the 12 of a press)
                        if pad.done % 12 < 4 {
                            keys |= k;
                        }
                        last_frame_keys = if pad.done % 12 < 4 { *k } else { 0 };
                        pad.done += 1;
                        frames -= 1;
                    }
                }
                Op::Goto(x, y, secs) => {
                    if pad.done == 0 {
                        pad.op_started = now;
                    }
                    let (at_x, at_y) = (cond(&format!("cx={x}")), cond(&format!("cy={y}")));
                    if at_x && at_y {
                        log::info!("pad script: cursor at ({x},{y})");
                        pad.at += 1;
                        pad.done = 0;
                    } else if now.duration_since(pad.op_started).as_secs_f64() > *secs {
                        log::warn!("pad script: gave up walking the cursor to ({x},{y})");
                        pad.at += 1;
                        pad.done = 0;
                    } else if frames == 0 {
                        break;
                    } else {
                        let k = if !at_x {
                            if cond(&format!("cxlt={x}")) {
                                key_bits("RIGHT")
                            } else {
                                key_bits("LEFT")
                            }
                        } else if cond(&format!("cylt={y}")) {
                            key_bits("DOWN")
                        } else {
                            key_bits("UP")
                        };
                        if pad.done % 12 < 4 {
                            keys |= k;
                        }
                        last_frame_keys = if pad.done % 12 < 4 { k } else { 0 };
                        pad.done += 1;
                        frames -= 1;
                    }
                }
                Op::Shot(path) => {
                    self.script_shots.push(path.clone());
                    pad.at += 1;
                    pad.done = 0;
                }
                Op::Type(text) => {
                    self.script_typed.push(text.clone());
                    pad.at += 1;
                    pad.done = 0;
                }
                Op::Label(_) => {
                    pad.at += 1;
                    pad.done = 0;
                }
                Op::JumpIf(c, name) => {
                    pad.done = 0;
                    if cond(c) {
                        match ops.iter().position(|o| matches!(o, Op::Label(l) if l == name)) {
                            Some(i) => pad.at = i,
                            None => pad.at += 1,
                        }
                    } else {
                        pad.at += 1;
                    }
                }
                Op::Log(text) => {
                    log::info!("pad script: {text}");
                    pad.at += 1;
                    pad.done = 0;
                }
            }
        }
        // (no frame was due: the keys stay as they were, or a press would be let go and made again)
        let out = if had_frames { keys } else { pad.held };
        pad.held = last_frame_keys;
        Some(out)
    }
}

pub fn save_png(shot: &iced::window::Screenshot, path: &PathBuf) {
    let (w, h) = (shot.size.width, shot.size.height);
    if let Some(img) = image::RgbaImage::from_raw(w, h, shot.rgba.to_vec()) {
        if let Some(dir) = path.parent() {
            let _ = std::fs::create_dir_all(dir);
        }
        let _ = img.save(path);
    }
}

#[cfg(test)]
mod tests {
    use super::parse_script;

    #[test]
    fn a_good_script_parses() {
        let t =
            "wait 5\npress A 8\nuntil battle 90\nseek A !turnended\nuntil army=2\nshot /x.png\nsession\nlog hi\n# c\n";
        assert_eq!(parse_script(t).unwrap().len(), 2);
    }

    #[test]
    fn a_bad_line_is_an_error() {
        for t in [
            "wait x",
            "press Q 4",
            "until nonsense",
            "until army=x",
            "seek A battle 1 2",
            "frobnicate",
        ] {
            assert!(parse_script(t).is_err(), "{t}");
        }
    }
}
