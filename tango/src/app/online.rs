//! tangoAW2's in-game lobby, the app's half (the game's is
//! `tango_gamesupport_aw2::online`): while the game is played alone, its mailbox
//! is read every frame. A room made or joined there is a [`netplay::room::Room`]
//! (up to five players: the host dials for guests through the matchmaking
//! server, every guest has a link of its own to the host): the connection's
//! progress and the players are written back for the game to show, READY in the
//! game is the guest's ready and the host's START starts the match for everyone.
//! When the match ends (the host leaves SELECT MAP, a player quits, or a link
//! drops) the game is booted again, straight to its LOBBY menu, with how it
//! ended.

use super::{App, Message};
use crate::unranked_live;
use crate::{netplay, session, tabs};
use netplay::room::{Room, RoomParams, RoomPhase};
use tango_library::online::{self as mailbox, Request, Status};

// (the room's host draws the UNRANKED map pick into the same bit the game reads)
const _: () = assert!(
    tango_net_protocol::control::UNRANKED_PICK_GUEST == tango_library::online::UNRANKED_PICK_GUEST
);

/// What the app knows of the in-game lobby.
#[derive(Default)]
pub struct Flow {
    /// The last request handled.
    seen: Option<u8>,
    /// The room this player made or joined.
    room: Option<Room>,
    /// The room's match is being built.
    building: bool,
    /// A lobby-made match is running (its end brings the game back).
    in_match: bool,
    /// ...and it is an UNRANKED one (its end is logged: the hook for the stats).
    unranked_match: bool,
    /// Said on the LOBBY menu when the game comes back.
    back_message: Option<String>,
    /// The public announcement of the room this player made (withdrawn when the match starts or the room closes).
    announcer: Option<netplay::browse::Announcer>,
    /// The look at the public lobby list, while the game's lobby browser is open.
    browse: Option<(netplay::browse::Browse, std::time::Instant)>,
    /// When the game left the lobby browser (the look then goes on for a while, so that opening it again shows
    /// the list at once instead of searching again).
    browse_left: Option<std::time::Instant>,
    /// The lobbies in the order they were first seen (so the list does not shuffle at every refresh).
    browse_order: Vec<String>,
    /// What was last logged of the list.
    browse_logged: Vec<String>,
    /// Test aid (`TANGOAW2_ONLINE_LOG=1`): when the state was last logged.
    last_log: Option<std::time::Instant>,
    /// The Connection status: when the menu's polite refresh last ran, what was last written, the level before.
    conn_refreshed: Option<std::time::Instant>,
    conn_written: Option<(u8, Vec<String>)>,
    conn_checked_at: Option<std::time::Instant>,
    conn_level: u8,
    /// The online record (loaded when first needed), and a count of its changes (the console's copy of its page).
    stats: Option<super::online_stats::Stats>,
    stats_rev: u32,
    synced_rev: u32,
    /// This peer's seat and the room's players' gamertags, for judging the match's battles.
    match_seat: usize,
    match_names: Vec<String>,
    /// The number of the last battle recorded (a battle noted twice, after a rollback, is recorded once).
    last_battle: Option<u8>,
    typed_test: bool,
    /// The matches cut short that are saved (the RESUME page's list, newest first), read again when the page
    /// is opened and when one is deleted or saved.
    saved: Vec<tango_match::SuspendedMatch>,
    saved_dirty: bool,
    in_saved_menu: bool,
    /// The saved match this session resumed (deleted when it ends the way a match does).
    resumed: Option<u64>,
    /// Who disconnected, as the session last said (it is gone when the match ends).
    dropped: Option<String>,
    /// Set by the session's sink when it has kept the match.
    kept: std::sync::Arc<std::sync::atomic::AtomicBool>,
    /// UNRANKED crash recovery. The match that is on (its file on disk is touched while it runs), when it was last touched,
    /// the match this app crashed out of that may still be on (offered on the ONLINE screen), the player returning to it,
    /// and the player who stayed, waiting for the other to come back.
    live: Option<unranked_live::Live>,
    live_touched: Option<std::time::Instant>,
    live_pending: Option<unranked_live::Live>,
    offer: Option<unranked_live::Live>,
    returning: Option<Returning>,
    stayed: Option<Stayed>,
}

/// A player coming back to an UNRANKED match its app crashed out of.
struct Returning {
    /// Giving the match up: the room is joined only to tell the other player, then left.
    giving_up: bool,
    ready_sent: bool,
}

/// The player who stayed in an UNRANKED match while the other is waited for: a room (a resumed match's, the newest settled state
/// of the console) the returning player joins.
#[derive(Default)]
struct Stayed {
    asked: bool,
    room: Option<Room>,
    guest_seen: bool,
    /// How many goodbyes of returning players the room had when it was made (more means one gave the match up).
    leaves_seen: u32,
    since: Option<std::time::Instant>,
}

fn row_of(m: &tango_match::SuspendedMatch) -> mailbox::SavedRow {
    let info = m.info();
    mailbox::SavedRow {
        players: m.players.join(", "),
        map: info.map,
        tail: format!("Day {} {}", info.day.min(99), crate::suspended::date(m.saved_at)),
    }
}

