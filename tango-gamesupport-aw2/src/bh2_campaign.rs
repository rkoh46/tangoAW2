//! The BH2 Campaign, development build: Black Hole's eastern war on the AW1-style picture world map (docs/BH2_CAMPAIGN.md). Only Act I's five missions exist so far, as
//! minimal `MissionDef`s (the armies, the COs of the design table, M4's two fronts, M5's held second HQ) with no dialogue: they exist to enter the maps in the game and
//! photograph them (`aw2dev maps boot --campaign bh2`), the real game's pictures the owner reviews. The maps are `five/bh2/spec/*.py` -> `bh2_map_data.rs`.
//!
//! It is behind a development flag (`TANGOAW2_BH2_CAMPAIGN`, [`available`]) and never shows to players: the Campaign sub-menu's "BH2 CAMPAIGN" stays "Coming soon".
//! Its record is Flash slot 10 ("AWB2"), a mission saved halfway shares the BH Campaign's slot 12 (`suspend::source_tag`); see docs/dev/bh2-maps.md "Flash".

use mgba::core::Core;

use crate::campaign_model::Model;
use crate::campaign_model::{ring, SendRule, VolcanoDef};
use crate::custom_campaign::{co, colour, unit, *};
use crate::es_campaign::{after, deployment, wave};

/// The campaign's source index in [`crate::campaign_model::SOURCES`].
pub const SOURCE: usize = 3;

/// The development flag: the environment variable `TANGOAW2_BH2_CAMPAIGN` is set (every console of the harness sets it for itself).
pub fn dev_flag() -> bool {
    std::env::var_os("TANGOAW2_BH2_CAMPAIGN").is_some()
}

/// The campaign is playable (the Dual Strike pack is on and the development flag is set).
pub fn available(core: &Core) -> bool {
    crate::ds_weather::is_on(core) && dev_flag()
}

/// The roster, in unlock order: every Black Hole officer (all open: the development build has no unlocks yet).
pub const ROSTER: [(u8, bool); 12] = [
    (crate::co_new::ASUKA, true),
    (co::CRUMB, true),
    (co::HAWKE, true),
    (co::STURM, true),
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

/// The cell of Allied M5's second HQ (the map's `Q`) and of the capital's HQ.
const M5_HQ: (u8, u8) = (25, 9);
const M5_HQ2: (u8, u8) = (36, 3);
/// M2's crate truck destination: the quay's port.
const M2_QUAY: (u8, u8) = (26, 19);

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
    m.flag = flag(1);
    m.stars = 1;
    m.needs = Needs::Start;
    m
}

/// M2 The Quartermaster's Crate: Asuka + Crumb (forced pair), the crate truck must reach the quay.
fn bh2_02() -> MissionDef {
    let mut m = MissionDef::new("bh2_02", "The Quartermaster's Crate");
    m.objective = "Bring the crate truck to the quay before day 14.";
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
                x: M2_QUAY.0,
                y: M2_QUAY.1,
            },
            vec![Action::Win],
        ),
        after(Cond::UnitGone("crate"), vec![Action::Lose]),
    ];
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
    m.rank_days = 14;
    // The sky front (BH1's M15 rule): open sky and aircraft, won and lost by AW2's rout rule; its aircraft attack (role 4), none goes for an HQ.
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
    m.flag = flag(4);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_03"]);
    m
}

/// M5 Evergreen in Exile: the forced pair Sturm + Asuka against the Allied army, Javier first; when the capital's HQ falls Eagle takes over from the second HQ.
fn bh2_05() -> MissionDef {
    let mut m = MissionDef::new("bh2_05", "Evergreen in Exile");
    m.objective = "Take the capital's HQ, then the airport district's.";
    m.map = MapSrc::Built("bh2_05");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::STURM, crate::co_new::ASUKA)).funds(20000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JAVIER)).funds(30000),
    ];
    m.units = deployment("bh2_05");
    m.rank_days = 22;
    m.look = 3; // the Wasteland look: the exile capital stands on blasted ground
                // One Allied army throughout: the capital's HQ is held (its capture defeats nobody); Eagle takes the same army over from the airport district's `Q`.
    m.held_hq = Some(M5_HQ);
    m.triggers = vec![
        Trigger::new(
            When::AfterAction,
            Cond::OwnerAt {
                x: M5_HQ.0,
                y: M5_HQ.1,
                army: 1,
            },
            vec![
                Action::TakeOver {
                    army: 2,
                    co: co::EAGLE,
                    meter_pct: 30,
                },
                Action::AddFunds { army: 2, funds: 10000 },
                Action::Spawn(wave(2, unit::FIGHTER, &[(37, 1), (38, 2)])),
            ],
        ),
        after(beaten(2, M5_HQ2), vec![Action::Win]),
    ];
    m.flag = flag(5);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_04"]);
    m
}

