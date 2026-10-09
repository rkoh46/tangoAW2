//! Act 5, first half: Orange Star's lands (M23 to M28). Its missions are `MissionDef`s
//! (docs/AW2.md "BH Campaign": adding a mission); this file is the half-act's alone,
//! so builders can work on acts in parallel. A mission names what it needs by key
//! (`Needs::All(vec!["bh22"])`), not by index. M29 and M30 are `bh_act5.rs`'s, M31 the
//! secret mission's (`bh_secret.rs`).
//!
//! The maps are `five/bh/bh23.txt` .. `bh28.txt` (built by `five/bhmap.py` into
//! `bh_map_data.rs`: roads, rivers, coasts and shoals joined as AW2 draws them,
//! reachability and the Landers' beaches checked). The scenes are placeholders until the
//! design bible's dialogue (docs/BH_CAMPAIGN.md section 4.6) is wired in.

// (the builders' imports: each act uses what it needs)
#![allow(unused_imports)]

use mgba::core::Core;

use crate::bh_campaign::{region, roster};
use crate::campaign_model::{OnyxDef, SendRule, VolcanoDef};
use crate::custom_campaign::{co, colour, unit, *};

// --- Writing helpers ---------------------------------------------------------------

fn troop(text: &'static str) -> Line {
    Line::soldier(colour::BLACK_HOLE, text)
}

fn say(c: u8, text: &'static str) -> Line {
    Line::say(c, text)
}

/// "On day `d`, at the start of the player's turn": fires once, on that day.
fn on_day(d: u16, cond: Option<Cond>, then: Vec<Action>) -> Trigger {
    let day = Cond::EveryDays { n: 1000, from: d };
    let cond = match cond {
        Some(c) => Cond::All(vec![day, c]),
        None => day,
    };
    Trigger::new(When::TurnStart, cond, then).repeating()
}

/// After each action, while the condition holds (a win or a loss: the match ends).
fn after(cond: Cond, then: Vec<Action>) -> Trigger {
    Trigger::new(When::AfterAction, cond, then).repeating()
}

/// The enemy army is as good as routed: at most one unit left, or its HQ is the player's.
fn beaten(enemy: u8, hq: (u8, u8), player: u8) -> Cond {
    Cond::Any(vec![Cond::ArmyUnitsAtMost { army: enemy, n: 1 }, Cond::OwnerAt { x: hq.0, y: hq.1, army: player }])
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

// --- M23 Laboratory 7 ----------------------------------------------------------------

fn bh23() -> MissionDef {
    let mut m = MissionDef::new("bh23", "Laboratory 7");
    m.objective = "Capture Lash's HQ in the fog. 22 days.";
    m.map = MapSrc::Built("bh23");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(8000),
        // Lash commands Orange Star's lab army in its colours.
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::LASH)).funds(20000),
    ];
    m.fog = true;
    m.day_limit = 22;
    m.rank_days = 15;
    m.intro = Scene::new(vec![troop("Laboratory 7. Fog on the test yard. Lash's toys are loose.")]);
    m.victory = Scene::new(vec![troop("The lab is ours.")]);
    m.after = Scene::new(vec![troop("Lash is coming with us.")]);
    m.needs = Needs::All(vec!["bh22"]);
    m.recruits = vec![roster::LASH];
    m.flag = region::ORANGE_STAR[0];
    m.stars = 2;
    m
}

// --- M24 Sky Gala --------------------------------------------------------------------

fn adders_aircraft_gone(core: &mut Core) -> bool {
    units_of(core, 2).iter().all(|u| !matches!(u.1, unit::FIGHTER | unit::BOMBER | unit::STEALTH | unit::B_COPTER | unit::T_COPTER | unit::BLACK_BOMB))
}