impl App {
    /// Every session frame: the in-game lobby's mailbox, and the way back from a
    /// match it made.
    pub(super) fn online_tick(&mut self) -> iced::Task<Message> {
        // (a match starting, or a room closing, withdraws the public lobby whatever the game is doing)
        self.online_announce();
        // A lobby-made match just ended: back to the game, at its lobby.
        if self.online.in_match && !self.session.is_active() {
            self.online_record_battles();
            self.online.in_match = false;
            self.online_live_end();
            // (a later game without a room has no gamertags to show)
            tango_library::online::set_room(Vec::new(), 0);
            self.online.room = None;
            self.online.seen = None;
            let dropped = self.online.dropped.take();
            let kept = self.online.kept.swap(false, std::sync::atomic::Ordering::AcqRel);
            let resumed = self.online.resumed.take();
            let unranked_was = self.online.unranked_match;
            let how = match self.session.results.take() {
                Some(r) if r.end == session::results::MatchEnd::Disconnected => {
                    let who = r.dropped.clone().or(dropped).filter(|n| !n.is_empty()).unwrap_or_else(|| "A player".to_string());
                    if kept {
                        self.online.saved_dirty = true;
                        format!("{who} disconnected - match saved. Resume it from ONLINE > RESUME")
                    } else {
                        format!("{who} disconnected.")
                    }
                }
                Some(r) => {
                    // (a resumed match that was played to its end is done with)
                    if let Some(id) = resumed {
                        crate::suspended::delete(&self.config.data_path, id);
                        self.online.saved_dirty = true;
                    }
                    if r.everyone_left && unranked_was {
                        // (UNRANKED: the opponent's army yielded and the battle was won: the record has it)
                        "Your opponent left. The match is over.".to_string()
                    } else if r.everyone_left {
                        // (the room fell to one player: the match is over, and why)
                        "Everyone else left the room. The match is over.".to_string()
                    } else {
                        "The match is over.".to_string()
                    }
                }
                None => "You left the match.".to_string(),
            };
            if std::mem::take(&mut self.online.unranked_match) {
                log::info!("unranked: the match ended ({how})");
            }
            self.online.back_message = Some(how);
            mailbox::boot_to_lobby();
            return self.update_play(tabs::play::Message::PlayOfflinePressed);
        }
        self.online_record_battles();
        if let Some(pvp) = self.session.active_as::<session::pvp::PvpSession>() {
            if let Some(name) = pvp.dropped_player() {
                self.online.dropped = Some(name);
            }
            if std::env::var("TANGOAW2_ONLINE_LOG").is_ok_and(|v| v == "1")
                && self.online.last_log.is_none_or(|t| t.elapsed().as_secs() >= 1)
            {
                self.online.last_log = Some(std::time::Instant::now());
                log::info!(
                    "match state: probe {:#x} list {:#x} map {:#x}",
                    tango_library::online::probe_bits(),
                    tango_library::online::list_debug(),
                    tango_library::online::map_debug()
                );
            }
            return self.online_unranked_tick();
        }
        self.online_stats();
        let Some(solo) = self.session.active_as::<session::singleplayer::SinglePlayerSession>() else {
            // (no game: no look at the lobby list)
            self.online.browse = None;
            return iced::Task::none();
        };
        let mut read = |a: u32, b: &mut [u8]| {
            solo.peek(a, b);
        };
        // A console just started: it gets the gamertag and the record's page.
        let fresh = mailbox::needs_sync(&mut read);
        if fresh || self.online.synced_rev != self.online.stats_rev {
            let tag = mailbox::clean_gamertag(&self.config.gamertag.clone().unwrap_or_default());
            let lines = self.online.stats.as_ref().map(|s| s.lines()).unwrap_or_default();
            let mut write = |a: u32, b: &[u8]| {
                solo.poke(a, b);
            };
            mailbox::sync(&mut write, &tag, &lines);
            self.online.synced_rev = self.online.stats_rev;
            // (an UNRANKED match this app crashed out of is offered on the ONLINE screen of the console that comes up)
            if fresh && self.online.offer.is_some() {
                mailbox::write_rejoin(&mut write, 1);
            }
        }
        if std::env::var("TANGOAW2_ONLINE_LOG").is_ok_and(|v| v == "1")
            && self.online.last_log.is_none_or(|t| t.elapsed().as_secs() >= 1)
        {
            self.online.last_log = Some(std::time::Instant::now());
            log::info!(
                "online state: level {} status {} players {:?} probe {:#x}",
                mailbox::level(&mut read),
                tango_library::online::status(&mut read),
                tango_library::online::players(&mut read),
                tango_library::online::probe_bits()
            );
        }
        let level = mailbox::level(&mut read);
        self.online_refresh_saved(level);
        self.online_connection(level);
        let solo = self.session.active_as::<session::singleplayer::SinglePlayerSession>().expect("checked above");
        let mut read = |a: u32, b: &mut [u8]| {
            solo.peek(a, b);
        };
        // Test aid: `TANGOAW2_TYPE_CODE=<code>` types the room's code on the keyboard's path once its page is up.
        if !self.online.typed_test && level == 3 {
            if let Ok(code) = std::env::var("TANGOAW2_TYPE_CODE") {
                self.online.typed_test = true;
                let mut chars: Vec<u8> = code.bytes().collect();
                chars.push(13);
                let mut write = |a: u32, b: &[u8]| {
                    solo.poke(a, b);
                };
                mailbox::type_chars(&mut read, &mut write, &chars);
            }
        }
        if level == 0 && self.online.room.is_none() && self.online.back_message.is_none() {
            // (nothing asked; keep up with the serial so an old request is never taken for a new one)
            self.online.seen = Some(mailbox::serial(&mut read));
            return iced::Task::none();
        }
        let seen = *self.online.seen.get_or_insert_with(|| mailbox::serial(&mut read));
        let request = mailbox::read_request(&mut read, seen);
        let mut task = iced::Task::none();
        if let Some((serial, request)) = request {
            self.online.seen = Some(serial);
            self.online_request(request);
        }
        self.online_returning(level);
        // The room's match is ready: build it.
        if let Some(room) = self.online.room.as_ref() {
            if room.view().phase == RoomPhase::Ready && !self.online.building {
                if let Some(m) = room.take_match() {
                    self.online.building = true;
                    task = self.online_build_match(m);
                }
            }
        }
        self.online_write_back();
        self.online_announce();
        self.online_browse(level);
        task
    }

