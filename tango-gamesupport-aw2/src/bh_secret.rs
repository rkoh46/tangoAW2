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
const DOCK: Rect = Rect::new(38, 9, 40, 11);   // (the dock's land is x 38..39; x 40 is the sea beside it)
/// Where truck C appears on day 3: the ford road's east side (C's first leg).
const TRUCK_C: (u8, u8) = (24, 9);
const TRUCKS: [&str; 3] = ["vault1", "vault2", "vault3"];

/// The trucks' roads, as corner points (`five/bh/bh31.txt`): A the hill switchbacks and the east leg (55 move points from its start to the
/// dock), B the south serpentine (56), C the middle zone's three legs (41, from day 3).
const A_ROAD: [(u8, u8); 9] = [(9, 2), (18, 2), (18, 4), (9, 4), (9, 6), (20, 6), (37, 6), (37, 10), (38, 10)];
const B_ROAD: [(u8, u8); 9] = [(16, 16), (34, 16), (34, 18), (24, 18), (24, 20), (34, 20), (37, 20), (37, 10), (38, 10)];
const C_ROAD: [(u8, u8); 9] = [(24, 9), (34, 9), (34, 11), (24, 11), (24, 13), (34, 13), (37, 13), (37, 10), (38, 10)];

/// Every cell of a road given by its corners.
fn cells(corners: &[(u8, u8)]) -> Vec<(u8, u8)> {
    let mut v = vec![corners[0]];
    for w in corners.windows(2) {
        let (mut x, mut y) = w[0];
        while (x, y) != w[1] {
            x = if x < w[1].0 { x + 1 } else if x > w[1].0 { x - 1 } else { x };
            y = if y < w[1].1 { y + 1 } else if y > w[1].1 { y - 1 } else { y };
            v.push((x, y));
        }
    }
    v
}

fn any_truck(f: impl Fn(&'static str) -> Cond) -> Cond {
    Cond::Any(TRUCKS.iter().map(|n| f(n)).collect())
}

fn charge_sonja(core: &mut Core) {
    meter(core, 2, 100);
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
    // Yellow Comet's units: the trucks (which march), their escorts and the road-block groups hold, as do the
    // Anti-Air, Artillery, Rockets, Missiles, Transport Copters and the ships; two Neotanks and two Tanks advance on
    // Black Hole. None of Sonja's units stands on a truck's road (a march stops at an occupied cell).
    // The Vault Trucks have no fuel for the computer's own dispatch (an APC's AI would load the Infantry beside it and drive
    // off: the march is what moves them, and does not use fuel).
    m.units = roles(
        built_units("bh31"),
        1,
        &[(9, 2), (10, 1), (8, 3), (16, 16), (17, 15), (15, 17), (14, 3), (17, 5), (19, 3), (19, 7), (24, 4), (25, 4), (30, 3), (30, 4), (33, 4), (35, 5), (31, 7), (22, 10), (25, 5), (31, 12), (36, 11), (36, 8), (20, 13), (24, 17), (25, 22), (36, 18), (29, 19), (30, 22), (37, 22), (36, 14), (36, 7), (30, 8), (32, 15), (41, 10), (35, 27)],
    )
    .into_iter()
    .map(|u| if u.name.is_some() { u.fuel(0) } else { u })
    .collect();
    // The trucks drive their roads at full APC speed (6 move points a day), A and B from day 1, C from day 3.
    m.marches = vec![
        MarchDef::speed("vault1", &cells(&A_ROAD), 6),
        MarchDef::speed("vault2", &cells(&B_ROAD), 6),
        MarchDef::speed("vault3", &cells(&C_ROAD), 6).from(3),
    ];
    // The two Black Cannons (ours: (27,3) facing south over the east leg and the middle zone, (27,23) facing north over the south
    // and middle zones; they reach nine columns either side and twelve rows, never the dock) are jammed until
    // day 4 and fire from day 4's Black Hole turn (measured with the fog off: first hits on day 4; with `DayAtLeast(3)` they
    // fired on day 3). In the fog a cannon only fires at what Black Hole sees.
    m.jams = vec![
        JamDef { at: (26, 2), until: Cond::DayAtLeast(4) },
        JamDef { at: (26, 22), until: Cond::DayAtLeast(4) },
    ];
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
        // Day 3: the third truck rolls out of the ford woods (it marches from now on).
        Trigger::new(
            When::TurnStart,
            Cond::DayAtLeast(3),
            vec![
                Action::Scene(Scene::new(day3_lines())),
                Action::Spawn(vec![UnitDef::new(2, unit::APC, TRUCK_C.0, TRUCK_C.1).fuel(0).named("vault3")]),
            ],
        ),
        // Day 4: the cannons are online.
        on_day(4, vec![Action::Scene(Scene::new(text::m31_cannon_on()))]),
        // Day 5: Sonja's power (her meter is full: the fog thickens as her vision grows).
        on_day(5, vec![Action::Scene(Scene::new(text::m31_day_5())), Action::Custom(charge_sonja)]),
        Trigger::new(
            When::AfterAction,
            any_truck(Cond::UnitGone),
            vec![Action::Scene(Scene::new(text::m31_when_the_first_vault_truck_is_destroyed()))],
        ),
        // The win: all three trucks destroyed (truck C is not "gone" before it has appeared, so never before day 3).
        Trigger::new(When::AfterAction, Cond::All(TRUCKS.iter().map(|n| Cond::UnitGone(n)).collect()), vec![Action::Win]).repeating(),
        Trigger::new(When::TurnStart, Cond::All(TRUCKS.iter().map(|n| Cond::UnitGone(n)).collect()), vec![Action::Win]).repeating(),
        // The losses: a truck on a dock tile (also seen when the player's turn starts, after Sonja's), the Black Hole HQ
        // captured, day 12 starting.
        Trigger::new(When::AfterAction, any_truck(|n| Cond::NamedIn { name: n, area: DOCK }), vec![Action::Lose]).repeating(),
        Trigger::new(When::TurnStart, any_truck(|n| Cond::NamedIn { name: n, area: DOCK }), vec![Action::Lose]).repeating(),
        Trigger::new(When::AfterAction, Cond::Not(Box::new(Cond::OwnerAt { x: 3, y: 20, army: 1 })), vec![Action::Lose]).repeating(),
        Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: 12 }, vec![Action::Lose]).repeating(),
    ];
    m.needs = Needs::Bonds(vec!["bh28"]);
    m.recruits = vec![roster::SONJA];
    m.flag = region::BLACK_HOLE[2];
    m.stars = 4;
    m
}

/// The secret mission.
pub fn missions() -> Vec<MissionDef> {
    vec![bh31()]
}

