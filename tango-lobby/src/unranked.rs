//! UNRANKED discovery: look for a random opponent in a pool, no server of our own.
//!
//! The public matchmaking server pairs the first two clients that connect with the same session id
//! ([`unranked_session`]); the two draw lots over the link (the lower number hosts) and play a room of two
//! ([`super::Room::unranked`]).

use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio_util::sync::CancellationToken;

use super::{fail, guest_session, serve_guest, start_room, Inner, RoomPhase, FIRST_WORDS};
use tango_net_protocol::control::{room_password_hash, Packet, RoomJoin, RoomMsg};

/// How long an UNRANKED search goes on before it says nobody else is looking.
const SEARCH_DEADLINE: Duration = Duration::from_secs(300);

/// The matchmaking session id of the UNRANKED pool: the first two players to connect with it are paired. Players on
/// different simulations never meet (their sim version is part of the id), so nobody is paired to a match that cannot
/// be played.
pub fn unranked_session(sim_version: u32) -> String {
    format!("tangoaw2-unranked-v1-s{sim_version}")
}

/// Look for an opponent in the pool; the two paired draw lots and play a room of two.
pub(super) async fn unranked_main(inner: Arc<Mutex<Inner>>, cancel: CancellationToken) {
    let (endpoint, use_relay, session, join) = {
        let mut g = inner.lock().unwrap();
        g.message = "Looking for an opponent...".into();
        // (READY at once: the pairing is the agreement to play)
        g.my_ready = true;
        let sim = g.params.game_info.as_ref().map_or(0, |i| i.sim_version);
        (
            g.params.endpoint.clone(),
            g.params.use_relay,
            unranked_session(sim),
            RoomJoin {
                nickname: g.params.nickname.clone(),
                password: room_password_hash(&g.params.code, &g.params.password),
                game_info: g.params.game_info.clone(),
                content: g.params.content,
                saves: Vec::new(),
            },
        )
    };
    let deadline = web_time::Instant::now() + SEARCH_DEADLINE;
    let (mut channels, theirs, mine) = loop {
        let left = deadline.saturating_duration_since(web_time::Instant::now());
        if left.is_zero() {
            fail(&inner, "Nobody else is looking.");
            return;
        }
        let route = tango_net::connect::Route::Matchmaking {
            endpoint: &endpoint,
            session_id: &session,
            use_relay,
        };
        let opened = tokio::select! {
            _ = cancel.cancelled() => return,
            r = tango_platform::timeout(left, tango_net::open_channels(route, |_| {})) => r,
        };
        let mut channels = match opened {
            Err(_) => {
                fail(&inner, "Nobody else is looking.");
                return;
            }
            Ok(Ok(c)) => c,
            Ok(Err(tango_net::ConnectError::Signaling(e))) => {
                let text = format!("{e}");
                log::warn!("unranked: the matchmaking server: {text}");
                if text.contains("Websocket") || text.contains("Io") {
                    fail(&inner, "Server cannot be reached.");
                    return;
                }
                tokio::select! {
                    _ = cancel.cancelled() => return,
                    _ = tango_platform::sleep(Duration::from_secs(1)) => {}
                }
                continue;
            }
            Ok(Err(e)) => {
                log::warn!("unranked: could not connect: {e}");
                tokio::select! {
                    _ = cancel.cancelled() => return,
                    _ = tango_platform::sleep(Duration::from_millis(700)) => {}
                }
                continue;
            }
        };
        // Paired. Draw lots.
        let mine: u64 = rand::random();
        if channels.control.0.send_packet(&Packet::Room(RoomMsg::Pool(mine))).await.is_err() {
            continue;
        }
        match tango_platform::timeout(FIRST_WORDS, channels.control.1.receive()).await {
            Ok(Ok(Packet::Room(RoomMsg::Pool(theirs)))) if theirs != mine => break (channels, theirs, mine),
            _ => {
                log::info!("unranked: the pairing did not hold; looking again");
                continue;
            }
        }
    };
    log::info!("unranked: paired; {} hosts", if mine < theirs { "this peer" } else { "the other" });
    {
        let mut g = inner.lock().unwrap();
        g.message.clear();
        g.phase = RoomPhase::Open;
        g.host = mine < theirs;
    }
    if mine < theirs {
        // The host: the guest's Join comes next. Start as soon as it is in and READY.
        let (inner2, cancel2) = (inner.clone(), cancel.clone());
        tango_platform::spawn(async move { serve_guest(inner2, cancel2, channels).await });
        let mut seen_guest = false;
        let paired = web_time::Instant::now();
        loop {
            let gone = {
                let g = inner.lock().unwrap();
                if g.started || matches!(g.phase, RoomPhase::Failed | RoomPhase::Closed) {
                    return;
                }
                seen_guest |= !g.peers.is_empty();
                seen_guest && g.peers.is_empty()
            };
            if gone || (!seen_guest && paired.elapsed() > FIRST_WORDS * 2) {
                fail(&inner, if gone { "The other player left." } else { "The other player left." });
                return;
            }
            start_room(&inner, &cancel);
            tokio::select! {
                _ = cancel.cancelled() => return,
                _ = tango_platform::sleep(Duration::from_millis(100)) => {}
            }
        }
    } else {
        if channels.control.0.send_packet(&Packet::Room(RoomMsg::Join(join))).await.is_err() {
            fail(&inner, "The other player left.");
            return;
        }
        match tango_platform::timeout(FIRST_WORDS, channels.control.1.receive()).await {
            Ok(Ok(Packet::Room(RoomMsg::Welcome(w)))) | Ok(Ok(Packet::Room(RoomMsg::Roster(w)))) => {
                guest_session(inner, cancel, channels, w).await;
            }
            Ok(Ok(Packet::Room(RoomMsg::Reject(r)))) => fail(&inner, r.text),
            _ => fail(&inner, "The other player left."),
        }
    }
}
