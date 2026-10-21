//! The AI debug channel: a way for an AI developer (or any tool) to look into the running game and drive it, instead of
//! pressing keys blind with a pad script.
//!
//! **Off unless asked for.** It ships in every build and does nothing until `TANGOAW2_AI_DEBUG=<port | socket path>`
//! is set (or the hidden `ai_debug` key of `config.json`). With it off nothing listens, no thread exists and the
//! console's tick hook ([`tick`]) is one relaxed atomic load. It listens on 127.0.0.1 or a Unix socket only (with an
//! optional token, `TANGOAW2_AI_DEBUG_TOKEN`), never draws anything for the players, and logs a line when it is
//! enabled. It reads the console between ticks and changes nothing unless a command says so: a press goes through the
//! seat's normal input path, so the netplay sync (a waiting seat's keys are dropped by the console's merge) is
//! never bypassed. See tools/aidebug/README.md for the protocol.
//!
//! Layout: [`crate::inspect`] decodes the console; this module's hook ([`tick`], called from the game's
//! `before_tick` on the console's real ticks, never on a waiting seat's scratch copy) keeps the latest decoded state,
//! turns the change between two looks into events, and services the commands that need the console itself (peek,
//! poke, hash, checkpoints); [`server`] is the transport and the command table; [`cond`] the `wait_until` language;
//! [`inject`] the pad.

pub mod cond;
pub mod inject;
#[cfg(not(target_arch = "wasm32"))]
pub mod server;

use mgba::core::Core;
use serde_json::{json, Value};
use std::collections::VecDeque;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::mpsc::{channel, Sender};
use std::sync::{Condvar, Mutex, OnceLock};
use std::time::{Duration, Instant};

/// The protocol version [`server`] speaks.
pub const PROTOCOL: u32 = 1;
/// A new decoded state is made every this many ticks.
const STATE_EVERY: u64 = 3;
const EVENT_KEEP: usize = 4000;
const LOG_KEEP: usize = 2000;

static ENABLED: AtomicBool = AtomicBool::new(false);
static HUB: OnceLock<Hub> = OnceLock::new();
/// How often a seat offered keys the console's merge then did not let through (a waiting seat's presses), by seat.
static OFFERED: [AtomicU64; 5] = [const { AtomicU64::new(0) }; 5];
static DROPPED: [AtomicU64; 5] = [const { AtomicU64::new(0) }; 5];

/// Whether the channel is on (the hook's gate).
pub fn enabled() -> bool {
    ENABLED.load(Ordering::Relaxed)
}

/// What the app tells the hub about its own side, every ~16 ms.
#[derive(Clone, Debug, Default)]
pub struct LocalInfo {
    /// `none` (no session), `offline`, `online`, `replay`, `other`.
    pub session: String,
    /// This window's seat in a room (online).
    pub seat: usize,
}

/// A command the console must run itself (at a tick boundary, on its own thread).
pub enum CoreReq {
    Peek { addr: u32, len: usize },
    Poke { addr: u32, bytes: Vec<u8> },
    Hash,
    Procs,
    /// A fresh decoded state, made at the next tick.
    State,
    CheckpointSave { name: String },
    CheckpointLoad { name: String },
}

struct Pending {
    req: CoreReq,
    reply: Sender<Result<Value, String>>,
}

pub struct Latest {
    pub seq: u64,
    pub tick: u64,
    pub at: Instant,
    pub online: bool,
    pub json: Value,
}

struct Inner {
    latest: Option<std::sync::Arc<Latest>>,
    prev: Option<crate::inspect::Snapshot>,
    events: VecDeque<(u64, Value)>,
    next_event: u64,
    logs: VecDeque<String>,
    link: Value,
    local: LocalInfo,
    last_hash: Option<(u32, u64)>,
    checkpoint_dir: PathBuf,
    boot_checkpoint: Option<String>,
}

pub struct Hub {
    inner: Mutex<Inner>,
    changed: Condvar,
    reqs: Mutex<VecDeque<Pending>>,
    ticks: AtomicU64,
    seq: AtomicU64,
    injector: Mutex<inject::Injector>,
}

