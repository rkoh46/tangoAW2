//! tangoAW2's public lobby list: every room is announced, and anyone on the same version can list the rooms.
//!
//! There is no server of ours. A room's host announces it on public Nostr relays (websocket servers that store and
//! forward small signed events, run by third parties) and a player who opens the lobby browser asks the same relays
//! for the announcements. A matchmaking pool pairs two clients and cannot list anything; a relay keeps what it is
//! told, which is what a list needs.
//!
//! **The announcement** is one *parameterized replaceable* event (kind [`KIND`], 30078, "application specific
//! data"), `d` = the room's code, `t` = [`TAG`], with a NIP-40 `expiration` a few seconds after a few refreshes.
//! It is signed by a throw-away key made when the host app starts (nobody can be told from it) and replaced every
//! [`REFRESH`] (15 s) by a new one with the same `d`: the relay keeps just the latest. Its content is [`Lobby`] as JSON:
//! code, host gamertag, players and seats, whether there is a password, the game version and whether the content
//! pack is on. **Never an address**: the connection is still made through the matchmaking server, in the session
//! `tangoaw2-room-<code>` ([`crate::room::room_session`]). A lobby that starts or closes is replaced by an event with
//! `{"x":1}` as its content; one that just disappears (a crash) is gone [`TTL`] after its last refresh.
//!
//! **The list** ([`Browse`]) subscribes to the `t` tag with `since` a few minutes back on every relay at once, keeps the
//! newest event of each (author, code), drops those older than [`TTL`] and the closed ones, and shows only the lobbies
//! of this game version and the same pack setting ([`Compat`]); everything a relay sends is verified (id and
//! signature) and checked ([`Lobby::decode`]) before it is believed, since anybody can write to a public relay. Any
//! relay that fails is retried; the list works as long as one answers.
//!
//! Relays see the IP address of whoever connects to them, as any server does; nothing else of the player.

use futures::{SinkExt, StreamExt};
use k256::schnorr::{Signature, SigningKey, VerifyingKey};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio_tungstenite::tungstenite::Message;
use tokio_util::sync::CancellationToken;

/// The `t` tag of every tangoAW2 lobby announcement (its `-v1` is this format).
pub const TAG: &str = "tangoaw2-lobby-v1";
/// Nostr kind 30078: parameterized replaceable, application specific data.
pub const KIND: u64 = 30078;
/// The public relay pool (see [`tango_net::endpoints::NOSTR`] for how each was verified). One client uses at most
/// [`MAX_BROWSE`] / [`MAX_ANNOUNCE`] of them at a time, picked by [`tango_net::endpoints::nostr_plan`]: two
/// time-bucketed *anchor* relays that a host always announces on and a browser always has one of (so they meet),
/// then the healthiest of the rest, shuffled; a relay that fails or says stop is swapped for the next.
pub const RELAYS: &[&str] = tango_net::endpoints::NOSTR;
pub const MAX_BROWSE: usize = tango_net::endpoints::NOSTR_MAX_BROWSE;
pub const MAX_ANNOUNCE: usize = tango_net::endpoints::NOSTR_MAX_ANNOUNCE;
/// How often a host repeats its announcement.
pub const REFRESH: Duration = Duration::from_secs(15);
/// An announcement older than this is a lobby that is gone (four refreshes missed; a closing event removes a lobby at
/// once, so this only waits for a host that vanished).
pub const TTL: u64 = 60;
/// Most lobbies kept and shown.
pub const MAX_LISTED: usize = 9;
const CONNECT_TIMEOUT: Duration = Duration::from_secs(8);

/// What is announced of a lobby.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Lobby {
    /// The room's code ([`crate::room::room_session`] makes the matchmaking session of it).
    pub code: String,
    /// The host's gamertag.
    pub host: String,
    /// The room's name (the host's choice). An announcement of a host that has none (a 0.8.4 one) is listed by the host's gamertag.
    pub name: String,
    /// Players in the room now, host included, and the most it holds.
    pub players: u8,
    pub max: u8,
    /// A password is needed (it is never announced).
    pub locked: bool,
    /// The game's version string and whether the content pack is on: only equal ones are listed to each other.
    pub version: String,
    pub pack: bool,
}

/// A lobby as listed: who announced it and when.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Listing {
    pub lobby: Lobby,
    pub author: String,
    pub created_at: u64,
}

/// What a listing must match to be shown.
#[derive(Clone, Debug)]
pub struct Compat {
    pub version: String,
    pub pack: bool,
}

/// Text from the public channel made safe to draw: printable ASCII, runs of spaces made one, none at either end, at most `max`
/// characters.
pub fn clean_text(s: &str, max: usize) -> String {
    let mut out = String::new();
    for c in s.chars().filter(|c| c.is_ascii() && !c.is_ascii_control()) {
        if c == ' ' && (out.is_empty() || out.ends_with(' ')) {
            continue;
        }
        out.push(c);
    }
    out.chars().take(max).collect::<String>().trim_end().to_string()
}

/// What a lobby's code may be made of.
fn code_ok(c: &str) -> bool {
    c.len() == 6 && c.bytes().all(|b| b.is_ascii_alphanumeric())
}

impl Lobby {
    /// The event's content.
    pub fn encode(&self) -> String {
        json!({
            "c": self.code,
            "h": self.host,
            "r": self.name,
            "n": self.players,
            "m": self.max,
            "l": self.locked,
            "v": self.version,
            "p": self.pack,
        })
        .to_string()
    }

