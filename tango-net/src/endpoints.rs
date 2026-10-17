//! Every free public service tangoAW2's online play leans on, in one place: the lists, a live health table, polite
//! backoff, and the order to try them in.
//!
//! * **Signalling** (matchmaking): the Tango public server first. Tried in health order, 5 s each, then retried.
//! * **STUN**: libdatachannel (libjuice) uses only the *first* STUN server it is given, so the pool is probed
//!   lazily with one binding request and the best, shuffled per session, is put first.
//! * **TURN**: the Tango server hands out its own Cloudflare TURN with fresh credentials. No other TURN service is
//!   free, public and usable without an account, so none is listed; `TANGOAW2_EXTRA_TURN` adds one the player has.
//! * **Nostr relays** (lobby browser): see [`NOSTR`], [`nostr_plan`] and `tango-lobby`'s `browse`.
//!
//! **Politeness** (all numbers are here, in one place): a failure backs an endpoint off 5 s, 10 s, 20 s ... up to
//! 10 min, with +-25 % jitter; anything that says "blocked", "rate limited", "403", "429", "too many" ... backs it off
//! for 1 h to 1.5 h. Backoff is kept in the profile ([`set_state_path`]) so a restart does not retry at once.
//! Health is learned from real use; the only probes are a single STUN binding request, at most 3 per call and never
//! for an endpoint checked in the last 5 min, and none during a match.
//!
//! Test aids (env): `TANGOAW2_EXTRA_SIGNALING|STUN|TURN|NOSTR` (comma separated, appended; hidden), and
//! `TANGOAW2_BLOCK_ENDPOINTS=a,b` (any endpoint containing one of these fails at once).

use std::collections::HashMap;
use std::sync::Mutex;

/// Signalling servers, the primary first. (No other compatible public server exists: the protocol is Tango's own.)
pub const SIGNALING: &[&str] = &["wss://matchmaking.tango.n1gp.net"];

/// Public STUN servers, probed 2026-10-17 (a binding request answered by each in under 330 ms). Google's five are
/// one operator but separate addresses; Cloudflare, FreeSWITCH, Twilio (global, no account), Nextcloud, sipgate and
/// voipgate are others.
pub const STUN: &[&str] = &[
    "stun.l.google.com:19302",
    "stun1.l.google.com:19302",
    "stun2.l.google.com:19302",
    "stun3.l.google.com:19302",
    "stun4.l.google.com:19302",
    "stun.cloudflare.com:3478",
    "stun.freeswitch.org:3478",
    "global.stun.twilio.com:3478",
    "stun.nextcloud.com:3478",
    "stun.sipgate.net:3478",
    "stun.voipgate.com:3478",
];

/// Public Nostr relays that took kind 30078 with a `#t` filter and answered the question (probe 2026-10-17).
/// relay.damus.io answered "internal error"; nostr.wine, relay.nostr.band, purplepag.es and einundzwanzig refuse or
/// are unreachable, so they are not here.
pub const NOSTR: &[&str] = &[
    "wss://nos.lol",
    "wss://relay.primal.net",
    "wss://nostr.mom",
    "wss://relay.snort.social",
    "wss://nostr-pub.wellorder.net",
    "wss://nostr.oxtr.dev",
    "wss://nostr.bitcoiner.social",
    "wss://relay.coinos.io",
    "wss://offchain.pub",
    "wss://nostr.data.haus",
];

/// Most Nostr relays one client keeps a connection to (the lobby list), and most a host announces on.
pub const NOSTR_MAX_BROWSE: usize = 3;
pub const NOSTR_MAX_ANNOUNCE: usize = 3;
/// Signalling connections at a time.
pub const SIGNALING_CONNECTIONS: usize = 1;
/// How long one signalling server gets before the next is tried.
pub const SIGNALING_TIMEOUT_SECS: u64 = 5;
/// STUN: how many a session hands to ICE, how many are probed per call, how long a check stays fresh.
pub const STUN_PER_SESSION: usize = 3;
pub const STUN_PROBES_PER_CALL: usize = 3;
pub const CHECK_FRESH_SECS: u64 = 300;
/// Backoff: first step, cap, and the long block for a server's own "stop" signals.
pub const BACKOFF_FIRST_SECS: u64 = 5;
pub const BACKOFF_CAP_SECS: u64 = 600;
pub const LONG_BLOCK_SECS: u64 = 3600;
/// A host repeats its announcement every 15-20 s (a change goes out sooner but never within [`MIN_PUBLISH_GAP_SECS`]
/// of the last one): at most 12 events a minute per relay, normally 3-4.
pub const REFRESH_BASE_SECS: u64 = 15;
pub const REFRESH_JITTER_SECS: u64 = 5;
pub const MIN_PUBLISH_GAP_SECS: u64 = 5;
/// The anchor relays (see [`nostr_plan`]) change every 6 hours.
pub const ANCHOR_BUCKET_SECS: u64 = 6 * 3600;

pub fn unix_now() -> u64 {
    web_time::SystemTime::now()
        .duration_since(web_time::UNIX_EPOCH)
        .map_or(0, |d| d.as_secs())
}

/// `u` in [0, 1).
fn unit() -> f64 {
    rand::random::<f64>()
}

