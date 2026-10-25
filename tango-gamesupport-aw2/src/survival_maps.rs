//! Dual Strike's Survival maps and runs, read from the Dual Strike pack and
//! converted to Advance Wars 2's map format at run time (nothing of either
//! game is in the repository).
//!
//! Where Dual Strike (USA) keeps them (overlay 0 is loaded at 0x022AD560):
//!
//! - **The maps**: Dual Strike's map headers, read and converted by
//!   [`crate::ds_maps`] (its header table, names and terrain): each map's
//!   tiles, units, armies, colours, look, weather, fog, par days (the speed
//!   rank's day limit) and the computer armies' COs (armies 2 and 3).
//! - **The three runs**: eleven map ids each (u16, zero-ended), overlay 0
//!   `0x022F64FC` (Time), `0x022F652C` (Money), `0x022F6514` (Turn); the
//!   kind -> list switch is arm9 `0x020EAC50` (kinds 3..5, the Champion
//!   courses, use the same lists).
//! - **Budgets**: arm9 `0x02168D04`, a word per kind: Time 90000 frames
//!   (25 minutes), Money 500000 G, Turn 99 days; Champion 108000, 600000,
//!   120 (read by `sub_020EAA8C`).
//!
use std::sync::OnceLock;

const BUDGETS: u32 = 0x0216_8D04;
/// Each kind's map list (Time, Money, Turn).
const LISTS: [u32; 3] = [0x022F_64FC, 0x022F_652C, 0x022F_6514];
pub const MAPS_PER_RUN: usize = 11;
/// Dual Strike's text for Survival on Select Mode.
const HELP_TEXT: u16 = 1224;

/// The three Survival kinds, in Dual Strike's order (its kind byte, survival
/// state +7: 0 Time, 1 Money, 2 Turn).
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Kind {
    Time = 0,
    Money = 1,
    Turn = 2,
}

impl Kind {
    pub const ALL: [Kind; 3] = [Kind::Money, Kind::Turn, Kind::Time];
    pub fn from_u8(v: u8) -> Option<Kind> {
        match v {
            0 => Some(Kind::Time),
            1 => Some(Kind::Money),
            2 => Some(Kind::Turn),
            _ => None,
        }
    }
    pub fn name(self) -> &'static str {
        match self {
            Kind::Time => "Time Survival",
            Kind::Money => "Money Survival",
            Kind::Turn => "Turn Survival",
        }
    }
    /// Dual Strike's names for the Champion courses (its text ids 406..408,
    /// the shop's items).
    pub fn champion_name(self) -> &'static str {
        match self {
            Kind::Time => "Time Champion",
            Kind::Money => "Money Champion",
            Kind::Turn => "Turn Champion",
        }
    }
}

pub use crate::ds_maps::{convert_co, convert_tile, convert_unit, Structure, Unit};

#[derive(Clone, Debug)]
pub struct Map {
    /// Dual Strike's map id.
    pub ds_id: u16,
    pub name: String,
    pub width: u8,
    pub height: u8,
    /// AW2 tile ids, row by row (converted).
    pub tiles: Vec<u16>,
    pub units: Vec<Unit>,
    pub armies: u8,
    /// Colour of armies 1..4 (1 Orange Star .. 5 Black Hole).
    pub colours: [u8; 4],
    /// The computer armies' COs as tangoAW2 CO ids (armies 2..4; None: none).
    pub cos: [Option<u8>; 3],
    pub fog: bool,
    /// 0 clear, 1 snow, 2 rain, 3 sandstorm.
    pub weather: u8,
    /// Dual Strike's look: 0 normal, 1 snow, 2 desert, 3 wasteland.
    pub look: u8,
    /// The speed rank's day limit.
    pub speed_days: u16,
    /// The picture of the map's 4x4 structure, for maps with one: the
    /// header's +0x24 points at a `bmap` file name (Convoy Cape and Lone
    /// Wolf "0a5", the missile pad; Silo Sweep "0a6", the fortress).
    pub structure: Option<Structure>,
}

#[derive(Clone, Debug)]
pub struct Run {
    pub kind: Kind,
    /// Funds, days, or frames (60 a second).
    pub budget: u32,
    /// The Champion course's budget (the same lists, endless: arm9
    /// `0x02168D04`'s kinds 3..5).
    pub champion_budget: u32,
    /// Indexes into [`Survival::maps`].
    pub maps: [usize; MAPS_PER_RUN],
}

