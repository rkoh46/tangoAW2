//! The debug channel's transport and command table. Line-delimited JSON over TCP 127.0.0.1 or a Unix socket: each
//! request is one line `{"id":1,"cmd":"state", ...}`, each answer one line `{"id":1,"ok":true, ...}` or
//! `{"id":1,"ok":false,"error":"..."}`; after `subscribe` event lines `{"event":"act", ..., "eid":17}` are interleaved
//! (they have no `id`). The command list is in tools/aidebug/README.md.

use super::{cond, inject, CoreReq};
use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Read, Write};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{channel, Sender};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

/// A command only the app can run (it owns the session, the window picture and the network faults).
pub struct AppCall {
    pub name: String,
    pub args: Value,
    pub reply: Sender<Result<Value, String>>,
}

#[derive(Clone)]
pub struct Settings {
    /// `<port>` (0: pick one), or a socket path.
    pub listen: String,
    pub token: Option<String>,
    /// `TANGOAW2_AI_DEBUG_TEST=1`: `inject` is allowed.
    pub test_mode: bool,
    /// `TANGOAW2_AI_DEBUG_WRITE=1`: an online peer may be poked (with `force_offline`).
    pub write_online: bool,
    pub app_version: String,
}

struct Shared {
    settings: Settings,
    app: Mutex<Sender<AppCall>>,
}

pub fn b64(data: &[u8]) -> String {
    const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(data.len().div_ceil(3) * 4);
    for c in data.chunks(3) {
        let n = (c[0] as u32) << 16 | (*c.get(1).unwrap_or(&0) as u32) << 8 | *c.get(2).unwrap_or(&0) as u32;
        out.push(T[(n >> 18) as usize & 63] as char);
        out.push(T[(n >> 12) as usize & 63] as char);
        out.push(if c.len() > 1 { T[(n >> 6) as usize & 63] as char } else { '=' });
        out.push(if c.len() > 2 { T[n as usize & 63] as char } else { '=' });
    }
    out
}

/// Starts listening; returns a description of where (the port picked for `0`). The accept loop runs on its own thread.
pub fn start(settings: Settings, app: Sender<AppCall>) -> std::io::Result<String> {
    let listen = settings.listen.clone();
    let shared = Arc::new(Shared { settings, app: Mutex::new(app) });
    if !listen.is_empty() && listen.bytes().all(|c| c.is_ascii_digit()) {
        let port: u16 = listen.parse().map_err(|_| std::io::Error::other("bad port"))?;
        let l = std::net::TcpListener::bind(("127.0.0.1", port))?;
        let at = format!("127.0.0.1:{}", l.local_addr()?.port());
        std::thread::Builder::new().name("ai-debug-accept".into()).spawn(move || {
            for c in l.incoming().flatten() {
                let _ = c.set_nodelay(true);
                let Ok(w) = c.try_clone() else { continue };
                let sh = shared.clone();
                let _ = std::thread::Builder::new().name("ai-debug-conn".into()).spawn(move || serve(sh, c, w));
            }
        })?;
        Ok(at)
    } else {
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let _ = std::fs::remove_file(&listen);
            let l = std::os::unix::net::UnixListener::bind(&listen)?;
            let _ = std::fs::set_permissions(&listen, std::fs::Permissions::from_mode(0o600));
            std::thread::Builder::new().name("ai-debug-accept".into()).spawn(move || {
                for c in l.incoming().flatten() {
                    let Ok(w) = c.try_clone() else { continue };
                    let sh = shared.clone();
                    let _ = std::thread::Builder::new().name("ai-debug-conn".into()).spawn(move || serve(sh, c, w));
                }
            })?;
            Ok(format!("unix:{listen}"))
        }
        #[cfg(not(unix))]
        {
            let _ = shared;
            Err(std::io::Error::other("socket paths need a Unix system; use a port"))
        }
    }
}

type Out = Arc<Mutex<Box<dyn Write + Send>>>;

fn send(out: &Out, v: &Value) -> bool {
    let mut line = v.to_string();
    line.push('\n');
    let mut g = out.lock().unwrap();
    g.write_all(line.as_bytes()).and_then(|_| g.flush()).is_ok()
}

struct Conn {
    authed: bool,
    sub: Option<Arc<AtomicBool>>,
}

