//! Timers and task spawning, per target.
//!
//! `tokio::time` needs a runtime with a timer driver, which a browser has
//! no way to provide — reaching for one there panics on `Instant::now`
//! before it even gets to the driver, and `tokio::spawn` has nothing to
//! spawn onto. The page's own timers and microtask queue do the job
//! instead, behind the shapes this crate's loops actually use: a deadline
//! on a read, a ping cadence, and a detached task.

/// Sleep for `duration`.
#[cfg(not(target_arch = "wasm32"))]
pub(crate) async fn sleep(duration: std::time::Duration) {
    tokio::time::sleep(duration).await;
}

#[cfg(target_arch = "wasm32")]
pub(crate) async fn sleep(duration: std::time::Duration) {
    gloo_timers::future::sleep(duration).await;
}

/// A deadline passed before the future finished.
#[derive(Debug)]
pub(crate) struct Elapsed;

/// Run `future` with a deadline.
#[cfg(not(target_arch = "wasm32"))]
pub(crate) async fn timeout<F: std::future::Future>(
    duration: std::time::Duration,
    future: F,
) -> Result<F::Output, Elapsed> {
    tokio::time::timeout(duration, future).await.map_err(|_| Elapsed)
}

#[cfg(target_arch = "wasm32")]
pub(crate) async fn timeout<F: std::future::Future>(
    duration: std::time::Duration,
    future: F,
) -> Result<F::Output, Elapsed> {
    use futures_util::future::Either;
    futures_util::pin_mut!(future);
    match futures_util::future::select(future, Box::pin(sleep(duration))).await {
        Either::Left((output, _)) => Ok(output),
        Either::Right(_) => Err(Elapsed),
    }
}

/// A fixed-period tick, for the loops that ping on a cadence.
///
/// Late ticks are dropped rather than queued: a loop blocked past several
/// periods wants the next one on schedule, not a burst catching up.
pub(crate) struct Ticker {
    #[cfg(target_arch = "wasm32")]
    period: std::time::Duration,
    #[cfg(not(target_arch = "wasm32"))]
    inner: tokio::time::Interval,
}

impl Ticker {
    /// Tick every `period`, starting one period from now.
    pub(crate) fn every(period: std::time::Duration) -> Self {
        #[cfg(not(target_arch = "wasm32"))]
        {
            let mut inner = tokio::time::interval_at(tokio::time::Instant::now() + period, period);
            inner.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
            Self { inner }
        }
        #[cfg(target_arch = "wasm32")]
        Self { period }
    }

    pub(crate) async fn tick(&mut self) {
        #[cfg(not(target_arch = "wasm32"))]
        {
            self.inner.tick().await;
        }
        #[cfg(target_arch = "wasm32")]
        sleep(self.period).await;
    }
}

/// Spawn a detached task.
///
/// Natively that's the runtime's; in a browser it's the microtask queue,
/// which is why the future needn't be `Send` there.
#[cfg(not(target_arch = "wasm32"))]
pub(crate) fn spawn(future: impl std::future::Future<Output = ()> + Send + 'static) {
    tokio::spawn(future);
}

#[cfg(target_arch = "wasm32")]
pub(crate) fn spawn(future: impl std::future::Future<Output = ()> + 'static) {
    wasm_bindgen_futures::spawn_local(future);
}