    /// The UNRANKED match that was on is over (or left): its file goes, nobody waits for it.
    fn online_live_end(&mut self) {
        if self.online.live.take().is_some() || self.online.live_pending.take().is_some() {
            unranked_live::clear(&self.config.data_path);
        }
        self.online.live_touched = None;
        if let Some(st) = self.online.stayed.take() {
            if let Some(room) = st.room {
                room.leave();
            }
        }
    }

    /// At startup: an UNRANKED match this app crashed out of. Within its window the ONLINE screen offers to rejoin it; after it the
    /// army has yielded and the LOBBY menu says so (once). Either way the game comes up at the ONLINE menu.
    pub(super) fn online_startup(&mut self) -> Option<iced::Task<Message>> {
        let live = unranked_live::read(&self.config.data_path)?;
        match live.verdict(unranked_live::now_ms()) {
            unranked_live::Verdict::Rejoin { left_ms } => {
                log::info!(
                    "unranked: a match of {:?} was on when the app stopped ({} s of the window are left): offering to rejoin",
                    live.players,
                    left_ms / 1000
                );
                self.online.offer = Some(live);
            }
            unranked_live::Verdict::Ended => {
                log::info!("unranked: a match of {:?} was on when the app stopped, long ago: its army yielded", live.players);
                unranked_live::clear(&self.config.data_path);
                self.online.back_message = Some("Your Unranked match ended: your army yielded.".to_string());
            }
        }
        tango_library::online::boot_to_lobby();
        Some(iced::Task::done(Message::Play(crate::tabs::play::Message::PlayOfflinePressed)))
    }

    /// The player who rejoins or gives up: its room is joined, READY once it is in, and left again when the way back is gone.
    fn online_returning(&mut self, level: u8) {
        let Some(ret) = self.online.returning.as_mut() else { return };
        let Some(room) = self.online.room.as_ref() else {
            self.online.returning = None;
            return;
        };
        let view = room.view();
        if view.joined && ret.giving_up {
            log::info!("unranked: the other player is told; leaving its room");
            if let Some(room) = self.online.room.take() {
                room.leave();
            }
            self.online.returning = None;
            return;
        }
        if view.joined && !ret.ready_sent {
            ret.ready_sent = true;
            room.set_ready(true);
            log::info!("unranked: back in the room of the match; ready");
        }
        if matches!(view.phase, RoomPhase::Failed | RoomPhase::Closed) {
            if ret.giving_up {
                // (nobody was there to tell: the match is over already)
                self.online.room = None;
                self.online.returning = None;
                return;
            }
            // The way back is gone: the match is over. The game's box says so; leaving it frees the room.
            if self.online.offer.take().is_some() {
                log::info!("unranked: the match could not be rejoined ({}): it is over", view.message);
                unranked_live::clear(&self.config.data_path);
            }
            if level != mailbox::REJOIN_LEVEL {
                self.online.room = None;
                self.online.returning = None;
            }
        }
    }