    /// The lobby an event's content describes, if it is one that makes sense (a closed one is `Ok(None)`). Anything
    /// off is `Err`: the channel is public, so every field is checked and the gamertag is made safe to draw.
    pub fn decode(content: &str) -> Result<Option<Lobby>, &'static str> {
        let v: Value = serde_json::from_str(content).map_err(|_| "not json")?;
        if v.get("x").is_some() {
            return Ok(None);
        }
        let s = |k: &str| v.get(k).and_then(Value::as_str);
        let n = |k: &str| v.get(k).and_then(Value::as_u64);
        let code = s("c").ok_or("no code")?.to_ascii_uppercase();
        if !code_ok(&code) {
            return Err("bad code");
        }
        let host = clean_text(s("h").ok_or("no host")?, 12);
        // (an announcement without a name, or with one that is nothing, is listed by its host's gamertag)
        let name = s("r").map(|r| clean_text(r, 18)).filter(|r| !r.is_empty());
        let (players, max) = (n("n").ok_or("no players")?, n("m").ok_or("no max")?);
        if !(2..=5).contains(&max) || players < 1 || players > max {
            return Err("bad counts");
        }
        let version = s("v").ok_or("no version")?;
        if version.is_empty() || version.len() > 24 || !version.bytes().all(|b| b.is_ascii_graphic()) {
            return Err("bad version");
        }
        let host = if host.is_empty() { "Player".to_string() } else { host };
        Ok(Some(Lobby {
            code,
            name: name.unwrap_or_else(|| host.clone()),
            host,
            players: players as u8,
            max: max as u8,
            locked: v.get("l").and_then(Value::as_bool).unwrap_or(false),
            version: version.to_string(),
            pack: v.get("p").and_then(Value::as_bool).unwrap_or(false),
        }))
    }

    /// Whether `compat` players can play in this lobby.
    pub fn fits(&self, compat: &Compat) -> bool {
        self.version == compat.version && self.pack == compat.pack
    }
}

// --- Nostr events ---------------------------------------------------------------------------------------------

fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}

fn unhex(s: &str) -> Option<Vec<u8>> {
    if s.len() % 2 != 0 || !s.is_ascii() {
        return None;
    }
    (0..s.len() / 2)
        .map(|k| u8::from_str_radix(&s[2 * k..2 * k + 2], 16).ok())
        .collect()
}

fn event_id(pubkey: &str, created_at: u64, kind: u64, tags: &Value, content: &str) -> [u8; 32] {
    let s = json!([0, pubkey, created_at, kind, tags, content]).to_string();
    Sha256::digest(s.as_bytes()).into()
}

/// A signed announcement event (`lobby` None is the closing one).
pub fn make_event(key: &SigningKey, code: &str, lobby: Option<&Lobby>, created_at: u64) -> Value {
    let pubkey = hex(&key.verifying_key().to_bytes());
    let content = lobby.map_or_else(|| json!({"x": 1}).to_string(), |l| l.encode());
    // (gone a little after a few refreshes would have been; a closing event only has to outlive being read)
    let expiry = created_at + if lobby.is_some() { TTL + 30 } else { 120 };
    let tags = json!([
        ["d", code.to_ascii_uppercase()],
        ["t", TAG],
        ["expiration", expiry.to_string()]
    ]);
    let id = event_id(&pubkey, created_at, KIND, &tags, &content);
    let sig = key
        .sign_raw(&id, &rand::random::<[u8; 32]>())
        .map(|s| hex(&s.to_bytes()))
        .unwrap_or_default();
    json!({"id": hex(&id), "pubkey": pubkey, "created_at": created_at, "kind": KIND, "tags": tags, "content": content, "sig": sig})
}

/// An event from a relay: its id and signature checked, and what it announces (None: a lobby closed). `Err` is
/// anything that is not a tangoAW2 announcement or is not genuine.
pub fn read_event(ev: &Value) -> Result<(String, String, u64, Option<Lobby>), &'static str> {
    let text = |k: &str| ev.get(k).and_then(Value::as_str).ok_or("field");
    let (id, pubkey, content, sig) = (text("id")?, text("pubkey")?, text("content")?, text("sig")?);
    let created_at = ev.get("created_at").and_then(Value::as_u64).ok_or("field")?;
    if ev.get("kind").and_then(Value::as_u64) != Some(KIND) {
        return Err("kind");
    }
    let tags = ev.get("tags").ok_or("field")?;
    let tag = |name: &str| {
        tags.as_array()?
            .iter()
            .find(|t| t.get(0).and_then(Value::as_str) == Some(name))
            .and_then(|t| t.get(1))
            .and_then(Value::as_str)
    };
    if tag("t") != Some(TAG) {
        return Err("tag");
    }
    let d = tag("d").ok_or("no d")?.to_ascii_uppercase();
    if !code_ok(&d) {
        return Err("bad d");
    }
    let want = event_id(pubkey, created_at, KIND, tags, content);
    if unhex(id).as_deref() != Some(&want[..]) {
        return Err("id");
    }
    let vk = VerifyingKey::from_bytes(&unhex(pubkey).ok_or("pubkey")?).map_err(|_| "pubkey")?;
    let sig = Signature::try_from(unhex(sig).ok_or("sig")?.as_slice()).map_err(|_| "sig")?;
    vk.verify_raw(&want, &sig).map_err(|_| "signature")?;
    let lobby = Lobby::decode(content)?;
    if lobby.as_ref().is_some_and(|l| l.code != d) {
        return Err("d differs from the code");
    }
    Ok((pubkey.to_string(), d, created_at, lobby))
}

fn now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| d.as_secs())
}

fn new_key() -> SigningKey {
    loop {
        if let Ok(k) = SigningKey::from_bytes(&rand::random::<[u8; 32]>()) {
            return k;
        }
    }
}

