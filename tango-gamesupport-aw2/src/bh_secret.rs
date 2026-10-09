//! The secret mission, M31 "The Colonel's Vault" (opens with `Needs::Bonds(..)`: every
//! hidden bond earned). Its map is `five/bh/bh31.txt` (built by `five/bhmap.py`); the
//! scenes are placeholders until the design bible's dialogue (docs/BH_CAMPAIGN.md 4.7a)
//! is wired in.

// (the builders' imports: each act uses what it needs)
#![allow(unused_imports)]

use mgba::core::Core;

use crate::bh_campaign::{region, roster};
use crate::custom_campaign::{co, colour, unit, *};

/// Sonja's three Vault Trucks (the map's named APCs).
const TRUCKS: [&str; 3] = ["vault1", "vault2", "vault3"];
/// The dock tiles: two trucks here and the heist is lost.
const DOCK: Rect = Rect::new(25, 9, 27, 11);

fn truck_cells(core: &mut Core) -> Vec<(u8, u8)> {
    TRUCKS
        .iter()
        .filter_map(|n| unit_by_name(core, n))
        .filter(|(_, alive)| *alive)
        .map(|(a, _)| (core.raw_read_8(a + 2, -1), core.raw_read_8(a + 3, -1)))
        .collect()
}

fn all_trucks_gone(core: &mut Core) -> bool {
    truck_cells(core).is_empty()
}

fn two_trucks_docked(core: &mut Core) -> bool {
    truck_cells(core).iter().filter(|(x, y)| DOCK.has(*x, *y)).count() >= 2
}

fn bh31() -> MissionDef {
    let mut m = MissionDef::new("bh31", "The Colonel's Vault");
    m.objective = "Destroy the 3 Vault Trucks or take the Safe House. 8 days.";
    m.map = MapSrc::Built("bh31");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(4000),
        // Sonja and her raiders, in Yellow Comet's colours.
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::SONJA)).funds(0),
    ];
    m.fog = true;
    m.day_limit = 8;
    m.rank_days = 6;
    m.intro = Scene::new(vec![troop("Von Bolt's Hall. Sonja's trucks are leaving with the vault.")]);
    m.victory = Scene::new(vec![troop("The vault is safe.")]);
    m.after = Scene::new(vec![troop("Sonja is staying to audit the books.")]);
    m.triggers = vec![
        Trigger::new(When::AfterAction, Cond::Custom(all_trucks_gone), vec![Action::Win]).repeating(),
        Trigger::new(When::AfterAction, Cond::Custom(two_trucks_docked), vec![Action::Lose]).repeating(),
        Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: 9 }, vec![Action::Lose]).repeating(),
    ];
    m.needs = Needs::Bonds(vec!["bh28"]);
    m.recruits = vec![roster::SONJA];
    m.flag = region::BLACK_HOLE[5];
    m.stars = 4;
    m
}

/// The secret mission.
pub fn missions() -> Vec<MissionDef> {
    vec![bh31()]
}

fn troop(text: &'static str) -> Line {
    Line::soldier(colour::BLACK_HOLE, text)
}
