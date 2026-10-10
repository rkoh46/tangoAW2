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
//!   the moment a session starts); other lines are ignored.

use std::path::PathBuf;
use std::time::Instant;

pub struct DebugAids {
    start: Instant,
    shots: Vec<(f64, PathBuf, bool)>,
    pub exit_after: bool,
    pad: Option<Pad>,
}

struct Pad {
    /// The joypad word of each frame.
    frames: Vec<u32>,
    session_start: Option<Instant>,
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
            let text = std::fs::read_to_string(path).ok()?;
            let mut frames = Vec::new();
            for line in text.lines() {
                let p: Vec<&str> = line.split_whitespace().collect();
                match p.as_slice() {
                    ["wait", n] => frames.extend(std::iter::repeat(0).take(n.parse().ok()?)),
                    ["press", k, n] => {
                        frames.extend(std::iter::repeat(key_bits(k)).take(n.parse().ok()?));
                        frames.extend(std::iter::repeat(0).take(6));
                    }
                    ["hold", k, n] => frames.extend(std::iter::repeat(key_bits(k)).take(n.parse().ok()?)),
                    _ => {}
                }
            }
            Some(Pad { frames, session_start: None })
        });
        DebugAids {
            start: Instant::now(),
            shots,
            exit_after: std::env::var("TANGOAW2_SCREENSHOT_EXIT").is_ok_and(|v| v == "1"),
            pad,
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

    /// The pad word for now; `None` once the script is over (or none).
    pub fn pad_keys(&mut self, session_active: bool) -> Option<u32> {
        let pad = self.pad.as_mut()?;
        if !session_active {
            pad.session_start = None;
            return None;
        }
        let t0 = *pad.session_start.get_or_insert_with(Instant::now);
        let frame = (t0.elapsed().as_secs_f64() * 60.0) as usize;
        pad.frames.get(frame).copied()
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
