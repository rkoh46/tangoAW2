//! The last line against a black window: what the host puts on screen for a live match.
//!
//! The console draws pictures that are entirely black for a moment of its own making (a screen fading out between
//! pages, a load, a forced blank) and the pictures made for waiting seats can fail the same way. In a room a
//! player's window is never to go black while the match is live: [`BlackGuard`] keeps the last few pictures that
//! were not black and shows the best of them in place of a black one, for up to [`HOLD_TICKS`] (a third of a second, the
//! last gap of a wipe's frames): the game's own fades and wipes are shown as the game draws them, longer ones too. The
//! seats' pictures that the app makes are guarded for longer where they are made (tango-backend-mgba's `SharedSide`).

use std::collections::VecDeque;

/// How many pictures that were not black are kept.
pub const RING: usize = 3;
/// How long a black picture is replaced, in ticks (60 a second).
pub const HOLD_TICKS: u32 = 20;

/// Whether `rgba` (RGBA8, any size) is black: over 99% of the pixels above the bottom eighth (where a status bar
/// would sit) under a luma of 8.
pub fn is_black(rgba: &[u8]) -> bool {
    let top = &rgba[..rgba.len() / 8 * 7 / 4 * 4];
    if top.is_empty() {
        return false;
    }
    let dark = top
        .chunks_exact(4)
        .filter(|p| (p[0] as u32 * 30 + p[1] as u32 * 59 + p[2] as u32 * 11) / 100 < 8)
        .count();
    dark * 100 > (top.len() / 4) * 99
}

fn brightness(rgba: &[u8]) -> u64 {
    rgba.chunks_exact(4)
        .step_by(7)
        .map(|p| p[0] as u64 + p[1] as u64 + p[2] as u64)
        .sum()
}

#[derive(Default)]
pub struct BlackGuard {
    ring: VecDeque<Vec<u8>>,
    black_ticks: u32,
    held: u64,
}

impl BlackGuard {
    pub fn new() -> Self {
        Self::default()
    }

    /// The picture to present for `frame`: itself unless it is black and a better one was seen in the last
    /// [`HOLD_TICKS`] ticks of black.
    pub fn filter(&mut self, frame: Vec<u8>) -> Vec<u8> {
        if !is_black(&frame) {
            self.black_ticks = 0;
            if self.ring.len() == RING {
                self.ring.pop_front();
            }
            self.ring.push_back(frame.clone());
            return frame;
        }
        self.black_ticks = self.black_ticks.saturating_add(1);
        if self.black_ticks > HOLD_TICKS {
            return frame;
        }
        // (the brightest of the last few: the newest can be the first step of a fade)
        match self
            .ring
            .iter()
            .filter(|f| f.len() == frame.len())
            .max_by_key(|f| brightness(f))
        {
            Some(best) => {
                if self.black_ticks == 1 {
                    self.held += 1;
                    log::warn!(
                        "a black picture was held back (#{}): showing the last one that was not",
                        self.held
                    );
                }
                best.clone()
            }
            None => frame,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn flat(v: u8) -> Vec<u8> {
        std::iter::repeat([v, v, v, 255]).take(240 * 160).flatten().collect()
    }

    #[test]
    fn a_black_picture_shows_the_last_good_one() {
        let mut g = BlackGuard::new();
        assert_eq!(g.filter(flat(200)), flat(200));
        assert_eq!(g.filter(flat(0)), flat(200));
        assert_eq!(g.filter(flat(3)), flat(200));
        assert_eq!(g.filter(flat(90)), flat(90));
    }

    #[test]
    fn nothing_before_a_good_picture_and_black_after_the_hold() {
        let mut g = BlackGuard::new();
        assert_eq!(g.filter(flat(0)), flat(0));
        g.filter(flat(100));
        for _ in 0..HOLD_TICKS {
            assert_eq!(g.filter(flat(0)), flat(100));
        }
        assert_eq!(g.filter(flat(0)), flat(0));
    }

    #[test]
    fn a_status_bar_alone_does_not_make_a_picture() {
        let mut f = flat(0);
        let n = f.len();
        for b in f[n / 8 * 7..].iter_mut() {
            *b = 255;
        }
        assert!(is_black(&f));
    }
}
