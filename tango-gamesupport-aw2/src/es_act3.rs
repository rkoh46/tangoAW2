//! Act III, The Trail: M9 Grain Ships (against Black Hole), M10 The Quiet Pass, M11 The Treasure Train, M12 Siege of Iron. Maps `five/es/spec/es09.py` ..
//! `es12.py`, dialogue `es_text/act3.txt`.

#![allow(unused_imports)]

use crate::custom_campaign::{co, colour, unit, *};
use crate::es_campaign::{after, deployment, leads, on_day, region, roster, wave};
use crate::es_co::{AURELIA, CASSIUS, KLAUS, LIVIA};
use crate::es_text::{chain, scene};

fn owns(x: u8, y: u8) -> Cond {
    Cond::OwnerAt { x, y, army: 1 }
}

// --- M9 Grain Ships (Black Hole's freight yards: inventions allowed) ----------------------------

/// Kite Hill's air depot (the airport on the plateau).
const DEPOT: (u8, u8) = (8, 4);

fn barges_gone() -> Cond {
    Cond::All(vec![Cond::UnitGone("barge1"), Cond::UnitGone("barge2"), Cond::UnitGone("barge3")])
}

fn depot_and_barges() -> Cond {
    Cond::All(vec![owns(DEPOT.0, DEPOT.1), barges_gone()])
}

fn es09() -> MissionDef {
    let mut m = MissionDef::new("es09", "Grain Ships");
    m.objective = "Take the Kite Hill depot and sink the three grain barges before day 11.";
    m.map = MapSrc::Built("es09");
    m.armies = vec![
        // (Orange Star's colour: Black Hole's is the enemy's in this mission)
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pick).funds(5000),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::ADDER, co::FLAK)).funds(10000),
    ];
    m.pool = leads();
    m.units = deployment("es09");
    m.rank_days = 9;
    m.intro = chain(&["m09_pre", "m09_pre2"]);
    m.victory = scene("m09_post");
    m.after = chain(&["m09_map"]);
    m.triggers = vec![
        on_day(4, None, vec![Action::Scene(scene("m09_day4"))]),
        after(depot_and_barges(), vec![Action::Win]),
        // Day 11: the barges sail.
        on_day(11, Some(Cond::Not(Box::new(depot_and_barges()))), vec![Action::Lose]),
    ];
    m.flag = region::ACT3[0];
    m.stars = 3;
    m.needs = Needs::All(vec!["es08"]);
    m
}

// --- M10 The Quiet Pass ----------------------------------------------------------------------

fn es10() -> MissionDef {
    let mut m = MissionDef::new("es10", "The Quiet Pass");
    m.objective = "Climb the pass and take the summit HQ.";
    m.map = MapSrc::Built("es10");
    m.fog = true;
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(4000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KANBEI)).team(2).funds(6000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::SONJA)).team(2).funds(3000),
    ];
    m.pool = leads();
    m.units = deployment("es10");
    m.rank_days = 14;
    m.intro = scene("m10_pre");
    m.victory = scene("m10_post");
    m.after = chain(&["m10_map"]);
    m.recruits = vec![roster::KANBEI];
    m.triggers = vec![
        on_day(4, None, vec![Action::Scene(scene("m10_day4"))]),
        // Kanbei's summit taken: his army falls, Sonja's ridge is left to its watching.
        after(Cond::ArmyDefeated(2), vec![Action::Win]),
    ];
    m.flag = region::ACT3[1];
    m.stars = 3;
    m.needs = Needs::All(vec!["es09"]);
    m
}

// --- M11 The Treasure Train ---------------------------------------------------------------

const CAMP: Rect = Rect::new(22, 5, 25, 7);
const APCS: [&str; 4] = ["apc1", "apc2", "apc3", "apc4"];

fn es11() -> MissionDef {
    let mut m = MissionDef::new("es11", "The Treasure Train");
    m.objective = "Bring all four APCs to the relay camp. Lose none; the day limit is 14.";
    m.map = MapSrc::Built("es11");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(3000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::LASH)).team(2).funds(5000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::FLAK)).team(2).funds(5000),
    ];
    m.pool = leads();
    m.units = deployment("es11");
    // The relay camp's city is the Senate's: the player's from the start.
    m.props = vec![Prop { kind: PropKind::City, owner: 1, x: 24, y: 6 }];
    m.day_limit = 14;
    m.rank_days = 10;
    m.intro = scene("m11_pre");
    m.victory = scene("m11_post");
    m.after = chain(&["m11_map"]);
    m.triggers = vec![
        on_day(5, None, vec![Action::Scene(scene("m11_day5"))]),
        after(Cond::All(APCS.iter().map(|&n| Cond::NamedIn { name: n, area: CAMP }).collect()), vec![Action::Win]),
        after(Cond::Any(APCS.iter().map(|&n| Cond::UnitGone(n)).collect()), vec![Action::Lose]),
    ];
    m.flag = region::ACT3[2];
    m.stars = 3;
    m.needs = Needs::All(vec!["es10"]);
    m
}

// --- M12 Siege of Iron -----------------------------------------------------------------------

fn es12() -> MissionDef {
    let mut m = MissionDef::new("es12", "Siege of Iron");
    m.objective = "Take the Iron Bastion's HQ. Klaus and Aurelia fight as a pair.";
    m.map = MapSrc::Built("es12");
    m.look = 1; // snow
    m.weather = Weather::Snow;
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(KLAUS, AURELIA)).funds(5000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF)).team(2).funds(7000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::GRIT)).team(2).funds(4000),
    ];
    m.units = deployment("es12");
    m.rank_days = 16;
    m.intro = scene("m12_pre");
    m.victory = scene("m12_post");
    m.after = chain(&["m12_map"]);
    m.triggers = vec![
        on_day(5, None, vec![Action::Scene(scene("m12_day5"))]),
        // The bastion's HQ (Olaf's) taken: the siege is won, Grit's spur is left.
        after(Cond::ArmyDefeated(2), vec![Action::Win]),
    ];
    m.flag = region::ACT3[3];
    m.stars = 4;
    m.needs = Needs::All(vec!["es11"]);
    m
}

/// Act III's missions.
pub fn missions() -> Vec<MissionDef> {
    vec![es09(), es10(), es11(), es12()]
}
