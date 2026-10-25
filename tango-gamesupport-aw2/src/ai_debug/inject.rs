//! The debug channel's pad: key presses played into the session as the app's pad script does, 60 frames a second by
//! the wall clock. The app polls [`Injector::poll`] every ~16 ms and hands the word it returns to the session's normal
//! input path (`Session::set_input`), so in a netplay match a waiting seat's keys are dropped by the console's own
//! merge exactly as a person's would be: nothing here reaches around the sync.
//!
//! Ops: `press` (keys held for N frames, then six frames released so two presses never run together), `hold` (until
//! `release`), `goto` (walks the map cursor to a cell, reading the cursor from the latest state).

use std::collections::VecDeque;
use std::sync::mpsc::Sender;
use std::time::{Duration, Instant};

pub const KEYS: [(&str, u32); 10] = [
    ("A", 1),
    ("B", 1 << 1),
    ("SELECT", 1 << 2),
    ("START", 1 << 3),
    ("RIGHT", 1 << 4),
    ("LEFT", 1 << 5),
    ("UP", 1 << 6),
    ("DOWN", 1 << 7),
    ("R", 1 << 8),
    ("L", 1 << 9),
];

/// `"A"`, `"A+B"`, `"left"`: the joypad word, or the first name not understood.
pub fn parse_keys(s: &str) -> Result<u32, String> {
    let mut word = 0;
    for k in s.split('+').map(str::trim).filter(|k| !k.is_empty()) {
        match KEYS.iter().find(|(n, _)| n.eq_ignore_ascii_case(k)) {
            Some((_, b)) => word |= b,
            None => return Err(format!("unknown key `{k}` (A B SELECT START RIGHT LEFT UP DOWN R L)")),
        }
    }
    Ok(word)
}

/// What a finished op reports.
#[derive(Debug, Clone, PartialEq)]
pub enum Outcome {
    Done,
    /// A `goto` that gave up: where the cursor was.
    TimedOut(u16, u16),
}

enum Op {
    Hold { keys: u32, frames: u32 },
    Gap { frames: u32 },
    Goto { x: u16, y: u16, timeout: Duration },
}

struct Item {
    ops: VecDeque<Op>,
    done: Option<Sender<Outcome>>,
}

pub struct Injector {
    queue: VecDeque<Item>,
    /// The op at the front: frames done, and when it began.
    done: u32,
    started: Option<Instant>,
    sticky: u32,
    last: Instant,
    carry: f64,
    active: bool,
}

impl Injector {
    pub fn new(now: Instant) -> Self {
        Injector {
            queue: VecDeque::new(),
            done: 0,
            started: None,
            sticky: 0,
            last: now,
            carry: 0.0,
            active: false,
        }
    }

    /// Queues keys held for `frames`, then released for six; `done` hears when both are over.
    pub fn press(&mut self, keys: u32, frames: u32, done: Option<Sender<Outcome>>) {
        self.queue.push_back(Item {
            ops: VecDeque::from([
                Op::Hold {
                    keys,
                    frames: frames.max(1),
                },
                Op::Gap { frames: 6 },
            ]),
            done,
        });
    }

    /// Queues the cursor walk to a cell.
    pub fn goto(&mut self, x: u16, y: u16, timeout: Duration, done: Option<Sender<Outcome>>) {
        self.queue.push_back(Item {
            ops: VecDeque::from([Op::Goto { x, y, timeout }]),
            done,
        });
    }

    pub fn hold(&mut self, keys: u32) {
        self.sticky |= keys;
    }

    /// Lets go of the keys held by `hold` (all of them for `u32::MAX`), and drops what is queued.
    pub fn release(&mut self, keys: u32) {
        self.sticky &= !keys;
        if keys == u32::MAX {
            for item in self.queue.drain(..) {
                if let Some(tx) = item.done {
                    let _ = tx.send(Outcome::Done);
                }
            }
            self.done = 0;
            self.started = None;
        }
    }

    pub fn idle(&self) -> bool {
        self.queue.is_empty() && self.sticky == 0
    }