// --- The list ---------------------------------------------------------------------------------------------------

/// What the events heard so far say, newest per (author, code).
#[derive(Default)]
struct Heard {
    latest: HashMap<(String, String), (u64, Option<Lobby>)>,
}

impl Heard {
    fn hear(&mut self, author: String, code: String, created_at: u64, lobby: Option<Lobby>) {
        let e = self.latest.entry((author, code)).or_insert((0, None));
        if created_at >= e.0 && (created_at > e.0 || lobby.is_none()) {
            *e = (created_at, lobby);
        }
    }

    /// How many lobbies are open `at` but not shown because they are of another version or pack.
    fn hidden(&self, at: u64, compat: &Compat) -> usize {
        self.latest
            .values()
            .filter(|(created_at, l)| l.as_ref().is_some_and(|l| !l.fits(compat)) && *created_at + TTL >= at)
            .count()
    }

    /// The lobbies that are open `at` unix time and fit `compat`, newest first, one per code.
    fn listings(&self, at: u64, compat: &Compat) -> Vec<Listing> {
        let mut by_code: HashMap<&str, Listing> = HashMap::new();
        for ((author, code), (created_at, lobby)) in &self.latest {
            let Some(l) = lobby else { continue };
            // (a clock a minute ahead is not believed either)
            if *created_at + TTL < at || *created_at > at + 60 || !l.fits(compat) {
                continue;
            }
            let item = Listing {
                lobby: l.clone(),
                author: author.clone(),
                created_at: *created_at,
            };
            match by_code.get(code.as_str()) {
                Some(old) if old.created_at >= *created_at => {}
                _ => {
                    by_code.insert(code, item);
                }
            }
        }
        let mut v: Vec<Listing> = by_code.into_values().collect();
        v.sort_by(|a, b| b.created_at.cmp(&a.created_at).then(a.lobby.code.cmp(&b.lobby.code)));
        v.truncate(MAX_LISTED);
        v
    }
}

/// How the relays are doing.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct RelayStats {
    /// Relays in use (an announcer's spare ones are not, until needed).
    pub relays: usize,
    /// Connected now.
    pub connected: usize,
    /// Relays that have answered the question (browser: sent the end of the stored events) or accepted an
    /// announcement lately (announcer).
    pub answered: usize,
    /// Announcements heard (browser) or accepted (announcer), in all.
    pub events: usize,
}

/// What one relay is doing, for the log and the stats.
#[derive(Default)]
struct Relay {
    url: String,
    connected: AtomicBool,
    /// Browser: when the relay ended the stored events (EOSE) on this connection. Announcer: when it last accepted
    /// something. (Seconds on [`mono`]; 0: never.)
    answered: AtomicU64,
    events: AtomicUsize,
    /// Whether the task of this relay runs (the announcer keeps spare relays idle until needed).
    active: AtomicBool,
    /// Failures in a row on this run (2 gets the relay swapped for a spare).
    fails: std::sync::atomic::AtomicU32,
    /// Cancels this relay's own task (the swap), apart from the whole lookup's token.
    stop: Mutex<Option<CancellationToken>>,
    note: Mutex<String>,
}

impl Relay {
    fn new(url: &str) -> Arc<Relay> {
        Arc::new(Relay {
            url: url.to_string(),
            ..Default::default()
        })
    }

    /// This relay's task failed (never answered, or was told to stop).
    fn failed(&self, why: &str) {
        let n = if tango_net::endpoints::is_stop_signal(why) {
            2
        } else {
            1
        };
        self.fails.fetch_add(n, Ordering::Relaxed);
        tango_net::endpoints::record_fail(&self.url, why);
    }

    fn succeeded(&self, ms: u32) {
        self.fails.store(0, Ordering::Relaxed);
        tango_net::endpoints::record_ok(&self.url, ms);
    }

    fn note(&self, s: impl Into<String>) {
        *self.note.lock().unwrap() = s.into();
    }
}

/// Seconds since the first call, plus one (so 0 can mean never).
fn mono() -> u64 {
    static T0: std::sync::OnceLock<std::time::Instant> = std::sync::OnceLock::new();
    T0.get_or_init(std::time::Instant::now).elapsed().as_secs() + 1
}

/// How long an acceptance by a relay counts as healthy.
const HEALTHY_FOR: u64 = 40;

fn stats_of(relays: &[Arc<Relay>], announcer: bool) -> RelayStats {
    let t = mono();
    let mut s = RelayStats::default();
    for r in relays.iter().filter(|r| r.active.load(Ordering::Relaxed)) {
        s.relays += 1;
        s.connected += r.connected.load(Ordering::Relaxed) as usize;
        s.events += r.events.load(Ordering::Relaxed);
        let a = r.answered.load(Ordering::Relaxed);
        s.answered += (a != 0 && (!announcer || t.saturating_sub(a) <= HEALTHY_FOR)) as usize;
    }
    s
}

fn describe(relays: &[Arc<Relay>]) -> String {
    let t = mono();
    relays
        .iter()
        .map(|r| {
            let a = r.answered.load(Ordering::Relaxed);
            let state = if !r.active.load(Ordering::Relaxed) {
                "spare"
            } else if r.connected.load(Ordering::Relaxed) {
                "up"
            } else {
                "down"
            };
            let ok = if a != 0 {
                format!("/answered {}s ago", t.saturating_sub(a))
            } else {
                String::new()
            };
            let note = r.note.lock().unwrap().clone();
            let note = if note.is_empty() {
                String::new()
            } else {
                format!(" ({note})")
            };
            format!(
                "{}={state}{ok} ev{}{note}",
                r.url.trim_start_matches("wss://"),
                r.events.load(Ordering::Relaxed)
            )
        })
        .collect::<Vec<_>>()
        .join(", ")
}

