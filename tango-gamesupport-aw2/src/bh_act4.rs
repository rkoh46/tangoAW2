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

/// Narration and the soldiers (Crumb, Mortar, Wick, "Soldier"): the Black Hole trooper's face.
fn troop(text: &'static str) -> Line {
    Line::soldier(colour::BLACK_HOLE, text)
}

fn say(c: u8, text: &'static str) -> Line {
    Line::say(c, text)
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


/// The COs the player may lead in Act 4 (the roster up to Flak).
const ALL_COS: [u8; 7] = [co::STURM, co::VON_BOLT, co::HAWKE, co::KOAL, co::KINDLE, co::JUGGER, co::FLAK];

/// One row for each of these COs, spoken by that CO and shown for its own player ([CO] in the design).
fn each(cos: &[u8], text: &'static str) -> Vec<Line> {
    cos.iter().map(|&c| say(c, text).only(c)).collect()
}

/// The player's lead CO is Hawke / Sturm.
fn lead_is_hawke(core: &mut Core) -> bool {
    crate::tag::army_co_of(core, 1) == co::HAWKE
}

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

/// The computer's roles (UnitDef::ai: 0 holds its ground, 1 goes for the enemy HQ): every enemy unit
/// advances except those `holds` names (indirect fire, HQ guards and a few anchors: each mission says
/// which and why). The player's own units keep the default.
fn roles(units: Vec<UnitDef>, holds: impl Fn(&UnitDef) -> bool) -> Vec<UnitDef> {
    units
        .into_iter()
        .map(|mut u| {
            if u.army != 1 {
                u.ai = if holds(&u) { 0 } else { 1 };
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
    u.ai = 1;
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
    m.units = roles(built_units("bh17"), |u| matches!(u.kind, unit::MISSILES | unit::NEOTANK) || (u.kind == unit::INFANTRY && u.x >= 21));
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
        say(co::KOAL, "Three metres wide, machine. Learn it.").only(co::KOAL),
        say(co::HAWKE, "Fog and steel. A lovely board.").only(co::HAWKE),
    ]);
    let mut post = vec![
        sad(co::JUGGER, "ERROR. DEFEAT. THIS IS UNEXPECTED."),
        say(co::JUGGER, "QUERY: WHY SHOULD I JOIN YOUR FORCE?"),
        say(co::HAWKE, "Because here you will not be called too literal.").only(co::HAWKE),
        say(co::HAWKE, "Precision is a virtue. Be exact.").only(co::HAWKE),
        say(co::JUGGER, "EXACT. ADOPTED.").only(co::HAWKE),
        say(co::KOAL, "Because roads are exact. So are you. Come build.").only(co::KOAL),
        say(co::JUGGER, "ROADS: A GOOD DIRECTIVE. HOW LONG?").only(co::KOAL),
        say(co::KOAL, "Forever.").only(co::KOAL),
        say(co::JUGGER, "FOREVER IS NOT A NUMBER. ...ACCEPTABLE.").only(co::KOAL),
    ];
    post.extend(each(&[co::STURM, co::VON_BOLT, co::KINDLE], "We give orders that never expire."));
    post.push(say(co::JUGGER, "NEVER EXPIRE: UNPRECEDENTED. ...AFFIRMATIVE.").only(co::STURM));
    post.push(say(co::JUGGER, "NEVER EXPIRE: UNPRECEDENTED. ...AFFIRMATIVE.").only(co::VON_BOLT));
    post.push(say(co::JUGGER, "NEVER EXPIRE: UNPRECEDENTED. ...AFFIRMATIVE.").only(co::KINDLE));
    post.push(say(co::JUGGER, "DIRECTIVE ACCEPTED. HUMOR SUBROUTINE: NOT FOUND."));
    post.push(troop("Welcome aboard, sir!"));
    post.push(say(co::JUGGER, "PRIVATE CRUMB: BISCUIT-DEPENDENT. LOGGED."));
    m.victory = Scene::new(post);
    m.after = Scene::new(vec![
        say(co::JUGGER, "SUBJECT: GERALD. STATUS: DEAD. OR UNSTATED."),
        troop("He's fine!"),
        say(co::JUGGER, "AFFIRMATIVE. HE IS FINE. I WILL STOP."),
        troop("The pit guard says Flak obeys strength and sparkle."),
        troop("That is Sir Sturm and Lady Kindle, I should think!"),
    ]);
    m.triggers = vec![
        on_day(4, None, vec![Action::Scene(Scene::new(vec![say(co::JUGGER, "ODDS: 61 PERCENT. YOUR ODDS: LOWER.")]))]),
        on_day(10, None, vec![Action::Scene(Scene::new(vec![say(co::JUGGER, "RECALCULATING. ...RECALCULATING.")]))]),
    ];
    // Jugger's bond: Hawke (or Koal, who has his own pitch) leads.
    m.triggers.extend(win_with_bond(beaten(2, (21, 9)), lead_is_hawke, 4));
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
    m.units = roles(built_units("bh18"), |u| u.kind == unit::NEOTANK);
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
        say(co::KINDLE, "Darling, you may not eat my soldiers.").only(co::KINDLE),
        say(co::FLAK, "Flak not eat. Flak smash. Then eat.").only(co::KINDLE),
        troop("Sir, he is very large. Is he nice?"),
        say(co::FLAK, "Flak is nice! Flak is Nice Flak!"),
    ]);
    let mut post = vec![
        sad(co::FLAK, "Ow. Ow... Flak is down. Flak is on the floor."),
        say(co::FLAK, "Why you hit so good? Why Flak follow you?"),
        say(co::STURM, "Because I will give you wars you cannot finish.").only(co::STURM),
        say(co::STURM, "A thousand battles. And a full table.").only(co::STURM),
        say(co::FLAK, "Thousand?! Full table?!").only(co::STURM),
        say(co::STURM, "Yes.").only(co::STURM),
        say(co::FLAK, "Flak... Flak loves you.").only(co::STURM),
        say(co::KINDLE, "Because I will make you a star. And there is pastry.").only(co::KINDLE),
        say(co::FLAK, "Pastry! Star! Pastry!").only(co::KINDLE),
        say(co::KINDLE, "Lots of both.").only(co::KINDLE),
    ];
    post.extend(each(&[co::VON_BOLT, co::HAWKE, co::KOAL, co::JUGGER], "Serve us. We offer endless fights and food."));
    for c in [co::VON_BOLT, co::HAWKE, co::KOAL, co::JUGGER] {
        post.push(say(co::FLAK, "Endless fights... food... Okay!").only(c));
    }
    post.push(say(co::FLAK, "Flak is yours, boss! Where is food?"));
    post.push(troop("This way, sir!"));
    post.push(say(co::FLAK, "Small man! Small man is friend!"));
    m.victory = Scene::new(post);
    m.after = Scene::new(vec![
        say(co::FLAK, "What is this?"),
        sad(co::FLAK, "..."),
        troop("That is Gerald!"),
        say(co::FLAK, "Looks good! Flak bites it!"),
        troop("NO!"),
        sad(co::FLAK, "...Hard. Flak cries."),
        troop("There, there."),
    ]);
    m.triggers = vec![
        on_day(6, None, vec![Action::Scene(Scene::new(vec![say(co::FLAK, "Bell! Bell! Next round!")]))]),
        on_day(10, None, vec![Action::Scene(Scene::new(vec![say(co::FLAK, "Hit me harder! Flak is sleepy!")]))]),
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
    m.units = roles(built_units("bh19"), |u| matches!(u.kind, unit::ARTILLERY | unit::MISSILES | unit::ANTI_AIR) || (u.kind == unit::INFANTRY && u.x >= 26));
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(7000),
        // Sasha, with real production: 5 bases, 2 airports, 9 cities.
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::SASHA)).funds(45000),
    ];
    m.day_limit = 28;
    m.rank_days = 18;
    m.factory = F19.to_vec();
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
    m.victory = Scene::new(vec![
        sad(co::SASHA, "My line... my beautiful line, stopped."),
        say(co::SASHA, "I have been outspent. Just this once."),
        say(co::VON_BOLT, "Kehh-heh! I took no offer. I took her VAULT."),
        say(co::SASHA, "You did what?"),
        say(co::VON_BOLT, "Everything in it. Gold-plated, too."),
        say(co::SASHA, "Hmph. I will audit you. Eternally."),
    ]);
    m.after = Scene::new(vec![
        say(co::JUGGER, "AUDIT NOTICE RECEIVED. PLEASE SIGN HERE."),
        say(co::VON_BOLT, "Burn it."),
        say(co::JUGGER, "AFFIRMATIVE. BURNING. ...CORRECTION: FILING."),
        say(co::VON_BOLT, "FILING?!"),
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

fn second_front_won(core: &mut Core) -> bool {
    core.raw_read_8(0x0203_E401, -1) == 2
}

fn bh20() -> MissionDef {
    let mut m = MissionDef::new("bh20", "Moonlit Harbours");
    m.objective = "Take Olaf's HQ; win the sea front for a partner.";
    m.map = MapSrc::Built("bh20");
    // Olaf advances, but his Artillery and the Infantry on his HQ hold.
    m.units = roles(built_units("bh20"), |u| u.kind == unit::ARTILLERY || (u.kind == unit::INFANTRY && u.x >= 21));
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
    // Colin's fleet: Cruisers and Subs hunt; the Battleships and the Carrier hold the line off his shelf.
    let mut sea = built_units("bh20b");
    sea.push(UnitDef::new(2, unit::CARRIER, 16, 8));
    let sea = roles(sea, |u| matches!(u.kind, unit::BATTLESHIP | unit::CARRIER));
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
    m.intro = Scene::new(vec![
        say(co::OLAF, "Behold Snow Harbour! Behold OLAF, the pride of Blue Moon!"),
        say(co::OLAF, "A cold front, a cold fleet, and a hot heart!"),
        say(co::COLIN, "H-hi! I'm Colin! My sister got me a navy! A big one!"),
        say(co::COLIN, "It's, um, very big. ...Is it big?"),
        say(co::OLAF, "Colin, my boy, it is HUGE! Leave the rest to Olaf!"),
        say(co::HAWKE, "Harbour front, open sea. Choose two hands."),
    ]);
    m.victory = Scene::new(vec![
        sad(co::OLAF, "Gnn! The harbour freezes and a hero thaws..."),
        say(co::OLAF, "Colin, retreat! I have a sled."),
        say(co::COLIN, "A s-sled? Great! Go, go!"),
        say(co::HAWKE, "Two fronts. Both ours."),
    ]);
    m.after = Scene::new(vec![
        troop("Sir! There is a flag on the horizon. Orange."),
        say(co::HAWKE, "Orange Star has noticed us."),
        troop("Is that good or bad, sir?"),
        say(co::HAWKE, "It is a complication."),
    ]);
    // The sea front's winner reports to the main front as the tag partner (any CO the player picked).
    let reports: Vec<Line> = ALL_COS.iter().map(|&c| say(c, "The sea is ours. Reporting to the harbour.").only_partner(c)).collect();
    m.triggers = vec![
        Trigger::new(When::TurnStart, Cond::Custom(second_front_won), vec![Action::Scene(Scene::new(reports))]),
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
    (unit::RECON, 3, 40), // (the loader caps ammo at the table's maximum: the Recon's is 0)
    (unit::TANK, 2, 30),
    (unit::MD_TANK, 1, 25),
    (unit::ARTILLERY, 0, 25),
    (unit::ROCKETS, 0, 25),
    (unit::MISSILES, 0, 25),
    (unit::ANTI_AIR, 3, 30),
    (unit::B_COPTER, 0, 20),
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
    m.units = roles(built_units("bh21"), |u| u.army == 3 && matches!(u.kind, unit::ARTILLERY | unit::MISSILES))
        .into_iter()
        .map(|u| match COLUMN.iter().find(|c| u.army == 1 && c.0 == u.kind) {
            Some(&(_, ammo, fuel)) => u.ammo(ammo).fuel(fuel),
            None => u,
        })
        .collect();
    let mut intro = vec![
        troop("Blue Moon, the river valley. Far from supply."),
        troop("Sir... my canteen is empty. So are the Tanks'."),
        troop("Everything is empty, Crumb. The convoy is late."),
    ];
    intro.extend(each(&ALL_COS, "Report ammunition."));
    intro.extend([
        troop("Artillery, none. Rockets, none. Tanks, two shots each."),
        say(co::HAWKE, "The convoy left port on time. The road did not."),
        say(co::MAX, "Hey! Black Hole! You look thirsty!"),
        say(co::GRIT, "Easy there, Max. They're near out of shells. Make it count."),
        say(co::MAX, "That's the best news all day! Charge, charge, charge!"),
    ]);
    intro.extend(each(&ALL_COS, "Fall back across the river. Hold the west bank."));
    intro.extend([
        say(co::HAWKE, "Hold until the convoy arrives. Then we cross back."),
        say(co::STURM, "We retreat. We do not run. There is a difference.").only(co::STURM),
        say(co::FLAK, "Flak out of bullets. Flak still has fists.").only(co::FLAK),
        say(co::MAX, "Ha! A big man! Come on!").only(co::FLAK),
        say(co::JUGGER, "AMMUNITION: 11 PERCENT. OUTLOOK: UNFAVOURABLE.").only(co::JUGGER),
        say(co::KOAL, "The convoy is on my road. I laid that road. It is late.").only(co::KOAL),
    ]);
    m.intro = Scene::new(intro);
    m.victory = Scene::new(vec![
        sad(co::MAX, "You ran out of ammo and still beat me?!"),
        say(co::GRIT, "They ran dry, and they got stubborn. That does it."),
        say(co::MAX, "Argh! Tell Nell I did my best!"),
        say(co::GRIT, "Reckon we eat our hats, Max. Fall back."),
        say(co::HAWKE, "A good lesson. The best supply is a promise kept."),
        troop("Sir! I kept one! A promise! And a biscuit!"),
    ]);
    m.after = Scene::new(vec![
        say(co::NELL, "This is Nell, Orange Star. To every nation listening:"),
        say(co::NELL, "Blue Moon, Yellow Comet, Green Earth: not alone."),
        say(co::NELL, "I have called every one of you home."),
        say(co::NELL, "Hold on a little longer. Please."),
        troop("She sounds like my mum."),
        troop("My mum with a general's hat."),
        say(co::STURM, "Turn it off."),
        troop("Sir? I... yes, sir."),
        say(co::STURM, "Leave it on. I will hear what I must break."),
    ]);
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
                Action::Scene(Scene::new(vec![
                    troop("Sir! Biscuit delivery! One APC, two tanks, me!"),
                    troop("Gerald rode on the bumper!"),
                    say(co::HAWKE, "Supply the Artillery first."),
                ])),
            ],
        ),
        on_day(
            4,
            None,
            vec![
                Action::Spawn(vec![
                    go_new(2, unit::RECON, 26, 15),
                    go_new(2, unit::RECON, 26, 14),
                    go_new(2, unit::TANK, 25, 15),
                    go_new(2, unit::TANK, 25, 14),
                ]),
                Action::Scene(Scene::new(vec![
                    say(co::GRIT, "Their supply truck's on the south road. Cut it off."),
                    say(co::MAX, "Raiders, go! Hit the truck!"),
                ])),
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
                Action::Scene(Scene::new(vec![
                    troop("Second convoy, sir! Two more APCs, full of shells!"),
                    troop("I am driving the second one! Gerald's Taxi!"),
                ])),
            ],
        ),
        on_day(
            9,
            None,
            vec![
                Action::Spawn(vec![
                    go_new(2, unit::MD_TANK, 26, 16),
                    go_new(2, unit::MD_TANK, 26, 14),
                    go_new(2, unit::NEOTANK, 26, 18),
                    go_new(3, unit::ROCKETS, 24, 4),
                    go_new(3, unit::ROCKETS, 23, 4),
                ]),
                Action::Scene(Scene::new(vec![say(co::MAX, "More tanks! Everybody, push! Push!")])),
            ],
        ),
        // The counter-attack opens when the guns have shells again.
        Trigger::new(
            When::AfterAction,
            Cond::Custom(resupplied),
            vec![Action::Scene(Scene::new({
                let mut v = each(&ALL_COS, "Now we cross.");
                v.push(say(co::GRIT, "Well, now. They've got shells again!"));
                v.push(say(co::MAX, "So? We have tanks!"));
                v
            }))],
        ),
        // The supply is cut: the convoys' APCs are all gone before the guns were refilled.
        after(
            Cond::Custom(supply_cut),
            vec![
                Action::Scene(Scene::new(vec![troop("No more trucks, sir. No more shells.")])),
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
    m.units = roles(built_units("bh22"), |u| matches!(u.kind, unit::ARTILLERY | unit::MISSILES) || (u.kind == unit::INFANTRY && u.y <= 3));
    m.look = 1; // Snow
    m.weather = Weather::Snow;
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(12000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Pair(co::OLAF, co::SASHA)).funds(28000),
    ];
    m.day_limit = 24;
    m.rank_days = 16;
    let mut intro = vec![
        say(co::OLAF, "This is my palace! Come at me in the blizzard!"),
        say(co::SASHA, "The Moon Palace. We fight for the people inside."),
        say(co::SASHA, "Not for gold. ...Mostly not for gold."),
        say(co::OLAF, "Whiteout, friends! Cold enough to freeze fire!"),
        say(co::STURM, "Weather obeys. So will you.").with(co::STURM),
        say(co::JUGGER, "TEMPERATURE: -22. ALL SYSTEMS NOMINAL.").with(co::JUGGER),
        say(co::FLAK, "Cold! Flak likes! Flak's blanket is hot soup.").with(co::FLAK),
    ];
    for c in [co::VON_BOLT, co::HAWKE, co::KOAL, co::KINDLE] {
        intro.push(say(c, "Cold is only weather. We have weather, too.").with(c));
    }
    m.intro = Scene::new(intro);
    m.victory = Scene::new(vec![
        sad(co::OLAF, "My palace... my snow... my poor fish."),
        say(co::SASHA, "Take it. But spare the children in the lower hall."),
        say(co::SASHA, "And my brother. Colin. Is he safe?"),
        say(co::HAWKE, "He fled by sled. Unharmed."),
        say(co::SASHA, "...Then I can breathe."),
        say(co::STURM, "Those children are mine now. Touch them and answer."),
        say(co::SASHA, "...Thank you. I did not expect that."),
        say(co::OLAF, "Black Hole... you are not as cold as the snow."),
    ]);
    m.after = Scene::new(vec![
        troop("Sir, the Blue Moon people gave us blankets."),
        troop("They are prisoners, Crumb."),
        troop("Then it's very polite of them."),
        say(co::HAWKE, "The blankets are warm. ...I do not like that."),
        troop("A lab cleaner says Doctor Lash loves gadgets and gold."),
        troop("Mr Jugger and the Colonel, sir. Both very shiny."),
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