/// M6 Paper Lanterns: a free pick, a night intel raid on Sensei's B Copter fleet (rain and fog, the normal look).
fn bh2_06() -> MissionDef {
    let mut m = MissionDef::new("bh2_06", "Paper Lanterns");
    m.objective = "Raid Roost, destroy Sensei's B Copter fleet and take his HQ.";
    m.map = MapSrc::Built("bh2_06");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(8000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::SENSEI)).funds(12000),
    ];
    m.units = deployment("bh2_06");
    m.fog = true;
    m.weather = Weather::Rain; // night rain over the lantern islands
    m.rank_days = 14;
    m.flag = flag(6);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_05"]);
    m
}

/// M7 Comet Highway: the forced tag pair Koal + Kindle against one Yellow Comet army under the pair Grimm + Sensei; a straight battle along the river bridges (desert, sandstorm).
fn bh2_07() -> MissionDef {
    let mut m = MissionDef::new("bh2_07", "Comet Highway");
    m.objective = "Cross the four rivers and take the Yellow Comet HQ.";
    m.map = MapSrc::Built("bh2_07");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::KOAL, co::KINDLE)).funds(12000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Pair(co::GRIMM, co::SENSEI)).funds(18000),
    ];
    m.units = deployment("bh2_07");
    m.look = 2; // the Desert look
    m.weather = Weather::Sandstorm;
    m.rank_days = 14;
    m.flag = flag(7);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_06"]);
    m
}

/// M8 Black Lanterns: a free pick with Black Crystals that heal, against Grimm's big army (rain; the plan's clear weather is rain so that M8 and M9, both the normal look, differ).
fn bh2_08() -> MissionDef {
    let mut m = MissionDef::new("bh2_08", "Black Lanterns");
    m.objective = "Hold the crystals' line and take Grimm's HQ across the river.";
    m.map = MapSrc::Built("bh2_08");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(10000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::GRIMM)).funds(24000),
    ];
    m.units = deployment("bh2_08");
    m.weather = Weather::Rain;
    m.rank_days = 16;
    m.flag = flag(8);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_07"]);
    m
}

/// M9's half strength: Kanbei's army has lost half of the units it started with (28 on the map).
const M9_HALF: u8 = 14;
/// The airlift's B Copters (the map's `mark_air` cells) and Infantry (its `mark_inf` cells).
const M9_AIR: [(u8, u8); 4] = [(17, 5), (25, 5), (21, 9), (13, 7)];
const M9_INF: [(u8, u8); 5] = [(6, 10), (14, 10), (21, 10), (28, 10), (35, 10)];

/// Kanbei has no tank left (Tank, Md Tank, Neotank, Megatank): he yields.
fn m9_no_tanks(core: &mut Core) -> bool {
    units_of(core, 2)
        .iter()
        .all(|u| !matches!(u.1, unit::TANK | unit::MD_TANK | unit::NEOTANK | unit::MEGATANK))
}

/// M9 The Table: Asuka (forced) against Kanbei + Sensei at the capital. No time limit. Scripted: Sensei's airlift at half strength, Kanbei's surrender with his last tank.
fn bh2_09() -> MissionDef {
    let mut m = MissionDef::new("bh2_09", "The Table");
    m.objective = "Break Kanbei's wall and take the capital's HQ.";
    m.map = MapSrc::Built("bh2_09");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(crate::co_new::ASUKA)).funds(15000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Pair(co::KANBEI, co::SENSEI)).funds(20000),
    ];
    m.units = deployment("bh2_09");
    m.rank_days = 20;
    let mut airlift: Vec<UnitDef> = M9_AIR.iter().map(|&(x, y)| UnitDef::new(2, unit::B_COPTER, x, y).attack()).collect();
    airlift.extend(M9_INF.iter().map(|&(x, y)| UnitDef::new(2, unit::INFANTRY, x, y).attack()));
    m.triggers = vec![
        // at half strength Kanbei calls Sensei's airlift
        Trigger::new(When::AfterAction, Cond::ArmyUnitsAtMost { army: 2, n: M9_HALF }, vec![Action::Spawn(airlift)]),
        // his last tank falls: he yields the field
        after(Cond::Custom(m9_no_tanks), vec![Action::Win]),
    ];
    m.flag = flag(9);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_08"]);
    m
}

