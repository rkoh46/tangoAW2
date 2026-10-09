//! Act 3: Yellow Comet (M12 to M16). Its missions are `MissionDef`s
//! (docs/AW2.md "BH Campaign": adding a mission); this file is the act's
//! alone, so builders can work on acts in parallel. A mission names what it
//! needs by key (`Needs::All(vec!["bh11"])`), not by index.
//!
//! The maps are `five/bh/bh12.txt` .. `bh16.txt` (+ `bh15b.txt`, M15's sky
//! front), built by `five/bhmap.py` into `bh_map_data.rs`: roads, rivers,
//! coasts and shoals joined as AW2 draws them, reachability checked. The
//! dialogue is the design bible's (docs/BH_CAMPAIGN.md section 4.4, branch
//! bh-design).
//!
//! First pass: maps, armies, rules and the openings; the scenes' conditional
//! lines (`@IF CO`), the recruit pitches, triggers and balance follow.

// (the builders' imports: each act uses what it needs)
#![allow(unused_imports)]

use mgba::core::Core;

use crate::bh_campaign::{region, roster};
use crate::campaign_model::SendRule;
use crate::custom_campaign::{co, colour, unit, *};

// --- Writing helpers ---------------------------------------------------------------

/// Narration and the soldiers (Crumb, Mortar, Wick, "Soldier"): the Black Hole trooper's face.
fn troop(text: &'static str) -> Line {
    Line::soldier(colour::BLACK_HOLE, text)
}

fn say(c: u8, text: &'static str) -> Line {
    Line::say(c, text)
}

fn happy(c: u8, text: &'static str) -> Line {
    Line::feel(c, Mood::Happy, text)
}

fn sad(c: u8, text: &'static str) -> Line {
    Line::feel(c, Mood::Sad, text)
}

/// The mission's rule "on day `d`, at the start of the player's turn, do these": fires once, on that
/// day (`EveryDays` with a period no mission reaches), without taking one of the campaign's 96
/// once-latch flags.
fn on_day(d: u16, cond: Option<Cond>, then: Vec<Action>) -> Trigger {
    let day = Cond::EveryDays { n: 1000, from: d };
    let cond = match cond {
        Some(c) => Cond::All(vec![day, c]),
        None => day,
    };
    Trigger::new(When::TurnStart, cond, then).repeating()
}

/// After each action, while the condition holds (a win or a loss: the match ends; or a one-way event).
fn after(cond: Cond, then: Vec<Action>) -> Trigger {
    Trigger::new(When::AfterAction, cond, then).repeating()
}

/// The enemy army is as good as routed: at most one unit left, or its HQ is the player's.
fn beaten(enemy: u8, hq: (u8, u8)) -> Cond {
    Cond::Any(vec![Cond::ArmyUnitsAtMost { army: enemy, n: 1 }, Cond::OwnerAt { x: hq.0, y: hq.1, army: 1 }])
}

/// The units of a built map's text file, for a second front (whose deployment is the front's own).
fn built_units(name: &str) -> Vec<UnitDef> {
    let Some(m) = crate::bh_map_data::MAPS.iter().find(|m| m.name == name) else { return Vec::new() };
    m.units
        .iter()
        .map(|u| {
            let mut d = UnitDef::new(u.army, u.kind, u.x, u.y).hp(u.hp);
            if u.hold {
                d = d.hold();
            }
            if !u.name.is_empty() {
                d = d.named(u.name);
            }
            d
        })
        .collect()
}

// --- World map ---------------------------------------------------------------------

/// Act 3's flags on AW2's Yellow Comet (the centre land, x 225..300, y 50..180): M12 .. M16.
pub const FLAGS: [(i16, i16); 5] = [
    region::YELLOW_COMET[0], // M12 Highway to the Horizon
    region::YELLOW_COMET[1], // M13 Festival of Flame
    region::YELLOW_COMET[2], // M14 No Soldier Left Behind
    region::YELLOW_COMET[3], // M15 The Skybridge
    region::YELLOW_COMET[4], // M16 Comet Keep
];

// --- M12 Highway to the Horizon (recruit Koal) --------------------------------------