/// Logs every relay's state now and then until `cancel` fires.
fn spawn_status_log(what: &'static str, relays: Vec<Arc<Relay>>, cancel: CancellationToken) {
    tokio::spawn(async move {
        while nap(&cancel, Duration::from_secs(20)).await {
            log::info!("lobby {what}: relays: {}", describe(&relays));
        }
    });
}

/// Keeps at most `max` relays of `infos` (best first) running: starts the first usable ones, and every few seconds
/// swaps a relay that has failed twice (or been told to stop) for the next unused one. Never more than `max` at once.
fn keep_running(
    infos: Vec<Arc<Relay>>,
    max: usize,
    cancel: CancellationToken,
    begin: Arc<dyn Fn(&Arc<Relay>, CancellationToken) + Send + Sync>,
    replan: Arc<dyn Fn() -> Vec<String> + Send + Sync>,
) {
    let start = {
        let begin = begin.clone();
        let cancel = cancel.clone();
        move |r: &Arc<Relay>| {
            let t = cancel.child_token();
            *r.stop.lock().unwrap() = Some(t.clone());
            r.active.store(true, Ordering::Relaxed);
            begin(r, t);
        }
    };
    let usable = |r: &Arc<Relay>| {
        !r.active.load(Ordering::Relaxed)
            && r.fails.load(Ordering::Relaxed) == 0
            && !tango_net::endpoints::blocked(&r.url)
    };
    // The relays to start now, in the plan's order as it stands (a relay found dead changes the anchors, so the plan
    // is made again at each swap: clients that saw the same relay fail converge on the same anchors).
    let next = {
        let infos = infos.clone();
        move |n: usize| -> Vec<Arc<Relay>> {
            replan()
                .iter()
                .filter_map(|u| infos.iter().find(|r| &r.url == u))
                .filter(|r| usable(r))
                .take(n)
                .cloned()
                .collect()
        }
    };
    for r in next(max) {
        start(&r);
    }
    tokio::spawn(async move {
        while nap(&cancel, Duration::from_secs(6)).await {
            for r in infos
                .iter()
                .filter(|r| r.active.load(Ordering::Relaxed) && r.fails.load(Ordering::Relaxed) >= 2)
            {
                log::info!("lobby: {} keeps failing; swapped for a spare", r.url);
                if let Some(t) = r.stop.lock().unwrap().take() {
                    t.cancel();
                }
                r.active.store(false, Ordering::Relaxed);
                r.connected.store(false, Ordering::Relaxed);
            }
            let active = infos.iter().filter(|r| r.active.load(Ordering::Relaxed)).count();
            for r in next(max.saturating_sub(active)) {
                log::info!("lobby: adding spare relay {}", r.url);
                start(&r);
            }
        }
    });
}

/// A running look at the public lobby list: dropping it stops.
pub struct Browse {
    heard: Arc<Mutex<Heard>>,
    compat: Compat,
    relays: Vec<Arc<Relay>>,
    /// When a relay last answered (the list stays as it was through a stretch with none: a hiccup is not "no
    /// lobbies").
    healthy_at: Mutex<std::time::Instant>,
    cancel: CancellationToken,
}

/// How long the last list is kept as it was when no relay answers.
const HICCUP: u64 = 60;

impl Browse {
    /// Starts looking on up to [`MAX_BROWSE`] of the pool `relays` (must run inside the tokio runtime).
    pub fn start(relays: &[&str], compat: Compat) -> Browse {
        let heard = Arc::new(Mutex::new(Heard::default()));
        let cancel = CancellationToken::new();
        let pool: Vec<String> = relays.iter().map(|s| s.to_string()).collect();
        let plan = tango_net::endpoints::plan_now(&pool, None);
        log::info!(
            "online: lobby list plan {}",
            plan.iter().take(MAX_BROWSE).cloned().collect::<Vec<_>>().join(", ")
        );
        let infos: Vec<Arc<Relay>> = plan.iter().map(|u| Relay::new(u)).collect();
        let begin: Arc<dyn Fn(&Arc<Relay>, CancellationToken) + Send + Sync> = {
            let heard = heard.clone();
            Arc::new(move |r: &Arc<Relay>, t: CancellationToken| {
                let (r, heard) = (r.clone(), heard.clone());
                tokio::spawn(async move { browse_relay(r, heard, t).await });
            })
        };
        let replan: Arc<dyn Fn() -> Vec<String> + Send + Sync> =
            Arc::new(move || tango_net::endpoints::plan_now(&pool, None));
        keep_running(infos.clone(), MAX_BROWSE, cancel.clone(), begin, replan);
        spawn_status_log("list", infos.clone(), cancel.clone());
        Browse {
            heard,
            compat,
            relays: infos,
            healthy_at: Mutex::new(std::time::Instant::now()),
            cancel,
        }
    }

    /// The open lobbies of this version, newest first.
    pub fn listings(&self) -> Vec<Listing> {
        // A stretch with no relay answering stops the clock of the list (for at most [`HICCUP`]).
        let mut at = now();
        {
            let mut h = self.healthy_at.lock().unwrap();
            if self.stats().answered > 0 {
                *h = std::time::Instant::now();
            } else {
                at = at.saturating_sub(h.elapsed().as_secs().min(HICCUP));
            }
        }
        self.heard.lock().unwrap().listings(at, &self.compat)
    }

    /// How many lobbies are heard but hidden because they are of another version or pack.
    pub fn hidden(&self) -> usize {
        self.heard.lock().unwrap().hidden(now(), &self.compat)
    }