fn env_list(name: &str) -> Vec<String> {
    std::env::var(name)
        .unwrap_or_default()
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

/// Test aid: whether `TANGOAW2_BLOCK_ENDPOINTS` names this endpoint (it then fails as if unreachable).
pub fn test_blocked(endpoint: &str) -> bool {
    env_list("TANGOAW2_BLOCK_ENDPOINTS").iter().any(|b| endpoint.contains(b.as_str()))
}

/// The pool for a kind, then the player's extras (hidden env setting).
fn with_extra(defaults: &[&str], env: &str) -> Vec<String> {
    let mut v: Vec<String> = defaults.iter().map(|s| s.to_string()).collect();
    for e in env_list(env) {
        if !v.contains(&e) {
            v.push(e);
        }
    }
    v
}

pub fn signaling_pool(configured: &str) -> Vec<String> {
    // The player's setting (default: the Tango server) is first, then the others.
    let mut v = vec![configured.to_string()];
    for s in with_extra(SIGNALING, "TANGOAW2_EXTRA_SIGNALING") {
        if !v.contains(&s) {
            v.push(s);
        }
    }
    v
}

pub fn stun_pool() -> Vec<String> {
    with_extra(STUN, "TANGOAW2_EXTRA_STUN")
}

pub fn nostr_pool() -> Vec<String> {
    with_extra(NOSTR, "TANGOAW2_EXTRA_NOSTR")
}

// --- Backoff -----------------------------------------------------------------------------------------------------

/// Seconds to back off after the `fails`-th failure in a row (1 = first): 5, 10, 20 ... capped at 10 min, scaled by
/// 0.75 + 0.5 * `u` (`u` in [0,1)) so a crowd does not retry in step.
pub fn backoff_secs(fails: u32, u: f64) -> u64 {
    let base = BACKOFF_FIRST_SECS.saturating_mul(1u64 << fails.saturating_sub(1).min(20));
    let base = base.min(BACKOFF_CAP_SECS);
    ((base as f64) * (0.75 + 0.5 * u.clamp(0.0, 0.999))).round().max(1.0) as u64
}

/// The long block after a server's own stop signal: 1 h to 1.5 h.
pub fn long_block_secs(u: f64) -> u64 {
    (LONG_BLOCK_SECS as f64 * (1.0 + 0.5 * u.clamp(0.0, 0.999))).round() as u64
}

/// Whether a relay's or server's message is a stop signal (blocked, rate limited, forbidden, payment or login
/// needed): the endpoint is then left alone for [`LONG_BLOCK_SECS`] and more.
pub fn is_stop_signal(text: &str) -> bool {
    let w = text.to_ascii_lowercase();
    w.starts_with("rate")
        || [
            "blocked", "rate-limit", "rate limit", "ratelimit", "too many", "slow down", "429", "403", "forbidden",
            "banned", "restricted", "payment", "paid", "auth-required", "pow:", "not allowed", "quota", "486",
        ]
        .iter()
        .any(|k| w.contains(k))
}

// --- Health ------------------------------------------------------------------------------------------------------

#[derive(Clone, Debug, Default, PartialEq)]
pub struct Entry {
    /// Failures in a row.
    pub fails: u32,
    /// Unix seconds before which the endpoint is left alone.
    pub until: u64,
    /// Unix seconds of the last success or successful check (0: never).
    pub ok_at: u64,
    /// Round trip of the last good check, ms.
    pub rtt_ms: u32,
    /// Whether `until` came from a stop signal (not a plain failure).
    pub long: bool,
}

#[derive(Default)]
pub struct Health {
    map: HashMap<String, Entry>,
    dirty: bool,
}

impl Health {
    pub fn ok(&mut self, key: &str, now: u64, rtt_ms: u32) {
        let e = self.map.entry(key.to_string()).or_default();
        *e = Entry { fails: 0, until: 0, ok_at: now, rtt_ms, long: false };
        self.dirty = true;
    }

    /// A plain failure: backoff doubles. (`u` is the jitter draw.)
    pub fn fail(&mut self, key: &str, now: u64, u: f64) {
        let e = self.map.entry(key.to_string()).or_default();
        e.fails = e.fails.saturating_add(1);
        // (never shorten a long block that is running)
        let until = now + backoff_secs(e.fails, u);
        if !(e.long && e.until > until) {
            e.until = until;
            e.long = false;
        }
        self.dirty = true;
    }

    /// The server said stop: 1 h or more.
    pub fn stop(&mut self, key: &str, now: u64, u: f64) {
        let e = self.map.entry(key.to_string()).or_default();
        e.fails = e.fails.saturating_add(1);
        e.until = now + long_block_secs(u);
        e.long = true;
        self.dirty = true;
    }

    /// Fails, or stops when `why` is a stop signal.
    pub fn fail_because(&mut self, key: &str, now: u64, u: f64, why: &str) {
        if is_stop_signal(why) {
            self.stop(key, now, u)
        } else {
            self.fail(key, now, u)
        }
    }

    pub fn get(&self, key: &str) -> Option<&Entry> {
        self.map.get(key)
    }

    pub fn blocked(&self, key: &str, now: u64) -> bool {
        self.map.get(key).is_some_and(|e| e.until > now)
    }

    pub fn long_blocked(&self, key: &str, now: u64) -> bool {
        self.map.get(key).is_some_and(|e| e.until > now && e.long)
    }

    /// Seconds until the endpoint may be tried again (0: now).
    pub fn wait_for(&self, key: &str, now: u64) -> u64 {
        self.map.get(key).map_or(0, |e| e.until.saturating_sub(now))
    }

    /// Whether a check of this endpoint is stale (never done, or older than [`CHECK_FRESH_SECS`]) and allowed.
    pub fn needs_check(&self, key: &str, now: u64) -> bool {
        match self.map.get(key) {
            None => true,
            Some(e) => e.until <= now && now.saturating_sub(e.ok_at) >= CHECK_FRESH_SECS,
        }
    }

    /// Tier of an endpoint for ordering: 0 known good, 1 unknown, 2 failed but the wait is over, 3 waiting.
    fn tier(&self, key: &str, now: u64) -> u8 {
        match self.map.get(key) {
            None => 1,
            Some(e) if e.until > now => 3,
            Some(e) if e.fails > 0 => 2,
            Some(e) if e.ok_at > 0 => 0,
            Some(_) => 1,
        }
    }

    /// `pool` in the order to try: known-good first (those within twice the best round trip, at least 100 ms,
    /// shuffled, then the slower ones), then unknown ones (shuffled), then ones whose backoff has run out. Ones still
    /// backing off are left out; ones under a stop signal never come back before it ends.
    pub fn order(&self, pool: &[String], now: u64, rng: &mut impl FnMut() -> f64) -> Vec<String> {
        let mut tiers: [Vec<&String>; 3] = Default::default();
        for p in pool {
            match self.tier(p, now) {
                t @ 0..=2 => tiers[t as usize].push(p),
                _ => {}
            }
        }
        let shuffle = |v: &mut Vec<&String>, rng: &mut dyn FnMut() -> f64| {
            for i in (1..v.len()).rev() {
                let j = ((rng() * (i + 1) as f64) as usize).min(i);
                v.swap(i, j);
            }
        };
        let mut out: Vec<String> = Vec::new();
        let mut good = std::mem::take(&mut tiers[0]);
        good.sort_by_key(|k| self.map.get(k.as_str()).map_or(u32::MAX, |e| e.rtt_ms));
        let best = good.first().and_then(|k| self.map.get(k.as_str())).map_or(0, |e| e.rtt_ms);
        let cut = (best * 2).max(100);
        let (mut near, mut far): (Vec<&String>, Vec<&String>) =
            good.into_iter().partition(|k| self.map.get(k.as_str()).is_some_and(|e| e.rtt_ms <= cut));
        shuffle(&mut near, rng);
        shuffle(&mut far, rng);
        out.extend(near.into_iter().chain(far).cloned());
        for t in [1usize, 2] {
            let mut v = std::mem::take(&mut tiers[t]);
            shuffle(&mut v, rng);
            out.extend(v.into_iter().cloned());
        }
        out
    }

    // --- persistence: one line per endpoint, tab separated ---

    pub fn to_text(&self) -> String {
        let mut keys: Vec<_> = self.map.keys().collect();
        keys.sort();
        keys.iter()
            .map(|k| {
                let e = &self.map[*k];
                format!("{k}\t{}\t{}\t{}\t{}\t{}\n", e.fails, e.until, e.ok_at, e.rtt_ms, e.long as u8)
            })
            .collect()
    }

    pub fn from_text(text: &str) -> Health {
        let mut h = Health::default();
        for l in text.lines() {
            let f: Vec<&str> = l.split('\t').collect();
            if f.len() == 6 {
                if let (Ok(fails), Ok(until), Ok(ok_at), Ok(rtt_ms)) =
                    (f[1].parse(), f[2].parse(), f[3].parse(), f[4].parse())
                {
                    h.map.insert(f[0].to_string(), Entry { fails, until, ok_at, rtt_ms, long: f[5] == "1" });
                }
            }
        }
        h
    }
}

struct Global {
    health: Health,
    path: Option<std::path::PathBuf>,
    saved: u64,
    last_turn: Option<String>,
}

static GLOBAL: Mutex<Option<Global>> = Mutex::new(None);

fn with_global<R>(f: impl FnOnce(&mut Global) -> R) -> R {
    let mut g = GLOBAL.lock().unwrap_or_else(|e| e.into_inner());
    let g = g.get_or_insert_with(|| Global { health: Health::default(), path: None, saved: 0, last_turn: None });
    f(g)
}

/// Keeps the health table (and so every backoff) in this file across restarts.
pub fn set_state_path(path: std::path::PathBuf) {
    #[cfg(not(target_arch = "wasm32"))]
    {
        let text = std::fs::read_to_string(&path).unwrap_or_default();
        with_global(|g| {
            let loaded = Health::from_text(&text);
            for (k, v) in loaded.map {
                g.health.map.entry(k).or_insert(v);
            }
            g.path = Some(path);
        });
    }
    #[cfg(target_arch = "wasm32")]
    let _ = path;
}

fn maybe_save(g: &mut Global, now: u64) {
    #[cfg(not(target_arch = "wasm32"))]
    if g.health.dirty && now.saturating_sub(g.saved) >= 5 {
        g.saved = now;
        g.health.dirty = false;
        if let Some(p) = &g.path {
            if let Some(d) = p.parent() {
                let _ = std::fs::create_dir_all(d);
            }
            let _ = std::fs::write(p, g.health.to_text());
        }
    }
    #[cfg(target_arch = "wasm32")]
    let _ = (g, now);
}

/// Records a success of `key` (a signalling URL, a `host:port` STUN/TURN or a relay URL).
pub fn record_ok(key: &str, rtt_ms: u32) {
    let now = unix_now();
    with_global(|g| {
        g.health.ok(key, now, rtt_ms);
        maybe_save(g, now)
    });
}

/// Records a failure; `why` that is a stop signal blocks the endpoint for an hour or more.
pub fn record_fail(key: &str, why: &str) {
    let now = unix_now();
    with_global(|g| {
        g.health.fail_because(key, now, unit(), why);
        let e = g.health.get(key).cloned().unwrap_or_default();
        log::info!("online: {key} failed ({why}); left alone for {} s", e.until.saturating_sub(now));
        maybe_save(g, now)
    });
}

pub fn wait_for(key: &str) -> u64 {
    let now = unix_now();
    with_global(|g| g.health.wait_for(key, now))
}

pub fn blocked(key: &str) -> bool {
    wait_for(key) > 0
}

pub fn snapshot(key: &str) -> Option<Entry> {
    with_global(|g| g.health.get(key).cloned())
}

/// `pool` in the order to try, by the live health table.
pub fn order(pool: &[String]) -> Vec<String> {
    let now = unix_now();
    with_global(|g| g.health.order(pool, now, &mut unit))
}

// --- Signalling -------------------------------------------------------------------------------------------------

/// The signalling servers to try for this dial, in order: the player's own setting first while it is not backing off
/// (it is the Tango server by default), the rest by health. Servers under a stop signal are left out.
pub fn signaling_order(configured: &str) -> Vec<String> {
    let pool = signaling_pool(configured);
    let now = unix_now();
    with_global(|g| {
        let mut out: Vec<String> = Vec::new();
        if !g.health.blocked(configured, now) {
            out.push(configured.to_string());
        }
        let rest: Vec<String> = pool.iter().filter(|p| !out.contains(p)).cloned().collect();
        out.extend(g.health.order(&rest, now, &mut unit));
        // Servers that only failed (short backoff) are the last resort, the soonest-available first, while nothing else is
        // left (a person pressing "try again"); a stop signal is never overridden.
        if out.is_empty() {
            let mut left: Vec<&String> = pool.iter().filter(|p| !g.health.long_blocked(p, now)).collect();
            left.sort_by_key(|p| g.health.wait_for(p, now));
            out.extend(left.into_iter().cloned());
        }
        out
    })
}

// --- STUN and TURN ------------------------------------------------------------------------------------------------

/// `host:port` of a `stun:` / `turn:` URL (credentials, scheme and query dropped).
pub fn url_host(url: &str) -> String {
    let rest = url.split_once(':').map_or(url, |(_, r)| r);
    let rest = rest.rsplit_once('@').map_or(rest, |(_, r)| r);
    rest.split('?').next().unwrap_or(rest).to_string()
}

/// The ICE URLs to hand to WebRTC: STUN best-and-shuffled first ([`STUN_PER_SESSION`] of them), then the TURN
/// servers by health (the Tango one, then the player's own `TANGOAW2_EXTRA_TURN`). `urls` is what the signalling
/// server offered, credentials merged in as `scheme:user:pass@host`.
pub fn ice_urls(urls: Vec<String>, use_relay: Option<bool>) -> Vec<String> {
    let (mut stuns, mut turns): (Vec<String>, Vec<String>) = (vec![], vec![]);
    for u in urls {
        match u.split(':').next() {
            Some("stun") => stuns.push(u),
            Some("turn") | Some("turns") => turns.push(u),
            _ => {}
        }
    }
    let mut out = Vec::new();
    let now = unix_now();
    let mut pool: Vec<String> = stuns.iter().map(|u| url_host(u)).collect();
    for s in stun_pool() {
        if !pool.contains(&s) {
            pool.push(s);
        }
    }
    let chosen: Vec<String> = with_global(|g| {
        let pool: Vec<String> = pool.into_iter().filter(|p| !test_blocked(p)).collect();
        g.health.order(&pool, now, &mut unit)
    })
    .into_iter()
    .take(STUN_PER_SESSION)
    .collect();
    if use_relay != Some(true) {
        log::info!("online: STUN {}", chosen.join(", "));
        out.extend(chosen.iter().map(|h| format!("stun:{h}")));
    }
    if use_relay != Some(false) {
        for e in env_list("TANGOAW2_EXTRA_TURN") {
            if !turns.contains(&e) {
                turns.push(e);
            }
        }
        let hosts: Vec<String> = turns.iter().map(|u| url_host(u)).collect();
        let mut order: Vec<usize> = (0..turns.len()).collect();
        with_global(|g| {
            order.sort_by_key(|&i| g.health.tier(&hosts[i], now));
            g.last_turn = order.first().map(|&i| hosts[i].clone());
        });
        if let Some(h) = with_global(|g| g.last_turn.clone()) {
            log::info!("online: TURN {h} first of {}", turns.len());
        }
        out.extend(order.into_iter().map(|i| turns[i].clone()));
    }
    out
}

/// A connection came up: was it relayed? Credits (or blames) the TURN server that went first.
pub fn turn_outcome(relayed: bool, ok: bool) {
    let host = with_global(|g| g.last_turn.clone());
    if let Some(h) = host {
        if ok && relayed {
            record_ok(&h, 0);
        } else if !ok && relayed {
            record_fail(&h, "relayed connection failed");
        }
    }
}

/// Installs [`ice_urls`] into the signalling client (once).
pub fn install() {
    static ONCE: std::sync::Once = std::sync::Once::new();
    ONCE.call_once(|| tango_signaling::set_ice_filter(ice_urls));
}

/// One STUN binding request to `host:port`; the round trip in ms, or None.
#[cfg(not(target_arch = "wasm32"))]
pub async fn stun_probe(host_port: &str) -> Option<u32> {
    if test_blocked(host_port) {
        return None;
    }
    let started = std::time::Instant::now();
    let addr = tokio::net::lookup_host(host_port).await.ok()?.find(|a| a.is_ipv4())?;
    let sock = tokio::net::UdpSocket::bind("0.0.0.0:0").await.ok()?;
    let tid: [u8; 12] = rand::random();
    let mut req = vec![0u8, 1, 0, 0, 0x21, 0x12, 0xA4, 0x42];
    req.extend_from_slice(&tid);
    sock.send_to(&req, addr).await.ok()?;
    let mut buf = [0u8; 576];
    let r = tango_platform::timeout(std::time::Duration::from_millis(1500), async {
        loop {
            let (n, from) = sock.recv_from(&mut buf).await.ok()?;
            if from == addr && n >= 20 && buf[0] == 1 && buf[1] == 1 && buf[8..20] == tid {
                return Some(());
            }
        }
    })
    .await
    .ok()??;
    let _ = r;
    Some(started.elapsed().as_millis() as u32)
}

/// Lazily checks the STUN pool: at most [`STUN_PROBES_PER_CALL`] endpoints whose last check is older than
/// [`CHECK_FRESH_SECS`] (or never done), one binding request each, concurrently. Call before a dial and, at most
/// that often, while the ONLINE menu is open. Never during a match.
#[cfg(not(target_arch = "wasm32"))]
pub async fn check_stun() {
    let now = unix_now();
    let mut stale: Vec<String> = with_global(|g| stun_pool().into_iter().filter(|p| g.health.needs_check(p, now)).collect());
    for i in (1..stale.len()).rev() {
        let j = ((unit() * (i + 1) as f64) as usize).min(i);
        stale.swap(i, j);
    }
    stale.truncate(STUN_PROBES_PER_CALL);
    let probes = stale.into_iter().map(|h| async move {
        let r = stun_probe(&h).await;
        (h, r)
    });
    for (h, r) in futures::future::join_all(probes).await {
        match r {
            Some(ms) => record_ok(&h, ms),
            None => record_fail(&h, "no STUN answer"),
        }
    }
}

// --- Nostr --------------------------------------------------------------------------------------------------------

/// FNV-1a, stable across platforms.
fn fnv(s: &str) -> u64 {
    s.bytes().fold(0xcbf29ce484222325, |h, b| (h ^ b as u64).wrapping_mul(0x100000001b3))
}

/// The two *anchor* relays of the moment: the same for every client for 6 hours (by a hash of the relay and the time
/// bucket, among relays not backing off). A host always announces on both and a browser always listens on one of
/// them (chosen at random), so a lobby is found whatever else is down, while the load still moves from one bucket to
/// the next and splits between two relays.
pub fn anchors(pool: &[String], h: &Health, now: u64) -> Vec<String> {
    let bucket = now / ANCHOR_BUCKET_SECS;
    let mut v: Vec<&String> = pool.iter().filter(|p| !h.blocked(p, now)).collect();
    v.sort_by_key(|p| fnv(&format!("{bucket}|{p}")));
    v.into_iter().take(2).cloned().collect()
}

/// Which Nostr relays to use, in order of preference, at most `want` first. `room_code`: a host's room (its hash
/// picks one more relay deterministically from the rest, so the same room is found on the same relay by anyone who
/// knows it); a browser passes None. The anchors lead (a host both, a browser one at random), then the rest of the
/// pool by health, shuffled among the equally good. Entries beyond `want` are the spares, in order.
pub fn nostr_plan(pool: &[String], room_code: Option<&str>, h: &Health, now: u64, rng: &mut impl FnMut() -> f64) -> Vec<String> {
    let anc = anchors(pool, h, now);
    let mut plan: Vec<String> = Vec::new();
    match room_code {
        Some(_) => plan.extend(anc.iter().cloned()),
        None => {
            if !anc.is_empty() {
                plan.push(anc[((rng() * anc.len() as f64) as usize).min(anc.len() - 1)].clone());
            }
        }
    }
    let rest: Vec<String> = pool.iter().filter(|p| !plan.contains(p)).cloned().collect();
    let mut rest = h.order(&rest, now, rng);
    if let Some(code) = room_code {
        if !rest.is_empty() {
            // (the room's own relay: the hash picks among the healthy ones at the front of the list)
            let k = (fnv(&code.to_ascii_uppercase()) as usize) % rest.len().min(4);
            let r = rest.remove(k);
            plan.push(r);
        }
    }
    plan.extend(rest);
    // Relays backing off come last, as a last resort for the caller (which re-checks the table before each use).
    for p in pool {
        if !plan.contains(p) {
            plan.push(p.clone());
        }
    }
    plan
}

pub fn plan_now(pool: &[String], room_code: Option<&str>) -> Vec<String> {
    let now = unix_now();
    with_global(|g| nostr_plan(pool, room_code, &g.health, now, &mut unit))
}

/// A refresh interval for a host's announcement: 15-20 s.
pub fn refresh_interval() -> std::time::Duration {
    std::time::Duration::from_secs(REFRESH_BASE_SECS) + std::time::Duration::from_secs_f64(unit() * REFRESH_JITTER_SECS as f64)
}


// --- The Connection page ------------------------------------------------------------------------------------------

/// How the whole online side stands, for the ONLINE screen's corner and its Connection page.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Overall {
    /// Nothing checked yet.
    Checking,
    Online,
    Limited,
    Offline,
}

