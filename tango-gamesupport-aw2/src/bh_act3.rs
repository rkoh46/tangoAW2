//! Act 3: Yellow Comet (M12 to M16). Its missions are `MissionDef`s
//! (docs/AW2.md "BH Campaign": adding a mission); this file is the act's
//! alone, so builders can work on acts in parallel. A mission names what it
//! needs by key (`Needs::All(vec!["bh11"])`), not by index.
//!
//! The maps are `five/bh/bh12.txt` .. `bh16.txt` (+ `bh15b.txt`, M15's sky
//! front), built by `five/bhmap.py` into `bh_map_data.rs`: roads, rivers,
//! coasts and shoals joined as AW2 draws them, reachability checked. The
//! dialogue is the design bible's (docs/BH_CAMPAIGN.md section 4.4, branch
//! bh-design): a design row is one box, its `@IF CO` groups are [`Line::only`]
//! lines, `[CO]` lines one row per CO the player may be ([`others`]), its soldiers and narration the Black Hole trooper's face.

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

/// A group for every CO of `pool` that is not in `named` (the design's `@IF OTHER`): `rows` are
/// (speaker, text), speaker 0 meaning the player's CO itself.
fn others(pool: &[u8], named: &[u8], rows: &[(u8, &'static str)]) -> Vec<Line> {
    let mut v = Vec::new();
    for &c in pool.iter().filter(|c| !named.contains(c)) {
        for &(who, t) in rows {
            v.push(say(if who == 0 { c } else { who }, t).only(c));
        }
    }
    v
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

/// The enemy army is as good as routed: at most one unit left, or its HQ is the player's.
fn beaten(enemy: u8, hq: (u8, u8)) -> Cond {
    Cond::Any(vec![Cond::ArmyUnitsAtMost { army: enemy, n: 1 }, Cond::OwnerAt { x: hq.0, y: hq.1, army: 1 }])
}

/// The player's CO is one of these (a recruit's affinity COs).
fn player_is(cos: &[u8]) -> Cond {
    Cond::Any(cos.iter().map(|&c| Cond::PlayerCo(c)).collect())
}

/// An army's CO meter set to `pct` of its full meter (AW2's units: a CO Power's cost is the first power's full bar).
fn meter(core: &mut Core, army: u32, pct: u32) {
    let p = crate::tag::player(core, army);
    let co = crate::tag::army_co_of(core, army);
    let uses = core.raw_read_8(p + 0x25, -1);
    let full = crate::tag::cop_cost(core, co, uses);
    core.raw_write_32(p + 0x20, -1, full * pct / 100);
}

fn charge_army2_full(core: &mut Core) {
    meter(core, 2, 100);
}

/// The second front's outcome (crate::two_front's state byte: 2 won, 3 lost).
fn second_front_won(core: &mut Core) -> bool {
    core.raw_read_8(0x0203_E401, -1) == 2
}

/// The units of a built map's text file, for a second front (whose deployment is the front's own).
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

/// Gives the enemy army's units their orders (the computer's role byte): the units `holds` picks stay
/// where they stand (role 0: they still fire at what comes into reach), foot soldiers go for the
/// player's properties (3, `Assault`), everything else toward the nearest enemy (4, `Strike`).
/// (The map files' `hold` flag is AW2's role 1, "go for the HQ": not used here.)
fn roles(units: Vec<UnitDef>, holds: impl Fn(&UnitDef) -> bool) -> Vec<UnitDef> {
    units
        .into_iter()
        .map(|mut u| {
            if u.army == 2 {
                u.ai = if holds(&u) {
                    0
                } else if u.kind == unit::INFANTRY || u.kind == unit::MECH {
                    3
                } else {
                    4
                };
            }
            u
        })
        .collect()
}

// --- World map ---------------------------------------------------------------------

/// Act 3's flags on AW2's Yellow Comet (the centre land, x 225..300, y 50..180): M12 .. M16.
pub const FLAGS: [(i16, i16); 5] = [
    region::YELLOW_COMET[0], // M12 Highway to the Horizon
    region::YELLOW_COMET[1], // M13 Festival of Flame
    region::YELLOW_COMET[2], // M14 No Soldier Left Behind
    region::YELLOW_COMET[3], // M15 The Skybridge
    region::YELLOW_COMET[4], // M16 Comet Keep
];

/// The COs the player may be in M12 / M13 (the roster when the mission is reached, without its own recruit).
const POOL12: [u8; 3] = [co::STURM, co::VON_BOLT, co::HAWKE];
const POOL13: [u8; 4] = [co::STURM, co::VON_BOLT, co::HAWKE, co::KOAL];
const POOL15: [u8; 5] = [co::STURM, co::VON_BOLT, co::HAWKE, co::KINDLE, co::KOAL];

// --- M12 Highway to the Horizon (recruit Koal) --------------------------------------

/// Factory table F12 (docs/BH_CAMPAIGN.md 3.5): per day the three doors' units (0 none).
const F12: [(u8, [u8; 3]); 9] = [
    (2, [unit::RECON, 0, unit::RECON]),
    (3, [0, unit::TANK, 0]),
    (5, [unit::MD_TANK, unit::MECH, 0]),
    (7, [0, unit::MD_TANK, 0]), // (the factory never builds a Piperunner: the table no longer asks for one)
    (8, [unit::TANK, 0, unit::TANK]),
    (10, [unit::MD_TANK, 0, unit::MD_TANK]),
    (12, [0, unit::NEOTANK, 0]),
    (14, [unit::MECH, unit::MECH, unit::MECH]),
    (16, [0, unit::MD_TANK, 0]),
];

fn bh12() -> MissionDef {
    let mut m = MissionDef::new("bh12", "Highway to the Horizon");
    m.objective = "Wake the Black Factory, take Koal's HQ.";
    m.map = MapSrc::Built("bh12");
    m.look = 2; // desert
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(9000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KOAL)).funds(30000),
    ];
    m.pool = POOL12.to_vec();
    m.day_limit = 28;
    m.rank_days = 17;
    m.factory = F12.to_vec();
    m.units = roles(built_units("bh12"), |u| u.kind == unit::ANTI_AIR);
    m.recruits = vec![roster::KOAL];
    m.intro = Scene::new(vec![
        say(co::KOAL, "Stop. Right there. You stand on my shoulder."),
        say(co::KOAL, "The hard shoulder. Three metres wide. Move."),
        say(co::KOAL, "Welcome to the Trans-Comet Highway. Two thousand miles."),
        say(co::KOAL, "Not one pothole. Not one border."),
        say(co::KOAL, "Except the ones at the end. I hate the ones at the end."),
        say(co::KOAL, "The Council pays me to build and then to stop."),
        say(co::KOAL, "I wish to build and not stop. Take it from me. Try."),
        say(co::VON_BOLT, "A toll road! Koal, think of the tolls!").only(co::VON_BOLT),
        say(co::KOAL, "NO TOLLS.").only(co::VON_BOLT),
        say(co::VON_BOLT, "...Small tolls?").only(co::VON_BOLT),
        say(co::HAWKE, "A line without borders is a logistician's dream.").only(co::HAWKE),
        say(co::STURM, "Show me the road. Then I will own the end.").only(co::STURM),
        say(co::KOAL, "The end is the problem.").only(co::STURM),
        troop("Sir! I inspected the shoulder. It is very firm!"),
        say(co::KOAL, "...You touched my shoulder?"),
        troop("I only measured it, sir!"),
        say(co::KOAL, "I like him."),
    ]);
    let mut pitch = vec![
        sad(co::KOAL, "My highway... broken at the junction. Unforgivable."),
        say(co::KOAL, "I'll hear you out. Why take your orders?"),
        say(co::STURM, "Because borders end where we arrive.").only(co::STURM),
        say(co::STURM, "Take the world. The road will have no end.").only(co::STURM),
        say(co::KOAL, "No... end?").only(co::STURM),
        say(co::STURM, "The last mile is mine to name.").only(co::STURM),
        say(co::KOAL, "...Hm. Send me the survey maps. All of them.").only(co::STURM),
        say(co::HAWKE, "Black Hole pays for roads. Every nation's.").only(co::HAWKE),
        say(co::HAWKE, "One standard. One camber. One road.").only(co::HAWKE),
        say(co::KOAL, "One camber...!").only(co::HAWKE),
        say(co::HAWKE, "One camber.").only(co::HAWKE),
        say(co::KOAL, "Where do I sign?").only(co::HAWKE),
    ];
    pitch.extend(others(
        &POOL12,
        &[co::STURM, co::HAWKE],
        &[
            (0, "Join us. The road will cross every border."),
            (co::KOAL, "Every border?"),
            (0, "Every one."),
            (co::KOAL, "...Fine. The lane widths are mine."),
        ],
    ));
    pitch.push(say(co::KOAL, "I accept. Mind the lane."));
    m.victory = Scene::new(pitch);
    m.after = Scene::new(vec![
        say(co::KOAL, "Corporal. You. Come here."),
        troop("Sir? I'm a Private, sir."),
        say(co::KOAL, "Not on my road. You are my road inspector now."),
        troop("Gerald, we got a job!"),
        troop("The road inspector will report for duty at dawn."),
        troop("A lady at the toll hut wrote down my name, sir."),
        troop("She wrote down everyone's. Even the cart horses'."),
        troop("Wrote it in what?"),
        troop("A small black book. She signed it \"S.\""),
        troop("She said Gerald has a lovely colour."),
        troop("A stall-keeper says Lady Kindle likes gold, manners."),
        troop("That is the Colonel and the Marshal, sir. I think."),
    ]);
    m.triggers = vec![
        on_day(5, None, vec![Action::Scene(Scene::new(vec![say(co::KOAL, "A Black Factory in my median? Rude.")]))]),
        on_day(12, None, vec![Action::Scene(Scene::new(vec![say(co::KOAL, "The pipeline is mine. Do not smoke near it.")]))]),
        // The win: Koal's bond is earned with Sturm or Hawke leading (the pitch is the victory scene).
        after(Cond::All(vec![beaten(2, (34, 9)), player_is(&[co::STURM, co::HAWKE])]), vec![Action::EarnBond(2), Action::Win]),
        after(Cond::All(vec![beaten(2, (34, 9)), Cond::Not(Box::new(player_is(&[co::STURM, co::HAWKE])))]), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh11"]);
    m.flag = FLAGS[0];
    m.stars = 3;
    m
}

// --- M13 Festival of Flame (recruit Kindle) ---------------------------------------------

/// The four Fireworks Towers (the plaza's corners).
const TOWERS: [(u8, u8); 4] = [(8, 5), (13, 5), (8, 10), (13, 10)];
/// The stage (Kindle's HQ cell: a city in this mission, so that taking it is not the game's own win).
const STAGE: (u8, u8) = (10, 3);

/// The stage is the player's and at least three of the four Towers are.
fn stage_and_towers() -> Cond {
    let owns = |(x, y): (u8, u8)| Cond::OwnerAt { x, y, army: 1 };
    let mut triples = Vec::new();
    for skip in 0..4 {
        triples.push(Cond::All(TOWERS.iter().enumerate().filter(|(i, _)| *i != skip).map(|(_, &t)| owns(t)).collect()));
    }
    Cond::All(vec![owns(STAGE), Cond::Any(triples)])
}

fn bh13() -> MissionDef {
    let mut m = MissionDef::new("bh13", "Festival of Flame");
    m.objective = "Take the stage and hold 3 of 4 towers. 14 days.";
    m.map = MapSrc::Built("bh13");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(6000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KINDLE)).funds(12000),
    ];
    m.pool = POOL13.to_vec();
    // The stage is a city of Kindle's (no HQ to capture: the win is the stage and the Towers together).
    m.props = vec![Prop { kind: PropKind::City, owner: 2, x: STAGE.0, y: STAGE.1 }];
    m.day_limit = 14;
    m.rank_days = 10;
    m.units = roles(built_units("bh13"), |u| (8..=13).contains(&u.x) && u.y <= 5);
    m.recruits = vec![roster::KINDLE];
    m.intro = Scene::new(vec![
        say(co::KINDLE, "Darlings! You are late to my festival!"),
        say(co::KINDLE, "The Flame Festival! The greatest night in the east!"),
        say(co::KINDLE, "And I am its patron, its star, its everything."),
        say(co::KINDLE, "Yellow Comet pays me to stand here and shine."),
        say(co::KINDLE, "I would shine anyway. The pay is nice."),
        say(co::HAWKE, "Kindle. You are on the rolls of Black Hole."),
        say(co::KINDLE, "Rolls! Ha! I am on posters, darling."),
        say(co::KINDLE, "Impress me. Take my plaza before the last firework."),
        say(co::KINDLE, "Fourteen days. I get bored in thirteen."),
        say(co::VON_BOLT, "Kindle, you owe me fourteen thousand!").only(co::VON_BOLT),
        say(co::KINDLE, "Darling, I owe the world. You are a small part.").only(co::VON_BOLT),
        say(co::KOAL, "Fireworks over a road. Keep them off the camber.").only(co::KOAL),
        say(co::KINDLE, "Darling, the camber is not a stage. ...Yet.").only(co::KOAL),
    ]);
    let mut pitch = vec![
        sad(co::KINDLE, "My plaza! My lovely plaza! You... brute."),
        say(co::KINDLE, "Fine. You impress me. Slightly. Do continue."),
        say(co::KINDLE, "Why should I join? Yellow Comet adores me."),
        say(co::VON_BOLT, "Adoration is a debt, my dear. We pay it in gold.").only(co::VON_BOLT),
        say(co::VON_BOLT, "Statues, Kindle. Gold ones. Taller each year.").only(co::VON_BOLT),
        say(co::KINDLE, "...Gold ones.").only(co::VON_BOLT),
        say(co::VON_BOLT, "And an audience that never goes home.").only(co::VON_BOLT),
        say(co::KINDLE, "Ahaha! Gold ones! Sold!").only(co::VON_BOLT),
        say(co::HAWKE, "Yellow Comet has one festival. We have a world.").only(co::HAWKE),
        say(co::HAWKE, "Every city a stage. Every night an opening.").only(co::HAWKE),
        say(co::KINDLE, "Opening night forever. ...You flatter well.").only(co::HAWKE),
        say(co::HAWKE, "I do it professionally.").only(co::HAWKE),
    ];
    pitch.extend(others(
        &POOL13,
        &[co::VON_BOLT, co::HAWKE],
        &[
            (0, "Black Hole has a larger stage than Yellow Comet."),
            (0, "Perform for the world. Join us."),
            (co::KINDLE, "That is it? No gold? No statues?"),
            (co::KINDLE, "Fine. I'll bring my own."),
        ],
    ));
    pitch.extend([
        say(co::KINDLE, "I accept, darlings. Now. Where is my seat?"),
        troop("Ma'am, I kept it warm."),
        say(co::KINDLE, "It is a crate."),
        troop("A premium crate!"),
        say(co::KINDLE, "...Adorable. Keep him."),
    ]);
    m.victory = Scene::new(pitch);
    m.after = Scene::new(vec![
        troop("Ma'am Kindle gave me a sash!"),
        troop("It says \"Audience\"."),
        troop("It says \"Audience\"! I'm in her audience!"),
        troop("Don't clap unless asked."),
        troop("...I clapped."),
        say(co::KINDLE, "Darlings, a girl in the rafters took notes all night."),
        say(co::KINDLE, "Dark coat. Gloomy. Not one clap. I did not mind."),
    ]);
    let win = || Cond::All(vec![stage_and_towers(), player_is(&[co::VON_BOLT, co::HAWKE])]);
    m.triggers = vec![
        on_day(4, None, vec![Action::Scene(Scene::new(vec![say(co::KINDLE, "Fireworks! Clap, peasants, clap!")]))]),
        on_day(10, None, vec![Action::Scene(Scene::new(vec![say(co::KINDLE, "Four days left, darling. Entertain me. Properly.")]))]),
        // The win: the stage and three Towers; Kindle's bond is earned with Von Bolt or Hawke leading.
        after(win(), vec![Action::EarnBond(3), Action::Win]),
        after(Cond::All(vec![stage_and_towers(), Cond::Not(Box::new(player_is(&[co::VON_BOLT, co::HAWKE])))]), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh12"]);
    m.flag = FLAGS[1];
    m.stars = 3;
    m
}

// --- M14 No Soldier Left Behind -------------------------------------------------------

/// Pad Echo, the extraction airport: Crumb must stand on it (or be carried onto it by a T Copter).
const PAD_ECHO: (u8, u8) = (19, 18);
/// The Yellow Comet "HQ" in the north-east (a city here: taking it must not end the mission).
const SONJA_POST: (u8, u8) = (20, 2);

/// Crumb's hollow (the ring's inside).
fn in_basin(x: u8, y: u8) -> bool {
    (1..=5).contains(&x) && (1..=6).contains(&y)
}

/// Day 3: the ring round Crumb stops holding and closes in (role 3 for foot, 4 for the rest).
fn release_ring(core: &mut Core) {
    for (addr, kind, x, y) in units_of(core, 2) {
        if in_basin(x, y) {
            let role = if kind == unit::INFANTRY || kind == unit::MECH { 3 } else { 4 };
            core.raw_write_8(addr + 0x0B, -1, role);
            // refuelled: the type's full tank
            let tank = match kind {
                unit::MD_TANK => 50,
                unit::MECH | unit::TANK => 70,
                unit::RECON => 80,
                _ => 99,
            };
            let old = core.raw_read_8(addr + 6, -1);
            core.raw_write_8(addr + 6, -1, (old & 0x80) | tank);
        }
    }
}

/// Crumb is on Pad Echo, on foot or inside a Transport Copter standing there.
fn crumb_extracted(core: &mut Core) -> bool {
    let Some((a, true)) = unit_by_name(core, "crumb") else { return false };
    if core.raw_read_8(a + 2, -1) == PAD_ECHO.0 && core.raw_read_8(a + 3, -1) == PAD_ECHO.1 {
        return true;
    }
    let base = core.raw_read_32(0x0849_9594, -1);
    units_of(core, 1).iter().any(|&(addr, kind, x, y)| {
        kind == unit::T_COPTER && (x, y) == PAD_ECHO && {
            let cargo = core.raw_read_8(addr + 7, -1) as u32;
            cargo != 0 && base + 12 * cargo == a
        }
    })
}

fn bh14() -> MissionDef {
    let mut m = MissionDef::new("bh14", "No Soldier Left Behind");
    m.objective = "Bring Crumb to Pad Echo within fifteen days.";
    m.map = MapSrc::Built("bh14");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(0),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::SONJA)).funds(0),
    ];
    // Yellow Comet's post in the north-east is a city, not an HQ: the only win is the evacuation.
    m.props = vec![Prop { kind: PropKind::City, owner: 2, x: SONJA_POST.0, y: SONJA_POST.1 }];
    // The ring round Crumb and the gap guards hold (the ring is released on day 3), the rest hunts the column.
    const GUARDS: [(u8, u8); 9] = [(7, 3), (3, 9), (8, 9), (9, 7), (8, 5), (9, 5), (9, 4), (11, 6), (11, 7)];
    // (the ring's tanks and soldiers stand with empty tanks until day 3: held units still strike what is in
    // reach, and Crumb has 1 HP; they are refuelled by `release_ring`)
    m.units = roles(built_units("bh14"), |u| u.kind == unit::ANTI_AIR || in_basin(u.x, u.y) || GUARDS.contains(&(u.x, u.y)))
        .into_iter()
        .map(|u| if u.army == 2 && in_basin(u.x, u.y) { u.fuel(0) } else { u })
        .collect();
    m.fog = true;
    m.day_limit = 15;
    m.rank_days = 12;
    m.intro = Scene::new(vec![
        troop("Sir? Crumb here. I am slightly surrounded."),
        say(co::HAWKE, "Where?"),
        troop("Highlands, west of the highway. Eight of them. Ten."),
        troop("They are waving. I do not think they are friendly."),
        say(co::SONJA, "A lost sparrow. And a radio that sings."),
        say(co::SONJA, "I will keep him safe. For the price of a general."),
        say(co::HAWKE, "One soldier. This is not worth a battalion."),
        say(co::VON_BOLT, "He owes me for boots! Fetch him!"),
        say(co::KOAL, "He inspected my road. I owe him."),
        say(co::KINDLE, "The cute one? Rescue him at once!"),
        say(co::STURM, "Silence."),
        say(co::STURM, "What is mine stays mine. Nobody takes from Black Hole."),
        say(co::STURM, "An army that leaves one behind is a crowd."),
        say(co::STURM, "Fifteen days. Take him back."),
        say(co::SONJA, "Fifteen days. I shall count them for you."),
    ]);
    m.victory = Scene::new(vec![
        troop("Is it... is it over?"),
        say(co::STURM, "You are extracted."),
        troop("Sir, you came for me."),
        say(co::STURM, "He is mine. I take back what is mine. Nothing more."),
        troop("Yes, sir! Gerald is fine. Very fine!"),
        say(co::VON_BOLT, "The boots! Where are my boots?!"),
        troop("I still have both, Colonel."),
        say(co::VON_BOLT, "Kehh... I'll collect them later. Tonight, rest."),
        say(co::SONJA, "He was bait, and you took him anyway. Surprising."),
        say(co::SONJA, "I will record that. It is worth knowing."),
        say(co::SONJA, "He turned an army round for one private."),
        say(co::SONJA, "I keep a book of men who would not. He is not in it."),
        say(co::STURM, "Do not write that down."),
        say(co::SONJA, "Page one, I think."),
    ]);
    m.after = Scene::new(vec![
        troop("Medic says one HP is technically alive."),
        troop("Technically is my best rank, Sergeant!"),
        troop("I... I was worried. Stupidly worried."),
        troop("It's all right, Wick. Gerald was worried, too."),
        troop("Eat your soup."),
        troop("Sir. Thank you. For Hobb."),
        say(co::STURM, "Do not thank me. Win."),
    ]);
    m.triggers = vec![
        // Day 2: an open line between father and daughter (Sonja's cameo).
        on_day(
            2,
            None,
            vec![Action::Scene(Scene::new(vec![
                say(co::KANBEI, "Sonja! Daughter! Have you eaten? The highlands are cold!"),
                say(co::SONJA, "Father. This is an open line."),
                say(co::KANBEI, "Then I shall say it to all: she is my pride!"),
                say(co::SONJA, "...Father."),
            ]))],
        ),
        on_day(
            3,
            None,
            vec![
                Action::Custom(release_ring),
                Action::Scene(Scene::new(vec![
                    troop("They moved, sir. Closer. I stopped eating."),
                    troop("That is how serious it is."),
                ])),
            ],
        ),
        on_day(6, None, vec![Action::Scene(Scene::new(vec![troop("Gerald says hold on. He is very brave, sir.")]))]),
        on_day(
            8,
            None,
            vec![Action::Scene(Scene::new(vec![
                say(co::SONJA, "The fog hides him from you. It does not hide you from me."),
            ]))],
        ),
        on_day(12, None, vec![Action::Scene(Scene::new(vec![troop("Three days, sir? I can hear the helicopter.")]))]),
        // The win: Crumb on Pad Echo (or carried onto it). On day 12 or sooner Crumb's secret quote is earned
        // (bond 9: the CO page's tenth secret quote, needs a tenth entry in `bh_campaign::BONDS`).
        after(Cond::All(vec![Cond::Custom(crumb_extracted), Cond::Not(Box::new(Cond::DayAtLeast(13)))]), vec![Action::EarnBond(9), Action::Win]),
        after(Cond::Custom(crumb_extracted), vec![Action::Win]),
        after(Cond::UnitGone("crumb"), vec![Action::Lose]),
    ];
    m.needs = Needs::All(vec!["bh13"]);
    m.flag = FLAGS[2];
    m.stars = 4;
    m
}

