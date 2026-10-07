//! Frame-rate counters for diagnosing pacing: emulated frames (what the
//! drive thread steps), UI messages that carry a new frame, and redraws
//! of the session view, reported once every few seconds at info level
//! (`TANGOAW2_FPS_LOG=0` silences it). Cheap: a few relaxed atomics per
//! frame, and nothing here touches emulation state.

use std::sync::atomic::{AtomicU32, AtomicU64, Ordering::Relaxed};
use std::sync::Mutex;
use std::time::{Duration, Instant};

static EMU_FRAMES: AtomicU32 = AtomicU32::new(0);
static EMU_TICK_US: AtomicU64 = AtomicU64::new(0);
static EMU_TICK_MAX_US: AtomicU32 = AtomicU32::new(0);
static UI_UPDATES: AtomicU32 = AtomicU32::new(0);
static UI_REDRAWS: AtomicU32 = AtomicU32::new(0);
static UI_GAP_MAX_US: AtomicU32 = AtomicU32::new(0);
static LAST: Mutex<Option<(Instant, Option<Instant>)>> = Mutex::new(None);

const REPORT_EVERY: Duration = Duration::from_secs(5);

fn enabled() -> bool {
    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *ON.get_or_init(|| std::env::var("TANGOAW2_FPS_LOG").map_or(true, |v| v != "0"))
}

/// A drive thread finished stepping one emulated frame in `tick`.
pub fn emu_frame(tick: Duration) {
    EMU_FRAMES.fetch_add(1, Relaxed);
    let us = tick.as_micros().min(u32::MAX as u128) as u32;
    EMU_TICK_US.fetch_add(us as u64, Relaxed);
    EMU_TICK_MAX_US.fetch_max(us, Relaxed);
}

/// The UI took a new frame (`UpdateFramebuffer`).
pub fn ui_update() {
    UI_UPDATES.fetch_add(1, Relaxed);
}

/// The session view was redrawn.
pub fn ui_redraw() {
    if !enabled() {
        return;
    }
    UI_REDRAWS.fetch_add(1, Relaxed);
    let now = Instant::now();
    let Ok(mut last) = LAST.lock() else { return };
    let (start, prev) = last.get_or_insert((now, None));
    if let Some(prev) = *prev {
        UI_GAP_MAX_US.fetch_max(now.duration_since(prev).as_micros().min(u32::MAX as u128) as u32, Relaxed);
    }
    *prev = Some(now);
    let elapsed = now.duration_since(*start);
    if elapsed < REPORT_EVERY {
        return;
    }
    *start = now;
    let secs = elapsed.as_secs_f64();
    #[cfg(target_os = "ios")]
    {
        static LINK_TICKS: AtomicU64 = AtomicU64::new(0);
        let d = crate::platform::ios::display_report();
        let ticks = d.link_ticks.saturating_sub(LINK_TICKS.swap(d.link_ticks, Relaxed));
        log::info!(
            "display: {:.1} Hz granted (screen max {}), low power mode {}, thermal state {}",
            ticks as f64 / secs,
            d.max_fps,
            d.low_power,
            d.thermal
        );
    }
    let frames = EMU_FRAMES.swap(0, Relaxed);
    let tick_us = EMU_TICK_US.swap(0, Relaxed);
    log::info!(
        "fps: emulated {:.2}/s (step avg {:.2} ms, worst {:.2} ms) | ui frames {:.2}/s | redraws {:.2}/s (longest gap {:.1} ms)",
        frames as f64 / secs,
        if frames > 0 { tick_us as f64 / frames as f64 / 1000.0 } else { 0.0 },
        EMU_TICK_MAX_US.swap(0, Relaxed) as f64 / 1000.0,
        UI_UPDATES.swap(0, Relaxed) as f64 / secs,
        UI_REDRAWS.swap(0, Relaxed) as f64 / secs,
        UI_GAP_MAX_US.swap(0, Relaxed) as f64 / 1000.0,
    );
}
