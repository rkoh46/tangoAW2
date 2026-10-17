//! Noticing a peer that went quiet without closing its connection (a frozen app, a sleeping laptop, a phone
//! suspended in the background). Its transport can take 100 s and more to give up on its own; this watch calls
//! the peer lost after [`SILENT_AFTER`] without a single frame from it.
//!
//! What counts as "heard from" is any frame of the in-match channel: an input, or the bare ack that the
//! retransmit heartbeat ([`tango_net::InMatchTx`]) sends every emulator frame while the emulator sends
//! nothing (a match held for someone else, a menu, a throttled sim). That heartbeat is the keepalive, and it
//! runs on the network task, never on the emulator, so a busy but live peer is never silent.

use std::time::Duration;

/// How long without a frame from the peer makes it lost (the reconnect box comes up). A hiccup of one or two
/// seconds is far below it; the keepalive arrives about sixty times a second.
pub(super) const SILENT_AFTER: Duration = Duration::from_secs(5);

/// A gap this long between two polls of the watch means this process itself was not running (suspended, or the
/// machine slept): every peer then looks silent for that long, so the watch starts its count again.
pub(super) const OWN_PAUSE: Duration = Duration::from_millis(1500);

/// After the box is up, how long the match waits for the peer's frames to come back before the transport is
/// torn down and rebuilt. A peer that was only frozen continues at once; one that slept long may need the rebuild.
pub(super) const RESUME_WINDOW: Duration = Duration::from_secs(8);

/// The poll cadence of the watch.
pub(super) const POLL: Duration = Duration::from_millis(100);

/// One link's silence timer. All times are milliseconds on the room's clock.
pub(super) struct SilenceWatch {
    silent_after_ms: u64,
    own_pause_ms: u64,
    /// The latest of "we started watching" and "we were last stopped ourselves": frames before it do not count
    /// against the peer.
    floor: u64,
    last_poll: u64,
}

impl SilenceWatch {
    pub(super) fn new(now_ms: u64) -> Self {
        Self::with(now_ms, SILENT_AFTER, OWN_PAUSE)
    }

    pub(super) fn with(now_ms: u64, silent_after: Duration, own_pause: Duration) -> Self {
        SilenceWatch {
            silent_after_ms: silent_after.as_millis() as u64,
            own_pause_ms: own_pause.as_millis() as u64,
            floor: now_ms,
            last_poll: now_ms,
        }
    }

    /// Poll at `now_ms` with the time the last frame from the peer arrived. True: the peer is lost.
    pub(super) fn lost(&mut self, now_ms: u64, last_rx_ms: u64) -> bool {
        if now_ms.saturating_sub(self.last_poll) > self.own_pause_ms {
            self.floor = now_ms;
        }
        self.last_poll = now_ms;
        let heard = last_rx_ms.max(self.floor);
        now_ms.saturating_sub(heard) >= self.silent_after_ms
    }

    /// Whether frames have come in since `since_ms` (the peer is back).
    pub(super) fn heard_since(last_rx_ms: u64, since_ms: u64) -> bool {
        last_rx_ms > since_ms
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Polls every 100 ms from `from` to `to`; the peer's last frame is `rx(t)`. First poll time that says lost.
    fn first_lost(w: &mut SilenceWatch, from: u64, to: u64, rx: impl Fn(u64) -> u64) -> Option<u64> {
        (from..=to).step_by(100).find(|&t| w.lost(t, rx(t)))
    }

    #[test]
    fn a_peer_sending_every_frame_is_never_lost() {
        let mut w = SilenceWatch::new(0);
        assert_eq!(first_lost(&mut w, 100, 60_000, |t| t), None);
    }

    #[test]
    fn a_peer_that_stops_is_lost_after_five_seconds() {
        let mut w = SilenceWatch::new(0);
        // frames until 10 s, then nothing
        let t = first_lost(&mut w, 100, 30_000, |t| t.min(10_000)).unwrap();
        assert_eq!(t, 15_000);
    }

    #[test]
    fn a_hiccup_of_one_or_two_seconds_is_not_loss() {
        for gap in [1_000u64, 2_000, 4_900] {
            let mut w = SilenceWatch::new(0);
            // frames until 10 s, a gap, frames again
            let rx = |t: u64| if t <= 10_000 { t } else if t < 10_000 + gap { 10_000 } else { t };
            assert_eq!(first_lost(&mut w, 100, 40_000, rx), None, "gap {gap}");
        }
    }

    #[test]
    fn our_own_pause_does_not_make_the_peer_silent() {
        let mut w = SilenceWatch::new(0);
        assert!(!w.lost(10_000, 10_000));
        // this process is suspended 10 s: the next poll sees a stale last frame
        assert!(!w.lost(20_000, 10_000));
        // and the peer gets the full window from there
        assert_eq!(first_lost(&mut w, 20_100, 40_000, |_| 10_000), Some(25_000));
    }

    #[test]
    fn a_peer_never_heard_is_lost_five_seconds_after_the_watch_began() {
        let mut w = SilenceWatch::new(2_000);
        assert_eq!(first_lost(&mut w, 2_100, 20_000, |_| 0), Some(7_000));
    }

    #[test]
    fn resumed_frames_are_seen() {
        assert!(!SilenceWatch::heard_since(15_000, 15_000));
        assert!(SilenceWatch::heard_since(15_001, 15_000));
    }
}
