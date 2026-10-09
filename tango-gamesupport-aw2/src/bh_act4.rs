//! Act 4: Blue Moon (M17 to M22). Its missions are `MissionDef`s
//! (docs/AW2.md "BH Campaign": adding a mission); this file is the act's alone,
//! so builders can work on acts in parallel. A mission names what it needs by
//! key (`Needs::All(vec!["bh16"])`), not by index.
//!
//! The maps are `five/bh/bh17.txt` .. `bh22.txt` (+ `bh20b.txt`, the second front of M20),
//! built by `five/bhmap.py` into `bh_map_data.rs`: roads, rivers, coasts and shoals joined as
//! AW2 draws them, reachability checked. The dialogue is the design bible's
//! (docs/BH_CAMPAIGN.md section 4.5, branch bh-design): a design row is one box,
//! its `@IF CO` groups are `Line::only` lines, its soldiers and narration the
//! Black Hole trooper's face.

// (the builders' imports: each act uses what it needs)
#![allow(unused_imports)]

use mgba::core::Core;

use crate::bh_campaign::{region, roster};
use crate::campaign_model::SendRule;
use crate::custom_campaign::{co, colour, unit, *};

// --- Writing helpers ---------------------------------------------------------------

/// Until the conditional scene lines (`Line::only`, act 2's engine change) are in this tree: a line for
/// one CO shows for every CO (an inherent `Line::only` wins over this once the engine has it).
trait OnlyFor {
    fn only(self, c: u8) -> Line;
}

impl OnlyFor for Line {
    fn only(self, _c: u8) -> Line {
        self
    }
}

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

/// The enemy army is as good as routed: at most one unit left (the match's own rout, the last unit's
/// death, is decided before a trigger can play the victory scene and earn the bond), or its HQ is the
/// player's.
fn beaten(enemy: u8, hq: (u8, u8)) -> Cond {
    Cond::Any(vec![Cond::ArmyUnitsAtMost { army: enemy, n: 1 }, Cond::OwnerAt { x: hq.0, y: hq.1, army: 1 }])
}

/// The units of a built map's text file (its deployment), as the mission's own list.
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

/// Act 4's flags on AW2's Blue Moon (the south land), in play order: M17 .. M22.
pub const FLAGS: [(i16, i16); 6] = region::BLUE_MOON;

// --- M17 Cold Iron -------------------------------------------------------------------

fn bh17() -> MissionDef {
    let mut m = MissionDef::new("bh17", "Cold Iron");
    m.objective = "Capture Jugger's foundry HQ.";
    m.map = MapSrc::Built("bh17");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(9000),
        // Jugger in Blue Moon's colours.
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::JUGGER)).funds(18000),
    ];
    m.fog = true;
    m.day_limit = 22;
    m.rank_days = 14;
    m.intro = Scene::new(vec![
        troop("Blue Moon. A dead foundry. Cold iron, colder steel."),
        say(co::JUGGER, "INTRUDERS DETECTED. COUNT: FIVE. OR SIX."),
        say(co::JUGGER, "IDENTIFY. ANSWER IN COMPLETE SENTENCES."),
        troop("Hello, sir! I am a Private!"),
        say(co::JUGGER, "PRIVATE: A RANK. A HUNGRY ONE."),
        say(co::JUGGER, "I AM JUGGER. I WAS A BLUE MOON UNIT. I AM IDLE."),
        say(co::JUGGER, "BLUE MOON SAID \"TOO LITERAL\". QUERY: WHY?"),
        say(co::JUGGER, "PROVE YOU ARE NOT INEFFICIENT. WIN."),
        say(co::JUGGER, "ELSE I RETIRE YOU FROM THE MAP."),
        say(co::KOAL, "A machine that follows lanes. I approve.").only(co::KOAL),
        say(co::JUGGER, "LANES: ADEQUATE. SHOULDERS: UNKNOWN.").only(co::KOAL),
        say(co::HAWKE, "Fog and steel. A lovely board.").only(co::HAWKE),
    ]);
    m.triggers = vec![
        on_day(4, None, vec![Action::Scene(Scene::new(vec![say(co::JUGGER, "ODDS: 61 PERCENT. YOUR ODDS: LOWER.")]))]),
        on_day(10, None, vec![Action::Scene(Scene::new(vec![say(co::JUGGER, "RECALCULATING. ...RECALCULATING.")]))]),
        after(beaten(2, (21, 9)), vec![Action::Win]),
    ];
    m.recruits = vec![roster::JUGGER];
    m.needs = Needs::All(vec!["bh16"]);
    m.flag = FLAGS[0];
    m.stars = 3;
    m
}

// --- M18 The Pit ---------------------------------------------------------------------