    /// While an UNRANKED match runs: its file is touched; and when the other player is gone (their app crashed) a way back is
    /// made for them: a room the returning player joins, with the newest settled state of the console. The match goes on from
    /// that state for both, in new sessions.
    fn online_unranked_tick(&mut self) -> iced::Task<Message> {
        if !self.online.unranked_match {
            return iced::Task::none();
        }
        let now = std::time::Instant::now();
        if let Some(live) = self.online.live.as_mut() {
            if self.online.live_touched.is_none_or(|t| t.elapsed().as_millis() as u64 >= unranked_live::TOUCH_EVERY_MS) {
                self.online.live_touched = Some(now);
                live.touched_ms = unranked_live::now_ms();
                if let Err(e) = unranked_live::write(&self.config.data_path, live) {
                    log::warn!("unranked: could not touch the match's file: {e}");
                }
            }
        }
        let Some(pvp) = self.session.active_as::<session::pvp::PvpSession>() else {
            return iced::Task::none();
        };
        let hold = pvp.rejoin_hold();
        if self.online.building {
            return iced::Task::none();
        }
        match (hold.as_ref(), self.online.stayed.is_some()) {
            (Some((name, left)), false) if *left >= 3 => {
                log::info!("unranked: {name:?} is gone ({left} s of its window left): making a way back for it");
                pvp.request_rejoin_state();
                self.online.stayed = Some(Stayed { asked: true, since: Some(now), ..Default::default() });
                return iced::Task::none();
            }
            (None, true) => {
                // The wait is over: the player came back by itself, or the window passed (the army yielded).
                pvp.set_rejoin_busy(false);
                if let Some(st) = self.online.stayed.take() {
                    log::info!("unranked: the wait for the other player is over");
                    if let Some(room) = st.room {
                        room.leave();
                    }
                }
                return iced::Task::none();
            }
            _ => {}
        }
        let Some(live) = self.online.live.clone() else { return iced::Task::none() };
        let Some(mut st) = self.online.stayed.take() else { return iced::Task::none() };
        let task = iced::Task::none();
        if st.room.is_none() {
            match pvp.take_rejoin_state() {
                Some(sm) => {
                    if let Some(c) = sm.newest().cloned() {
                        let names = unranked_live::room_names(&sm.players);
                        let mut params = self.online_params_for(&live.code);
                        params.nickname = names.get(sm.seat as usize).cloned().unwrap_or_else(|| self.online_nickname());
                        params.match_type = sm.match_type;
                        params.resume = Some(netplay::room::ResumeParams {
                            match_id: sm.match_id,
                            players: names,
                            seat: sm.seat as usize,
                            tick: c.tick,
                            digest: c.image.digest,
                            state: c.image.state,
                            match_ts: sm.match_ts,
                            match_type: sm.match_type,
                            save: sm.save,
                        });
                        log::info!("unranked: a room for the returning player is open (state of tick {})", c.tick);
                        st.room = Some(Room::host(params));
                        st.leaves_seen = 0;
                        st.since = Some(now);
                    }
                }
                None if st.since.is_some_and(|t| t.elapsed().as_secs() >= 3) => {
                    st.since = Some(now);
                    pvp.request_rejoin_state();
                }
                None => {}
            }
            self.online.stayed = Some(st);
            return task;
        }
        let view = st.room.as_ref().expect("checked").view();
        if view.players.len() >= 2 {
            if !st.guest_seen {
                log::info!("unranked: the other player is back in the room");
            }
            st.guest_seen = true;
            pvp.set_rejoin_busy(true);
        } else if view.said_leave > st.leaves_seen && view.phase == RoomPhase::Open {
            // It came and left: it gave the match up.
            log::info!("unranked: the other player gave the match up: its army yields");
            pvp.rejoin_gave_up();
            pvp.set_rejoin_busy(false);
            if let Some(r) = st.room.take() {
                r.leave();
            }
            st.guest_seen = false;
            st.leaves_seen = view.said_leave;
            self.online.stayed = Some(st);
            return task;
        }
        if view.all_ready && view.phase == RoomPhase::Open {
            let room = st.room.as_ref().expect("checked");
            room.set_ready(true);
            room.start();
        }
        match view.phase {
            RoomPhase::Ready => {
                if let Some(m) = st.room.as_ref().expect("checked").take_match() {
                    log::info!("unranked: the other player is back: the match goes on from the state we both have");
                    pvp.set_rejoin_busy(true);
                    self.online.building = true;
                    self.online.stayed = Some(st);
                    self.online_record_battles();
                    return self.online_build_match(m);
                }
            }
            RoomPhase::Failed | RoomPhase::Closed => {
                log::info!("unranked: the room for the returning player failed ({}); making it again", view.message);
                pvp.set_rejoin_busy(false);
                st.room = None;
                st.guest_seen = false;
                st.since = Some(now);
                pvp.request_rejoin_state();
            }
            _ => {}
        }
        self.online.stayed = Some(st);
        task
    }

    /// The public relays used by the lobby list (`TANGOAW2_LOBBY_RELAYS`, comma separated, for tests).
    fn lobby_relays() -> Vec<String> {
        match std::env::var("TANGOAW2_LOBBY_RELAYS") {
            Ok(v) if !v.trim().is_empty() => v.split(',').map(|s| s.trim().to_string()).collect(),
            _ => netplay::browse::RELAYS.iter().map(|s| s.to_string()).collect(),
        }
    }

    fn lobby_version() -> String {
        env!("CARGO_PKG_VERSION").to_string()
    }

    fn lobby_pack() -> bool {
        tango_library::shared_content_flag() != 0 && std::env::var("TANGOAW2_NO_CONTENT").is_err()
    }

    /// The room made here is listed while it waits for players, and withdrawn once its match starts or it closes.
    fn online_announce(&mut self) {
        let open = self.online.room.as_ref().is_some_and(|r| {
            r.is_host() && matches!(r.view().phase, RoomPhase::Connecting | RoomPhase::Open)
        });
        if !open {
            if self.online.announcer.take().is_some() {
                log::info!("lobby list: the lobby is withdrawn");
            }
            return;
        }
        // The game was left (closed, or the player went to another page of the app) while the room was open: nobody
        // is there to start it, so it is closed and withdrawn rather than listed for as long as the app lives.
        if !self.online.building
            && self.session.active_as::<session::singleplayer::SinglePlayerSession>().is_none()
        {
            if let Some(room) = self.online.room.take() {
                room.leave();
            }
            self.online.announcer = None;
            log::info!("lobby list: the game was left; the room is closed and its lobby withdrawn");
            return;
        }
        let Some(room) = self.online.room.as_ref() else { return };
        let players = room.view().players.len().clamp(1, netplay::room::MAX_PLAYERS) as u8;
        if let Some(a) = self.online.announcer.as_ref() {
            a.update(|l| l.players = players);
        }
    }