fn serve<R: Read + Send + 'static, W: Write + Send + 'static>(sh: Arc<Shared>, r: R, w: W) {
    let out: Out = Arc::new(Mutex::new(Box::new(w)));
    let mut conn = Conn { authed: sh.settings.token.is_none(), sub: None };
    let mut rd = BufReader::new(r);
    loop {
        let mut line = String::new();
        match rd.by_ref().take(1 << 20).read_line(&mut line) {
            Ok(0) | Err(_) => break,
            Ok(_) => {}
        }
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let req: Value = match serde_json::from_str(line) {
            Ok(v) => v,
            Err(e) => {
                send(&out, &json!({"ok": false, "error": format!("not JSON: {e}")}));
                continue;
            }
        };
        let id = req.get("id").cloned();
        let mut resp = match handle(&sh, &mut conn, &out, &req) {
            Ok(Value::Object(mut m)) => {
                m.insert("ok".into(), json!(true));
                Value::Object(m)
            }
            Ok(v) => json!({"ok": true, "value": v}),
            Err(e) => json!({"ok": false, "error": e}),
        };
        if let (Some(id), Some(m)) = (id, resp.as_object_mut()) {
            m.insert("id".into(), id);
        }
        if !send(&out, &resp) {
            break;
        }
    }
    if let Some(s) = conn.sub {
        s.store(false, Ordering::Relaxed);
    }
}

fn num(v: &Value, key: &str) -> Option<u64> {
    match v.get(key)? {
        Value::Number(n) => n.as_u64(),
        Value::String(s) => s.strip_prefix("0x").map_or_else(|| s.parse().ok(), |h| u64::from_str_radix(h, 16).ok()),
        _ => None,
    }
}

fn keys_of(req: &Value) -> Result<u32, String> {
    match req.get("keys") {
        Some(Value::String(s)) => inject::parse_keys(s),
        Some(Value::Array(a)) => a.iter().map(|k| inject::parse_keys(k.as_str().unwrap_or(""))).try_fold(0, |x, k| k.map(|k| x | k)),
        _ => Err("`keys` is required (\"A\", \"A+B\" or [\"A\",\"B\"])".into()),
    }
}

fn app_call(sh: &Shared, name: &str, args: Value, timeout: Duration) -> Result<Value, String> {
    let (tx, rx) = channel();
    sh.app.lock().unwrap().send(AppCall { name: name.into(), args, reply: tx }).map_err(|_| "the app is gone".to_string())?;
    rx.recv_timeout(timeout).map_err(|_| format!("the app did not answer `{name}`"))?
}

fn need_session() -> Result<super::LocalInfo, String> {
    let l = super::local();
    if l.session == "none" {
        Err("no session is running (start one: `start_offline`)".into())
    } else {
        Ok(l)
    }
}

fn state_value(fresh: bool) -> Result<Value, String> {
    if fresh {
        let _ = super::ask_console(CoreReq::State, Duration::from_secs(2));
    }
    match super::latest() {
        Some(l) => {
            let mut v = l.json.clone();
            if let Some(m) = v.as_object_mut() {
                m.insert("age_ms".into(), json!(l.at.elapsed().as_millis() as u64));
            }
            Ok(v)
        }
        None => Ok(json!({"phase": "none", "screen": "none", "mode": "none", "local": {"session": super::local().session}})),
    }
}

fn pick_fields(v: Value, fields: Option<&Vec<Value>>) -> Value {
    match (v, fields) {
        (Value::Object(m), Some(f)) => {
            Value::Object(m.into_iter().filter(|(k, _)| f.iter().any(|x| x.as_str() == Some(k)) || k == "tick" || k == "frame").collect())
        }
        (v, _) => v,
    }
}