    /// The pad word for now, or `None` when the injector has nothing to say (it says a final 0 once when it falls
    /// idle, so a released key is let go). `cursor` is the map cursor's cell as of the latest state.
    pub fn poll(&mut self, now: Instant, cursor: Option<(u16, u16)>) -> Option<u32> {
        if self.idle() && !self.active {
            self.last = now;
            self.carry = 0.0;
            return None;
        }
        self.carry += now.duration_since(self.last).as_secs_f64() * 60.0;
        self.last = now;
        let mut frames = (self.carry as u32).min(30);
        self.carry -= self.carry.floor();
        let mut keys = self.sticky;
        let mut guard = 0;
        loop {
            guard += 1;
            if guard > 1000 {
                break;
            }
            let Some(item) = self.queue.front_mut() else { break };
            let Some(op) = item.ops.front() else {
                let item = self.queue.pop_front().expect("front exists");
                if let Some(tx) = item.done {
                    let _ = tx.send(Outcome::Done);
                }
                self.done = 0;
                self.started = None;
                continue;
            };
            match *op {
                Op::Hold { keys: k, frames: n } => {
                    if self.done >= n {
                        item.ops.pop_front();
                        self.done = 0;
                    } else if frames == 0 {
                        break;
                    } else {
                        keys |= k;
                        self.done += 1;
                        frames -= 1;
                    }
                }
                Op::Gap { frames: n } => {
                    if self.done >= n {
                        item.ops.pop_front();
                        self.done = 0;
                    } else if frames == 0 {
                        break;
                    } else {
                        self.done += 1;
                        frames -= 1;
                    }
                }
                Op::Goto { x, y, timeout } => {
                    let started = *self.started.get_or_insert(now);
                    match cursor {
                        Some((cx, cy)) if (cx, cy) == (x, y) => {
                            item.ops.pop_front();
                            self.done = 0;
                            self.started = None;
                        }
                        _ if now.duration_since(started) > timeout => {
                            let at = cursor.unwrap_or((0, 0));
                            let item = self.queue.pop_front().expect("front exists");
                            if let Some(tx) = item.done {
                                let _ = tx.send(Outcome::TimedOut(at.0, at.1));
                            }
                            self.done = 0;
                            self.started = None;
                        }
                        None => break,
                        Some((cx, cy)) => {
                            if frames == 0 {
                                break;
                            }
                            // (as the pad script walks: a key for 4 frames of 12, x first)
                            let k = if cx != x {
                                if cx < x {
                                    KEYS[4].1
                                } else {
                                    KEYS[5].1
                                }
                            } else if cy < y {
                                KEYS[7].1
                            } else {
                                KEYS[6].1
                            };
                            if self.done % 12 < 4 {
                                keys |= k;
                            }
                            self.done += 1;
                            frames -= 1;
                        }
                    }
                }
            }
        }
        self.active = !self.idle();
        Some(keys)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn run(inj: &mut Injector, t0: Instant, frames: u32, cursor: Option<(u16, u16)>) -> Vec<u32> {
        (1..=frames)
            .map(|f| {
                inj.poll(t0 + Duration::from_secs_f64(f as f64 / 60.0 + 0.0001), cursor)
                    .unwrap_or(u32::MAX)
            })
            .collect()
    }

    #[test]
    fn keys_parse() {
        assert_eq!(parse_keys("A").unwrap(), 1);
        assert_eq!(parse_keys("a+Left").unwrap(), 1 | 1 << 5);
        assert!(parse_keys("A+Z").is_err());
    }

    #[test]
    fn a_press_holds_for_its_frames_then_lets_go() {
        let t0 = Instant::now();
        let mut inj = Injector::new(t0);
        assert_eq!(inj.poll(t0, None), None);
        let (tx, rx) = std::sync::mpsc::channel();
        inj.press(1, 8, Some(tx));
        let words = run(&mut inj, t0, 30, None);
        assert_eq!(words.iter().take(8).filter(|&&w| w == 1).count(), 8, "{words:?}");
        assert_eq!(words[8], 0, "{words:?}");
        assert_eq!(rx.try_recv(), Ok(Outcome::Done));
        // idle again: one last 0 was said, then silence
        assert!(inj.idle());
        assert_eq!(words.iter().rev().find(|&&w| w != u32::MAX), Some(&0));
        assert_eq!(inj.poll(t0 + Duration::from_secs(2), None), None);
    }

    #[test]
    fn hold_stays_until_release() {
        let t0 = Instant::now();
        let mut inj = Injector::new(t0);
        inj.hold(1 << 4);
        assert!(run(&mut inj, t0, 10, None).iter().all(|&w| w == 1 << 4));
        inj.release(1 << 4);
        assert_eq!(inj.poll(t0 + Duration::from_secs(1), None), Some(0));
    }

    #[test]
    fn goto_walks_toward_the_cell_and_gives_up() {
        let t0 = Instant::now();
        let mut inj = Injector::new(t0);
        let (tx, rx) = std::sync::mpsc::channel();
        inj.goto(5, 1, Duration::from_secs(1), Some(tx));
        let words = run(&mut inj, t0, 20, Some((2, 1)));
        assert!(words.iter().any(|&w| w == KEYS[4].1), "{words:?}");
        assert!(words.iter().all(|&w| w & (KEYS[5].1 | KEYS[6].1 | KEYS[7].1) == 0));
        // arrives
        inj.poll(t0 + Duration::from_millis(500), Some((5, 1)));
        assert_eq!(rx.try_recv(), Ok(Outcome::Done));
        let (tx, rx) = std::sync::mpsc::channel();
        inj.goto(9, 9, Duration::from_millis(100), Some(tx));
        inj.poll(t0 + Duration::from_secs(2), Some((0, 0)));
        inj.poll(t0 + Duration::from_secs(3), Some((0, 0)));
        assert_eq!(rx.try_recv(), Ok(Outcome::TimedOut(0, 0)));
    }
}
