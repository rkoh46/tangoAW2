//! The BH2 Campaign: Black Hole's eastern war on the AW1-style picture world map (docs/BH2_CAMPAIGN.md, docs/dev/bh2-maps.md, docs/dev/bh2-text.md). Thirty-one missions
//! (M30 and M31 are the final mission's two maps) and the secret M32: the maps are `five/bh2/spec/*.py` -> `bh2_map_data.rs`, the dialogue is `src/bh2_text/*.txt`
//! (`bh2_text.rs`, wired below with `txt("...")`), the songs `music/bh2/*.m4t` (`es_music::SOURCES`).
//!
//! It is a campaign of the Campaign chooser ([`available`]; the release toggle [`RELEASED`]). Its record lives in the BH Campaign's Flash slot 13, after the BH record
//! (`campaign_model::Source::save_offset`); a mission saved halfway shares slot 12 (`suspend::source_tag`).
//!
//! TODO(map-switch merge): M30 is now "The Orange Line" (a new map) and the gauntlet plus Aria's citadel become the one finale mission M31 (a mid-battle map switch). Until then the
//! scenes of M30 and of M31's opening, takeovers, switch and second stage are not asked for ([`TODO_SCENES`]); only `m31_post` and the epilogue are wired.

use mgba::core::Core;

use crate::campaign_model::Model;
use crate::campaign_model::{ring, SendRule, VolcanoDef};
use crate::custom_campaign::{co, colour, unit, *};
use crate::es_campaign::{after, deployment, on_day, wave};

/// The scene with this key from `src/bh2_text/*.txt` (a missing key panics; `tools/bh2text/lint.py` and the test `every_dialogue_scene_is_used` check them all).
fn txt(key: &str) -> Scene {
    crate::bh2_text::scene(key)
}

/// The second front's outcome (crate::two_front's state byte: 2 won, 3 lost).
fn second_front_won(core: &mut Core) -> bool {
    core.raw_read_8(0x0203_E401, -1) == 2
}

fn second_front_lost(core: &mut Core) -> bool {
    core.raw_read_8(0x0203_E401, -1) == 3
}

/// The roster without one officer (a mission whose lead is forced elsewhere: Hawke leads M4's sky front).
fn pool_but(c: u8) -> Vec<u8> {
    ROSTER.iter().map(|r| r.0).filter(|&x| x != c).collect()
}

/// `n` units of an army, as many as `num / den` of what the map gives it at the start.
fn share(map: &str, army: u8, num: usize, den: usize) -> u8 {
    let c = built_map(map).map_or(0, |m| m.units.iter().filter(|u| u.army == army).count());
    (c * num / den) as u8
}

/// The campaign's source index in [`crate::campaign_model::SOURCES`].
pub const SOURCE: usize = 3;

/// The release toggle (docs/dev/bh2-maps.md "Release"): `true` shows the campaign in every build. Set it `false` to hide the campaign again; the environment variable
/// `TANGOAW2_BH2_CAMPAIGN` (any value) shows it anyway, as the test harness does.
pub const RELEASED: bool = true;

/// The campaign is shown and playable: released (or the variable is set).
pub fn dev_flag() -> bool {
    RELEASED || std::env::var_os("TANGOAW2_BH2_CAMPAIGN").is_some()
}

/// The campaign is playable (the Dual Strike pack is on and the campaign is released).
pub fn available(core: &Core) -> bool {
    crate::ds_weather::is_on(core) && dev_flag()
}

/// The scenes of the dialogue files that no mission asks for yet (the map-switch merge wires them); `every_dialogue_scene_is_used` allows exactly these.
pub const TODO_SCENES: [&str; 14] = [
    "m30_pre",
    "m30_day5",
    "m30_post",
    "m30_map",
    "m31_pre",
    "m31_day5",
    "m31_takeover_olaf",
    "m31_takeover_kanbei",
    "m31_takeover_eagle",
    "m31_switch",
    "m31_stage2",
    "m31_day6",
    "m31_day9",
    "m31_day12",
];

/// The roster, in unlock order: the eleven Black Hole officers the dialogue expects, all open (Sturm is never a free pick: he is forced with Asuka in M5 only).
pub const ROSTER: [(u8, bool); 11] = [
    (crate::co_new::ASUKA, true),
    (co::CRUMB, true),
    (co::HAWKE, true),
    (co::KOAL, true),
    (co::KINDLE, true),
    (co::JUGGER, true),
    (co::FLAK, true),
    (co::LASH, true),
    (co::ADDER, true),
    (co::VON_BOLT, true),
    (co::CLONE_ANDY, true),
];

/// A mission's flag place on the picture world map (`world_picture::BH2_FLAGS`).
fn flag(mission: u8) -> (i16, i16) {
    crate::world_picture::BH2_FLAGS
        .iter()
        .find(|f| f.0 == mission)
        .map_or((0, 0), |f| (f.2, f.3))
}

/// M2's crate truck destination: the goal tile of the depot town at the end of the main road.
const M2_GOAL: (u8, u8) = (26, 19);

fn beaten(enemy: u8, hq: (u8, u8)) -> Cond {
    Cond::Any(vec![
        Cond::ArmyUnitsAtMost { army: enemy, n: 1 },
        Cond::OwnerAt {
            x: hq.0,
            y: hq.1,
            army: 1,
        },
    ])
}

/// M1 Black Insight: fog, Asuka (forced) against Drake.
fn bh2_01() -> MissionDef {
    let mut m = MissionDef::new("bh2_01", "Black Insight");
    m.objective = "Land on Halyard Isle and take the fort's HQ.";
    m.map = MapSrc::Built("bh2_01");
    m.fog = true;
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(crate::co_new::ASUKA)).funds(6000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::DRAKE)).funds(9000),
    ];
    m.units = deployment("bh2_01");
    m.rank_days = 12;
    m.intro = txt("m01_pre");
    m.victory = txt("m01_post");
    m.after = crate::bh2_text::chain(&["m01_map"]);
    m.triggers.push(on_day(4, None, vec![Action::Scene(txt("m01_day4"))]));
    m.flag = flag(1);
    m.stars = 1;
    m.needs = Needs::Start;
    m
}

/// M2 The Quartermaster's Crate: Asuka + Crumb (forced pair), the crate truck must reach the depot town.
fn bh2_02() -> MissionDef {
    let mut m = MissionDef::new("bh2_02", "The Quartermaster's Crate");
    m.objective = "Bring the crate truck to the depot town at the end of the road before day 14.";
    m.map = MapSrc::Built("bh2_02");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(crate::co_new::ASUKA, co::CRUMB)).funds(4000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JESS)).funds(12000),
    ];
    m.units = deployment("bh2_02");
    m.day_limit = 14;
    m.rank_days = 11;
    m.triggers = vec![
        after(
            Cond::UnitAt {
                name: "crate",
                x: M2_GOAL.0,
                y: M2_GOAL.1,
            },
            vec![Action::Win],
        ),
        after(Cond::UnitGone("crate"), vec![Action::Lose]),
    ];
    m.intro = txt("m02_pre");
    m.victory = txt("m02_post");
    m.after = crate::bh2_text::chain(&["m02_map"]);
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m02_day5"))]));
    m.triggers.push(on_day(10, None, vec![Action::Scene(txt("m02_day10"))]));
    m.flag = flag(2);
    m.stars = 1;
    m.needs = Needs::All(vec!["bh2_01"]);
    m
}

/// Factory table of M3 (day, the three doors' slots; 0 none): ground units mostly, a Md Tank and an Anti-Air slot for the days the Fighters come.
const F3: [(u8, [u8; 3]); 14] = [
    (2, [0, unit::TANK, 0]),
    (3, [unit::INFANTRY, 0, unit::INFANTRY]),
    (4, [0, unit::MD_TANK, 0]),
    (5, [unit::TANK, 0, unit::TANK]),
    (6, [0, unit::ARTILLERY, 0]),
    (7, [unit::MECH, 0, unit::MECH]),
    (8, [0, unit::MD_TANK, unit::ANTI_AIR]),
    (9, [unit::TANK, 0, unit::TANK]),
    (10, [unit::INFANTRY, unit::MD_TANK, unit::INFANTRY]),
    (11, [0, unit::TANK, 0]),
    (12, [unit::MECH, 0, unit::ROCKETS]),
    (13, [0, unit::MD_TANK, 0]),
    (14, [unit::TANK, 0, unit::TANK]),
    (16, [unit::INFANTRY, unit::MD_TANK, unit::ANTI_AIR]),
];