#[derive(Debug)]
pub struct Survival {
    /// Every map any run uses, in Dual Strike's id order.
    pub maps: Vec<Map>,
    /// Time, Money, Turn (Dual Strike's kind order).
    pub runs: [Run; 3],
    /// Dual Strike's help line for Survival on Select Mode (its text 1224).
    pub help: String,
}

impl Survival {
    pub fn run(&self, kind: Kind) -> &Run {
        &self.runs[kind as usize]
    }
}

/// A Survival map from Dual Strike's header (crate::ds_maps).
fn survival_map(m: crate::ds_maps::Map) -> Map {
    Map {
        ds_id: m.ds_id,
        cos: [m.cos[1].0, if m.armies >= 3 { m.cos[2].0 } else { None }, None],
        speed_days: m.par.0,
        name: m.name,
        width: m.width,
        height: m.height,
        tiles: m.tiles,
        units: m.units,
        armies: m.armies,
        colours: m.colours,
        fog: m.fog,
        weather: m.weather,
        look: m.look,
        structure: m.structure,
    }
}

fn read(pack: &crate::ds_pack::Pack) -> Option<Survival> {
    let r = crate::ds_maps::Reader::new(pack);
    let mut ids: Vec<u16> = Vec::new();
    let mut lists = Vec::new();
    for list in LISTS {
        let mut l = [0u16; MAPS_PER_RUN];
        for (k, slot) in l.iter_mut().enumerate() {
            *slot = r.u16(list + 2 * k as u32)?;
            if *slot == 0 {
                return None;
            }
        }
        ids.extend(l);
        lists.push(l);
    }
    ids.sort();
    ids.dedup();
    let maps: Vec<Map> = ids
        .iter()
        .map(|&id| r.map(id).map(survival_map))
        .collect::<Option<_>>()?;
    let budget = |k: u32| -> Option<u32> {
        pack.arm9_at(BUDGETS + 4 * k, 4)
            .map(|b| u32::from_le_bytes(b.try_into().unwrap()))
    };
    let run = |kind: Kind| -> Option<Run> {
        let l = &lists[kind as usize];
        let mut m = [0usize; MAPS_PER_RUN];
        for (k, id) in l.iter().enumerate() {
            m[k] = ids.iter().position(|x| x == id)?;
        }
        Some(Run {
            kind,
            budget: budget(kind as u32)?,
            champion_budget: budget(3 + kind as u32)?,
            maps: m,
        })
    };
    let help = r
        .text(HELP_TEXT)
        .unwrap_or_else(|| "Fight through a series of maps with three limitations.".into());
    Some(Survival {
        runs: [run(Kind::Time)?, run(Kind::Money)?, run(Kind::Turn)?],
        maps,
        help,
    })
}

static SURVIVAL: OnceLock<Option<Survival>> = OnceLock::new();

/// Dual Strike's Survival, from the pack (None without it).
pub fn survival() -> Option<&'static Survival> {
    SURVIVAL.get_or_init(|| crate::ds_pack::pack().and_then(read)).as_ref()
}

// --- Dual Strike's rank and score rules -----------------------------------

/// The final rank for what is left of a basic run (`sub_020EAD98`): 5 S,
/// 4 A, 3 B, 2 C. Time in frames, money in G, turns in days.
pub fn rank(kind: Kind, left: u32) -> u8 {
    let t = match kind {
        Kind::Time => [32400, 21600, 10800], // 9, 6 and 3 minutes
        Kind::Money => [50000, 25000, 10000],
        Kind::Turn => [25, 15, 5],
    };
    if left >= t[0] {
        5
    } else if left >= t[1] {
        4
    } else if left >= t[2] {
        3
    } else {
        2
    }
}

pub fn rank_letter(r: u8) -> char {
    match r {
        5 => 'S',
        4 => 'A',
        3 => 'B',
        _ => 'C',
    }
}

/// The points a cleared run's leftover is worth (`sub_020EB024`): a point
/// per 2 seconds, 10 per day, 1 per 200 G.
pub fn leftover_points(kind: Kind, left: u32) -> u32 {
    match kind {
        Kind::Time => left / 60 / 2,
        Kind::Turn => left * 10,
        Kind::Money => left / 200,
    }
}

/// Dual Strike caps a run's points at 9999.
pub const MAX_POINTS: u32 = 9999;

/// The rank of a Champion run (`sub_020EAD98`, kinds 3..5: it goes by the
/// maps cleared, whatever the budget): 5 S from 20, 4 A from 15, 3 B from 10,
/// else 2 C.
pub fn champion_rank(maps: u32) -> u8 {
    if maps >= 20 {
        5
    } else if maps >= 15 {
        4
    } else if maps >= 10 {
        3
    } else {
        2
    }
}

