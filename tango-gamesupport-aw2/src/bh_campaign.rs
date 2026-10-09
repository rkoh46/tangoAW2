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

use crate::bh_act1;
use crate::bh_act2;
use crate::bh_act3;
use crate::bh_act4;
use crate::bh_act5;
use crate::bh_act5b;
use crate::bh_secret;
use crate::campaign_model::{Model, OnyxDef, SendRule, VolcanoDef};
use crate::custom_campaign::{co, colour, unit, *};

/// The roster, in unlock order (Von Bolt, Hawke, Koal, Kindle, Jugger, Flak,
/// Lash, Adder, Clone Andy, then Sonja after the secret mission): the entry's index is its bit in the record.
/// Sturm is open at the start; the recruit missions open the rest.
pub const ROSTER: [(u8, bool); 12] = [
    (co::STURM, true),
    (co::VON_BOLT, false),
    (co::HAWKE, false),
    (co::KOAL, false),
    (co::KINDLE, false),
    (co::JUGGER, false),
    (co::FLAK, false),
    (co::LASH, false),
    (co::ADDER, false),
    (co::CLONE_ANDY, false),
    (co::SONJA, false),
    (co::CRUMB, false),
];

/// Roster indexes by name, for `recruits`.
pub mod roster {
    pub const STURM: u8 = 0;
    pub const VON_BOLT: u8 = 1;
    pub const HAWKE: u8 = 2;
    pub const KOAL: u8 = 3;
    pub const KINDLE: u8 = 4;
    pub const JUGGER: u8 = 5;
    pub const FLAK: u8 = 6;
    pub const LASH: u8 = 7;
    pub const ADDER: u8 = 8;
    pub const CLONE_ANDY: u8 = 9;
    /// Joins after the secret mission (its `recruits`), Free Play only in effect.
    pub const SONJA: u8 = 10;
    /// Crumb, promoted at the end of M28 and offered from M29 on: M28's
    /// builder puts `roster::CRUMB` in the mission's `recruits` (the win
    /// unlocks him) or, to unlock him in the middle of the mission (the
    /// promotion scene), ends a trigger's `then` with [`super::unlock_crumb`].
    pub const CRUMB: u8 = 11;
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
            CreditSection { heading: "BH CAMPAIGN", names: vec!["PLACEHOLDER"], secret: false },
            CreditSection { heading: "THANKS FOR PLAYING", names: vec![], secret: false },
        ],
        missions: [bh_act1::missions(), bh_act2::missions(), bh_act3::missions(), bh_act4::missions(), bh_act5::missions(), bh_act5b::missions(), bh_secret::missions()].concat(),
        final_mission: "bh02",
        bonds: BONDS.to_vec(),
        extra_bonds: 1,
        secret_mission: "",
    }
}

/// The action of Crumb's promotion: he is unlocked at once (the roster's
/// index [`roster::CRUMB`], `Action::Unlock`; saved with the record, nothing in
/// a replay). Use it in M28's win trigger (or give the mission
/// `recruits = vec![roster::CRUMB]`: the same, at the win).
pub fn unlock_crumb() -> Action {
    Action::Unlock(roster::CRUMB)
}

/// The bond index of Crumb's secret quote (flag 0xA9 of the design: earned by
/// winning M14 on day 12 or sooner, `Action::EarnBond(bond::CRUMB_QUOTE)`).
/// It is the tenth bond and does not count for the secret mission, which
/// opens when the first nine are earned.
pub mod bond {
    pub const CRUMB_QUOTE: u8 = 9;
}