/// Colour class of a page line (the game paints it): good, middling, bad.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Tone {
    Good,
    Middling,
    Bad,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Summary {
    pub overall: Overall,
    /// (label, value, tone): Matchmaking, Lobby browser, Direct (STUN), Relay (TURN), Last check.
    pub lines: Vec<(String, String, Tone)>,
}

/// What a Connection page says, from the health table. `lobby_live` is (relays answering, relays in use) when the
/// lobby list is running now (the live connections are better than the table), `turn_host` the TURN server named by
/// the last signalling hello (None before any dial).
pub fn summarize(h: &Health, now: u64, signaling: &[String], lobby_live: Option<(usize, usize)>, turn_host: Option<&str>) -> Summary {
    let good = |k: &str| h.get(k).is_some_and(|e| e.fails == 0 && e.ok_at > 0);
    let bad = |k: &str| h.blocked(k, now) || h.get(k).is_some_and(|e| e.fails > 0);
    // Matchmaking
    let sig_ok = signaling.iter().find(|s| good(s));
    let (mm, mm_tone, sig_down) = if let Some(s) = sig_ok {
        let name = s.trim_start_matches("wss://").trim_start_matches("ws://");
        let name = name.split('.').find(|p| !matches!(*p, "matchmaking" | "www")).unwrap_or(name);
        let name = if name == "tango" { "Tango" } else { name };
        (format!("OK ({name})"), Tone::Good, false)
    } else if signaling.iter().any(|s| !h.long_blocked(s, now)) && signaling.iter().any(|s| bad(s)) && signaling.len() > 1 {
        ("Trying next...".to_string(), Tone::Middling, false)
    } else if signaling.iter().any(|s| bad(s)) {
        ("Unreachable".to_string(), Tone::Bad, true)
    } else {
        ("Not checked yet".to_string(), Tone::Middling, false)
    };
    // Lobby relays
    let pool = nostr_pool();
    let (n, m) = lobby_live.unwrap_or_else(|| (pool.iter().filter(|p| good(p)).count().min(NOSTR_MAX_BROWSE), NOSTR_MAX_BROWSE));
    let lobby_tone = if n >= 2 { Tone::Good } else if n == 1 { Tone::Middling } else { Tone::Bad };
    // STUN
    let stuns = stun_pool();
    let stun_ok = stuns.iter().filter(|p| good(p)).count();
    let stun_any_bad = stuns.iter().any(|p| bad(p));
    let (stun, stun_tone) = if stun_ok > 0 {
        ("OK".to_string(), Tone::Good)
    } else if stun_any_bad {
        ("Unreachable".to_string(), Tone::Bad)
    } else {
        ("Not checked yet".to_string(), Tone::Middling)
    };
    // TURN: the Tango server's own relay; unknown until a dial names it, bad when it failed or is backing off.
    let (turn, turn_tone) = match turn_host {
        Some(t) if bad(t) => ("Unavailable".to_string(), Tone::Bad),
        Some(_) => ("OK".to_string(), Tone::Good),
        None => ("OK (Tango)".to_string(), Tone::Good),
    };
    // Last check
    let last = signaling.iter().chain(stuns.iter()).chain(pool.iter()).filter_map(|k| h.get(k)).map(|e| e.ok_at).max().unwrap_or(0);
    let last_text = if last == 0 {
        "never".to_string()
    } else {
        match now.saturating_sub(last) / 60 {
            0 => "just now".to_string(),
            1 => "1 min ago".to_string(),
            k => format!("{k} min ago"),
        }
    };
    let nothing_known = sig_ok.is_none() && !sig_down && stun_ok == 0 && !stun_any_bad && lobby_live.is_none() && n == 0;
    let overall = if nothing_known {
        Overall::Checking
    } else if sig_ok.is_some() && n >= 2 {
        Overall::Online
    } else if sig_down && n == 0 && stun_ok == 0 {
        Overall::Offline
    } else if sig_ok.is_none() && n == 0 && stun_ok == 0 && stun_any_bad {
        Overall::Offline
    } else {
        Overall::Limited
    };
    Summary {
        overall,
        lines: vec![
            ("Matchmaking".into(), mm, mm_tone),
            ("Lobby browser".into(), format!("{n} of {m} OK"), lobby_tone),
            ("Direct (STUN)".into(), stun, stun_tone),
            ("Relay (TURN)".into(), turn, turn_tone),
            ("Last check".into(), last_text, Tone::Good),
        ],
    }
}

