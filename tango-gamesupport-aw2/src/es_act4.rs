//! Act IV, Pax: M13 The Free Port (against Black Hole among others), M14 Varro's Gambit, M15 Pax Romana, M16 Sol Invictus. Maps `five/es/spec/es13.py` ..
//! `es16.py`, dialogue `es_text/act4.txt`.

#![allow(unused_imports)]

use mgba::core::Core;

use crate::campaign_model::VolcanoDef;
use crate::custom_campaign::{co, colour, unit, *};
use crate::es_campaign::{after, deployment, leads, on_day, region, roster, wave, STATE};
use crate::es_co::{AURELIA, CASSIUS, KLAUS, LIVIA, VARRO};
use crate::es_text::{chain, scene};

fn owns(x: u8, y: u8) -> Cond {
    Cond::OwnerAt { x, y, army: 1 }
}

/// Everyone the player may pick: the four leads and the two tag partners.
fn everyone() -> Vec<u8> {
    crate::es_campaign::ROSTER.iter().map(|r| r.0).collect()
}

// --- M13 The Free Port (Black Hole's yard: inventions allowed) ---------------------------------

/// The Harbour Office, the neutral city in the middle of the port.
const OFFICE: (u8, u8) = (19, 15);

fn reset_hold(core: &mut Core) {
    core.raw_write_8(STATE, -1, 0);
    core.raw_write_8(STATE + 1, -1, 0);
}

/// At each of the player's turn starts: one more turn if the player holds the Office, else none. The counter (STATE) belongs to the battle that
/// wrote it: it counts on only if the last count was the day before (STATE + 1), so memory left by an earlier battle never wins the mission.
fn count_hold(core: &mut Core) {
    let army = crate::ds_campaign::player_army(core);
    let day = crate::custom_campaign::day(core).min(255) as u8;
    let last = core.raw_read_8(STATE + 1, -1);
    if last == day {
        return;
    }
    let before = if last != 0 && last + 1 == day {
        core.raw_read_8(STATE, -1)
    } else {
        0
    };
    let n = if owner_at(core, OFFICE.0, OFFICE.1) == army {
        before.saturating_add(1)
    } else {
        0
    };
    core.raw_write_8(STATE, -1, n);
    core.raw_write_8(STATE + 1, -1, day);
}

fn held_three(core: &mut Core) -> bool {
    core.raw_read_8(STATE, -1) >= 3
}

fn es13() -> MissionDef {
    let mut m = MissionDef::new("es13", "The Free Port");
    m.objective = "Take the Harbour Office and hold it for 3 days. Four flags, no friends.";
    m.map = MapSrc::Built("es13");
    m.look = 3; // wasteland (the bays are lava)
    m.weather = Weather::Clear;
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::PickPair).funds(6000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JAVIER)).funds(7000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::SONJA)).funds(7000),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::KINDLE)).funds(8000),
    ];
    m.pool = everyone();
    m.units = deployment("es13");
    m.rank_days = 14;
    m.intro = scene("m13_pre");
    m.victory = scene("m13_post");
    m.after = chain(&["m13_map"]);
    m.triggers = vec![
        on_day(1, None, vec![Action::Custom(reset_hold)]),
        Trigger::new(When::TurnStart, Cond::DayAtLeast(2), vec![Action::Custom(count_hold)]).repeating(),
        on_day(4, None, vec![Action::Scene(scene("m13_day4"))]),
        Trigger::new(When::TurnStart, Cond::Custom(held_three), vec![Action::Win]).repeating(),
    ];
    m.flag = region::ACT4[0];
    m.stars = 4;
    m.needs = Needs::All(vec!["es12"]);
    m
}

// --- M14 Varro's Gambit ------------------------------------------------------------------------

/// The legion's own reserves come up the camp road beside the player's HQ on days 5 and 8.
const LEGION: [(u8, u8); 4] = [(7, 14), (8, 14), (6, 14), (9, 15)];
/// Castra Maxima's reserve road, inside the camp's east side (`five/es/spec/es14.py`): the Consul's reserves reach the HQ from here on days 5 and 8.
const RESERVE: [(u8, u8); 4] = [(40, 12), (40, 13), (40, 15), (40, 16)];