    pub fn stats(&self) -> RelayStats {
        stats_of(&self.relays, false)
    }

    /// Every relay's state in a line (for the log).
    pub fn describe(&self) -> String {
        describe(&self.relays)
    }
}

impl Drop for Browse {
    fn drop(&mut self) {
        self.cancel.cancel();
    }
}

type Ws = tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>;

async fn connect(url: &str) -> Result<Ws, String> {
    if tango_net::endpoints::test_blocked(url) {
        return Err("blocked by TANGOAW2_BLOCK_ENDPOINTS".into());
    }
    // Left alone while it is backing off (also across restarts).
    let wait = tango_net::endpoints::wait_for(url);
    if wait > 0 {
        return Err(format!("backing off for {wait} s"));
    }
    match tango_platform::timeout(CONNECT_TIMEOUT, tokio_tungstenite::connect_async(url)).await {
        Err(_) => Err("timed out".into()),
        Ok(Err(e)) => Err(e.to_string()),
        Ok(Ok((ws, _))) => Ok(ws),
    }
}

/// Waits `d`, or returns false when cancelled.
async fn nap(cancel: &CancellationToken, d: Duration) -> bool {
    tokio::select! {
        _ = cancel.cancelled() => false,
        _ = tango_platform::sleep(d) => true,
    }
}

/// Seconds to wait before this relay is dialled again: its backoff (5 s doubling to 10 min, jittered, or an hour
/// after a stop signal), at least 2 s.
fn redial_wait(url: &str) -> u64 {
    tango_net::endpoints::wait_for(url).max(2)
}

async fn browse_relay(relay: Arc<Relay>, heard: Arc<Mutex<Heard>>, cancel: CancellationToken) {
    let url = relay.url.clone();
    loop {
        let mut wait = 2;
        match connect(&url).await {
            Err(e) => {
                log::info!("lobby list: {url}: {e}");
                if !e.starts_with("backing off") {
                    relay.failed(&e);
                }
                relay.note(e);
                wait = redial_wait(&url);
            }
            Ok(mut ws) => {
                relay.connected.store(true, Ordering::Relaxed);
                relay.note("");
                let r = browse_session(&relay, &mut ws, &heard, &cancel).await;
                relay.connected.store(false, Ordering::Relaxed);
                let answered = relay.answered.swap(0, Ordering::Relaxed) != 0;
                log::info!("lobby list: {url} ended: {r:?}");
                if let Err(e) = r {
                    // (a relay that had answered and then dropped is only retried soon; one that never answered, or
                    // said stop, is backed off)
                    if !answered || tango_net::endpoints::is_stop_signal(&e) {
                        relay.failed(&e);
                        wait = redial_wait(&url);
                    }
                    relay.note(e);
                }
            }
        }
        if cancel.is_cancelled() || !nap(&cancel, Duration::from_secs(wait)).await {
            return;
        }
    }
}

async fn browse_session(
    relay: &Relay,
    ws: &mut Ws,
    heard: &Arc<Mutex<Heard>>,
    cancel: &CancellationToken,
) -> Result<(), String> {
    let url = relay.url.as_str();
    let started = std::time::Instant::now();
    // Looks every 5 s, asks (a small REQ, newest 100) at once and then every 45 s: the answer is also the liveness
    // check; the websocket's own pings are answered by the library.
    let mut ask = tango_platform::Ticker::immediate(Duration::from_secs(5));
    let mut asked: Option<std::time::Instant> = None;
    loop {
        tokio::select! {
            _ = cancel.cancelled() => {
                let _ = ws.close(None).await;
                return Ok(());
            }
            // The subscription stays open (the relay then pushes new announcements by itself); asking again on it
            // replays what is stored: a safety net against a relay that stops pushing, and a liveness check.
            _ = ask.tick() => {
                // (a relay that has not answered the question in 20 s is not one to wait for: another connection)
                if relay.answered.load(Ordering::Relaxed) == 0 && started.elapsed().as_secs() >= 20 {
                    return Err("no answer to the question".into());
                }
                if asked.is_some_and(|a| a.elapsed().as_secs() < 45) {
                    continue;
                }
                asked = Some(std::time::Instant::now());
                let req = json!(["REQ", "lobbies", {"kinds": [KIND], "#t": [TAG], "since": now().saturating_sub(150), "limit": 100}]);
                ws.send(Message::Text(req.to_string())).await.map_err(|e| e.to_string())?;
            }
            m = ws.next() => {
                let Some(m) = m else { return Err("closed".into()) };
                match m.map_err(|e| e.to_string())? {
                    Message::Text(t) => {
                        let Ok(v) = serde_json::from_str::<Value>(&t) else { continue };
                        match v.get(0).and_then(Value::as_str) {
                            Some("EVENT") => match v.get(2).map(read_event) {
                                Some(Ok((author, code, at, lobby))) => {
                                    relay.events.fetch_add(1, Ordering::Relaxed);
                                    heard.lock().unwrap().hear(author, code, at, lobby);
                                }
                                Some(Err(why)) => log::debug!("lobby list: {url}: event ignored: {why}"),
                                None => {}
                            },
                            Some("EOSE") => {
                                if relay.answered.swap(mono(), Ordering::Relaxed) == 0 {
                                    log::info!("lobby list: {url} answered after {} ms", started.elapsed().as_millis());
                                    relay.succeeded(started.elapsed().as_millis() as u32);
                                }
                            }
                            Some("NOTICE") | Some("CLOSED") => {
                                relay.note(t.chars().take(60).collect::<String>());
                                log::info!("lobby list: {url}: {t}");
                                // A relay's own words of refusal are believed: it is left alone for an hour or more.
                                if tango_net::endpoints::is_stop_signal(&t) {
                                    return Err(t.chars().take(80).collect());
                                }
                            }
                            _ => {}
                        }
                    }
                    Message::Close(_) => return Err("closed by the relay".into()),
                    _ => {}
                }
            }
        }
    }
}