/// [`summarize`] for the live table.
pub fn summary_now(signaling_configured: &str, lobby_live: Option<(usize, usize)>) -> Summary {
    let now = unix_now();
    let pool = signaling_pool(signaling_configured);
    with_global(|g| summarize(&g.health, now, &pool, lobby_live, g.last_turn.as_deref()))
}

/// One cheap check of a signalling server: open the websocket, read its hello, close. No session is started (the
/// peer never comes). Records the result. Call at most once per [`CHECK_FRESH_SECS`] per server (see
/// [`signaling_needs_check`]) and never during a match.
#[cfg(not(target_arch = "wasm32"))]
pub async fn signaling_check(url: &str) {
    use futures::StreamExt;
    if test_blocked(url) {
        record_fail(url, "blocked by TANGOAW2_BLOCK_ENDPOINTS");
        return;
    }
    let started = std::time::Instant::now();
    let full = format!("{}/?session_id=tangoaw2-check-{:016x}&protocol_version={:x}", url.trim_end_matches('/'), rand::random::<u64>(), tango_net_protocol::PROTOCOL_VERSION);
    let r = tango_platform::timeout(std::time::Duration::from_secs(SIGNALING_TIMEOUT_SECS), async {
        let (mut ws, _) = tokio_tungstenite::connect_async(full.as_str()).await.map_err(|e| e.to_string())?;
        let first = ws.next().await;
        let _ = futures::SinkExt::close(&mut ws).await;
        match first {
            Some(Ok(_)) => Ok(()),
            Some(Err(e)) => Err(e.to_string()),
            None => Err("closed".to_string()),
        }
    })
    .await;
    match r {
        Ok(Ok(())) => record_ok(url, started.elapsed().as_millis() as u32),
        Ok(Err(e)) => record_fail(url, &e),
        Err(_) => record_fail(url, "timed out"),
    }
}

