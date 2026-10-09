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
const TRUCKS: [&str; 3] = ["vault1", "vault2", "vault3"];

/// The trucks' roads, as corner points (`five/bh/bh31.txt`): A the north switchbacks (52 move points from its start to the
/// dock), B the south serpentine (55), C the ford road and its two legs (39, from day 3).
const A_ROAD: [(u8, u8); 11] = [(19, 5), (25, 5), (25, 1), (36, 1), (36, 4), (27, 4), (27, 7), (36, 7), (37, 7), (37, 12), (38, 12)];
const B_ROAD: [(u8, u8); 8] = [(19, 20), (35, 20), (35, 23), (26, 23), (26, 25), (37, 25), (37, 12), (38, 12)];
const C_ROAD: [(u8, u8); 9] = [(24, 11), (35, 11), (35, 14), (28, 14), (28, 17), (36, 17), (37, 17), (37, 12), (38, 12)];

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
        &[(19, 5), (20, 4), (18, 4), (19, 20), (20, 21), (18, 21), (23, 1), (24, 1), (30, 0), (31, 0), (37, 3), (35, 2), (37, 4), (29, 3), (32, 9), (24, 19), (25, 19), (36, 20), (36, 21), (27, 22), (30, 24), (31, 24), (34, 24), (23, 11), (23, 12), (29, 10), (30, 10), (34, 12), (29, 16), (30, 16), (34, 13), (30, 9), (33, 18), (41, 10), (35, 27)],
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
    // The two Black Cannons (ours; they reach nine columns either side and twelve rows down, never the dock) are jammed until
    // day 3: restored on day 3 they fire from day 4.
    m.jams = vec![
        JamDef { at: (25, 9), until: Cond::DayAtLeast(3) },
        JamDef { at: (25, 14), until: Cond::DayAtLeast(3) },
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

