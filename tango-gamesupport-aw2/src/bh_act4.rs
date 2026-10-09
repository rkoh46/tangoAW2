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


/// The player's lead CO is Sturm.
fn lead_is_sturm(core: &mut Core) -> bool {
    crate::tag::army_co_of(core, 1) == co::STURM
}

/// A win that also earns the recruit's bond when `affinity` holds for the player's CO.
fn win_with_bond(done: Cond, affinity: fn(&mut Core) -> bool, bond: u8) -> Vec<Trigger> {
    vec![
        after(Cond::All(vec![done.clone(), Cond::Custom(affinity)]), vec![Action::EarnBond(bond), Action::Win]),
        after(Cond::All(vec![done, Cond::Not(Box::new(Cond::Custom(affinity)))]), vec![Action::Win]),
    ]
}

/// The computer's roles for an act-4 army (AW2's AI byte): foot soldiers capture (3), every indirect and
/// most vehicles, aircraft and ships hunt units (4), every third direct-fire vehicle goes for the enemy HQ (1)
/// so the HQ is always under threat, and only the true garrisons `holds` names stay (0). The player's units
/// keep the default.
fn cpu_roles(units: Vec<UnitDef>, holds: impl Fn(&UnitDef) -> bool) -> Vec<UnitDef> {
    let mut vehicles = 0;
    units
        .into_iter()
        .map(|mut u| {
            if u.army != 1 {
                u.ai = if holds(&u) {
                    0
                } else {
                    match u.kind {
                        unit::INFANTRY | unit::MECH => 3,
                        unit::ARTILLERY | unit::ROCKETS | unit::MISSILES => 4,
                        _ => {
                            vehicles += 1;
                            if vehicles % 3 == 0 { 1 } else { 4 }
                        }
                    }
                };
            }
            u
        })
        .collect()
}

/// A new reinforcement that advances on the enemy HQ.
fn go_new(army: u8, kind: u8, x: u8, y: u8) -> UnitDef {
    go(UnitDef::new(army, kind, x, y))
}

/// A reinforcement that advances on the enemy HQ.
fn go(mut u: UnitDef) -> UnitDef {
    u.ai = match u.kind {
        unit::INFANTRY | unit::MECH => 3,
        unit::ARTILLERY | unit::ROCKETS | unit::MISSILES => 4,
        _ => 1,
    };
    u
}

// --- World map ---------------------------------------------------------------------

/// Act 4's flags on AW2's Blue Moon (the south land), in play order: M17 .. M22.
pub const FLAGS: [(i16, i16); 6] = region::BLUE_MOON;

// --- M17 Cold Iron -------------------------------------------------------------------