/// M3 Iron Ledger: a free pick, with Black Hole's Black Factory, against one Green Earth army under the tag pair Javier + Jess.
fn bh2_03() -> MissionDef {
    let mut m = MissionDef::new("bh2_03", "Iron Ledger");
    m.objective = "Hold the foundry and take Javier's HQ.";
    m.map = MapSrc::Built("bh2_03");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(10000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Pair(co::JAVIER, co::JESS)).funds(20000),
    ];
    m.units = deployment("bh2_03");
    m.rank_days = 16;
    m.look = 2; // the Desert look
    m.weather = Weather::Sandstorm; // dust over the desert (long guns lose a cell of range), so M3 does not read as M5's tan wasteland
                                    // Black Hole's Black Factory (the foundry): its schedule by day, three doors (the units are the slots' price caps: the smart spawner, `bh_factory` / `bh_smart`,
                                    // chooses what each slot builds from the field: Anti-Air and Fighters only against air, foot soldiers for captures, indirects behind a safe line, a varied mix)
    m.factory = F3.to_vec();
    // Mount Ember (the volcano in the middle of the map): from day 3 it erupts every day on 3 of the 28 cells of the ring road round it (5 HP, any army's units, never below 1).
    m.volcano = Some(VolcanoDef::new(3, 1, 5, &ring(19, 10, 26, 17)).per_eruption(3));
    m.intro = txt("m03_pre");
    m.victory = txt("m03_post");
    m.after = crate::bh2_text::chain(&["m03_map"]);
    m.triggers.push(on_day(6, None, vec![Action::Scene(txt("m03_day6"))]));
    m.flag = flag(3);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_02"]);
    m
}

/// M4 Talons: front 1 a free pick against Drake, front 2 (the sky) Hawke against Eagle.
fn bh2_04() -> MissionDef {
    let mut m = MissionDef::new("bh2_04", "Talons");
    m.objective = "Hold the island and take Drake's HQ; Hawke fights the sky.";
    m.map = MapSrc::Built("bh2_04");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(10000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::DRAKE)).funds(14000),
    ];
    m.units = deployment("bh2_04");
    m.pool = pool_but(co::HAWKE); // Hawke leads the sky front
    m.rank_days = 14;
    // The sky front (BH1's M20 rule): open sky and aircraft, won and lost by AW2's rout rule; its aircraft attack (role 4), none goes for an HQ.
    m.front2 = Some(FrontDef {
        map: MapSrc::Built("bh2_04b"),
        props: Vec::new(),
        structures: Vec::new(),
        units: crate::bh_ai::built_units("bh2_04b")
            .into_iter()
            .map(|mut u| {
                u.ai = crate::bh_ai::ATTACK;
                u
            })
            .collect(),
        cos: [
            CoSpec::Fixed(co::HAWKE),
            CoSpec::Fixed(co::EAGLE),
            CoSpec::None,
            CoSpec::None,
        ],
        send: SendRule::Air,
        sky: true,
        weather: Weather::Clear,
        fog: false,
    });
    m.intro = txt("m04_pre");
    m.victory = txt("m04_post");
    m.after = crate::bh2_text::chain(&["m04_map"]);
    m.triggers.push(on_day(6, None, vec![Action::Scene(txt("m04_day6"))]));
    m.triggers.push(Trigger::new(When::TurnStart, Cond::Custom(second_front_won), vec![Action::Scene(txt("m04_front2_post"))]));
    m.triggers.push(Trigger::new(When::TurnStart, Cond::Custom(second_front_lost), vec![Action::Scene(txt("m04_front2_lost"))]));
    m.flag = flag(4);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_03"]);
    m
}

/// M5 Evergreen in Exile: the forced pair Sturm + Asuka against two allied armies: Javier + Eagle (a tag pair, one Green Earth army) in the capital and Blue Moon's Grit in the airport district, each with its own HQ; both HQs fall to win.
fn bh2_05() -> MissionDef {
    let mut m = MissionDef::new("bh2_05", "Evergreen in Exile");
    m.objective = "Take the capital's HQ and Grit's HQ in the airport district.";
    m.map = MapSrc::Built("bh2_05");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::STURM, crate::co_new::ASUKA)).funds(20000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Pair(co::JAVIER, co::EAGLE)).team(2).funds(30000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::GRIT)).team(2).funds(16000),
    ];
    m.units = deployment("bh2_05");
    m.rank_days = 22;
    m.look = 3; // the Wasteland look: the exile capital stands on blasted ground
    m.intro = txt("m05_pre");
    m.victory = txt("m05_post");
    m.after = crate::bh2_text::chain(&["m05_map"]);
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m05_day5"))]));
    m.flag = flag(5);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_04"]);
    m
}

/// Javier's four Com Towers on M6's map (the `tower` notes).
const M6_TOWERS: [(u8, u8); 4] = [(25, 5), (31, 10), (28, 16), (35, 14)];
/// Where Eagle's air wing lands when the towers fall.
const M6_WING: [(u8, (u8, u8)); 5] = [
    (unit::FIGHTER, (36, 5)),
    (unit::FIGHTER, (38, 3)),
    (unit::FIGHTER, (33, 9)),
    (unit::B_COPTER, (38, 7)),
    (unit::BOMBER, (32, 3)),
];

/// M6 Forest of Spears: a free pick against Javier (Green Earth) in a forest country of long wooded ridges; when Black Hole holds all four of his Com Towers Eagle takes command of the same army and an air wing lands (a scripted fight, no second HQ).
fn bh2_06() -> MissionDef {
    let mut m = MissionDef::new("bh2_06", "Forest of Spears");
    m.objective = "Take Javier's HQ. Hold all four of his Com Towers and Eagle takes command with an air wing.";
    m.map = MapSrc::Built("bh2_06");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(8000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JAVIER)).funds(14000),
    ];
    m.units = deployment("bh2_06");
    m.rank_days = 18;
    m.triggers = vec![Trigger::new(
        When::AfterAction,
        Cond::All(M6_TOWERS.iter().map(|&(x, y)| Cond::OwnerAt { x, y, army: 1 }).collect()),
        vec![
            Action::Scene(txt("m06_takeover")),
            Action::TakeOver { army: 2, co: co::EAGLE, meter_pct: 40 },
            Action::AddFunds { army: 2, funds: 6000 },
            Action::Spawn(M6_WING.iter().map(|&(k, (x, y))| UnitDef::new(2, k, x, y).attack()).collect()),
        ],
    )];
    m.intro = txt("m06_pre");
    m.victory = txt("m06_post");
    m.after = crate::bh2_text::chain(&["m06_map"]);
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m06_day5"))]));
    m.flag = flag(6);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_05"]);
    m
}

/// M7 Drake's Harbour: a free pick against Drake (Green Earth): a harbour assault over a reef-strewn channel, ports and Landers (desert look).
fn bh2_07() -> MissionDef {
    let mut m = MissionDef::new("bh2_07", "Drake's Harbour");
    m.objective = "Cross the channel by sea, land on the beaches and take Drake's HQ.";
    m.map = MapSrc::Built("bh2_07");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(10000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::DRAKE)).funds(14000),
    ];
    m.units = deployment("bh2_07");
    m.look = 2; // the Desert look
    m.rank_days = 20;
    m.intro = txt("m07_pre");
    m.victory = txt("m07_post");
    m.after = crate::bh2_text::chain(&["m07_map"]);
    m.triggers.push(on_day(6, None, vec![Action::Scene(txt("m07_day6"))]));
    m.flag = flag(7);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_06"]);
    m
}

/// M8 Fuel Line: Koal (forced) against Jess (Green Earth): the road builder against the tanks, along a highway with fuel depots (normal look, sandstorm).
fn bh2_08() -> MissionDef {
    let mut m = MissionDef::new("bh2_08", "Fuel Line");
    m.objective = "Hold the highway's depots and take Jess's HQ.";
    m.map = MapSrc::Built("bh2_08");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::KOAL)).funds(8000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JESS)).funds(14000),
    ];
    m.units = deployment("bh2_08");
    m.weather = Weather::Sandstorm;
    m.rank_days = 20;
    m.intro = txt("m08_pre");
    m.victory = txt("m08_post");
    m.after = crate::bh2_text::chain(&["m08_map", "m08_warroom", "m08_staff"]);
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m08_day5"))]));
    m.flag = flag(8);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_07"]);
    m
}

/// M14 The Long Border: a free pair against Javier (Green Earth) and Grit (Blue Moon), two allied armies across a river with four bridges.
fn bh2_14() -> MissionDef {
    let mut m = MissionDef::new("bh2_14", "The Long Border");
    m.objective = "Cross the river and take both HQs.";
    m.map = MapSrc::Built("bh2_14");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(12000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JAVIER)).team(2).funds(14000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::GRIT)).team(2).funds(14000),
    ];
    m.units = deployment("bh2_14");
    m.weather = Weather::Sandstorm; // a dust storm on the border (and M14 is no look twin of M12)
    m.rank_days = 22;
    m.intro = txt("m14_pre");
    m.victory = txt("m14_post");
    m.after = crate::bh2_text::chain(&["m14_map"]);
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m14_day5"))]));
    m.flag = flag(14);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_13"]);
    m
}

/// M15 Iron Gate Pass: Hawke (forced) against Olaf (Blue Moon) over a mountain massif with three ways through (snow look).
fn bh2_15() -> MissionDef {
    let mut m = MissionDef::new("bh2_15", "Iron Gate Pass");
    m.objective = "Force the Iron Gate, or turn it by the side paths, and take Olaf's HQ.";
    m.map = MapSrc::Built("bh2_15");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::HAWKE)).funds(10000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF)).funds(14000),
    ];
    m.units = deployment("bh2_15");
    m.look = 1; // the Snow look
    m.rank_days = 22;
    m.intro = txt("m15_pre");
    m.victory = txt("m15_post");
    m.after = crate::bh2_text::chain(&["m15_map"]);
    m.triggers.push(on_day(6, None, vec![Action::Scene(txt("m15_day6"))]));
    m.flag = flag(15);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_14"]);
    m
}