/// Day 4: Cassius's army (army 3) goes over to the player's side (AW2's team byte of its player block).
fn cassius_changes_sides(core: &mut Core) {
    let players = crate::five::players(core);
    let team = core.raw_read_8(players + 0x3C + 0x2A, -1);
    core.raw_write_8(players + 0x3C * 3 + 0x2A, -1, team);
}

fn es14() -> MissionDef {
    let mut m = MissionDef::new("es14", "Varro's Gambit");
    m.objective = "Storm Castra Maxima: take the Consul's HQ or rout his army.";
    m.map = MapSrc::Built("es14");
    m.armies = vec![
        ArmyDef::new(colour::BLUE_MOON, CoSpec::PickPartner(KLAUS)).funds(6000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(VARRO)).funds(14000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(CASSIUS)).funds(5000),
    ];
    m.pool = vec![AURELIA, CASSIUS, LIVIA, co::KANBEI, co::COLIN];
    m.units = deployment("es14");
    m.rank_days = 12;
    m.intro = scene("m14_pre");
    m.victory = scene("m14_post");
    m.after = chain(&["m14_map"]);
    m.triggers = vec![
        on_day(
            4,
            None,
            vec![Action::Scene(scene("m14_day4")), Action::Custom(cassius_changes_sides)],
        ),
        // The legion's convoy reaches the camp road on days 5 and 8, and the Consul's reserves march in from the camp's east road.
        on_day(5, None, vec![Action::Spawn(wave(1, unit::MD_TANK, &LEGION[0..2]))]),
        on_day(
            8,
            None,
            vec![Action::Spawn(
                [
                    wave(1, unit::NEOTANK, &LEGION[2..3]),
                    wave(1, unit::MD_TANK, &LEGION[3..4]),
                ]
                .concat(),
            )],
        ),
        on_day(5, None, vec![Action::Spawn(wave(2, unit::MD_TANK, &RESERVE[0..2]))]),
        on_day(
            8,
            None,
            vec![Action::Spawn(
                [
                    wave(2, unit::NEOTANK, &RESERVE[2..3]),
                    wave(2, unit::MD_TANK, &RESERVE[3..4]),
                ]
                .concat(),
            )],
        ),
        // The Consul's second line (the ramp towards Stormhold): Tanks on day 3, Md Tanks on day 6.
        on_day(3, None, vec![Action::Spawn(wave(2, unit::TANK, &RESERVE[0..2]))]),
        on_day(6, None, vec![Action::Spawn(wave(2, unit::MD_TANK, &RESERVE[2..4]))]),
    ];
    m.flag = region::ACT4[1];
    m.stars = 4;
    m.needs = Needs::All(vec!["es13"]);
    m
}

// --- M15 Pax Romana ----------------------------------------------------------------------------

/// The Strait Fort's harbour, in the inlet of the east shore (`five/es/spec/es15.py`): the port to take once the flagship is sunk.
const HARBOUR: (u8, u8) = (39, 13);
/// Open water along the strait's top edge (`five/es/spec/es15.py`: rows 0 and 1 are sea from x = 9 to 38): where the Accord's reinforcements appear.
const STRAIT: [(u8, u8); 7] = [(33, 0), (35, 0), (30, 0), (31, 0), (34, 1), (32, 0), (37, 0)];

