//! Act 1: Cinders. M1 Storm Landing (Von Bolt's recruit mission, a beach
//! assault with Black Crystals and an Obelisk), M2 The Sleeping Foundry (a Black
//! Factory that wakes on day 3, a set-piece defence) and M3 Blockade Runner (a
//! naval tag battle against Drake and Eagle). The design is
//! docs/BH_CAMPAIGN.md (sections 3.5, 4.1, 4.2 and 4.11); the maps are
//! `five/bh/bh01.txt` .. `bh03.txt`, built by `five/bhmap.py` into
//! `bh_map_data.rs`.
//!
//! Its missions are `MissionDef`s (docs/AW2.md "BH Campaign": adding a
//! mission); this file is the act's alone, so builders can work on acts in
//! parallel. A mission names what it needs by key (`Needs::All(vec!["bh01"])`),
//! not by index.

use mgba::core::Core;

use crate::bh_campaign::{region, roster};
use crate::custom_campaign::{co, colour, unit, *};

/// Black Hole's trooper face (Crumb, Sgt. Mortar, Pvt. Wick): AW2's soldier
/// portraits are faces 19..23, Black Hole's is 23, with the happy and sad
/// expressions as for a CO (`co + 24 * mood`).
const TROOPER: u8 = 23;

// --- Scenes (docs/BH_CAMPAIGN.md 4.2 and 4.11, line for line) -----------------------

fn m01_pre() -> Scene {
    Scene::new(vec![
        Line::narrate("Cinder Coast. Dawn.\rThe first storm in years."),
        Line::feel(
            TROOPER,
            Mood::Happy,
            "Landing complete, sir!\rLost two boots. Only two!",
        ),
        Line::say(co::STURM, "Boots are replaceable.\rReport."),
        Line::say(TROOPER, "Green tanks on the ridge,\rgreen flags on the walls."),
        Line::feel(TROOPER, Mood::Sad, "Even the cook's apron\rwas green, sir. I checked."),
        Line::say(co::STURM, "Green Earth holds nothing\ron this coast."),
        Line::say(TROOPER, "Then why do they fly\rtheir flag over our ruins?"),
        Line::say(co::VON_BOLT, "Kehh-heh! Who walks\rmy beach unannounced?"),
        Line::say(co::VON_BOLT, "A storm in a coat!\rThe rumours were true."),
        Line::say(co::STURM, "Von Bolt. You are older\rthan the rumours."),
        Line::say(co::VON_BOLT, "And richer! Tanks, paint,\rall bought cheap!"),
        Line::say(co::VON_BOLT, "Want my coast? Then\ryou want my paint, too."),
        Line::say(co::STURM, "I want what you guard.\rAnd what you know."),
        Line::say(co::VON_BOLT, "Everything I know is\rfor sale. Everything."),
        Line::say(co::STURM, "Then name your price."),
        Line::say(co::VON_BOLT, "Defeat me, little\rstorm. Then we talk numbers."),
        Line::say(TROOPER, "Sir... may I keep my\rremaining boots?"),
        Line::say(co::STURM, "Fight in them."),
    ])
}

fn m01_day3() -> Scene {
    Scene::new(vec![
        Line::say(co::VON_BOLT, "Those crystals! Mine!\rThey hum for ME!"),
        Line::say(co::STURM, "They hum for whoever\rstands in their light."),
    ])
}

fn m01_day7() -> Scene {
    Scene::new(vec![Line::say(
        co::VON_BOLT,
        "Kehh! A discount!\rEverything must go! Charge!",
    )])
}

fn m01_post() -> Scene {
    Scene::new(vec![
        Line::feel(
            co::VON_BOLT,
            Mood::Sad,
            "My coast... my paint...\rmy lovely, cheap tanks...",
        ),
        Line::say(co::STURM, "Von Bolt. You are not\rfinished. You are priced."),
        Line::say(co::VON_BOLT, "Hm?"),
        Line::say(co::STURM, "Join me. The world is a\rledger. I hold the pen."),
        Line::say(co::VON_BOLT, "The whole world...\rin the black?"),
        Line::say(co::STURM, "In ours."),
        Line::say(co::VON_BOLT, "Kehh... heh heh heh...\rGloriously greedy."),
        Line::say(co::VON_BOLT, "I accept. First pick\rof every vault we open."),
        Line::say(co::STURM, "You may pick second."),
        Line::say(co::VON_BOLT, "...Second pick. It\ris still a pick."),
        Line::feel(TROOPER, Mood::Happy, "Does this mean I keep\rmy boots, sir?"),
        Line::say(co::VON_BOLT, "Hm. Perhaps. For now."),
    ])
}