/// M9 Paper Lanterns: a free pick, a night intel raid on Sensei's B Copter fleet (rain and fog, the normal look).
fn bh2_09() -> MissionDef {
    let mut m = MissionDef::new("bh2_09", "Paper Lanterns");
    m.objective = "Raid Roost, destroy Sensei's B Copter fleet and take his HQ.";
    m.map = MapSrc::Built("bh2_09");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(8000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::SENSEI)).funds(12000),
    ];
    m.units = deployment("bh2_09");
    m.fog = true;
    m.weather = Weather::Rain; // night rain over the lantern islands
    m.rank_days = 14;
    m.intro = txt("m09_pre");
    m.victory = txt("m09_post");
    m.after = crate::bh2_text::chain(&["m09_map"]);
    m.triggers.push(on_day(4, None, vec![Action::Scene(txt("m09_day4"))]));
    m.flag = flag(9);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_08"]);
    m
}

/// M10 Comet Highway: the forced tag pair Koal + Kindle against one Yellow Comet army under the pair Grimm + Sensei; a straight battle along the river bridges (desert, sandstorm).
fn bh2_10() -> MissionDef {
    let mut m = MissionDef::new("bh2_10", "Comet Highway");
    m.objective = "Cross the four rivers and take the Yellow Comet HQ.";
    m.map = MapSrc::Built("bh2_10");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::KOAL, co::KINDLE)).funds(12000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Pair(co::GRIMM, co::SENSEI)).funds(18000),
    ];
    m.units = deployment("bh2_10");
    m.look = 2; // the Desert look
    m.weather = Weather::Sandstorm;
    m.rank_days = 14;
    m.intro = txt("m10_pre");
    m.victory = txt("m10_post");
    m.after = crate::bh2_text::chain(&["m10_map"]);
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m10_day5"))]));
    m.triggers.push(on_day(9, None, vec![Action::Scene(txt("m10_day9"))]));
    m.flag = flag(10);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_09"]);
    m
}

/// M11 Black Lanterns: a free pick with Black Crystals that heal, against Grimm's big army (rain; the plan's clear weather is rain so that M11 and M12, both the normal look, differ).
fn bh2_11() -> MissionDef {
    let mut m = MissionDef::new("bh2_11", "Black Lanterns");
    m.objective = "Hold the crystals' line and take Grimm's HQ across the river.";
    m.map = MapSrc::Built("bh2_11");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(10000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::GRIMM)).funds(24000),
    ];
    m.units = deployment("bh2_11");
    m.weather = Weather::Rain;
    m.rank_days = 16;
    m.intro = txt("m11_pre");
    m.victory = txt("m11_post");
    m.after = crate::bh2_text::chain(&["m11_map"]);
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m11_day5"))]));
    m.flag = flag(11);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_10"]);
    m
}

/// M12's half strength: Kanbei's army has lost half of the units it started with (28 on the map).
const M12_HALF: u8 = 14;
/// The airlift's B Copters (the map's `mark_air` cells) and Infantry (its `mark_inf` cells).
const M12_AIR: [(u8, u8); 4] = [(17, 5), (25, 5), (21, 9), (13, 7)];
const M12_INF: [(u8, u8); 5] = [(6, 10), (14, 10), (21, 10), (28, 10), (35, 10)];

/// Kanbei has no tank left (Tank, Md Tank, Neotank, Megatank): he yields.
fn m9_no_tanks(core: &mut Core) -> bool {
    units_of(core, 2)
        .iter()
        .all(|u| !matches!(u.1, unit::TANK | unit::MD_TANK | unit::NEOTANK | unit::MEGATANK))
}

/// M12 The Table: Asuka (forced) against Kanbei + Sensei at the capital. No time limit. Scripted: Sensei's airlift at half strength, Kanbei's surrender with his last tank.
fn bh2_12() -> MissionDef {
    let mut m = MissionDef::new("bh2_12", "The Table");
    m.objective = "Break Kanbei's wall and take the capital's HQ.";
    m.map = MapSrc::Built("bh2_12");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(crate::co_new::ASUKA)).funds(15000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Pair(co::KANBEI, co::SENSEI)).funds(20000),
    ];
    m.units = deployment("bh2_12");
    m.rank_days = 20;
    let mut airlift: Vec<UnitDef> = M12_AIR.iter().map(|&(x, y)| UnitDef::new(2, unit::B_COPTER, x, y).attack()).collect();
    airlift.extend(M12_INF.iter().map(|&(x, y)| UnitDef::new(2, unit::INFANTRY, x, y).attack()));
    m.triggers = vec![
        // at half strength Kanbei calls Sensei's airlift
        Trigger::new(When::AfterAction, Cond::ArmyUnitsAtMost { army: 2, n: M12_HALF }, vec![Action::Scene(txt("m12_airlift")), Action::Spawn(airlift)]),
        // his last tank falls: he yields the field
        after(Cond::Custom(m9_no_tanks), vec![Action::Win]),
    ];
    m.intro = txt("m12_pre");
    m.victory = txt("m12_post");
    m.after = crate::bh2_text::chain(&["m12_map"]);
    m.flag = flag(12);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_11"]);
    m
}

/// M13 Two Tides: two fronts. Front 1, Asuka (forced) against Kanbei's last stand; front 2, a free pick against Grimm (Wasteland look, fog, lava for water).
fn bh2_13() -> MissionDef {
    let mut m = MissionDef::new("bh2_13", "Two Tides");
    m.objective = "Take Kanbei's HQ; the second front takes Grimm's.";
    m.map = MapSrc::Built("bh2_13");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(crate::co_new::ASUKA)).funds(10000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KANBEI)).funds(18000),
    ];
    m.units = deployment("bh2_13");
    m.look = 3; // the Wasteland look: the tides are lava
    m.fog = true;
    m.rank_days = 18;
    m.front2 = Some(FrontDef {
        map: MapSrc::Built("bh2_13b"),
        props: Vec::new(),
        structures: Vec::new(),
        units: crate::bh_ai::built_units("bh2_13b"),
        cos: [CoSpec::Pick, CoSpec::Fixed(co::GRIMM), CoSpec::None, CoSpec::None],
        send: SendRule::Ground,
        sky: false,
        weather: Weather::Clear,
        fog: true,
    });
    m.intro = txt("m13_pre");
    m.victory = txt("m13_post");
    m.after = crate::bh2_text::chain(&["m13_map", "m13_warroom", "m13_staff"]);
    m.triggers.push(on_day(6, None, vec![Action::Scene(txt("m13_day6"))]));
    m.triggers.push(Trigger::new(When::TurnStart, Cond::Custom(second_front_won), vec![Action::Scene(txt("m13_front2_post"))]));
    m.triggers.push(Trigger::new(When::TurnStart, Cond::Custom(second_front_lost), vec![Action::Scene(txt("m13_front2_lost"))]));
    // Kanbei's guard holds the strait bridge to the last: the scene plays when his army is down to a third
    m.triggers.push(Trigger::new(When::AfterAction, Cond::ArmyUnitsAtMost { army: 2, n: share("bh2_13", 2, 1, 3) }, vec![Action::Scene(txt("m13_stand"))]));
    m.flag = flag(13);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_12"]);
    m
}

/// M16 Cold Wire: Jugger (forced) against Grit on Blue Moon's snowbound border; the pipe walls' seams are the short cuts. A straight battle.
fn bh2_16() -> MissionDef {
    let mut m = MissionDef::new("bh2_16", "Cold Wire");
    m.objective = "Cut the Allied wire: break the walls' seams and take Grit's HQ.";
    m.map = MapSrc::Built("bh2_16");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::JUGGER)).funds(10000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::GRIT)).funds(16000),
    ];
    m.units = deployment("bh2_16");
    m.look = 1; // the Snow look
    m.weather = Weather::Snow;
    m.rank_days = 16;
    m.intro = txt("m16_pre");
    m.victory = txt("m16_post");
    m.after = crate::bh2_text::chain(&["m16_map"]);
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m16_day5"))]));
    m.triggers.push(on_day(9, None, vec![Action::Scene(txt("m16_day9"))]));
    // "Seam six: cut": the wire is read when Black Hole holds the Com Tower between the walls
    m.triggers.push(Trigger::new(When::AfterAction, Cond::OwnerAt { x: 20, y: 10, army: 1 }, vec![Action::Scene(txt("m16_wire"))]));
    m.flag = flag(16);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_15"]);
    m
}

/// M17 Lot 42: Lash (forced) with a free tag partner against one Blue Moon army under Sasha + Colin, on the lab island; Black Hole's Black Obelisk (snow, fog).
fn bh2_17() -> MissionDef {
    let mut m = MissionDef::new("bh2_17", "Lot 42");
    m.objective = "Take the lab island's HQ; the Obelisk stands with you.";
    m.map = MapSrc::Built("bh2_17");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPartner(co::LASH)).funds(10000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Pair(co::SASHA, co::COLIN)).funds(20000),
    ];
    m.units = deployment("bh2_17");
    m.look = 1;
    m.fog = true;
    m.rank_days = 18;
    m.intro = txt("m17_pre");
    m.victory = txt("m17_post");
    m.after = crate::bh2_text::chain(&["m17_map"]);
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m17_day5"))]));
    m.triggers.push(on_day(8, None, vec![Action::Scene(txt("m17_day8"))]));
    m.flag = flag(17);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_16"]);
    m
}

