//! Act 5: Orange Star (the finale's two missions so far: M29 The Orange Gate and
//! M30 Nell's Stand). Its missions are `MissionDef`s (docs/AW2.md "BH Campaign":
//! adding a mission); this file is the act's alone, so builders can work on acts
//! in parallel. A mission names what it needs by key (`Needs::All(vec!["bh28"])`),
//! not by index.
//!
//! The maps are `five/bh/bh29.txt` and `bh30.txt` (built by `five/bhmap.py` into
//! `bh_map_data.rs`: walls of mountains, the moat's shoals and bridge, roads
//! joined as AW2 draws them, reachability checked). The design is the bible's
//! (docs/BH_CAMPAIGN.md, branch bh-design: 3.2b the inventions, 4.6 and 4.7 the
//! scenes, the mission sheets).

// (the builders' imports: each act uses what it needs)
#![allow(unused_imports)]

use crate::bh_campaign::{region, roster};
use crate::custom_campaign::{co, colour, unit, *};

fn say(c: u8, text: &'static str) -> Line {
    Line::say(c, text)
}

fn troop(text: &'static str) -> Line {
    Line::soldier(colour::BLACK_HOLE, text)
}

// --- M29 The Orange Gate -----------------------------------------------------------

fn bh29() -> MissionDef {
    let mut m = MissionDef::new("bh29", "The Orange Gate");
    m.objective = "Take the Orange Gate and capture Orange Star's HQ.";
    m.map = MapSrc::Built("bh29");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(14000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::NELL, co::MAX)).funds(60000),
    ];
    m.day_limit = 32;
    m.rank_days = 20;
    m.intro = Scene::new(vec![
        troop("The Orange Gate. Walls, a canal, a woman on the wall."),
        say(co::NELL, "This is the Orange Gate. I would rather you turned back."),
        say(co::NELL, "You will not. I know. So I will ask you to be careful."),
        say(co::MAX, "Nell! I'm right here! Nobody touches you!"),
    ]);
    m.victory = Scene::new(vec![say(co::NELL, "The Gate holds no longer. Max, Sami: fall back. Now.")]);
    m.after = Scene::new(vec![say(co::NELL, "Then come to it, and meet what I have kept for you.")]);
    m.triggers = vec![Trigger::new(When::AfterAction, Cond::OwnerAt { x: 31, y: 13, army: 1 }, vec![Action::Win]).repeating()];
    m.needs = Needs::All(vec!["bh28"]);
    m.flag = region::ORANGE_STAR[4];
    m.stars = 3;
    m
}

// --- M30 Nell's Stand --------------------------------------------------------------

fn bh30() -> MissionDef {
    let mut m = MissionDef::new("bh30", "Nell's Stand");
    m.objective = "Take the Great Hall, then the Rail Yard.";
    m.map = MapSrc::Built("bh30");
    // Army 3 is Andy's stage-two army: on Nell's team, an HQ of its own (the Rail Yard) and one token unit.
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(20000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::NELL, co::ANDY)).team(2).funds(90000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::ANDY)).team(2),
    ];
    m.day_limit = 34;
    m.rank_days = 24;
    m.intro = Scene::new(vec![
        troop("The Orange Castle. The last gate. The last light."),
        say(co::NELL, "Black Hole. You took the Gate. I did not stop you."),
        say(co::NELL, "Behind me are ten thousand people. I will hold."),
        say(co::ANDY, "Nell! I'm with you! Always!"),
    ]);
    m.victory = Scene::new(vec![say(co::NELL, "Andy. Come here. It is all right. It is done.")]);
    m.after = Scene::new(vec![say(co::NELL, "The flag is yours. Take it gently.")]);
    m.needs = Needs::All(vec!["bh29"]);
    m.flag = region::ORANGE_STAR[5];
    m.stars = 3;
    m
}

/// Act 5's missions, in world-map order (so far the finale's two).
pub fn missions() -> Vec<MissionDef> {
    let mut v = Vec::new();
    // (until M28 is in the tree, a locked placeholder keeps the finale's `needs` valid)
    v.push(dev_stub_bh28());
    v.push(bh29());
    v.push(bh30());
    v
}

/// Development fallback: a stand-in for M28 while it is not in the tree yet.
fn dev_stub_bh28() -> MissionDef {
    let mut m = MissionDef::new("bh28", "Placeholder 28");
    m.objective = "Rout the Orange Star force.";
    m.map = MapSrc::Ascii(&["1.........", "..ff..c...", "....mm....", "...c..c...", ".........2"]);
    m.armies = vec![ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)), ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::NELL))];
    m.units = vec![UnitDef::new(1, unit::INFANTRY, 1, 1), UnitDef::new(2, unit::INFANTRY, 8, 3)];
    m.needs = Needs::Bonds(vec!["bh02"]);
    m.flag = region::ORANGE_STAR[3];
    m
}