/// M10 Two Tides: two fronts. Front 1, Asuka (forced) against Kanbei's last stand; front 2, a free pick against Grimm (Wasteland look, fog, lava for water).
fn bh2_10() -> MissionDef {
    let mut m = MissionDef::new("bh2_10", "Two Tides");
    m.objective = "Take Kanbei's HQ; the second front takes Grimm's.";
    m.map = MapSrc::Built("bh2_10");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(crate::co_new::ASUKA)).funds(10000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KANBEI)).funds(18000),
    ];
    m.units = deployment("bh2_10");
    m.look = 3; // the Wasteland look: the tides are lava
    m.fog = true;
    m.rank_days = 18;
    m.front2 = Some(FrontDef {
        map: MapSrc::Built("bh2_10b"),
        props: Vec::new(),
        structures: Vec::new(),
        units: crate::bh_ai::built_units("bh2_10b"),
        cos: [CoSpec::Pick, CoSpec::Fixed(co::GRIMM), CoSpec::None, CoSpec::None],
        send: SendRule::Ground,
        sky: false,
        weather: Weather::Clear,
        fog: true,
    });
    m.flag = flag(10);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_09"]);
    m
}

/// M11 Cold Wire: Jugger (forced) against Grit on Blue Moon's snowbound border; the pipe walls' seams are the short cuts. A straight battle.
fn bh2_11() -> MissionDef {
    let mut m = MissionDef::new("bh2_11", "Cold Wire");
    m.objective = "Cut the Allied wire: break the walls' seams and take Grit's HQ.";
    m.map = MapSrc::Built("bh2_11");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::JUGGER)).funds(10000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::GRIT)).funds(16000),
    ];
    m.units = deployment("bh2_11");
    m.look = 1; // the Snow look
    m.weather = Weather::Snow;
    m.rank_days = 16;
    m.flag = flag(11);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_10"]);
    m
}

/// M12 Lot 42: Lash (forced) with a free tag partner against one Blue Moon army under Sasha + Colin, on the lab island; Black Hole's Black Obelisk (snow, fog).
fn bh2_12() -> MissionDef {
    let mut m = MissionDef::new("bh2_12", "Lot 42");
    m.objective = "Take the lab island's HQ; the Obelisk stands with you.";
    m.map = MapSrc::Built("bh2_12");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPartner(co::LASH)).funds(10000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Pair(co::SASHA, co::COLIN)).funds(20000),
    ];
    m.units = deployment("bh2_12");
    m.look = 1;
    m.fog = true;
    m.rank_days = 18;
    m.flag = flag(12);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_11"]);
    m
}

/// M13 Whiteout Harbour: Flak (forced) against Olaf, a naval and ground mix in the heaviest snow (snow weather and fog).
fn bh2_13() -> MissionDef {
    let mut m = MissionDef::new("bh2_13", "Whiteout Harbour");
    m.objective = "Land on Olaf's coast and take his HQ.";
    m.map = MapSrc::Built("bh2_13");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::FLAK)).funds(10000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF)).funds(18000),
    ];
    m.units = deployment("bh2_13");
    m.look = 1;
    m.weather = Weather::Snow;
    m.fog = true; // the whiteout: snow and fog together (M12 is fog alone, M11 snow alone)
    m.rank_days = 18;
    m.flag = flag(13);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_12"]);
    m
}

/// Factory table of M14 (day, the three doors' slots; 0 none): heavier than M3's, with a Neotank slot and the Anti-Air slots for the days Blue Moon's Fighters come.
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

/// M14 Thirty Years of Iron: a free pair with Black Hole's Black Factory (the foundry) against one Blue Moon army under Olaf + Grit; Mount Cinder erupts (Wasteland look). Ends Act III.
fn bh2_14() -> MissionDef {
    let mut m = MissionDef::new("bh2_14", "Thirty Years of Iron");
    m.objective = "Hold the foundry and take the Blue Moon HQ.";
    m.map = MapSrc::Built("bh2_14");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(12000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Pair(co::OLAF, co::GRIT)).funds(26000),
    ];
    m.units = deployment("bh2_14");
    m.look = 3; // the Wasteland look
    m.rank_days = 20;
    m.factory = F14.to_vec();
    // Mount Cinder: from day 3 it erupts every day on 3 of the cells of the ring road round it (5 HP, any army's units, never below 1).
    m.volcano = Some(VolcanoDef::new(3, 1, 5, &ring(20, 10, 27, 17)).per_eruption(3));
    m.flag = flag(14);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_13"]);
    m
}

/// M15 Every Colour: a free pair against one Orange Star army under Max + Sami on the border plains (normal look, clear).
fn bh2_15() -> MissionDef {
    let mut m = MissionDef::new("bh2_15", "Every Colour");
    m.objective = "Cross both rivers and take the Orange Star HQ.";
    m.map = MapSrc::Built("bh2_15");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(12000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::MAX, co::SAMI)).funds(20000),
    ];
    m.units = deployment("bh2_15");
    m.rank_days = 16;
    m.flag = flag(15);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_14"]);
    m
}