fn hub() -> &'static Hub {
    HUB.get_or_init(|| Hub {
        inner: Mutex::new(Inner {
            latest: None,
            prev: None,
            events: VecDeque::new(),
            next_event: 1,
            logs: VecDeque::new(),
            link: Value::Null,
            local: LocalInfo { session: "none".into(), seat: 0 },
            last_hash: None,
            checkpoint_dir: PathBuf::from("checkpoints"),
            boot_checkpoint: None,
        }),
        changed: Condvar::new(),
        reqs: Mutex::new(VecDeque::new()),
        ticks: AtomicU64::new(0),
        seq: AtomicU64::new(0),
        injector: Mutex::new(inject::Injector::new(Instant::now())),
    })
}

/// Turns the hook on (the server and the boot checkpoint both need it). Idempotent.
pub fn enable(checkpoint_dir: &Path) {
    let h = hub();
    h.inner.lock().unwrap().checkpoint_dir = checkpoint_dir.to_path_buf();
    if !ENABLED.swap(true, Ordering::Relaxed) {
        log::warn!("ai-debug: the debug hook is ON (checkpoints in {})", checkpoint_dir.display());
    }
}

/// The checkpoint to load into the first offline session (`TANGOAW2_BOOT_CHECKPOINT`).
pub fn set_boot_checkpoint(name: Option<String>) {
    hub().inner.lock().unwrap().boot_checkpoint = name;
}

pub fn take_boot_checkpoint() -> Option<String> {
    hub().inner.lock().unwrap().boot_checkpoint.take()
}

pub fn boot_checkpoint_pending() -> bool {
    HUB.get().is_some_and(|h| h.inner.lock().unwrap().boot_checkpoint.is_some())
}

/// The app's view of itself (see [`LocalInfo`]) and of the netplay link (a JSON object for `state.link`).
pub fn set_local(local: LocalInfo, link: Value) {
    let mut g = hub().inner.lock().unwrap();
    g.local = local;
    g.link = link;
}

pub fn local() -> LocalInfo {
    hub().inner.lock().unwrap().local.clone()
}

/// The pad word for now (see [`inject::Injector::poll`]); the app hands it to the session.
pub fn pad_word(now: Instant) -> Option<u32> {
    let h = HUB.get()?;
    let cursor = h.inner.lock().unwrap().latest.as_ref().and_then(|l| {
        let c = &l.json["cursor"];
        Some((c["x"].as_u64()? as u16, c["y"].as_u64()? as u16))
    });
    h.injector.lock().unwrap().poll(now, cursor)
}

/// Runs `f` on the injector.
pub fn with_injector<R>(f: impl FnOnce(&mut inject::Injector) -> R) -> R {
    f(&mut hub().injector.lock().unwrap())
}

/// A log line, for `log_tail` and error events (the app's logger calls this for every record; free while off).
pub fn log_record(level: log::Level, target: &str, msg: &str) {
    if !enabled() {
        return;
    }
    let line = format!("{level:<5} {target}: {msg}");
    let mut g = hub().inner.lock().unwrap();
    if g.logs.len() >= LOG_KEEP {
        g.logs.pop_front();
    }
    g.logs.push_back(line.clone());
    if level == log::Level::Error {
        let id = g.next_event;
        g.next_event += 1;
        g.events.push_back((id, json!({"event": "error", "message": line})));
        if g.events.len() > EVENT_KEEP {
            g.events.pop_front();
        }
        drop(g);
        hub().changed.notify_all();
    }
}

pub fn log_tail(lines: usize) -> Vec<String> {
    let g = hub().inner.lock().unwrap();
    let skip = g.logs.len().saturating_sub(lines);
    g.logs.iter().skip(skip).cloned().collect()
}

