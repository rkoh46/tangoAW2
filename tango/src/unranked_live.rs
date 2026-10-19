//! A live match of a room (a lobby's or UNRANKED's), kept on disk so that a player whose app crashed (or was killed) can come back to it.
//!
//! One file, `<data>/unranked_live.json`, made when the match starts, touched every few seconds while it runs and removed when it ends
//! in any way the app knows (the match is over, the player left, the player gave up). A file that is still there when the app starts
//! is a crash: the match the player was in may still be on. The other players' apps wait for a returning player for [`GRACE_MS`] (the
//! reconnect window); a file whose last touch is within that is offered on the ONLINE screen ("Your match in <room> is still on.
//! Rejoin?", on the JOIN list too: "<room> - In progress"), an older one is told once ("Your match in <room> ended: your army
//! yielded.") and removed. An UNRANKED match has no room name; its words are "Your Unranked match ...".
//!
//! The file holds no game data: who played, which seat, the room's name and the rendezvous code the players meet at again (derived
//! from the match seed and id, see `tango_net_protocol::derive::derive_rejoin_code`).

use std::path::{Path, PathBuf};

/// How long the other player waits for a returning one (the reconnect window of a match).
pub const GRACE_MS: u64 = 60_000;
/// How often a running match touches its file.
pub const TOUCH_EVERY_MS: u64 = 4_000;

const FILE: &str = "unranked_live.json";
/// 2 added the room's name (a file of version 1 is an UNRANKED match's).
const VERSION: u32 = 2;

#[derive(Clone, Debug, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct Live {
    pub version: u32,
    pub match_id: u64,
    /// The room code the two players meet at again.
    pub code: String,
    /// This player's seat and everyone's gamertag in seat order.
    pub seat: usize,
    pub players: Vec<String>,
    pub match_type: (u8, u8),
    /// When the match began and when this file was last touched (milliseconds since the unix epoch).
    pub started_ms: u64,
    pub touched_ms: u64,
    /// The room's name; empty in an UNRANKED match.
    #[serde(default)]
    pub room_name: String,
}

/// What a file found at startup means.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Verdict {
    /// The match may still be on: this many milliseconds of the window are left.
    Rejoin { left_ms: u64 },
    /// The window has passed: the army yielded.
    Ended,
}

impl Live {
    pub fn new(match_id: u64, code: String, seat: usize, players: Vec<String>, match_type: (u8, u8), room_name: String, now_ms: u64) -> Self {
        Self { version: VERSION, match_id, code, seat, players, match_type, started_ms: now_ms, touched_ms: now_ms, room_name }
    }

    /// An UNRANKED match (it has no room).
    pub fn is_unranked(&self) -> bool {
        self.room_name.is_empty()
    }

    /// What the player is told, once, when the window passed without them.
    pub fn ended_message(&self) -> String {
        if self.is_unranked() {
            "Your Unranked match ended: your army yielded.".to_string()
        } else {
            format!("Your match in {} ended: your army yielded.", self.room_name)
        }
    }

    pub fn verdict(&self, now_ms: u64) -> Verdict {
        let age = now_ms.saturating_sub(self.touched_ms);
        if age < GRACE_MS {
            Verdict::Rejoin { left_ms: GRACE_MS - age }
        } else {
            Verdict::Ended
        }
    }

    /// The opponent's gamertag (the other seat of a match of two).
    pub fn opponent(&self) -> String {
        self.players.iter().enumerate().find(|&(k, _)| k != self.seat).map(|(_, n)| n.clone()).unwrap_or_default()
    }
}

pub fn path(data_path: &Path) -> PathBuf {
    data_path.join(FILE)
}

/// Write the file whole, then move it into place (a crash never leaves half of it).
pub fn write(data_path: &Path, live: &Live) -> std::io::Result<()> {
    let tmp = path(data_path).with_extension("part");
    std::fs::write(&tmp, serde_json::to_vec(live).map_err(std::io::Error::other)?)?;
    std::fs::rename(&tmp, path(data_path))
}

/// The file, if there is one that can be read.
pub fn read(data_path: &Path) -> Option<Live> {
    let live: Live = serde_json::from_slice(&std::fs::read(path(data_path)).ok()?).ok()?;
    (1..=VERSION).contains(&live.version).then_some(live)
}

pub fn clear(data_path: &Path) {
    let _ = std::fs::remove_file(path(data_path));
    let _ = std::fs::remove_file(path(data_path).with_extension("part"));
}

/// The gamertags a rejoin room uses: the room tells its players by name, so two players of one name are told apart
/// (the second gets a 2). Both players compute the same.
pub fn room_names(players: &[String]) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    for n in players {
        let mut name = n.clone();
        if out.contains(&name) {
            let keep: String = n.chars().take(11).collect();
            name = format!("{keep}2");
        }
        out.push(name);
    }
    out
}

