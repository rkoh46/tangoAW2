//! tangoAW2's public lobby list: every room is announced, and anyone on the same version can list the rooms.
//!
//! There is no server of ours. A room's host announces it on public Nostr relays (websocket servers that store and
//! forward small signed events, run by third parties) and a player who opens the lobby browser asks the same relays
//! for the announcements. A matchmaking pool pairs two clients and cannot list anything; a relay keeps what it is
//! told, which is what a list needs.
//!
//! **The announcement** is one *parameterized replaceable* event (kind [`KIND`], 30078, "application specific
//! data"), `d` = the room's code, `t` = [`TAG`], with a NIP-40 `expiration` a few seconds after the next refresh.
//! It is signed by a throw-away key made when the host app starts (nobody can be told from it) and replaced every
//! [`REFRESH`] (12 s) by a new one with the same `d`: the relay keeps just the latest. Its content is [`Lobby`] as JSON:
//! code, host gamertag, players and seats, whether there is a password, the game version and whether the content
//! pack is on. **Never an address**: the connection is still made through the matchmaking server, in the session
//! `tangoaw2-room-<code>` ([`crate::room::room_session`]). A lobby that starts or closes is replaced by an event with
//! `{"x":1}` as its content; one that just disappears (a crash) is gone [`TTL`] after its last refresh.
//!
//! **The list** ([`Browse`]) subscribes to the `t` tag with `since` a minute back on every relay at once, keeps the
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
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio_tungstenite::tungstenite::Message;
use tokio_util::sync::CancellationToken;