/// The merge noted what the seats offered and what got through (a waiting seat's keys do not): counters for the state.
pub fn note_merge(inputs: &[u32], merged: u32) {
    if !enabled() {
        return;
    }
    for (i, &k) in inputs.iter().enumerate().take(5) {
        if k & 0x3FF != 0 {
            OFFERED[i].fetch_add(1, Ordering::Relaxed);
            if k & 0x3FF & !merged != 0 {
                DROPPED[i].fetch_add(1, Ordering::Relaxed);
            }
        }
    }
}

fn input_counters() -> Value {
    let get = |a: &[AtomicU64; 5]| a.iter().map(|x| x.load(Ordering::Relaxed)).collect::<Vec<_>>();
    json!({"offered_ticks": get(&OFFERED), "dropped_ticks": get(&DROPPED),
           "note": "console-side counts of ticks, rollback re-simulations included"})
}

/// The console's tick hook: call it from the game's `before_tick` on the real console only. One atomic load when off.
pub fn tick(core: &mut Core, mode: Option<(u8, u8)>, _keys: u32) {
    if !enabled() {
        return;
    }
    hub().on_tick(core, mode.is_some());
}

impl Hub {
    fn on_tick(&self, core: &mut Core, online: bool) {
        let tick = self.ticks.fetch_add(1, Ordering::Relaxed) + 1;
        // Commands first (a load changes what the look below sees).
        let pending: Vec<Pending> = self.reqs.lock().unwrap().drain(..).collect();
        let forced = pending.iter().any(|p| matches!(p.req, CoreReq::State));
        for p in pending {
            let out = self.serve(core, online, &p.req);
            let _ = p.reply.send(out);
        }
        let fc = core.frame_counter();
        if tick % STATE_EVERY == 0 || forced {
            self.publish(core, online, tick);
        }
        if fc % 60 == 0 {
            let mut g = self.inner.lock().unwrap();
            if g.last_hash.map(|h| h.0) != Some(fc) {
                let h = crate::inspect::ram_hash(core);
                g.last_hash = Some((fc, h));
                let id = g.next_event;
                g.next_event += 1;
                g.events.push_back((id, json!({"event": "hash", "frame": fc, "tick": tick, "h": format!("{h:016x}")})));
                if g.events.len() > EVENT_KEEP {
                    g.events.pop_front();
                }
                drop(g);
                self.changed.notify_all();
            }
        }
    }

    fn publish(&self, core: &Core, online: bool, tick: u64) {
        let snap = crate::inspect::snapshot(core, online);
        let mut json = snap.to_json();
        let seq = self.seq.fetch_add(1, Ordering::Relaxed) + 1;
        let mut g = self.inner.lock().unwrap();
        if let Some(m) = json.as_object_mut() {
            m.insert("tick".into(), json!(tick));
            m.insert("seq".into(), json!(seq));
            m.insert("link".into(), g.link.clone());
            m.insert("local".into(), json!({"session": g.local.session, "seat": g.local.seat}));
            if let Some((f, h)) = g.last_hash {
                m.insert("last_hash".into(), json!({"frame": f, "h": format!("{h:016x}")}));
            }
            if let Some(o) = m.get_mut("online").and_then(|o| o.as_object_mut()) {
                o.insert("input".into(), input_counters());
            }
        }
        let mut new_events = Vec::new();
        if let Some(prev) = g.prev.as_ref() {
            new_events = crate::inspect::events(prev, &snap);
        }
        for e in new_events {
            let id = g.next_event;
            g.next_event += 1;
            g.events.push_back((id, e));
        }
        while g.events.len() > EVENT_KEEP {
            g.events.pop_front();
        }
        g.prev = Some(snap);
        g.latest = Some(std::sync::Arc::new(Latest { seq, tick, at: Instant::now(), online, json }));
        drop(g);
        self.changed.notify_all();
    }