fn bh18() -> MissionDef {
    let mut m = MissionDef::new("bh18", "The Pit");
    m.objective = "Rout Flak or take the arena throne. 12 days.";
    m.map = MapSrc::Built("bh18");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(4000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::FLAK)).funds(10000),
    ];
    m.day_limit = 12;
    m.rank_days = 9;
    m.intro = Scene::new(vec![
        troop("Blue Moon's Pit. A ring of seats, a crowd, a roar."),
        say(co::FLAK, "Hey! Little guys! Flak fights anything! For money!"),
        say(co::FLAK, "Blue Moon pays Flak in coins. Coins don't fight back."),
        say(co::FLAK, "You fight back? Good. Flak likes it."),
        say(co::FLAK, "Bell is twelve rounds. Win, boss. Lose, snack."),
        say(co::HAWKE, "Private Flak. I made you a sergeant once."),
        say(co::FLAK, "Hee! Hawke! Flak remembers! Stripes! And ham!"),
        say(co::HAWKE, "I regret the ham."),
        say(co::STURM, "Twelve days. Then you are mine.").only(co::STURM),
        say(co::FLAK, "Hee! Big words! Flak hits bigger!").only(co::STURM),
        troop("Sir, he is very large. Is he nice?"),
        say(co::FLAK, "Flak is nice! Flak is Nice Flak!"),
    ]);
    m.triggers = vec![
        on_day(6, None, vec![Action::Scene(Scene::new(vec![say(co::FLAK, "Bell! Bell! Next round!")]))]),
        on_day(10, None, vec![Action::Scene(Scene::new(vec![say(co::FLAK, "Hit me harder! Flak is sleepy!")]))]),
        // Win: rout Flak, or take the throne in the arena's heart.
        after(Cond::Any(vec![beaten(2, (10, 1)), Cond::OwnerAt { x: 10, y: 10, army: 1 }]), vec![Action::Win]),
    ];
    m.recruits = vec![roster::FLAK];
    m.needs = Needs::All(vec!["bh17"]);
    m.flag = FLAGS[1];
    m.stars = 3;
    m
}

// --- M19 The Assembly Line -----------------------------------------------------------

/// Factory table F19 (docs/BH_CAMPAIGN.md 3.5 M19): per day the three doors' units (0 none).
#[allow(dead_code)]
const F19: [(u8, [u8; 3]); 9] = [
    (2, [unit::TANK, unit::TANK, 0]),
    (3, [0, unit::MD_TANK, 0]),
    (5, [unit::NEOTANK, 0, unit::NEOTANK]),
    (6, [unit::MISSILES, 0, unit::ROCKETS]),
    (8, [0, unit::MEGATANK, 0]),
    (10, [unit::MD_TANK, unit::MD_TANK, 0]),
    (12, [unit::NEOTANK, unit::MECH, unit::NEOTANK]),
    (14, [0, unit::NEOTANK, 0]),
    (16, [unit::ROCKETS, unit::ANTI_AIR, unit::ROCKETS]),
];