/// Factory table F12 (docs/BH_CAMPAIGN.md 3.5): per day the three doors' units (0 none).
#[allow(dead_code)]
const F12: [(u8, [u8; 3]); 9] = [
    (2, [unit::RECON, 0, unit::RECON]),
    (3, [0, unit::TANK, 0]),
    (5, [unit::MD_TANK, unit::MECH, 0]),
    (7, [0, unit::PIPERUNNER, 0]),
    (8, [unit::TANK, 0, unit::TANK]),
    (10, [unit::MD_TANK, 0, unit::MD_TANK]),
    (12, [0, unit::NEOTANK, 0]),
    (14, [unit::MECH, unit::MECH, unit::MECH]),
    (16, [0, unit::MD_TANK, 0]),
];

fn bh12() -> MissionDef {
    let mut m = MissionDef::new("bh12", "Highway to the Horizon");
    m.objective = "Wake the Black Factory, take Koal's HQ.";
    m.map = MapSrc::Built("bh12");
    m.look = 2; // desert
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(9000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KOAL)).funds(30000),
    ];
    m.pool = vec![co::STURM, co::VON_BOLT, co::HAWKE];
    m.day_limit = 28;
    m.rank_days = 17;
    // TODO(engine): `m.factory = F12.to_vec();` needs MissionDef::factory (bh-act2's engine commit 6c3ba0fb1, merged later).
    m.recruits = vec![roster::KOAL];
    m.intro = Scene::new(vec![
        say(co::KOAL, "Stop. Right there. You stand on my shoulder."),
        say(co::KOAL, "The hard shoulder. Three metres wide. Move."),
        say(co::KOAL, "Welcome to the Trans-Comet Highway. Two thousand miles."),
        say(co::KOAL, "Not one pothole. Not one border."),
        say(co::KOAL, "Except the ones at the end. I hate the ones at the end."),
        say(co::KOAL, "The Council pays me to build and then to stop."),
        say(co::KOAL, "I wish to build and not stop. Take it from me. Try."),
    ]);
    m.victory = Scene::new(vec![sad(co::KOAL, "My highway... broken at the junction. Unforgivable.")]);
    m.after = Scene::new(vec![say(co::KOAL, "Corporal. You. Come here."), troop("Sir? I'm a Private, sir.")]);
    m.triggers = vec![
        on_day(5, None, vec![Action::Scene(Scene::new(vec![say(co::KOAL, "A Black Factory in my median? Rude.")]))]),
        on_day(12, None, vec![Action::Scene(Scene::new(vec![say(co::KOAL, "The pipeline is mine. Do not smoke near it.")]))]),
        after(beaten(2, (34, 9)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh11"]);
    m.flag = FLAGS[0];
    m.stars = 3;
    m
}

// --- M13 Festival of Flame (recruit Kindle) ---------------------------------------------

fn bh13() -> MissionDef {
    let mut m = MissionDef::new("bh13", "Festival of Flame");
    m.objective = "Take the stage and hold the towers before the last firework.";
    m.map = MapSrc::Built("bh13");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(6000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KINDLE)).funds(12000),
    ];
    m.pool = vec![co::STURM, co::VON_BOLT, co::HAWKE, co::KOAL];
    m.day_limit = 14;
    m.rank_days = 10;
    m.recruits = vec![roster::KINDLE];
    m.intro = Scene::new(vec![
        say(co::KINDLE, "Darlings! You are late to my festival!"),
        say(co::KINDLE, "The Flame Festival! The greatest night in the east!"),
        say(co::KINDLE, "And I am its patron, its star, its everything."),
        say(co::KINDLE, "Impress me. Take my plaza before the last firework."),
        say(co::KINDLE, "Fourteen days. I get bored in thirteen."),
    ]);
    m.victory = Scene::new(vec![sad(co::KINDLE, "My plaza! My lovely plaza! You... brute.")]);
    m.after = Scene::new(vec![troop("Ma'am Kindle gave me a sash!")]);
    m.triggers = vec![
        on_day(4, None, vec![Action::Scene(Scene::new(vec![say(co::KINDLE, "Fireworks! Clap, peasants, clap!")]))]),
        on_day(10, None, vec![Action::Scene(Scene::new(vec![say(co::KINDLE, "Four days left, darling. Entertain me. Properly.")]))]),
        after(beaten(2, (10, 3)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh12"]);
    m.flag = FLAGS[1];
    m.stars = 3;
    m
}

// --- M14 No Soldier Left Behind -------------------------------------------------------

/// Pad Echo, the extraction airport: Crumb must stand on it (or be carried onto it).
const PAD_ECHO: (u8, u8) = (19, 18);

fn bh14() -> MissionDef {
    let mut m = MissionDef::new("bh14", "No Soldier Left Behind");
    m.objective = "Bring Crumb to Pad Echo within fifteen days.";
    m.map = MapSrc::Built("bh14");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(0),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::SONJA)).funds(0),
    ];
    m.fog = true;
    m.day_limit = 15;
    m.rank_days = 12;
    m.intro = Scene::new(vec![
        sad(co::STURM, "Crumb is slightly surrounded."),
        say(co::SONJA, "A lost sparrow. And a radio that sings."),
        say(co::SONJA, "I will keep him safe. For the price of a general."),
        say(co::STURM, "What is mine stays mine. Nobody takes from Black Hole."),
        say(co::STURM, "Fifteen days. Take him back."),
        say(co::SONJA, "Fifteen days. I shall count them for you."),
    ]);
    m.victory = Scene::new(vec![sad(co::SONJA, "He was bait, and you took him anyway. Surprising.")]);
    m.after = Scene::new(vec![troop("Medic says one HP is technically alive.")]);
    m.triggers = vec![
        after(Cond::UnitAt { name: "crumb", x: PAD_ECHO.0, y: PAD_ECHO.1 }, vec![Action::Win]),
        after(Cond::UnitGone("crumb"), vec![Action::Lose]),
    ];
    m.needs = Needs::All(vec!["bh13"]);
    m.flag = FLAGS[2];
    m.stars = 4;
    m
}