fn handle(sh: &Arc<Shared>, conn: &mut Conn, out: &Out, req: &Value) -> Result<Value, String> {
    let cmd = req.get("cmd").and_then(Value::as_str).ok_or("`cmd` is required")?;
    if cmd == "auth" {
        if sh.settings.token.as_deref() == req.get("token").and_then(Value::as_str) {
            conn.authed = true;
            return Ok(json!({}));
        }
        return Err("bad token".into());
    }
    if !conn.authed {
        if sh.settings.token.as_deref() == req.get("token").and_then(Value::as_str) {
            conn.authed = true;
        } else {
            return Err("token required (send {\"cmd\":\"auth\",\"token\":...} first)".into());
        }
    }
    let local = super::local();
    let online = local.session == "online";
    match cmd {
        "ping" => Ok(json!({"pong": true})),
        "hello" => Ok(json!({
            "protocol": super::PROTOCOL,
            "app": "tangoAW2",
            "version": sh.settings.app_version,
            "session": local.session,
            "seat": local.seat,
            "test_mode": sh.settings.test_mode,
            "write_online": sh.settings.write_online,
            "token_required": sh.settings.token.is_some(),
            "checkpoint_dir": super::checkpoint_dir().display().to_string(),
            "commands": COMMANDS,
        })),
        "state" => {
            let v = state_value(req.get("fresh").and_then(Value::as_bool).unwrap_or(false))?;
            let v = pick_fields(v, req.get("fields").and_then(Value::as_array));
            Ok(json!({"state": v}))
        }
        "press" | "goto" | "hold" | "release" => {
            let l = need_session()?;
            if let Some(seat) = num(req, "seat") {
                if online && seat as usize != l.seat {
                    return Err(format!("this window is seat {}: a client drives its own peer (give seat {} its own port)", l.seat, seat));
                }
            }
            match cmd {
                "press" => {
                    let keys = keys_of(req)?;
                    let frames = num(req, "frames").unwrap_or(8).clamp(1, 3600) as u32;
                    let (tx, rx) = channel();
                    let wait = req.get("wait").and_then(Value::as_bool).unwrap_or(true);
                    super::with_injector(|i| i.press(keys, frames, wait.then_some(tx)));
                    if wait {
                        rx.recv_timeout(Duration::from_secs_f64(frames as f64 / 60.0 + 10.0)).map_err(|_| "the press did not finish (is the app polling?)".to_string())?;
                    }
                    Ok(json!({"keys": keys, "frames": frames, "seat": l.seat, "note": "a seat that is waiting has its keys dropped by the console"}))
                }
                "hold" => {
                    super::with_injector(|i| i.hold(keys_of(req).unwrap_or(0)));
                    keys_of(req).map(|k| json!({"held": k}))
                }
                "release" => {
                    let keys = if req.get("keys").is_some() { keys_of(req)? } else { u32::MAX };
                    super::with_injector(|i| i.release(keys));
                    Ok(json!({}))
                }
                _ => {
                    let (x, y) = (num(req, "x").ok_or("`x` is required")?, num(req, "y").ok_or("`y` is required")?);
                    let secs = req.get("timeout").and_then(Value::as_f64).unwrap_or(30.0);
                    let (tx, rx) = channel();
                    super::with_injector(|i| i.goto(x as u16, y as u16, Duration::from_secs_f64(secs), Some(tx)));
                    match rx.recv_timeout(Duration::from_secs_f64(secs + 5.0)) {
                        Ok(inject::Outcome::Done) => Ok(json!({"x": x, "y": y})),
                        Ok(inject::Outcome::TimedOut(cx, cy)) => Err(format!("the cursor stopped at ({cx},{cy}) (not on the map, or the keys are being dropped)")),
                        Err(_) => Err("goto did not finish".into()),
                    }
                }
            }
        }
        "type" => {
            need_session()?;
            app_call(sh, "type", json!({"text": req.get("text").and_then(Value::as_str).ok_or("`text` is required")?}), Duration::from_secs(5))
        }
        "wait_until" => {
            let cond = req.get("cond").ok_or("`cond` is required")?;
            let secs = req.get("timeout").and_then(Value::as_f64).unwrap_or(30.0);
            let start = Instant::now();
            // (a malformed condition is told at once)
            cond::matches(&json!({}), cond)?;
            loop {
                if let Some(l) = super::latest() {
                    if cond::matches(&l.json, cond)? {
                        let j = &l.json;
                        return Ok(json!({
                            "matched": true, "waited_ms": start.elapsed().as_millis() as u64,
                            "state": {"phase": j["phase"], "screen": j["screen"], "active_army": j["active_army"], "day": j["day"], "tick": j["tick"], "frame": j["frame"]},
                        }));
                    }
                }
                if start.elapsed().as_secs_f64() > secs {
                    let j = super::latest().map(|l| l.json.clone()).unwrap_or(Value::Null);
                    return Err(format!(
                        "timeout after {secs}s; at {} / {} (army {}, day {})",
                        j["phase"], j["screen"], j["active_army"], j["day"]
                    ));
                }
                super::wait_changed(Duration::from_millis(100));
            }
        }
        "screenshot" => {
            need_session()?;
            let r = app_call(sh, "screenshot", json!({"raw": req.get("raw").and_then(Value::as_bool).unwrap_or(false)}), Duration::from_secs(10))?;
            if let Some(path) = req.get("path").and_then(Value::as_str) {
                let png = r["png_b64"].as_str().and_then(b64_decode).ok_or("no picture")?;
                std::fs::write(path, &png).map_err(|e| format!("{path}: {e}"))?;
                let mut r = r;
                r.as_object_mut().map(|m| m.remove("png_b64"));
                r["path"] = json!(path);
                return Ok(r);
            }
            Ok(r)
        }
        "peek" => {
            let addr = num(req, "addr").ok_or("`addr` is required")? as u32;
            let len = num(req, "len").unwrap_or(16).clamp(1, 0x10000) as usize;
            super::ask_console(CoreReq::Peek { addr, len }, Duration::from_secs(3))
        }
        "poke" => {
            let addr = num(req, "addr").ok_or("`addr` is required")? as u32;
            let hex = req.get("hex").and_then(Value::as_str).ok_or("`hex` is required (bytes as hex)")?;
            if hex.len() % 2 != 0 || hex.len() > 0x20000 {
                return Err("`hex` is an even number of hex digits".into());
            }
            let bytes: Vec<u8> = (0..hex.len() / 2).map(|i| u8::from_str_radix(&hex[2 * i..2 * i + 2], 16).map_err(|_| "bad hex".to_string())).collect::<Result<_, _>>()?;
            if online {
                let force = req.get("force_offline").and_then(Value::as_bool).unwrap_or(false);
                if !(force && sh.settings.write_online) {
                    return Err("refused: this is an online match and a poke desyncs the peers. (Only with TANGOAW2_AI_DEBUG_WRITE=1 and \"force_offline\":true, on this peer alone.)".into());
                }
            }
            super::ask_console(CoreReq::Poke { addr, bytes }, Duration::from_secs(3))
        }
        "hash" => super::ask_console(CoreReq::Hash, Duration::from_secs(3)),
        "proc_list" => super::ask_console(CoreReq::Procs, Duration::from_secs(3)),
        "log_tail" => Ok(json!({"lines": super::log_tail(num(req, "lines").unwrap_or(50).min(2000) as usize)})),
        "checkpoint_save" => {
            let name = req.get("name").and_then(Value::as_str).ok_or("`name` is required")?;
            super::ask_console(CoreReq::CheckpointSave { name: name.into() }, Duration::from_secs(10))
        }
        "checkpoint_load" => {
            if online {
                return Err("checkpoint_load is offline only (see the README for the online scenario)".into());
            }
            let name = req.get("name").and_then(Value::as_str).ok_or("`name` is required")?;
            super::ask_console(CoreReq::CheckpointLoad { name: name.into() }, Duration::from_secs(10))
        }
        "checkpoint_list" => Ok(json!({"dir": super::checkpoint_dir().display().to_string(), "checkpoints": super::checkpoint_list(&super::checkpoint_dir())})),
        "start_offline" => {
            if online {
                return Err("a session is running".into());
            }
            app_call(sh, "start_offline", json!({}), Duration::from_secs(5))
        }
        "inject" => {
            if !sh.settings.test_mode {
                return Err("refused: `inject` needs the app started with TANGOAW2_AI_DEBUG_TEST=1 (offline/test use only)".into());
            }
            app_call(sh, "inject", req.clone(), Duration::from_secs(5))
        }
        "net" => {
            let v = state_value(false)?;
            Ok(json!({"link": v["link"], "online": v["online"], "local": v["local"]}))
        }
        "events" => {
            let after = num(req, "after").unwrap_or(0);
            let evs = super::events_after(after, 500);
            Ok(json!({"events": evs.iter().map(|(id, e)| with_eid(e, *id)).collect::<Vec<_>>(), "last": super::last_event_id()}))
        }
        "subscribe" => {
            if let Some(old) = conn.sub.take() {
                old.store(false, Ordering::Relaxed);
            }
            let filter: Option<Vec<String>> = req.get("events").and_then(Value::as_array).map(|a| a.iter().filter_map(|x| x.as_str().map(String::from)).collect());
            let from = num(req, "after").unwrap_or_else(super::last_event_id);
            let alive = Arc::new(AtomicBool::new(true));
            conn.sub = Some(alive.clone());
            let out = out.clone();
            std::thread::Builder::new().name("ai-debug-events".into()).spawn(move || {
                let mut last = from;
                while alive.load(Ordering::Relaxed) {
                    for (id, e) in super::events_after(last, 200) {
                        last = id;
                        let kind = e["event"].as_str().unwrap_or("");
                        if filter.as_ref().is_some_and(|f| !f.iter().any(|k| k == kind)) {
                            continue;
                        }
                        if !send(&out, &with_eid(&e, id)) {
                            return;
                        }
                    }
                    super::wait_changed(Duration::from_millis(250));
                }
            })
            .map_err(|e| e.to_string())?;
            Ok(json!({"subscribed": true, "from": from, "kinds": EVENT_KINDS}))
        }
        "unsubscribe" => {
            if let Some(s) = conn.sub.take() {
                s.store(false, Ordering::Relaxed);
            }
            Ok(json!({}))
        }
        other => Err(format!("unknown command `{other}`")),
    }
}

