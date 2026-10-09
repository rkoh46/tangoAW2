//! Act 5, first half: Orange Star's lands (M23 to M28). Its missions are `MissionDef`s
//! (docs/AW2.md "BH Campaign": adding a mission); this file is the half-act's alone,
//! so builders can work on acts in parallel. A mission names what it needs by key
//! (`Needs::All(vec!["bh22"])`), not by index. M29 and M30 are `bh_act5.rs`'s, M31 the
//! secret mission's (`bh_secret.rs`).
//!
//! The maps are `five/bh/bh23.txt` .. `bh28.txt` (built by `five/bhmap.py` into
//! `bh_map_data.rs`: roads, rivers, coasts and shoals joined as AW2 draws them,
//! reachability and the Landers' beaches checked). The dialogue is the design bible's
//! (docs/BH_CAMPAIGN.md 4.6, converted into `bh_act5b_text.rs`).

// (the builders' imports: each act uses what it needs)
#![allow(unused_imports)]

use mgba::core::Core;

use crate::bh_campaign::{region, roster};
use crate::campaign_model::{OnyxDef, SendRule, VolcanoDef};
use crate::custom_campaign::{co, colour, unit, *};

#[path = "bh_act5b_text.rs"]
pub(crate) mod text;

fn scene(lines: Vec<Line>) -> Scene {
    Scene::new(lines)
}

/// An army's CO meter set to `pct` of its full meter.
pub(crate) fn meter(core: &mut Core, army: u32, pct: u32) {
    let p = crate::tag::player(core, army);
    let co = crate::tag::army_co_of(core, army);
    let uses = core.raw_read_8(p + 0x25, -1);
    let full = crate::tag::cop_cost(core, co, uses);
    core.raw_write_32(p + 0x20, -1, full * pct / 100);
}

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


/// A development aid for the review pictures (`TANGOAW2_BH_STILL=1`): the computer's armies hold and have no
/// funds, so a picture taken after their first turns still shows the deployment as designed.
pub(crate) fn still() -> bool {
    std::env::var_os("TANGOAW2_BH_STILL").is_some()
}

/// The computer's orders for a mission's units (AW2's roles, measured in docs/AW2.md: 0 holds where it
/// stands, 3 goes for the enemy's properties, 4 for the enemy's units): everything of the computer's
/// advances (foot soldiers on the properties, the rest on the units) but the deliberate holders:
/// `holders` are the cells of the units that stay put (HQ guards, the guns that cover them, a Lander
/// with nothing to carry). The player's own units keep role 0 (a human moves them).
pub(crate) fn roles(units: Vec<UnitDef>, player: u8, holders: &[(u8, u8)]) -> Vec<UnitDef> {
    let still = still();
    units
        .into_iter()
        .map(|mut u| {
            u.ai = if still || u.army == player || holders.contains(&(u.x, u.y)) {
                0
            } else if matches!(u.kind, unit::INFANTRY | unit::MECH) {
                3
            } else {
                4
            };
            u
        })
        .collect()
}

