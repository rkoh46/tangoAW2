//! Act I, The Landing: M1 Landfall, M2 Testudo, M3 The Wall, M4 The Second Legion. Maps `five/es/spec/es01.py` .. `es04.py`, dialogue `es_text/act1.txt`.
//! A mission names what it needs by key (`Needs::All(vec!["es01"])`).

// (the acts' imports: each uses what it needs)
#![allow(unused_imports)]

use crate::custom_campaign::{co, colour, unit, *};
use crate::es_campaign::{after, deployment, leads, on_day, region, roster, wave};
use crate::es_co::{AURELIA, CASSIUS, KLAUS};
use crate::es_text::{chain, scene};

// --- M1 Landfall --------------------------------------------------------------------------

fn es01() -> MissionDef {
    let mut m = MissionDef::new("es01", "Landfall");
    m.objective = "Land from the sandbar and take the fort's HQ.";
    m.map = MapSrc::Built("es01");
    m.armies = vec![
        // Klaus's legion is pre-deployed on the fleet's sandbar: no production, no funds.
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(KLAUS)).funds(0),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JESS)).funds(8000),
    ];
    m.units = deployment("es01");
    m.rank_days = 10;
    m.intro = scene("m01_pre");
    m.victory = scene("m01_post");
    m.after = chain(&["m01_map"]);
    m.triggers = vec![
        on_day(2, None, vec![Action::Scene(scene("m01_day2"))]),
        // The second wave: an Anti-Air tank and two Tanks reach the sandbar on day 3.
        on_day(
            3,
            None,
            vec![Action::Spawn(vec![
                UnitDef::new(1, unit::ANTI_AIR, 12, 26),
                UnitDef::new(1, unit::TANK, 15, 26),
                UnitDef::new(1, unit::TANK, 18, 26),
            ])],
        ),
    ];
    m.flag = region::ACT1[0];
    m.stars = 1;
    m.needs = Needs::Start;
    m
}

// --- M2 Testudo ------------------------------------------------------------------------------

fn es02() -> MissionDef {
    let mut m = MissionDef::new("es02", "Testudo");
    m.objective = "Hold the ridge until day 9. Do not lose the HQ.";
    m.map = MapSrc::Built("es02");
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(KLAUS)).funds(3000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Pair(co::JESS, co::EAGLE)).funds(14000),
    ];
    m.units = deployment("es02");
    m.rank_days = 9;
    m.intro = scene("m02_pre");
    m.victory = scene("m02_post");
    m.after = chain(&["m02_map"]);
    m.triggers = vec![
        // Day 3: the engineers send Anti-Air and Missiles up behind the HQ; the first wave comes down the roads.
        on_day(
            3,
            None,
            vec![
                Action::Spawn(
                    [wave(1, unit::ANTI_AIR, &[(3, 13), (5, 13)]), wave(1, unit::MISSILES, &[(2, 12)])].concat(),
                ),
                Action::Spawn([wave(2, unit::TANK, &[(4, 0), (6, 0)]), wave(2, unit::MD_TANK, &[(8, 0)])].concat()),
            ],
        ),
        // Day 4: Eagle's wing.
        on_day(4, None, vec![Action::Scene(scene("m02_day4")), Action::Spawn(wave(2, unit::FIGHTER, &[(19, 8)]))]),
        on_day(5, None, vec![Action::Spawn([wave(2, unit::TANK, &[(4, 0), (6, 0)]), wave(2, unit::INFANTRY, &[(19, 5)])].concat())]),
        on_day(7, None, vec![Action::Spawn([wave(2, unit::MD_TANK, &[(4, 0)]), wave(2, unit::TANK, &[(6, 0)])].concat())]),
        // Day 9: the causeway is open. (The HQ falling is the match's own defeat.)
        on_day(9, None, vec![Action::Win]),
    ];
    m.flag = region::ACT1[1];
    m.stars = 1;
    m.needs = Needs::All(vec!["es01"]);
    m
}

// --- M3 The Wall -------------------------------------------------------------------------------

fn es03() -> MissionDef {
    let mut m = MissionDef::new("es03", "The Wall");
    m.objective = "Breach the wall and take the keep's HQ.";
    m.map = MapSrc::Built("es03");
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(AURELIA)).funds(2000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JAVIER)).funds(6000),
    ];
    m.units = deployment("es03");
    m.rank_days = 14;
    m.intro = scene("m03_pre");
    m.victory = scene("m03_post");
    m.after = chain(&["m03_map"]);
    m.recruits = vec![roster::AURELIA];
    m.triggers = vec![
        // Day 2: the engineers' Bomber.
        on_day(2, None, vec![Action::Spawn(wave(1, unit::BOMBER, &[(9, 15)]))]),
        on_day(3, None, vec![Action::Scene(scene("m03_day3"))]),
    ];
    m.flag = region::ACT1[2];
    m.stars = 2;
    m.needs = Needs::All(vec!["es02"]);
    m
}

// --- M4 The Second Legion ----------------------------------------------------------------------

fn es04() -> MissionDef {
    let mut m = MissionDef::new("es04", "The Second Legion");
    m.objective = "Rout Cassius's legion or take its camp HQ.";
    m.map = MapSrc::Built("es04");
    m.fog = true;
    m.armies = vec![
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Pick).funds(4000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(CASSIUS)).funds(4000),
    ];
    m.pool = vec![KLAUS, AURELIA];
    m.units = deployment("es04");
    m.rank_days = 12;
    m.intro = scene("m04_pre");
    m.victory = scene("m04_post");
    m.after = chain(&["m04_map"]);
    m.recruits = vec![roster::CASSIUS];
    m.triggers = vec![on_day(5, None, vec![Action::Scene(scene("m04_day5"))])];
    m.flag = region::ACT1[3];
    m.stars = 2;
    m.needs = Needs::All(vec!["es03"]);
    m
}

/// Act I's missions.
pub fn missions() -> Vec<MissionDef> {
    vec![es01(), es02(), es03(), es04()]
}