fn with_eid(e: &Value, id: u64) -> Value {
    let mut v = e.clone();
    if let Some(m) = v.as_object_mut() {
        m.insert("eid".into(), json!(id));
    }
    v
}

fn b64_decode(s: &str) -> Option<Vec<u8>> {
    let val = |c: u8| -> Option<u32> {
        Some(match c {
            b'A'..=b'Z' => c - b'A',
            b'a'..=b'z' => c - b'a' + 26,
            b'0'..=b'9' => c - b'0' + 52,
            b'+' => 62,
            b'/' => 63,
            _ => return None,
        } as u32)
    };
    let b: Vec<u8> = s.bytes().filter(|&c| c != b'=').collect();
    let mut out = Vec::new();
    for c in b.chunks(4) {
        let mut n = 0u32;
        for (i, &x) in c.iter().enumerate() {
            n |= val(x)? << (18 - 6 * i);
        }
        out.push((n >> 16) as u8);
        if c.len() > 2 {
            out.push((n >> 8) as u8);
        }
        if c.len() > 3 {
            out.push(n as u8);
        }
    }
    Some(out)
}

pub const COMMANDS: [&str; 25] = [
    "hello", "ping", "auth", "state", "press", "hold", "release", "type", "goto", "wait_until", "screenshot", "peek", "poke", "hash",
    "proc_list", "log_tail", "checkpoint_save", "checkpoint_load", "checkpoint_list", "start_offline", "inject", "events", "subscribe",
    "unsubscribe", "net",
];