/// M16 The East Tower: a free pick against Andy + Rachel, a castle assault in the rain; no scripted escape.
fn bh2_16() -> MissionDef {
    let mut m = MissionDef::new("bh2_16", "The East Tower");
    m.objective = "Break the castle wall's gates and take the keep's HQ.";
    m.map = MapSrc::Built("bh2_16");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(10000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::ANDY, co::RACHEL)).funds(20000),
    ];
    m.units = deployment("bh2_16");
    m.weather = Weather::Rain;
    m.rank_days = 18;
    m.flag = flag(16);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_15"]);
    m
}

/// M17 Echo, Again: Clone Andy (forced) against Andy among the Lab 7 ruins (Wasteland look, fog).
fn bh2_17() -> MissionDef {
    let mut m = MissionDef::new("bh2_17", "Echo, Again");
    m.objective = "Cross the river and defeat Andy.";
    m.map = MapSrc::Built("bh2_17");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::CLONE_ANDY)).funds(10000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::ANDY)).funds(10000),
    ];
    m.units = deployment("bh2_17");
    m.look = 3;
    m.fog = true;
    m.rank_days = 16;
    m.flag = flag(17);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_16"]);
    m
}

/// M18's crate tile (the yard, `mark_crate`) and the reserve's Neotanks (`mark_neo*`).
const M18_CRATE: (u8, u8) = (9, 16);
const M18_NEO: [(u8, u8); 4] = [(5, 15), (7, 19), (11, 15), (11, 19)];

/// M18 The Door Is Open: Asuka + Crumb defend the depot; when Crumb (the named APC) reaches the crate tile the reserve's Neotanks appear; Crumb lost is the mission lost.
fn bh2_18() -> MissionDef {
    let mut m = MissionDef::new("bh2_18", "The Door Is Open");
    m.objective = "Defend the depot until Crumb reaches the crate.";
    m.map = MapSrc::Built("bh2_18");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(crate::co_new::ASUKA, co::CRUMB)).funds(10000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::HACHI, co::JAKE)).funds(18000),
    ];
    m.units = deployment("bh2_18");
    m.rank_days = 16;
    m.triggers = vec![
        after(
            Cond::UnitAt {
                name: "crumb",
                x: M18_CRATE.0,
                y: M18_CRATE.1,
            },
            vec![Action::Spawn(wave(1, unit::NEOTANK, &M18_NEO))],
        ),
        after(Cond::UnitGone("crumb"), vec![Action::Lose]),
    ];
    m.flag = flag(18);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_17"]);
    m
}

/// M19 Skyfall: Adder (forced) against Rachel + Jake on the desert coast; the air war against the Allies' Anti-Air belt (desert look, clear).
fn bh2_19() -> MissionDef {
    let mut m = MissionDef::new("bh2_19", "Skyfall");
    m.objective = "Win the air war and take the Allied HQ.";
    m.map = MapSrc::Built("bh2_19");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::ADDER)).funds(14000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::RACHEL, co::JAKE)).funds(20000),
    ];
    m.units = deployment("bh2_19");
    m.look = 2; // the Desert look
    m.rank_days = 18;
    m.flag = flag(19);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_18"]);
    m
}

/// M20 The Rail East: two fronts. Front 1, a free pick against Andy on the rail corridor (fog); front 2, a free pick against Hachi in the rail yard in a sandstorm. Ends Act IV.
fn bh2_20() -> MissionDef {
    let mut m = MissionDef::new("bh2_20", "The Rail East");
    m.objective = "Take Andy's terminus; the second front takes Hachi's yard.";
    m.map = MapSrc::Built("bh2_20");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(10000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::ANDY)).funds(18000),
    ];
    m.units = deployment("bh2_20");
    m.fog = true; // (M18 and M20 are both the normal look and clear: fog tells them apart)
    m.rank_days = 18;
    m.front2 = Some(FrontDef {
        map: MapSrc::Built("bh2_20b"),
        props: Vec::new(),
        structures: Vec::new(),
        units: crate::bh_ai::built_units("bh2_20b"),
        cos: [CoSpec::Pick, CoSpec::Fixed(co::HACHI), CoSpec::None, CoSpec::None],
        send: SendRule::Ground,
        sky: false,
        weather: Weather::Sandstorm,
        fog: true,
    });
    m.flag = flag(20);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_19"]);
    m
}

/// M21 The Second Folder: Asuka + Hawke (forced pair) against Max + Sami at Black Hole's eastern HQ, between two frozen lakes (snow look, clear).
fn bh2_21() -> MissionDef {
    let mut m = MissionDef::new("bh2_21", "The Second Folder");
    m.objective = "Hold the isthmus and take the Orange Star HQ.";
    m.map = MapSrc::Built("bh2_21");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(crate::co_new::ASUKA, co::HAWKE)).funds(14000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::MAX, co::SAMI)).funds(22000),
    ];
    m.units = deployment("bh2_21");
    m.look = 1; // the Snow look
    m.rank_days = 18;
    m.flag = flag(21);
    m.stars = 2;
    m.needs = Needs::All(vec!["bh2_20"]);
    m
}