    /// The game's lobby browser is open (level 7): look at the public list and write what is found.
    fn online_browse(&mut self, level: u8) {
        // The look goes on while a lobby picked from the list is joined or its password typed (the list is still there
        // when B comes back); any other page ends it.
        if matches!(level, 3..=5) && self.online.browse.is_some() {
            return;
        }
        if level != 7 {
            if self.online.browse.is_some() {
                // (kept for a minute and a half: the page is often left for a password or a lobby and come back to)
                let left = *self.online.browse_left.get_or_insert_with(std::time::Instant::now);
                if left.elapsed().as_secs() >= 90 {
                    self.online.browse = None;
                    self.online.browse_left = None;
                    self.online.browse_order.clear();
                    self.online.browse_logged.clear();
                    log::info!("lobby list: the look ended");
                }
            }
            return;
        }
        self.online.browse_left = None;
        let relays = Self::lobby_relays();
        let relays: Vec<&str> = relays.iter().map(String::as_str).collect();
        let (browse, since) = self.online.browse.get_or_insert_with(|| {
            (
                netplay::browse::Browse::start(
                    &relays,
                    netplay::browse::Compat {
                        version: Self::lobby_version(),
                        pack: Self::lobby_pack(),
                    },
                ),
                std::time::Instant::now(),
            )
        });
        let mine = self.online.room.as_ref().map(|r| r.code());
        let listed: Vec<netplay::browse::Listing> = browse
            .listings()
            .into_iter()
            .filter(|l| Some(&l.lobby.code) != mine.as_ref())
            .collect();
        let stats = browse.stats();
        let elapsed = since.elapsed().as_secs_f32();
        // "No lobbies" is only said once a relay has answered (its stored lobbies are in) or the wait is long; until
        // then the page says it is searching.
        let net = if stats.connected == 0 && elapsed >= 10.0 {
            mailbox::BrowseNet::Offline
        } else if stats.answered > 0 || stats.events > 0 || (stats.connected > 0 && elapsed >= 15.0) {
            mailbox::BrowseNet::Ok
        } else {
            mailbox::BrowseNet::Looking
        };
        // First seen first; a lobby that is gone leaves the order.
        self.online.browse_order.retain(|c| listed.iter().any(|l| &l.lobby.code == c));
        // (lobbies seen for the first time in this look, by code: the same order wherever they came from first)
        let mut fresh: Vec<&String> = listed
            .iter()
            .map(|l| &l.lobby.code)
            .filter(|c| !self.online.browse_order.contains(c))
            .collect();
        fresh.sort();
        let fresh: Vec<String> = fresh.into_iter().cloned().collect();
        self.online.browse_order.extend(fresh);
        let rows: Vec<mailbox::BrowseRow> = self
            .online
            .browse_order
            .iter()
            .filter_map(|c| listed.iter().find(|l| &l.lobby.code == c))
            .map(|l| mailbox::BrowseRow {
                code: l.lobby.code.clone(),
                host: l.lobby.host.clone(),
                players: l.lobby.players,
                max: l.lobby.max,
                locked: l.lobby.locked,
            })
            .collect();
        let codes: Vec<String> = rows.iter().map(|r| r.code.clone()).collect();
        if codes != self.online.browse_logged {
            log::info!(
                "lobby list: rows now {codes:?} ({net:?}, {stats:?}, {} of another version hidden)",
                browse.hidden()
            );
            log::info!("lobby list: relays: {}", browse.describe());
            self.online.browse_logged = codes;
        }
        let Some(solo) = self.session.active_as::<session::singleplayer::SinglePlayerSession>() else {
            return;
        };
        let mut write = |a: u32, b: &[u8]| {
            solo.poke(a, b);
        };
        mailbox::write_browse(&mut write, &rows, net, &Self::lobby_version());
    }

    /// The ONLINE screen's status and Connection page: kept up to date from the health table of the relay services.
    /// While the ONLINE menu (or the page) is open there is one polite refresh every 5 minutes at most (a binding
    /// request to each stale STUN server, a signalling handshake, a short look at the lobby relays); never during a
    /// match (this runs only on the menu console).
    fn online_connection(&mut self, level: u8) {
        static STATE_PATH: std::sync::Once = std::sync::Once::new();
        STATE_PATH.call_once(|| {
            if let Some(d) = crate::config::config_dir() {
                tango_net::endpoints::set_state_path(d.join("relay_health.txt"));
            }
        });
        let before = std::mem::replace(&mut self.online.conn_level, level);
        if !matches!(level, 0 | 1 | 11) {
            return;
        }
        let stale = self.online.conn_refreshed.is_none_or(|t| t.elapsed().as_secs() >= 300);
        if stale || (level == 11 && before != 11 && self.online.conn_refreshed.is_none_or(|t| t.elapsed().as_secs() >= 30)) {
            self.online.conn_refreshed = Some(std::time::Instant::now());
            let endpoint = self.config.matchmaking_endpoint.clone();
            tokio::spawn(async move { tango_net::endpoints::refresh(&endpoint).await });
            // (a short look at the lobby relays teaches the table which of them answer; it ends by itself)
            if self.online.browse.is_none() {
                let relays = Self::lobby_relays();
                let relays: Vec<&str> = relays.iter().map(String::as_str).collect();
                self.online.browse = Some((
                    netplay::browse::Browse::start(
                        &relays,
                        netplay::browse::Compat { version: Self::lobby_version(), pack: Self::lobby_pack() },
                    ),
                    std::time::Instant::now(),
                ));
                self.online.browse_left = Some(std::time::Instant::now());
            }
        }
        if self.online.conn_checked_at.is_some_and(|t| t.elapsed().as_millis() < 1500) {
            return;
        }
        self.online.conn_checked_at = Some(std::time::Instant::now());
        let live = self.online.browse.as_ref().map(|(b, _)| {
            let s = b.stats();
            (s.answered, s.relays)
        });
        let summary = tango_net::endpoints::summary_now(&self.config.matchmaking_endpoint, live);
        use tango_net::endpoints::{Overall, Tone};
        let state = match summary.overall {
            Overall::Checking => 0,
            Overall::Online => 1,
            Overall::Limited => 2,
            Overall::Offline => 3,
        };
        let lines: Vec<String> = summary
            .lines
            .iter()
            .map(|(l, v, t)| format!("{}|{l}\t{v}", match t { Tone::Good => 'g', Tone::Middling => 'y', Tone::Bad => 'r' }))
            .collect();
        if self.online.conn_written.as_ref() == Some(&(state, lines.clone())) {
            return;
        }
        if let Some(solo) = self.session.active_as::<session::singleplayer::SinglePlayerSession>() {
            let mut write = |a: u32, b: &[u8]| {
                solo.poke(a, b);
            };
            mailbox::write_connection(&mut write, state, &lines);
            if std::env::var("TANGOAW2_ONLINE_LOG").is_ok_and(|v| v == "1") {
                log::info!("online: connection {:?}: {}", summary.overall, lines.join(" / "));
            }
            self.online.conn_written = Some((state, lines));
        }
    }

