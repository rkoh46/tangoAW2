//! Runtime network faults and counters for the AI debug channel (tango-gamesupport-aw2 `ai_debug`).
//!
//! Faults exist only in a process started with `TANGOAW2_AI_DEBUG_TEST=1` ([`test_mode`]): the data channels are then
//! wrapped by [`crate::impair`] even without `TANGOAW2_NET_IMPAIR`, and this block says what that wrapper does *now*:
//! extra one-way latency, jitter and loss (loss on the unreliable in-match channel only, as the env aid), a drop
//! (everything this side sends is discarded for N seconds: a dead link) or a freeze (everything is held and released
//! when the freeze ends: a stall). Nothing here is used outside test mode except two counters.

use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};
use std::sync::OnceLock;
use std::time::Instant;

static EPOCH: OnceLock<Instant> = OnceLock::new();
static LATENCY_MS: AtomicU32 = AtomicU32::new(0);
static JITTER_MS: AtomicU32 = AtomicU32::new(0);
/// Loss in hundredths of a percent.
static LOSS_X100: AtomicU32 = AtomicU32::new(0);
static DROP_UNTIL_MS: AtomicU64 = AtomicU64::new(0);
static FREEZE_UNTIL_MS: AtomicU64 = AtomicU64::new(0);
/// Whether a runtime setting has been made (it then outranks the environment's).
static OVERRIDE: AtomicU32 = AtomicU32::new(0);

/// In-match frames this side built (new inputs) and the heartbeat's re-sends of the unacked window: the loss the link is
/// working around shows as resends beyond the idle heartbeat.
pub static FRAMES_SENT: AtomicU64 = AtomicU64::new(0);
pub static RESENDS: AtomicU64 = AtomicU64::new(0);
/// Packets the faults discarded, and held.
pub static INJECTED_DROPS: AtomicU64 = AtomicU64::new(0);
pub static INJECTED_DELAYED: AtomicU64 = AtomicU64::new(0);

fn now_ms() -> u64 {
    EPOCH.get_or_init(Instant::now).elapsed().as_millis() as u64 + 1
}

/// `TANGOAW2_AI_DEBUG_TEST=1`.
pub fn test_mode() -> bool {
    static ON: OnceLock<bool> = OnceLock::new();
    *ON.get_or_init(|| std::env::var("TANGOAW2_AI_DEBUG_TEST").is_ok_and(|v| v == "1"))
}

/// What the wrapper applies now: (latency ms, jitter ms, loss %) when a runtime setting was made.
pub fn current() -> Option<(u32, u32, f32)> {
    (OVERRIDE.load(Ordering::Relaxed) != 0).then(|| {
        (LATENCY_MS.load(Ordering::Relaxed), JITTER_MS.load(Ordering::Relaxed), LOSS_X100.load(Ordering::Relaxed) as f32 / 100.0)
    })
}

pub fn set_link(latency_ms: u32, jitter_ms: u32, loss_pct: f32) {
    LATENCY_MS.store(latency_ms.min(5000), Ordering::Relaxed);
    JITTER_MS.store(jitter_ms.min(5000), Ordering::Relaxed);
    LOSS_X100.store((loss_pct.clamp(0.0, 100.0) * 100.0) as u32, Ordering::Relaxed);
    OVERRIDE.store(1, Ordering::Relaxed);
}

pub fn drop_for(secs: f64) {
    DROP_UNTIL_MS.store(now_ms() + (secs.clamp(0.0, 600.0) * 1000.0) as u64, Ordering::Relaxed);
}

pub fn freeze_for(secs: f64) {
    FREEZE_UNTIL_MS.store(now_ms() + (secs.clamp(0.0, 600.0) * 1000.0) as u64, Ordering::Relaxed);
}

/// Back to no faults.
pub fn clear() {
    for a in [&LATENCY_MS, &JITTER_MS, &LOSS_X100, &OVERRIDE] {
        a.store(0, Ordering::Relaxed);
    }
    DROP_UNTIL_MS.store(0, Ordering::Relaxed);
    FREEZE_UNTIL_MS.store(0, Ordering::Relaxed);
}

/// Whether sends are being discarded now.
pub fn dropping() -> bool {
    now_ms() < DROP_UNTIL_MS.load(Ordering::Relaxed)
}

/// How long a packet sent now is held by a freeze.
pub fn frozen_for() -> std::time::Duration {
    std::time::Duration::from_millis(FREEZE_UNTIL_MS.load(Ordering::Relaxed).saturating_sub(now_ms()))
}

/// For the `inject status` answer: (latency, jitter, loss, drop seconds left, freeze seconds left).
pub fn status() -> (u32, u32, f32, f64, f64) {
    let left = |a: &AtomicU64| a.load(Ordering::Relaxed).saturating_sub(now_ms()) as f64 / 1000.0;
    (
        LATENCY_MS.load(Ordering::Relaxed),
        JITTER_MS.load(Ordering::Relaxed),
        LOSS_X100.load(Ordering::Relaxed) as f32 / 100.0,
        left(&DROP_UNTIL_MS),
        left(&FREEZE_UNTIL_MS),
    )
}