fn m01_map() -> Scene {
    Scene::new(vec![
        Line::feel(
            TROOPER,
            Mood::Happy,
            "Sergeant! The old man\rsays second pick is a pick!",
        ),
        Line::say(TROOPER, "Crumb. Second pick of\rvaults. Not of boots."),
        Line::say(TROOPER, "Gerald says boots count."),
        Line::say(TROOPER, "Who is Gerald?"),
        Line::feel(TROOPER, Mood::Happy, "My biscuit, Sergeant!\rBasic training issue."),
        Line::say(TROOPER, "That thing is older than\rthe Obelisk."),
        Line::say(TROOPER, "Gerald says that's rude."),
        Line::feel(TROOPER, Mood::Sad, "Does anyone know why our\rtanks are still green?"),
        Line::say(co::VON_BOLT, "Paint costs money."),
    ])
}

fn m02_pre() -> Scene {
    Scene::new(vec![
        Line::say(co::VON_BOLT, "Behold! The Foundry.\rAsleep for forty years."),
        Line::say(co::STURM, "It sleeps still."),
        Line::say(co::VON_BOLT, "It wakes when the\rledger balances. Three days."),
        Line::say(co::STURM, "Three days."),
        Line::say(TROOPER, "Sir, it's making a noise\rlike a cough."),
        Line::say(co::VON_BOLT, "It's clearing its\rthroat. Kehh!"),
        Line::say(co::JESS, "Halt! Green Earth Coastal\rWatch! Hands where I see them!"),
        Line::say(co::JESS, "By order of... by order.\rOf Green Earth. Stand down!"),
        Line::say(co::STURM, "Your orders do not reach\rthis soil."),
        Line::feel(
            co::JESS,
            Mood::Sad,
            "I know. But Command wants\rthe Foundry. And a report.",
        ),
        Line::say(co::JESS, "I'm sorry. I have to do\rthis properly."),
        Line::say(co::VON_BOLT, "She apologises! Delightful.\rCrush her gently."),
    ])
}

// conditional: Co(co::STURM)
fn m02_pre_sturm() -> Scene {
    Scene::new(vec![Line::say(
        co::STURM,
        "Hold the Foundry. Three\rdays. Then it speaks.",
    )])
}

// conditional: NotCo(co::STURM)
fn m02_pre_other() -> Scene {
    Scene::new(vec![Line::say(
        co::VON_BOLT,
        "Hold the Foundry for\rthree days. It will answer.",
    )])
}

fn m02_day3() -> Scene {
    Scene::new(vec![
        Line::narrate("The Foundry shudders,\rcoughs, and breathes fire."),
        Line::feel(TROOPER, Mood::Happy, "It sneezed a Tank!\rI'm calling him Dennis!"),
        Line::say(co::VON_BOLT, "Free tanks! Free!\rKehh-heh! Beautiful!"),
    ])
}

fn m02_day6() -> Scene {
    Scene::new(vec![Line::say(
        co::JESS,
        "More tanks are coming. Hold\rthe line, Green Earth!",
    )])
}

fn m02_post() -> Scene {
    Scene::new(vec![
        Line::feel(co::JESS, Mood::Sad, "Fall back to the coast.\rFall back!"),
        Line::say(co::JESS, "Green Earth will hear of\rthis. We will return."),
        Line::say(co::STURM, "Return with more. The\rFoundry is always hungry."),
        Line::say(co::VON_BOLT, "She'll tell everyone!\rFree advertising!"),
        Line::say(co::STURM, "Let them hear the storm\rbefore it arrives."),
        Line::say(TROOPER, "Sir? Dennis is fine.\rCan he have a hat?"),
        Line::say(co::STURM, "...He may have a hat."),
    ])
}

fn m02_map() -> Scene {
    Scene::new(vec![
        Line::feel(TROOPER, Mood::Happy, "Dennis has a hat, Sergeant!\rIt's a bucket!"),
        Line::say(TROOPER, "Crumb, that bucket is\rColonel Von Bolt's coin pail."),
        Line::say(co::VON_BOLT, "My PAIL?!"),
        Line::feel(TROOPER, Mood::Sad, "Gerald, run."),
        Line::say(TROOPER, "He's naming the tanks now."),
        Line::say(TROOPER, "Let him. It keeps him\rout of the ammo."),
    ])
}