    /// The RESUME page's list, written into the console when the page (or the LOBBY menu in front of it) is up.
    fn online_refresh_saved(&mut self, level: u8) {
        let in_menu = matches!(level, 1 | 8);
        if in_menu && (self.online.saved_dirty || !self.online.in_saved_menu) {
            self.online.saved = crate::suspended::list(&self.config.data_path);
            self.online.saved_dirty = false;
            let rows: Vec<mailbox::SavedRow> = self.online.saved.iter().map(row_of).collect();
            if let Some(solo) = self.session.active_as::<session::singleplayer::SinglePlayerSession>() {
                let mut write = |a: u32, b: &[u8]| {
                    solo.poke(a, b);
                };
                mailbox::write_saved(&mut write, &rows);
            }
        }
        self.online.in_saved_menu = in_menu;
    }

    fn online_request(&mut self, request: Request) {
        log::info!("online: the game asks {request:?}");
        match request {
            Request::Host { password } => {
                let seed = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .map_or(1, |d| d.as_nanos() as u64);
                let code = std::env::var("TANGOAW2_ONLINE_CODE").unwrap_or_else(|_| mailbox::new_code(seed));
                let params = self.online_params(&code, &password);
                self.online.back_message = None;
                self.online.room = Some(Room::host(params));
                // Every lobby is public: listed for everyone on this version (never with an address).
                let relays = Self::lobby_relays();
                let relays: Vec<&str> = relays.iter().map(String::as_str).collect();
                self.online.announcer = Some(netplay::browse::Announcer::start(
                    &relays,
                    netplay::browse::Lobby {
                        code: code.clone(),
                        host: self.online_nickname(),
                        players: 1,
                        max: netplay::room::MAX_PLAYERS as u8,
                        locked: !password.is_empty(),
                        version: Self::lobby_version(),
                        pack: Self::lobby_pack(),
                    },
                ));
            }
            Request::Join { code, password } => {
                let params = self.online_params(&code, &password);
                self.online.back_message = None;
                self.online.room = Some(Room::join(params));
            }
            Request::Unranked => {
                // (a pool of players looking: see `tango_lobby::room::Room::unranked`)
                let mut params = self.online_params("unranked", "");
                params.match_type.1 |= mailbox::UNRANKED_MATCH;
                self.online.back_message = None;
                self.online.room = Some(Room::unranked(params));
            }
            Request::Resume { index } => {
                let Some(m) = self.online.saved.get(index).cloned() else {
                    log::warn!("online: no saved match at {index}");
                    return;
                };
                let seed = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .map_or(1, |d| d.as_nanos() as u64);
                let code = std::env::var("TANGOAW2_ONLINE_CODE").unwrap_or_else(|_| mailbox::new_code(seed));
                let mut params = self.online_params(&code, "");
                if let Some(c) = m.newest() {
                    let mut players = m.players.clone();
                    // (my seat is mine whatever my gamertag was then)
                    if let Some(me) = players.get_mut(m.seat as usize) {
                        *me = params.nickname.clone();
                    }
                    params.resume = Some(netplay::room::ResumeParams {
                        match_id: m.match_id,
                        players,
                        seat: m.seat as usize,
                        tick: c.tick,
                        digest: c.image.digest,
                        state: c.image.state.clone(),
                        match_ts: m.match_ts,
                        match_type: m.match_type,
                        save: m.save.clone(),
                    });
                    params.match_type = m.match_type;
                    self.online.back_message = None;
                    self.online.room = Some(Room::host(params));
                }
            }
            Request::Rejoin | Request::GiveUp => {
                let giving_up = request == Request::GiveUp;
                let Some(live) = self.online.offer.clone() else {
                    log::warn!("unranked: no match to rejoin");
                    return;
                };
                let names = unranked_live::room_names(&live.players);
                let mut params = self.online_params(&live.code, "");
                params.nickname = names.get(live.seat).cloned().unwrap_or_else(|| self.online_nickname());
                params.match_type = live.match_type;
                params.saves = vec![live.match_id];
                params.join_seconds = if giving_up { 12 } else { 20 };
                self.online.room = Some(Room::join(params));
                self.online.returning = Some(Returning { giving_up, ready_sent: false });
                if giving_up {
                    // (the other player is told by the room's goodbye; the match is over for this one at once)
                    log::info!("unranked: the player gives the match up");
                    unranked_live::clear(&self.config.data_path);
                    self.online.offer = None;
                    self.online.back_message = Some("You gave up your Unranked match. Your army yielded.".to_string());
                } else {
                    log::info!("unranked: the player rejoins the match (room {})", live.code);
                }
            }
            Request::DeleteSaved { index } => {
                if let Some(m) = self.online.saved.get(index) {
                    crate::suspended::delete(&self.config.data_path, m.match_id);
                }
                self.online.saved_dirty = true;
            }
            Request::Leave => {
                self.online.announcer = None;
                if let Some(room) = self.online.room.take() {
                    room.leave();
                }
            }
            Request::Ready => {
                if let Some(room) = self.online.room.as_ref() {
                    room.set_ready(true);
                }
            }
            Request::NotReady => {
                if let Some(room) = self.online.room.as_ref() {
                    room.set_ready(false);
                }
            }
            Request::Start => {
                if let Some(room) = self.online.room.as_ref() {
                    room.set_ready(true);
                    room.start();
                }
            }
            Request::SetGamertag(name) => {
                let name = mailbox::clean_gamertag(&name);
                if !name.is_empty() {
                    self.config.gamertag = Some(name);
                    self.persist_config();
                }
            }
        }
    }

