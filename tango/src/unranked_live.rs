//! A live UNRANKED match, kept on disk so that a player whose app crashed (or was killed) can come back to it.
//!
//! One file, `<data>/unranked_live.json`, made when an UNRANKED match starts, touched every few seconds while it runs
//! and removed when it ends in any way the app knows (the match is over, the player left, the player gave up). A file
//! that is still there when the app starts is a crash: the match the player was in may still be on. The other player's
//! app waits for a returning player for [`GRACE_MS`] (the reconnect window); a file whose last touch is within that is
//! offered on the ONLINE screen ("Your Unranked match is still on. Rejoin?"), an older one is told once ("Your
//! Unranked match ended: your army yielded.") and removed.
//!
//! The file holds no game data: who played, which seat, and the rendezvous code the two meet at again (derived from the
//! match seed and id, see `tango_net_protocol::derive::derive_rejoin_code`).

use std::path::{Path, PathBuf};

/// How long the other player waits for a returning one (the reconnect window of a match).
pub const GRACE_MS: u64 = 60_000;
/// How often a running match touches its file.
pub const TOUCH_EVERY_MS: u64 = 4_000;

const FILE: &str = "unranked_live.json";
const VERSION: u32 = 1;

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
    pub fn new(match_id: u64, code: String, seat: usize, players: Vec<String>, match_type: (u8, u8), now_ms: u64) -> Self {
        Self { version: VERSION, match_id, code, seat, players, match_type, started_ms: now_ms, touched_ms: now_ms }
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
    (live.version == VERSION).then_some(live)
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

pub fn now_ms() -> u64 {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(0, |d| d.as_millis() as u64)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn live(now: u64) -> Live {
        Live::new(7, "rejoinabc".into(), 1, vec!["Ann".into(), "Bo".into()], (0, 3), now)
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
    fn the_opponent_is_the_other_seat() {
        assert_eq!(live(0).opponent(), "Ann");
    }
}