/// M18 Whiteout Harbour: Flak (forced) against Olaf, a naval and ground mix in the heaviest snow (snow weather and fog).
fn bh2_18() -> MissionDef {
    let mut m = MissionDef::new("bh2_18", "Whiteout Harbour");
    m.objective = "Land on Olaf's coast and take his HQ.";
    m.map = MapSrc::Built("bh2_18");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::FLAK)).funds(10000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF)).funds(18000),
    ];
    m.units = deployment("bh2_18");
    m.look = 1;
    m.weather = Weather::Snow;
    m.fog = true; // the whiteout: snow and fog together (M17 is fog alone, M16 snow alone)
    m.rank_days = 18;
    m.intro = txt("m18_pre");
    m.victory = txt("m18_post");
    m.after = crate::bh2_text::chain(&["m18_map"]);
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m18_day5"))]));
    m.triggers.push(on_day(8, None, vec![Action::Scene(txt("m18_day8"))]));
    m.flag = flag(18);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_17"]);
    m
}

/// Factory table of M19 (day, the three doors' slots; 0 none): heavier than M3's, with a Neotank slot and the Anti-Air slots for the days Blue Moon's Fighters come.
const F14: [(u8, [u8; 3]); 14] = [
    (2, [0, unit::TANK, 0]),
    (3, [unit::INFANTRY, 0, unit::INFANTRY]),
    (4, [0, unit::MD_TANK, 0]),
    (5, [unit::TANK, 0, unit::TANK]),
    (6, [0, unit::ARTILLERY, 0]),
    (7, [unit::MECH, 0, unit::MECH]),
    (8, [0, unit::MD_TANK, unit::ANTI_AIR]),
    (9, [unit::TANK, 0, unit::TANK]),
    (10, [unit::INFANTRY, unit::MD_TANK, unit::INFANTRY]),
    (11, [0, unit::NEOTANK, 0]),
    (12, [unit::MECH, 0, unit::ROCKETS]),
    (13, [0, unit::MD_TANK, 0]),
    (14, [unit::TANK, 0, unit::TANK]),
    (16, [unit::INFANTRY, unit::NEOTANK, unit::ANTI_AIR]),
];

/// M19 Thirty Years of Iron: a free pair with Black Hole's Black Factory (the foundry) against one Blue Moon army under Olaf + Grit; Mount Cinder erupts (Wasteland look). Ends Act III.
fn bh2_19() -> MissionDef {
    let mut m = MissionDef::new("bh2_19", "Thirty Years of Iron");
    m.objective = "Hold the foundry and take the Blue Moon HQ.";
    m.map = MapSrc::Built("bh2_19");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(12000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Pair(co::OLAF, co::GRIT)).funds(26000),
    ];
    m.units = deployment("bh2_19");
    m.look = 3; // the Wasteland look
    m.rank_days = 20;
    m.factory = F14.to_vec();
    // Mount Cinder: from day 3 it erupts every day on 3 of the cells of the ring road round it (5 HP, any army's units, never below 1).
    m.volcano = Some(VolcanoDef::new(3, 1, 5, &ring(20, 10, 27, 17)).per_eruption(3));
    m.intro = txt("m19_pre");
    m.victory = txt("m19_post");
    m.after = crate::bh2_text::chain(&["m19_map", "m19_warroom", "m19_staff"]);
    m.triggers.push(on_day(6, None, vec![Action::Scene(txt("m19_day6"))]));
    m.flag = flag(19);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_18"]);
    m
}

/// M20 Every Colour: a free pair against one Orange Star army under Max + Sami on the border plains (normal look, clear).
fn bh2_20() -> MissionDef {
    let mut m = MissionDef::new("bh2_20", "Every Colour");
    m.objective = "Cross both rivers and take the Orange Star HQ.";
    m.map = MapSrc::Built("bh2_20");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(12000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::MAX, co::SAMI)).funds(20000),
    ];
    m.units = deployment("bh2_20");
    m.rank_days = 16;
    m.intro = txt("m20_pre");
    m.victory = txt("m20_post");
    m.after = crate::bh2_text::chain(&["m20_map"]);
    m.triggers.push(on_day(4, None, vec![Action::Scene(txt("m20_day4"))]));
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m20_split"))]));
    m.flag = flag(20);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_19"]);
    m
}

/// M21 The East Tower: a free pick against Andy + Rachel, a castle assault in the rain; no scripted escape.
fn bh2_21() -> MissionDef {
    let mut m = MissionDef::new("bh2_21", "The East Tower");
    m.objective = "Break the castle wall's gates and take the keep's HQ.";
    m.map = MapSrc::Built("bh2_21");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(10000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::ANDY, co::RACHEL)).funds(20000),
    ];
    m.units = deployment("bh2_21");
    m.weather = Weather::Rain;
    m.rank_days = 18;
    m.intro = txt("m21_pre");
    m.victory = txt("m21_post");
    m.after = crate::bh2_text::chain(&["m21_map"]);
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m21_day5"))]));
    // Andy's commandos free Nell when Black Hole takes the East Tower
    m.triggers.push(Trigger::new(When::AfterAction, Cond::OwnerAt { x: 21, y: 6, army: 1 }, vec![Action::Scene(txt("m21_freed"))]));
    m.flag = flag(21);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_20"]);
    m
}

/// M22 Echo, Again: Clone Andy (forced) against Andy among the Lab 7 ruins (Wasteland look, fog).
fn bh2_22() -> MissionDef {
    let mut m = MissionDef::new("bh2_22", "Echo, Again");
    m.objective = "Cross the river and defeat Andy.";
    m.map = MapSrc::Built("bh2_22");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::CLONE_ANDY)).funds(10000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::ANDY)).funds(10000),
    ];
    m.units = deployment("bh2_22");
    m.look = 3;
    m.fog = true;
    m.rank_days = 16;
    m.intro = txt("m22_pre");
    m.victory = txt("m22_post");
    m.after = crate::bh2_text::chain(&["m22_map"]);
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m22_day5"))]));
    // the archive (the ruins' Com Tower) is reached
    m.triggers.push(Trigger::new(When::AfterAction, Cond::OwnerAt { x: 17, y: 9, army: 1 }, vec![Action::Scene(txt("m22_binder"))]));
    m.flag = flag(22);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_21"]);
    m
}

/// M23's crate tile (the yard, `mark_crate`) and the reserve's Neotanks (`mark_neo*`).
const M23_CRATE: (u8, u8) = (9, 16);
const M23_NEO: [(u8, u8); 4] = [(5, 15), (7, 19), (11, 15), (11, 19)];

/// M23 The Door Is Open: Asuka + Crumb defend the depot; when Crumb (the named APC) reaches the crate tile the reserve's Neotanks appear; Crumb lost is the mission lost.
fn bh2_23() -> MissionDef {
    let mut m = MissionDef::new("bh2_23", "The Door Is Open");
    m.objective = "Defend the depot until Crumb reaches the crate.";
    m.map = MapSrc::Built("bh2_23");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(crate::co_new::ASUKA, co::CRUMB)).funds(10000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::HACHI, co::JAKE)).funds(18000),
    ];
    m.units = deployment("bh2_23");
    m.rank_days = 16;
    m.triggers = vec![
        // (once: the scenes play, the reserve wakes)
        Trigger::new(
            When::AfterAction,
            Cond::UnitAt {
                name: "crumb",
                x: M23_CRATE.0,
                y: M23_CRATE.1,
            },
            vec![
                Action::Scene(crate::bh2_text::chain(&["m23_crate", "m23_journal", "m23_reserve"])),
                Action::Spawn(wave(1, unit::NEOTANK, &M23_NEO)),
            ],
        ),
        after(Cond::UnitGone("crumb"), vec![Action::Lose]),
    ];
    m.intro = txt("m23_pre");
    m.victory = txt("m23_post");
    m.after = crate::bh2_text::chain(&["m23_map"]);
    m.triggers.push(on_day(2, None, vec![Action::Scene(txt("m23_day2"))]));
    m.triggers.push(on_day(4, None, vec![Action::Scene(txt("m23_day4"))]));
    m.flag = flag(23);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_22"]);
    m
}

/// M24 Skyfall: Adder (forced) against Rachel + Jake on the desert coast; the air war against the Allies' Anti-Air belt (desert look, clear).
fn bh2_24() -> MissionDef {
    let mut m = MissionDef::new("bh2_24", "Skyfall");
    m.objective = "Win the air war and take the Allied HQ.";
    m.map = MapSrc::Built("bh2_24");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::ADDER)).funds(14000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::RACHEL, co::JAKE)).funds(20000),
    ];
    m.units = deployment("bh2_24");
    m.look = 2; // the Desert look
    m.rank_days = 18;
    m.intro = txt("m24_pre");
    m.victory = txt("m24_post");
    m.after = crate::bh2_text::chain(&["m24_map"]);
    m.triggers.push(on_day(3, None, vec![Action::Scene(txt("m24_day3"))]));
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m24_day5"))]));
    m.flag = flag(24);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_23"]);
    m
}

