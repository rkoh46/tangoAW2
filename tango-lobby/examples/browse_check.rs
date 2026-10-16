//! Harness-free check of the public lobby list against the real relays: announces two lobbies (one with a password)
//! for a while and lists them from a second client. `cargo run -p tango-lobby --example browse_check [seconds]`.
use tango_lobby::browse::{Announcer, Browse, Compat, Lobby, RELAYS};

#[tokio::main]
async fn main() {
    let env = std::env::var("RELAYS").unwrap_or_default();
    let relays: Vec<&str> = if env.is_empty() { RELAYS.to_vec() } else { env.split(',').collect() };
    let relays = &relays[..];
    env_logger::Builder::new().filter_level(log::LevelFilter::Info).init();
    let secs: u64 = std::env::args().nth(1).and_then(|s| s.parse().ok()).unwrap_or(40);
    let lobby = |code: &str, locked| Lobby {
        code: code.into(),
        host: if locked { "LockedHost" } else { "OpenHost" }.into(),
        players: 1,
        max: 5,
        locked,
        version: "check".into(),
        pack: true,
    };
    let a = Announcer::start(relays, lobby("TEST01", false));
    let b = Announcer::start(relays, lobby("TEST02", true));
    let list = Browse::start(relays, Compat { version: "check".into(), pack: true });
    let t0 = std::time::Instant::now();
    let mut first = None;
    while t0.elapsed().as_secs() < secs {
        tokio::time::sleep(std::time::Duration::from_secs(2)).await;
        let l = list.listings();
        if l.len() >= 2 && first.is_none() {
            first = Some(t0.elapsed());
        }
        println!(
            "{:>3}s announce {:?} / {:?} browse {:?} listed {:?}",
            t0.elapsed().as_secs(),
            a.stats(),
            b.stats(),
            list.stats(),
            l.iter().map(|x| format!("{}:{}{}", x.lobby.code, x.lobby.host, if x.lobby.locked { "*" } else { "" })).collect::<Vec<_>>()
        );
    }
    println!("both lobbies first listed after {first:?}");
    // Withdraw one: it must leave the list.
    drop(b);
    for _ in 0..4 {
        tokio::time::sleep(std::time::Duration::from_secs(2)).await;
        println!("after withdrawing TEST02: {:?}", list.listings().iter().map(|x| x.lobby.code.clone()).collect::<Vec<_>>());
    }
    drop(a);
    tokio::time::sleep(std::time::Duration::from_secs(3)).await;
    println!("after withdrawing both: {:?}", list.listings().iter().map(|x| x.lobby.code.clone()).collect::<Vec<_>>());
}