/// The units of a built map's text file, for a second front (whose deployment is the front's own).
pub(crate) fn built_units(name: &str) -> Vec<UnitDef> {
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

/// Bond indexes (`bh_campaign::BONDS`).
const BOND_LASH: u8 = 6;
const BOND_ADDER: u8 = 7;
const BOND_CLONE: u8 = 8;

fn bh23() -> MissionDef {
    let mut m = MissionDef::new("bh23", "Laboratory 7");
    m.objective = "Capture Lash's HQ in the fog. 22 days.";
    m.map = MapSrc::Built("bh23");
    // Lash's HQ guard (the two Infantry beside the HQ) holds; her toys and the rest advance.
    m.units = roles(built_units("bh23"), 1, &[(18, 8), (18, 10)]);
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(8000),
        // Lash commands Orange Star's lab army in its colours.
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::LASH)).funds(20000),
    ];
    m.fog = true;
    m.day_limit = 22;
    m.rank_days = 15;
    m.intro = scene(text::m23_pre());
    m.victory = scene(text::m23_post());
    m.after = scene(text::m23_map());
    m.triggers = vec![
        on_day(5, None, vec![Action::Scene(scene(text::m23_day_5()))]),
        on_day(11, None, vec![Action::Scene(scene(text::m23_day_11()))]),
        // The win: Jugger's pitch earns Lash's bond (the design's affinity: Lash and Jugger).
        after(Cond::All(vec![beaten(2, (19, 9), 1), Cond::PlayerCo(co::JUGGER)]), vec![Action::EarnBond(BOND_LASH), Action::Win]),
        after(Cond::All(vec![beaten(2, (19, 9), 1), Cond::Not(Box::new(Cond::PlayerCo(co::JUGGER)))]), vec![Action::Win]),
    ];
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
    m.look = 2; // the Desert look: an airfield in the sand
    // The aircraft and the Missiles advance; the HQ's Anti-Air and Infantry hold the HQ and the apron.
    m.units = roles(built_units("bh24"), 1, &[(18, 7), (18, 9), (18, 8), (18, 5), (18, 10)]);
    // A pre-deployed dogfight: one airport each way, no bases.
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(6000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::ADDER)).funds(14000),
    ];
    m.day_limit = 14;
    m.rank_days = 9;
    m.intro = scene(text::m24_pre());
    m.victory = scene(text::m24_post());
    m.after = scene(text::m24_map());
    let won = || Cond::Any(vec![Cond::Custom(adders_aircraft_gone), Cond::OwnerAt { x: 19, y: 8, army: 1 }]);
    m.triggers = vec![
        on_day(4, None, vec![Action::Scene(scene(text::m24_day_4()))]),
        on_day(9, None, vec![Action::Scene(scene(text::m24_day_9()))]),
        // Kindle's pitch earns Adder's bond.
        after(Cond::All(vec![won(), Cond::PlayerCo(co::KINDLE)]), vec![Action::EarnBond(BOND_ADDER), Action::Win]),
        after(Cond::All(vec![won(), Cond::Not(Box::new(Cond::PlayerCo(co::KINDLE)))]), vec![Action::Win]),
    ];
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

/// The second front is the one on the screen.
fn on_second_front(core: &mut Core) -> bool {
    crate::two_front::second_live(core)
}