/// Factory table of M22 (day, the three doors' slots; 0 none): the foundry builds against a fortress, Anti-Air only when the Allied Fighters show.
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

/// M22 Von Bolt's Note: Von Bolt (forced) + a free partner against Jess + Colin at the Orange Star sea fortress; the player's Black Factory and Deathray (rain).
fn bh2_22() -> MissionDef {
    let mut m = MissionDef::new("bh2_22", "Von Bolt's Note");
    m.objective = "Cross the strait and take the fortress's HQ; the Deathray covers the east.";
    m.map = MapSrc::Built("bh2_22");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPartner(co::VON_BOLT)).funds(14000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::JESS, co::COLIN)).funds(26000),
    ];
    m.units = deployment("bh2_22");
    m.weather = Weather::Rain;
    m.rank_days = 22;
    m.factory = F22.to_vec();
    m.flag = flag(22);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_21"]);
    m
}

/// M23's reinforcement cells (the map's `mark_wave*` notes): waves of three on days 2, 4, 6 and 8.
const M23_WAVES: [(u8, u8); 12] = [(42, 5), (42, 9), (42, 13), (42, 17), (41, 7), (41, 11), (41, 15), (41, 19), (42, 3), (42, 21), (41, 4), (41, 22)];

/// A reinforcement trigger on a day: the army's units appear on the cells.
fn day_wave(day: u16, units: Vec<UnitDef>) -> Trigger {
    Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: day }, vec![Action::Spawn(units)]).repeating()
}

/// M23 Where the Map Ends: Asuka + Crumb (forced pair) hold the Obelisk against Drake + Grit's strike force for nine days (wasteland, sandstorm).
fn bh2_23() -> MissionDef {
    let mut m = MissionDef::new("bh2_23", "Where the Map Ends");
    m.objective = "Hold the Obelisk until day 10. The waves come over the bridges and by air.";
    m.map = MapSrc::Built("bh2_23");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(crate::co_new::ASUKA, co::CRUMB)).funds(12000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Pair(co::DRAKE, co::GRIT)).funds(18000),
    ];
    m.units = deployment("bh2_23");
    m.look = 3; // the Wasteland look
    m.weather = Weather::Sandstorm; // the storm
    m.rank_days = 10;
    let w = |k: usize, kind: u8| UnitDef::new(2, kind, M23_WAVES[k].0, M23_WAVES[k].1).attack();
    m.triggers = vec![
        day_wave(2, vec![w(0, unit::NEOTANK), w(1, unit::MD_TANK), w(2, unit::B_COPTER)]),
        day_wave(4, vec![w(3, unit::NEOTANK), w(4, unit::ROCKETS), w(5, unit::FIGHTER)]),
        day_wave(6, vec![w(6, unit::MD_TANK), w(7, unit::BOMBER), w(8, unit::NEOTANK)]),
        day_wave(8, vec![w(9, unit::NEOTANK), w(10, unit::STEALTH), w(11, unit::MEGATANK)]),
        // nine days held: the storm passes
        Trigger::new(When::TurnStart, Cond::DayAtLeast(10), vec![Action::Win]),
    ];
    m.flag = flag(23);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_22"]);
    m
}

/// M24 The Gate of Colours: a free pair against Andy and Max + Sami, two allied armies (three armies), on the desert delta.
fn bh2_24() -> MissionDef {
    let mut m = MissionDef::new("bh2_24", "The Gate of Colours");
    m.objective = "Cross the three rivers and take both Allied HQs.";
    m.map = MapSrc::Built("bh2_24");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(14000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::ANDY)).team(2).funds(16000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Pair(co::MAX, co::SAMI)).team(2).funds(16000),
    ];
    m.units = deployment("bh2_24");
    m.look = 2; // the Desert look
    m.rank_days = 22;
    m.flag = flag(24);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_23"]);
    m
}

/// M25's stage HQs (the map's `Q` tiles): Nell's `2` at (8,10) is the first line; the others are held until the last.
const M25_NELL: (u8, u8) = (8, 10);
const M25_OLAF: (u8, u8) = (24, 6);
const M25_KANBEI: (u8, u8) = (39, 6);
const M25_EAGLE: (u8, u8) = (38, 20);
const M25_ARIA: (u8, u8) = (22, 21);
/// Aria's CO id: the new Orange Star commander (the `aria` branch's id 93: not merged here, so a placeholder CO takes her place; replace this constant when it lands).
const ARIA_CO: u8 = co::MAX;

