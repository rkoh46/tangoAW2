//! The BH Campaign: thirty missions played as Black Hole, defined as data
//! ([`crate::custom_campaign`]); the engine is the DS Campaign's. It needs
//! the Dual Strike pack (its COs, units and looks come from it).
//!
//! Today it holds two placeholder missions that prove the pipeline end to
//! end; the thirty are added here as [`MissionDef`]s (docs/AW2.md "BH
//! Campaign: adding a mission"). Nothing of AW2's or Dual Strike's art is
//! in this file: maps are text pictures or names of the player's own ROMs'
//! maps, scenes are original placeholder text.

use mgba::core::Core;

use crate::campaign_model::{Model, Requires, SendRule};
use crate::custom_campaign::{co, colour, unit, *};

/// The roster, in unlock order: the entry's index is its bit in the
/// record. Sturm is open at the start; the recruit missions open the rest.
pub const ROSTER: [(u8, bool); 10] = [
    (co::STURM, true),
    (co::VON_BOLT, false),
    (co::HAWKE, false),
    (co::KINDLE, false),
    (co::KOAL, false),
    (co::JUGGER, false),
    (co::FLAK, false),
    (co::LASH, false),
    (co::ADDER, false),
    (co::CLONE_ANDY, false),
];

/// Roster indexes by name, for `recruits`.
pub mod roster {
    pub const STURM: u8 = 0;
    pub const VON_BOLT: u8 = 1;
    pub const HAWKE: u8 = 2;
    pub const KINDLE: u8 = 3;
    pub const KOAL: u8 = 4;
    pub const JUGGER: u8 = 5;
    pub const FLAK: u8 = 6;
    pub const LASH: u8 = 7;
    pub const ADDER: u8 = 8;
    pub const CLONE_ANDY: u8 = 9;
}

/// The world map's regions on AW2's own map (map pixels; its picture is
/// 432 x 256): Black Hole's land is the small island at the top (AW2 puts
/// its last two missions there; it holds the campaign's first missions),
/// then the campaign goes round through Green Earth (the east land),
/// Yellow Comet (the centre land), Blue Moon (the south) and Orange Star
/// (the west). Each region lists flag places inside its land, in play
/// order; a mission's `flag` is one of them (or any point of the picture).
pub mod region {
    pub const BLACK_HOLE: [(i16, i16); 6] = [(160, 30), (172, 26), (184, 32), (168, 42), (180, 46), (188, 54)];
    pub const GREEN_EARTH: [(i16, i16); 6] = [(350, 95), (372, 118), (332, 135), (345, 160), (325, 190), (340, 215)];
    pub const YELLOW_COMET: [(i16, i16); 6] = [(290, 57), (265, 60), (250, 80), (275, 100), (245, 115), (255, 140)];
    pub const BLUE_MOON: [(i16, i16); 6] = [(205, 200), (190, 170), (160, 215), (150, 185), (130, 225), (110, 200)];
    pub const ORANGE_STAR: [(i16, i16); 6] = [(115, 175), (95, 150), (70, 175), (60, 130), (110, 100), (75, 85)];
}

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
    m.requires = Requires::All(vec![0]);
    m.flag = region::BLACK_HOLE[1];
    m.stars = 1;
    m
}

/// The campaign.
pub fn def() -> CampaignDef {
    CampaignDef {
        source: 1,
        roster: ROSTER.to_vec(),
        prologue: vec![
            Page { text: "Placeholder prologue, page one. Black Hole rises again.", picture: None, who: None },
            Page { text: "Placeholder prologue, page two. Sturm leads the way.", picture: None, who: None },
        ],
        credits: vec![
            CreditSection { heading: "BH CAMPAIGN", names: vec!["PLACEHOLDER"] },
            CreditSection { heading: "THANKS FOR PLAYING", names: vec![] },
        ],
        missions: vec![placeholder_one(), placeholder_two()],
        final_mission: 1,
    }
}