fn m03_pre() -> Scene {
    Scene::new(vec![
        Line::say(co::DRAKE, "Ahoy, strangers! Welcome\rto the Ember Strait!"),
        Line::say(co::DRAKE, "Population: me, and a few\rhundred ships."),
        Line::say(co::EAGLE, "Don't get comfy. Green\rEarth owns sea and sky."),
        Line::say(co::EAGLE, "Turn around, or I'll make\ryou walk home. On water."),
        Line::say(co::STURM, "We do not turn."),
        Line::say(co::VON_BOLT, "Sturm, I am an old man.\rI am seasick already."),
        Line::say(co::STURM, "Endure it."),
        Line::say(co::DRAKE, "Seasick! Ha! A pirate\rof the dry land!"),
        Line::say(co::VON_BOLT, "Pirate?! I am a\rCREDITOR!"),
        Line::say(co::EAGLE, "Enough. Clear the lanes,\rDrake. I'll cover the sky."),
        Line::say(co::STURM, "Break the blockade. Their\rfleet will drown itself."),
    ])
}

fn m03_day4() -> Scene {
    Scene::new(vec![Line::say(
        co::EAGLE,
        "My Fighters own the\rclouds! Dodge, sailors!",
    )])
}

fn m03_day8() -> Scene {
    Scene::new(vec![Line::say(
        co::DRAKE,
        "Fine, fine! You've got\rsome wave in you after all.",
    )])
}

fn m03_post() -> Scene {
    Scene::new(vec![
        Line::feel(co::DRAKE, Mood::Sad, "...I've been sunk more\rgently by a bathtub."),
        Line::say(co::EAGLE, "Drake, pull out! Fall back\rand regroup!"),
        Line::say(co::EAGLE, "The mainland has real\rpilots. You'll see."),
        Line::say(co::STURM, "The mainland is next."),
        Line::say(co::VON_BOLT, "Gah... my stomach... no\rmore boats. Ever."),
        Line::say(co::HAWKE, "Admirable crossing. I have\rbeen watching."),
        Line::say(co::STURM, "Hawke."),
        Line::say(co::HAWKE, "Marshal Hawke, officially.\rFort Verdant has a road."),
        Line::say(co::HAWKE, "If you can walk it. Do come."),
    ])
}

fn m03_map() -> Scene {
    Scene::new(vec![
        Line::feel(TROOPER, Mood::Sad, "I gave Gerald to a\rseagull. Then took him back."),
        Line::say(TROOPER, "The seagull took the news\rbadly."),
        Line::say(TROOPER, "Sergeant, do you think\rthe COs ever get scared?"),
        Line::say(TROOPER, "The tall one doesn't know\rhow."),
        Line::say(TROOPER, "The old one's scared of\rthe sea. That counts."),
        Line::say(TROOPER, "The mess says the Marshal\rtrusts Sturm and Von Bolt."),
        Line::say(TROOPER, "The mess says a lot. Mostly\rabout the stew."),
        Line::say(co::STURM, "Private."),
        Line::say(TROOPER, "Sir!"),
        Line::say(co::STURM, "Your name."),
        Line::feel(TROOPER, Mood::Happy, "Hobb, sir! Pip Hobb!\rThey call me Crumb!"),
        Line::say(co::STURM, "Noted."),
    ])
}

// --- Rules written in Rust --------------------------------------------------------

/// The player's army (army 1) is led by Sturm.
fn player_is_sturm(core: &mut Core) -> bool {
    let army = crate::ds_campaign::player_army(core) as u32;
    crate::tag::army_co_of(core, army) == co::STURM
}

/// Army 2's first power is ready: its meter is full for a normal power.
fn charge_jess(core: &mut Core) {
    let p = crate::tag::player(core, 2);
    // (the player block: CO +0x1D, powers used +0x25, meter +0x20)
    let (jess, uses) = (core.raw_read_8(p + 0x1D, -1), core.raw_read_8(p + 0x25, -1));
    let full = crate::tag::cop_cost(core, jess, uses);
    if core.raw_read_32(p + 0x20, -1) < full {
        core.raw_write_32(p + 0x20, -1, full);
    }
}