fn bh17() -> MissionDef {
    let mut m = MissionDef::new("bh17", "Cold Iron");
    m.objective = "Capture Jugger's foundry HQ.";
    m.map = MapSrc::Built("bh17");
    // Jugger's roles: his Md Tanks, Mech and field Infantry advance by the odds; the Missiles (fire from
    // behind), the Neotank (the HQ's anchor) and the two Infantry at the HQ hold.
    m.units = cpu_roles(built_units("bh17"), |u| u.kind == unit::NEOTANK || (u.kind == unit::INFANTRY && u.x >= 21));
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(9000),
        // Jugger in Blue Moon's colours; Grit, the sniper, babysits him.
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Pair(co::JUGGER, co::GRIT)).funds(18000),
    ];
    m.fog = true;
    m.day_limit = 22;
    m.rank_days = 14;
    m.intro = crate::bh_text::scene("m17_pre");
    m.victory = crate::bh_text::scene("m17_post");
    m.after = crate::bh_text::scene("m17_map");
    m.triggers = vec![
        on_day(4, None, vec![Action::Scene(crate::bh_text::scene("m17_day4"))]),
        on_day(7, None, vec![Action::Scene(crate::bh_text::scene("m17_day7"))]),
        on_day(10, None, vec![Action::Scene(crate::bh_text::scene("m17_day10"))]),
    ];
    // Jugger's bond: Hawke is in the player's pair (lead or partner).
    let jugger_down = beaten(2, (21, 9));
    m.triggers.push(after(Cond::All(vec![jugger_down.clone(), Cond::PlayerHas(co::HAWKE)]), vec![Action::EarnBond(4), Action::Win]));
    m.triggers.push(after(Cond::All(vec![jugger_down, Cond::Not(Box::new(Cond::PlayerHas(co::HAWKE)))]), vec![Action::Win]));
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
    // Flak just charges: everyone advances on the player's HQ, but the two Neotanks stay by his own.
    m.units = cpu_roles(built_units("bh18"), |u| u.kind == unit::NEOTANK);
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(4000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::FLAK)).funds(10000),
    ];
    m.day_limit = 12;
    m.rank_days = 9;
    m.intro = crate::bh_text::scene("m18_pre");
    m.victory = crate::bh_text::scene("m18_post");
    m.after = crate::bh_text::scene("m18_map");
    m.triggers = vec![
        on_day(6, None, vec![Action::Scene(crate::bh_text::scene("m18_day6"))]),
        on_day(10, None, vec![Action::Scene(crate::bh_text::scene("m18_day10"))]),
    ];
    // Win: rout Flak, or take the throne in the arena's heart. Flak's bond: Sturm leads.
    m.triggers.extend(win_with_bond(Cond::Any(vec![beaten(2, (10, 1)), Cond::OwnerAt { x: 10, y: 10, army: 1 }]), lead_is_sturm, 5));
    m.recruits = vec![roster::FLAK];
    m.needs = Needs::All(vec!["bh17"]);
    m.flag = FLAGS[1];
    m.stars = 3;
    m
}

// --- M19 The Assembly Line -----------------------------------------------------------