/// The hidden bonds (placeholders): each earned in a recruit mission by
/// `Action::EarnBond(k)`, its quote on its CO's page; the secret mission
/// opens when all nine are earned (and the tenth, Crumb's page quote, is its
/// own: [`bond::CRUMB_QUOTE`]).
pub const BONDS: [Bond; 10] = [
    Bond { co: co::VON_BOLT, quote: "Placeholder bond quote." },
    Bond { co: co::HAWKE, quote: "Placeholder bond quote." },
    Bond { co: co::KOAL, quote: "Placeholder bond quote." },
    Bond { co: co::KINDLE, quote: "Placeholder bond quote." },
    Bond { co: co::JUGGER, quote: "Placeholder bond quote." },
    Bond { co: co::FLAK, quote: "Placeholder bond quote." },
    Bond { co: co::LASH, quote: "Placeholder bond quote." },
    Bond { co: co::ADDER, quote: "Placeholder bond quote." },
    Bond { co: co::CLONE_ANDY, quote: "Placeholder bond quote." },
    // Crumb's: an extra (M14, a win by day 12), not one of the nine of the secret mission.
    Bond { co: co::CRUMB, quote: crate::crumb::SECRET_QUOTE },
];

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
    a.units = vec![
        UnitDef::new(1, unit::INFANTRY, 1, 1),
        UnitDef::new(2, unit::INFANTRY, 10, 7).hold(),
        UnitDef::new(2, unit::INFANTRY, 9, 7).hold(),
        UnitDef::new(2, unit::INFANTRY, 10, 6).hold(),
        UnitDef::new(2, unit::INFANTRY, 9, 6).hold(),
    ];
    a.triggers = vec![Trigger {
        once: true,
        when: When::TurnStart,
        cond: Cond::DayAtLeast(2),
        then: vec![
            Action::SetFunds { army: 1, funds: 9900 },
            Action::AddFunds { army: 1, funds: 100 },
            Action::EarnBond(0),
            unlock_crumb(),
            Action::Strike { hp: 3 },
            Action::Scene(Scene::new(vec![Line::say(co::STURM, "Day two.")])),
        ],
    }];
    a.recruits = vec![roster::HAWKE];
    a.music = Some(220); // (AW2's song at Sturm's citadel)
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
            once: true,
            when: When::AfterAction,
            cond: Cond::UnitAt { name: "courier", x: 10, y: 5 },
            then: vec![Action::Scene(Scene::new(vec![Line::say(co::STURM, "The courier is out.")])), Action::Win],
        },
        Trigger {
            once: true,
            when: When::TurnStart,
            cond: Cond::All(vec![Cond::DayAtLeast(4), Cond::Not(Box::new(Cond::UnitAt { name: "courier", x: 10, y: 5 }))]),
            then: vec![Action::Lose],
        },
    ];
    b.triggers.push(Trigger::new(
        When::AfterAction,
        Cond::PlayerPair { a: co::STURM, b: co::HAWKE },
        vec![Action::Scene(Scene::new(vec![Line::say(co::HAWKE, "Together.")]))],
    ));
    b.triggers.push(Trigger::new(
        When::AfterAction,
        Cond::UnitAt { name: "courier", x: 5, y: 5 },
        vec![Action::Spawn(vec![UnitDef::new(1, unit::INFANTRY, 3, 3), UnitDef::new(1, unit::TANK, 4, 3)]), Action::AddFunds { army: 1, funds: 500 }],
    ));
    b.triggers.push(Trigger::new(When::TurnStart, Cond::UnitGone("courier"), vec![Action::Lose]));
    b.victory = Scene::new(vec![Line::say(co::STURM, "Extracted.")]);
    b.needs = Needs::All(vec!["f01"]);
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
    c.needs = Needs::All(vec!["f02"]);
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
    d.needs = Needs::All(vec!["f03"]);
    // (compiled, not played: the stage-2 pattern, a repeating strike, a rectangle, a function of its own)
    d.triggers = vec![
        Trigger::new(
            When::AfterAction,
            Cond::ArmyDefeated(2),
            vec![Action::SetCo { army: 3, co: co::HAWKE }, Action::Spawn(vec![UnitDef::new(3, unit::TANK, 0, 0)])],
        ),
        Trigger::new(When::TurnStart, Cond::EveryDays { n: 5, from: 5 }, vec![Action::Strike { hp: 8 }]).repeating(),
        Trigger::new(
            When::AfterAction,
            Cond::Any(vec![
                Cond::UnitsIn { army: 1, area: Rect::new(0, 0, 3, 3), at_least: 2 },
                Cond::OwnerAt { x: 1, y: 1, army: 1 },
                Cond::Custom(|core| day(core) > 99),
            ]),
            vec![Action::Custom(|_core| {})],
        ),
    ];
    d.flag = region::BLACK_HOLE[3];
    let mut f = MissionDef::new("f05", "Features Five");
    f.objective = "Test: Dual Strike's first campaign map.";
    f.map = MapSrc::Ds { record: 0 };
    f.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::ADDER)),
    ];
    f.needs = Needs::All(vec!["f04"]);
    f.flag = region::BLACK_HOLE[4];

    let mut g = MissionDef::new("f06", "Features Secret");
    g.objective = "Test: opens when every bond is earned.";
    g.map = MapSrc::Built("bh_example"); // (five/bh/example.txt: its tiles and units)
    g.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::VON_BOLT)),
    ];
    g.needs = Needs::Bonds(vec!["f01"]);
    g.recruits = vec![roster::SONJA];
    g.flag = region::BLACK_HOLE[5];

    // Five armies: the player is the fifth (Black Hole), a tag pair.
    let mut h = MissionDef::new("f07", "Features Five Armies");
    h.objective = "Test: five armies, the player the fifth.";
    h.map = MapSrc::Built("bh_five");
    h.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::ANDY)),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF)),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::EAGLE)),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KANBEI)),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::STURM, co::HAWKE)),
    ];
    h.needs = Needs::All(vec!["f01"]);
    h.flag = region::BLACK_HOLE[3];

    // A second stage: Nell's army (2) falls, Andy's (3, on her team, with a token
    // unit and an HQ of its own) takes over with reinforcements.
    let mut i = MissionDef::new("f08", "Features Stage Two");
    i.objective = "Test: when army 2 falls, army 3 takes over.";
    i.map = MapSrc::Ascii(&["1.........", "..........", "..........", "..........", "..2.......", "........3."]);
    i.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::NELL)).team(2),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::ANDY)).team(2),
    ];
    i.units = vec![
        UnitDef::new(1, unit::INFANTRY, 1, 1),
        UnitDef::new(2, unit::INFANTRY, 5, 4).hold(),
        UnitDef::new(3, unit::INFANTRY, 9, 5).hold().named("token"),
    ];
    i.triggers = vec![Trigger::new(
        // (the fall is known after the turn starts: after the player's first action)
        When::AfterAction,
        Cond::ArmyDefeated(2),
        vec![
            Action::Spawn(vec![UnitDef::new(3, unit::TANK, 7, 5), UnitDef::new(3, unit::TANK, 8, 4)]),
            Action::AddFunds { army: 3, funds: 9000 },
            Action::Scene(Scene::new(vec![Line::say(co::ANDY, "Stage two.")])),
        ],
    )];
    i.needs = Needs::All(vec!["f01"]);
    i.flag = region::BLACK_HOLE[5];

    // A lose trigger on a city: the Gate ('A': a city of army 1) is lost
    // when an enemy takes it.
    let mut j = MissionDef::new("f09", "Features Gate");
    j.objective = "Test: lose when the Gate city is captured.";
    j.map = MapSrc::Ascii(&["1....A....", "..........", "..........", "..........", "..2......."]);
    j.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::VON_BOLT)),
    ];
    j.units = vec![
        UnitDef::new(1, unit::INFANTRY, 1, 1),
        UnitDef::new(2, unit::INFANTRY, 8, 4).hold(),
        // low on purpose (an APC resupply would win such a mission)
        UnitDef::new(1, unit::TANK, 2, 2).ammo(2).fuel(30),
    ];
    j.triggers = vec![Trigger::new(
        When::AfterAction,
        Cond::Not(Box::new(Cond::OwnerAt { x: 5, y: 0, army: 1 })),
        vec![Action::Scene(Scene::new(vec![Line::say(co::STURM, "The Gate has fallen.")])), Action::Lose],
    )];
    j.needs = Needs::All(vec!["f01"]);
    j.flag = region::BLACK_HOLE[4];

    // A reversed Black Onyx: four allies (one team) against the player, army 5 (Black
    // Hole); the satellite fires every fifth day, the silos in the corners launch at it.
    let mut k = MissionDef::new("f10", "Features Onyx");
    k.objective = "Test: a reversed Black Onyx.";
    k.map = MapSrc::Built("bh_onyx");
    k.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::ANDY)).team(1),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF)).team(1),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::EAGLE)).team(1),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KANBEI)).team(1),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::STURM, co::HAWKE)),
    ];
    // (the allies' Tanks have no ammo and stay put: the test turns them into soldiers
    // for the silos and must not lose the mission to them)
    k.units = vec![
        UnitDef::new(1, unit::TANK, 4, 4).hold().ammo(0),
        UnitDef::new(2, unit::TANK, 11, 4).hold().ammo(0),
        UnitDef::new(3, unit::TANK, 4, 10).hold().ammo(0),
        UnitDef::new(4, unit::TANK, 11, 10).hold().ammo(0),
        UnitDef::new(5, unit::INFANTRY, 7, 5),
        UnitDef::new(5, unit::TANK, 8, 6),
    ];
    k.onyx = Some(OnyxDef::new((5, 7)));
    k.triggers = vec![
        Trigger::new(When::AfterAction, Cond::OnyxHitsAtMost(3), vec![Action::Scene(Scene::new(vec![Line::say(co::EAGLE, "One down.")]))]),
        Trigger::new(When::AfterAction, Cond::OnyxDestroyed, vec![Action::Scene(Scene::new(vec![Line::say(co::STURM, "The Onyx falls.")]))]),
    ];
    k.needs = Needs::All(vec!["f01"]);
    k.flag = region::BLACK_HOLE[2];

    // A computer Black Hole army on a map with no Black Factory (it must not
    // reset the game when the factory spawner runs for it).
    let mut m = MissionDef::new("f11", "Features No Factory");
    m.objective = "Test: a computer Black Hole army, no factory.";
    m.map = MapSrc::Ascii(&["1.........", "..........", "..........", "..........", ".........2"]);
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::ANDY)),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
    ];
    // (a Md Tank on the player's HQ: the computer's soldier cannot capture it)
    m.units = vec![UnitDef::new(1, unit::MD_TANK, 0, 0), UnitDef::new(1, unit::MD_TANK, 1, 1), UnitDef::new(2, unit::INFANTRY, 8, 3).hold()];
    m.needs = Needs::All(vec!["f01"]);
    m.flag = region::BLACK_HOLE[1];

    // Two fronts, a Black Factory on the main front only; the player's Black Hole army on the
    // second front is the computer's (Auto CO) and must not trip over the missing factory.
    let mut n = MissionDef::new("f12", "Features Two Fronts No Factory");
    n.objective = "Test: a second front without a factory.";
    n.map = MapSrc::Ascii(&["1.........", "..........", "..........", "..........", ".........2"]);
    n.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JUGGER)),
    ];
    n.structures = vec![(Structure::BlackFactory, 5, 2)];
    n.units = vec![UnitDef::new(1, unit::MD_TANK, 0, 0), UnitDef::new(1, unit::MD_TANK, 1, 1), UnitDef::new(2, unit::MD_TANK, 8, 3).hold()];
    n.front2 = Some(FrontDef {
        map: MapSrc::Ascii(&["1......", ".......", "......2"]),
        props: Vec::new(),
        structures: Vec::new(),
        units: vec![UnitDef::new(1, unit::MD_TANK, 0, 0), UnitDef::new(1, unit::MD_TANK, 1, 1), UnitDef::new(2, unit::MD_TANK, 5, 1).hold().named("carrier")],
        cos: [CoSpec::Fixed(co::HAWKE), CoSpec::Fixed(co::KOAL), CoSpec::None, CoSpec::None],
        send: SendRule::Ground,
        sky: false,
        weather: Weather::Clear,
        fog: false,
    });
    // The second front's own rules: its named unit destroyed is a scene and the front's win.
    n.front2_triggers = vec![Trigger::new(
        When::TurnStart,
        Cond::UnitGone("carrier"),
        vec![Action::Scene(Scene::new(vec![Line::say(co::HAWKE, "The carrier is down.")])), Action::Win],
    )];
    n.front2_victory = Scene::new(vec![Line::say(co::HAWKE, "The east is ours.")]);
    n.needs = Needs::All(vec!["f01"]);
    n.flag = region::BLACK_HOLE[3];

    // The player's Black Factory in a campaign mission picks what the battle needs
    // (crate::bh_smart): against many Bombers, and against many Md Tanks.
    let factory_mission = |key: &'static str, enemy: u8| {
        let mut q = MissionDef::new(key, "Features Factory");
        q.objective = "Test: the smart Black Factory.";
        q.map = MapSrc::Ascii(&["1.........", "..........", "..........", "..........", "..........", ".........2"]);
        q.armies = vec![
            ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
            ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::VON_BOLT)),
        ];
        q.structures = vec![(Structure::BlackFactory, 5, 2)];
        let mut units = vec![UnitDef::new(1, unit::MD_TANK, 0, 0), UnitDef::new(1, unit::INFANTRY, 1, 1)];
        for k in 0..6u8 {
            units.push(UnitDef::new(2, enemy, 6 + k % 4, 5 - k / 4).hold());
        }
        q.units = units;
        q.needs = Needs::All(vec!["f01"]);
        q.flag = region::BLACK_HOLE[0];
        q
    };
    let o = factory_mission("f13", unit::BOMBER);
    let r = factory_mission("f14", unit::MD_TANK);

    // A human Black Hole army's Laser and minicannon (AW2 only ever gave them to the computer):
    // they fire at the enemy on the player's turn.
    let mut u = MissionDef::new("f15", "Features Cannons");
    u.objective = "Test: the player's Laser and minicannon fire.";
    u.map = MapSrc::Ascii(&["1.........", "..........", "..........", "..........", "..........", "..........", ".........2"]);
    u.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::VON_BOLT)),
    ];
    u.structures = vec![(Structure::Laser, 2, 4), (Structure::MiniCannonRight, 0, 2)];
    u.units = vec![
        UnitDef::new(1, unit::MD_TANK, 0, 0),
        // (no fuel: the computer's tanks stay where the cannons can find them)
        UnitDef::new(2, unit::TANK, 7, 4).hold().fuel(0),
        UnitDef::new(2, unit::TANK, 2, 1).hold().fuel(0),
        UnitDef::new(2, unit::TANK, 3, 2).hold().fuel(0),
        UnitDef::new(2, unit::TANK, 9, 6).hold().fuel(0),
    ];
    u.needs = Needs::All(vec!["f01"]);
    u.flag = region::BLACK_HOLE[2];

    // A volcano as a neutral hazard: from day 3, every 2 days, three cells erupt for 3 HP
    // (any army's units there), marked from the day before.
    let mut w = MissionDef::new("f16", "Features Volcano");
    w.objective = "Test: a volcano erupts on a schedule.";
    w.map = MapSrc::Ascii(&[
        "1...............",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "..............2.",
    ]);
    w.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::VON_BOLT)),
    ];
    w.structures = vec![(Structure::Volcano, 2, 4)];
    w.volcano = Some(VolcanoDef::new(3, 2, 3, &[(6, 2), (7, 2), (6, 3)]));
    w.units = vec![
        UnitDef::new(1, unit::MD_TANK, 0, 0),
        UnitDef::new(1, unit::TANK, 6, 3).fuel(0),
        UnitDef::new(2, unit::TANK, 6, 2).hold().fuel(0),
        UnitDef::new(2, unit::TANK, 7, 2).hold().fuel(0).hp(20),
        UnitDef::new(2, unit::TANK, 8, 2).hold().fuel(0),
    ];
    w.needs = Needs::All(vec!["f01"]);
    w.flag = region::BLACK_HOLE[3];

    // A tag pair of the player's own pick from the whole roster.
    let mut y = MissionDef::new("f17", "Features Pair");
    y.objective = "Test: the player's pair from every CO.";
    y.map = MapSrc::Ascii(&["1.........", "..........", "..........", ".........2"]);
    y.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::VON_BOLT)),
    ];
    y.units = vec![UnitDef::new(1, unit::MD_TANK, 0, 0), UnitDef::new(2, unit::TANK, 9, 3).hold().ammo(0)];
    y.needs = Needs::All(vec!["f01"]);
    y.flag = region::BLACK_HOLE[1];

    // Black Hole's cannons owned by the player (army 5 in a five-army mission, army 1 in a
    // two-army one) must never hurt the player's own units.
    let own_cannons = |key: &'static str, five: bool| {
        let mut q = MissionDef::new(key, "Features Own Cannons");
        q.objective = "Test: the player's cannons spare the player's units.";
        if five {
            q.map = MapSrc::Built("bh_five");
            q.armies = vec![
                ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::ANDY)),
                ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF)),
                ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::EAGLE)),
                ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KANBEI)),
                ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
            ];
            q.structures = vec![(Structure::MiniCannonRight, 5, 7), (Structure::MiniCannonLeft, 9, 9), (Structure::Laser, 3, 5), (Structure::BlackCannonDown, 7, 3), (Structure::BlackCannonUp, 8, 12), (Structure::Deathray, 13, 8), (Structure::Volcano, 12, 4)];
            q.units = vec![
                // (APCs: no weapon at all; a Tank's machine gun needs no ammo)
                UnitDef::new(1, unit::APC, 3, 2).hold(),
                UnitDef::new(2, unit::APC, 12, 2).hold(),
                UnitDef::new(3, unit::APC, 3, 12).hold(),
                UnitDef::new(4, unit::APC, 12, 12).hold(),
                UnitDef::new(5, unit::TANK, 6, 7),
                UnitDef::new(5, unit::TANK, 8, 9),
                UnitDef::new(5, unit::INFANTRY, 7, 8),
                UnitDef::new(5, unit::INFANTRY, 4, 7),
            ];
        } else {
            q.map = MapSrc::Ascii(&["1.........", "..........", "..........", "..........", "..........", "..........", ".........2"]);
            q.armies = vec![
                ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
                ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::VON_BOLT)),
            ];
            q.structures = vec![(Structure::MiniCannonRight, 0, 2), (Structure::Laser, 2, 4), (Structure::BlackCannonDown, 6, 1), (Structure::Deathray, 8, 3)];
            q.units = vec![
                UnitDef::new(1, unit::MD_TANK, 0, 0),
                UnitDef::new(1, unit::TANK, 1, 1),
                UnitDef::new(1, unit::INFANTRY, 1, 3),
                UnitDef::new(1, unit::TANK, 3, 3),
                UnitDef::new(2, unit::APC, 9, 5).hold(),
            ];
        }
        q.needs = Needs::All(vec!["f01"]);
        q.flag = region::BLACK_HOLE[2];
        q
    };
    // Mission 28 of the design, as the act V builder has it (its map file, five armies, teams, Onyx, Volcano).
    let mut z = MissionDef::new("f20", "Features Fortress");
    z.objective = "Test: the fortress of five armies.";
    z.map = MapSrc::Built("bh28");
    z.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::RACHEL)).team(1).funds(12000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF)).team(1).funds(12000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::EAGLE)).team(1).funds(12000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KANBEI)).team(1).funds(12000),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::STURM, co::CLONE_ANDY)).funds(16000),
    ];
    z.look = 2;
    z.onyx = Some(OnyxDef::new((16, 14)));
    z.volcano = Some(VolcanoDef::new(3, 1, 5, &[(25, 15), (27, 15), (29, 15)]));
    z.needs = Needs::All(vec!["f01"]);
    z.flag = region::BLACK_HOLE[4];
    // Marches, a named spawn and a jammed minicannon: the walker (a Tank on row 0, a blocker
    // ahead of it) goes two cells a day, a named truck spawned on day 2 six move points (a forest cell costs two), the minicannon
    // (0,2) is jammed until day 4.
    let mut v = MissionDef::new("f21", "Features March");
    v.objective = "Test: marches, a named spawn, a jammed cannon.";
    v.map = MapSrc::Ascii(&["1...........", "......f.....", "............", "............", "..........2."]);
    v.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::VON_BOLT)),
    ];
    v.structures = vec![(Structure::MiniCannonRight, 0, 2)];
    v.units = vec![
        UnitDef::new(1, unit::MD_TANK, 0, 0),
        UnitDef::new(2, unit::TANK, 4, 0).hold().fuel(0).named("walker"),
        UnitDef::new(2, unit::INFANTRY, 7, 0).hold().fuel(0).named("blocker"),
        UnitDef::new(2, unit::TANK, 3, 2).hold().fuel(0),
    ];
    v.triggers = vec![on_day_spawn(2, vec![UnitDef::new(2, unit::APC, 4, 1).hold().fuel(0).named("truck")])];
    v.marches = vec![
        MarchDef::new("walker", &[(4, 0), (5, 0), (6, 0), (7, 0), (8, 0), (9, 0), (10, 0), (11, 0)], 2),
        MarchDef::speed("truck", &[(4, 1), (5, 1), (6, 1), (7, 1), (8, 1), (9, 1), (10, 1), (11, 1)], 6),
    ];
    v.jams = vec![JamDef { at: (0, 2), until: Cond::DayAtLeast(4) }];
    v.needs = Needs::All(vec!["f01"]);
    v.flag = region::BLACK_HOLE[3];
    let own2 = own_cannons("f18", false);
    let own5 = own_cannons("f19", true);

    CampaignDef {
        source: 1,
        roster: ROSTER.to_vec(),
        prologue: vec![Page { text: "Features.", picture: None, who: None }],
        credits: vec![
            CreditSection { heading: "FEATURES", names: vec!["TEST"], secret: false },
            CreditSection { heading: "SECRET LINE", names: vec!["THE AUDITOR"], secret: true },
        ],
        missions: vec![a, b, c, d, f, g, h, i, j, k, m, n, o, r, u, w, y, own2, own5, z, v],
        final_mission: "f21",
        bonds: vec![Bond { co: co::HAWKE, quote: "Bond test: Hawke's secret page." }, Bond { co: co::KOAL, quote: "Bond test: an extra." }],
        extra_bonds: 1,
        secret_mission: "f06",
    }
}

/// A trigger that spawns units at the start of the player's turn on day `d`.
fn on_day_spawn(d: u16, units: Vec<UnitDef>) -> Trigger {
    Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: d }, vec![Action::Spawn(units)]).repeating()
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
        assert_eq!(ROSTER[roster::CRUMB as usize].0, co::CRUMB);
        assert_eq!(BONDS[bond::CRUMB_QUOTE as usize].co, co::CRUMB);
        assert!(ROSTER.len() as u32 <= crate::ds_campaign::BOND_SHIFT, "the roster's bits stay under the bonds'");
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
        assert!(d.missions.iter().any(|m| m.key == d.final_mission));
    }
}