// --- The announcement ---------------------------------------------------------------------------------------

/// A host's running announcement: dropping it withdraws the lobby.
pub struct Announcer {
    lobby: Arc<Mutex<Lobby>>,
    relays: Vec<Arc<Relay>>,
    cancel: CancellationToken,
}

impl Announcer {
    /// Announces `lobby` on [`MAX_ANNOUNCE`] relays of the pool `relays` (must run inside the tokio runtime): both
    /// anchor relays and one more chosen by the room's code, and a spare for each that fails or says stop.
    pub fn start(relays: &[&str], lobby: Lobby) -> Announcer {
        let key = Arc::new(new_key());
        let pool: Vec<String> = relays.iter().map(|s| s.to_string()).collect();
        let plan = tango_net::endpoints::plan_now(&pool, Some(&lobby.code));
        log::info!(
            "online: lobby announce plan {}",
            plan.iter().take(MAX_ANNOUNCE).cloned().collect::<Vec<_>>().join(", ")
        );
        let lobby = Arc::new(Mutex::new(lobby));
        let cancel = CancellationToken::new();
        let infos: Vec<Arc<Relay>> = plan.iter().map(|u| Relay::new(u)).collect();
        let begin: Arc<dyn Fn(&Arc<Relay>, CancellationToken) + Send + Sync> = {
            let (key, lobby) = (key, lobby.clone());
            Arc::new(move |r: &Arc<Relay>, t: CancellationToken| {
                let (r, key, lobby) = (r.clone(), key.clone(), lobby.clone());
                tokio::spawn(async move { announce_relay(r, key, lobby, t).await });
            })
        };
        let replan: Arc<dyn Fn() -> Vec<String> + Send + Sync> = {
            let (pool, lobby) = (pool.clone(), lobby.clone());
            Arc::new(move || tango_net::endpoints::plan_now(&pool, Some(&lobby.lock().unwrap().code)))
        };
        keep_running(infos.clone(), MAX_ANNOUNCE, cancel.clone(), begin, replan);
        spawn_status_log("announce", infos.clone(), cancel.clone());
        Announcer {
            lobby,
            relays: infos,
            cancel,
        }
    }

    /// Changes what is announced (sent at the next look, within a second).
    pub fn update(&self, f: impl FnOnce(&mut Lobby)) {
        f(&mut self.lobby.lock().unwrap());
    }

    pub fn stats(&self) -> RelayStats {
        stats_of(&self.relays, true)
    }

    /// Every relay's state in a line (for the log).
    pub fn describe(&self) -> String {
        describe(&self.relays)
    }
}

impl Drop for Announcer {
    fn drop(&mut self) {
        // (each relay's task sends the closing event before it ends)
        self.cancel.cancel();
    }
}

async fn announce_relay(relay: Arc<Relay>, key: Arc<SigningKey>, lobby: Arc<Mutex<Lobby>>, cancel: CancellationToken) {
    let url = relay.url.clone();
    let mut last_at = 0;
    loop {
        let mut wait = 2;
        match connect(&url).await {
            Err(e) => {
                log::info!("lobby announce: {url}: {e}");
                if !e.starts_with("backing off") {
                    relay.failed(&e);
                }
                relay.note(e);
                wait = redial_wait(&url);
            }
            Ok(mut ws) => {
                relay.connected.store(true, Ordering::Relaxed);
                relay.note("");
                let r = announce_session(&relay, &mut ws, &key, &lobby, &cancel, &mut last_at).await;
                relay.connected.store(false, Ordering::Relaxed);
                relay.answered.store(0, Ordering::Relaxed);
                log::info!("lobby announce: {url} ended: {r:?}");
                // (a refusal was recorded by the session: a stop signal blocks the relay for an hour or more)
                if r.is_err() {
                    wait = redial_wait(&url);
                }
            }
        }
        if cancel.is_cancelled() || !nap(&cancel, Duration::from_secs(wait)).await {
            return;
        }
    }
}