    fn serve(&self, core: &mut Core, online: bool, req: &CoreReq) -> Result<Value, String> {
        match req {
            CoreReq::Peek { addr, len } => {
                let mut buf = vec![0u8; *len];
                core.raw_read_range(*addr, -1, &mut buf);
                Ok(json!({"addr": addr, "len": len, "hex": hex(&buf)}))
            }
            CoreReq::Poke { addr, bytes } => {
                core.raw_write_range(*addr, -1, bytes);
                log::warn!("ai-debug: poke {addr:08x} {} bytes{}", bytes.len(), if online { " ONLINE (desync risk)" } else { "" });
                Ok(json!({"addr": addr, "len": bytes.len(), "desync_risk": online}))
            }
            CoreReq::Hash => {
                let h = crate::inspect::ram_hash(core);
                Ok(json!({"frame": core.frame_counter(), "h": format!("{h:016x}")}))
            }
            CoreReq::Procs => Ok(json!({
                "procs": crate::fog_view::procs(core).iter().map(|p| format!("0x{p:08X}")).collect::<Vec<_>>(),
                "main_loop": format!("0x{:08X}", core.raw_read_32(0x0300_0000, -1)),
            })),
            CoreReq::State => Ok(Value::Null),
            CoreReq::CheckpointSave { name } => {
                let dir = self.inner.lock().unwrap().checkpoint_dir.clone();
                checkpoint_save(core, &dir, name, online)
            }
            CoreReq::CheckpointLoad { name } => {
                if online {
                    return Err("checkpoint_load is offline only: every peer of a match would have to load the same state at the same tick".into());
                }
                let dir = self.inner.lock().unwrap().checkpoint_dir.clone();
                checkpoint_load(core, &dir, name)
            }
        }
    }
}

fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}

/// Asks the console to run a command at its next tick and waits for the answer.
pub fn ask_console(req: CoreReq, timeout: Duration) -> Result<Value, String> {
    if !enabled() {
        return Err("the debug hook is off".into());
    }
    let (tx, rx) = channel();
    hub().reqs.lock().unwrap().push_back(Pending { req, reply: tx });
    rx.recv_timeout(timeout).map_err(|_| "no console is ticking (no session, or it is paused)".to_string())?
}

/// The latest decoded state, if the console has ticked.
pub fn latest() -> Option<std::sync::Arc<Latest>> {
    HUB.get()?.inner.lock().unwrap().latest.clone()
}

/// Waits (up to `timeout`) for something to change in the hub (a new state or event); true if woken.
pub fn wait_changed(timeout: Duration) -> bool {
    let h = hub();
    let g = h.inner.lock().unwrap();
    let (_g, r) = h.changed.wait_timeout(g, timeout).unwrap();
    !r.timed_out()
}

/// Events after `after` (ids rise), at most `max`.
pub fn events_after(after: u64, max: usize) -> Vec<(u64, Value)> {
    let g = hub().inner.lock().unwrap();
    g.events.iter().filter(|(id, _)| *id > after).take(max).cloned().collect()
}

/// The id of the newest event (0: none yet).
pub fn last_event_id() -> u64 {
    hub().inner.lock().unwrap().events.back().map_or(0, |e| e.0)
}

pub fn push_event(ev: Value) {
    let mut g = hub().inner.lock().unwrap();
    let id = g.next_event;
    g.next_event += 1;
    g.events.push_back((id, ev));
    drop(g);
    hub().changed.notify_all();
}

// --- Checkpoints --------------------------------------------------------------------------------------------

/// A checkpoint's name: letters, digits, `_`, `-`, `.`; no path.
pub fn valid_name(name: &str) -> bool {
    !name.is_empty() && name.len() <= 64 && !name.starts_with('.') && name.bytes().all(|c| c.is_ascii_alphanumeric() || b"_-.".contains(&c))
}

fn state_size() -> usize {
    std::mem::size_of::<mgba::state::State>()
}

/// What a checkpoint must agree with to be loaded: the Dual Strike pack flags the console was built with (the pack's
/// features change what the console's patches do), and the cartridge.
fn setup_flags(core: &Core) -> Value {
    let rom: Vec<u8> = (0..16).map(|i| core.raw_read_8(0x0800_00A0 + i, -1)).collect();
    json!({
        "ds_features": crate::ds_pack::features(None),
        "ds_pack_present": crate::ds_pack::pack().is_some(),
        "ds_pack_outdated": crate::ds_pack::outdated(),
        "rom_title": String::from_utf8_lossy(&rom).trim_end_matches('\0').to_string(),
        "state_size": state_size(),
    })
}

