//! The player's own online record, kept in the profile's data folder (`online_stats.json`) and shown on the in-game
//! ONLINE screen's STATS page (see `tango_gamesupport_aw2::online_stats`): what the console noted at the end of
//! each battle of a room's match is judged here (who won, whose units fell) and added up.

use tango_library::online::{ArmySummary, BattleSummary};

/// Opponents remembered.
const LAST_KEPT: usize = 8;
const VERSION: u32 = 1;

#[derive(Clone, Debug, Default, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(default)]
pub struct LastBattle {
    /// The other teams' players.
    pub opponents: Vec<String>,
    pub won: bool,
    pub days: u32,
    /// Unix seconds.
    pub when: u64,
}

#[derive(Clone, Debug, Default, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(default)]
pub struct Stats {
    pub version: u32,
    pub battles: u32,
    pub won: u32,
    pub lost: u32,
    pub units_destroyed: u32,
    pub units_lost: u32,
    pub powers: u32,
    pub days: u32,
    /// Newest first.
    pub last: Vec<LastBattle>,
}

/// How one battle went for a seat.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Verdict {
    pub won: bool,
    pub destroyed: u32,
    pub lost: u32,
    pub powers: u32,
    pub days: u32,
    /// Seats of the other teams' players.
    pub opponents: Vec<usize>,
}

/// The army a seat plays (a room has an army a player, odd armies the host's: `seat_of_n`).
fn seat_of(army: &ArmySummary, players: usize) -> usize {
    (army.army as usize - 1) % players.max(1)
}

/// Who won the battle `b`, for `seat` of a room of `players`: `None` when it was not played to its end (a team still
/// has armies in with another's, or none is left).
pub fn judge(b: &BattleSummary, seat: usize, players: usize) -> Option<Verdict> {
    // (the room has an army a player: any others in the console's table are not in the battle)
    let b = &BattleSummary {
        armies: b.armies.iter().filter(|a| a.army as usize <= players).cloned().collect(),
        ..b.clone()
    };
    let mine: Vec<&ArmySummary> = b.armies.iter().filter(|a| seat_of(a, players) == seat).collect();
    let me = mine.first()?;
    let in_play: Vec<&ArmySummary> = b.armies.iter().filter(|a| !a.out).collect();
    let mut teams: Vec<u8> = in_play.iter().map(|a| a.team).collect();
    teams.sort_unstable();
    teams.dedup();
    if teams.len() != 1 {
        return None;
    }
    let others: Vec<&ArmySummary> = b.armies.iter().filter(|a| a.team != me.team).collect();
    Some(Verdict {
        won: teams[0] == me.team,
        destroyed: others.iter().map(|a| a.lost as u32).sum(),
        lost: mine.iter().map(|a| a.lost as u32).sum(),
        powers: mine.iter().map(|a| a.powers as u32).sum(),
        days: b.day as u32,
        opponents: others.iter().map(|a| seat_of(a, players)).collect(),
    })
}

impl Stats {
    pub fn path(data_path: &std::path::Path) -> std::path::PathBuf {
        data_path.join("online_stats.json")
    }

    /// The record kept in `path` (empty when there is none or it cannot be read).
    pub fn load(path: &std::path::Path) -> Stats {
        match std::fs::read(path) {
            Ok(b) => serde_json::from_slice(&b).unwrap_or_else(|e| {
                log::warn!("online stats: {} could not be read ({e}); starting again", path.display());
                Stats::default()
            }),
            Err(_) => Stats::default(),
        }
    }

    /// Writes the record next to `path` and moves it into place.
    pub fn save(&self, path: &std::path::Path) {
        let mut s = self.clone();
        s.version = VERSION;
        let tmp = path.with_extension("json.tmp");
        let result = serde_json::to_vec_pretty(&s)
            .map_err(std::io::Error::other)
            .and_then(|b| std::fs::write(&tmp, b))
            .and_then(|_| std::fs::rename(&tmp, path));
        if let Err(e) = result {
            log::warn!("online stats: could not write {}: {e}", path.display());
        }
    }

