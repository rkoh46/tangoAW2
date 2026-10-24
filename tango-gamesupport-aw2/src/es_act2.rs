//! Act II, The Road North: M5 Dust and Wheels, M6 Tribute, M7 Mare Nostrum, M8 Hammer and Anvil. Maps `five/es/spec/es05.py` .. `es08.py`, dialogue `es_text/act2.txt`.

#![allow(unused_imports)]

use crate::custom_campaign::{co, colour, unit, *};
use crate::es_campaign::{after, deployment, leads, on_day, region, roster, wave};
use crate::es_co::{AURELIA, CASSIUS, KLAUS, LIVIA};
use crate::es_text::{chain, scene};

/// The player's army (army 1) owns the cell.
fn owns(x: u8, y: u8) -> Cond {
    Cond::OwnerAt { x, y, army: 1 }
}

// --- M5 Dust and Wheels ----------------------------------------------------------------------

/// The three signal-posts (the cities beyond the bridges).
const POSTS: [(u8, u8); 3] = [(27, 5), (27, 12), (27, 21)];

fn all_posts() -> Cond {
    Cond::All(POSTS.iter().map(|&(x, y)| owns(x, y)).collect())
}

fn es05() -> MissionDef {
    let mut m = MissionDef::new("es05", "Dust and Wheels");
    m.objective = "Take the three signal-posts by day 9, before the bridges are blown.";
    m.map = MapSrc::Built("es05");
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(CASSIUS)).funds(3000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Pair(co::GRIMM, co::SENSEI)).funds(9000),
    ];
    m.units = deployment("es05");
    m.rank_days = 8;
    m.intro = scene("m05_pre");
    m.victory = scene("m05_post");
    m.after = chain(&["m05_map"]);
    m.triggers = vec![
        on_day(4, None, vec![Action::Scene(scene("m05_day4"))]),
        // All three posts held: the road is saved.
        after(all_posts(), vec![Action::Win]),
        // Day 10: the bridges blow and the road is lost.
        on_day(10, Some(Cond::Not(Box::new(all_posts()))), vec![Action::Lose]),
    ];
    m.flag = region::ACT2[0];
    m.stars = 2;
    m.needs = Needs::All(vec!["es04"]);
    m
}

// --- M6 Tribute ----------------------------------------------------------------------------

fn es06() -> MissionDef {
    let mut m = MissionDef::new("es06", "Tribute");
    m.objective = "Own 14 properties at once by day 16.";
    m.map = MapSrc::Built("es06");
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(LIVIA)).funds(3000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::COLIN)).team(2).funds(5000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::SASHA)).team(2).funds(5000),
    ];
    m.units = deployment("es06");
    m.rank_days = 14;
    m.intro = scene("m06_pre");
    m.victory = scene("m06_post");
    m.after = chain(&["m06_map"]);
    m.recruits = vec![roster::LIVIA, roster::COLIN];
    m.triggers = vec![
        on_day(6, None, vec![Action::Scene(scene("m06_day6"))]),
        after(Cond::PropertiesAtLeast { army: 1, n: 14 }, vec![Action::Win]),
        // The audit: day 17 begins and the tribute is not in hand (losing the square is the match's own defeat).
        on_day(17, Some(Cond::Not(Box::new(Cond::PropertiesAtLeast { army: 1, n: 14 }))), vec![Action::Lose]),
    ];
    m.flag = region::ACT2[1];
    m.stars = 2;
    m.needs = Needs::All(vec!["es05"]);
    m
}

// --- M7 Mare Nostrum -----------------------------------------------------------------------

/// Isle Verdant's harbour (the port to take).
const HARBOUR: (u8, u8) = (15, 8);

fn es07() -> MissionDef {
    let mut m = MissionDef::new("es07", "Mare Nostrum");
    m.objective = "Sink the Warden flagship and take Isle Verdant's harbour.";
    m.map = MapSrc::Built("es07");
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pick).funds(8000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::DRAKE)).team(2).funds(10000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::EAGLE)).team(2).funds(8000),
    ];
    m.pool = leads();
    m.units = deployment("es07");
    m.rank_days = 14;
    m.intro = scene("m07_pre");
    m.victory = scene("m07_post");
    m.after = chain(&["m07_map"]);
    m.triggers = vec![
        on_day(5, None, vec![Action::Scene(scene("m07_day5"))]),
        after(Cond::All(vec![Cond::UnitGone("flagship"), owns(HARBOUR.0, HARBOUR.1)]), vec![Action::Win]),
    ];
    m.flag = region::ACT2[2];
    m.stars = 3;
    m.needs = Needs::All(vec!["es06"]);
    m
}

// --- M8 Hammer and Anvil -------------------------------------------------------------------

fn es08() -> MissionDef {
    let mut m = MissionDef::new("es08", "Hammer and Anvil");
    m.objective = "Defeat the Orange Star border force at Ironhold. Klaus and Cassius fight as a pair.";
    m.map = MapSrc::Built("es08");
    m.armies = vec![
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Pair(KLAUS, CASSIUS)).funds(4000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::MAX)).team(2).funds(9000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::JAKE)).team(2).funds(7000),
    ];
    m.units = deployment("es08");
    m.rank_days = 12;
    m.intro = scene("m08_pre");
    m.victory = scene("m08_post");
    m.after = chain(&["m08_map"]);
    m.triggers = vec![on_day(3, None, vec![Action::Scene(scene("m08_day3"))])];
    m.flag = region::ACT2[3];
    m.stars = 3;
    m.needs = Needs::All(vec!["es07"]);
    m
}

/// Act II's missions.
pub fn missions() -> Vec<MissionDef> {
    vec![es05(), es06(), es07(), es08()]
}
