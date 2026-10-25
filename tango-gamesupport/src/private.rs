//! The window of a seat that is choosing something in private (tangoAW2's simultaneous map picks): statics of the window's process,
//! presentation only. Nothing here is console state; the only way a private choice reaches the simulation is the words the session
//! sends in the input stream ([`next_word`], `tango_match::keys::command::pick_words`).
//!
//! - **Keys in.** The session says which keys the local seat holds ([`set_keys`], every tick it plays); the game's private view of the
//!   seat reads them ([`take_keys`]): the keys held now, and every key pressed since the last look (a tap shorter than the view's
//!   own pace is not lost).
//! - **Words out.** The game's private view queues the seat's final choice ([`queue_pick`]); the session sends its two words on the
//!   next two ticks of the seat's own input ([`next_word`]).

use std::collections::VecDeque;
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Mutex;

/// The most seats of a room.
pub const SEATS: usize = 5;

static HELD: [AtomicU32; SEATS] = [const { AtomicU32::new(0) }; SEATS];
static PRESSED: [AtomicU32; SEATS] = [const { AtomicU32::new(0) }; SEATS];
static OUT: Mutex<[VecDeque<u32>; SEATS]> = Mutex::new([const { VecDeque::new() }; SEATS]);

/// The keys the seat holds this tick (a seat of the session's: the local one).
pub fn set_keys(seat: usize, keys: u32) {
    if seat < SEATS {
        HELD[seat].store(keys, Ordering::Relaxed);
        PRESSED[seat].fetch_or(keys, Ordering::Relaxed);
    }
}

/// The keys the seat holds now and the ones pressed since the last call (taken).
pub fn take_keys(seat: usize) -> (u32, u32) {
    if seat >= SEATS {
        return (0, 0);
    }
    (
        HELD[seat].load(Ordering::Relaxed),
        PRESSED[seat].swap(0, Ordering::Relaxed),
    )
}

/// The seat's choice is made: its words go out in the seat's next two inputs.
pub fn queue_pick(seat: usize, words: [u32; 2]) {
    if seat < SEATS {
        let mut out = OUT.lock().unwrap();
        out[seat].clear();
        out[seat].extend(words);
    }
}

/// The word the seat's input is to carry this tick instead of its keys, if a choice is waiting to go out.
pub fn next_word(seat: usize) -> Option<u32> {
    if seat >= SEATS {
        return None;
    }
    OUT.lock().unwrap()[seat].pop_front()
}

/// Whether a choice is still waiting to go out.
pub fn pending(seat: usize) -> bool {
    seat < SEATS && !OUT.lock().unwrap()[seat].is_empty()
}

/// Forget everything (a new match).
pub fn reset() {
    for k in 0..SEATS {
        HELD[k].store(0, Ordering::Relaxed);
        PRESSED[k].store(0, Ordering::Relaxed);
    }
    OUT.lock().unwrap().iter_mut().for_each(VecDeque::clear);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn taps_between_two_looks_are_kept_and_a_pick_goes_out_in_two_words() {
        reset();
        set_keys(1, 0x1);
        set_keys(1, 0);
        // the key was let go before the view looked: it was pressed all the same
        assert_eq!(take_keys(1), (0, 0x1));
        assert_eq!(take_keys(1), (0, 0));
        queue_pick(1, [7, 9]);
        assert!(pending(1) && !pending(0));
        assert_eq!((next_word(1), next_word(1), next_word(1)), (Some(7), Some(9), None));
        assert_eq!(next_word(9), None);
    }
}