    fn online_stats(&mut self) -> &mut super::online_stats::Stats {
        let path = super::online_stats::Stats::path(&self.config.data_path);
        self.online
            .stats
            .get_or_insert_with(|| super::online_stats::Stats::load(&path))
    }

    /// The battles the match's console finished since the last look go into the record.
    fn online_record_battles(&mut self) {
        let battles = mailbox::take_battles();
        if battles.is_empty() {
            return;
        }
        let (seat, names) = (self.online.match_seat, self.online.match_names.clone());
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_or(0, |d| d.as_secs());
        for b in battles {
            if self.online.last_battle.is_some_and(|n| n == b.no) {
                continue;
            }
            let Some(v) = super::online_stats::judge(&b, seat, names.len().max(2)) else {
                log::info!("online stats: battle {} was not played to its end; not recorded", b.no);
                continue;
            };
            log::info!("online stats: battle {} recorded: {v:?}", b.no);
            self.online.last_battle = Some(b.no);
            let opponents = v
                .opponents
                .iter()
                .map(|&s| names.get(s).cloned().unwrap_or_else(|| format!("Player {}", s + 1)))
                .collect();
            let path = super::online_stats::Stats::path(&self.config.data_path);
            let stats = self.online_stats();
            stats.add(&v, opponents, now);
            stats.save(&path);
            self.online.stats_rev += 1;
        }
    }

    fn online_params_for(&self, code: &str) -> RoomParams {
        self.online_params(code, "")
    }

    fn online_params(&self, code: &str, password: &str) -> RoomParams {
        let (_, subtype) = mailbox::MATCH_TYPE;
        log::info!(
            "online: relay mode {:?} -> use_relay {:?}",
            self.config.relay_mode,
            self.config.relay_mode.use_relay()
        );
        RoomParams {
            endpoint: self.config.matchmaking_endpoint.clone(),
            use_relay: self.config.relay_mode.use_relay(),
            code: code.to_string(),
            password: password.to_string(),
            nickname: self.online_nickname(),
            game_info: self.loadout.game_info(),
            match_type: (0, subtype),
            save: self.loaded.as_ref().map(|l| l.snapshot_sram()).unwrap_or_default(),
            content: tango_library::shared_content_flag() != 0 && std::env::var("TANGOAW2_NO_CONTENT").is_err(),
            saves: self.online.saved.iter().map(|m| m.match_id).collect(),
            resume: None,
            join_seconds: 0,
        }
    }

    fn online_nickname(&self) -> String {
        let me = mailbox::clean_gamertag(&self.config.gamertag.clone().unwrap_or_default());
        if me.is_empty() {
            // (never the device's hostname: no gamertag yet reads as "Player")
            "Player".to_string()
        } else {
            me
        }
    }

    /// The room's match is ready: build the session (every link is handed over to it).
    fn online_build_match(&mut self, m: netplay::room::RoomMatch) -> iced::Task<Message> {
        let is_host = m.is_host;
        self.online.unranked_match = m.match_type.1 & mailbox::UNRANKED_MATCH != 0;
        let seat = m.seat;
        let host_seat = m.host_seat;
        let match_id = m.match_id;
        let resume_state = m.resume_state.clone();
        let players = m.players.clone();
        // UNRANKED: the match is kept on disk while it runs, for a player whose app crashes to come back to (the file is written
        // when the session is up, see `finish_room_match`)
        let unranked = self.online.unranked_match;
        self.online.live_pending = unranked.then(|| {
            unranked_live::Live::new(
                match_id,
                tango_net_protocol::derive::derive_rejoin_code(&m.seed, match_id),
                seat,
                players.clone(),
                m.match_type,
                unranked_live::now_ms(),
            )
        });
        self.online.offer = None;
        self.online.returning = None;
        // Who is who, for the game's pictures (gamertags next to the armies).
        tango_library::online::set_room(players.clone(), seat);
        mailbox::forget_battles();
        self.online.last_battle = None;
        self.online.match_seat = seat;
        self.online.match_names = players.clone();
        let settings = |nickname: String, host: bool| tango_net_protocol::control::Settings {
            nickname,
            // (the shared-content bit stays only when everyone has it: the room decided)
            match_type: (
                m.match_type.0,
                (m.match_type.1 & !tango_net_protocol::control::ROOM_HOST)
                    | if host { tango_net_protocol::control::ROOM_HOST } else { 0 },
            ),
            game_info: self.loadout.game_info(),
            blind_setup: false,
        };
        let other = players
            .iter()
            .enumerate()
            .find(|&(k, _)| k != seat)
            .map(|(_, n)| n.clone())
            .unwrap_or_default();
        let local = settings(self.online_nickname(), is_host);
        let remote = settings(other, !is_host);
        let (pre_match, extra_links) = m.into_pre_match(local, remote);
        let kept = self.online.kept.clone();
        let data_path = self.config.data_path.clone();
        let sink: std::sync::Arc<dyn Fn(tango_match::SuspendedMatch) + Send + Sync> =
            std::sync::Arc::new(move |m: tango_match::SuspendedMatch| match crate::suspended::save(&data_path, &m) {
                Ok(path) => {
                    log::info!("online: match {:016x} saved to {}", m.match_id, path.display());
                    kept.store(true, std::sync::atomic::Ordering::Release);
                }
                Err(e) => log::error!("online: could not save the suspended match: {e}"),
            });
        self.online.resumed = resume_state.is_some().then_some(match_id);
        let room_args = session::pvp::RoomArgs {
            players,
            seat,
            is_host,
            extra_links,
            host_seat,
            match_id,
            resume_state,
            suspend_sink: Some(sink),
            unranked,
            on_leave: unranked.then(|| {
                let data_path = self.config.data_path.clone();
                std::sync::Arc::new(move || unranked_live::clear(&data_path)) as std::sync::Arc<dyn Fn() + Send + Sync>
            }),
        };
        let scanners = self.scanners.clone();
        let config = self.config.clone();
        let audio_binder = self.audio_binder.clone();
        iced::Task::perform(
            async move { session::spawn_pvp(scanners, config, audio_binder, pre_match, Some(room_args)).await },
            |result| Message::RoomMatchBuilt(std::sync::Arc::new(std::sync::Mutex::new(Some(result)))),
        )
    }

