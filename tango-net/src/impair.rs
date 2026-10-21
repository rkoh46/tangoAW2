//! A debug aid: `TANGOAW2_NET_IMPAIR=latency_ms,jitter_ms,loss_pct` delays (and, on the unreliable in-match
//! channel only, drops) what this side sends over the data channels, to test netplay on a bad network without
//! root (`dnctl`/`pfctl`). The delay is one way, so with the variable set on both peers the round trip is twice
//! `latency_ms`. Off unless the variable is set; nothing here is used in a release player's session.
//!
//! Order: the reliable control channel keeps its order (a delayed packet holds the ones behind it, as a real
//! network does); the in-match channel reorders freely with the jitter, as UDP does.

use super::PacketSink;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Impairment {
    pub latency_ms: u32,
    pub jitter_ms: u32,
    pub loss_pct: f32,
}

impl Impairment {
    pub fn parse(s: &str) -> Option<Self> {
        let mut it = s.split(',').map(|p| p.trim());
        let latency_ms = it.next()?.parse().ok()?;
        let jitter_ms = it.next().map_or(Some(0), |p| p.parse().ok())?;
        let loss_pct: f32 = it.next().map_or(Some(0.0), |p| p.parse().ok())?;
        Some(Self {
            latency_ms,
            jitter_ms,
            loss_pct: loss_pct.clamp(0.0, 100.0),
        })
    }

    /// The setting of this process (`TANGOAW2_NET_IMPAIR`), read once.
    pub fn from_env() -> Option<Self> {
        static CELL: std::sync::OnceLock<Option<Impairment>> = std::sync::OnceLock::new();
        *CELL.get_or_init(|| {
            let v = std::env::var("TANGOAW2_NET_IMPAIR").ok()?;
            let i = Self::parse(&v);
            match i {
                Some(i) => log::warn!("net: TANGOAW2_NET_IMPAIR active: {i:?} (debug aid)"),
                None => log::warn!("net: TANGOAW2_NET_IMPAIR={v:?} ignored (want latency_ms,jitter_ms,loss_pct)"),
            }
            i
        })
    }
}

/// xorshift64*, enough for a test aid.
struct Rng(u64);

impl Rng {
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 >> 12;
        self.0 ^= self.0 << 25;
        self.0 ^= self.0 >> 27;
        self.0.wrapping_mul(0x2545F4914F6CDD1D)
    }
    fn below(&mut self, n: u64) -> u64 {
        if n == 0 {
            0
        } else {
            self.next() % n
        }
    }
}

struct Impaired {
    inner: Arc<tokio::sync::Mutex<Box<dyn PacketSink>>>,
    cfg: Impairment,
    reliable: bool,
    rng: Mutex<Rng>,
    /// Reliable: the latest release time handed out, so packets leave in order.
    last_due: Mutex<Instant>,
}

/// Wrap `sink` in the impairment, if the environment asks for one.
pub fn wrap(sink: Box<dyn PacketSink>, reliable: bool) -> Box<dyn PacketSink> {
    let test = super::netdbg::test_mode();
    let cfg = match Impairment::from_env() {
        Some(c) => c,
        None if test => Impairment { latency_ms: 0, jitter_ms: 0, loss_pct: 0.0 },
        None => return sink,
    };
    if !test && cfg.latency_ms == 0 && cfg.jitter_ms == 0 && cfg.loss_pct == 0.0 {
        return sink;
    }
    let seed = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(1, |d| d.as_nanos() as u64)
        | 1;
    Box::new(Impaired {
        inner: Arc::new(tokio::sync::Mutex::new(sink)),
        cfg,
        reliable,
        rng: Mutex::new(Rng(seed)),
        last_due: Mutex::new(Instant::now()),
    })
}

#[async_trait::async_trait]
impl PacketSink for Impaired {
    async fn send(&mut self, bytes: &[u8]) -> std::io::Result<()> {
        // (the AI debug channel's runtime faults, in test mode only: a runtime setting outranks the environment's)
        let test = super::netdbg::test_mode();
        if test && super::netdbg::dropping() {
            super::netdbg::INJECTED_DROPS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            return Ok(());
        }
        let cfg = if test {
            super::netdbg::current().map_or(self.cfg, |(latency_ms, jitter_ms, loss_pct)| Impairment { latency_ms, jitter_ms, loss_pct })
        } else {
            self.cfg
        };
        let (lost, delay) = {
            let mut rng = self.rng.lock().unwrap();
            let lost = !self.reliable && (rng.below(10_000) as f32) < cfg.loss_pct * 100.0;
            let jitter = rng.below(cfg.jitter_ms as u64 + 1);
            (lost, Duration::from_millis(cfg.latency_ms as u64 + jitter))
        };
        if lost {
            super::netdbg::INJECTED_DROPS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            return Ok(());
        }
        let mut due = Instant::now() + delay;
        if test {
            let held = super::netdbg::frozen_for();
            if !held.is_zero() {
                super::netdbg::INJECTED_DELAYED.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                due = due.max(Instant::now() + held);
            }
        }
        if self.reliable {
            let mut last = self.last_due.lock().unwrap();
            due = due.max(*last + Duration::from_millis(1));
            *last = due;
        }
        let inner = self.inner.clone();
        let bytes = bytes.to_vec();
        // (a task a packet; the reliable channel's release times are a millisecond apart at least, so they keep
        // their order)
        tokio::spawn(async move {
            let wait = due.saturating_duration_since(Instant::now());
            if !wait.is_zero() {
                tokio::time::sleep(wait).await;
            }
            if let Err(e) = inner.lock().await.send(&bytes).await {
                log::debug!("net impair: send failed: {e}");
            }
        });
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses() {
        assert_eq!(
            Impairment::parse("80,20,5"),
            Some(Impairment {
                latency_ms: 80,
                jitter_ms: 20,
                loss_pct: 5.0
            })
        );
        assert_eq!(Impairment::parse("40").map(|i| (i.jitter_ms, i.loss_pct)), Some((0, 0.0)));
        assert_eq!(Impairment::parse("x"), None);
    }
}