/// M25 The Rail East: two fronts. Front 1, a free pick against Andy on the rail corridor (fog); front 2, a free pick against Hachi in the rail yard in a sandstorm. Ends Act IV.
fn bh2_25() -> MissionDef {
    let mut m = MissionDef::new("bh2_25", "The Rail East");
    m.objective = "Take Andy's terminus; the second front takes Hachi's yard.";
    m.map = MapSrc::Built("bh2_25");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(10000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::ANDY)).funds(18000),
    ];
    m.units = deployment("bh2_25");
    m.fog = true; // (M23 and M25 are both the normal look and clear: fog tells them apart)
    m.rank_days = 18;
    m.front2 = Some(FrontDef {
        map: MapSrc::Built("bh2_25b"),
        props: Vec::new(),
        structures: Vec::new(),
        units: crate::bh_ai::built_units("bh2_25b"),
        cos: [CoSpec::Pick, CoSpec::Fixed(co::HACHI), CoSpec::None, CoSpec::None],
        send: SendRule::Ground,
        sky: false,
        weather: Weather::Sandstorm,
        fog: true,
    });
    m.intro = txt("m25_pre");
    m.victory = txt("m25_post");
    m.after = crate::bh2_text::chain(&["m25_map", "m25_warroom", "m25_staff"]);
    m.triggers.push(on_day(6, None, vec![Action::Scene(txt("m25_day6"))]));
    m.triggers.push(Trigger::new(When::TurnStart, Cond::Custom(second_front_won), vec![Action::Scene(txt("m25_front2_post"))]));
    m.triggers.push(Trigger::new(When::TurnStart, Cond::Custom(second_front_lost), vec![Action::Scene(txt("m25_front2_lost"))]));
    m.flag = flag(25);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_24"]);
    m
}

/// M26 The Second Folder: Asuka + Hawke (forced pair) against Max + Sami at Black Hole's eastern HQ, between two frozen lakes (snow look, clear).
fn bh2_26() -> MissionDef {
    let mut m = MissionDef::new("bh2_26", "The Second Folder");
    m.objective = "Hold the isthmus and take the Orange Star HQ.";
    m.map = MapSrc::Built("bh2_26");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(crate::co_new::ASUKA, co::HAWKE)).funds(14000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::MAX, co::SAMI)).funds(22000),
    ];
    m.units = deployment("bh2_26");
    m.look = 1; // the Snow look
    m.rank_days = 18;
    m.intro = txt("m26_pre");
    m.victory = txt("m26_post");
    m.after = crate::bh2_text::chain(&["m26_map"]);
    m.triggers.push(on_day(2, None, vec![Action::Scene(txt("m26_day2"))]));
    m.triggers.push(on_day(4, None, vec![Action::Scene(txt("m26_day4"))]));
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m26_folders"))]));
    m.flag = flag(26);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_25"]);
    m
}

/// Factory table of M27 (day, the three doors' slots; 0 none): the foundry builds against a fortress, Anti-Air only when the Allied Fighters show.
const F22: [(u8, [u8; 3]); 14] = [
    (2, [0, unit::MD_TANK, 0]),
    (3, [unit::INFANTRY, 0, unit::INFANTRY]),
    (4, [0, unit::TANK, 0]),
    (5, [unit::ARTILLERY, 0, unit::TANK]),
    (6, [0, unit::MD_TANK, 0]),
    (7, [unit::MECH, 0, unit::ROCKETS]),
    (8, [0, unit::MD_TANK, unit::ANTI_AIR]),
    (9, [unit::TANK, 0, unit::ARTILLERY]),
    (10, [unit::INFANTRY, unit::NEOTANK, unit::INFANTRY]),
    (11, [0, unit::MD_TANK, 0]),
    (12, [unit::MECH, 0, unit::ROCKETS]),
    (13, [0, unit::NEOTANK, 0]),
    (14, [unit::TANK, 0, unit::ANTI_AIR]),
    (16, [unit::INFANTRY, unit::MD_TANK, unit::ARTILLERY]),
];

/// Black Hole's (army 1's) funds, from the players table.
fn funds_of_player(core: &Core) -> u32 {
    let p = core.raw_read_32(0x0849_9598, -1) + 0x3C;
    core.raw_read_32(p, -1)
}

/// M27: day 6 or later and the vault (Black Hole's funds) is under 500.
fn vault_empty(core: &mut Core) -> bool {
    day(core) >= 6 && funds_of_player(core) < 500
}

/// M27 Von Bolt's Note: Von Bolt (forced) + a free partner against Jess + Colin at the Orange Star sea fortress; the player's Black Factory and Deathray (rain).
fn bh2_27() -> MissionDef {
    let mut m = MissionDef::new("bh2_27", "Von Bolt's Note");
    m.objective = "Cross the strait and take the fortress's HQ; the Deathray covers the east.";
    m.map = MapSrc::Built("bh2_27");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPartner(co::VON_BOLT)).funds(14000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::JESS, co::COLIN)).funds(26000),
    ];
    m.units = deployment("bh2_27");
    m.weather = Weather::Rain;
    m.rank_days = 22;
    m.factory = F22.to_vec();
    m.intro = txt("m27_pre");
    m.victory = txt("m27_post");
    m.after = crate::bh2_text::chain(&["m27_map"]);
    m.triggers.push(on_day(2, None, vec![Action::Scene(txt("m27_day2"))]));
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m27_day5"))]));
    // "The vault is empty": from day 6 on, when Black Hole's funds are spent, Von Bolt opens Sonja's note and sells Jess the truth; Jess retreats (the win)
    m.triggers.push(Trigger::new(
        When::AfterAction,
        Cond::Custom(vault_empty),
        vec![Action::Scene(crate::bh2_text::chain(&["m27_vault_empty", "m27_sale"])), Action::Win],
    ));
    m.flag = flag(27);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_26"]);
    m
}

/// M28's reinforcement cells (the map's `mark_wave*` notes): waves of three on days 2, 4, 6 and 8.
const M28_WAVES: [(u8, u8); 12] = [(42, 5), (42, 9), (42, 13), (42, 17), (41, 7), (41, 11), (41, 15), (41, 19), (42, 3), (42, 21), (41, 4), (41, 22)];

/// A reinforcement trigger on a day: the army's units appear on the cells.
fn day_wave(day: u16, units: Vec<UnitDef>) -> Trigger {
    Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: day }, vec![Action::Spawn(units)]).repeating()
}

/// M28 Where the Map Ends: Asuka + Crumb (forced pair) hold the Obelisk against Drake + Grit's strike force for nine days (wasteland, sandstorm).
fn bh2_28() -> MissionDef {
    let mut m = MissionDef::new("bh2_28", "Where the Map Ends");
    m.objective = "Hold the Obelisk until day 10. The waves come over the bridges and by air.";
    m.map = MapSrc::Built("bh2_28");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(crate::co_new::ASUKA, co::CRUMB)).funds(12000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Pair(co::DRAKE, co::GRIT)).funds(18000),
    ];
    m.units = deployment("bh2_28");
    m.look = 3; // the Wasteland look
    m.weather = Weather::Sandstorm; // the storm
    m.rank_days = 10;
    let w = |k: usize, kind: u8| UnitDef::new(2, kind, M28_WAVES[k].0, M28_WAVES[k].1).attack();
    m.triggers = vec![
        day_wave(2, vec![w(0, unit::NEOTANK), w(1, unit::MD_TANK), w(2, unit::B_COPTER)]),
        day_wave(4, vec![w(3, unit::NEOTANK), w(4, unit::ROCKETS), w(5, unit::FIGHTER)]),
        day_wave(6, vec![w(6, unit::MD_TANK), w(7, unit::BOMBER), w(8, unit::NEOTANK)]),
        day_wave(8, vec![w(9, unit::NEOTANK), w(10, unit::STEALTH), w(11, unit::MEGATANK)]),
        // nine days held: the storm passes
        Trigger::new(When::TurnStart, Cond::DayAtLeast(10), vec![Action::Win]),
    ];
    m.intro = txt("m28_pre");
    m.victory = txt("m28_post");
    m.after = crate::bh2_text::chain(&["m28_map"]);
    m.triggers.push(on_day(3, None, vec![Action::Scene(txt("m28_day3"))]));
    m.triggers.push(on_day(6, None, vec![Action::Scene(txt("m28_day6"))]));
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m28_door"))]));
    m.flag = flag(28);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_27"]);
    m
}

/// M29 The Gate of Colours: a free pair against Andy and Max + Sami, two allied armies (three armies), on the desert delta.
fn bh2_29() -> MissionDef {
    let mut m = MissionDef::new("bh2_29", "The Gate of Colours");
    m.objective = "Cross the three rivers and take both Allied HQs. The island in the south (four silos, an airport) falls to a Lander.";
    m.map = MapSrc::Built("bh2_29");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(14000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::ANDY)).team(2).funds(16000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Pair(co::MAX, co::SAMI)).team(2).funds(16000),
    ];
    m.units = deployment("bh2_29");
    m.look = 2; // the Desert look
    m.rank_days = 22;
    m.intro = txt("m29_pre");
    m.victory = txt("m29_post");
    m.after = crate::bh2_text::chain(&["m29_map", "m29_warroom"]);
    m.triggers.push(on_day(6, None, vec![Action::Scene(txt("m29_day6"))]));
    m.flag = flag(29);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_28"]);
    m
}