fn es15() -> MissionDef {
    let mut m = MissionDef::new("es15", "Pax Romana");
    m.objective = "Break the blockade: sink the flagship and take the Strait Fort's harbour.";
    m.map = MapSrc::Built("es15");
    m.armies = vec![
        ArmyDef::new(colour::BLUE_MOON, CoSpec::PickPair).funds(10000),
        // The Accord's strait fleet: Drake's ships and the fort, and Sensei's air wing, allied (the same team).
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::DRAKE))
            .team(2)
            .funds(14000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::SENSEI))
            .team(2)
            .funds(12000),
    ];
    m.pool = everyone();
    m.units = deployment("es15");
    m.rank_days = 16;
    m.intro = scene("m15_pre");
    m.victory = scene("m15_post");
    m.after = chain(&["m15_map"]);
    m.triggers = vec![
        // Day 6: Nell's call offers the Accord's table; the fleet fights on.
        on_day(6, None, vec![Action::Scene(scene("m15_day6"))]),
        // The Accord's reinforcements come in from the north sea (the strait's open water along the top edge): Drake's ships and Sensei's air wing.
        on_day(3, None, vec![Action::Spawn(wave(2, unit::CRUISER, &STRAIT[0..1]))]),
        on_day(
            5,
            None,
            vec![Action::Spawn(
                [
                    wave(2, unit::BATTLESHIP, &STRAIT[1..2]),
                    wave(3, unit::FIGHTER, &STRAIT[2..4]),
                ]
                .concat(),
            )],
        ),
        on_day(
            8,
            None,
            vec![Action::Spawn(
                [
                    wave(2, unit::BATTLESHIP, &STRAIT[4..5]),
                    wave(3, unit::BOMBER, &STRAIT[5..6]),
                    wave(3, unit::B_COPTER, &STRAIT[6..7]),
                ]
                .concat(),
            )],
        ),
        after(
            Cond::All(vec![Cond::UnitGone("flagship"), owns(HARBOUR.0, HARBOUR.1)]),
            vec![Action::Win],
        ),
    ];
    m.flag = region::ACT4[2];
    m.stars = 4;
    m.needs = Needs::All(vec!["es14"]);
    m
}

// --- M16 Sol Invictus --------------------------------------------------------------------------

/// Day 6: both defenders' power meters are full (the reserves scene says so): AW2's meter at the player block +0x20, for the army `army`.
fn charge(core: &mut Core, army: u32) {
    let p = crate::tag::player(core, army);
    let (co, uses) = (core.raw_read_8(p + 0x1D, -1), core.raw_read_8(p + 0x25, -1));
    let full = crate::tag::scop_cost(core, co, uses);
    if core.raw_read_32(p + 0x20, -1) < full {
        core.raw_write_32(p + 0x20, -1, full);
    }
}

fn charge_defenders(core: &mut Core) {
    charge(core, 2);
    charge(core, 3);
}

/// Eagle's air wing's reserve cells along the north airfield (`five/es/spec/es16.py`).
const AIRFIELD: [(u8, u8); 10] = [
    (27, 0),
    (28, 0),
    (29, 0),
    (30, 0),
    (31, 0),
    (32, 0),
    (33, 0),
    (34, 0),
    (32, 1),
    (33, 1),
];
/// Hachi's reserves come out of the south gate and the west gate.
const SOUTH_GATE: [(u8, u8); 5] = [(33, 13), (34, 13), (36, 13), (36, 14), (35, 15)];
const WEST_GATE: [(u8, u8); 6] = [(27, 9), (28, 9), (26, 10), (28, 10), (27, 11), (28, 11)];
/// The legion's own reinforcements land at the beachhead.
const CAMP: [(u8, u8); 6] = [(2, 19), (3, 19), (4, 19), (2, 20), (3, 20), (2, 21)];

