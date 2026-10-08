//! Act 1. Its missions are `MissionDef`s (docs/AW2.md "BH Campaign": adding
//! a mission); this file is the act's alone, so builders can work on acts
//! in parallel. A mission names what it needs by key (`Needs::All(vec!["bh01"])`),
//! not by index.

// (the builders' imports: each act uses what it needs)
#![allow(unused_imports)]

use crate::bh_campaign::{region, roster};
use crate::custom_campaign::{co, colour, unit, *};

fn placeholder_one() -> MissionDef {
    let mut m = MissionDef::new("bh01", "Placeholder One");
    m.objective = "Rout the Green Earth force.";
    m.map = MapSrc::Ascii(&[
        "1...........",
        ".....ff.....",
        "..c.....c...",
        "....mm......",
        "......mm....",
        "...c.....c..",
        ".....ff.....",
        "...........2",
    ]);
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
        // Von Bolt in Green Earth's colours: colour and CO are independent.
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::VON_BOLT)),
    ];
    m.units = vec![
        UnitDef::new(1, unit::INFANTRY, 1, 1),
        UnitDef::new(1, unit::TANK, 2, 0),
        UnitDef::new(2, unit::INFANTRY, 10, 6),
        UnitDef::new(2, unit::INFANTRY, 9, 7),
    ];
    m.intro = Scene::new(vec![
        Line::say(co::STURM, "Placeholder scene. Von Bolt's men are ahead."),
        Line::say(co::VON_BOLT, "Placeholder reply. Come and get us."),
    ]);
    m.victory = Scene::new(vec![Line::feel(co::VON_BOLT, Mood::Sad, "Placeholder defeat.")]);
    m.after = Scene::new(vec![Line::say(co::STURM, "Placeholder: Von Bolt joins us.")]);
    m.recruits = vec![roster::VON_BOLT];
    m.flag = region::BLACK_HOLE[0];
    m.stars = 1;
    m
}

fn placeholder_two() -> MissionDef {
    let mut m = MissionDef::new("bh02", "Placeholder Two");
    m.objective = "Rout the Yellow Comet force.";
    m.map = MapSrc::Ascii(&[
        "1.........",
        "..ff..c...",
        "....mm....",
        "...c..c...",
        "....mm....",
        "...ff..c..",
        ".........2",
    ]);
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick),
        // Kindle in Yellow Comet's colours.
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KINDLE)),
    ];
    m.units = vec![
        UnitDef::new(1, unit::INFANTRY, 1, 1),
        UnitDef::new(1, unit::TANK, 2, 0),
        UnitDef::new(2, unit::INFANTRY, 8, 5),
    ];
    m.pool = vec![co::STURM, co::VON_BOLT];
    m.intro = Scene::new(vec![Line::say(co::KINDLE, "Placeholder: Kindle holds this ground.")]);
    m.victory = Scene::new(vec![Line::feel(co::KINDLE, Mood::Sad, "Placeholder defeat.")]);
    m.after = Scene::new(vec![Line::say(co::STURM, "Placeholder: the road ahead.")]);
    m.needs = Needs::All(vec!["bh01"]);
    m.flag = region::BLACK_HOLE[1];
    m.stars = 1;
    m
}


/// Act 1's missions, in world-map order.
pub fn missions() -> Vec<MissionDef> {
    vec![placeholder_one(), placeholder_two()]
}