/// The `t` tag of every tangoAW2 lobby announcement (its `-v1` is this format).
pub const TAG: &str = "tangoaw2-lobby-v1";
/// Nostr kind 30078: parameterized replaceable, application specific data.
pub const KIND: u64 = 30078;
/// The public relays tried in parallel (any one working is enough). Chosen for being long-running, free to write to
/// and not asking for payment or a login.
pub const RELAYS: &[&str] = &[
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.primal.net",
    "wss://offchain.pub",
    "wss://nostr.mom",
    "wss://relay.snort.social",
    "wss://nostr-pub.wellorder.net",
    "wss://nostr.oxtr.dev",
];
/// How often a host repeats its announcement.
pub const REFRESH: Duration = Duration::from_secs(12);
/// An announcement older than this is a lobby that is gone.
pub const TTL: u64 = 40;
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
        let host: String = s("h")
            .ok_or("no host")?
            .chars()
            .filter(|c| c.is_ascii() && !c.is_ascii_control())
            .take(12)
            .collect();
        let host = host.trim().to_string();
        let (players, max) = (n("n").ok_or("no players")?, n("m").ok_or("no max")?);
        if !(2..=5).contains(&max) || players < 1 || players > max {
            return Err("bad counts");
        }
        let version = s("v").ok_or("no version")?;
        if version.is_empty() || version.len() > 24 || !version.bytes().all(|b| b.is_ascii_graphic()) {
            return Err("bad version");
        }
        Ok(Some(Lobby {
            code,
            host: if host.is_empty() { "Player".into() } else { host },
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
    (0..s.len() / 2).map(|k| u8::from_str_radix(&s[2 * k..2 * k + 2], 16).ok()).collect()
}

fn event_id(pubkey: &str, created_at: u64, kind: u64, tags: &Value, content: &str) -> [u8; 32] {
    let s = json!([0, pubkey, created_at, kind, tags, content]).to_string();
    Sha256::digest(s.as_bytes()).into()
}

/// A signed announcement event (`lobby` None is the closing one).
pub fn make_event(key: &SigningKey, code: &str, lobby: Option<&Lobby>, created_at: u64) -> Value {
    let pubkey = hex(&key.verifying_key().to_bytes());
    let content = lobby.map_or_else(|| json!({"x": 1}).to_string(), |l| l.encode());
    // (gone a little after the next refresh would have been; a closing event only has to outlive being read)
    let expiry = created_at + if lobby.is_some() { TTL } else { 120 };
    let tags = json!([["d", code.to_ascii_uppercase()], ["t", TAG], ["expiration", expiry.to_string()]]);
    let id = event_id(&pubkey, created_at, KIND, &tags, &content);
    let sig = key.sign_raw(&id, &rand::random::<[u8; 32]>()).map(|s| hex(&s.to_bytes())).unwrap_or_default();
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
    pub relays: usize,
    /// Connected now.
    pub connected: usize,
    /// Announcements heard (browser) or accepted (announcer), in all.
    pub events: usize,
}

#[derive(Default)]
struct Counters {
    connected: AtomicUsize,
    events: AtomicUsize,
}

/// A running look at the public lobby list: dropping it stops.
pub struct Browse {
    heard: Arc<Mutex<Heard>>,
    compat: Compat,
    counters: Arc<Counters>,
    relays: usize,
    cancel: CancellationToken,
}

impl Browse {
    /// Starts looking on `relays` (must run inside the tokio runtime).
    pub fn start(relays: &[&str], compat: Compat) -> Browse {
        let heard = Arc::new(Mutex::new(Heard::default()));
        let counters = Arc::new(Counters::default());
        let cancel = CancellationToken::new();
        for &url in relays {
            let (heard, counters, cancel) = (heard.clone(), counters.clone(), cancel.clone());
            let url = url.to_string();
            tokio::spawn(async move { browse_relay(url, heard, counters, cancel).await });
        }
        Browse {
            heard,
            compat,
            counters,
            relays: relays.len(),
            cancel,
        }
    }

    /// The open lobbies of this version, newest first.
    pub fn listings(&self) -> Vec<Listing> {
        self.heard.lock().unwrap().listings(now(), &self.compat)
    }

    pub fn stats(&self) -> RelayStats {
        RelayStats {
            relays: self.relays,
            connected: self.counters.connected.load(Ordering::Relaxed),
            events: self.counters.events.load(Ordering::Relaxed),
        }
    }
}

impl Drop for Browse {
    fn drop(&mut self) {
        self.cancel.cancel();
    }
}

type Ws = tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>;

async fn connect(url: &str) -> Result<Ws, String> {
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

async fn browse_relay(url: String, heard: Arc<Mutex<Heard>>, counters: Arc<Counters>, cancel: CancellationToken) {
    let mut wait = 3;
    let mut failures = 0u32;
    loop {
        match connect(&url).await {
            Err(e) => {
                failures += 1;
                if failures <= 2 {
                    log::info!("lobby list: {url}: {e}");
                }
            }
            Ok(mut ws) => {
                failures = 0;
                wait = 3;
                counters.connected.fetch_add(1, Ordering::Relaxed);
                let r = browse_session(&url, &mut ws, &heard, &counters, &cancel).await;
                counters.connected.fetch_sub(1, Ordering::Relaxed);
                log::info!("lobby list: {url} ended: {r:?}");
            }
        }
        if cancel.is_cancelled() || !nap(&cancel, Duration::from_secs(wait)).await {
            return;
        }
        wait = (wait * 2).min(30);
    }
}

async fn browse_session(
    url: &str,
    ws: &mut Ws,
    heard: &Arc<Mutex<Heard>>,
    counters: &Counters,
    cancel: &CancellationToken,
) -> Result<(), String> {
    let mut ask = tango_platform::Ticker::immediate(Duration::from_secs(15));
    loop {
        tokio::select! {
            _ = cancel.cancelled() => {
                let _ = ws.close(None).await;
                return Ok(());
            }
            // (asking again on the same subscription replays what is stored: also a liveness check)
            _ = ask.tick() => {
                let req = json!(["REQ", "lobbies", {"kinds": [KIND], "#t": [TAG], "since": now().saturating_sub(60)}]);
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
                                    counters.events.fetch_add(1, Ordering::Relaxed);
                                    heard.lock().unwrap().hear(author, code, at, lobby);
                                }
                                Some(Err(why)) => log::debug!("lobby list: {url}: event ignored: {why}"),
                                None => {}
                            },
                            Some("NOTICE") | Some("CLOSED") => log::info!("lobby list: {url}: {t}"),
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

/// A host's running announcement: dropping it (or [`stop`](Self::stop)) withdraws the lobby.
pub struct Announcer {
    lobby: Arc<Mutex<Lobby>>,
    counters: Arc<Counters>,
    relays: usize,
    cancel: CancellationToken,
}

impl Announcer {
    /// Announces `lobby` on `relays` (must run inside the tokio runtime).
    pub fn start(relays: &[&str], lobby: Lobby) -> Announcer {
        let key = Arc::new(new_key());
        let lobby = Arc::new(Mutex::new(lobby));
        let counters = Arc::new(Counters::default());
        let cancel = CancellationToken::new();
        for &url in relays {
            let (key, lobby, counters, cancel) = (key.clone(), lobby.clone(), counters.clone(), cancel.clone());
            let url = url.to_string();
            tokio::spawn(async move { announce_relay(url, key, lobby, counters, cancel).await });
        }
        Announcer {
            lobby,
            counters,
            relays: relays.len(),
            cancel,
        }
    }

    /// Changes what is announced (sent at the next look, within a second).
    pub fn update(&self, f: impl FnOnce(&mut Lobby)) {
        f(&mut self.lobby.lock().unwrap());
    }

    pub fn stats(&self) -> RelayStats {
        RelayStats {
            relays: self.relays,
            connected: self.counters.connected.load(Ordering::Relaxed),
            events: self.counters.events.load(Ordering::Relaxed),
        }
    }
}

impl Drop for Announcer {
    fn drop(&mut self) {
        // (each relay's task sends the closing event before it ends)
        self.cancel.cancel();
    }
}

async fn announce_relay(
    url: String,
    key: Arc<SigningKey>,
    lobby: Arc<Mutex<Lobby>>,
    counters: Arc<Counters>,
    cancel: CancellationToken,
) {
    let mut wait = 3;
    let mut failures = 0u32;
    let mut last_at = 0;
    loop {
        match connect(&url).await {
            Err(e) => {
                failures += 1;
                if failures <= 2 {
                    log::info!("lobby announce: {url}: {e}");
                }
            }
            Ok(mut ws) => {
                failures = 0;
                wait = 3;
                counters.connected.fetch_add(1, Ordering::Relaxed);
                let r = announce_session(&url, &mut ws, &key, &lobby, &counters, &cancel, &mut last_at).await;
                counters.connected.fetch_sub(1, Ordering::Relaxed);
                log::info!("lobby announce: {url} ended: {r:?}");
                // A relay that turned the announcement away (rate limits are common) is left alone for a while.
                if r == Err("refused".to_string()) {
                    wait = 90;
                }
            }
        }
        if cancel.is_cancelled() || !nap(&cancel, Duration::from_secs(wait)).await {
            return;
        }
        wait = if wait >= 90 { 30 } else { (wait * 2).min(30) };
    }
}

async fn announce_session(
    url: &str,
    ws: &mut Ws,
    key: &SigningKey,
    lobby: &Mutex<Lobby>,
    counters: &Counters,
    cancel: &CancellationToken,
    last_at: &mut u64,
) -> Result<(), String> {
    let mut sent: Option<(Lobby, std::time::Instant)> = None;
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
                let now_l = lobby.lock().unwrap().clone();
                let due = match &sent {
                    Some((l, at)) => *l != now_l || at.elapsed() >= REFRESH,
                    None => true,
                };
                if due {
                    *last_at = (*last_at + 1).max(now());
                    let ev = make_event(key, &now_l.code, Some(&now_l), *last_at);
                    ws.send(Message::Text(json!(["EVENT", ev]).to_string())).await.map_err(|e| e.to_string())?;
                    sent = Some((now_l, std::time::Instant::now()));
                }
            }
            m = ws.next() => {
                let Some(m) = m else { return Err("closed".into()) };
                match m.map_err(|e| e.to_string())? {
                    Message::Text(t) => {
                        if let Ok(v) = serde_json::from_str::<Value>(&t) {
                            if v.get(0).and_then(Value::as_str) == Some("OK") {
                                if v.get(2).and_then(Value::as_bool) == Some(true) {
                                    counters.events.fetch_add(1, Ordering::Relaxed);
                                } else {
                                    log::info!("lobby announce: {url} refused it: {}", v.get(3).and_then(Value::as_str).unwrap_or(""));
                                    // (a relay that does not take it: leave it for now)
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
        assert!(d.host.len() <= 12 && d.host.chars().all(|c| c.is_ascii() && !c.is_ascii_control()), "{}", d.host);
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
        let e = Lobby::decode(r#"{"c":"ab12cd","h":"","n":1,"m":5,"v":"1"}"#).unwrap().unwrap();
        assert_eq!((e.code.as_str(), e.host.as_str()), ("AB12CD", "Player"));
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
        assert!(ev["tags"].to_string().contains("\"expiration\",\"1040\""), "{}", ev["tags"]);
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
        // TTL: the one last heard at 110 is gone at 151, the other at 153.
        assert_eq!(h.listings(150, &compat()).len(), 2);
        assert_eq!(h.listings(151, &compat()).len(), 1);
        assert_eq!(h.listings(153, &compat()).len(), 0);
        // A lobby that closed is not listed, even though an older event of it arrives afterwards.
        hear(&mut h, &k2, None, "BBBBBB", 113);
        hear(&mut h, &k2, Some(&lobby("BBBBBB")), "BBBBBB", 112);
        let codes: Vec<_> = h.listings(115, &compat()).iter().map(|l| l.lobby.code.clone()).collect();
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
        let codes: Vec<_> = h.listings(101, &compat()).iter().map(|l| l.lobby.code.clone()).collect();
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
