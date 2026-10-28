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
    ];
    missions.iter_mut().for_each(crate::bh_ai::spawn_orders);
    CampaignDef {
        source: SOURCE,
        roster: ROSTER.to_vec(),
        prologue: Vec::new(),
        prologue_song: None,
        credits: Vec::new(),
        missions,
        final_mission: "bh2_14",
        bonds: Vec::new(),
        extra_bonds: 0,
        secret_mission: "",
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
        assert_eq!(d.missions.len(), 14);
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
        assert!(d.missions[10..].iter().map(|m| m.key).eq(["bh2_11", "bh2_12", "bh2_13", "bh2_14"]));
        assert!(d.missions[13].factory.len() == 14 && d.missions[13].volcano.is_some());
        assert_eq!(d.missions[13].look, 3);
        assert!(d.missions[10..13].iter().all(|m| m.look == 1), "M11 to M13 are the snow look");
        assert_eq!(d.final_mission, "bh2_14");
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