// --- M15 The Skybridge ----------------------------------------------------------------

fn bh15() -> MissionDef {
    let mut m = MissionDef::new("bh15", "The Skybridge");
    m.objective = "Take Kanbei's HQ, rout Grimm's air force.";
    m.map = MapSrc::Built("bh15");
    // The player picks two COs: the main front's, then the sky front's.
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(10000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KANBEI)).funds(16000),
    ];
    m.pool = POOL15.to_vec();
    m.day_limit = 24;
    m.rank_days = 16;
    m.units = roles(built_units("bh15"), |u| u.kind == unit::ANTI_AIR || u.kind == unit::ROCKETS);
    // The sky front's Black Factory table is dormant (there is none; AW2's turn calls the spawner all the same).
    m.factory = vec![(0, [0, 0, 0])];
    m.front2 = Some(FrontDef {
        map: MapSrc::Built("bh15b"),
        // The sky front is open sky and the units: no HQ, no city, no airport. It is won (and lost) by AW2's own rout rule,
        // every unit of one side destroyed; its air units all take AI role 4 (attack units), none goes for an HQ.
        props: Vec::new(),
        structures: Vec::new(),
        units: built_units("bh15b").into_iter().map(|mut u| { u.ai = 4; u }).collect(),
        cos: [CoSpec::Pick, CoSpec::Fixed(co::GRIMM), CoSpec::None, CoSpec::None],
        send: SendRule::Air,
        sky: true,
        weather: Weather::Clear,
        fog: false,
    });
    m.intro = Scene::new(vec![
        say(co::KANBEI, "Black Hole! You tread the Skybridge of Yellow Comet!"),
        say(co::KANBEI, "I, Kanbei, will not yield a step. Honour demands it!"),
        say(co::GRIMM, "Grimm here! Lemme at 'em! The sky's got no walls!"),
        say(co::GRIMM, "Don't wait, Boss! I'll punch a cloud!"),
        say(co::KANBEI, "Grimm. A cloud cannot be punched."),
        say(co::GRIMM, "Watch me."),
        say(co::HAWKE, "Two fronts. Mountain and sky. Divide as you see fit."),
        say(co::KOAL, "A rail cutting! Thin shoulders. I will fix them.").with(co::KOAL),
    ]);
    m.victory = Scene::new(vec![
        sad(co::KANBEI, "The mountain falls. Honour... remains."),
        sad(co::GRIMM, "I punched a cloud and it punched back."),
        say(co::KANBEI, "Yellow Comet will meet you at Comet Keep."),
    ]);
    m.after = Scene::new(vec![
        troop("Sir, the sky bridge wobbles. Is that normal?"),
        troop("It is a sky bridge, Crumb."),
        troop("Gerald is gripping my pocket very hard."),
    ]);
    let mut sky_won = Vec::new();
    for c in POOL15 {
        sky_won.push(say(c, "The sky is ours. Reporting to the main front.").only_partner(c));
    }
    m.triggers = vec![
        on_day(
            4,
            None,
            vec![Action::Scene(Scene::new(vec![
                say(co::SONJA, "Father, the code says never yield. Never lose."),
                say(co::SONJA, "When both cannot hold, which one gives way?"),
                say(co::KANBEI, "Both hold! That is why it is a code!"),
                say(co::SONJA, "...Yes, Father."),
                say(co::KANBEI, "She jests. She often jests. A fine strategist, my Sonja!"),
            ]))],
        ),
        Trigger::new(When::TurnStart, Cond::Custom(second_front_won), vec![Action::Scene(Scene::new(sky_won))]),
        on_day(8, None, vec![Action::Scene(Scene::new(vec![say(co::GRIMM, "A Stealth? Ha! I'll punch it until it shows up!")]))]),
        after(beaten(2, (22, 10)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh14"]);
    m.flag = FLAGS[3];
    m.stars = 4;
    m
}

// --- M16 Comet Keep -------------------------------------------------------------------

fn bh16() -> MissionDef {
    let mut m = MissionDef::new("bh16", "Comet Keep");
    m.objective = "Storm the Keep and capture the courtyard HQ.";
    m.map = MapSrc::Built("bh16");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(6000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Pair(co::KANBEI, co::SENSEI)).funds(18000),
    ];
    m.pool = POOL15.to_vec();
    m.day_limit = 24;
    m.rank_days = 16;
    m.units = roles(built_units("bh16"), |u| u.y <= 5);
    m.intro = Scene::new(vec![
        say(co::KANBEI, "This is Comet Keep. Born of honour and mountain."),
        say(co::KANBEI, "Come, black storm! Let honour judge us!"),
        say(co::SENSEI, "Kanbei, remember Hachi? Our old pupil. Sells maps now."),
        say(co::KANBEI, "Kanbei remembers! A fine blade, wasted on maps."),
        say(co::KANBEI, "Sonja guards the rear. No blade shall touch my daughter."),
        say(co::SONJA, "Father, I am a grown woman."),
        say(co::KANBEI, "And still my daughter!"),
        say(co::SENSEI, "He is incorrigible."),
        say(co::SENSEI, "Hawke. You wear a worse uniform than Green Earth's."),
        say(co::HAWKE, "Sensei. I do not underrate you.").with(co::HAWKE),
        say(co::SENSEI, "Good. Few manage it twice.").with(co::HAWKE),
    ]);
    m.victory = Scene::new(vec![
        sad(co::KANBEI, "Kanbei is beaten. The Keep is yours."),
        say(co::KANBEI, "Spare my people, storm. That is my only request."),
        say(co::STURM, "They are mine now. Harm none of what is mine."),
        say(co::KANBEI, "...Then I will bow."),
        say(co::SENSEI, "Hawke. Sleep sometimes. Wars wait, even for you."),
        say(co::SONJA, "Information is the last currency. Buy mine."),
        say(co::VON_BOLT, "What do you want for it?"),
        say(co::SONJA, "A discount."),
        say(co::KANBEI, "Sonja! We shall rebuild the Keep together, you and I!"),
        sad(co::SONJA, "...Of course, Father."),
    ]);
    m.after = Scene::new(vec![
        say(co::SONJA, "Blue Moon is rich, and afraid. Dangerous together."),
        say(co::VON_BOLT, "Rich! Tell me more!"),
        say(co::SONJA, "That will be extra."),
        say(co::SONJA, "One more thing, Colonel. A sealed note. Open it later."),
        say(co::VON_BOLT, "What does it say?"),
        say(co::SONJA, "Instructions. For the day your vault is empty."),
        say(co::VON_BOLT, "My vault is never empty!"),
        say(co::SONJA, "Then you will never need it."),
        say(co::VON_BOLT, "...Hmph. Last shelf. In the vault. With the crate."),
        troop("It's cold, Gerald. Cold enough to freeze a biscuit."),
        troop("...Not that he'd notice."),
        troop("Blue Moon folk whisper that a tin man hates sloppy talk."),
        troop("Mr Koal and the Marshal are tidy. Just saying, sir."),
    ]);
    // Sensei's paratroopers: nine Infantry land behind the player's line.
    let jump = vec![
        UnitDef::new(2, unit::INFANTRY, 10, 19),
        UnitDef::new(2, unit::INFANTRY, 11, 19),
        UnitDef::new(2, unit::INFANTRY, 12, 19),
        UnitDef::new(2, unit::INFANTRY, 14, 19),
        UnitDef::new(2, unit::INFANTRY, 15, 19),
        UnitDef::new(2, unit::INFANTRY, 16, 19),
        UnitDef::new(2, unit::INFANTRY, 11, 20),
        UnitDef::new(2, unit::INFANTRY, 12, 20),
        UnitDef::new(2, unit::INFANTRY, 14, 20),
    ];
    m.triggers = vec![
        // The first power is charged from the start (the Keep's pair).
        on_day(1, None, vec![Action::Custom(charge_army2_full)]),
        on_day(
            6,
            None,
            vec![Action::Scene(Scene::new(vec![say(co::SENSEI, "Jump, my paratroopers!")])), Action::Spawn(jump)],
        ),
        on_day(12, None, vec![Action::Scene(Scene::new(vec![say(co::KANBEI, "Kanbei leads! For honour, for Yellow Comet! Charge!")]))]),
        after(beaten(2, (13, 2)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh15"]);
    m.flag = FLAGS[4];
    m.stars = 4;
    m
}

/// Act 3's missions, in world-map order.
pub fn missions() -> Vec<MissionDef> {
    let mut v = Vec::new();
    v.push(bh12());
    v.push(bh13());
    v.push(bh14());
    v.push(bh15());
    v.push(bh16());
    // The day limit loses: the day after the last is the defeat (the header's counter only shows it).
    for m in v.iter_mut().filter(|m| m.key >= "bh12") {
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

    fn scenes(m: &MissionDef) -> Vec<(String, &Scene)> {
        let mut v = vec![(format!("{} intro", m.key), &m.intro), (format!("{} victory", m.key), &m.victory), (format!("{} after", m.key), &m.after)];
        for (i, t) in m.triggers.iter().enumerate() {
            for a in &t.then {
                if let Action::Scene(s) = a {
                    v.push((format!("{} trigger {i}", m.key), s));
                }
            }
        }
        v
    }

    #[test]
    fn act_three_is_m12_to_m16_in_order() {
        let keys: Vec<&str> = missions().iter().map(|m| m.key).filter(|k| *k >= "bh12").collect();
        assert_eq!(keys, ["bh12", "bh13", "bh14", "bh15", "bh16"]);
    }

    #[test]
    fn every_map_is_built_and_every_mission_has_scenes_and_a_flag_in_yellow_comet() {
        for m in missions().iter().filter(|m| m.key >= "bh12") {
            let MapSrc::Built(name) = &m.map else { panic!("{}: not a built map", m.key) };
            assert!(crate::bh_map_data::MAPS.iter().any(|b| b.name == *name), "{}: map {name} is not built (five/bhmap.py)", m.key);
            if let Some(f) = &m.front2 {
                let MapSrc::Built(n2) = &f.map else { panic!("{}: second front not built", m.key) };
                assert!(crate::bh_map_data::MAPS.iter().any(|b| b.name == *n2), "{}: map {n2}", m.key);
            }
            assert!(!m.intro.is_empty() && !m.after.is_empty(), "{}: scenes", m.key);
            // AW2's Yellow Comet, the centre land
            assert!((225..=300).contains(&m.flag.0) && (50..=180).contains(&m.flag.1), "{}: flag {:?} off Yellow Comet", m.key, m.flag);
        }
    }

    #[test]
    fn recruits_bonds_and_the_chain() {
        let ms = missions();
        let get = |k: &str| ms.iter().find(|m| m.key == k).unwrap();
        assert_eq!(get("bh12").recruits, vec![roster::KOAL]);
        assert_eq!(get("bh13").recruits, vec![roster::KINDLE]);
        assert_eq!(get("bh13").needs, Needs::All(vec!["bh12"]));
        assert_eq!(get("bh16").needs, Needs::All(vec!["bh15"]));
        let earns = |k: &str, b: u8| get(k).triggers.iter().any(|t| t.then.iter().any(|a| matches!(a, Action::EarnBond(x) if *x == b)));
        assert!(earns("bh12", 2) && earns("bh13", 3) && earns("bh14", 9));
        // (the pools hold only COs unlocked by then: Koal is not in M12's, Kindle not in M13's)
        assert!(!get("bh12").pool.contains(&co::KOAL) && !get("bh13").pool.contains(&co::KINDLE));
    }

    /// Every line of every scene fits one box (two lines of AW2's 176 pixels).
    /// Run with the AW2 ROM: `TANGOAW2_AW2_ROM=... cargo test -p tango-gamesupport-aw2 --lib bh_act3 -- --ignored`.
    #[test]
    #[ignore]
    fn dialogue_fits_the_boxes() {
        let rom = std::fs::read(std::env::var("TANGOAW2_AW2_ROM").unwrap()).unwrap();
        let widths = rom[0x4C_36E4..][..256].to_vec();
        let mut checked = 0;
        for m in missions().iter().filter(|m| m.key >= "bh12") {
            for (name, scene) in scenes(m) {
                for l in &scene.lines {
                    let t = wrap_dialogue(l.text.as_bytes(), &widths);
                    let boxes: Vec<&[u8]> = t.split(|&c| c == 0x0F).filter(|b| !b.is_empty()).collect();
                    assert_eq!(boxes.len(), 1, "{name}: {:?} needs {} boxes", l.text, boxes.len());
                    let lines = boxes[0].split(|&c| c == b'\r').count();
                    assert!(lines <= 2, "{name}: {:?} needs {lines} lines", l.text);
                    checked += 1;
                }
            }
        }
        assert!(checked > 150, "{checked} lines checked");
    }
}
