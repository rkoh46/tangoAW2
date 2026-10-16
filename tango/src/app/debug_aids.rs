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
//!   `army=N`, `menu=N` (the map menu's row: 0 CO .. 4 End), `cx=N`/`cy=N` (the map cursor's cell), `maparmies=N`, `status=N`, `players=N`, `ready=N`), `seek KEYS COND` presses
//!   keys now and then until the console shows COND, `shot PATH` saves the
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
const CONDS: [&str; 19] = [
    "onmenu", "selectmode", "selectmap", "teams", "battle", "versus", "nav", "turnended", "cursor", "level", "army",
    "maparmies", "status", "players", "ready", "menu", "cx", "cy", "!",
];

fn cond_ok(c: &str) -> bool {
    let c = c.trim_start_matches('!');
    let name = c.split_once('=').map_or(c, |(n, v)| if v.parse::<u32>().is_ok() { n } else { "?" });
    CONDS.contains(&name) 
}

fn keys_ok(k: &str) -> bool {
    k.split('+').all(|k| {
        ["A", "B", "SELECT", "START", "RIGHT", "LEFT", "UP", "DOWN", "R", "L"].contains(&k.to_ascii_uppercase().as_str())
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
            ["shot", path] => ops.push(Op::Shot(PathBuf::from(path))),
            ["log", rest @ ..] => ops.push(Op::Log(rest.join(" "))),
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
                parts: match parse_script(&text) {
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
        }
    }

    pub fn has_pad(&self) -> bool {
        self.pad.is_some()
    }

    /// The next screenshot that is due, if any.
    pub fn due_shot(&mut self) -> Option<(PathBuf, bool)> {
        let now = self.start.elapsed().as_secs_f64();
        let i = self.shots.iter().position(|(t, _, done)| !*done && *t <= now)?;
        self.shots[i].2 = true;
        let last = self.shots.iter().all(|s| s.2);
        Some((self.shots[i].1.clone(), last && self.exit_after))
    }

    /// A screenshot a pad script asked for, if one is waiting.
    pub fn take_script_shot(&mut self) -> Option<PathBuf> {
        self.script_shots.pop()
    }

    /// The pad word for now; `None` once the script is over (or none). `session` is the running session's install
    /// number; `cond` answers an `until` line's condition.
    pub fn pad_keys(&mut self, session: Option<u64>, cond: &mut dyn FnMut(&str) -> bool) -> Option<u32> {
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
                Op::Shot(path) => {
                    self.script_shots.push(path.clone());
                    pad.at += 1;
                    pad.done = 0;
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
        let t = "wait 5\npress A 8\nuntil battle 90\nseek A !turnended\nuntil army=2\nshot /x.png\nsession\nlog hi\n# c\n";
        assert_eq!(parse_script(t).unwrap().len(), 2);
    }

    #[test]
    fn a_bad_line_is_an_error() {
        for t in ["wait x", "press Q 4", "until nonsense", "until army=x", "seek A battle 1 2", "frobnicate"] {
            assert!(parse_script(t).is_err(), "{t}");
        }
    }
}