/// Each stage's fresh troops (cells in the stage's zone, free of start units): (kind, cell).
const OLAF_WAVE: [(u8, (u8, u8)); 18] = [
    (unit::MD_TANK, (16, 5)),
    (unit::MD_TANK, (16, 8)),
    (unit::NEOTANK, (17, 13)),
    (unit::ROCKETS, (18, 0)),
    (unit::MD_TANK, (21, 0)),
    (unit::ARTILLERY, (21, 13)),
    (unit::MD_TANK, (24, 11)),
    (unit::MECH, (24, 13)),
    (unit::NEOTANK, (25, 0)),
    (unit::ROCKETS, (25, 6)),
    (unit::INFANTRY, (27, 1)),
    (unit::NEOTANK, (27, 13)),
    (unit::MD_TANK, (30, 1)),
    (unit::ARTILLERY, (31, 13)),
    // Olaf's fleet on the riverland's lakes
    (unit::BATTLESHIP, (18, 5)),
    (unit::CRUISER, (29, 5)),
    (unit::CRUISER, (19, 7)),
    (unit::SUB, (29, 9)),
];
const KANBEI_WAVE: [(u8, (u8, u8)); 9] = [
    (unit::NEOTANK, (36, 8)),
    (unit::MEGATANK, (37, 5)),
    (unit::MD_TANK, (39, 7)),
    (unit::NEOTANK, (40, 5)),
    (unit::MEGATANK, (41, 7)),
    (unit::MD_TANK, (33, 13)),
    (unit::ARTILLERY, (34, 10)),
    (unit::NEOTANK, (39, 10)),
    (unit::MEGATANK, (39, 12)),
];
const EAGLE_WAVE: [(u8, (u8, u8)); 11] = [
    (unit::FIGHTER, (32, 22)),
    (unit::FIGHTER, (32, 25)),
    (unit::BOMBER, (34, 19)),
    (unit::STEALTH, (37, 20)),
    (unit::FIGHTER, (38, 23)),
    (unit::BOMBER, (40, 20)),
    (unit::B_COPTER, (41, 15)),
    (unit::STEALTH, (42, 18)),
    (unit::FIGHTER, (43, 16)),
    (unit::BOMBER, (44, 19)),
    (unit::B_COPTER, (45, 15)),
];
const ARIA_WAVE: [(u8, (u8, u8)); 8] = [
    (unit::NEOTANK, (15, 17)),
    (unit::MD_TANK, (15, 19)),
    (unit::MEGATANK, (15, 22)),
    (unit::ROCKETS, (20, 27)),
    (unit::NEOTANK, (21, 22)),
    (unit::FIGHTER, (22, 27)),
    (unit::MD_TANK, (23, 22)),
    (unit::ARTILLERY, (25, 26)),
];

fn stage(list: &[(u8, (u8, u8))]) -> Action {
    Action::Spawn(list.iter().map(|&(k, (x, y))| UnitDef::new(2, k, x, y).attack()).collect())
}

fn owned(c: (u8, u8)) -> Cond {
    Cond::OwnerAt { x: c.0, y: c.1, army: 1 }
}

/// The next line: when the player holds this stage's HQ (and every line before it has fallen: a stage's HQ taken out of order moves nothing), the same army goes on
/// under the next commander with fresh troops and funds.
fn takeover(hq: (u8, u8), before: &[(u8, u8)], co_next: u8, funds: i32, wave: &[(u8, (u8, u8))]) -> Trigger {
    let mut all = vec![owned(hq)];
    all.extend(before.iter().map(|&c| owned(c)));
    Trigger::new(
        When::AfterAction,
        Cond::All(all),
        vec![
            Action::TakeOver {
                army: 2,
                co: co_next,
                meter_pct: 40,
            },
            Action::AddFunds { army: 2, funds },
            stage(wave),
        ],
    )
}

/// M25 The Last Accord: the final mission, a gauntlet. Asuka + a free partner; Nell, then Olaf, Kanbei, Eagle and Aria take the same army over from a new HQ each time a line breaks; no time limit, no Black Hole inventions on the Allied side.
fn bh2_25() -> MissionDef {
    let mut m = MissionDef::new("bh2_25", "The Last Accord");
    m.objective = "Break Nell's line, then Olaf's, Kanbei's and Eagle's, and take Aria's HQ.";
    m.map = MapSrc::Built("bh2_25");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPartner(crate::co_new::ASUKA)).funds(30000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::NELL)).funds(30000),
    ];
    m.units = deployment("bh2_25");
    m.fog = true;
    m.rank_days = 40;
    m.held_hq = Some(M25_NELL);
    m.held_more = vec![M25_OLAF, M25_KANBEI, M25_EAGLE];
    m.triggers = vec![
        takeover(M25_NELL, &[], co::OLAF, 20000, &OLAF_WAVE),
        takeover(M25_OLAF, &[M25_NELL], co::KANBEI, 22000, &KANBEI_WAVE),
        takeover(M25_KANBEI, &[M25_NELL, M25_OLAF], co::EAGLE, 24000, &EAGLE_WAVE),
        takeover(M25_EAGLE, &[M25_NELL, M25_OLAF, M25_KANBEI], ARIA_CO, 30000, &ARIA_WAVE),
        // Aria's HQ is the last: its capture wins
        after(Cond::All(vec![owned(M25_ARIA), owned(M25_EAGLE)]), vec![Action::Win]),
    ];
    m.flag = flag(25);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_24"]);
    m
}

