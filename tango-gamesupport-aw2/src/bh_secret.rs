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

/// The dock tiles: one truck here and the heist is lost.
const DOCK: Rect = Rect::new(38, 11, 40, 13);   // (the dock's land is x 38..39; x 40 is the sea beside it)
/// Where truck C appears on day 3: the ford road's east side, behind the blocking Tank at (23,11).
const TRUCK_C: (u8, u8) = (24, 11);

/// Sonja's Vault Trucks (her only APCs): where they are. A and B are on the map from the start, C is spawned on
/// day 3 (a spawned unit has no name, so the trucks are told apart by their type).
fn truck_cells(core: &mut Core) -> Vec<(u8, u8)> {
    units_of(core, 2).iter().filter(|u| u.1 == unit::APC).map(|u| (u.2, u.3)).collect()
}

/// How many trucks there should be by now: two, and three from day 3.
fn trucks_due(core: &Core) -> usize {
    if day(core) >= 3 {
        3
    } else {
        2
    }
}

/// All three trucks are gone (never before truck C has appeared).
fn all_trucks_gone(core: &mut Core) -> bool {
    day(core) >= 3 && truck_cells(core).is_empty()
}

fn a_truck_docked(core: &mut Core) -> bool {
    truck_cells(core).iter().any(|(x, y)| DOCK.has(*x, *y))
}

fn charge_sonja(core: &mut Core) {
    meter(core, 2, 100);
}

fn a_truck_lost(core: &mut Core) -> bool {
    truck_cells(core).len() < trucks_due(core)
}

/// "On day `d`, at the start of the player's turn": fires once, on that day.
fn on_day(d: u16, then: Vec<Action>) -> Trigger {
    Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: d }, then).repeating()
}

fn day3_lines() -> Vec<Line> {
    let mut v = vec![Line::soldier(colour::BLACK_HOLE, "A third truck rolls out of the ford woods.")];
    v.extend(text::m31_day_3());
    v
}

fn bh31() -> MissionDef {
    let mut m = MissionDef::new("bh31", "The Colonel's Vault");
    m.objective = "Destroy the 3 Vault Trucks before one docks. 11 days.";
    m.map = MapSrc::Built("bh31");
    // Yellow Comet's units: the Vault Trucks, their escorts and the road-block groups at the chokepoints hold (the
    // trucks wait for the engine's march action: TODO(engine), no AW2 role drives a unit to a cell of the mission's
    // choosing); the Anti-Air, Artillery, Rockets, Missiles, Transport Copters and ships hold too. Four units
    // advance on Black Hole: two Neotanks and two Tanks (the mobile reserve).
    m.units = roles(
        built_units("bh31"),
        1,
        &[(19, 5), (20, 5), (18, 5), (19, 20), (20, 20), (18, 20), (25, 3), (25, 2), (31, 1), (32, 1), (36, 3), (36, 2), (33, 1), (30, 4), (34, 7), (25, 20), (26, 20), (35, 21), (35, 22), (28, 23), (31, 25), (32, 25), (35, 25), (23, 11), (23, 12), (30, 11), (31, 11), (34, 12), (30, 17), (31, 17), (35, 14), (30, 9), (33, 18), (41, 10), (35, 27)],
    );
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(4000),
        // Sonja and her raiders, in Yellow Comet's colours.
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::SONJA)).funds(0),
    ];
    m.fog = true;
    m.day_limit = 11;
    m.rank_days = 8;
    m.intro = Scene::new(text::m31_pre());
    m.victory = Scene::new(text::m31_post());
    // The world map: the MAP scene, Sonja's defection, then the letter at Comet Keep.
    let mut after_lines = text::m31_map();
    after_lines.extend(text::m31_defect());
    after_lines.extend(text::m31_kanbei());
    m.after = Scene::new(after_lines);
    m.triggers = vec![
        on_day(2, vec![Action::Scene(Scene::new(text::m31_day_2()))]),
        // Day 3: the third truck rolls out of the ford woods (spawned east of the ford; no name, see `truck_cells`).
        // TODO(engine): the "march" action: each truck moves its fixed road path at full APC speed (6 move points a
        // day): A 52 move points (the north switchbacks), B 55 (the south serpentine), C 39 (the ford road, from day 3).
        on_day(
            3,
            vec![Action::Scene(Scene::new(day3_lines())), Action::Spawn(vec![UnitDef::new(2, unit::APC, TRUCK_C.0, TRUCK_C.1)])],
        ),
        // Day 5: Sonja's power (her meter is full: the fog thickens as her vision grows).
        on_day(5, vec![Action::Scene(Scene::new(text::m31_day_5())), Action::Custom(charge_sonja)]),
        // The two Black Cannons (ours, (24..26, 8..10) and (24..26, 13..15), facing south; they reach nine columns either
        // side and twelve rows down, never the dock): off at the start, on from day 4. TODO(engine): the disable /
        // restore action (a day condition); today they are on from the start.
        Trigger::new(When::TurnStart, Cond::DayAtLeast(4), vec![Action::Scene(Scene::new(text::m31_cannon_on()))]),
        Trigger::new(When::AfterAction, Cond::Custom(a_truck_lost), vec![Action::Scene(Scene::new(text::m31_when_the_first_vault_truck_is_destroyed()))]),
        Trigger::new(When::AfterAction, Cond::Custom(all_trucks_gone), vec![Action::Win]).repeating(),
        Trigger::new(When::AfterAction, Cond::Custom(a_truck_docked), vec![Action::Lose]).repeating(),
        // (a truck that docks on Sonja's turn is seen when the player's turn starts)
        Trigger::new(When::TurnStart, Cond::Custom(a_truck_docked), vec![Action::Lose]).repeating(),
        // the Black Hole HQ captured loses (AW2's own rule too)
        Trigger::new(When::AfterAction, Cond::Not(Box::new(Cond::OwnerAt { x: 3, y: 20, army: 1 })), vec![Action::Lose]).repeating(),
        Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: 12 }, vec![Action::Lose]).repeating(),
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