/// M30's four HQs (the map's tiles `1`..`4`): Nell's at (8,8) is the first line; the others are held until the last. The player (Black Hole) is the fifth army.
const M30_NELL: (u8, u8) = (8, 8);
const M30_OLAF: (u8, u8) = (24, 6);
const M30_KANBEI: (u8, u8) = (39, 6);
const M30_EAGLE: (u8, u8) = (38, 20);
/// Aria's CO id: the new Orange Star commander of part two (CO 93, `crate::aria`).
const ARIA_CO: u8 = crate::co_new::ARIA;

/// Each nation's troops land when the stage before it falls (cells in its zone, free of start units): (kind, cell). The nation's army is present from the start
/// (a few units holding round its HQ) and owns nothing but the HQ, so it cannot build until then.
const OLAF_WAVE: [(u8, (u8, u8)); 21] = [
    (unit::MD_TANK, (24, 9)),
    (unit::MD_TANK, (17, 6)),
    (unit::MD_TANK, (18, 10)),
    (unit::MD_TANK, (16, 5)),
    (unit::NEOTANK, (30, 4)),
    (unit::NEOTANK, (23, 7)),
    (unit::NEOTANK, (17, 3)),
    (unit::MEGATANK, (19, 1)),
    (unit::ARTILLERY, (20, 12)),
    (unit::ARTILLERY, (22, 13)),
    (unit::ARTILLERY, (17, 1)),
    (unit::ROCKETS, (16, 4)),
    (unit::ROCKETS, (20, 10)),
    (unit::ROCKETS, (16, 11)),
    (unit::MISSILES, (26, 13)),
    (unit::INFANTRY, (28, 3)),
    (unit::INFANTRY, (21, 13)),
    (unit::INFANTRY, (18, 13)),
    (unit::MECH, (22, 2)),
    (unit::CRUISER, (19, 4)),
    (unit::SUB, (25, 2)),
];
const KANBEI_WAVE: [(u8, (u8, u8)); 16] = [
    (unit::NEOTANK, (38, 6)),
    (unit::NEOTANK, (39, 1)),
    (unit::NEOTANK, (33, 11)),
    (unit::NEOTANK, (43, 8)),
    (unit::MEGATANK, (39, 9)),
    (unit::MEGATANK, (36, 5)),
    (unit::MEGATANK, (44, 10)),
    (unit::MEGATANK, (38, 5)),
    (unit::MD_TANK, (39, 3)),
    (unit::MD_TANK, (37, 11)),
    (unit::MD_TANK, (44, 9)),
    (unit::ARTILLERY, (37, 3)),
    (unit::ARTILLERY, (32, 6)),
    (unit::ROCKETS, (32, 8)),
    (unit::ROCKETS, (45, 13)),
    (unit::MISSILES, (42, 3)),
];
const EAGLE_WAVE: [(u8, (u8, u8)); 16] = [
    (unit::FIGHTER, (44, 20)),
    (unit::FIGHTER, (40, 23)),
    (unit::FIGHTER, (43, 17)),
    (unit::FIGHTER, (44, 23)),
    (unit::FIGHTER, (42, 21)),
    (unit::FIGHTER, (33, 23)),
    (unit::BOMBER, (44, 21)),
    (unit::BOMBER, (35, 23)),
    (unit::BOMBER, (33, 24)),
    (unit::BOMBER, (38, 18)),
    (unit::B_COPTER, (40, 21)),
    (unit::B_COPTER, (38, 15)),
    (unit::STEALTH, (33, 15)),
    (unit::STEALTH, (38, 21)),
    (unit::STEALTH, (45, 14)),
    (unit::STEALTH, (42, 20)),
];

fn stage(army: u8, list: &[(u8, (u8, u8))]) -> Action {
    Action::Spawn(list.iter().map(|&(k, (x, y))| UnitDef::new(army, k, x, y).attack()).collect())
}

/// The player (the fifth army) holds this HQ.
fn owned(c: (u8, u8)) -> Cond {
    Cond::OwnerAt { x: c.0, y: c.1, army: 5 }
}

/// The next nation wakes: when the player holds this stage's HQ (and every line before it has fallen: a stage's HQ taken out of order moves nothing), the nation `army`'s troops land and
/// it gets its funds. The fallen nations stay on the map and fight on.
fn wake(hq: (u8, u8), before: &[(u8, u8)], army: u8, funds: i32, wave: &[(u8, (u8, u8))]) -> Trigger {
    let mut all = vec![owned(hq)];
    all.extend(before.iter().map(|&c| owned(c)));
    Trigger::new(When::AfterAction, Cond::All(all), vec![Action::AddFunds { army, funds }, stage(army, wave)])
}

/// M30 The Last Accord, part one: the final mission's first map. Asuka + a free partner (Black Hole, the fifth army) against the four nations of the Accord, each an army of its own colour: Nell's Orange Star
/// (army 1), then Olaf's Blue Moon (2), Kanbei's Yellow Comet (3) and Eagle's Green Earth (4), allied. Each later nation is present but dormant (a few holding units round its HQ, no property but the HQ) until
/// the HQ before it falls; Eagle's HQ ends part one (a scene, then the win) and part two (Aria's citadel, `bh2_31`) follows. No time limit, no Black Hole inventions on the Allied side.
fn bh2_30() -> MissionDef {
    let mut m = MissionDef::new("bh2_30", "The Last Accord");
    m.objective = "Break Nell's line, then Olaf's, Kanbei's and Eagle's.";
    m.map = MapSrc::Built("bh2_30");
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::NELL)).team(1).funds(40000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF)).team(1).funds(0),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KANBEI)).team(1).funds(0),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::EAGLE)).team(1).funds(0),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(30000),
    ];
    m.units = crate::bh_ai::orders(crate::bh_ai::built_units("bh2_30"), 5, crate::bh_ai::ATTACK, |u| u.ai == 1);
    m.rank_days = 40;
    m.held_hq = Some(M30_NELL);
    m.held_more = vec![M30_OLAF, M30_KANBEI, M30_EAGLE];
    m.triggers = vec![
        wake(M30_NELL, &[], 2, 90000, &OLAF_WAVE),
        wake(M30_OLAF, &[M30_NELL], 3, 90000, &KANBEI_WAVE),
        wake(M30_KANBEI, &[M30_NELL, M30_OLAF], 4, 90000, &EAGLE_WAVE),
        // Eagle's HQ is the last of part one: a scene, then the win (part two follows)
        after(
            Cond::All(vec![owned(M30_EAGLE), owned(M30_KANBEI), owned(M30_OLAF), owned(M30_NELL)]),
            vec![
                Action::Scene(Scene::new(vec![
                    Line::say(co::EAGLE, "The Accord's last wing is down. We held the sky as long as we could."),
                    Line::say(ARIA_CO, "Then it is mine to hold. Let them come to the citadel."),
                ])),
                Action::Win,
            ],
        ),
    ];
    // TODO(map-switch merge): this gauntlet becomes the first stage of M31 (m31_pre, m31_day5, m31_takeover_*, m31_switch, m31_stage2); M30 is the new "The Orange Line" (m30_*)
    m.flag = flag(30);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_29"]);
    m
}

/// M30 part two, The Last Citadel: the final mission's second map. Aria (Orange Star), a revived army of brand-new full-strength units, holds a fortress on a plateau of high ground; Asuka + a free partner
/// come over the Aisne's bridges and up the passes. Capturing her HQ or routing her army wins the campaign.
fn bh2_31() -> MissionDef {
    let mut m = MissionDef::new("bh2_31", "The Last Citadel");
    m.objective = "Cross the Aisne, climb the passes and take Aria's HQ.";
    m.map = MapSrc::Built("bh2_31");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPartner(crate::co_new::ASUKA)).funds(30000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(ARIA_CO)).funds(90000),
    ];
    m.units = deployment("bh2_31");
    m.look = 1; // the Snow look: the citadel stands on high ground (and M31 is no look twin of M30)
    m.rank_days = 40;
    m.intro = Scene::new(vec![
        Line::say(ARIA_CO, "Every unit here is new, and every one is mine. The Accord does not end at the lakes."),
        Line::say(crate::co_new::ASUKA, "Then we take it from the top, one pass at a time."),
    ])
    .with_song(Some(crate::campaign_music::Track::Own(ARIA_CO))); // (Aria's song, until the finale's m31_pre is wired)
    m.victory = txt("m31_post");
    // the epilogue on the world map after the last win; the credits follow (`def`)
    m.after = crate::bh2_text::chain(&["epilogue", "epilogue_toasts"]);
    // (the days 6, 9 and 12 belong to the finale's second stage: TODO_SCENES)
    m.flag = flag(31);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_30"]);
    m
}