/// The seat of the stayer who makes the room for a returning player: the lowest seat that is not the one waited for (every stayer works the
/// same out from the seats, so the others know to join it).
pub fn rejoin_maker(players: usize, held_seat: usize) -> usize {
    (0..players).find(|&s| s != held_seat).unwrap_or(0)
}

pub fn now_ms() -> u64 {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(0, |d| d.as_millis() as u64)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn live(now: u64) -> Live {
        Live::new(7, "rejoinabc".into(), 1, vec!["Ann".into(), "Bo".into()], (0, 3), "Ann's room".into(), now)
    }

    fn dir(tag: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("taw2-live-{tag}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn the_file_lives_from_the_start_to_the_end_of_a_match() {
        let d = dir("life");
        assert!(read(&d).is_none());
        let l = live(1_000);
        write(&d, &l).unwrap();
        assert_eq!(read(&d), Some(l.clone()));
        // touched while the match runs
        let mut t = l.clone();
        t.touched_ms = 5_000;
        write(&d, &t).unwrap();
        assert_eq!(read(&d).unwrap().touched_ms, 5_000);
        assert_eq!(read(&d).unwrap().started_ms, 1_000);
        // the match ends: nothing left to offer
        clear(&d);
        assert!(read(&d).is_none());
        // (clearing twice is nothing)
        clear(&d);
        let _ = std::fs::remove_dir_all(&d);
    }

    #[test]
    fn a_relaunch_inside_the_window_rejoins_and_after_it_the_army_has_yielded() {
        let l = live(0);
        assert_eq!(l.verdict(10_000), Verdict::Rejoin { left_ms: 50_000 });
        assert_eq!(l.verdict(59_999), Verdict::Rejoin { left_ms: 1 });
        assert_eq!(l.verdict(60_000), Verdict::Ended);
        assert_eq!(l.verdict(3_600_000), Verdict::Ended);
        // a clock that went back is no reason to give the match up
        assert_eq!(l.verdict(0), Verdict::Rejoin { left_ms: 60_000 });
    }

    #[test]
    fn a_broken_or_foreign_file_is_no_live_match() {
        let d = dir("bad");
        std::fs::write(path(&d), b"not json").unwrap();
        assert!(read(&d).is_none());
        let mut l = live(0);
        l.version = 99;
        std::fs::write(path(&d), serde_json::to_vec(&l).unwrap()).unwrap();
        assert!(read(&d).is_none());
        let _ = std::fs::remove_dir_all(&d);
    }

    #[test]
    fn two_players_of_one_name_are_told_apart_the_same_way_by_both() {
        let same = vec!["Player".to_string(), "Player".to_string()];
        assert_eq!(room_names(&same), vec!["Player".to_string(), "Player2".to_string()]);
        let long = vec!["Abcdefghijkl".to_string(), "Abcdefghijkl".to_string()];
        assert!(room_names(&long)[1].chars().count() <= 12);
        let other = vec!["Ann".to_string(), "Bo".to_string()];
        assert_eq!(room_names(&other), other);
    }

    #[test]
    fn a_lobby_match_has_its_rooms_name_and_an_unranked_one_none() {
        let l = live(0);
        assert!(!l.is_unranked());
        assert_eq!(l.ended_message(), "Your match in Ann's room ended: your army yielded.");
        let mut u = live(0);
        u.room_name.clear();
        assert!(u.is_unranked());
        assert_eq!(u.ended_message(), "Your Unranked match ended: your army yielded.");
        // (names with spaces and the like survive the file)
        let d = dir("name");
        let mut l = live(5);
        l.room_name = "Big Pent Room".into();
        l.players = vec!["Ann Lee".into(), "Bo  Ray".into()];
        write(&d, &l).unwrap();
        assert_eq!(read(&d), Some(l));
        let _ = std::fs::remove_dir_all(&d);
    }

    #[test]
    fn a_file_of_version_one_is_still_read_as_an_unranked_match() {
        let d = dir("v1");
        std::fs::write(
            path(&d),
            br#"{"version":1,"match_id":7,"code":"rejoinabc","seat":0,"players":["A","B"],"match_type":[0,3],"started_ms":1,"touched_ms":2}"#,
        )
        .unwrap();
        let l = read(&d).expect("a version 1 file");
        assert!(l.is_unranked());
        let _ = std::fs::remove_dir_all(&d);
    }

    #[test]
    fn the_lowest_seat_that_stayed_makes_the_room() {
        // a room of two: the one that stayed
        assert_eq!((rejoin_maker(2, 0), rejoin_maker(2, 1)), (1, 0));
        // a room of three or more: the host unless the host is the one gone, then the next seat
        assert_eq!((rejoin_maker(3, 0), rejoin_maker(3, 1), rejoin_maker(3, 2)), (1, 0, 0));
        assert_eq!(rejoin_maker(5, 0), 1);
        assert_eq!(rejoin_maker(5, 4), 0);
    }

    #[test]
    fn the_opponent_is_the_other_seat() {
        assert_eq!(live(0).opponent(), "Ann");
    }
}