async fn announce_session(
    relay: &Relay,
    ws: &mut Ws,
    key: &SigningKey,
    lobby: &Mutex<Lobby>,
    cancel: &CancellationToken,
    last_at: &mut u64,
) -> Result<(), String> {
    let url = relay.url.as_str();
    let mut sent: Option<(Lobby, std::time::Instant)> = None;
    let mut refresh = REFRESH;
    // After a rate limit: nothing is sent until then (the connection stays).
    let pause: Option<std::time::Instant> = None;
    let mut look = tango_platform::Ticker::immediate(Duration::from_secs(1));
    loop {
        tokio::select! {
            _ = cancel.cancelled() => {
                // Withdraw the lobby (best effort), then go.
                let code = lobby.lock().unwrap().code.clone();
                *last_at = (*last_at + 1).max(now());
                let ev = make_event(key, &code, None, *last_at);
                let _ = tango_platform::timeout(Duration::from_secs(2), async {
                    ws.send(Message::Text(json!(["EVENT", ev]).to_string())).await?;
                    // (wait for the relay's OK so the close is not cut)
                    while let Some(m) = ws.next().await {
                        if let Ok(Message::Text(t)) = m { if t.starts_with("[\"OK\"") { break; } }
                    }
                    Ok::<(), tokio_tungstenite::tungstenite::Error>(())
                }).await;
                let _ = ws.close(None).await;
                return Ok(());
            }
            _ = look.tick() => {
                if pause.is_some_and(|p| std::time::Instant::now() < p) {
                    continue;
                }
                let now_l = lobby.lock().unwrap().clone();
                let due = match &sent {
                    Some((l, at)) => {
                        // Every 15-20 s (jittered per send); a change goes out at once but never within 5 s of the
                        // last event: at most 12 events a minute on a relay.
                        (*l != now_l && at.elapsed().as_secs() >= tango_net::endpoints::MIN_PUBLISH_GAP_SECS)
                            || at.elapsed() >= refresh
                    }
                    None => true,
                };
                if due {
                    *last_at = (*last_at + 1).max(now());
                    let ev = make_event(key, &now_l.code, Some(&now_l), *last_at);
                    ws.send(Message::Text(json!(["EVENT", ev]).to_string())).await.map_err(|e| e.to_string())?;
                    sent = Some((now_l, std::time::Instant::now()));
                    refresh = tango_net::endpoints::refresh_interval();
                }
            }
            m = ws.next() => {
                let Some(m) = m else { return Err("closed".into()) };
                match m.map_err(|e| e.to_string())? {
                    Message::Text(t) => {
                        if let Ok(v) = serde_json::from_str::<Value>(&t) {
                            if v.get(0).and_then(Value::as_str) == Some("OK") {
                                let why = v.get(3).and_then(Value::as_str).unwrap_or("");
                                if v.get(2).and_then(Value::as_bool) == Some(true) || why.starts_with("duplicate") {
                                    relay.events.fetch_add(1, Ordering::Relaxed);
                                    if relay.answered.swap(mono(), Ordering::Relaxed) == 0 {
                                        relay.succeeded(0);
                                    }
                                    relay.note("");
                                } else {
                                    // Refused: believed. A stop signal (rate limit, blocked, payment, login) leaves
                                    // the relay alone for an hour or more; the swap brings a spare in.
                                    log::info!("lobby announce: {url} refused it: {why}");
                                    relay.note(format!("refused: {}", why.chars().take(40).collect::<String>()));
                                    relay.failed(why);
                                    return Err("refused".into());
                                }
                            }
                        }
                    }
                    Message::Close(_) => return Err("closed by the relay".into()),
                    _ => {}
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lobby(code: &str) -> Lobby {
        Lobby {
            code: code.into(),
            host: "Rkoh".into(),
            name: "Rkoh's room".into(),
            players: 2,
            max: 5,
            locked: true,
            version: "0.6.22".into(),
            pack: true,
        }
    }

    fn compat() -> Compat {
        Compat {
            version: "0.6.22".into(),
            pack: true,
        }
    }

    #[test]
    fn content_round_trips() {
        let l = lobby("AB12CD");
        assert_eq!(Lobby::decode(&l.encode()), Ok(Some(l)));
        assert_eq!(Lobby::decode("{\"x\":1}"), Ok(None));
    }

    #[test]
    fn content_is_checked() {
        let mut l = lobby("AB12CD");
        l.host = "Very\u{1}long name\u{e9} indeed".into();
        let d = Lobby::decode(&l.encode()).unwrap().unwrap();
        assert!(
            d.host.len() <= 12 && d.host.chars().all(|c| c.is_ascii() && !c.is_ascii_control()),
            "{}",
            d.host
        );
        for bad in [
            "nope",
            "{}",
            r#"{"c":"AB1","h":"x","n":1,"m":5,"v":"1"}"#,
            r#"{"c":"AB12CD","h":"x","n":6,"m":5,"v":"1"}"#,
            r#"{"c":"AB12CD","h":"x","n":0,"m":5,"v":"1"}"#,
            r#"{"c":"AB12CD","h":"x","n":1,"m":9,"v":"1"}"#,
            r#"{"c":"AB12CD","h":"x","n":1,"m":5,"v":""}"#,
        ] {
            assert!(Lobby::decode(bad).is_err(), "{bad}");
        }
        // (the host's name may be empty: the screen then says Player)
        let e = Lobby::decode(r#"{"c":"ab12cd","h":"","n":1,"m":5,"v":"1"}"#)
            .unwrap()
            .unwrap();
        assert_eq!((e.code.as_str(), e.host.as_str()), ("AB12CD", "Player"));
    }

    #[test]
    fn a_room_has_its_name_and_an_old_announcement_its_host() {
        let mut l = lobby("AB12CD");
        l.name = "Big  Pent  Room ".into();
        // (spaces survive the announcement, one at a time, none at an end)
        let d = Lobby::decode(&l.encode()).unwrap().unwrap();
        assert_eq!(d.name, "Big Pent Room");
        // 0.8.4's announcement has no name: the host's gamertag is listed
        let old = Lobby::decode(r#"{"c":"AB12CD","h":"Ann Lee","n":1,"m":5,"v":"0.8.4"}"#)
            .unwrap()
            .unwrap();
        assert_eq!((old.name.as_str(), old.host.as_str()), ("Ann Lee", "Ann Lee"));
        // an all-space name is no name
        let blank = Lobby::decode(r#"{"c":"AB12CD","h":"Bo","r":"    ","n":1,"m":5,"v":"1"}"#)
            .unwrap()
            .unwrap();
        assert_eq!(blank.name, "Bo");
        // never more than 18 characters, never anything to hurt the screen
        let long = Lobby::decode(&format!(
            r#"{{"c":"AB12CD","h":"Bo","r":"{}\u0001é","n":1,"m":5,"v":"1"}}"#,
            "x".repeat(40)
        ))
        .unwrap()
        .unwrap();
        assert_eq!(long.name.len(), 18);
        assert_eq!(clean_text("  a   b  ", 12), "a b");
        assert_eq!(clean_text("abc def", 4), "abc");
    }

    #[test]
    fn events_are_signed_and_checked() {
        let key = new_key();
        let ev = make_event(&key, "ab12cd", Some(&lobby("AB12CD")), 1000);
        let (author, code, at, l) = read_event(&ev).unwrap();
        assert_eq!((code.as_str(), at), ("AB12CD", 1000));
        assert_eq!(author, hex(&key.verifying_key().to_bytes()));
        assert_eq!(l, Some(lobby("AB12CD")));
        // The tags carry an expiration.
        assert!(
            ev["tags"].to_string().contains("\"expiration\",\"1090\""),
            "{}",
            ev["tags"]
        );
        // Tampering with any part is refused.
        let mut e2 = ev.clone();
        e2["content"] = json!(lobby("AB12CD").encode().replace("Rkoh", "Evil"));
        assert_eq!(read_event(&e2).unwrap_err(), "id");
        let mut e3 = ev.clone();
        e3["sig"] = json!(hex(&[7u8; 64]));
        assert!(read_event(&e3).is_err());
        let mut e4 = ev.clone();
        e4["tags"] = json!([["d", "AB12CD"], ["t", "something-else"]]);
        assert_eq!(read_event(&e4).unwrap_err(), "tag");
        // A genuine event whose d does not match its content is refused too.
        let bad = make_event(&key, "ZZZZZZ", Some(&lobby("AB12CD")), 1000);
        assert_eq!(read_event(&bad).unwrap_err(), "d differs from the code");
        // The closing event reads as a closed lobby.
        let closed = make_event(&key, "AB12CD", None, 1001);
        assert_eq!(read_event(&closed).unwrap().3, None);
    }

    fn hear(h: &mut Heard, key: &SigningKey, l: Option<&Lobby>, code: &str, at: u64) {
        let ev = make_event(key, code, l, at);
        let (a, c, t, l) = read_event(&ev).unwrap();
        h.hear(a, c, t, l);
    }

    #[test]
    fn listing_keeps_the_newest_and_expires() {
        let (k1, k2) = (new_key(), new_key());
        let mut h = Heard::default();
        let mut a = lobby("AAAAAA");
        hear(&mut h, &k1, Some(&a), "AAAAAA", 100);
        a.players = 3;
        hear(&mut h, &k1, Some(&a), "AAAAAA", 110);
        // (an older one arriving late does not win)
        a.players = 2;
        hear(&mut h, &k1, Some(&a), "AAAAAA", 105);
        hear(&mut h, &k2, Some(&lobby("BBBBBB")), "BBBBBB", 112);
        let at = h.listings(115, &compat());
        assert_eq!(at.len(), 2);
        assert_eq!(at[0].lobby.code, "BBBBBB");
        assert_eq!(at[1].lobby.players, 3);
        // TTL: the one last heard at 110 is gone after 170, the other after 172.
        assert_eq!(h.listings(170, &compat()).len(), 2);
        assert_eq!(h.listings(171, &compat()).len(), 1);
        assert_eq!(h.listings(173, &compat()).len(), 0);
        // A lobby that closed is not listed, even though an older event of it arrives afterwards.
        hear(&mut h, &k2, None, "BBBBBB", 113);
        hear(&mut h, &k2, Some(&lobby("BBBBBB")), "BBBBBB", 112);
        let codes: Vec<_> = h
            .listings(115, &compat())
            .iter()
            .map(|l| l.lobby.code.clone())
            .collect();
        assert_eq!(codes, ["AAAAAA"]);
        // (a clock far ahead is not believed)
        hear(&mut h, &k2, Some(&lobby("CCCCCC")), "CCCCCC", 500);
        assert_eq!(h.listings(115, &compat()).len(), 1);
    }

    #[test]
    fn other_versions_and_packs_are_hidden() {
        let k = new_key();
        let mut h = Heard::default();
        let mut other = lobby("AAAAAA");
        other.version = "0.6.21".into();
        hear(&mut h, &k, Some(&other), "AAAAAA", 100);
        let mut nopack = lobby("BBBBBB");
        nopack.pack = false;
        hear(&mut h, &k, Some(&nopack), "BBBBBB", 100);
        hear(&mut h, &k, Some(&lobby("CCCCCC")), "CCCCCC", 100);
        let codes: Vec<_> = h
            .listings(101, &compat())
            .iter()
            .map(|l| l.lobby.code.clone())
            .collect();
        assert_eq!(codes, ["CCCCCC"]);
    }

    #[test]
    fn one_listing_per_code_and_a_cap() {
        let (k1, k2) = (new_key(), new_key());
        let mut h = Heard::default();
        // (two authors for one code: the newest shows)
        let mut a = lobby("AAAAAA");
        hear(&mut h, &k1, Some(&a), "AAAAAA", 100);
        a.players = 4;
        hear(&mut h, &k2, Some(&a), "AAAAAA", 101);
        let l = h.listings(102, &compat());
        assert_eq!((l.len(), l[0].lobby.players), (1, 4));
        for k in 0..20 {
            let code = format!("X{k:05}");
            hear(&mut h, &k1, Some(&lobby(&code)), &code, 100 + k);
        }
        assert_eq!(h.listings(125, &compat()).len(), MAX_LISTED);
    }

    #[test]
    fn the_matchmaking_session_has_no_address() {
        // What is announced is the code; the connection is the existing room session.
        let l = lobby("AB12CD");
        assert!(!l.encode().contains("tangoaw2-room"));
        assert_eq!(crate::room::room_session(&l.code), "tangoaw2-room-ab12cd");
    }
}