/// A campaign that exercises the format's fields (funds, weather, fog, a
/// day limit, structures, a named unit that must reach a place, triggers,
/// scenes, a second front), for the engine's tests: `load` plays it instead
/// of the BH Campaign when the environment variable `TANGOAW2_BH_FEATURES`
/// is set (`tools/aw2test/tests/test_bh_campaign.py`). Not shipped content.
pub fn features_def() -> CampaignDef {
    let mut a = MissionDef::new("f01", "Features One");
    a.objective = "Test: funds, rain, fog, structures.";
    a.map = MapSrc::Ascii(&[
        "1...........",
        "............",
        "............",
        "............",
        "............",
        "............",
        "............",
        "............",
        "...........2",
    ]);
    a.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)).funds(5000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::VON_BOLT)).funds(7000),
    ];
    a.weather = Weather::Rain;
    a.fog = true;
    a.day_limit = 6;
    a.structures = vec![(Structure::BlackFactory, 6, 4), (Structure::BlackCrystal, 3, 3), (Structure::BlackObelisk, 9, 2), (Structure::Laser, 1, 6)];
    a.units = vec![UnitDef::new(1, unit::INFANTRY, 1, 1), UnitDef::new(2, unit::INFANTRY, 10, 7)];
    a.triggers = vec![Trigger {
        when: When::TurnStart,
        cond: Cond::DayAtLeast(2),
        then: vec![Action::SetFunds { army: 1, funds: 9900 }, Action::Scene(Scene::new(vec![Line::say(co::STURM, "Day two.")]))],
    }];
    a.recruits = vec![roster::HAWKE];
    a.flag = region::BLACK_HOLE[0];

    let mut b = MissionDef::new("f02", "Features Two");
    b.objective = "Test: the courier reaches (10, 6).";
    b.map = MapSrc::Ascii(&[
        "1...........",
        "............",
        "............",
        "............",
        "............",
        "............",
        "...........2",
    ]);
    b.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::HAWKE, co::KOAL)),
    ];
    b.units = vec![
        UnitDef::new(1, unit::INFANTRY, 1, 1).hp(10).named("courier"),
        UnitDef::new(1, unit::TANK, 2, 0),
        UnitDef::new(2, unit::INFANTRY, 8, 2).hold(),
        UnitDef::new(2, unit::TANK, 9, 2).hold(),
    ];
    b.triggers = vec![
        Trigger {
            when: When::AfterAction,
            cond: Cond::UnitAt { name: "courier", x: 10, y: 5 },
            then: vec![Action::Scene(Scene::new(vec![Line::say(co::STURM, "The courier is out.")])), Action::Win],
        },
        Trigger {
            when: When::TurnStart,
            cond: Cond::All(vec![Cond::DayAtLeast(4), Cond::Not(Box::new(Cond::UnitAt { name: "courier", x: 10, y: 5 }))]),
            then: vec![Action::Lose],
        },
    ];
    b.victory = Scene::new(vec![Line::say(co::STURM, "Extracted.")]);
    b.requires = Requires::All(vec![0]);
    b.pool = vec![co::STURM, co::VON_BOLT, co::HAWKE];
    b.flag = region::BLACK_HOLE[1];

    // Two fronts: the player's tag pair on the main front, a pick of its own
    // for the second.
    let mut c = MissionDef::new("f03", "Features Three");
    c.objective = "Test: two fronts, a CO for each.";
    c.map = MapSrc::Ascii(&["1.........", "..........", "..........", ".........2"]);
    c.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JUGGER)),
    ];
    c.units = vec![UnitDef::new(1, unit::INFANTRY, 1, 1), UnitDef::new(2, unit::INFANTRY, 8, 2).hold()];
    c.front2 = Some(FrontDef {
        map: MapSrc::Ascii(&["1......", ".......", "......2"]),
        props: Vec::new(),
        structures: Vec::new(),
        units: vec![UnitDef::new(1, unit::INFANTRY, 1, 1), UnitDef::new(2, unit::INFANTRY, 5, 1).hold()],
        cos: [CoSpec::Pick, CoSpec::Fixed(co::KOAL), CoSpec::None, CoSpec::None],
        send: SendRule::Ground,
        sky: false,
        weather: Weather::Clear,
        fog: false,
    });
    c.requires = Requires::All(vec![1]);
    c.pool = vec![co::STURM, co::VON_BOLT, co::HAWKE];
    c.flag = region::BLACK_HOLE[2];

    // Maps of AW2's and of Dual Strike's, with their own deployments.
    let mut d = MissionDef::new("f04", "Features Four");
    d.objective = "Test: AW2's first campaign map.";
    d.map = MapSrc::Aw2 { id: 0x8A };
    d.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::LASH)),
    ];
    d.requires = Requires::All(vec![2]);
    d.flag = region::BLACK_HOLE[3];
    let mut f = MissionDef::new("f05", "Features Five");
    f.objective = "Test: Dual Strike's first campaign map.";
    f.map = MapSrc::Ds { record: 0 };
    f.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::ADDER)),
    ];
    f.requires = Requires::All(vec![3]);
    f.flag = region::BLACK_HOLE[4];

    CampaignDef {
        source: 1,
        roster: ROSTER.to_vec(),
        prologue: vec![Page { text: "Features.", picture: None, who: None }],
        credits: vec![CreditSection { heading: "FEATURES", names: vec!["TEST"] }],
        missions: vec![a, b, c, d, f],
        final_mission: 4,
    }
}

/// The campaign's source `load`.
pub fn load(core: &Core) -> Option<Model> {
    let def = if std::env::var_os("TANGOAW2_BH_FEATURES").is_some() { features_def() } else { def() };
    match compile(core, &def) {
        Ok(m) => Some(m),
        Err(e) => {
            eprintln!("BH Campaign: {e}");
            None
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roster_order() {
        assert_eq!(ROSTER[0], (co::STURM, true));
        assert!(ROSTER[1..].iter().all(|r| !r.1));
        assert_eq!(ROSTER[roster::CLONE_ANDY as usize].0, co::CLONE_ANDY);
    }

    #[test]
    fn missions_are_consistent() {
        let d = def();
        assert!(d.missions.len() <= crate::campaign_model::MAX_MISSIONS);
        for m in &d.missions {
            assert!(m.armies.len() >= 2);
            for r in &m.recruits {
                assert!((*r as usize) < d.roster.len());
            }
        }
        assert!(d.final_mission < d.missions.len());
    }
}