fn es16() -> MissionDef {
    let mut m = MissionDef::new("es16", "Sol Invictus");
    m.objective = "Break Stormhold: take Eagle's and Hachi's HQs or rout their armies.";
    m.map = MapSrc::Built("es16");
    m.armies = vec![
        ArmyDef::new(colour::BLUE_MOON, CoSpec::PickPartner(KLAUS)).funds(15000),
        // The Allied last stand: Eagle's air wing and Hachi's deep stores, allies with real production.
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::EAGLE))
            .team(2)
            .funds(13000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::HACHI))
            .team(2)
            .funds(13000),
    ];
    m.pool = vec![AURELIA, CASSIUS, LIVIA, co::KANBEI, co::COLIN];
    m.units = crate::es_campaign::deployment("es16");
    m.rank_days = 20;
    m.intro = scene("m16_pre");
    m.victory = chain(&["m16_post", "m16_post2"]);
    m.after = chain(&["m16_map", "m16_epilogue", "m16_epilogue2"]);
    let units_in = |x0, y0, x1, y1| Cond::UnitsIn {
        army: 1,
        area: Rect::new(x0, y0, x1, y1),
        at_least: 1,
    };
    m.triggers = vec![
        // The approaches: a unit at the walls of the plateau; inside the city.
        Trigger::new(
            When::AfterAction,
            units_in(22, 5, 33, 17),
            vec![Action::Scene(scene("m16_phase2"))],
        ),
        Trigger::new(
            When::AfterAction,
            units_in(30, 6, 39, 14),
            vec![Action::Scene(scene("m16_phase3"))],
        ),
        // Day 6: the defenders' meters are full and Eagle's air wing comes in from the north.
        on_day(
            6,
            None,
            vec![
                Action::Scene(scene("m16_reserves")),
                Action::Custom(charge_defenders),
                Action::Spawn(
                    [
                        wave(2, unit::FIGHTER, &AIRFIELD[0..3]),
                        wave(2, unit::BOMBER, &AIRFIELD[3..5]),
                        wave(2, unit::B_COPTER, &AIRFIELD[5..6]),
                    ]
                    .concat(),
                ),
            ],
        ),
        // Hachi's reserves: armour out of the south gate and the west gate, foot behind it.
        on_day(
            3,
            None,
            vec![Action::Spawn(
                [
                    wave(3, unit::MD_TANK, &SOUTH_GATE[0..1]),
                    wave(3, unit::TANK, &SOUTH_GATE[1..2]),
                ]
                .concat(),
            )],
        ),
        on_day(
            5,
            None,
            vec![Action::Spawn(
                [
                    wave(3, unit::NEOTANK, &WEST_GATE[0..1]),
                    wave(3, unit::MD_TANK, &WEST_GATE[1..2]),
                ]
                .concat(),
            )],
        ),
        on_day(
            7,
            None,
            vec![Action::Spawn(
                [
                    wave(3, unit::MD_TANK, &SOUTH_GATE[2..3]),
                    wave(3, unit::NEOTANK, &SOUTH_GATE[3..4]),
                ]
                .concat(),
            )],
        ),
        on_day(
            9,
            None,
            vec![
                Action::Spawn(wave(2, unit::FIGHTER, &AIRFIELD[6..7])),
                Action::Spawn(wave(3, unit::INFANTRY, &WEST_GATE[2..5])),
            ],
        ),
        // The last stand's second wave (the ramp ends here): Hachi's Neotanks on day 6, Eagle's Fighters on day 8, Md Tanks again out of the south gate on day 10.
        on_day(
            6,
            None,
            vec![Action::Spawn(
                [
                    wave(3, unit::NEOTANK, &SOUTH_GATE[4..5]),
                    wave(3, unit::NEOTANK, &WEST_GATE[5..6]),
                ]
                .concat(),
            )],
        ),
        on_day(8, None, vec![Action::Spawn(wave(2, unit::FIGHTER, &AIRFIELD[7..9]))]),
        on_day(10, None, vec![Action::Spawn(wave(3, unit::MD_TANK, &SOUTH_GATE[0..2]))]),
        // The legion's own reinforcements: the Quaestor's second convoy, on days 4 and 8.
        on_day(
            4,
            None,
            vec![Action::Spawn(
                [
                    wave(1, unit::ANTI_AIR, &CAMP[0..1]),
                    wave(1, unit::MD_TANK, &CAMP[1..2]),
                    wave(1, unit::ARTILLERY, &CAMP[2..3]),
                ]
                .concat(),
            )],
        ),
        on_day(
            8,
            None,
            vec![Action::Spawn(
                [
                    wave(1, unit::NEOTANK, &CAMP[3..4]),
                    wave(1, unit::MISSILES, &CAMP[4..5]),
                    wave(1, unit::MD_TANK, &CAMP[5..6]),
                ]
                .concat(),
            )],
        ),
    ];
    // Mount Sol below the west gate (`five/es/spec/es16.py`): from day 3 it erupts every day on 3 cells of the ring round its rock, 4 HP to any army's
    // units there (Dual Strike's volcano, as the BH Campaign's M11 has it): a hazard for the legion's column and the city's sallies alike.
    m.volcano = Some(VolcanoDef::new(3, 1, 4, &crate::campaign_model::ring(19, 10, 26, 17)).per_eruption(3));
    m.flag = region::ACT4[3];
    m.style = 8; // the last mission's marker
    m.stars = 5;
    m.needs = Needs::All(vec!["es15"]);
    m
}

/// Act IV's missions.
pub fn missions() -> Vec<MissionDef> {
    vec![es13(), es14(), es15(), es16()]
}
