//! tangoAW2's in-game lobby, the app's half (the game's is
//! `tango_gamesupport_aw2::online`): while the game is played alone, its mailbox
//! is read every frame. A room made or joined there is dialled through the
//! matchmaking server like a link code ([`tango_library::online::link_code`]:
//! the room's code, and its password), played as the "Online lobby" match type,
//! with the room's maker in seat 0 (`ROOM_HOST`). The connection's progress and
//! the players are written back for the game to show; READY in the game is the
//! lobby's Ready (the save committed), and the host's START is the host's own
//! Ready, once the guest is. When the match ends (the host leaves SELECT MAP, a
//! player quits, or the link drops) the game is booted again, straight to its
//! LOBBY menu, with how it ended.

use super::{App, Message};
use crate::{netplay, session, tabs};
use tango_library::online::{self as mailbox, Request, Status};

/// What the app knows of the in-game lobby.
#[derive(Default)]
pub struct Flow {
    /// The last request handled.
    seen: Option<u8>,
    /// The room this player made or joined.
    room: Option<Room>,
    /// A match made in the lobby is running (its end brings the game back).
    in_match: bool,
    /// Said on the LOBBY menu when the game comes back.
    back_message: Option<String>,
    /// Test aid (`TANGOAW2_ONLINE_LOG=1`): when the state was last logged.
    last_log: Option<std::time::Instant>,
}

struct Room {
    code: String,
    host: bool,
}

impl App {
    /// Every session frame: the in-game lobby's mailbox, and the way back from
    /// a match it made.
    pub(super) fn online_tick(&mut self) -> iced::Task<Message> {
        // A lobby-made match just ended: back to the game, at its lobby.
        if self.online.in_match && !self.session.is_active() {
            self.online.in_match = false;
            self.online.room = None;
            self.online.seen = None;
            let how = match self.session.results.take() {
                Some(r) if r.end == session::results::MatchEnd::Disconnected => "The other player left.",
                Some(_) => "The match is over.",
                None => "You left the match.",
            };
            self.online.back_message = Some(how.to_string());
            self.netplay.disconnect();
            mailbox::boot_to_lobby();
            return self.update_play(tabs::play::Message::PlayOfflinePressed);
        }
        if let Some(pvp) = self.session.active_as::<session::pvp::PvpSession>() {
            if self.online.room.is_some() {
                self.online.in_match = true;
                // Who is who, for the game's pictures (gamertags next to the armies).
                let local = pvp.local_player_index() as usize;
                let me = self.config.nickname.clone().filter(|n| !n.is_empty()).unwrap_or_else(|| "You".into());
                let mut names = vec![String::new(); 2];
                names[local] = me;
                names[1 - local] = pvp.remote_nickname.clone();
                tango_library::online::set_room(names, local);
            }
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
            task = self.online_request(request);
        }
        self.online_write_back();
        task
    }

    fn online_request(&mut self, request: Request) -> iced::Task<Message> {
        log::info!("online: the game asks {request:?}");
        match request {
            Request::Host { password } => {
                let seed = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .map_or(1, |d| d.as_nanos() as u64);
                let code = std::env::var("TANGOAW2_ONLINE_CODE").unwrap_or_else(|_| mailbox::new_code(seed));
                self.online.room = Some(Room {
                    code: code.clone(),
                    host: true,
                });
                self.online_connect(&code, &password)
            }
            Request::Join { code, password } => {
                self.online.room = Some(Room {
                    code: code.clone(),
                    host: false,
                });
                self.online_connect(&code, &password)
            }
            Request::Leave => {
                self.online.room = None;
                self.netplay.disconnect();
                iced::Task::none()
            }
            Request::Ready | Request::Start => self.update_play(tabs::play::Message::Ready),
            Request::NotReady => self.update_play(tabs::play::Message::Unready),
        }
    }

