//! The secret mission, M31 "The Colonel's Vault" (opens with `Needs::Bonds(..)`: every
//! hidden bond earned). Its map is `five/bh/bh31.txt` (built by `five/bhmap.py`); the
//! dialogue is the design bible's
//! (docs/BH_CAMPAIGN.md 4.7a, converted into `bh_act5b_text.rs`).

// (the builders' imports: each act uses what it needs)
#![allow(unused_imports)]

use mgba::core::Core;

use crate::bh_campaign::{region, roster};
use crate::bh_act5b::{built_units, meter, roles, text};
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

fn charge_sonja(core: &mut Core) {
    meter(core, 2, 100);
}

fn a_truck_lost(core: &mut Core) -> bool {
    TRUCKS.iter().filter_map(|n| unit_by_name(core, n)).any(|(_, alive)| !alive)
}

/// "On day `d`, at the start of the player's turn": fires once, on that day.
fn on_day(d: u16, then: Vec<Action>) -> Trigger {
    Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: d }, then).repeating()
}

fn bh31() -> MissionDef {
    let mut m = MissionDef::new("bh31", "The Colonel's Vault");
    m.objective = "Destroy the 3 Vault Trucks or take the Safe House. 8 days.";
    m.map = MapSrc::Built("bh31");
    // The Vault Trucks hold (TODO(engine): a march-to-the-dock action; no AW2 role drives a unit to a cell of
    // the mission's choosing), as do the vault's guard Infantry, the Rockets, the Anti-Air, the Transport
    // Copters and the dock's Lander; the raiders on the roads advance.
    m.units = roles(
        built_units("bh31"),
        1,
        &[(3, 8), (5, 8), (4, 9), (3, 7), (5, 7), (8, 6), (9, 9), (8, 5), (8, 15), (27, 9)],
    );
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(4000),
        // Sonja and her raiders, in Yellow Comet's colours.
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::SONJA)).funds(0),
    ];
    m.fog = true;
    m.day_limit = 8;
    m.rank_days = 6;
    m.intro = Scene::new(text::m31_pre());
    m.victory = Scene::new(text::m31_post());
    // The world map: the MAP scene, Sonja's defection, then the letter at Comet Keep.
    let mut after_lines = text::m31_map();
    after_lines.extend(text::m31_defect());
    after_lines.extend(text::m31_kanbei());
    m.after = Scene::new(after_lines);
    m.triggers = vec![
        on_day(2, vec![Action::Scene(Scene::new(text::m31_day_2()))]),
        // Day 3: two decoys (empty APCs) leave on the other road.
        on_day(
            3,
            vec![
                Action::Scene(Scene::new(text::m31_day_3())),
                Action::Spawn(vec![UnitDef::new(2, unit::APC, 9, 6), UnitDef::new(2, unit::APC, 9, 14)]),
            ],
        ),
        // Day 5: Sonja's power (her meter is full: the fog thickens as her vision grows).
        on_day(5, vec![Action::Scene(Scene::new(text::m31_day_5())), Action::Custom(charge_sonja)]),
        Trigger::new(When::AfterAction, Cond::Custom(a_truck_lost), vec![Action::Scene(Scene::new(text::m31_when_the_first_vault_truck_is_destroyed()))]),
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