/// M26's landing cells (the map's `mark_cav`, `mark_siege` and `mark_fleet` notes).
const M26_CAV: [(u8, u8); 4] = [(12, 4), (15, 6), (18, 8), (20, 11)];
const M26_SIEGE: [(u8, u8); 4] = [(37, 24), (35, 25), (38, 22), (33, 26)];
const M26_FLEET: [(u8, u8); 5] = [(22, 4), (25, 6), (27, 9), (30, 11), (20, 2)];

/// M26 Through the Door (secret): a free pair against Klaus + Aurelia, the Emerald Sun legion, on Black Hole's own island; Cassius's cavalry on day 3, Aurelia's siege on day 5, Livia's fleet on day 7. (The Emerald Sun skin on the enemy army is a hook: see docs/dev/bh2-maps.md.)
fn bh2_26() -> MissionDef {
    let mut m = MissionDef::new("bh2_26", "Through the Door");
    m.objective = "Hold the island against the legion's three waves and take Klaus's HQ.";
    m.map = MapSrc::Built("bh2_26");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(14000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Pair(crate::es_co::KLAUS, crate::es_co::AURELIA)).funds(22000),
    ];
    m.units = deployment("bh2_26");
    m.skin = Some((2, 0)); // the legion wears the Emerald Sun skin (skin 0), on the colour the mission gives army 2
    m.rank_days = 20;
    let at = |kind: u8, c: (u8, u8)| UnitDef::new(2, kind, c.0, c.1).attack();
    m.triggers = vec![
        // Cassius's cavalry
        day_wave(3, vec![at(unit::RECON, M26_CAV[0]), at(unit::TANK, M26_CAV[1]), at(unit::RECON, M26_CAV[2]), at(unit::TANK, M26_CAV[3])]),
        // Aurelia's siege engines
        day_wave(5, vec![at(unit::ARTILLERY, M26_SIEGE[0]), at(unit::ROCKETS, M26_SIEGE[1]), at(unit::MD_TANK, M26_SIEGE[2]), at(unit::ARTILLERY, M26_SIEGE[3])]),
        // Livia's fleet
        day_wave(7, vec![at(unit::BATTLESHIP, M26_FLEET[0]), at(unit::CRUISER, M26_FLEET[1]), at(unit::CRUISER, M26_FLEET[2]), at(unit::SUB, M26_FLEET[3]), at(unit::LANDER, M26_FLEET[4])]),
    ];
    m.flag = flag(26);
    m.stars = 3;
    m.needs = Needs::All(vec!["bh2_24"]); // the secret mission opens after M24
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
    ];
    missions.iter_mut().for_each(crate::bh_ai::spawn_orders);
    CampaignDef {
        source: SOURCE,
        roster: ROSTER.to_vec(),
        prologue: Vec::new(),
        prologue_song: None,
        credits: Vec::new(),
        missions,
        final_mission: "bh2_25",
        bonds: Vec::new(),
        extra_bonds: 0,
        secret_mission: "bh2_26",
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

    #[test]
    fn act_one_has_five_missions_and_a_second_front_for_m4() {
        let d = def();
        assert_eq!(d.missions.len(), 26);
        assert!(d.missions[3].front2.as_ref().is_some_and(|f| f.sky));
        assert!(d.missions[4].held_hq.is_some());
    }

    #[test]
    fn act_two_has_five_missions_and_a_second_front_for_m10() {
        let d = def();
        assert!(d.missions[5..10].iter().map(|m| m.key).eq(["bh2_06", "bh2_07", "bh2_08", "bh2_09", "bh2_10"]));
        let f = d.missions[9].front2.as_ref().expect("M10's second front");
        assert!(!f.sky && matches!(f.map, MapSrc::Built("bh2_10b")));
        assert_eq!(d.missions[9].look, 3);
        // M9's scripted fight: the airlift at half strength, the surrender; M9 has no time limit
        assert_eq!(d.missions[8].triggers.len(), 2);
        assert_eq!(d.missions[8].day_limit, 0);
    }

    #[test]
    fn act_three_has_four_missions_with_the_factory_in_m14() {
        let d = def();
        assert!(d.missions[10..14].iter().map(|m| m.key).eq(["bh2_11", "bh2_12", "bh2_13", "bh2_14"]));
        assert!(d.missions[13].factory.len() == 14 && d.missions[13].volcano.is_some());
        assert_eq!(d.missions[13].look, 3);
        assert!(d.missions[10..13].iter().all(|m| m.look == 1), "M11 to M13 are the snow look");
    }

    #[test]
    fn act_four_has_six_missions_a_scripted_depot_and_a_second_front_for_m20() {
        let d = def();
        assert!(d.missions[14..20].iter().map(|m| m.key).eq(["bh2_15", "bh2_16", "bh2_17", "bh2_18", "bh2_19", "bh2_20"]));
        assert_eq!(d.missions[16].look, 3);
        assert_eq!(d.missions[18].look, 2);
        let f = d.missions[19].front2.as_ref().expect("M20's second front");
        assert!(!f.sky && matches!(f.weather, Weather::Sandstorm) && matches!(f.map, MapSrc::Built("bh2_20b")));
        assert_eq!(d.missions[17].triggers.len(), 2);
    }

    /// M18: the crate tile and the Neotank cells are the map's `mark_` notes' cells, free of start units, on ground; Crumb is the named APC of Black Hole.
    #[test]
    fn m18_crate_and_reserve_cells_are_free_and_crumb_is_named() {
        let m = built_map("bh2_18").expect("bh2_18");
        for &(x, y) in std::iter::once(&M18_CRATE).chain(M18_NEO.iter()) {
            assert!(!m.units.iter().any(|u| (u.x, u.y) == (x, y)), "a unit starts on ({x}, {y})");
        }
        let c = m.units.iter().find(|u| u.name == "crumb").expect("crumb");
        assert_eq!((c.army, c.kind), (1, 7), "Crumb is Black Hole's APC");
        assert!(c.x > M18_CRATE.0 + 10, "Crumb starts by the quay, far from the crate");
    }

    #[test]
    fn act_five_has_the_gauntlet_the_waves_and_the_secret() {
        let d = def();
        assert!(d.missions[20..].iter().map(|m| m.key).eq(["bh2_21", "bh2_22", "bh2_23", "bh2_24", "bh2_25", "bh2_26"]));
        assert_eq!(d.final_mission, "bh2_25");
        assert_eq!(d.secret_mission, "bh2_26");
        // M22: the player's factory; M23: waves and the day-10 win, no day limit; M24: three armies; M25: four held HQs and five triggers (four takeovers and the win), no day limit
        assert!(d.missions[21].factory.len() == 14);
        assert_eq!(d.missions[22].triggers.len(), 5);
        assert_eq!(d.missions[22].day_limit, 0);
        assert_eq!(d.missions[23].armies.len(), 3);
        assert!(d.missions[24].held_hq.is_some() && d.missions[24].held_more.len() == 3);
        assert_eq!(d.missions[24].triggers.len(), 5);
        assert_eq!(d.missions[24].day_limit, 0);
        assert_eq!(d.missions[25].triggers.len(), 3);
    }

    /// Every cell a wave or a stage names is ground (sea for M26's fleet) and free of start units; M25's stage HQs are the map's `Q` tiles.
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
        free("bh2_23", &M23_WAVES, false);
        free("bh2_26", &M26_CAV, false);
        free("bh2_26", &M26_SIEGE, false);
        free("bh2_26", &M26_FLEET, true);
        for w in [&OLAF_WAVE[..], &KANBEI_WAVE[..], &EAGLE_WAVE[..], &ARIA_WAVE[..]] {
            free("bh2_25", &w.iter().map(|&(_, c)| c).collect::<Vec<_>>(), false);
        }
        let hq = |c: (u8, u8)| c;
        assert_eq!([hq(M25_NELL), M25_OLAF, M25_KANBEI, M25_EAGLE, M25_ARIA], [(8, 10), (24, 6), (39, 6), (38, 20), (22, 21)]);
    }

    /// M9's half-strength number is half of Kanbei's start, and the airlift's cells are free of start units.
    #[test]
    fn m9_airlift_cells_are_free_and_half_is_half() {
        let m = built_map("bh2_09").expect("bh2_09");
        let kanbei = m.units.iter().filter(|u| u.army == 2).count();
        assert_eq!(M9_HALF as usize * 2, kanbei, "M9_HALF is half of Kanbei's {kanbei} starting units");
        for &(x, y) in M9_AIR.iter().chain(M9_INF.iter()) {
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

    #[test]
    fn m5_hq_cells_are_the_maps() {
        // the held HQ and the second HQ are where the map's text puts `2` and `Q`
        let m = built_map("bh2_05").expect("bh2_05");
        assert!(m.tiles.len() == m.width as usize * m.height as usize);
    }

    #[test]
    fn m2_crate_is_where_the_mission_says() {
        let m = built_map("bh2_02").expect("bh2_02");
        let c = m.units.iter().find(|u| u.name == "crate").expect("crate");
        assert!(M2_QUAY.0 > c.x);
    }
}
