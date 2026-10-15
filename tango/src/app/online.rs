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
use crate::{netplay, session, tabs};
use netplay::room::{Room, RoomParams, RoomPhase};
use tango_library::online::{self as mailbox, Request, Status};

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
    /// Said on the LOBBY menu when the game comes back.
    back_message: Option<String>,
    /// Test aid (`TANGOAW2_ONLINE_LOG=1`): when the state was last logged.
    last_log: Option<std::time::Instant>,
}

impl App {
    /// Every session frame: the in-game lobby's mailbox, and the way back from a
    /// match it made.
    pub(super) fn online_tick(&mut self) -> iced::Task<Message> {
        // A lobby-made match just ended: back to the game, at its lobby.
        if self.online.in_match && !self.session.is_active() {
            self.online.in_match = false;
            self.online.room = None;
            self.online.seen = None;
            let how = match self.session.results.take() {
                Some(r) if r.end == session::results::MatchEnd::Disconnected => "A player left.",
                Some(_) => "The match is over.",
                None => "You left the match.",
            };
            self.online.back_message = Some(how.to_string());
            mailbox::boot_to_lobby();
            return self.update_play(tabs::play::Message::PlayOfflinePressed);
        }
        if self.session.active_as::<session::pvp::PvpSession>().is_some() {
            return iced::Task::none();
        }
        let Some(solo) = self.session.active_as::<session::singleplayer::SinglePlayerSession>() else {
            return iced::Task::none();
        };
        let mut read = |a: u32, b: &mut [u8]| {
            solo.peek(a, b);
        };
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
        if mailbox::level(&mut read) == 0 && self.online.room.is_none() && self.online.back_message.is_none() {
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
        task
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
            }
            Request::Join { code, password } => {
                let params = self.online_params(&code, &password);
                self.online.back_message = None;
                self.online.room = Some(Room::join(params));
            }
            Request::Leave => {
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
        }
    }

    fn online_params(&self, code: &str, password: &str) -> RoomParams {
        let (_, subtype) = mailbox::MATCH_TYPE;
        RoomParams {
            endpoint: self.config.matchmaking_endpoint.clone(),
            use_relay: self.config.relay_mode.use_relay(),
            code: code.to_string(),
            password: password.to_string(),
            nickname: self.online_nickname(),
            game_info: self.loadout.game_info(),
            match_type: (0, subtype),
            save: self.loaded.as_ref().map(|l| l.snapshot_sram()).unwrap_or_default(),
            content: tango_library::shared_content_flag() != 0,
        }
    }

    fn online_nickname(&self) -> String {
        let me = self.config.nickname.clone().unwrap_or_default();
        if me.is_empty() {
            "You".to_string()
        } else {
            me
        }
    }

    /// The room's match is ready: build the session (every link is handed over to it).
    fn online_build_match(&mut self, m: netplay::room::RoomMatch) -> iced::Task<Message> {
        let is_host = m.is_host;
        let seat = m.seat;
        let players = m.players.clone();
        // Who is who, for the game's pictures (gamertags next to the armies).
        tango_library::online::set_room(players.clone(), seat);
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
        let room_args = session::pvp::RoomArgs {
            players,
            seat,
            is_host,
            extra_links,
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
                self.session.install(launch, &self.audio_binder, &self.config);
            }
            Err(e) => {
                log::error!("online: the room's match could not be built: {e:#}");
                self.online.back_message = Some(format!("The match could not start ({e:#})."));
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
                mailbox::write_status(&mut write, Status::Back, &m);
            }
            return;
        };
        let view = room.view();
        if room.is_host() {
            mailbox::write_room(&mut write, &room.code());
        }
        let (status, message) = match view.phase {
            RoomPhase::Connecting => (
                if room.is_host() { Status::Waiting } else { Status::Connecting },
                view.message.clone(),
            ),
            RoomPhase::Open | RoomPhase::Starting | RoomPhase::Ready => {
                if view.players.len() >= 2 && view.joined {
                    let other = view
                        .players
                        .iter()
                        .find(|p| !p.you)
                        .map(|p| p.nickname.clone())
                        .unwrap_or_default();
                    (Status::Connected, other)
                } else if room.is_host() {
                    (Status::Waiting, String::new())
                } else {
                    (Status::Connecting, view.message.clone())
                }
            }
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
        }
    }
}