    fn online_connect(&mut self, code: &str, password: &str) -> iced::Task<Message> {
        self.online.back_message = None;
        let task = netplay::connect(
            &mut self.netplay,
            netplay::MatchmakingParams {
                link_code: mailbox::link_code(code, password),
                endpoint: self.config.matchmaking_endpoint.clone(),
                use_relay: self.config.relay_mode.use_relay(),
            },
        );
        // The lobby's own match type (not remembered as the player's pick), with the room's maker marked.
        let family = self.loadout.game().map(|g| g.family_and_variant().0);
        let host = self.online.room.as_ref().is_some_and(|r| r.host);
        let (mode, subtype) = mailbox::MATCH_TYPE;
        let flag = if host {
            tango_net_protocol::control::ROOM_HOST
        } else {
            0
        };
        self.netplay.pick_match_type(family, (mode, subtype | flag));
        task
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
        if room.host {
            mailbox::write_room(&mut write, &room.code);
        }
        let (status, message) = match &self.netplay.phase {
            netplay::Phase::Idle => (Status::Failed, "Not connected.".to_string()),
            netplay::Phase::Connecting {
                waiting_for_opponent, ..
            } => (
                if *waiting_for_opponent {
                    Status::Waiting
                } else {
                    Status::Connecting
                },
                String::new(),
            ),
            netplay::Phase::Negotiating { .. } => (Status::Connecting, String::new()),
            netplay::Phase::Lobby { .. } => match self.online_verdict() {
                Some(problem) => (Status::Failed, problem),
                None if self.netplay.lobby.remote.is_some() => (Status::Connected, self.online_remote_name()),
                None => (Status::Connecting, String::new()),
            },
            netplay::Phase::Failed { error } => (Status::Failed, online_error_text(error)),
        };
        mailbox::write_status(&mut write, status, &message);
        // The players: the host first.
        let ready = self.netplay.ready_view();
        let me = self.config.nickname.clone().unwrap_or_default();
        let me = if me.is_empty() { "You".to_string() } else { me };
        let local = (
            me.as_str(),
            ready.local_ready,
            mailbox::YOU | if room.host { mailbox::HOST } else { 0 },
        );
        let them_name = self.online_remote_name();
        let remote = (status == Status::Connected).then_some((
            them_name.as_str(),
            ready.remote_ready,
            if room.host { 0 } else { mailbox::HOST },
        ));
        // The room's maker is always the first slot, on every peer (a guest not yet connected to them sees "Host").
        let (first, second) = if room.host {
            (Some(local), remote)
        } else {
            (Some(remote.unwrap_or(("Host", false, mailbox::HOST))), Some(local))
        };
        mailbox::write_player(&mut write, 0, first);
        mailbox::write_player(&mut write, 1, second);
        for slot in 2..mailbox::MAX_PLAYERS {
            mailbox::write_player(&mut write, slot, None);
        }
    }

    fn online_remote_name(&self) -> String {
        self.netplay
            .lobby
            .remote
            .as_ref()
            .map(|s| s.nickname.clone())
            .filter(|n| !n.is_empty())
            .unwrap_or_else(|| "Player".to_string())
    }

    /// Why the two players cannot play together, if they cannot.
    fn online_verdict(&self) -> Option<String> {
        use netplay::compat::Verdict as V;
        let (Some(local), Some(remote)) = (self.netplay.lobby.local.as_ref(), self.netplay.lobby.remote.as_ref())
        else {
            return None;
        };
        let facts = self.scanners.compatibility_facts(local, remote);
        match netplay::compat::check(local, remote, facts) {
            V::Compatible => None,
            V::SimVersionTooOld => Some("The other player's tangoAW2 is older: they need to update.".into()),
            V::SimVersionTooNew => Some("Your tangoAW2 is older: update it to play them.".into()),
            V::DifferentMatchTypes => Some("The other player is in another kind of match.".into()),
            V::MissingRom | V::MissingGame => Some("The other player's game is not one you have.".into()),
            other => Some(format!("Cannot play: {other:?}")),
        }
    }
}

fn online_error_text(error: &netplay::Error) -> String {
    match error {
        netplay::Error::PeerDisconnected => "The other player left.".into(),
        netplay::Error::SignalingUnreachable(_) => "The matchmaking server cannot be reached.".into(),
        netplay::Error::SignalingVersionTooOld => "This tangoAW2 needs updating to play online.".into(),
        e => format!("Could not connect ({e})."),
    }
}