/// The bonus points of a Champion run (`sub_020EB024`, kinds 3..5): 5 for
/// the first map cleared, 10 more for the second, and so on (5 x n x
/// (n + 1) / 2), at most 9999.
pub fn champion_bonus(maps: u32) -> u32 {
    (5 * maps * (maps + 1) / 2).min(MAX_POINTS)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tiles_convert() {
        assert_eq!(convert_tile(0x1A1), 0x192);
        assert_eq!(convert_tile(0x1B9), 0x1D9);
        assert_eq!(convert_tile(0x1BD), 0x1DD);
        assert_eq!(convert_tile(0x02A), 0x02A);
        assert_eq!(convert_unit(25), Some(crate::roster::CARRIER));
        assert_eq!(convert_unit(26), Some(crate::roster::OOZIUM));
        assert_eq!(convert_unit(0), None);
    }

    #[test]
    fn ranks() {
        assert_eq!(rank(Kind::Money, 50000), 5);
        assert_eq!(rank(Kind::Money, 49999), 4);
        assert_eq!(rank(Kind::Turn, 4), 2);
        assert_eq!(rank(Kind::Time, 32400), 5);
        assert_eq!(leftover_points(Kind::Money, 500000), 2500);
    }

    #[test]
    fn champion_rules() {
        assert_eq!((champion_rank(0), champion_rank(9), champion_rank(10)), (2, 2, 3));
        assert_eq!(
            (
                champion_rank(14),
                champion_rank(15),
                champion_rank(19),
                champion_rank(20)
            ),
            (3, 4, 4, 5)
        );
        assert_eq!(
            (
                champion_bonus(0),
                champion_bonus(1),
                champion_bonus(2),
                champion_bonus(11)
            ),
            (0, 5, 15, 330)
        );
        assert_eq!(champion_bonus(255), 9999);
    }

    #[test]
    fn cos_convert() {
        assert_eq!(convert_co(2), Some(1)); // Andy
        assert_eq!(convert_co(10), Some(9)); // Drake
        assert_eq!(convert_co(14), Some(73)); // Koal
    }

    /// With a Dual Strike ROM (TANGOAW2_DS_ROM), the three runs read as
    /// Dual Strike has them.
    #[test]
    fn runs_from_the_rom() {
        let Some(path) = std::env::var_os("TANGOAW2_DS_ROM") else {
            return;
        };
        let Ok(buf) = std::fs::read(path) else { return };
        crate::ds_art::offer(&buf);
        let s = survival().expect("survival data");
        assert_eq!(s.maps.len(), 33);
        assert_eq!(s.run(Kind::Money).budget, 500000);
        assert_eq!(s.run(Kind::Turn).budget, 99);
        assert_eq!(s.run(Kind::Time).budget, 90000);
        assert_eq!(s.run(Kind::Money).champion_budget, 600000);
        assert_eq!(s.run(Kind::Turn).champion_budget, 120);
        assert_eq!(s.run(Kind::Time).champion_budget, 108000);
        let first = |k| &s.maps[s.run(k).maps[0]].name;
        assert_eq!(first(Kind::Money), "Silo Sweep");
        assert_eq!(first(Kind::Turn), "Convoy Cape");
        assert_eq!(first(Kind::Time), "Red Heart");
        let structure = |n: &str| s.maps.iter().find(|m| m.name == n).unwrap().structure;
        assert_eq!(structure("Convoy Cape"), Some(Structure::MissilePad));
        assert_eq!(structure("Lone Wolf"), Some(Structure::MissilePad));
        assert_eq!(structure("Silo Sweep"), Some(Structure::Fortress));
        assert_eq!(s.maps.iter().filter(|m| m.structure.is_some()).count(), 3);
        // Each map's own colours (Lone Wolf's computer is Black Hole, Fenced
        // In's Blue Moon), not the map before it's.
        let colours = |n: &str| s.maps.iter().find(|m| m.name == n).unwrap().colours;
        assert_eq!(colours("Lone Wolf"), [1, 5, 3, 4]);
        assert_eq!(colours("Fenced In"), [1, 2, 3, 4]);
        for m in &s.maps {
            // A map with a structure names its picture, the one its tiles show.
            assert_eq!(m.structure, Structure::of_tiles(&m.tiles), "{}", m.name);
            assert!(
                m.width as usize * m.height as usize <= 0x508 && m.height <= 40,
                "{}",
                m.name
            );
            assert!(m.tiles.iter().all(|&t| t < 0x200), "{}", m.name);
            assert!(m.cos[0].is_some(), "{} has a computer CO", m.name);
        }
    }
}