    pub fn add(&mut self, v: &Verdict, opponents: Vec<String>, when: u64) {
        self.battles = self.battles.saturating_add(1);
        if v.won {
            self.won = self.won.saturating_add(1);
        } else {
            self.lost = self.lost.saturating_add(1);
        }
        self.units_destroyed = self.units_destroyed.saturating_add(v.destroyed);
        self.units_lost = self.units_lost.saturating_add(v.lost);
        self.powers = self.powers.saturating_add(v.powers);
        self.days = self.days.saturating_add(v.days);
        self.last.insert(
            0,
            LastBattle {
                opponents,
                won: v.won,
                days: v.days,
                when,
            },
        );
        self.last.truncate(LAST_KEPT);
    }

    /// The STATS page's lines: "label", a tab, "value" (no tab: a heading; a label with leading spaces: a sub-line).
    pub fn lines(&self) -> Vec<String> {
        if self.battles == 0 {
            return Vec::new();
        }
        let rate = self.won * 100 / self.battles;
        let mut l = vec![
            format!("Battles played\t{}", self.battles),
            format!("Won\t{}", self.won),
            format!("Lost\t{}", self.lost),
            format!("Win rate\t{rate}%"),
            format!("Units destroyed\t{}", self.units_destroyed),
            format!("Units lost\t{}", self.units_lost),
            format!("CO powers used\t{}", self.powers),
            format!("Days played\t{}", self.days),
            "Last opponents".to_string(),
        ];
        for b in &self.last {
            let who = if b.opponents.is_empty() { "?".to_string() } else { b.opponents.join(", ") };
            // (whole names: the first, and how many more)
            let who: String = if who.chars().count() <= 17 {
                who
            } else if b.opponents.len() > 1 {
                format!("{} +{}", b.opponents[0].chars().take(12).collect::<String>(), b.opponents.len() - 1)
            } else {
                who.chars().take(17).collect()
            };
            l.push(format!("  {who}\t{}", if b.won { "Won" } else { "Lost" }));
        }
        l
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn army(n: u8, team: u8, out: bool, lost: u8) -> ArmySummary {
        ArmySummary {
            army: n,
            team,
            human: true,
            out,
            built: 10,
            lost,
            ..Default::default()
        }
    }

    #[test]
    fn the_winner_is_the_team_left() {
        let b = BattleSummary {
            no: 1,
            day: 9,
            armies: vec![army(1, 1, false, 3), army(2, 2, true, 7)],
        };
        let host = judge(&b, 0, 2).unwrap();
        assert!(host.won);
        assert_eq!((host.destroyed, host.lost, host.days, host.opponents.clone()), (7, 3, 9, vec![1]));
        assert!(!judge(&b, 1, 2).unwrap().won);
        // Not played to the end: both still in.
        let b2 = BattleSummary {
            armies: vec![army(1, 1, false, 0), army(2, 2, false, 0)],
            ..b.clone()
        };
        assert_eq!(judge(&b2, 0, 2), None);
        // Allies win together.
        let b3 = BattleSummary {
            armies: vec![army(1, 1, false, 0), army(2, 2, true, 4), army(3, 1, false, 2)],
            ..b
        };
        assert!(judge(&b3, 2, 3).unwrap().won);
    }

    #[test]
    fn the_record_survives_a_round_trip_and_unknown_fields() {
        let mut s = Stats::default();
        let v = Verdict {
            won: true,
            destroyed: 5,
            lost: 2,
            powers: 1,
            days: 8,
            opponents: vec![1],
        };
        for _ in 0..10 {
            s.add(&v, vec!["BOB".into()], 1);
        }
        assert_eq!(s.last.len(), LAST_KEPT);
        assert_eq!(s.battles, 10);
        let json = serde_json::to_string(&s).unwrap();
        let json = json.replacen('{', "{\"future\":1,", 1);
        let back: Stats = serde_json::from_str(&json).unwrap();
        assert_eq!(back.battles, 10);
        assert!(s.lines().len() <= 24);
    }
}
