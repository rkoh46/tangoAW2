//! Act 2: Green Earth (M4 to M10) and the pass out of it (M11). Its missions
//! are `MissionDef`s (docs/AW2.md "BH Campaign": adding a mission); this file
//! is the act's alone, so builders can work on acts in parallel. A mission
//! names what it needs by key (`Needs::All(vec!["bh03"])`), not by index.
//!
//! The maps are `five/bh/bh04.txt` .. `bh11.txt` (built by `five/bhmap.py`
//! into `bh_map_data.rs`: roads, rivers, coasts and shoals joined as AW2 draws
//! them, reachability checked). The dialogue is the design bible's
//! (docs/BH_CAMPAIGN.md section 4.3, branch bh-design): a design row is one
//! box, its `@IF CO` groups are [`Line::only`] lines, its soldiers and
//! narration the Black Hole trooper's face.

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

/// An army's CO meter set to `pct` of its full meter (AW2's units: a CO Power's cost, `cop_cost`,
/// is the first power's full bar).
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

fn charge_army2_60(core: &mut Core) {
    meter(core, 2, 60);
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

// --- World map ---------------------------------------------------------------------

/// Act 2's flags on AW2's Green Earth (the east land, x 300..390, y 85..230), in the design's order
/// (docs/BH_CAMPAIGN.md 2.2, the grid mirrored onto the picture): M4 .. M11. M6 and M7 are the branch.
pub const FLAGS: [(i16, i16); 8] = [
    (350, 95),  // M4 Marshal in Green (north)
    (372, 118), // M5 Night Raid
    (332, 135), // M6 Stepping Stones (west coast, isles)
    (345, 160), // M7 Greenhaven Arsenal (south coast)
    (350, 135), // M8 The Twin Gates (heartland)
    (325, 190), // M9 The Loot Train
    (340, 215), // M10 Evergreen Citadel
    (310, 100), // M11 Exiles' Last Stand (the pass towards Yellow Comet)
];

// --- M4 Marshal in Green -------------------------------------------------------------

fn bh04() -> MissionDef {
    let mut m = MissionDef::new("bh04", "Marshal in Green");
    m.objective = "Capture Fort Verdant or rout Hawke.";
    m.map = MapSrc::Built("bh04");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(8000),
        // Hawke commands Green Earth's northern army in its colours.
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::HAWKE)).funds(18000),
    ];
    m.pool = vec![co::STURM, co::VON_BOLT];
    m.fog = true;
    m.day_limit = 20;
    m.rank_days = 12;
    m.intro = Scene::new(vec![
        troop("Green Earth, the northern march. Fog, forest, a Marshal."),
        say(co::HAWKE, "Welcome. You walked my road without tripping."),
        say(co::HAWKE, "That is rarer than you think."),
        say(co::STURM, "I did not come to be praised.").only(co::STURM),
        say(co::HAWKE, "Of course not. Praise is for people who need it.").only(co::STURM),
        say(co::VON_BOLT, "Flattery! Does it come with a fee?").only(co::VON_BOLT),
        say(co::HAWKE, "A courtesy, Colonel. Free, this once.").only(co::VON_BOLT),
        say(co::HAWKE, "I serve Green Earth. In name. In green. In habit."),
        say(co::HAWKE, "But I have waited for someone worth serving."),
        say(co::HAWKE, "Show me. No wasted orders. No wasted men."),
        say(co::HAWKE, "The fog is mine. I like my odds."),
        troop("Sir, is he allowed to say that out loud?"),
        say(co::HAWKE, "Who is this?"),
        troop("Pip Hobb, sir! Runner!"),
        say(co::HAWKE, "A runner. How quaint."),
    ]);
    m.victory = Scene::new(vec![
        sad(co::HAWKE, "Check. Not mate, but check. I concede the valley."),
        say(co::HAWKE, "Before I fold: why should I serve you?"),
        say(co::STURM, "You will not serve. You will command beside me.").only(co::STURM),
        say(co::STURM, "Write the doctrine. I will supply the storm.").only(co::STURM),
        say(co::HAWKE, "A storm without a captain wrecks only itself.").only(co::STURM),
        say(co::STURM, "Then be the captain. Not mine. The storm's.").only(co::STURM),
        say(co::HAWKE, "...Interesting. That is a different offer.").only(co::STURM),
        say(co::VON_BOLT, "Marshal, the pay is the world. In writing.").only(co::VON_BOLT),
        say(co::VON_BOLT, "Every vault and port. You choose the quarter.").only(co::VON_BOLT),
        say(co::HAWKE, "You sell me an empire by the quarter.").only(co::VON_BOLT),
        say(co::VON_BOLT, "By the ton!").only(co::VON_BOLT),
        say(co::HAWKE, "Crude. Effective. I like the ledger.").only(co::VON_BOLT),
        say(co::HAWKE, "I accept. But I will correct your orders."),
        say(co::HAWKE, "Every army needs a mind. I volunteer mine."),
        troop("Does the Marshal need a runner, sir?"),
        say(co::HAWKE, "...Fine. You. Do not run into me."),
    ]);
    m.after = Scene::new(vec![
        troop("Runner Hobb reporting! The Marshal's tea is cold!"),
        troop("Why did you tell him?"),
        troop("He asked."),
        troop("He's polite about it."),
        troop("He said \"adequate\". I think that's a medal."),
        troop("The radio man liked both bosses, Sergeant. Could tell."),
        troop("Gerald says either would do for the Marshal."),
    ]);
    m.triggers = vec![
        // Hawke's Md Tank wedge arrives on day 4 if the Marshal's valley was not scouted.
        on_day(
            4,
            Some(Cond::Not(Box::new(Cond::UnitsIn { army: 1, area: Rect::new(10, 0, 23, 17), at_least: 1 }))),
            vec![Action::Spawn(vec![
                UnitDef::new(2, unit::MD_TANK, 16, 8),
                UnitDef::new(2, unit::MD_TANK, 16, 10),
                UnitDef::new(2, unit::MD_TANK, 17, 7),
            ])],
        ),
        on_day(5, None, vec![Action::Scene(Scene::new(vec![say(co::HAWKE, "Fog is a curtain. I decide what the audience sees.")]))]),
        // Hawke's power is charged by day 6.
        on_day(6, None, vec![Action::Custom(charge_army2_full)]),
        on_day(10, None, vec![Action::Scene(Scene::new(vec![say(co::HAWKE, "Impressive. You have reduced the fog to a rumour.")]))]),
        // The win (the pitch is the victory scene; the bond is earned with it).
        after(beaten(2, (21, 9)), vec![Action::EarnBond(1), Action::Win]),
    ];
    m.recruits = vec![roster::HAWKE];
    m.needs = Needs::All(vec!["bh03"]);
    m.flag = FLAGS[0];
    m.stars = 2;
    m
}