pub const EVENT_KINDS: [&str; 9] = ["scene", "turn", "act", "hash", "error", "rollback", "link", "migration", "rejoin"];

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpStream;

    #[test]
    fn base64_round_trips() {
        for n in 0..10 {
            let d: Vec<u8> = (0..n as u8).collect();
            assert_eq!(b64_decode(&b64(&d)).unwrap(), d);
        }
        assert_eq!(b64(b"Man"), "TWFu");
    }

    fn ask(s: &mut BufReader<TcpStream>, w: &mut TcpStream, req: Value) -> Value {
        writeln!(w, "{req}").unwrap();
        let mut line = String::new();
        s.read_line(&mut line).unwrap();
        serde_json::from_str(&line).unwrap()
    }

    #[test]
    fn a_client_talks_to_the_server_and_the_token_is_enforced() {
        let (tx, _rx) = channel();
        let at = start(
            Settings { listen: "0".into(), token: Some("sekrit".into()), test_mode: false, write_online: false, app_version: "t".into() },
            tx,
        )
        .unwrap();
        assert!(at.starts_with("127.0.0.1:"));
        let c = TcpStream::connect(&at).unwrap();
        let mut w = c.try_clone().unwrap();
        let mut r = BufReader::new(c);
        let a = ask(&mut r, &mut w, json!({"id": 1, "cmd": "state"}));
        assert_eq!(a["ok"], false);
        assert_eq!(a["id"], 1);
        assert_eq!(ask(&mut r, &mut w, json!({"cmd": "auth", "token": "nope"}))["ok"], false);
        assert_eq!(ask(&mut r, &mut w, json!({"cmd": "auth", "token": "sekrit"}))["ok"], true);
        let a = ask(&mut r, &mut w, json!({"id": "x", "cmd": "state"}));
        assert_eq!(a["ok"], true);
        assert_eq!(a["state"]["phase"], "none");
        // inject is refused outside test mode, peek needs a console
        assert_eq!(ask(&mut r, &mut w, json!({"cmd": "inject", "op": "clear"}))["ok"], false);
        let a = ask(&mut r, &mut w, json!({"cmd": "bogus"}));
        assert!(a["error"].as_str().unwrap().contains("unknown"));
    }

    #[test]
    fn the_server_listens_on_loopback_only() {
        let (tx, _rx) = channel();
        let at = start(Settings { listen: "0".into(), token: None, test_mode: false, write_online: false, app_version: String::new() }, tx).unwrap();
        assert!(at.starts_with("127.0.0.1:"), "{at}");
    }
}