/// M32's landing cells (the map's `mark_cav`, `mark_siege` and `mark_fleet` notes).
const M32_CAV: [(u8, u8); 4] = [(12, 4), (15, 6), (18, 8), (20, 11)];
const M32_SIEGE: [(u8, u8); 4] = [(37, 24), (35, 25), (38, 22), (33, 26)];
const M32_FLEET: [(u8, u8); 5] = [(22, 4), (25, 6), (27, 9), (30, 11), (20, 2)];

/// M32 Through the Door (secret): a free pair against Klaus + Aurelia, the Emerald Sun legion, on Black Hole's own island; Cassius's cavalry on day 3, Aurelia's siege on day 5, Livia's fleet on day 7. (The Emerald Sun skin on the enemy army is a hook: see docs/dev/bh2-maps.md.)
fn bh2_32() -> MissionDef {
    let mut m = MissionDef::new("bh2_32", "Through the Door");
    m.objective = "Hold the island against the legion's three waves and take Klaus's HQ.";
    m.map = MapSrc::Built("bh2_32");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(14000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Pair(crate::es_co::KLAUS, crate::es_co::AURELIA)).funds(22000),
    ];
    m.units = deployment("bh2_32");
    m.skin = Some((2, 0)); // the legion wears the Emerald Sun skin (skin 0), on the colour the mission gives army 2
    m.look = 2; // the Desert look: Black Hole's own sunburnt island (its sea stays water; and M32 is no look twin of M30)
    m.rank_days = 20;
    let at = |kind: u8, c: (u8, u8)| UnitDef::new(2, kind, c.0, c.1).attack();
    m.triggers = vec![
        // Cassius's cavalry
        day_wave(3, vec![at(unit::RECON, M32_CAV[0]), at(unit::TANK, M32_CAV[1]), at(unit::RECON, M32_CAV[2]), at(unit::TANK, M32_CAV[3])]),
        // Aurelia's siege engines
        day_wave(5, vec![at(unit::ARTILLERY, M32_SIEGE[0]), at(unit::ROCKETS, M32_SIEGE[1]), at(unit::MD_TANK, M32_SIEGE[2]), at(unit::ARTILLERY, M32_SIEGE[3])]),
        // Livia's fleet
        day_wave(7, vec![at(unit::BATTLESHIP, M32_FLEET[0]), at(unit::CRUISER, M32_FLEET[1]), at(unit::CRUISER, M32_FLEET[2]), at(unit::SUB, M32_FLEET[3]), at(unit::LANDER, M32_FLEET[4])]),
    ];
    m.intro = txt("m32_pre");
    m.victory = txt("m32_post");
    m.after = txt("m32_epilogue");
    m.triggers.push(on_day(3, None, vec![Action::Scene(txt("m32_day3"))]));
    m.triggers.push(on_day(5, None, vec![Action::Scene(txt("m32_day5"))]));
    m.triggers.push(on_day(7, None, vec![Action::Scene(txt("m32_day7"))]));
    m.flag = flag(32);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_29"]); // the secret mission opens after M29
    m
}

/// The campaign.
pub fn def() -> CampaignDef {
    let mut missions = vec![
        bh2_01(),
        bh2_02(),
        bh2_03(),
        bh2_04(),
        bh2_05(),
        bh2_06(),
        bh2_07(),
        bh2_08(),
        bh2_09(),
        bh2_10(),
        bh2_11(),
        bh2_12(),
        bh2_13(),
        bh2_14(),
        bh2_15(),
        bh2_16(),
        bh2_17(),
        bh2_18(),
        bh2_19(),
        bh2_20(),
        bh2_21(),
        bh2_22(),
        bh2_23(),
        bh2_24(),
        bh2_25(),
        bh2_26(),
        bh2_27(),
        bh2_28(),
        bh2_29(),
        bh2_30(),
        bh2_31(),
        bh2_32(),
    ];
    missions.iter_mut().for_each(crate::bh_ai::spawn_orders);
    CampaignDef {
        source: SOURCE,
        roster: ROSTER.to_vec(),
        prologue: crate::bh2_text::pages("prologue"),
        prologue_song: crate::bh2_text::song("prologue"),
        prologue_scenes: vec![txt("prologue_castle"), txt("prologue_allies"), txt("prologue_turn")],
        credits: crate::bh2_text::credits(),
        missions,
        final_mission: "bh2_31",
        bonds: Vec::new(),
        extra_bonds: 0,
        secret_mission: "bh2_32",
    }
}