// --- M15 The Skybridge ----------------------------------------------------------------

fn bh15() -> MissionDef {
    let mut m = MissionDef::new("bh15", "The Skybridge");
    m.objective = "Take Kanbei's HQ and drive Grimm from the sky.";
    m.map = MapSrc::Built("bh15");
    // The player picks two COs: the main front's, then the sky front's.
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(10000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KANBEI)).funds(16000),
    ];
    m.pool = vec![co::STURM, co::VON_BOLT, co::HAWKE, co::KINDLE, co::KOAL];
    m.day_limit = 24;
    m.rank_days = 16;
    m.front2 = Some(FrontDef {
        map: MapSrc::Built("bh15b"),
        props: Vec::new(),
        structures: Vec::new(),
        units: built_units("bh15b"),
        cos: [CoSpec::Pick, CoSpec::Fixed(co::GRIMM), CoSpec::None, CoSpec::None],
        send: SendRule::Air,
        sky: true,
        weather: Weather::Clear,
        fog: false,
    });
    m.intro = Scene::new(vec![
        say(co::KANBEI, "Black Hole! You tread the Skybridge of Yellow Comet!"),
        say(co::KANBEI, "I, Kanbei, will not yield a step. Honour demands it!"),
        say(co::GRIMM, "Grimm here! Lemme at 'em! The sky's got no walls!"),
        say(co::GRIMM, "Don't wait, Boss! I'll punch a cloud!"),
        say(co::KANBEI, "Grimm. A cloud cannot be punched."),
        say(co::GRIMM, "Watch me."),
        say(co::HAWKE, "Two fronts. Mountain and sky. Divide as you see fit."),
    ]);
    m.victory = Scene::new(vec![sad(co::KANBEI, "The mountain falls. Honour... remains.")]);
    m.after = Scene::new(vec![troop("Sir, the sky bridge wobbles. Is that normal?")]);
    m.triggers = vec![after(beaten(2, (22, 10)), vec![Action::Win])];
    m.needs = Needs::All(vec!["bh14"]);
    m.flag = FLAGS[3];
    m.stars = 4;
    m
}

// --- M16 Comet Keep -------------------------------------------------------------------