    /// The room's match was built (or not).
    pub(super) fn finish_room_match(&mut self, result: anyhow::Result<session::Launch>) -> iced::Task<Message> {
        self.online.building = false;
        match result {
            Ok(launch) => {
                self.online.in_match = true;
                // (a session that a rejoin replaces: its closing is no leaving)
                if let Some(old) = self.session.active_as::<session::pvp::PvpSession>() {
                    old.set_swapped();
                }
                if let Some(st) = self.online.stayed.take() {
                    if let Some(room) = st.room {
                        room.leave();
                    }
                }
                self.session.install(launch, &self.audio_binder, &self.config);
                if let Some(live) = self.online.live_pending.take() {
                    if let Err(e) = unranked_live::write(&self.config.data_path, &live) {
                        log::warn!("unranked: could not keep the match's file: {e}");
                    }
                    self.online.live = Some(live);
                    self.online.live_touched = Some(std::time::Instant::now());
                }
            }
            Err(e) => {
                self.online.live_pending = None;
                log::error!("online: the room's match could not be built: {e:#}");
                self.online.back_message = Some(format!("The match could not start ({}).", short_error(&format!("{e:#}"))));
                self.online.room = None;
            }
        }
        iced::Task::none()
    }

    /// The connection and the players, for the game to show.
    fn online_write_back(&mut self) {
        let Some(solo) = self.session.active_as::<session::singleplayer::SinglePlayerSession>() else {
            return;
        };
        let mut write = |a: u32, b: &[u8]| {
            solo.poke(a, b);
        };
        let Some(room) = self.online.room.as_ref() else {
            if let Some(m) = self.online.back_message.take() {
                mailbox::write_note(&mut write, &m);
                mailbox::write_status(&mut write, Status::Back, "");
            }
            return;
        };
        let view = room.view();
        if room.is_host() && !room.is_unranked() {
            mailbox::write_room(&mut write, &room.code());
        }
        let (status, message) = match view.phase {
            RoomPhase::Connecting if view.resuming && !view.waiting_for.is_empty() => {
                (Status::Waiting, mailbox::waiting_for(&view.waiting_for))
            }
            RoomPhase::Connecting => (
                if room.is_host() { Status::Waiting } else { Status::Connecting },
                view.message.clone(),
            ),
            RoomPhase::Open | RoomPhase::Starting | RoomPhase::Ready => {
                if view.resuming && !view.waiting_for.is_empty() {
                    // (a saved match: it starts when all of its players are in)
                    (Status::Waiting, mailbox::waiting_for(&view.waiting_for))
                } else if view.players.len() >= 2 && view.joined {
                    let other = view
                        .players
                        .iter()
                        .find(|p| !p.you)
                        .map(|p| p.nickname.clone())
                        .unwrap_or_default();
                    (Status::Connected, other)
                } else if room.is_host() && !room.is_unranked() {
                    (Status::Waiting, String::new())
                } else {
                    (Status::Connecting, view.message.clone())
                }
            }
            RoomPhase::Failed if self.online.returning.is_some() => (Status::Failed, "Your Unranked match is over.".to_string()),
            RoomPhase::Failed => (Status::Failed, view.message.clone()),
            RoomPhase::Closed => (Status::Failed, "Not connected.".to_string()),
        };
        mailbox::write_status(&mut write, status, &message);
        for slot in 0..mailbox::MAX_PLAYERS {
            let player = view.players.get(slot).map(|p| {
                (
                    p.nickname.as_str(),
                    p.ready,
                    (if p.you { mailbox::YOU } else { 0 }) | (if p.host { mailbox::HOST } else { 0 }),
                )
            });
            mailbox::write_player(&mut write, slot, player);
            if let Some(link) = view.players.get(slot).and_then(|p| p.link) {
                use netplay::room::{LinkKind, LinkView};
                let LinkView { kind, rtt_ms } = link;
                let kind = match kind {
                    Some(LinkKind::Direct) => mailbox::LINK_DIRECT,
                    Some(LinkKind::Relayed) => mailbox::LINK_RELAY,
                    None => 0,
                };
                mailbox::write_link(&mut write, slot, kind, rtt_ms.unwrap_or(0).max(rtt_ms.is_some() as u32));
            }
        }
    }
}

/// An error's text cut to a length a page of the game shows whole (at a word's end, with "..").
fn short_error(e: &str) -> String {
    const MAX: usize = 60;
    if e.chars().count() <= MAX {
        return e.to_string();
    }
    let cut: String = e.chars().take(MAX).collect();
    let cut = cut.rsplit_once(' ').map_or(cut.as_str(), |(a, _)| a);
    format!("{cut}..")
}