fn bh25() -> MissionDef {
    let mut m = MissionDef::new("bh25", "Twin Harbours");
    m.objective = "Take Port Orange and the Market Atoll. 24 days.";
    m.map = MapSrc::Built("bh25");
    // Sami's HQ Infantry and her three Landers (nothing to carry until the player lands) hold; the rest advance.
    m.units = roles(built_units("bh25"), 1, &[(28, 9), (28, 11), (22, 7), (22, 14), (21, 10)]);
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
        // (Hachi's two HQ Infantry and his two Landers hold; the rest advance)
        units: roles(built_units("bh25b"), 1, &[(20, 7), (20, 9), (17, 5), (17, 11)]),
        cos: [CoSpec::Pick, CoSpec::Fixed(co::HACHI), CoSpec::None, CoSpec::None],
        send: SendRule::Ground,
        sky: false,
        weather: Weather::Clear,
        fog: false,
    });
    m.intro = scene(text::m25_pre());
    m.victory = scene(text::m25_post());
    m.after = scene(text::m25_map());
    m.triggers = vec![
        Trigger::new(When::TurnStart, Cond::Custom(second_front_won), vec![Action::Scene(scene(text::m25_day()))]),
        Trigger::new(When::TurnStart, Cond::Custom(second_front_lost), vec![Action::Scene(scene(vec![say(co::HACHI, "The market is mine, customer!")]))]),
        on_day(6, None, vec![Action::Scene(scene(text::m25_day_6()))]),
        // Hachi's till: on the market front he takes 3000 a day (a script, as the design says).
        Trigger::new(When::TurnStart, Cond::Custom(on_second_front), vec![Action::AddFunds { army: 2, funds: 3000 }]).repeating(),
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
    // Each ally's Infantry beside its HQ holds it (and Grimm's Fighters fly); the rest advance on BH.
    m.units = roles(built_units("bh26"), 1, &[(3, 3), (5, 3), (3, 21), (5, 22), (32, 13), (32, 15)]);
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(20000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::JAKE)).team(2).funds(5000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::COLIN)).team(2).funds(5000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::GRIMM)).team(2).funds(5000),
    ];
    m.day_limit = 30;
    m.rank_days = 20;
    m.intro = scene(text::m26_pre());
    m.victory = scene(text::m26_post());
    m.after = scene(text::m26_map());
    m.triggers = vec![on_day(8, None, vec![Action::Scene(scene(text::m26_day_8()))]), after(
        Cond::All(vec![beaten(2, (4, 4), 1), beaten(3, (4, 23), 1), beaten(4, (33, 14), 1)]),
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
    // The Orange Star base is held by its two Artillery and the Infantry about the HQ; the rest advance.
    m.units = roles(built_units("bh27"), 1, &[(21, 8), (21, 10), (22, 9), (20, 8), (20, 10)]);
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(5000),
        // Clone Andy leads; the real Andy fights beside him.
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::CLONE_ANDY, co::ANDY)).funds(14000),
    ];
    m.fog = true;
    m.day_limit = 20;
    m.rank_days = 13;
    m.intro = scene(text::m27_pre());
    m.victory = scene(text::m27_post());
    // (the world-map scenes: this mission's, then the alarm from home that opens M28)
    let mut after_lines = text::m27_map();
    after_lines.extend(text::m28_map_before_the_mission());
    m.after = scene(after_lines);
    m.triggers = vec![
        on_day(5, None, vec![Action::Scene(scene(text::m27_day_5()))]),
        on_day(10, None, vec![Action::Scene(scene(text::m27_day_10()))]),
        // Lash's or Sturm's pitch earns Clone Andy's bond (the design's affinity: Clone and Lash).
        after(Cond::All(vec![beaten(2, (21, 9), 1), Cond::PlayerCo(co::LASH)]), vec![Action::EarnBond(BOND_CLONE), Action::Win]),
        after(Cond::All(vec![beaten(2, (21, 9), 1), Cond::Not(Box::new(Cond::PlayerCo(co::LASH)))]), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh26"]);
    m.recruits = vec![roster::CLONE_ANDY];
    m.flag = region::ORANGE_STAR[4];
    m.stars = 3;
    m
}

// --- M28 Home Is Where The Black Is ----------------------------------------------------

/// The Obelisk Gate (the city north of the Obelisk) is in the coalition's hands.
fn gate_lost(core: &mut Core) -> bool {
    !holds(core, &Cond::OwnerAt { x: 17, y: 13, army: 5 })
}

fn bh28() -> MissionDef {
    let mut m = MissionDef::new("bh28", "Home Is Where The Black Is");
    m.objective = "Hold the Obelisk Gate, break all four armies. 36 days.";
    m.map = MapSrc::Built("bh28");
    // Each ally's two Infantry beside its HQ hold it and the Rockets cover them; the rest of the four armies advance
    // on the fortress (the coalition attacks).
    m.units = roles(built_units("bh28"), 5, &[(2, 3), (4, 3), (32, 3), (30, 3), (2, 27), (4, 27), (32, 27), (30, 27), (8, 3), (28, 3), (8, 27), (29, 28)]);
    m.look = 2; // the Desert look (the Wasteland look paints water as lava: Blue Moon's river and coast stay water)
    let ally_funds = if still() { 0 } else { 12000 };
    // Five armies: the player is the fifth (Black Hole), a tag pair (the natural one: Sturm and
    // Clone Andy; the engine has no pick yet in five-army missions).
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::RACHEL)).team(1).funds(ally_funds),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF)).team(1).funds(ally_funds),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::EAGLE)).team(1).funds(ally_funds),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KANBEI)).team(1).funds(ally_funds),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::STURM, co::CLONE_ANDY)).funds(16000),
    ];
    m.day_limit = 36;
    m.rank_days = 24;
    // The Black Onyx is ours, on a five-day cycle; the four corner silos can bring it down.
    m.onyx = Some(OnyxDef::new((16, 14)));
    // Mount Ember's rim: from day 3, every day, three marked cells of the east gate road erupt for 5 HP (any army).
    m.volcano = Some(VolcanoDef::new(3, 1, 5, &[(25, 15), (27, 15), (29, 15)]));
    m.intro = scene(text::m28_pre());
    m.victory = scene(text::m28_post());
    // The world map: the MAP scene, then Crumb's promotion at dusk (he is a CO from the win: `recruits`).
    let mut after_lines = text::m28_map();
    after_lines.extend(text::m28_promotion());
    m.after = scene(after_lines);
    m.recruits = vec![roster::CRUMB];
    m.triggers = vec![
        on_day(5, None, vec![Action::Scene(scene(text::m28_day_5()))]),
        on_day(10, None, vec![Action::Scene(scene(text::m28_day_10()))]),
        on_day(15, None, vec![Action::Scene(scene(text::m28_day_15()))]),
        on_day(20, None, vec![Action::Scene(scene(text::m28_day_20()))]),
        Trigger::new(When::AfterAction, Cond::OnyxHitsAtMost(3), vec![Action::Scene(scene(text::m28_onyx_hit1()))]),
        Trigger::new(When::AfterAction, Cond::OnyxHitsAtMost(2), vec![Action::Scene(scene(text::m28_onyx_hit2()))]),
        Trigger::new(When::AfterAction, Cond::OnyxHitsAtMost(1), vec![Action::Scene(scene(text::m28_onyx_hit3()))]),
        Trigger::new(When::AfterAction, Cond::OnyxDestroyed, vec![Action::Scene(scene(text::m28_onyx_destroyed()))]),
        after(
            Cond::All(vec![beaten(1, (3, 3), 5), beaten(2, (31, 3), 5), beaten(3, (3, 27), 5), beaten(4, (31, 27), 5)]),
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ds_campaign_data::wrap_dialogue;

    fn all_scenes() -> Vec<(String, Scene)> {
        let mut v = Vec::new();
        for m in missions().into_iter().chain(crate::bh_secret::missions()) {
            v.push((format!("{} intro", m.key), m.intro.clone()));
            v.push((format!("{} victory", m.key), m.victory.clone()));
            v.push((format!("{} after", m.key), m.after.clone()));
            for (i, t) in m.triggers.iter().enumerate() {
                for a in &t.then {
                    if let Action::Scene(s) = a {
                        v.push((format!("{} trigger {i}", m.key), s.clone()));
                    }
                }
            }
        }
        v
    }

    #[test]
    fn act_five_b_is_m23_to_m28_in_order_with_the_design_flags() {
        let ms = missions();
        let keys: Vec<&str> = ms.iter().map(|m| m.key).filter(|k| *k >= "bh23").collect();
        assert_eq!(keys, ["bh23", "bh24", "bh25", "bh26", "bh27", "bh28"]);
        let get = |k: &str| ms.iter().find(|m| m.key == k).unwrap();
        assert_eq!(get("bh26").needs, Needs::All(vec!["bh24", "bh25"]));
        assert_eq!(get("bh23").recruits, vec![roster::LASH]);
        assert_eq!(get("bh24").recruits, vec![roster::ADDER]);
        assert_eq!(get("bh27").recruits, vec![roster::CLONE_ANDY]);
        assert_eq!(get("bh28").recruits, vec![roster::CRUMB]);
        for k in ["bh23", "bh24", "bh27"] {
            assert!(get(k).triggers.iter().any(|t| t.then.iter().any(|a| matches!(a, Action::EarnBond(_)))), "{k}: bond");
        }
        assert!(get("bh28").onyx.is_some() && get("bh28").volcano.is_some());
        assert_eq!(get("bh28").armies.len(), 5);
        assert!(get("bh25").front2.is_some());
    }

    #[test]
    fn every_map_is_built_with_its_units() {
        for m in missions().iter().filter(|m| m.key >= "bh23").chain(crate::bh_secret::missions().iter()) {
            let MapSrc::Built(name) = &m.map else { panic!("{}: not built", m.key) };
            let b = crate::bh_map_data::MAPS.iter().find(|b| b.name == *name).unwrap_or_else(|| panic!("{}: map {name} not built", m.key));
            assert!(b.units.len() > 20, "{}: units", m.key);
            assert_eq!(b.armies as usize, m.armies.len(), "{}: armies", m.key);
        }
        // two Vault Trucks (APCs) are on the map; the third is spawned on day 3
        let b = crate::bh_map_data::MAPS.iter().find(|b| b.name == "bh31").unwrap();
        assert_eq!(b.units.iter().filter(|u| u.army == 2 && u.kind == unit::APC).count(), 2);
    }

    /// Every line of every scene fits one box (two lines of AW2's 176 pixels).
    /// Run with the AW2 ROM: `TANGOAW2_AW2_ROM=... cargo test -p tango-gamesupport-aw2 --lib bh_act5b -- --ignored`.
    #[test]
    #[ignore]
    fn dialogue_fits_the_boxes() {
        let rom = std::fs::read(std::env::var("TANGOAW2_AW2_ROM").unwrap()).unwrap();
        let widths = rom[0x4C_36E4..][..256].to_vec();
        let mut checked = 0;
        for (name, scene) in all_scenes() {
            for l in &scene.lines {
                let t = wrap_dialogue(l.text.as_bytes(), &widths);
                let boxes: Vec<&[u8]> = t.split(|&c| c == 0x0F).filter(|b| !b.is_empty()).collect();
                assert_eq!(boxes.len(), 1, "{name}: {:?} needs {} boxes", l.text, boxes.len());
                assert!(boxes[0].split(|&c| c == b'\r').count() <= 2, "{name}: {:?}", l.text);
                checked += 1;
            }
        }
        assert!(checked > 300, "{checked} lines checked");
    }
}