/// The campaign's source `load`.
pub fn load(core: &Core) -> Option<Model> {
    match compile(core, &def()) {
        Ok(m) => Some(m),
        Err(e) => {
            eprintln!("BH2 Campaign: {e}");
            None
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn at<'a>(d: &'a CampaignDef, key: &str) -> &'a MissionDef {
        d.missions.iter().find(|m| m.key == key).unwrap_or_else(|| panic!("{key}"))
    }

    #[test]
    fn the_campaign_is_thirty_one_missions_and_a_secret_in_the_plan_order() {
        let d = def();
        assert_eq!(d.missions.len(), 32);
        let keys: Vec<String> = d.missions.iter().map(|m| m.key.to_string()).collect();
        let want: Vec<String> = (1..=32).map(|n| format!("bh2_{n:02}")).collect();
        assert_eq!(keys, want, "mission n is bh2_NN");
        assert_eq!(d.final_mission, "bh2_31");
        assert_eq!(d.secret_mission, "bh2_32");
    }

    #[test]
    fn act_one_has_eight_missions_two_fronts_for_m4_and_three_armies_in_m5() {
        let d = def();
        assert!(at(&d, "bh2_04").front2.as_ref().is_some_and(|f| f.sky));
        let m5 = at(&d, "bh2_05");
        assert!(m5.held_hq.is_none() && m5.held_more.is_empty(), "M5 has no held or second HQ");
        assert_eq!(m5.armies.len(), 3);
        // M6: the Com Tower network and Eagle's takeover (one trigger); M7 a harbour assault; M8 Koal's fuel line
        assert_eq!(at(&d, "bh2_06").triggers.len(), 2, "the takeover and the day-5 scene");
        assert_eq!(at(&d, "bh2_07").look, 2);
        assert!(matches!(at(&d, "bh2_08").weather, Weather::Sandstorm));
    }

    #[test]
    fn act_two_has_five_missions_and_a_second_front_for_m13() {
        let d = def();
        assert!(d.missions[8..13].iter().map(|m| m.key).eq(["bh2_09", "bh2_10", "bh2_11", "bh2_12", "bh2_13"]));
        let m13 = at(&d, "bh2_13");
        let f = m13.front2.as_ref().expect("M13's second front");
        assert!(!f.sky && matches!(f.map, MapSrc::Built("bh2_13b")));
        assert_eq!(m13.look, 3);
        // M12's scripted fight: the airlift at half strength, the surrender; M12 has no time limit
        assert_eq!(at(&d, "bh2_12").triggers.len(), 2);
        assert_eq!(at(&d, "bh2_12").day_limit, 0);
    }

    #[test]
    fn act_three_has_the_border_the_pass_and_the_factory_in_m19() {
        let d = def();
        assert_eq!(at(&d, "bh2_14").armies.len(), 3);
        assert_eq!(at(&d, "bh2_15").look, 1);
        assert!(d.missions[15..19].iter().map(|m| m.key).eq(["bh2_16", "bh2_17", "bh2_18", "bh2_19"]));
        let m19 = at(&d, "bh2_19");
        assert!(m19.factory.len() == 14 && m19.volcano.is_some());
        assert_eq!(m19.look, 3);
        assert!(d.missions[15..18].iter().all(|m| m.look == 1), "M16 to M18 are the snow look");
    }

    #[test]
    fn act_four_has_six_missions_a_scripted_depot_and_a_second_front_for_m25() {
        let d = def();
        assert!(d.missions[19..25].iter().map(|m| m.key).eq(["bh2_20", "bh2_21", "bh2_22", "bh2_23", "bh2_24", "bh2_25"]));
        assert_eq!(at(&d, "bh2_22").look, 3);
        assert_eq!(at(&d, "bh2_24").look, 2);
        let m25 = at(&d, "bh2_25");
        let f = m25.front2.as_ref().expect("M25's second front");
        assert!(!f.sky && matches!(f.weather, Weather::Sandstorm) && matches!(f.map, MapSrc::Built("bh2_25b")));
        assert_eq!(at(&d, "bh2_23").triggers.len(), 4, "the crate scenes and reserve, the loss, the day-2 and day-4 scenes");
    }

    /// M23: the crate tile and the Neotank cells are the map's `mark_` notes' cells, free of start units, on ground; Crumb is the named APC of Black Hole.
    #[test]
    fn m18_crate_and_reserve_cells_are_free_and_crumb_is_named() {
        let m = built_map("bh2_23").expect("bh2_23");
        for &(x, y) in std::iter::once(&M23_CRATE).chain(M23_NEO.iter()) {
            assert!(!m.units.iter().any(|u| (u.x, u.y) == (x, y)), "a unit starts on ({x}, {y})");
        }
        let c = m.units.iter().find(|u| u.name == "crumb").expect("crumb");
        assert_eq!((c.army, c.kind), (1, 7), "Crumb is Black Hole's APC");
        assert!(c.x > M23_CRATE.0 + 10, "Crumb starts by the quay, far from the crate");
    }

    #[test]
    fn act_five_has_the_gauntlet_the_waves_and_the_secret() {
        let d = def();
        // M27: the player's factory; M28: waves and the day-10 win, no day limit; M29: three armies; M30: four held HQs and four triggers (three wakes and the win), no day limit
        assert!(at(&d, "bh2_27").factory.len() == 14);
        assert_eq!(at(&d, "bh2_28").triggers.len(), 8, "four waves, the day-10 win and the day-3, 5 and 6 scenes");
        assert_eq!(at(&d, "bh2_28").day_limit, 0);
        assert_eq!(at(&d, "bh2_29").armies.len(), 3);
        let m30 = at(&d, "bh2_30");
        assert!(m30.held_hq.is_some() && m30.held_more.len() == 3);
        assert_eq!(m30.triggers.len(), 4, "three wakes and the win");
        assert_eq!(m30.armies.len(), 5);
        assert_eq!(m30.day_limit, 0);
        assert_eq!(at(&d, "bh2_32").triggers.len(), 6, "three waves and their day scenes");
    }

    /// Every cell a wave or a stage names is ground (sea for M32's fleet) and free of start units; M30's stage HQs are the map's `Q` tiles.
    #[test]
    fn act_five_spawn_cells_are_on_the_maps_and_free() {
        let free = |map: &str, cells: &[(u8, u8)], sea: bool| {
            let m = built_map(map).unwrap_or_else(|| panic!("{map}"));
            for &(x, y) in cells {
                assert!((x as usize) < m.width as usize && (y as usize) < m.height as usize, "{map}: ({x}, {y}) is off the map");
                assert!(!m.units.iter().any(|u| (u.x, u.y) == (x, y)), "{map}: a unit starts on ({x}, {y})");
                let _ = sea;
            }
        };
        free("bh2_28", &M28_WAVES, false);
        free("bh2_06", &M6_WING.iter().map(|&(_, c)| c).collect::<Vec<_>>(), false);
        for t in M6_TOWERS {
            assert!(!built_map("bh2_06").expect("bh2_06").units.iter().any(|u| (u.x, u.y) == t), "a unit starts on a tower");
        }
        free("bh2_32", &M32_CAV, false);
        free("bh2_32", &M32_SIEGE, false);
        free("bh2_32", &M32_FLEET, true);
        for w in [&OLAF_WAVE[..], &KANBEI_WAVE[..], &EAGLE_WAVE[..]] {
            free("bh2_30", &w.iter().map(|&(_, c)| c).collect::<Vec<_>>(), false);
        }
        let hq = |c: (u8, u8)| c;
        assert_eq!([hq(M30_NELL), M30_OLAF, M30_KANBEI, M30_EAGLE], [(8, 8), (24, 6), (39, 6), (38, 20)]);
    }

    /// M12's half-strength number is half of Kanbei's start, and the airlift's cells are free of start units.
    #[test]
    fn m9_airlift_cells_are_free_and_half_is_half() {
        let m = built_map("bh2_12").expect("bh2_12");
        let kanbei = m.units.iter().filter(|u| u.army == 2).count();
        assert_eq!(M12_HALF as usize * 2, kanbei, "M12_HALF is half of Kanbei's {kanbei} starting units");
        for &(x, y) in M12_AIR.iter().chain(M12_INF.iter()) {
            assert!(!m.units.iter().any(|u| (u.x, u.y) == (x, y)), "a unit starts on the airlift cell ({x}, {y})");
        }
    }

    #[test]
    fn every_mission_has_a_built_map_and_a_flag_on_land() {
        for m in def().missions {
            let MapSrc::Built(n) = &m.map else { panic!("{}", m.key) };
            assert!(built_map(n).is_some(), "{n}");
            let (x, y) = m.flag;
            let region = crate::world_picture::BH2.map().region_at(x as i32, y as i32);
            assert!(region != 0, "{}: the flag ({x}, {y}) is on the sea", m.key);
        }
    }

    /// Every scene of the dialogue files is asked for by the code, except the map-switch merge's TODO list, and every scene the code asks for exists
    /// (a missing one is a panic in `def()`).
    #[test]
    fn every_dialogue_scene_is_used() {
        let _ = def();
        let used = crate::bh2_text::keys_used();
        let unused: Vec<String> = crate::bh2_text::keys()
            .into_iter()
            .filter(|k| !used.contains(k) && !TODO_SCENES.contains(&k.as_str()))
            .collect();
        assert!(unused.is_empty(), "scenes in src/bh2_text/*.txt that no mission asks for: {unused:?}");
        for k in TODO_SCENES {
            assert!(crate::bh2_text::keys().iter().any(|x| x == k), "{k} is in the TODO list but not in the files");
            assert!(!used.contains(k), "{k} is wired: take it off TODO_SCENES");
        }
    }

    /// The pools: the eleven officers, no Sturm; M4 without Hawke (he leads the sky front); every mission's lead is as the mission list says.
    #[test]
    fn the_free_pick_pool_is_the_eleven_officers_and_leads_are_forced_as_planned() {
        let cos: Vec<u8> = ROSTER.iter().map(|r| r.0).collect();
        assert_eq!(cos.len(), 11);
        assert!(!cos.contains(&co::STURM), "Sturm is never a free pick");
        assert!(ROSTER.iter().all(|r| r.1));
        let d = def();
        assert!(!at(&d, "bh2_04").pool.contains(&co::HAWKE) && at(&d, "bh2_04").pool.len() == 10);
        let asuka = crate::co_new::ASUKA;
        let lead = |k: &str| match &at(&d, k).armies.iter().find(|a| a.colour == colour::BLACK_HOLE).unwrap().co {
            CoSpec::Fixed(c) => Some((*c, None)),
            CoSpec::Pair(a, b) => Some((*a, Some(*b))),
            CoSpec::PickPartner(a) => Some((*a, None)),
            _ => None,
        };
        let forced: [(&str, u8); 17] = [
            ("bh2_01", asuka),
            ("bh2_02", asuka),
            ("bh2_05", co::STURM),
            ("bh2_08", co::KOAL),
            ("bh2_10", co::KOAL),
            ("bh2_12", asuka),
            ("bh2_13", asuka),
            ("bh2_15", co::HAWKE),
            ("bh2_16", co::JUGGER),
            ("bh2_17", co::LASH),
            ("bh2_18", co::FLAK),
            ("bh2_22", co::CLONE_ANDY),
            ("bh2_23", asuka),
            ("bh2_24", co::ADDER),
            ("bh2_26", asuka),
            ("bh2_27", co::VON_BOLT),
            ("bh2_28", asuka),
        ];
        for (k, c) in forced {
            assert_eq!(lead(k).map(|l| l.0), Some(c), "{k}'s lead");
        }
        assert_eq!(lead("bh2_31").map(|l| l.0), Some(asuka));
        for k in ["bh2_03", "bh2_06", "bh2_07", "bh2_09", "bh2_11", "bh2_14", "bh2_19", "bh2_20", "bh2_21", "bh2_25", "bh2_29", "bh2_30", "bh2_32"] {
            assert!(lead(k).is_none(), "{k} is a free pick");
        }
    }

    /// M29 opens the secret M32 and nothing else needs M32; the staff roll has the secret pages; the prologue has its pages and three scenes.
    #[test]
    fn the_secret_opens_after_m29_and_the_story_is_wired() {
        let d = def();
        assert!(matches!(&at(&d, "bh2_32").needs, Needs::All(v) if v == &vec!["bh2_29"]));
        assert!(d.missions.iter().filter(|m| m.key != "bh2_32").all(|m| !matches!(&m.needs, Needs::All(v) if v.contains(&"bh2_32"))));
        assert!(!d.prologue.is_empty() && d.prologue_scenes.len() == 3 && d.prologue_song.is_some());
        assert!(d.credits.iter().any(|c| c.secret) && d.credits.iter().any(|c| !c.secret));
        assert!(!at(&d, "bh2_31").after.lines.is_empty() && !at(&d, "bh2_32").after.lines.is_empty());
        for m in &d.missions {
            assert!(!m.intro.lines.is_empty() && !m.victory.lines.is_empty() || m.key == "bh2_30", "{} has its pre and post scenes", m.key);
        }
    }

    /// Aria is the real CO 93 in the final mission.
    #[test]
    fn aria_is_co_93_in_the_final_mission() {
        assert_eq!(ARIA_CO, 93);
        let d = def();
        assert!(matches!(&at(&d, "bh2_31").armies[1].co, CoSpec::Fixed(93)));
    }

    /// The release toggle shows the campaign; the text ids of every scene fit the compiler's budget.
    #[test]
    fn released_and_the_text_ids_fit() {
        assert!(RELEASED && dev_flag());
        let used = crate::custom_campaign::text_ids_used(&def());
        assert!(used + 150 <= 3072, "the BH2 Campaign's scenes use {used} text ids: pack or trim");
    }

    #[test]
    fn m2_crate_is_where_the_mission_says() {
        let m = built_map("bh2_02").expect("bh2_02");
        let c = m.units.iter().find(|u| u.name == "crate").expect("crate");
        assert!(M2_GOAL.0 > c.x);
    }
}