fn bh24() -> MissionDef {
    let mut m = MissionDef::new("bh24", "Sky Gala");
    m.objective = "Rout Adder's air force or take his HQ. 14 days.";
    m.map = MapSrc::Built("bh24");
    // A pre-deployed dogfight: one airport each way, no bases.
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(6000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::ADDER)).funds(14000),
    ];
    m.day_limit = 14;
    m.rank_days = 9;
    m.intro = Scene::new(vec![troop("An air show. Adder's whole air force is on the field.")]);
    m.victory = Scene::new(vec![troop("The sky is ours.")]);
    m.after = Scene::new(vec![troop("Adder wants a new flag.")]);
    m.triggers = vec![after(Cond::Custom(adders_aircraft_gone), vec![Action::Win])];
    m.needs = Needs::All(vec!["bh23"]);
    m.recruits = vec![roster::ADDER];
    m.flag = region::ORANGE_STAR[1];
    m.stars = 2;
    m
}

// --- M25 Twin Harbours ---------------------------------------------------------------

/// The second front's outcome (crate::two_front's state byte: 2 won, 3 lost).
fn second_front_won(core: &mut Core) -> bool {
    core.raw_read_8(0x0203_E401, -1) == 2
}

fn second_front_lost(core: &mut Core) -> bool {
    core.raw_read_8(0x0203_E401, -1) == 3
}

fn bh25() -> MissionDef {
    let mut m = MissionDef::new("bh25", "Twin Harbours");
    m.objective = "Take Port Orange and the market district. 24 days.";
    m.map = MapSrc::Built("bh25");
    // The player picks two COs: the main front's, then the second front's.
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(10000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::SAMI)).funds(16000),
    ];
    m.day_limit = 24;
    m.rank_days = 16;
    m.front2 = Some(FrontDef {
        map: MapSrc::Built("bh25b"),
        props: Vec::new(),
        structures: Vec::new(),
        units: built_units("bh25b"),
        cos: [CoSpec::Pick, CoSpec::Fixed(co::HACHI), CoSpec::None, CoSpec::None],
        send: SendRule::Ground,
        sky: false,
        weather: Weather::Clear,
        fog: false,
    });
    m.intro = Scene::new(vec![troop("Port Orange by the bay, a market town inland. Two fronts.")]);
    m.victory = Scene::new(vec![troop("Both harbours are ours.")]);
    m.after = Scene::new(vec![troop("The alliance is forming against us.")]);
    m.triggers = vec![
        Trigger::new(When::TurnStart, Cond::Custom(second_front_won), vec![Action::Scene(Scene::new(vec![troop("The market district is ours.")]))]),
        Trigger::new(When::TurnStart, Cond::Custom(second_front_lost), vec![Action::Scene(Scene::new(vec![say(co::HACHI, "The market is mine, customer!")]))]),
        after(beaten(2, (23, 6), 1), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh23"]);
    m.flag = region::ORANGE_STAR[2];
    m.stars = 3;
    m
}

// --- M26 The Last Alliance -----------------------------------------------------------

fn bh26() -> MissionDef {
    let mut m = MissionDef::new("bh26", "The Last Alliance");
    m.objective = "Break Jake, Colin and Grimm. 30 days, par 20.";
    m.map = MapSrc::Built("bh26");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(14000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::JAKE)).team(2).funds(8000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::COLIN)).team(2).funds(8000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::GRIMM)).team(2).funds(8000),
    ];
    m.day_limit = 30;
    m.rank_days = 20;
    m.intro = Scene::new(vec![troop("Three young commanders, one alliance, one ruined temple.")]);
    m.victory = Scene::new(vec![troop("The alliance is broken.")]);
    m.after = Scene::new(vec![troop("Next: the clone.")]);
    m.triggers = vec![after(
        Cond::All(vec![beaten(2, (3, 2), 1), beaten(3, (26, 2), 1), beaten(4, (26, 21), 1)]),
        vec![Action::Win],
    )];
    m.needs = Needs::All(vec!["bh24", "bh25"]);
    m.flag = region::ORANGE_STAR[3];
    m.stars = 3;
    m
}

// --- M27 Echo ------------------------------------------------------------------------

