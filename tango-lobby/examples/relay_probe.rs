//! Probes public Nostr relays for the lobby list: for each (`RELAYS=a,b` or the defaults and a few more) connects,
//! publishes one announcement, then asks for it the way the browser does and prints what happened and how long it
//! took. `cargo run -p tango-lobby --example relay_probe`.
use futures::{SinkExt, StreamExt};
use serde_json::{json, Value};
use std::time::{Duration, Instant};
use tango_lobby::browse::{make_event, read_event, Lobby, KIND, RELAYS, TAG};
use tokio_tungstenite::tungstenite::Message;

const EXTRA: &[&str] = &[
    "wss://relay.nostr.band",
    "wss://nostr.bitcoiner.social",
    "wss://relay.nostrplebs.com",
    "wss://purplepag.es",
    "wss://relay.mostr.pub",
    "wss://nostr.fmt.wiz.biz",
    "wss://relay.0xchat.com",
    "wss://nostr-01.yakihonne.com",
    "wss://relay.nostr.bg",
    "wss://nostr.einundzwanzig.space",
    "wss://relay.nostrdice.com",
    "wss://relay.lexingtonbitcoin.org",
    "wss://nostr.data.haus",
    "wss://relay.illuminodes.com",
    "wss://relay.coinos.io",
    "wss://nostr.zebedee.cloud",
];

async fn probe(url: String, code: String) -> String {
    let t0 = Instant::now();
    let ms = |t: Instant| t.elapsed().as_millis();
    let conn = tokio::time::timeout(Duration::from_secs(8), tokio_tungstenite::connect_async(url.as_str())).await;
    let mut ws = match conn {
        Err(_) => return format!("{url:38} connect TIMEOUT"),
        Ok(Err(e)) => return format!("{url:38} connect ERR {e}"),
        Ok(Ok((ws, _))) => ws,
    };
    let c = ms(t0);
    let key = k256::schnorr::SigningKey::from_bytes(&rand::random::<[u8; 32]>()).unwrap();
    let now = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs();
    let lobby = Lobby { code: code.clone(), host: "Probe".into(), name: "Probe room".into(), players: 1, max: 5, locked: false, version: "probe".into(), pack: true };
    let ev = make_event(&key, &code, Some(&lobby), now);
    let _ = ws.send(Message::Text(json!(["EVENT", ev]).to_string())).await;
    let tp = Instant::now();
    let mut ok = String::from("no OK");
    let mut seen_event = None;
    let mut eose = None;
    let mut sent_req = false;
    let mut notices = vec![];
    let deadline = Instant::now() + Duration::from_secs(10);
    while Instant::now() < deadline {
        let m = tokio::time::timeout(Duration::from_millis(500), ws.next()).await;
        if let Ok(Some(Ok(Message::Text(t)))) = m {
            let v: Value = serde_json::from_str(&t).unwrap_or(Value::Null);
            match v.get(0).and_then(Value::as_str) {
                Some("OK") => {
                    ok = format!("OK {} {:?} in {}ms", v[2], v[3].as_str().unwrap_or(""), ms(tp));
                    if !sent_req {
                        sent_req = true;
                        let req = json!(["REQ", "lobbies", {"kinds": [KIND], "#t": [TAG], "since": now.saturating_sub(60)}]);
                        let _ = ws.send(Message::Text(req.to_string())).await;
                    }
                }
                Some("EVENT") => {
                    if let Ok((_, d, _, _)) = read_event(&v[2]) {
                        if d == code && seen_event.is_none() {
                            seen_event = Some(ms(tp));
                        }
                    }
                }
                Some("EOSE") => eose = Some(ms(tp)),
                Some("NOTICE") | Some("CLOSED") | Some("AUTH") => notices.push(t.chars().take(80).collect::<String>()),
                _ => {}
            }
            if seen_event.is_some() && eose.is_some() {
                break;
            }
        }
        if !sent_req && ok == "no OK" && tp.elapsed().as_secs() >= 4 {
            sent_req = true;
            let req = json!(["REQ", "lobbies", {"kinds": [KIND], "#t": [TAG], "since": now.saturating_sub(60)}]);
            let _ = ws.send(Message::Text(req.to_string())).await;
        }
    }
    format!("{url:38} conn {c}ms | {ok} | req returned it: {seen_event:?} EOSE: {eose:?} {notices:?}")
}

#[tokio::main]
async fn main() {
    let env = std::env::var("RELAYS").unwrap_or_default();
    let list: Vec<String> = if env.is_empty() {
        RELAYS.iter().chain(EXTRA.iter()).map(|s| s.to_string()).collect()
    } else {
        env.split(',').map(String::from).collect()
    };
    let mut tasks = vec![];
    for (k, u) in list.into_iter().enumerate() {
        tasks.push(tokio::spawn(probe(u, format!("PRB{:03}", k))));
    }
    for t in tasks {
        println!("{}", t.await.unwrap());
    }
}