fn bh16() -> MissionDef {
    let mut m = MissionDef::new("bh16", "Comet Keep");
    m.objective = "Storm the Keep and capture the courtyard HQ.";
    m.map = MapSrc::Built("bh16");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(6000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Pair(co::KANBEI, co::SENSEI)).funds(18000),
    ];
    m.pool = vec![co::STURM, co::VON_BOLT, co::HAWKE, co::KINDLE, co::KOAL];
    m.day_limit = 24;
    m.rank_days = 16;
    m.intro = Scene::new(vec![
        say(co::KANBEI, "This is Comet Keep. Born of honour and mountain."),
        say(co::KANBEI, "Come, black storm! Let honour judge us!"),
        say(co::SENSEI, "Kanbei, remember Hachi? Our old pupil. Sells maps now."),
        say(co::KANBEI, "Sonja guards the rear. No blade shall touch my daughter."),
    ]);
    m.victory = Scene::new(vec![sad(co::KANBEI, "Kanbei is beaten. The Keep is yours.")]);
    m.after = Scene::new(vec![say(co::SONJA, "Blue Moon is rich, and afraid. Dangerous together.")]);
    m.triggers = vec![
        on_day(6, None, vec![Action::Scene(Scene::new(vec![say(co::SENSEI, "Jump, my paratroopers!")]))]),
        on_day(12, None, vec![Action::Scene(Scene::new(vec![say(co::KANBEI, "Kanbei leads! For honour, for Yellow Comet! Charge!")]))]),
        after(beaten(2, (13, 2)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh15"]);
    m.flag = FLAGS[4];
    m.stars = 4;
    m
}

/// Development fallback: a stand-in for Act 2's M11 while it is not in the tree.
fn dev_stub_bh11() -> MissionDef {
    let mut m = MissionDef::new("bh11", "Placeholder Eleven");
    m.objective = "Rout the Green Earth force.";
    m.map = MapSrc::Ascii(&["1.........", "..ff..c...", "....mm....", "...c..c...", ".........2"]);
    m.armies = vec![ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)), ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::DRAKE))];
    m.units = vec![UnitDef::new(1, unit::INFANTRY, 1, 1), UnitDef::new(2, unit::INFANTRY, 8, 3)];
    m.needs = Needs::Start;
    m.flag = region::GREEN_EARTH[0];
    m
}

/// Act 3's missions, in world-map order.
pub fn missions() -> Vec<MissionDef> {
    let mut v = Vec::new();
    // (until Act 2's M11 is in the tree, a placeholder keeps Act 3's `needs` valid)
    if !crate::bh_act2::missions().iter().any(|m| m.key == "bh11") {
        v.push(dev_stub_bh11());
    }
    v.push(bh12());
    v.push(bh13());
    v.push(bh14());
    v.push(bh15());
    v.push(bh16());
    // The day limit loses: the day after the last is the defeat (the header's counter only shows it).
    for m in v.iter_mut().filter(|m| m.key >= "bh12") {
        if m.day_limit > 0 {
            let up = Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: m.day_limit + 1 }, vec![Action::Lose]).repeating();
            m.triggers.push(up);
        }
    }
    v
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn act_three_is_m12_to_m16_in_order() {
        let keys: Vec<&str> = missions().iter().map(|m| m.key).filter(|k| *k >= "bh12").collect();
        assert_eq!(keys, ["bh12", "bh13", "bh14", "bh15", "bh16"]);
    }

    #[test]
    fn every_map_is_built_and_every_mission_has_scenes_and_a_flag_in_yellow_comet() {
        for m in missions().iter().filter(|m| m.key >= "bh12") {
            let MapSrc::Built(name) = &m.map else { panic!("{}: not a built map", m.key) };
            assert!(crate::bh_map_data::MAPS.iter().any(|b| b.name == *name), "{}: map {name} is not built (five/bhmap.py)", m.key);
            if let Some(f) = &m.front2 {
                let MapSrc::Built(n2) = &f.map else { panic!("{}: second front not built", m.key) };
                assert!(crate::bh_map_data::MAPS.iter().any(|b| b.name == *n2), "{}: map {n2}", m.key);
            }
            assert!(!m.intro.is_empty() && !m.after.is_empty(), "{}: scenes", m.key);
            // AW2's Yellow Comet, the centre land
            assert!((225..=300).contains(&m.flag.0) && (50..=180).contains(&m.flag.1), "{}: flag {:?} off Yellow Comet", m.key, m.flag);
        }
    }
}