// --- M5 Night Raid -------------------------------------------------------------------

/// Every parked aircraft of Green Earth (Fighters and Bombers) is destroyed.
fn aircraft_destroyed(core: &mut Core) -> bool {
    units_of(core, 2).iter().all(|u| u.1 != unit::FIGHTER && u.1 != unit::BOMBER)
}

fn bh05() -> MissionDef {
    let mut m = MissionDef::new("bh05", "Night Raid");
    m.objective = "Destroy 8 aircraft, take the Com Tower. 9 days.";
    m.map = MapSrc::Built("bh05");
    // A pre-deployed raid: no bases, no funds, on either side.
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(0),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JAVIER)).funds(0),
    ];
    m.fog = true;
    m.day_limit = 9;
    m.rank_days = 7;
    let mut v = vec![
        say(co::HAWKE, "Skyhaven by moonlight. Eagle's aircraft sleep."),
        say(co::HAWKE, "Javier's tower hears a mouse sneeze at two miles."),
        say(co::JAVIER, "This is Javier on all channels. All! You are heard!"),
        say(co::JAVIER, "Intruders: please be unheard. It is bad manners."),
        say(co::HAWKE, "Eight aircraft on the tarmac. Nine days."),
        say(co::HAWKE, "I picked the night. Do not waste it.").only(co::HAWKE),
        say(co::STURM, "Fire in the dark is quieter than people expect.").only(co::STURM),
        say(co::VON_BOLT, "Eight aircraft! A hundred coins each! Kehh!").only(co::VON_BOLT),
        troop("I have the lantern, sir!"),
        say(co::HAWKE, "Put it out."),
        troop("...Yes, sir."),
    ];
    m.intro = Scene::new(std::mem::take(&mut v));
    m.victory = Scene::new(vec![
        sad(co::JAVIER, "The tower's out. I can't... why is it quiet?"),
        say(co::JAVIER, "Eagle will hear of this! Eventually!"),
        say(co::HAWKE, "Eight aircraft. No losses of mine. Tidy."),
        troop("Sir, I put the lantern out. Mostly."),
    ]);
    m.after = Scene::new(vec![
        troop("I saw a bomber go up like a firework."),
        troop("It was a lovely colour, Wick."),
        troop("Somebody's job was that bomber."),
        troop("...Yes. Right. Sorry."),
        troop("Eat something, Crumb."),
    ]);
    m.triggers = vec![
        // The alarm: three Tanks and two Anti-Air arrive by the east road.
        on_day(
            3,
            None,
            vec![
                Action::Scene(Scene::new(vec![say(co::JAVIER, "Alarm! Alarm! I like alarms. Everyone, up!")])),
                Action::Spawn(vec![
                    UnitDef::new(2, unit::TANK, 23, 8),
                    UnitDef::new(2, unit::TANK, 23, 7),
                    UnitDef::new(2, unit::TANK, 23, 9),
                    UnitDef::new(2, unit::ANTI_AIR, 23, 6),
                    UnitDef::new(2, unit::ANTI_AIR, 23, 10),
                ]),
            ],
        ),
        on_day(6, None, vec![Action::Scene(Scene::new(vec![say(co::JAVIER, "Flares! I am extremely bright, you see.")]))]),
        // Eight aircraft gone and the tower taken.
        after(Cond::All(vec![Cond::Custom(aircraft_destroyed), Cond::OwnerAt { x: 19, y: 3, army: 1 }]), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh04"]);
    m.flag = FLAGS[1];
    m.stars = 2;
    m
}

// --- M6 Stepping Stones --------------------------------------------------------------

fn bh06() -> MissionDef {
    let mut m = MissionDef::new("bh06", "Stepping Stones");
    m.objective = "Hop the isles and capture Drake's HQ.";
    m.map = MapSrc::Built("bh06");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(12000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::DRAKE)).funds(22000),
    ];
    m.day_limit = 22;
    m.rank_days = 16;
    m.intro = Scene::new(vec![
        say(co::DRAKE, "Welcome to my pond! Mind the pelicans."),
        say(co::DRAKE, "Five islands. Five ways to get your feet wet."),
        say(co::DRAKE, "I always say: the sea is just the long way round."),
        say(co::VON_BOLT, "No boats. I said no boats!").only(co::VON_BOLT),
        say(co::HAWKE, "Island chain. Supply is the whole war.").only(co::HAWKE),
        say(co::STURM, "Tides obey. The rest follows.").only(co::STURM),
        troop("Sir, the Lander says \"welcome aboard\". Smiling."),
        troop("...I think that's a wave."),
    ]);
    let mut post = vec![
        sad(co::DRAKE, "Abandon ship! ...Politely."),
        say(co::DRAKE, "Best loss I've had all year. Come for a drink!"),
        say(co::STURM, "No.").only(co::STURM),
        say(co::DRAKE, "Ha! Tough crowd. Next time.").only(co::STURM),
    ];
    for c in [co::VON_BOLT, co::HAWKE] {
        post.push(say(c, "Another time. When the war is over.").only(c));
        post.push(say(co::DRAKE, "Deal. I'll bring snacks.").only(c));
    }
    m.victory = Scene::new(post);
    m.after = Scene::new(vec![
        troop("I think the sea is angry at me, Wick."),
        troop("You were sick on the Lander."),
        troop("I was sick in solidarity."),
        troop("With who?"),
        troop("The fish."),
    ]);
    m.triggers = vec![
        on_day(5, None, vec![Action::Scene(Scene::new(vec![say(co::DRAKE, "Fighters off the Carrier! Wave hello!")]))]),
        // The Carrier launches Fighters every third day from day 5 (from its isle's air).
        Trigger::new(When::TurnStart, Cond::EveryDays { n: 3, from: 5 }, vec![Action::Spawn(vec![UnitDef::new(2, unit::FIGHTER, 24, 10)])]).repeating(),
        on_day(12, None, vec![Action::Scene(Scene::new(vec![say(co::DRAKE, "Hey! Do not sink my sandwich boat!")]))]),
        after(beaten(2, (28, 14)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh05"]);
    m.flag = FLAGS[2];
    m.stars = 2;
    m
}

// --- M7 Greenhaven Arsenal -----------------------------------------------------------

/// Factory table F7 (docs/BH_CAMPAIGN.md 3.5): per day the three doors' units (0 none).
const F7: [(u8, [u8; 3]); 10] = [
    (2, [unit::TANK, 0, unit::TANK]),
    (3, [0, unit::ANTI_AIR, 0]),
    (4, [unit::MD_TANK, 0, 0]),
    (5, [unit::MISSILES, unit::MECH, 0]),
    (6, [0, unit::NEOTANK, 0]),
    (7, [unit::INFANTRY, unit::INFANTRY, unit::INFANTRY]),
    (9, [0, unit::RECON, unit::ANTI_AIR]),
    (11, [unit::MD_TANK, 0, unit::MD_TANK]),
    (13, [0, unit::OOZIUM, 0]),
    (15, [unit::NEOTANK, 0, unit::ANTI_AIR]),
];

fn bh07() -> MissionDef {
    let mut m = MissionDef::new("bh07", "Greenhaven Arsenal");
    m.objective = "Wake the Black Factory, take Eagle's HQ.";
    m.map = MapSrc::Built("bh07");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(7000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::EAGLE)).funds(18000),
    ];
    m.day_limit = 22;
    m.rank_days = 14;
    m.factory = F7.to_vec();
    m.intro = Scene::new(vec![
        say(co::EAGLE, "Greenhaven! The Arsenal of the south! My home field!"),
        say(co::EAGLE, "I'm the sky, you're the ground. That's the whole war."),
        say(co::EAGLE, "Fly with me, or fall without me!"),
        say(co::HAWKE, "The crane yard hides a second Foundry. Wake it."),
        say(co::HAWKE, "He announces his plans to everyone. Convenient.").only(co::HAWKE),
        say(co::STURM, "Overhead is not above.").only(co::STURM),
        say(co::VON_BOLT, "A shipyard! Cranes! Gold!").only(co::VON_BOLT),
    ]);
    m.victory = Scene::new(vec![
        sad(co::EAGLE, "I never lose in the air. This was ground."),
        say(co::EAGLE, "I'll be back. In a bigger plane."),
        say(co::HAWKE, "Arsenals do not forgive. Neither do I."),
    ]);
    m.after = Scene::new(vec![
        troop("The Oozium followed me to the latrine, Sergeant."),
        troop("Then he knows where your biscuit is."),
        troop("Gerald is NOT a food."),
    ]);
    m.triggers = vec![
        on_day(6, None, vec![Action::Scene(Scene::new(vec![say(co::EAGLE, "Bombers! Show them what weather is!")]))]),
        // Eagle's funds: +5000 on day 10, a second Bomber on day 12.
        on_day(10, None, vec![Action::AddFunds { army: 2, funds: 5000 }]),
        on_day(12, None, vec![Action::Spawn(vec![UnitDef::new(2, unit::BOMBER, 22, 17)])]),
        on_day(
            13,
            None,
            vec![Action::Scene(Scene::new(vec![
                troop("The Foundry made an Oozium! It looks at me!"),
                say(co::HAWKE, "Do not feed it."),
                troop("...Gerald is hiding."),
            ]))],
        ),
        after(beaten(2, (21, 16)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh05"]);
    m.flag = FLAGS[3];
    m.stars = 2;
    m
}

// --- M8 The Twin Gates ---------------------------------------------------------------

/// The second front's outcome (crate::two_front's state byte: 2 won, 3 lost).
fn second_front_won(core: &mut Core) -> bool {
    core.raw_read_8(0x0203_E401, -1) == 2
}

fn second_front_lost(core: &mut Core) -> bool {
    core.raw_read_8(0x0203_E401, -1) == 3
}

fn bh08() -> MissionDef {
    let mut m = MissionDef::new("bh08", "The Twin Gates");
    m.objective = "Take both gates. The dusk gate's CO joins.";
    m.map = MapSrc::Built("bh08");
    // The player picks two COs: the main front's, then the second front's.
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(8000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JESS)).funds(14000),
    ];
    m.day_limit = 22;
    m.rank_days = 16;
    // The dusk gate's Black Factory is dormant (an all-zero table): AW2's computer-Black-Hole turn calls
    // the factory spawner, which on a map without a factory wrote garbage and reset the game on day 2 (the
    // player's army there is played by Auto CO).
    m.factory = vec![(0, [0, 0, 0])];
    m.front2 = Some(FrontDef {
        map: MapSrc::Built("bh08b"),
        props: Vec::new(),
        structures: Vec::new(),
        units: built_units("bh08b"),
        cos: [CoSpec::Pick, CoSpec::Fixed(co::JAVIER), CoSpec::None, CoSpec::None],
        send: SendRule::Ground,
        sky: false,
        weather: Weather::Clear,
        fog: false,
    });
    m.intro = Scene::new(vec![
        say(co::JESS, "Two gates, two fronts. Standard procedure!"),
        say(co::JAVIER, "And I'm on both radios! Hello, both of you!"),
        say(co::JESS, "Javier, you needn't announce that."),
        say(co::JAVIER, "It is cheaper than a second Javier."),
        say(co::HAWKE, "One mind, two fronts. Split the sword."),
        say(co::HAWKE, "Choose your hands. The dawn gate and the dusk gate."),
    ]);
    m.victory = Scene::new(vec![
        sad(co::JESS, "Javier, fall back. We hold the keep."),
        say(co::JAVIER, "I would like to say I meant that. I did not."),
        say(co::HAWKE, "Two gates. Both open. On to the capital."),
    ]);
    m.after = Scene::new(vec![
        troop("Marshal! The messages from both fronts arrived!"),
        say(co::HAWKE, "At the same time?"),
        troop("Mostly. One of them was a pigeon."),
        say(co::HAWKE, "...Interesting."),
    ]);
    let mut won_lines = Vec::new();
    for c in [co::STURM, co::VON_BOLT, co::HAWKE] {
        won_lines.push(say(c, "The dusk gate is ours. Reporting to the main front.").only_partner(c));
    }
    m.triggers = vec![
        Trigger::new(When::TurnStart, Cond::Custom(second_front_won), vec![Action::Scene(Scene::new(won_lines))]),
        Trigger::new(
            When::TurnStart,
            Cond::Custom(second_front_lost),
            vec![Action::Scene(Scene::new(vec![say(co::JAVIER, "Static! Sorry! Not sorry! Your gate is mine!")]))],
        ),
        after(beaten(2, (22, 9)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh06", "bh07"]);
    m.flag = FLAGS[4];
    m.stars = 3;
    m
}

// --- M9 The Loot Train ---------------------------------------------------------------

/// The yard of the east port (26, 7): where the Vault APCs must arrive.
const PORT_YARD: Rect = Rect::new(24, 6, 26, 8);
const VAULTS: [&str; 3] = ["vault1", "vault2", "vault3"];

/// (Vault APCs alive, of them in the port's yard).
fn vaults(core: &mut Core) -> (usize, usize) {
    let (mut alive, mut home) = (0, 0);
    for n in VAULTS {
        if let Some((a, true)) = unit_by_name(core, n) {
            alive += 1;
            if PORT_YARD.has(core.raw_read_8(a + 2, -1), core.raw_read_8(a + 3, -1)) {
                home += 1;
            }
        }
    }
    (alive, home)
}

/// All three trucks are home.
fn all_three_home(core: &mut Core) -> bool {
    vaults(core) == (3, 3)
}

/// Two trucks are home and the third is gone.
fn two_home_third_gone(core: &mut Core) -> bool {
    vaults(core) == (2, 2)
}

/// Fewer than two trucks survive.
fn trucks_lost(core: &mut Core) -> bool {
    vaults(core).0 < 2
}

/// A truck has passed the first bridge (x = 8): Javier's comms raise the alarm.
fn alarm(core: &mut Core) -> bool {
    VAULTS.iter().any(|n| unit_by_name(core, n).is_some_and(|(a, alive)| alive && core.raw_read_8(a + 2, -1) >= 8))
}

fn bh09() -> MissionDef {
    let mut m = MissionDef::new("bh09", "The Loot Train");
    m.objective = "Escort 2 of 3 Vault APCs to the east port.";
    m.map = MapSrc::Built("bh09");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(0),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Pair(co::JAVIER, co::DRAKE)).funds(0),
    ];
    m.fog = true;
    m.day_limit = 16;
    m.rank_days = 12;
    m.intro = Scene::new(vec![
        say(co::VON_BOLT, "My vault! My vault trucks! Three, plus bribes."),
        say(co::HAWKE, "Why are we moving your treasure through enemy land?"),
        say(co::VON_BOLT, "Because the bank is closed. I trust only me."),
        troop("Sir, there is a rooster on the lead truck."),
        say(co::VON_BOLT, "His name is Interest."),
        say(co::JAVIER, "This is Javier. I see trucks. They go east."),
        say(co::DRAKE, "Three trucks, three guys, three problems. Welcome!"),
    ]);
    m.after = Scene::new(vec![
        troop("Sir, Interest the rooster pecked the Colonel."),
        troop("Is that a salute?"),
        troop("Hard to tell. I think he's good with money."),
    ]);
    m.triggers = vec![
        on_day(4, None, vec![Action::Scene(Scene::new(vec![say(co::DRAKE, "Ambush! Ha! I always wanted to say that.")]))]),
        on_day(9, None, vec![Action::Scene(Scene::new(vec![say(co::JAVIER, "The east road is mine. Turn back, turn back!")]))]),
        // Javier's comms: a truck past the first bridge wakes a pursuit behind it.
        Trigger::new(
            When::AfterAction,
            Cond::Custom(alarm),
            vec![Action::Spawn(vec![
                UnitDef::new(2, unit::TANK, 0, 6),
                UnitDef::new(2, unit::TANK, 0, 8),
                UnitDef::new(2, unit::RECON, 0, 7),
            ])],
        ),
        after(
            Cond::Custom(all_three_home),
            vec![
                Action::Scene(Scene::new(vec![
                    say(co::VON_BOLT, "All three! Kehh-heh! Not one coin missing!"),
                    say(co::VON_BOLT, "Interest is laying eggs. Golden ones. Perhaps."),
                ])),
                Action::Win,
            ],
        ),
        after(
            Cond::Custom(two_home_third_gone),
            vec![
                Action::Scene(Scene::new(vec![
                    sad(co::VON_BOLT, "One truck gone... ...my coins, my poor coins."),
                    say(co::HAWKE, "Seventy per cent. Within tolerance."),
                    say(co::VON_BOLT, "TOLERANCE?!"),
                ])),
                Action::Win,
            ],
        ),
        after(Cond::Custom(trucks_lost), vec![Action::Lose]),
    ];
    m.needs = Needs::All(vec!["bh08"]);
    m.flag = FLAGS[5];
    m.stars = 3;
    m
}

// --- M10 Evergreen Citadel -----------------------------------------------------------

fn bh10() -> MissionDef {
    let mut m = MissionDef::new("bh10", "Evergreen Citadel");
    m.objective = "Siege the Citadel and capture its HQ.";
    m.map = MapSrc::Built("bh10");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(5000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Pair(co::EAGLE, co::JESS)).funds(25000),
    ];
    m.day_limit = 24;
    m.rank_days = 16;
    let mut intro = vec![
        say(co::JESS, "This is Evergreen. It has never fallen. Never!"),
        say(co::EAGLE, "Fly, fight, win. That is all we have left!"),
        say(co::HAWKE, "A siege is mathematics. Eagle forgets arithmetic."),
        say(co::JESS, "Why do this? Your army wears our colour!"),
        say(co::HAWKE, "It was a good colour. It suited the ministry."),
        sad(co::JESS, "...Marshal. I admired you."),
        say(co::HAWKE, "I admired my plan more."),
    ];
    intro.extend(anyone("Tonight Green Earth learns what a storm is."));
    m.intro = Scene::new(intro);
    m.victory = Scene::new(vec![
        sad(co::JESS, "The Citadel... has fallen."),
        say(co::EAGLE, "Retreat east! To the Comets! Do not stop!"),
        say(co::JESS, "I'm sorry. I could not protect them."),
        say(co::HAWKE, "You did well. Be proud of that."),
    ]);
    m.after = Scene::new(vec![
        troop("Hobb! The Marshal says you carry the flag."),
        troop("Which flag?"),
        troop("Ours."),
        troop("I'm Standard-Bearer?!"),
        troop("By accident. Don't drop it."),
        troop("Gerald, I'm a Standard-Bearer! Look!"),
    ]);
    m.triggers = vec![
        // Eagle and Jess start with their powers 60% charged.
        on_day(1, None, vec![Action::Custom(charge_army2_60)]),
        on_day(6, None, vec![Action::Scene(Scene::new(vec![say(co::JESS, "A beam! Of course there is a beam!")]))]),
        on_day(12, None, vec![Action::Scene(Scene::new(vec![say(co::EAGLE, "Jess! The wall is cracking! Hold!")]))]),
        after(beaten(2, (14, 3)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh09"]);
    m.flag = FLAGS[6];
    m.stars = 3;
    m
}

// --- M11 Exiles' Last Stand ----------------------------------------------------------

fn bh11() -> MissionDef {
    let mut m = MissionDef::new("bh11", "Exiles' Last Stand");
    m.objective = "Break Green Earth and Yellow Comet at the pass.";
    m.map = MapSrc::Built("bh11");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(14000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JAVIER)).team(2).funds(9000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::SENSEI)).team(2).funds(9000),
    ];
    m.day_limit = 22;
    m.rank_days = 15;
    m.intro = Scene::new(vec![
        say(co::SENSEI, "Easy there, youngsters. This pass is old as I am."),
        say(co::SENSEI, "Green Earth's refugees asked for a roof. I gave one."),
        say(co::JAVIER, "And a radio! He gave me a radio! I love him!"),
        say(co::SENSEI, "Do not love me. Hold the left gap."),
        say(co::HAWKE, "Sensei. You taught me to read maps.").with(co::HAWKE),
        say(co::SENSEI, "I taught you maps. You chose the wrong ones.").with(co::HAWKE),
        say(co::VON_BOLT, "Another old man! Shall we compare ages?").with(co::VON_BOLT),
        say(co::SENSEI, "I am older. And I have my own teeth.").with(co::VON_BOLT),
        say(co::VON_BOLT, "...Mine are in a vault.").with(co::VON_BOLT),
    ]);
    // ([CO]: the lead's line)
    let mut intro_tail = Vec::new();
    intro_tail.extend(anyone("Two armies, one pass. Cut them apart."));
    m.intro.lines.extend(intro_tail);
    m.victory = Scene::new(vec![
        sad(co::SENSEI, "Hmph. Old bones, beaten by a gale."),
        say(co::JAVIER, "Retreat? Yes! I have a very good one ready!"),
        say(co::SENSEI, "Tell Kanbei the storm is faster than gossip."),
    ]);
    m.after = Scene::new(vec![
        say(co::HAWKE, "Two names turned up on the old rolls. Koal. Kindle."),
        say(co::HAWKE, "Koal is building Yellow Comet a road. A very long one."),
        say(co::VON_BOLT, "And Kindle! She owes me fourteen thousand!"),
        say(co::HAWKE, "She runs their festival."),
        troop("Do they know we're coming, sir?"),
        say(co::HAWKE, "Everyone knows. The question is who will mind."),
        troop("A farmer says Mr Koal listens to Sturm and Hawke."),
        troop("Roads and orders, he said. I wrote it on my sleeve."),
    ]);
    let paratroopers = vec![
        UnitDef::new(3, unit::INFANTRY, 1, 6),
        UnitDef::new(3, unit::INFANTRY, 1, 12),
        UnitDef::new(3, unit::INFANTRY, 2, 7),
        UnitDef::new(3, unit::INFANTRY, 2, 11),
        UnitDef::new(3, unit::INFANTRY, 3, 6),
    ];
    m.triggers = vec![
        on_day(
            5,
            None,
            vec![Action::Scene(Scene::new(vec![say(co::SENSEI, "Paratroopers! Jump, you lazy sparrows!")])), Action::Spawn(paratroopers.clone())],
        ),
        on_day(10, None, vec![Action::Spawn(paratroopers)]),
        after(Cond::All(vec![beaten(2, (23, 3)), beaten(3, (23, 15))]), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh10"]);
    m.flag = FLAGS[7];
    m.stars = 3;
    m
}

/// A line any of the three COs the player may be ([CO]): one row for each, shown for its own player.
fn anyone(text: &'static str) -> Vec<Line> {
    [co::STURM, co::VON_BOLT, co::HAWKE].iter().map(|&c| say(c, text).only(c)).collect()
}

/// Act 2's missions, in world-map order.
pub fn missions() -> Vec<MissionDef> {
    let mut v = Vec::new();
    // (until act 1's M3 is in the tree, a placeholder keeps act 2's `needs` valid)
    if !crate::bh_act1::missions().iter().any(|m| m.key == "bh03") {
        v.push(dev_stub_bh03());
    }
    v.push(bh04());
    v.push(bh05());
    v.push(bh06());
    v.push(bh07());
    v.push(bh08());
    v.push(bh09());
    v.push(bh10());
    v.push(bh11());
    // The day limit loses: the day after the last is the defeat (the header's counter only shows it).
    for m in v.iter_mut().filter(|m| m.key >= "bh04") {
        if m.day_limit > 0 {
            let up = Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: m.day_limit + 1 }, vec![Action::Lose]).repeating();
            m.triggers.push(up);
        }
    }
    v
}

/// Development fallback: a stand-in for act 1's M3 when it is not in the tree yet.
fn dev_stub_bh03() -> MissionDef {
    let mut m = MissionDef::new("bh03", "Placeholder Three");
    m.objective = "Rout the Green Earth force.";
    m.map = MapSrc::Ascii(&["1.........", "..ff..c...", "....mm....", "...c..c...", ".........2"]);
    m.armies = vec![ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)), ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::DRAKE))];
    m.units = vec![UnitDef::new(1, unit::INFANTRY, 1, 1), UnitDef::new(2, unit::INFANTRY, 8, 3)];
    m.needs = Needs::All(vec!["bh02"]);
    m.flag = region::BLACK_HOLE[2];
    m
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
    fn act_two_is_m4_to_m11_in_order() {
        let keys: Vec<&str> = missions().iter().map(|m| m.key).filter(|k| *k >= "bh04").collect();
        assert_eq!(keys, ["bh04", "bh05", "bh06", "bh07", "bh08", "bh09", "bh10", "bh11"]);
    }

    #[test]
    fn every_map_is_built_and_every_mission_has_scenes_and_a_flag_in_green_earth() {
        for m in missions().iter().filter(|m| m.key >= "bh04") {
            let MapSrc::Built(name) = &m.map else { panic!("{}: not a built map", m.key) };
            assert!(crate::bh_map_data::MAPS.iter().any(|b| b.name == *name), "{}: map {name} is not built (five/bhmap.py)", m.key);
            if let Some(f) = &m.front2 {
                let MapSrc::Built(n2) = &f.map else { panic!("{}: second front not built", m.key) };
                assert!(crate::bh_map_data::MAPS.iter().any(|b| b.name == *n2), "{}: map {n2}", m.key);
            }
            assert!(!m.intro.is_empty() && !m.after.is_empty(), "{}: scenes", m.key);
            // AW2's Green Earth, the east land
            assert!((300..=390).contains(&m.flag.0) && (85..=230).contains(&m.flag.1), "{}: flag {:?} off Green Earth", m.key, m.flag);
        }
    }

    #[test]
    fn the_branch_and_the_gate() {
        let ms = missions();
        let get = |k: &str| ms.iter().find(|m| m.key == k).unwrap();
        assert_eq!(get("bh06").needs, Needs::All(vec!["bh05"]));
        assert_eq!(get("bh07").needs, Needs::All(vec!["bh05"]));
        assert_eq!(get("bh08").needs, Needs::All(vec!["bh06", "bh07"]));
        assert_eq!(get("bh04").recruits, vec![roster::HAWKE]);
        assert!(get("bh04").triggers.iter().any(|t| t.then.iter().any(|a| matches!(a, Action::EarnBond(1)))));
    }

    /// Every line of every scene fits one box (two lines of AW2's 176 pixels).
    /// Run with the AW2 ROM: `TANGOAW2_AW2_ROM=... cargo test -p tango-gamesupport-aw2 --lib bh_act2 -- --ignored`.
    #[test]
    #[ignore]
    fn dialogue_fits_the_boxes() {
        let rom = std::fs::read(std::env::var("TANGOAW2_AW2_ROM").unwrap()).unwrap();
        let widths = rom[0x4C_36E4..][..256].to_vec();
        let mut checked = 0;
        for m in missions().iter().filter(|m| m.key >= "bh04") {
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