fn bh27() -> MissionDef {
    let mut m = MissionDef::new("bh27", "Echo");
    m.objective = "Capture the Orange Star base at (21, 9). 20 days.";
    m.map = MapSrc::Built("bh27");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(5000),
        // Clone Andy leads; the real Andy fights beside him.
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::CLONE_ANDY, co::ANDY)).funds(14000),
    ];
    m.fog = true;
    m.day_limit = 20;
    m.rank_days = 13;
    m.intro = Scene::new(vec![troop("Sunrise Plains. Two Andys, one fog.")]);
    m.victory = Scene::new(vec![troop("The base is ours.")]);
    m.after = Scene::new(vec![troop("The clone wants to come home.")]);
    m.needs = Needs::All(vec!["bh26"]);
    m.recruits = vec![roster::CLONE_ANDY];
    m.flag = region::ORANGE_STAR[4];
    m.stars = 3;
    m
}

// --- M28 Home Is Where The Black Is ----------------------------------------------------

/// The Obelisk Gate (the city north of the Obelisk) is in the coalition's hands.
fn gate_lost(core: &mut Core) -> bool {
    !holds(core, &Cond::OwnerAt { x: 14, y: 12, army: 5 })
}

fn bh28() -> MissionDef {
    let mut m = MissionDef::new("bh28", "Home Is Where The Black Is");
    m.objective = "Hold the Obelisk Gate, break all four armies. 36 days.";
    m.map = MapSrc::Built("bh28");
    m.look = 3; // the Wasteland look
    // Five armies: the player is the fifth (Black Hole), a tag pair (the natural one: Sturm and
    // Clone Andy; the engine has no pick yet in five-army missions).
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::RACHEL)).team(1).funds(12000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF)).team(1).funds(12000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::EAGLE)).team(1).funds(12000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KANBEI)).team(1).funds(12000),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::STURM, co::CLONE_ANDY)).funds(16000),
    ];
    m.day_limit = 36;
    m.rank_days = 24;
    // The Black Onyx is ours, on a five-day cycle; the four corner silos can bring it down.
    m.onyx = Some(OnyxDef::new((13, 13)));
    // Mount Ember's rim track: from day 3, every day, three marked cells erupt for 5 HP (any army).
    m.volcano = Some(VolcanoDef::new(3, 1, 5, &[(20, 12), (24, 8), (24, 15)]));
    m.intro = Scene::new(vec![troop("The Black Wastes. Four armies at the gates and a satellite overhead.")]);
    m.victory = Scene::new(vec![troop("Home holds.")]);
    m.after = Scene::new(vec![troop("Crumb has a commander's sash now.")]);
    m.triggers = vec![
        after(
            Cond::All(vec![beaten(1, (4, 4), 5), beaten(2, (24, 4), 5), beaten(3, (4, 24), 5), beaten(4, (24, 24), 5)]),
            vec![Action::Win],
        ),
        after(Cond::Custom(gate_lost), vec![Action::Lose]),
    ];
    m.needs = Needs::All(vec!["bh27"]);
    m.flag = region::BLACK_HOLE[4];
    m.stars = 4;
    m
}

/// Development fallback: a stand-in for act 4's M22 when it is not in the tree yet.
fn dev_stub_bh22() -> MissionDef {
    let mut m = MissionDef::new("bh22", "Placeholder 22");
    m.objective = "Rout the Blue Moon force.";
    m.map = MapSrc::Ascii(&["1.........", "..ff..c...", "....mm....", "...c..c...", ".........2"]);
    m.armies = vec![ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)), ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF))];
    m.units = vec![UnitDef::new(1, unit::INFANTRY, 1, 1), UnitDef::new(2, unit::INFANTRY, 8, 3)];
    m.flag = region::BLUE_MOON[5];
    m
}

/// Act 5's first half, in world-map order.
pub fn missions() -> Vec<MissionDef> {
    let mut v = vec![dev_stub_bh22(), bh23(), bh24(), bh25(), bh26(), bh27(), bh28()];
    // The day limit loses: the day after the last is the defeat (the header's counter only shows it).
    for m in v.iter_mut().filter(|m| m.key >= "bh23") {
        if m.day_limit > 0 {
            let up = Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: m.day_limit + 1 }, vec![Action::Lose]).repeating();
            m.triggers.push(up);
        }
    }
    v
}