/// The days run out: the mission is lost when the day after the limit begins
/// (the game itself only ranks by days).
fn time_up(limit: u16) -> Trigger {
    Trigger::new(When::TurnStart, Cond::DayAtLeast(limit + 1), vec![Action::Lose])
}

// --- M1 Storm Landing --------------------------------------------------------------

fn bh01() -> MissionDef {
    let mut m = MissionDef::new("bh01", "Storm Landing");
    m.objective = "Take the HQ. Von Bolt wants the biggest account in the world.";
    m.map = MapSrc::Built("bh01");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)).funds(6000),
        // Von Bolt in Green Earth's colours (his stolen surplus).
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::VON_BOLT)).funds(20000),
    ];
    m.day_limit = 20;
    m.rank_days = 10;
    m.intro = m01_pre();
    m.victory = m01_post();
    m.after = m01_map();
    m.recruits = vec![roster::VON_BOLT];
    // The win (Von Bolt routed or his HQ taken): the bond is earned (Sturm is fixed
    // in this mission, so it is automatic), then the victory scene.
    m.on_win = vec![Action::EarnBond(0)];
    m.triggers = vec![
        // Day 3: a Black Hole unit stands in a Crystal's light (within 2 of it).
        Trigger::new(
            When::TurnStart,
            Cond::All(vec![
                Cond::DayAtLeast(3),
                Cond::Any(vec![
                    Cond::UnitsIn {
                        army: 1,
                        area: Rect::new(4, 4, 8, 8),
                        at_least: 1,
                    },
                    Cond::UnitsIn {
                        army: 1,
                        area: Rect::new(13, 6, 17, 10),
                        at_least: 1,
                    },
                ]),
            ]),
            vec![Action::Scene(m01_day3())],
        ),
        // Day 4: the loot sale: with six properties Von Bolt buys two Md Tanks.
        Trigger::new(
            When::TurnStart,
            Cond::All(vec![Cond::DayAtLeast(4), Cond::PropertiesAtLeast { army: 2, n: 6 }]),
            vec![Action::Spawn(vec![
                UnitDef::new(2, unit::MD_TANK, 19, 4),
                UnitDef::new(2, unit::MD_TANK, 21, 4),
            ])],
        ),
        // Day 7: everything must go.
        Trigger::new(When::TurnStart, Cond::DayAtLeast(7), vec![Action::Scene(m01_day7())]),
        time_up(20),
    ];
    m.flag = region::BLACK_HOLE[0];
    m.stars = 1;
    m
}

// --- M2 The Sleeping Foundry ---------------------------------------------------------

