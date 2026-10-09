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
/// The dock tiles: a truck here and the heist is lost.
const DOCK: Rect = Rect::new(25, 9, 27, 11);   // (the dock's land is x 25..26; x 27 is the sea beside it)

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

fn a_truck_docked(core: &mut Core) -> bool {
    truck_cells(core).iter().any(|(x, y)| DOCK.has(*x, *y))
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
    m.objective = "Destroy the 3 Vault Trucks before one docks. 8 days.";
    m.map = MapSrc::Built("bh31");
    // The Vault Trucks hold (TODO(engine): a march-to-the-dock action; no AW2 role drives a unit to a cell of
    // the mission's choosing), as do the vault's guard Infantry, the Rockets, the Anti-Air, the Transport
    // Copters and the dock's Lander; the raiders on the roads advance.
    m.units = roles(
        built_units("bh31"),
        1,
        // the trucks, the road-block Infantry, the Anti-Air and Missiles, the Transport Copters and the ships hold;
        // the Tank, Md Tank and Neotank counter-attack
        &[(11, 6), (11, 14), (5, 8), (12, 6), (11, 5), (12, 14), (11, 15), (11, 10), (12, 10), (16, 6), (19, 6), (16, 14), (19, 14), (21, 10), (22, 8), (22, 12), (23, 4), (23, 14), (27, 9), (27, 13)],
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
        // Day 3: the third truck (vault3) leaves the vault by the ford road (y 10).
        // TODO(engine): the "march" action that moves a named unit along a fixed path each day (the three trucks reach
        // the docks around day 8: A the North Road y 6, B the South Road y 14, C the ford road y 10 from day 3), and
        // the Black Cannon's "disable / restore" (jammed at the start, restored by capturing the Control Room (8,14)).
        on_day(3, vec![Action::Scene(Scene::new(text::m31_day_3()))]),
        // Day 5: Sonja's power (her meter is full: the fog thickens as her vision grows).
        on_day(5, vec![Action::Scene(Scene::new(text::m31_day_5())), Action::Custom(charge_sonja)]),
        Trigger::new(When::AfterAction, Cond::Custom(a_truck_lost), vec![Action::Scene(Scene::new(text::m31_when_the_first_vault_truck_is_destroyed()))]),
        Trigger::new(When::AfterAction, Cond::Custom(all_trucks_gone), vec![Action::Win]).repeating(),
        Trigger::new(When::AfterAction, Cond::Custom(a_truck_docked), vec![Action::Lose]).repeating(),
        // the Black Hole HQ captured loses (AW2's own rule too)
        Trigger::new(When::AfterAction, Cond::Not(Box::new(Cond::OwnerAt { x: 3, y: 14, army: 1 })), vec![Action::Lose]).repeating(),
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