pub fn signaling_needs_check(url: &str) -> bool {
    let now = unix_now();
    with_global(|g| g.health.needs_check(url, now))
}

/// The ONLINE menu is open: one polite refresh (stale STUN probes, a signalling hello check if stale), each endpoint
/// at most once per 5 min. Fire and forget.
#[cfg(not(target_arch = "wasm32"))]
pub async fn refresh(signaling_configured: &str) {
    install();
    for url in signaling_pool(signaling_configured) {
        if signaling_needs_check(&url) && !blocked(&url) {
            signaling_check(&url).await;
        }
    }
    check_stun().await;
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pool(n: usize) -> Vec<String> {
        (0..n).map(|k| format!("r{k}")).collect()
    }
    fn seq() -> impl FnMut() -> f64 {
        let mut s = 0.137f64;
        move || {
            s = (s * 7.31 + 0.211).fract();
            s
        }
    }

    #[test]
    fn backoff_doubles_to_the_cap_with_jitter() {
        assert_eq!(backoff_secs(1, 0.5), 5);
        assert_eq!(backoff_secs(2, 0.5), 10);
        assert_eq!(backoff_secs(3, 0.5), 20);
        assert_eq!(backoff_secs(30, 0.5), 600);
        // jitter stays within +-25 % and differs between draws
        for f in 1..12 {
            let base = backoff_secs(f, 0.5) as f64;
            for u in [0.0, 0.3, 0.999] {
                let b = backoff_secs(f, u) as f64;
                assert!(b >= base * 0.74 / 1.0 - 1.0 && b <= base * 1.26 + 1.0, "{f} {u} {b}");
            }
        }
        assert!(backoff_secs(5, 0.0) < backoff_secs(5, 0.99));
        // never above cap * 1.25
        assert!(backoff_secs(40, 0.999) <= 750);
        assert!((3600..=5400).contains(&long_block_secs(0.0)) && long_block_secs(0.999) <= 5400);
    }

    #[test]
    fn stop_signals_are_recognised() {
        for s in [
            "blocked: kind 30078 is not allowed",
            "rate-limited: slow down",
            "Rate limit exceeded",
            "HTTP error: 429 Too Many Requests",
            "HTTP error: 403 Forbidden",
            "restricted: payment required",
            "auth-required: login",
            "allocation quota reached (486)",
        ] {
            assert!(is_stop_signal(s), "{s}");
        }
        for s in ["timed out", "closed", "connection reset", "error: internal error"] {
            assert!(!is_stop_signal(s), "{s}");
        }
    }

    #[test]
    fn failures_back_off_and_stop_signals_block_for_an_hour() {
        let mut h = Health::default();
        h.fail("a", 1000, 0.5);
        assert!(h.blocked("a", 1004) && !h.blocked("a", 1005));
        h.fail("a", 1005, 0.5);
        assert_eq!(h.wait_for("a", 1005), 10);
        h.fail_because("b", 1000, 0.0, "blocked: nope");
        assert!(h.long_blocked("b", 1000 + 3599));
        // a plain failure does not shorten the running long block
        h.fail("b", 1100, 0.5);
        assert!(h.long_blocked("b", 4000));
        h.ok("a", 2000, 40);
        assert!(!h.blocked("a", 2000) && h.get("a").unwrap().fails == 0);
    }

    #[test]
    fn order_prefers_healthy_skips_waiting_and_spreads() {
        let mut h = Health::default();
        let p = pool(6);
        h.ok("r0", 100, 40);
        h.ok("r1", 100, 60);
        h.ok("r2", 100, 900);
        h.fail("r3", 100, 0.5);
        h.stop("r4", 100, 0.5);
        // r5 unknown. At 101: r3 and r4 are waiting, so left out.
        let mut first = std::collections::HashSet::new();
        let mut rng = seq();
        for _ in 0..40 {
            let o = h.order(&p, 101, &mut rng);
            assert_eq!(o.len(), 4, "{o:?}");
            assert!(!o.contains(&"r3".to_string()) && !o.contains(&"r4".to_string()));
            // r2 is much slower than the rest: after the near ones; unknown r5 after every known-good one
            assert_eq!(o[2], "r2");
            assert_eq!(o[3], "r5");
            first.insert(o[0].clone());
        }
        assert_eq!(first.len(), 2, "load spreads over the near ones: {first:?}");
        // after the short backoff r3 returns (after the unknown); r4 is still blocked
        let o = h.order(&p, 200, &mut rng);
        assert_eq!(o.last().unwrap(), "r3");
        assert!(!o.contains(&"r4".to_string()));
    }

    #[test]
    fn health_survives_a_restart() {
        let mut h = Health::default();
        h.ok("wss://nos.lol", 5, 120);
        h.stop("wss://x", 10, 0.5);
        let back = Health::from_text(&h.to_text());
        assert_eq!(back.get("wss://nos.lol"), h.get("wss://nos.lol"));
        assert!(back.long_blocked("wss://x", 11));
        assert!(Health::from_text("garbage\nline").map.is_empty());
    }

    #[test]
    fn anchors_agree_between_clients_and_rotate() {
        let p: Vec<String> = NOSTR.iter().map(|s| s.to_string()).collect();
        let h = Health::default();
        let a = anchors(&p, &h, 1_000_000);
        assert_eq!(a.len(), 2);
        assert_eq!(a, anchors(&p, &Health::default(), 1_000_000 + 100));
        let mut seen = std::collections::HashSet::new();
        for b in 0..30 {
            seen.extend(anchors(&p, &h, b * ANCHOR_BUCKET_SECS));
        }
        assert!(seen.len() >= 6, "anchors rotate over the pool: {}", seen.len());
        // a relay backing off is never an anchor
        let mut h2 = Health::default();
        h2.fail(&a[0], 1_000_000, 0.5);
        assert!(!anchors(&p, &h2, 1_000_001).contains(&a[0]));
    }

    #[test]
    fn plans_cap_overlap_and_dedupe() {
        let p: Vec<String> = NOSTR.iter().map(|s| s.to_string()).collect();
        let h = Health::default();
        let now = 5_000_000;
        let anc = anchors(&p, &h, now);
        let mut rng = seq();
        for k in 0..50 {
            let host = nostr_plan(&p, Some(&format!("ROOM{k:02}")), &h, now, &mut rng);
            let browse = nostr_plan(&p, None, &h, now, &mut rng);
            // all relays appear once
            let mut s = host.clone();
            s.sort();
            s.dedup();
            assert_eq!(s.len(), p.len());
            // a host's first three include both anchors; a browser's first is an anchor: they always meet
            assert!(host[..NOSTR_MAX_ANNOUNCE].contains(&anc[0]) && host[..NOSTR_MAX_ANNOUNCE].contains(&anc[1]));
            assert!(anc.contains(&browse[0]));
            assert!(host[..NOSTR_MAX_ANNOUNCE].contains(&browse[0]));
        }
        // the room's own relay is a function of its code
        let a = nostr_plan(&p, Some("ABCDEF"), &h, now, &mut seq());
        let b = nostr_plan(&p, Some("abcdef"), &h, now, &mut seq());
        assert_eq!(a[2], b[2]);
        // the browser's first relay varies between sessions (load spreads over both anchors)
        let firsts: std::collections::HashSet<_> =
            (0..40).map(|_| nostr_plan(&p, None, &h, now, &mut rng)[0].clone()).collect();
        assert_eq!(firsts.len(), 2);
    }

    #[test]
    fn the_connection_page_follows_the_table() {
        let sig = vec!["wss://matchmaking.tango.n1gp.net".to_string()];
        let mut h = Health::default();
        let s = summarize(&h, 1000, &sig, None, None);
        assert_eq!(s.overall, Overall::Checking);
        // all good
        h.ok(&sig[0], 990, 120);
        h.ok("stun.l.google.com:19302", 990, 40);
        let s = summarize(&h, 1000, &sig, Some((3, 3)), Some("turn.cloudflare.com:3478"));
        assert_eq!(s.overall, Overall::Online);
        assert_eq!(s.lines[0].1, "OK (Tango)");
        assert_eq!(s.lines[1].1, "3 of 3 OK");
        assert_eq!(s.lines[4].1, "just now");
        // limited: one relay, TURN failed
        h.fail("turn.cloudflare.com:3478", 1000, 0.5);
        let s = summarize(&h, 1001, &sig, Some((1, 3)), Some("turn.cloudflare.com:3478"));
        assert_eq!(s.overall, Overall::Limited);
        assert_eq!(s.lines[3], ("Relay (TURN)".into(), "Unavailable".into(), Tone::Bad));
        // offline: everything failed
        let mut h = Health::default();
        h.fail(&sig[0], 1000, 0.5);
        h.fail("stun.l.google.com:19302", 1000, 0.5);
        let s = summarize(&h, 1001, &sig, Some((0, 3)), None);
        assert_eq!(s.overall, Overall::Offline);
        assert_eq!(s.lines[0].1, "Unreachable");
        // a second signalling server being tried
        let sig2 = vec![sig[0].clone(), "wss://other.example".to_string()];
        let s = summarize(&h, 1001, &sig2, Some((2, 3)), None);
        assert_eq!(s.lines[0].1, "Trying next...");
    }

    #[test]
    fn signalling_fails_over_in_order_and_honours_stops() {
        // (unique names: the table is process-wide)
        let a = "wss://fo-primary.example";
        record_fail(a, "timed out");
        let o = signaling_order(a);
        // the configured server is backing off: it is only the last resort when nothing else is left
        assert_eq!(o.first().map(String::as_str), Some(SIGNALING[0]), "{o:?}");
        let b = "wss://fo-other.example";
        record_fail(b, "HTTP error: 429 Too Many Requests");
        // a stop signal is never overridden
        assert!(!signaling_order(b).contains(&b.to_string()));
        assert!(wait_for(b) >= 3600);
        record_ok(a, 80);
        assert_eq!(signaling_order(a)[0], a);
    }

    #[test]
    fn ice_urls_put_a_few_stun_first_and_keep_the_turn() {
        let hello = vec![
            "stun:stun.cloudflare.com:3478".to_string(),
            "turn:user:pw@turn.cloudflare.com:3478?transport=udp".to_string(),
        ];
        let out = ice_urls(hello.clone(), None);
        let stuns: Vec<_> = out.iter().filter(|u| u.starts_with("stun:")).collect();
        assert!(stuns.len() == STUN_PER_SESSION, "{out:?}");
        assert!(out.iter().any(|u| u.starts_with("turn:user:pw@turn.cloudflare.com")));
        assert!(out.iter().position(|u| u.starts_with("stun:")).unwrap() < out.iter().position(|u| u.starts_with("turn:")).unwrap());
        // relay-only: no STUN; never-relay: no TURN
        assert!(ice_urls(hello.clone(), Some(true)).iter().all(|u| !u.starts_with("stun:")));
        assert!(ice_urls(hello, Some(false)).iter().all(|u| !u.starts_with("turn:")));
        // load spreads: over many sessions more than one STUN server leads
        let leads: std::collections::HashSet<_> =
            (0..60).map(|_| ice_urls(vec![], None).into_iter().next().unwrap()).collect();
        assert!(leads.len() > 1, "{leads:?}");
    }

    #[test]
    fn urls_of_a_stun_or_turn_server() {
        assert_eq!(url_host("stun:stun.cloudflare.com:3478"), "stun.cloudflare.com:3478");
        assert_eq!(url_host("turn:user:pw@turn.cloudflare.com:3478?transport=udp"), "turn.cloudflare.com:3478");
    }
}