fn bh02() -> MissionDef {
    let mut m = MissionDef::new("bh02", "The Sleeping Foundry");
    m.objective = "Hold the Foundry. Rout Green Earth or take its HQ.";
    m.map = MapSrc::Built("bh02");
    m.armies = vec![
        // Pre-deployed: no bases, no funds; the Foundry is the factory.
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(0),
        // Jess has real production (3 bases, an airport, income) and 14000 to start.
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JESS)).funds(14000),
    ];
    m.pool = vec![co::STURM, co::VON_BOLT];
    m.day_limit = 18;
    m.rank_days = 11;
    m.intro = m02_pre();
    m.victory = m02_post();
    m.after = m02_map();
    // The Foundry wakes on day 3 (table F2, docs/BH_CAMPAIGN.md 3.5): the
    // three doors, left to right.
    m.factory = vec![
        (3, [0, unit::TANK, 0]),
        (4, [unit::INFANTRY, 0, unit::INFANTRY]),
        (5, [0, unit::MD_TANK, 0]),
        (6, [unit::MECH, unit::RECON, unit::MECH]),
        (7, [0, 0, unit::TANK]),
        (8, [unit::TANK, 0, unit::TANK]),
        (9, [0, unit::MD_TANK, 0]),
        (10, [unit::INFANTRY, unit::INFANTRY, unit::INFANTRY]),
        (11, [0, unit::TANK, 0]),
        (12, [unit::MECH, 0, unit::MECH]),
        (13, [0, unit::MD_TANK, 0]),
        (14, [unit::TANK, 0, unit::TANK]),
        (16, [0, unit::MD_TANK, 0]),
    ];
    let wave = |units: Vec<UnitDef>| vec![Action::Spawn(units)];
    m.triggers = vec![
        // The last line of the opening is Sturm's own, or whoever else leads.
        Trigger::new(
            When::TurnStart,
            Cond::All(vec![Cond::DayAtLeast(1), Cond::Custom(player_is_sturm)]),
            vec![Action::Scene(m02_pre_sturm())],
        ),
        Trigger::new(
            When::TurnStart,
            Cond::All(vec![
                Cond::DayAtLeast(1),
                Cond::Not(Box::new(Cond::Custom(player_is_sturm))),
            ]),
            vec![Action::Scene(m02_pre_other())],
        ),
        // Day 3: the Foundry wakes; Green Earth's first wave comes up the road.
        Trigger::new(When::TurnStart, Cond::DayAtLeast(3), vec![Action::Scene(m02_day3())]),
        Trigger::new(
            When::TurnStart,
            Cond::DayAtLeast(3),
            wave(vec![
                UnitDef::new(2, unit::TANK, 9, 22),
                UnitDef::new(2, unit::TANK, 10, 22),
                UnitDef::new(2, unit::TANK, 12, 22),
            ]),
        ),
        // Day 6: two Md Tanks and two Infantry.
        Trigger::new(When::TurnStart, Cond::DayAtLeast(6), vec![Action::Scene(m02_day6())]),
        Trigger::new(
            When::TurnStart,
            Cond::DayAtLeast(6),
            wave(vec![
                UnitDef::new(2, unit::MD_TANK, 9, 22),
                UnitDef::new(2, unit::MD_TANK, 10, 22),
                UnitDef::new(2, unit::INFANTRY, 12, 22),
                UnitDef::new(2, unit::INFANTRY, 13, 22),
                UnitDef::new(2, unit::B_COPTER, 17, 22),
            ]),
        ),
        // Day 9: Jess arrives with her first power charged.
        Trigger::new(
            When::TurnStart,
            Cond::DayAtLeast(9),
            vec![
                Action::Custom(charge_jess),
                Action::Spawn(vec![
                    UnitDef::new(2, unit::MD_TANK, 9, 22),
                    UnitDef::new(2, unit::MD_TANK, 10, 22),
                    UnitDef::new(2, unit::ROCKETS, 12, 22),
                ]),
            ],
        ),
        time_up(18),
    ];
    m.flag = region::BLACK_HOLE[4];
    m.stars = 1;
    m
}

// --- M3 Blockade Runner -------------------------------------------------------------

/// The player holds the middle isle: two of its three cities.
fn holds_the_isle() -> Cond {
    let at = |x, y| Cond::OwnerAt { x, y, army: 1 };
    Cond::Any(vec![
        Cond::All(vec![at(11, 9), at(14, 8)]),
        Cond::All(vec![at(11, 9), at(14, 5)]),
        Cond::All(vec![at(14, 8), at(14, 5)]),
    ])
}

fn bh03() -> MissionDef {
    let mut m = MissionDef::new("bh03", "Blockade Runner");
    m.objective = "Break the blockade. Take the east HQ or rout the fleet.";
    m.map = MapSrc::Built("bh03");
    m.armies = vec![
        // The only two COs there are: the "Black Apocalypse" pair.
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pair(co::STURM, co::VON_BOLT)).funds(12000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Pair(co::DRAKE, co::EAGLE)).funds(14000),
    ];
    m.day_limit = 25;
    m.rank_days = 14;
    m.intro = m03_pre();
    m.victory = m03_post();
    m.after = m03_map();
    m.triggers = vec![
        Trigger::new(When::TurnStart, Cond::DayAtLeast(4), vec![Action::Scene(m03_day4())]),
        Trigger::new(
            When::TurnStart,
            Cond::All(vec![Cond::DayAtLeast(8), holds_the_isle()]),
            vec![Action::Scene(m03_day8())],
        ),
        time_up(25),
    ];
    m.flag = region::BLACK_HOLE[5];
    m.stars = 2;
    m.needs = Needs::All(vec!["bh02"]);
    m
}

/// Act 1's missions, in world-map order.
pub fn missions() -> Vec<MissionDef> {
    let mut one = bh01();
    one.needs = Needs::Start;
    let mut two = bh02();
    two.needs = Needs::All(vec!["bh01"]);
    vec![one, two, bh03()]
}
