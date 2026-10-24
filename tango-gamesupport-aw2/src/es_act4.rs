//! Act IV, Pax: M13 The Free Port (against Black Hole among others), M14 Varro's Gambit, M15 Pax Romana, M16 Sol Invictus. Maps `five/es/spec/es13.py` ..
//! `es16.py`, dialogue `es_text/act4.txt`.

#![allow(unused_imports)]

use mgba::core::Core;

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
const OFFICE: (u8, u8) = (12, 10);

fn reset_hold(core: &mut Core) {
    core.raw_write_8(STATE, -1, 0);
}

/// At each of the player's turn starts: one more turn if the player holds the Office, else none.
fn count_hold(core: &mut Core) {
    let army = crate::ds_campaign::player_army(core);
    let n = if owner_at(core, OFFICE.0, OFFICE.1) == army { core.raw_read_8(STATE, -1).saturating_add(1) } else { 0 };
    core.raw_write_8(STATE, -1, n);
}

fn held_three(core: &mut Core) -> bool {
    core.raw_read_8(STATE, -1) >= 3
}

fn es13() -> MissionDef {
    let mut m = MissionDef::new("es13", "The Free Port");
    m.objective = "Take the Harbour Office and hold it for 3 days. Four flags, no friends.";
    m.map = MapSrc::Built("es13");
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

const DOCK1: (u8, u8) = (27, 5);
const DOCK2: (u8, u8) = (27, 12);

/// Day 4: Cassius's army (army 3) goes over to the player's side (AW2's team byte of its player block).
fn cassius_changes_sides(core: &mut Core) {
    let players = crate::five::players(core);
    let team = core.raw_read_8(players + 0x3C + 0x2A, -1);
    core.raw_write_8(players + 0x3C * 3 + 0x2A, -1, team);
}

fn es14() -> MissionDef {
    let mut m = MissionDef::new("es14", "Varro's Gambit");
    m.objective = "Hold the quay's HQ, then break out and take both docks by day 12.";
    m.map = MapSrc::Built("es14");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPartner(KLAUS)).funds(4000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(VARRO)).funds(12000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(CASSIUS)).funds(5000),
    ];
    m.pool = vec![AURELIA, CASSIUS, LIVIA, co::KANBEI, co::COLIN];
    m.units = deployment("es14");
    m.day_limit = 12;
    m.rank_days = 11;
    m.intro = scene("m14_pre");
    m.victory = scene("m14_post");
    m.after = chain(&["m14_map"]);
    m.triggers = vec![
        on_day(4, None, vec![Action::Scene(scene("m14_day4")), Action::Custom(cassius_changes_sides)]),
        after(Cond::All(vec![owns(DOCK1.0, DOCK1.1), owns(DOCK2.0, DOCK2.1)]), vec![Action::Win]),
    ];
    m.flag = region::ACT4[1];
    m.stars = 4;
    m.needs = Needs::All(vec!["es13"]);
    m
}

// --- M15 Pax Romana ----------------------------------------------------------------------------

/// Varro's flagship harbour, on the east island.
const FLAGSHIP_PORT: (u8, u8) = (23, 10);

fn es15() -> MissionDef {
    let mut m = MissionDef::new("es15", "Pax Romana");
    m.objective = "Rout Varro's fleet and take his flagship harbour. The Accord's ships join on day 6.";
    m.map = MapSrc::Built("es15");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(8000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(VARRO)).funds(14000),
        // The relief fleet: Nell's, with nothing until day 6.
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::NELL)).team(1).funds(0),
    ];
    m.pool = everyone();
    m.units = deployment("es15");
    m.rank_days = 14;
    m.intro = scene("m15_pre");
    m.victory = scene("m15_post");
    m.after = chain(&["m15_map"]);
    m.triggers = vec![
        on_day(
            6,
            None,
            vec![
                Action::Scene(scene("m15_day6")),
                Action::Spawn(
                    [
                        wave(3, unit::CRUISER, &[(8, 17), (8, 18)]),
                        wave(3, unit::BATTLESHIP, &[(8, 19)]),
                        wave(3, unit::SUB, &[(9, 18)]),
                        wave(3, unit::FIGHTER, &[(2, 17), (4, 17), (1, 18)]),
                        wave(3, unit::B_COPTER, &[(5, 18), (2, 19), (4, 19)]),
                    ]
                    .concat(),
                ),
            ],
        ),
        after(Cond::All(vec![owns(FLAGSHIP_PORT.0, FLAGSHIP_PORT.1), Cond::ArmyUnitsAtMost { army: 2, n: 6 }]), vec![Action::Win]),
    ];
    m.flag = region::ACT4[2];
    m.stars = 4;
    m.needs = Needs::All(vec!["es14"]);
    m
}

/// Act IV's missions (M16 follows when its map is done).
pub fn missions() -> Vec<MissionDef> {
    vec![es13(), es14(), es15()]
}