fn bh19() -> MissionDef {
    let mut m = MissionDef::new("bh19", "The Assembly Line");
    m.objective = "Wake the Black Factory, hold the river, take Sasha's HQ.";
    m.map = MapSrc::Built("bh19");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(7000),
        // Sasha, with real production: 5 bases, 2 airports, 9 cities.
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::SASHA)).funds(45000),
    ];
    m.day_limit = 28;
    m.rank_days = 18;
    // TODO(merge act 2's engine change): `m.factory = F19.to_vec();` (the per-mission Black Factory table).
    m.intro = Scene::new(vec![
        say(co::SASHA, "Welcome to my assembly line. Hands off the wiring."),
        say(co::SASHA, "Every shell, every tank: invoiced in advance."),
        say(co::SASHA, "I could buy a war. I would rather buy your retreat."),
        say(co::SASHA, "Name a price. I will pay triple not to fight."),
        say(co::VON_BOLT, "Triple?! Sturm, hear the lady's offer!"),
        say(co::STURM, "No."),
        say(co::VON_BOLT, "But triple!"),
        say(co::SASHA, "Von Bolt. We should talk. In private."),
        say(co::VON_BOLT, "...Hm."),
        say(co::HAWKE, "Colonel."),
        say(co::VON_BOLT, "I was only listening."),
        say(co::VON_BOLT, "Triple is a start. Let us discuss quadruple.").only(co::VON_BOLT),
    ]);
    m.triggers = vec![
        on_day(4, None, vec![Action::Scene(Scene::new(vec![say(co::SASHA, "Ten more tanks, invoiced. Do try to keep up.")]))]),
        // Sasha's funds: +6000 on days 8 and 16.
        on_day(8, None, vec![Action::AddFunds { army: 2, funds: 6000 }, Action::Scene(Scene::new(vec![say(co::SASHA, "Funds arrive. Delightful.")]))]),
        on_day(16, None, vec![Action::AddFunds { army: 2, funds: 6000 }, Action::Scene(Scene::new(vec![say(co::SASHA, "Do not worry. I will bill you for the repairs.")]))]),
        after(beaten(2, (29, 12)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh17"]);
    m.flag = FLAGS[2];
    m.stars = 4;
    m
}

// --- M20 Moonlit Harbours ------------------------------------------------------------

fn bh20() -> MissionDef {
    let mut m = MissionDef::new("bh20", "Moonlit Harbours");
    m.objective = "Take Olaf's HQ; win the sea front for a partner.";
    m.map = MapSrc::Built("bh20");
    m.look = 1; // Snow
    m.weather = Weather::Snow;
    // The player picks two COs: the main front's, then the second front's.
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(10000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF)).funds(18000),
    ];
    m.day_limit = 24;
    m.rank_days = 16;
    let mut sea = built_units("bh20b");
    sea.push(UnitDef::new(2, unit::CARRIER, 16, 8));
    m.front2 = Some(FrontDef {
        map: MapSrc::Built("bh20b"),
        props: Vec::new(),
        structures: Vec::new(),
        units: sea,
        cos: [CoSpec::Pick, CoSpec::Fixed(co::COLIN), CoSpec::None, CoSpec::None],
        send: SendRule::Ground,
        sky: false,
        weather: Weather::Clear,
        fog: false,
    });
    m.intro = Scene::new(vec![
        say(co::OLAF, "Behold Snow Harbour! Behold OLAF, the pride of Blue Moon!"),
        say(co::OLAF, "A cold front, a cold fleet, and a hot heart!"),
        say(co::COLIN, "H-hi! I'm Colin! My sister got me a navy! A big one!"),
        say(co::COLIN, "It's, um, very big. ...Is it big?"),
        say(co::OLAF, "Colin, my boy, it is HUGE! Leave the rest to Olaf!"),
        say(co::HAWKE, "Harbour front, open sea. Choose two hands."),
    ]);
    m.triggers = vec![
        on_day(8, None, vec![Action::Scene(Scene::new(vec![say(co::COLIN, "Whoa! They sank my Cruiser! That was a gift!")]))]),
        after(beaten(2, (23, 9)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh18", "bh19"]);
    m.flag = FLAGS[3];
    m.stars = 4;
    m
}

// --- M21 Running Dry -----------------------------------------------------------------

/// The player's forward column starts low on ammunition and fuel (docs/BH_CAMPAIGN.md 3.5 M21):
/// (type, ammo, fuel); the Infantry need no ammunition.
const COLUMN: [(u8, u8, u8); 9] = [
    (unit::MECH, 1, FULL),
    (unit::RECON, 3, 40),
    (unit::TANK, 2, 30),
    (unit::MD_TANK, 1, 25),
    (unit::ARTILLERY, 0, 25),
    (unit::ROCKETS, 0, 25),
    (unit::MISSILES, 0, 25),
    (unit::ANTI_AIR, 3, 30),
    (unit::B_COPTER, 0, 20),
];

fn bh21() -> MissionDef {
    let mut m = MissionDef::new("bh21", "Running Dry");
    m.objective = "Fall back, hold the river, resupply, then take both HQs.";
    m.map = MapSrc::Built("bh21");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(3000),
        // Max (Orange Star) and Grit (Blue Moon) are allies.
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::MAX)).team(2).funds(9000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::GRIT)).team(2).funds(9000),
    ];
    m.fog = true;
    m.day_limit = 26;
    m.rank_days = 18;
    // The column: low ammunition and fuel for the types listed in COLUMN.
    m.units = built_units("bh21")
        .into_iter()
        .map(|u| match COLUMN.iter().find(|c| u.army == 1 && c.0 == u.kind) {
            Some(&(_, ammo, fuel)) => u.ammo(ammo).fuel(fuel),
            None => u,
        })
        .collect();
    m.intro = Scene::new(vec![
        troop("Blue Moon, the river valley. Far from supply."),
        troop("Sir... my canteen is empty. So are the Tanks'."),
        troop("Everything is empty, Crumb. The convoy is late."),
        say(co::HAWKE, "The convoy left port on time. The road did not."),
        say(co::MAX, "Hey! Black Hole! You look thirsty!"),
        say(co::GRIT, "Easy there, Max. They're near out of shells. Make it count."),
        say(co::MAX, "That's the best news all day! Charge, charge, charge!"),
        say(co::HAWKE, "Hold until the convoy arrives. Then we cross back."),
    ]);
    // The convoys (Black Hole's reinforcements from the west edge), Max's raiders and the second wave.
    m.triggers = vec![
        on_day(
            3,
            None,
            vec![
                Action::Scene(Scene::new(vec![troop("Sir! Biscuit delivery! One APC, two tanks, me!")])),
                Action::Spawn(vec![
                    UnitDef::new(1, unit::APC, 0, 10),
                    UnitDef::new(1, unit::MD_TANK, 1, 10),
                    UnitDef::new(1, unit::MD_TANK, 0, 9),
                    UnitDef::new(1, unit::RECON, 0, 11),
                ]),
            ],
        ),
        on_day(
            4,
            None,
            vec![Action::Spawn(vec![
                UnitDef::new(2, unit::RECON, 26, 15),
                UnitDef::new(2, unit::RECON, 26, 14),
                UnitDef::new(2, unit::TANK, 24, 15),
                UnitDef::new(2, unit::TANK, 23, 15),
            ])],
        ),
        on_day(
            6,
            None,
            vec![
                Action::Scene(Scene::new(vec![troop("Second convoy, sir! Two more APCs, full of shells!")])),
                Action::Spawn(vec![
                    UnitDef::new(1, unit::APC, 0, 16),
                    UnitDef::new(1, unit::APC, 1, 16),
                    UnitDef::new(1, unit::TANK, 0, 15),
                ]),
            ],
        ),
        on_day(
            9,
            None,
            vec![
                Action::Scene(Scene::new(vec![say(co::MAX, "More tanks! Everybody, push! Push!")])),
                Action::Spawn(vec![
                    UnitDef::new(2, unit::MD_TANK, 24, 15),
                    UnitDef::new(2, unit::MD_TANK, 23, 14),
                    UnitDef::new(2, unit::NEOTANK, 24, 17),
                    UnitDef::new(3, unit::ROCKETS, 24, 4),
                    UnitDef::new(3, unit::ROCKETS, 23, 4),
                ]),
            ],
        ),
        after(Cond::All(vec![beaten(2, (25, 16)), beaten(3, (25, 4))]), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh20"]);
    m.flag = FLAGS[4];
    m.stars = 4;
    m
}

// --- M22 Whiteout --------------------------------------------------------------------

fn bh22() -> MissionDef {
    let mut m = MissionDef::new("bh22", "Whiteout");
    m.objective = "Cross the frozen lake and take the Moon Palace.";
    m.map = MapSrc::Built("bh22");
    m.look = 1; // Snow
    m.weather = Weather::Snow;
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(12000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Pair(co::OLAF, co::SASHA)).funds(28000),
    ];
    m.day_limit = 24;
    m.rank_days = 16;
    m.intro = Scene::new(vec![
        say(co::OLAF, "This is my palace! Come at me in the blizzard!"),
        say(co::SASHA, "The Moon Palace. We fight for the people inside."),
        say(co::SASHA, "Not for gold. ...Mostly not for gold."),
        say(co::OLAF, "Whiteout, friends! Cold enough to freeze fire!"),
        say(co::STURM, "Weather obeys. So will you.").only(co::STURM),
    ]);
    m.triggers = vec![
        on_day(6, None, vec![Action::Scene(Scene::new(vec![say(co::OLAF, "Whiteout! Everyone loses their way!")]))]),
        on_day(12, None, vec![Action::Scene(Scene::new(vec![say(co::SASHA, "Reinforcements! Pay them triple!")]))]),
        after(beaten(2, (14, 3)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh21"]);
    m.flag = FLAGS[5];
    m.stars = 5;
    m
}

/// Act 4's missions, in world-map order.
pub fn missions() -> Vec<MissionDef> {
    let mut v = Vec::new();
    // (until act 3's M16 is in the tree, a placeholder keeps act 4's `needs` valid)
    if !crate::bh_act3::missions().iter().any(|m| m.key == "bh16") {
        v.push(dev_stub_bh16());
    }
    v.push(bh17());
    v.push(bh18());
    v.push(bh19());
    v.push(bh20());
    v.push(bh21());
    v.push(bh22());
    // The day limit loses: the day after the last is the defeat (the header's counter only shows it).
    for m in v.iter_mut().filter(|m| m.key >= "bh17") {
        if m.day_limit > 0 {
            let up = Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: m.day_limit + 1 }, vec![Action::Lose]).repeating();
            m.triggers.push(up);
        }
    }
    v
}

/// Development fallback: a stand-in for act 3's M16 when it is not in the tree yet.
fn dev_stub_bh16() -> MissionDef {
    let mut m = MissionDef::new("bh16", "Placeholder Sixteen");
    m.objective = "Rout the Yellow Comet force.";
    m.map = MapSrc::Ascii(&["1.........", "..ff..c...", "....mm....", "...c..c...", ".........2"]);
    m.armies = vec![ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)), ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KINDLE))];
    m.units = vec![UnitDef::new(1, unit::INFANTRY, 1, 1), UnitDef::new(2, unit::INFANTRY, 8, 3)];
    m.needs = Needs::All(vec!["bh02"]);
    m.flag = region::YELLOW_COMET[5];
    m.stars = 3;
    m
}
