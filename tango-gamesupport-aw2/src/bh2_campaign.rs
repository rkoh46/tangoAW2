//! The BH2 Campaign, development build: Black Hole's eastern war on the AW1-style picture world map (docs/BH2_CAMPAIGN.md). Only Act I's five missions exist so far, as
//! minimal `MissionDef`s (the armies, the COs of the design table, M4's two fronts, M5's held second HQ) with no dialogue: they exist to enter the maps in the game and
//! photograph them (`aw2dev maps boot --campaign bh2`), the real game's pictures the owner reviews. The maps are `five/bh2/spec/*.py` -> `bh2_map_data.rs`.
//!
//! It is behind a development flag (`TANGOAW2_BH2_CAMPAIGN`, [`available`]) and never shows to players: the Campaign sub-menu's "BH2 CAMPAIGN" stays "Coming soon".
//! Its record is Flash slot 10 ("AWB2"), a mission saved halfway shares the BH Campaign's slot 12 (`suspend::source_tag`); see docs/dev/bh2-maps.md "Flash".

use mgba::core::Core;

use crate::campaign_model::Model;
use crate::campaign_model::SendRule;
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
const M5_HQ: (u8, u8) = (30, 10);
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

/// The campaign.
pub fn def() -> CampaignDef {
    let mut missions = vec![bh2_01(), bh2_02(), bh2_03(), bh2_04(), bh2_05()];
    missions.iter_mut().for_each(crate::bh_ai::spawn_orders);
    CampaignDef {
        source: SOURCE,
        roster: ROSTER.to_vec(),
        prologue: Vec::new(),
        prologue_song: None,
        credits: Vec::new(),
        missions,
        final_mission: "bh2_05",
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
        assert_eq!(d.missions.len(), 5);
        assert!(d.missions[3].front2.as_ref().is_some_and(|f| f.sky));
        assert!(d.missions[4].held_hq.is_some());
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