/// Factory table F19 (docs/BH_CAMPAIGN.md 3.5 M19): per day the three doors' units (0 none).
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
    // Sasha's roles: the line (Infantry, Mech, treads, the Megatank, the aircraft) advances; the Artillery,
    // Missiles and Anti-Air screen hold their ground, as do the Infantry round her HQ.
    m.units = cpu_roles(built_units("bh19"), |u| u.kind == unit::INFANTRY && u.x >= 26);
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(7000),
        // Sasha, with real production: 5 bases, 2 airports, 9 cities.
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::SASHA)).funds(45000),
    ];
    m.day_limit = 28;
    m.rank_days = 18;
    m.factory = F19.to_vec();
    m.intro = crate::bh_text::scene("m19_pre");
    m.victory = crate::bh_text::scene("m19_post");
    m.after = crate::bh_text::scene("m19_map");
    m.triggers = vec![
        on_day(4, None, vec![Action::Scene(crate::bh_text::scene("m19_day4"))]),
        // Sasha's funds: +6000 on days 8 and 16.
        on_day(8, None, vec![Action::AddFunds { army: 2, funds: 6000 }, Action::Scene(crate::bh_text::scene("m19_day8"))]),
        on_day(16, None, vec![Action::AddFunds { army: 2, funds: 6000 }, Action::Scene(crate::bh_text::scene("m19_day16"))]),
        after(beaten(2, (29, 12)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh17"]);
    m.flag = FLAGS[2];
    m.stars = 4;
    m
}

// --- M20 Moonlit Harbours ------------------------------------------------------------

fn second_front_won(core: &mut Core) -> bool {
    core.raw_read_8(0x0203_E401, -1) == 2
}

fn bh20() -> MissionDef {
    let mut m = MissionDef::new("bh20", "Moonlit Harbours");
    m.objective = "Take Olaf's HQ; win the sea front for a partner.";
    m.map = MapSrc::Built("bh20");
    // Olaf advances, but his Artillery and the Infantry on his HQ hold.
    m.units = cpu_roles(built_units("bh20"), |u| u.kind == unit::INFANTRY && u.x >= 21);
    m.look = 1; // Snow
    m.weather = Weather::Snow;
    // The player picks two COs: the main front's, then the second front's.
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(10000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF)).funds(18000),
    ];
    m.day_limit = 24;
    m.rank_days = 16;
    // (no Black Factory on either front: the engine's spawner guard keeps the computer's quiet)
    // Colin's fleet: Cruisers and Subs hunt; the Battleships and the Carrier hold the line off his shelf, the
    // Landers and the Infantry waiting on his ports hold until the computer ships them over.
    let mut sea = built_units("bh20b");
    sea.push(UnitDef::new(2, unit::CARRIER, 17, 8));
    let sea = cpu_roles(sea, |u| matches!(u.kind, unit::LANDER | unit::INFANTRY));
    // The sea front is won as AW2's rules decide it (the enemy routed, or its east shelf's HQ taken
    // by the Lander: the east port (18, 5), (18, 11) are the way in; `two_front` has no per-front triggers).
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
    m.intro = crate::bh_text::scene("m20_pre");
    m.victory = crate::bh_text::scene("m20_post");
    m.after = crate::bh_text::scene("m20_map");
    // The sea front's winner reports to the main front as the tag partner (any CO the player picked).
    m.triggers = vec![
        Trigger::new(When::TurnStart, Cond::Custom(second_front_won), vec![Action::Scene(crate::bh_text::scene("m20_front2_post"))]),
        on_day(8, None, vec![Action::Scene(crate::bh_text::scene("m20_day8"))]),
        after(beaten(2, (23, 9)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh18", "bh19"]);
    m.flag = FLAGS[3];
    m.stars = 4;
    m
}

// --- M21 Running Dry -----------------------------------------------------------------

/// Fourteen of the forward column's twenty units start low, by design (the mission is the retreat and the
/// resupply): nine with no ammunition at all (Artillery, Rockets, Missiles, the B Copter, the Md Tanks) and five
/// with one shot (Tanks, Mech). The Infantry, the Recon and the Anti-Air (the cover) are full. The B Copter's
/// fuel is low but safe (28: an air unit crashes at 0 fuel). (type, ammo, fuel)
const COLUMN: [(u8, u8, u8); 7] = [
    (unit::MD_TANK, 0, 25),
    (unit::ARTILLERY, 0, 25),
    (unit::ROCKETS, 0, 25),
    (unit::MISSILES, 0, 25),
    (unit::B_COPTER, 0, 28),
    (unit::TANK, 1, 30),
    (unit::MECH, 1, FULL),
];

/// The units that start with no ammunition at all (the six guns the convoy must refill).
fn is_empty_gun(kind: u8) -> bool {
    matches!(kind, unit::ARTILLERY | unit::ROCKETS | unit::MISSILES | unit::B_COPTER)
}

/// How many of the six empty guns have been supplied: they hold ammunition again (a unit record's bits
/// 7..10 of its word at +4 are its ammo).
fn supplied(core: &mut Core) -> usize {
    units_of(core, 1).iter().filter(|u| is_empty_gun(u.1) && (core.raw_read_16(u.0 + 4, -1) >> 7) & 0xF > 0).count()
}

/// The resupply is under way: four of the six empty guns have shells again (the counter-attack opens).
fn resupplied(core: &mut Core) -> bool {
    supplied(core) >= 4
}

/// The supply is cut: the convoys have come (day 7 on) and no APC is left before the guns were refilled.
fn supply_cut(core: &mut Core) -> bool {
    day(core) >= 7 && units_of(core, 1).iter().all(|u| u.1 != unit::APC) && supplied(core) < 4
}

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
    // Max's army charges (all advance); Grit's Artillery and Missiles hold their ridge to shell the bridges.
    m.units = cpu_roles(built_units("bh21"), |_| false)
        .into_iter()
        .map(|u| match COLUMN.iter().find(|c| u.army == 1 && c.0 == u.kind) {
            Some(&(_, ammo, fuel)) => u.ammo(ammo).fuel(fuel),
            None => u,
        })
        .collect();
    m.intro = crate::bh_text::scene("m21_pre");
    m.victory = crate::bh_text::scene("m21_post");
    m.after = crate::bh_text::scene("m21_map");
    // The convoys (Black Hole's reinforcements from the west edge), Max's raiders and the second wave.
    m.triggers = vec![
        on_day(
            3,
            None,
            vec![
                Action::Spawn(vec![
                    UnitDef::new(1, unit::APC, 0, 10),
                    UnitDef::new(1, unit::MD_TANK, 1, 10),
                    UnitDef::new(1, unit::MD_TANK, 0, 9),
                    UnitDef::new(1, unit::RECON, 0, 11),
                ]),
                Action::Scene(crate::bh_text::scene("m21_day3")),
            ],
        ),
        on_day(
            4,
            None,
            vec![
                Action::Spawn(vec![
                    go_new(2, unit::RECON, 27, 15),
                    go_new(2, unit::RECON, 27, 14),
                    go_new(2, unit::TANK, 26, 14),
                    go_new(2, unit::TANK, 26, 12),
                ]),
                Action::Scene(crate::bh_text::scene("m21_day4")),
            ],
        ),
        on_day(
            6,
            None,
            vec![
                Action::Spawn(vec![
                    UnitDef::new(1, unit::APC, 0, 16),
                    UnitDef::new(1, unit::APC, 1, 16),
                    UnitDef::new(1, unit::TANK, 0, 15),
                ]),
                Action::Scene(crate::bh_text::scene("m21_day6")),
            ],
        ),
        on_day(
            9,
            None,
            vec![
                Action::Spawn(vec![
                    go_new(2, unit::MD_TANK, 27, 16),
                    go_new(2, unit::MD_TANK, 27, 12),
                    go_new(2, unit::NEOTANK, 27, 17),
                    go_new(3, unit::ROCKETS, 26, 3),
                    go_new(3, unit::ROCKETS, 27, 4),
                ]),
                Action::Scene(crate::bh_text::scene("m21_day9")),
            ],
        ),
        // The counter-attack opens when the guns have shells again.
        Trigger::new(
            When::AfterAction,
            Cond::Custom(resupplied),
            vec![Action::Scene(crate::bh_text::scene("m21_resupplied"))],
        ),
        // The supply is cut: the convoys' APCs are all gone before the guns were refilled.
        after(
            Cond::Custom(supply_cut),
            vec![
                Action::Scene(crate::bh_text::scene("m21_supply_cut")),
                Action::Lose,
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
    // Olaf and Sasha: the line and the Fighters advance; Artillery, Missiles and the four palace-gate
    // Infantry (row 3) hold.
    m.units = cpu_roles(built_units("bh22"), |u| u.kind == unit::INFANTRY && u.y <= 3);
    m.look = 1; // Snow
    m.weather = Weather::Snow;
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::JUGGER, co::FLAK)).funds(12000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Pair(co::OLAF, co::SASHA)).funds(28000),
    ];
    m.day_limit = 24;
    m.rank_days = 16;
    m.intro = crate::bh_text::scene("m22_pre");
    m.victory = crate::bh_text::scene("m22_post");
    // The end of Act IV: the camp, then the Allied council Black Hole's relay overhears.
    m.after = Scene::new({
        let mut v = crate::bh_text::lines("m22_map");
        v.extend(crate::bh_text::lines("m22_warroom"));
        v
    });
    m.triggers = vec![
        on_day(6, None, vec![Action::Scene(crate::bh_text::scene("m22_day6"))]),
        on_day(12, None, vec![Action::Scene(crate::bh_text::scene("m22_day12"))]),
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