pub fn checkpoint_save(core: &Core, dir: &Path, name: &str, online: bool) -> Result<Value, String> {
    if !valid_name(name) {
        return Err("a checkpoint name is letters, digits, _ - . (at most 64)".into());
    }
    let state = core.save_state().map_err(|e| format!("save_state: {e:?}"))?;
    let bytes = state.as_slice();
    let hash = crate::inspect::ram_hash(core);
    let snap = crate::inspect::snapshot(core, online);
    std::fs::create_dir_all(dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    let meta = json!({
        "version": 1,
        "name": name,
        "frame": core.frame_counter(),
        "ram_hash": format!("{hash:016x}"),
        "online": online,
        "phase": snap.phase,
        "screen": snap.screen,
        "map": {"id": snap.map_id, "name": snap.map_name, "w": snap.width, "h": snap.height},
        "day": snap.day,
        "active_army": snap.active_army,
        "armies": snap.armies.iter().map(|a| json!({"army": a.army, "co": a.co, "team": a.team, "controller": a.controller, "colour": a.colour})).collect::<Vec<_>>(),
        "rules": snap.to_json()["rules"].clone(),
        "setup": setup_flags(core),
        "saved_unix": std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(0, |d| d.as_secs()),
    });
    let tmp = dir.join(format!("{name}.state.tmp"));
    std::fs::write(&tmp, bytes).map_err(|e| format!("{}: {e}", tmp.display()))?;
    std::fs::rename(&tmp, dir.join(format!("{name}.state"))).map_err(|e| e.to_string())?;
    std::fs::write(dir.join(format!("{name}.json")), serde_json::to_vec_pretty(&meta).unwrap_or_default()).map_err(|e| e.to_string())?;
    log::info!("ai-debug: checkpoint {name} saved at frame {} (ram hash {hash:016x})", core.frame_counter());
    Ok(json!({"name": name, "frame": core.frame_counter(), "ram_hash": format!("{hash:016x}"), "bytes": bytes.len(), "dir": dir.display().to_string(), "meta": meta}))
}

pub fn checkpoint_load(core: &mut Core, dir: &Path, name: &str) -> Result<Value, String> {
    if !valid_name(name) {
        return Err("a checkpoint name is letters, digits, _ - . (at most 64)".into());
    }
    let bytes = std::fs::read(dir.join(format!("{name}.state"))).map_err(|e| format!("checkpoint {name}: {e}"))?;
    let meta: Value = std::fs::read(dir.join(format!("{name}.json")))
        .ok()
        .and_then(|b| serde_json::from_slice(&b).ok())
        .unwrap_or(Value::Null);
    if bytes.len() != state_size() {
        return Err(format!("checkpoint {name}: {} bytes, this emulator's state is {}", bytes.len(), state_size()));
    }
    let now = setup_flags(core);
    for key in ["ds_features", "rom_title"] {
        let was = &meta["setup"][key];
        if !was.is_null() && was != &now[key] {
            return Err(format!("checkpoint {name} was saved with {key}={was}, this session has {}: boot the app the same way", now[key]));
        }
    }
    // (sound: exactly a state's size, from `save_state` of a console of this build)
    let loaded = unsafe { mgba::state::State::from_slice(&bytes) };
    core.load_state(&loaded).map_err(|e| format!("load_state: {e:?}"))?;
    core.audio_buffer().clear();
    let hash = crate::inspect::ram_hash(core);
    let expected = meta["ram_hash"].as_str().map(str::to_string);
    let same = expected.as_deref() == Some(format!("{hash:016x}").as_str());
    log::info!("ai-debug: checkpoint {name} loaded (ram hash {hash:016x}, saved {expected:?}, same {same})");
    Ok(json!({"name": name, "frame": core.frame_counter(), "ram_hash": format!("{hash:016x}"), "expected_hash": expected, "match": same, "meta": meta}))
}

/// The checkpoints in a directory (their metadata).
pub fn checkpoint_list(dir: &Path) -> Vec<Value> {
    let mut out = Vec::new();
    if let Ok(rd) = std::fs::read_dir(dir) {
        for e in rd.flatten() {
            let p = e.path();
            if p.extension().is_some_and(|x| x == "json") {
                if let Some(v) = std::fs::read(&p).ok().and_then(|b| serde_json::from_slice::<Value>(&b).ok()) {
                    out.push(v);
                }
            }
        }
    }
    out.sort_by(|a, b| a["name"].as_str().cmp(&b["name"].as_str()));
    out
}

pub fn checkpoint_dir() -> PathBuf {
    hub().inner.lock().unwrap().checkpoint_dir.clone()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn checkpoint_names_cannot_leave_the_directory() {
        assert!(valid_name("battle-1.start"));
        for bad in ["", "../x", "a/b", ".hidden", "a b", &"x".repeat(65)] {
            assert!(!valid_name(bad), "{bad}");
        }
    }

    /// The channel being on changes nothing the simulation sees: the same keys into two consoles, one with the hook on and
    /// a client asking for state, peeks and hashes all the while, leave the same RAM, tick for tick.
    /// Needs the ROM: `TANGOAW2_AW2_ROM=<Advance_wars_2.gba> cargo test -p tango-gamesupport-aw2 --lib the_channel_on -- --ignored`.
    #[test]
    #[ignore]
    fn the_channel_on_does_not_change_the_state_hashes() {
        use tango_match::{HostInput, Link};
        let rom = std::fs::read(std::env::var("TANGOAW2_AW2_ROM").expect("TANGOAW2_AW2_ROM")).unwrap();
        let save = vec![0xffu8; crate::SAVE_SIZE];
        let rtc = std::time::UNIX_EPOCH + std::time::Duration::from_secs(1_700_000_000);
        let run = |watched: bool| -> Vec<(u32, u64)> {
            let mut link = tango_backend_mgba::SharedLink::boot(&rom, Some(&save), Some(rtc), &crate::pvp::AW2E, None, None).expect("boot");
            let stop = std::sync::Arc::new(AtomicBool::new(false));
            let client = watched.then(|| {
                let stop = stop.clone();
                std::thread::spawn(move || {
                    let mut n = 0;
                    while !stop.load(Ordering::Relaxed) {
                        for req in [CoreReq::State, CoreReq::Peek { addr: 0x0300_0000, len: 64 }, CoreReq::Hash, CoreReq::Procs] {
                            let _ = ask_console(req, Duration::from_millis(200));
                        }
                        let _ = latest();
                        n += 1;
                    }
                    n
                })
            });
            let mut hashes = Vec::new();
            for t in 0..1800u32 {
                // (taps of START and A: through the title and into the menus)
                let keys = match t % 90 {
                    0..=5 => if t % 180 < 90 { 8 } else { 1 },
                    _ => 0,
                };
                link.tick_n(&[HostInput::keys(keys), HostInput::keys(0)]);
                if t % 60 == 0 {
                    hashes.push((t, crate::inspect::ram_hash(link.core())));
                }
            }
            stop.store(true, Ordering::Relaxed);
            if let Some(c) = client {
                assert!(c.join().unwrap() > 0 || !enabled());
            }
            hashes
        };
        let off = run(false);
        let dir = std::env::temp_dir().join("tangoaw2-aidebug-test");
        enable(&dir);
        let on = run(true);
        assert_eq!(off, on, "the hook or the client changed the console");
        assert!(latest().is_some(), "the hook never published a state");
    }

    #[test]
    fn with_the_hook_off_a_command_is_refused_and_the_counters_stay_put() {
        assert!(!enabled());
        assert!(ask_console(CoreReq::Hash, Duration::from_millis(10)).is_err());
        note_merge(&[1, 1], 0);
        assert_eq!(OFFERED[0].load(Ordering::Relaxed), 0);
    }
}
