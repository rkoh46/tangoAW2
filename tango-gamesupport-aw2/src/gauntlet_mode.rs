//! The Gauntlet mode's maps (docs/dev/gauntlet.md "The Gauntlet mode"): one battle per map against a fixed line-up of COs who come one after another, the player
//! with a free pick of one CO. Each map is a mission of a small custom campaign ([`def`]) played by the campaign engine (AW2's event engine runs only there), so the
//! gauntlet engine ([`crate::custom_campaign`]: `MissionDef::hidden`, `sleepers`, `cut_off`, `Action::Reveal`, `Cond::LineFallen`) works as in BH2's M31.
//! A new map is a spec (`five/gauntlet/spec/gauntlet_NN.py`, `aw2dev maps gen --campaign gauntlet`) and a function here added to [`def`]'s missions.

use mgba::core::Core;

use crate::custom_campaign::{co, colour, unit, *};

/// The Gauntlet's index in [`crate::campaign_model::SOURCES`].
pub const SOURCE: usize = 4;

/// Every CO the player may pick (all open from the start): AW2's, Dual Strike's, then tangoAW2's own.
pub const ROSTER: [(u8, bool); 35] = [
    (co::ANDY, true),
    (co::MAX, true),
    (co::SAMI, true),
    (co::NELL, true),
    (co::OLAF, true),
    (co::GRIT, true),
    (co::COLIN, true),
    (co::KANBEI, true),
    (co::SONJA, true),
    (co::SENSEI, true),
    (co::EAGLE, true),
    (co::DRAKE, true),
    (co::JESS, true),
    (co::HACHI, true),
    (co::STURM, true),
    (co::FLAK, true),
    (co::LASH, true),
    (co::ADDER, true),
    (co::HAWKE, true),
    (co::JAKE, true),
    (co::RACHEL, true),
    (co::SASHA, true),
    (co::GRIMM, true),
    (co::JAVIER, true),
    (co::JUGGER, true),
    (co::KOAL, true),
    (co::KINDLE, true),
    (co::VON_BOLT, true),
    (co::CLONE_ANDY, true),
    (co::CRUMB, true),
    (crate::es_co::TABITHA, true),
    (crate::es_co::LILI, true),
    (crate::es_co::CAULDER, true),
    (crate::co_new::ASUKA, true),
    (crate::co_new::ARIA, true),
];

/// A line falls: the player holds its HQ, or its army was destroyed (the gauntlet engine's [`Cond::LineFallen`]).
fn fell(c: (u8, u8)) -> Cond {
    Cond::LineFallen { x: c.0, y: c.1 }
}

/// A wave: `kind` on each cell for `army`, every unit attacking (a taken cell lands on the nearest free one it can enter: `custom_campaign::landing`).
fn spawn(army: u8, list: &[(u8, (u8, u8))]) -> Action {
    Action::Spawn(list.iter().map(|&(k, (x, y))| UnitDef::new(army, k, x, y).attack()).collect())
}

/// The next CO arrives when the line at `hq` falls (and every line before it): the scene, the reveal (its HQ built, its zone's properties its own), its war chest, its wave.
fn arrive(hq: (u8, u8), before: &[(u8, u8)], army: u8, chest: fn(&mut Core), wave: &[(u8, (u8, u8))], scene: Scene) -> Trigger {
    let mut all = vec![fell(hq)];
    all.extend(before.iter().map(|&c| fell(c)));
    Trigger::new(When::AfterAction, Cond::All(all), vec![Action::Scene(scene), Action::Reveal(army), Action::Custom(chest), spawn(army, wave)])
}

/// An arriving army's funds: `base` and `rate` for every day before today (the slower the player, the richer the next line; it earns nothing while it sleeps: `cut_funds`).
fn war_chest(core: &mut Core, army: u8, base: u32, rate: u32) {
    let day = crate::custom_campaign::day(core).max(1) as u32;
    let p = crate::five::players(core) + 0x3C * army as u32;
    let f = core.raw_read_32(p, -1);
    core.raw_write_32(p, -1, (f + base + rate * (day - 1)).min(999_999));
}

// --- Gauntlet 01, Cinder Sea -------------------------------------------------------------------------------------------------------------------------------

/// The HQs (five/gauntlet/spec/gauntlet_01.py): the player's, Drake's, Sensei's (hidden), Hawke's (hidden).
pub const CINDER_PLAYER: (u8, u8) = (3, 18);
pub const CINDER_DRAKE: (u8, u8) = (27, 18);
pub const CINDER_SENSEI: (u8, u8) = (3, 3);
pub const CINDER_HAWKE: (u8, u8) = (29, 3);

/// Sensei's wave: copters and airborne infantry on the north-west island, a Fighter, a Cruiser off its port.
const SENSEI_WAVE: [(u8, (u8, u8)); 12] = [
    (unit::B_COPTER, (5, 3)),
    (unit::B_COPTER, (8, 3)),
    (unit::B_COPTER, (4, 5)),
    (unit::B_COPTER, (8, 6)),
    (unit::T_COPTER, (2, 5)),
    (unit::MECH, (5, 4)),
    (unit::MECH, (6, 4)),
    (unit::INFANTRY, (3, 5)),
    (unit::INFANTRY, (5, 6)),
    (unit::FIGHTER, (6, 3)),
    (unit::ANTI_AIR, (2, 4)),
    (unit::CRUISER, (10, 5)),
];

/// Hawke's wave: Bombers, a Stealth and a Fighter over the volcano island, troops on it, a carrier group and a Black Boat off its shores.
const HAWKE_WAVE: [(u8, (u8, u8)); 12] = [
    (unit::BOMBER, (28, 4)),
    (unit::BOMBER, (29, 6)),
    (unit::STEALTH, (30, 4)),
    (unit::FIGHTER, (30, 2)),
    (unit::INFANTRY, (28, 3)),
    (unit::INFANTRY, (29, 2)),
    (unit::ANTI_AIR, (30, 5)),
    (unit::MISSILES, (22, 7)),
    (unit::BATTLESHIP, (19, 4)),
    (unit::CARRIER, (27, 9)),
    (unit::SUB, (31, 2)),
    (unit::BLACK_BOAT, (31, 7)),
];

fn sensei_chest(core: &mut Core) {
    war_chest(core, 3, 15000, 1000);
}
fn hawke_chest(core: &mut Core) {
    war_chest(core, 4, 20000, 1500);
}

/// Cinder Sea: the player (Orange Star, a free CO) against Drake (Green Earth), then Sensei (Yellow Comet), then Hawke (Black Hole) on his volcano island.
fn cinder_sea() -> MissionDef {
    let mut m = MissionDef::new("gauntlet_01", "Cinder Sea");
    m.objective = "Sink Drake's line, then Sensei's, then take Hawke's HQ on the volcano island.";
    m.map = MapSrc::Built("gauntlet_01");
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pick).funds(12000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::DRAKE)).team(2).funds(8000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::SENSEI)).team(2).funds(0),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::HAWKE)).team(2).funds(0),
    ];
    m.units = crate::es_campaign::deployment("gauntlet_01");
    m.rank_days = 24;
    // (the player's army has no team of its own written here: team 0 is its own army number, 1; the three enemies share team 2: with team 1 they were the player's allies)
    // the gauntlet: Drake's and Sensei's HQs are held (taking one routes that line at once: the engine's rout rule, custom_campaign::rout_army); Hawke's is the last
    m.held_hq = Some(CINDER_DRAKE);
    m.held_more = vec![CINDER_SENSEI, CINDER_HAWKE]; // (Hawke's too: his army must still stand while he says his last line, else AW2 draws face 0, Nell's; the Win trigger ends the battle)
    m.sleepers = vec![(3, vec![CINDER_DRAKE]), (4, vec![CINDER_DRAKE, CINDER_SENSEI])];
    m.cut_off = vec![(2, CINDER_DRAKE), (3, CINDER_SENSEI)];
    m.hidden = vec![
        Hidden { army: 3, hq: CINDER_SENSEI, zone: Rect::new(0, 0, 12, 9) },
        Hidden { army: 4, hq: CINDER_HAWKE, zone: Rect::new(18, 0, 31, 9) },
    ];
    m.triggers = vec![
        arrive(CINDER_DRAKE, &[], 3, sensei_chest, &SENSEI_WAVE, sensei_arrives()),
        arrive(CINDER_SENSEI, &[CINDER_DRAKE], 4, hawke_chest, &HAWKE_WAVE, hawke_arrives()),
        // Hawke's line is the last: when it falls (his HQ taken or his army routed) the battle is won at once, whatever Drake's and Sensei's cut-off survivors still hold
        Trigger::new(When::AfterAction, Cond::All(vec![fell(CINDER_HAWKE), fell(CINDER_SENSEI), fell(CINDER_DRAKE)]), vec![Action::Win]),
    ];
    // (no Setup phase: the battle starts on day 1 with the map's deployment)
    m.setup = false;
    // Hawke's volcano: from day 3 it erupts every day on 3 cells of the ring round its mountain wall (3 HP, any army's units, never below 1)
    m.volcano = Some(crate::campaign_model::VolcanoDef::new(3, 1, 3, &crate::campaign_model::ring(21, 0, 28, 7)).per_eruption(3));
    m.intro = intro();
    m.victory = victory();
    m.stars = 3;
    m
}

fn intro() -> Scene {
    Scene::new(vec![
        Line::say(co::DRAKE, "Ahoy! Welcome to the Cinder Sea. These are my waters."),
        Line::say(co::DRAKE, "Want to cross them? You'll have to get past my fleet first."),
        Line::say(co::DRAKE, "And mind the smoke up north. That old volcano's been grumbling all week."),
    ])
}

fn sensei_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::DRAKE, Mood::Sad, "Blast! My flagship's gone under. Sensei, the sea's yours now."),
        Line::feel(co::SENSEI, Mood::Happy, "Hoho! Drake's beaten? Then it's an old man's turn."),
        Line::say(co::SENSEI, "My copters have been itching to fly. Let's see how you handle the sky!"),
    ])
}

fn hawke_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::SENSEI, Mood::Sad, "Well, well. Beaten by a youngster. I'm getting too old for this."),
        Line::say(co::HAWKE, "So you broke through Drake and Sensei. Impressive."),
        Line::say(co::HAWKE, "But this island is mine, and the mountain answers to me. You will burn here."),
    ])
}

fn victory() -> Scene {
    Scene::new(vec![Line::say(co::HAWKE, "Hmph. The sea and the sky were yours today. Enjoy it while it lasts.")])
}

// --- Gauntlet 02, Iron Crown and Asuka's Keep -------------------------------------------------------------------------------------------------------------

/// The HQs of stage one (five/gauntlet/spec/gauntlet_02.py): Grit's (on the field), Jess's, Kanbei's and Rachel's (hidden). The player is the fifth army (Black Hole's colour wearing the Silver Nova skin).
pub const IRON_GRIT: (u8, u8) = (8, 9);
pub const IRON_JESS: (u8, u8) = (24, 5);
pub const IRON_KANBEI: (u8, u8) = (34, 6);
pub const IRON_RACHEL: (u8, u8) = (30, 20);
/// Asuka's HQ on stage two (five/gauntlet/spec/gauntlet_02b.py).
pub const KEEP_ASUKA: (u8, u8) = (22, 5);
/// The most funds the player carries into Asuka's Keep, and what Asuka holds her fortress with.
const KEEP_CARRY_CAP: u32 = 40000;
const KEEP_ASUKA_FUNDS: u32 = 80000;

/// Jess's wave: the forests of the north (tanks, Md Tanks, APCs, artillery, foot soldiers).
const JESS_WAVE: [(u8, (u8, u8)); 14] = [
    (unit::TANK, (23, 6)),
    (unit::TANK, (24, 4)),
    (unit::TANK, (25, 4)),
    (unit::MD_TANK, (24, 7)),
    (unit::MD_TANK, (22, 7)),
    (unit::MD_TANK, (24, 8)),
    (unit::APC, (23, 5)),
    (unit::APC, (22, 8)),
    (unit::INFANTRY, (21, 6)),
    (unit::INFANTRY, (23, 7)),
    (unit::ARTILLERY, (24, 3)),
    (unit::ANTI_AIR, (26, 6)),
    (unit::RECON, (20, 8)),
    (unit::MECH, (21, 7)),
];

/// Kanbei's wave: the keep's plateau (infantry and mechs, a Mega Tank and a Md Tank, artillery and rockets at the south pass).
const KANBEI_WAVE: [(u8, (u8, u8)); 15] = [
    (unit::INFANTRY, (32, 3)),
    (unit::INFANTRY, (35, 3)),
    (unit::INFANTRY, (31, 4)),
    (unit::INFANTRY, (37, 4)),
    (unit::INFANTRY, (33, 5)),
    (unit::INFANTRY, (35, 5)),
    (unit::MECH, (33, 6)),
    (unit::MECH, (35, 6)),
    (unit::MECH, (32, 7)),
    (unit::MECH, (33, 8)),
    (unit::MEGATANK, (35, 8)),
    (unit::MD_TANK, (37, 8)),
    (unit::ANTI_AIR, (31, 8)),
    (unit::ARTILLERY, (34, 9)),
    (unit::ROCKETS, (32, 9)),
];

/// Rachel's wave: the lowlands (Recons and Tanks to flank, Md Tanks, copters, artillery).
const RACHEL_WAVE: [(u8, (u8, u8)); 16] = [
    (unit::RECON, (29, 18)),
    (unit::RECON, (33, 17)),
    (unit::TANK, (31, 20)),
    (unit::TANK, (29, 20)),
    (unit::TANK, (31, 21)),
    (unit::MD_TANK, (28, 19)),
    (unit::MD_TANK, (30, 19)),
    (unit::MD_TANK, (33, 20)),
    (unit::ARTILLERY, (31, 22)),
    (unit::ROCKETS, (29, 22)),
    (unit::B_COPTER, (31, 19)),
    (unit::B_COPTER, (33, 19)),
    (unit::INFANTRY, (27, 20)),
    (unit::INFANTRY, (32, 21)),
    (unit::MECH, (29, 21)),
    (unit::ANTI_AIR, (29, 17)),
];

fn jess_chest(core: &mut Core) {
    war_chest(core, 2, 20000, 1000);
}
fn kanbei_chest(core: &mut Core) {
    war_chest(core, 3, 20000, 1500);
}
fn rachel_chest(core: &mut Core) {
    war_chest(core, 4, 25000, 2000);
}

/// A scene on a day's start (the stage's day scenes).
fn on_day(d: u16, then: Vec<Action>) -> Trigger {
    Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: d }, then).repeating()
}

/// Iron Crown, stage one: the player (a free CO, the Silver Nova army, the fifth) against Grit (Blue Moon), Jess (Green Earth), Kanbei (Yellow Comet) and Rachel (Orange Star), one after another on one land map; Rachel's fall moves
/// the battle in place to Asuka's Keep (stage two). Every enemy colour is fixed in its army's data (a colour pick for the player offers the colour the enemies leave free: Black Hole's here, `player_colours`).
fn iron_crown() -> MissionDef {
    let mut m = MissionDef::new("gauntlet_02", "Iron Crown");
    m.objective = "Break Grit's river line, then Jess's, Kanbei's and Rachel's, and take Asuka's Keep.";
    m.map = MapSrc::Built("gauntlet_02");
    m.armies = vec![
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::GRIT)).team(1).funds(9000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JESS)).team(1).funds(0),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KANBEI)).team(1).funds(0),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::RACHEL)).team(1).funds(0),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(20000),
    ];
    m.units = crate::bh_ai::orders(crate::bh_ai::built_units("gauntlet_02"), 5, crate::bh_ai::ATTACK, |u| u.ai == 1);
    m.rank_days = 40;
    m.held_hq = Some(IRON_GRIT);
    m.held_more = vec![IRON_JESS, IRON_KANBEI, IRON_RACHEL];
    m.sleepers = vec![(2, vec![IRON_GRIT]), (3, vec![IRON_GRIT, IRON_JESS]), (4, vec![IRON_GRIT, IRON_JESS, IRON_KANBEI])];
    m.cut_off = vec![(1, IRON_GRIT), (2, IRON_JESS), (3, IRON_KANBEI)];
    m.hidden = vec![
        Hidden { army: 2, hq: IRON_JESS, zone: Rect::new(18, 0, 29, 12) },
        Hidden { army: 3, hq: IRON_KANBEI, zone: Rect::new(30, 0, 39, 13) },
        Hidden { army: 4, hq: IRON_RACHEL, zone: Rect::new(19, 14, 39, 25) },
    ];
    m.triggers = vec![
        arrive(IRON_GRIT, &[], 2, jess_chest, &JESS_WAVE, jess_arrives()),
        arrive(IRON_JESS, &[IRON_GRIT], 3, kanbei_chest, &KANBEI_WAVE, kanbei_arrives()),
        arrive(IRON_KANBEI, &[IRON_GRIT, IRON_JESS], 4, rachel_chest, &RACHEL_WAVE, rachel_arrives()),
        // Rachel's line is the last of stage one: a scene, then the battle moves on to Asuka's Keep
        Trigger::new(
            When::AfterAction,
            Cond::All(vec![fell(IRON_RACHEL), fell(IRON_KANBEI), fell(IRON_JESS), fell(IRON_GRIT)]),
            vec![Action::Scene(keep_switch()), Action::NextStage],
        ),
    ];
    m.setup = false;
    // Stage two: Asuka's Keep. The player's survivors land on the cells the map deploys the first army on; the player's skin moves to Orange Star's colour (Asuka is Black Hole's).
    let keep = crate::es_campaign::deployment("gauntlet_02b");
    let mut st = StageDef::new(MapSrc::Built("gauntlet_02b"));
    st.deploy = keep.iter().filter(|u| u.army == 1).map(|u| (u.x, u.y)).collect();
    st.units = keep.into_iter().filter(|u| u.army == 2).collect();
    st.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Keep),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(crate::co_new::ASUKA)).funds(KEEP_ASUKA_FUNDS),
    ];
    st.weather = Weather::Rain; // Asuka's rain: the fortress is fogged
    st.fog = true;
    st.carry = Carry::All;
    st.funds_cap = Some(KEEP_CARRY_CAP);
    st.held = vec![KEEP_ASUKA];
    st.intro = keep_intro();
    st.victory = keep_victory();
    st.triggers = vec![
        on_day(4, vec![Action::Scene(keep_day4())]),
        on_day(8, vec![Action::Scene(keep_day8())]),
        // her HQ is held (taking it defeats nobody) so her army stands while she says her last line with her own face; the Win ends the battle
        Trigger::new(When::AfterAction, fell(KEEP_ASUKA), vec![Action::Win]),
    ];
    m.stages = vec![st];
    m.intro = iron_intro();
    m.stars = 3;
    m
}

fn iron_intro() -> Scene {
    Scene::new(vec![
        Line::say(co::GRIT, "Hey! Welcome to the Iron Crown. This river and these hills are mine."),
        Line::say(co::GRIT, "If you want to cross the Aube, you'll have to get past my artillery first!"),
        Line::say(co::GRIT, "And I'm not the only one waiting out here. Don't get comfortable!"),
    ])
}

fn jess_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::GRIT, Mood::Sad, "Dang! They crossed my river and I couldn't stop them. Jess, you're up!"),
        Line::feel(co::JESS, Mood::Happy, "You got it, Grit! The forest is on my side, so watch your step!"),
        Line::say(co::JESS, "I'm going to show you how Green Earth fights. Ready or not!"),
    ])
}

fn kanbei_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::JESS, Mood::Sad, "Oh no! The forest wasn't enough? Kanbei, please take over!"),
        Line::say(co::KANBEI, "I understand. You have fought well to reach my mountains."),
        Line::say(co::KANBEI, "But courage alone does not take a keep. Come, let us see you climb."),
    ])
}

fn rachel_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::KANBEI, Mood::Sad, "The keep has fallen. Rachel, the lowlands are yours to hold."),
        Line::feel(co::RACHEL, Mood::Happy, "You came all this way? Nice! Let's see if you can handle Orange Star's best!"),
        Line::say(co::RACHEL, "I'm Rachel, and I won't let you take another step!"),
    ])
}

fn keep_switch() -> Scene {
    Scene::new(vec![
        Line::feel(co::RACHEL, Mood::Sad, "No way! My whole line is gone? That wasn't supposed to happen!"),
        Line::say(crate::co_new::ASUKA, "Rachel, retire. The file on this army is almost complete."),
        Line::say(crate::co_new::ASUKA, "Come to my keep. I have prepared for you."),
    ])
}

fn keep_intro() -> Scene {
    Scene::new(vec![
        Line::say(crate::co_new::ASUKA, "I have read your every move. Observe."),
        Line::say(crate::co_new::ASUKA, "Every gate and every gun of this keep stands where you will step."),
        Line::say(crate::co_new::ASUKA, "The rain will blind you. It will not blind me. Begin."),
    ])
}

fn keep_day4() -> Scene {
    Scene::new(vec![Line::say(crate::co_new::ASUKA, "Day four. You crossed the river, as predicted. The next page is the wall.")])
}

fn keep_day8() -> Scene {
    Scene::new(vec![Line::say(crate::co_new::ASUKA, "Your army grows thin and my file does not. Surrender is also in the record.")])
}

fn keep_victory() -> Scene {
    Scene::new(vec![
        Line::say(crate::co_new::ASUKA, "Impossible. I did not record this ending."),
        Line::say(crate::co_new::ASUKA, "No. Not impossible, only unrecorded. Well played. I will update the file."),
    ])
}

// --- The maps added after the first two (Dustwind Basin, Brass Canal, ...): the shared wiring ---------------------------------------------------------------

/// A war chest paid when `army` arrives: `BASE` and `RATE` for each day before today (`war_chest`), as a function pointer the arrival trigger can hold.
fn chest<const ARMY: u8, const BASE: u32, const RATE: u32>(core: &mut Core) {
    war_chest(core, ARMY, BASE, RATE);
}

/// One line of a gauntlet: its army (1-based slot), its HQ and the zone its properties are taken from on arrival.
#[derive(Clone, Copy)]
struct Wire {
    army: u8,
    hq: (u8, u8),
    zone: Rect,
}

/// Wires a gauntlet's lines into `m` (the engine's data, docs/dev/gauntlet.md "A new gauntlet map"): the first line is on the field with its HQ held, every later line is hidden and
/// sleeps until the lines before it have fallen, every line but the last is routed when its HQ is taken (`cut_off`), the last line's HQ wins. `arrivals` are the later lines'
/// `arrive` triggers (their scene, wave and war chest, in order). The armies of two lines may be the same colour (a whole army's COs one after another): only the slots differ.
fn wire(m: &mut MissionDef, lines: &[Wire], arrivals: Vec<Trigger>) {
    m.held_hq = Some(lines[0].hq);
    m.held_more = lines[1..].iter().map(|l| l.hq).collect();
    m.sleepers = (1..lines.len()).map(|i| (lines[i].army, lines[..i].iter().map(|l| l.hq).collect())).collect();
    m.cut_off = lines[..lines.len() - 1].iter().map(|l| (l.army, l.hq)).collect();
    m.hidden = lines[1..].iter().map(|l| Hidden { army: l.army, hq: l.hq, zone: l.zone }).collect();
    m.triggers = arrivals;
    m.triggers.push(Trigger::new(When::AfterAction, Cond::All(lines.iter().map(|l| fell(l.hq)).collect()), vec![Action::Win]));
    m.setup = false;
    m.stars = 3;
}

/// The arrival trigger of line `k` (1..) of `lines`: it comes when every line before it has fallen.
fn arrival(lines: &[Wire], k: usize, chest: fn(&mut Core), wave: &[(u8, (u8, u8))], scene: Scene) -> Trigger {
    let before: Vec<(u8, u8)> = lines[..k].iter().map(|l| l.hq).collect();
    arrive(before[k - 1], &before[..k - 1], lines[k].army, chest, wave, scene)
}

// --- Gauntlet 03, Dustwind Basin ----------------------------------------------------------------------------------------------------------------------------

/// The HQs (five/gauntlet/spec/gauntlet_03.py): the player's, Koal's (on the field), Lash's (hidden).
pub const DUST_PLAYER: (u8, u8) = (3, 16);
pub const DUST_KOAL: (u8, u8) = (25, 10);
pub const DUST_LASH: (u8, u8) = (6, 3);

/// Lash's wave: the badlands' ground troops, artillery and Md Tanks, a recon and two copters.
const LASH_WAVE: [(u8, (u8, u8)); 18] = [
    (unit::INFANTRY, (4, 3)),
    (unit::INFANTRY, (10, 6)),
    (unit::INFANTRY, (6, 5)),
    (unit::INFANTRY, (11, 8)),
    (unit::MECH, (7, 4)),
    (unit::MECH, (8, 1)),
    (unit::MECH, (10, 9)),
    (unit::ARTILLERY, (7, 6)),
    (unit::ARTILLERY, (12, 9)),
    (unit::ARTILLERY, (12, 4)),
    (unit::MD_TANK, (6, 8)),
    (unit::MD_TANK, (8, 4)),
    (unit::MD_TANK, (11, 5)),
    (unit::ROCKETS, (6, 2)),
    (unit::ANTI_AIR, (12, 7)),
    (unit::RECON, (9, 5)),
    (unit::B_COPTER, (8, 6)),
    (unit::B_COPTER, (1, 4)),
];


/// Dustwind Basin: the player (a free CO) against Koal (Yellow Comet) on his mesa, then Lash (Black Hole) out of the north-west badlands. Two lines, three armies.
fn dustwind_basin() -> MissionDef {
    let mut m = MissionDef::new("gauntlet_03", "Dustwind Basin");
    m.objective = "Take Koal's mesa, then Lash's badlands.";
    m.map = MapSrc::Built("gauntlet_03");
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pick).funds(12000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::KOAL)).team(2).funds(8000),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::LASH)).team(2).funds(0),
    ];
    m.units = crate::es_campaign::deployment("gauntlet_03");
    m.rank_days = 22;
    let lines = [Wire { army: 2, hq: DUST_KOAL, zone: Rect::new(20, 3, 29, 17) }, Wire { army: 3, hq: DUST_LASH, zone: Rect::new(0, 0, 12, 9) }];
    wire(&mut m, &lines, vec![arrival(&lines, 1, chest::<3, 15000, 1000>, &LASH_WAVE, lash_arrives())]);
    m.intro = Scene::new(vec![
        Line::say(co::KOAL, "Welcome to Dustwind Basin! The roads up here are the best money can buy."),
        Line::say(co::KOAL, "My tanks are fast, my mesa is high and my patience is short. Let's go!"),
    ]);
    m.victory = Scene::new(vec![Line::say(co::LASH, "Hmph. You read the ground better than I did. Don't count on it twice.")]);
    m
}

fn lash_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::KOAL, Mood::Sad, "Aw, shucks! My mesa's lost. Lash, it's all yours."),
        Line::say(co::LASH, "Dunes, gullies, broken rock. Fine ground for my kind of fight."),
        Line::say(co::LASH, "You have to cross it first. Let me show you how it feels."),
    ])
}

// --- Gauntlet 04, Brass Canal -----------------------------------------------------------------------------------------------------------------------------

/// The HQs (five/gauntlet/spec/gauntlet_04.py): the player's, Sasha's (on the field), Javier's (hidden).
pub const CANAL_PLAYER: (u8, u8) = (3, 18);
pub const CANAL_SASHA: (u8, u8) = (5, 4);
pub const CANAL_JAVIER: (u8, u8) = (25, 17);

/// Javier's wave: Md Tanks and Tanks round his Com Towers, artillery behind the south canal, foot soldiers and a copter.
const JAVIER_WAVE: [(u8, (u8, u8)); 20] = [
    (unit::TANK, (24, 17)),
    (unit::TANK, (22, 18)),
    (unit::TANK, (26, 15)),
    (unit::TANK, (29, 16)),
    (unit::MD_TANK, (26, 17)),
    (unit::MD_TANK, (25, 13)),
    (unit::MD_TANK, (20, 14)),
    (unit::ARTILLERY, (21, 13)),
    (unit::ARTILLERY, (26, 13)),
    (unit::ARTILLERY, (23, 14)),
    (unit::ROCKETS, (22, 14)),
    (unit::INFANTRY, (19, 18)),
    (unit::INFANTRY, (28, 20)),
    (unit::INFANTRY, (19, 15)),
    (unit::INFANTRY, (28, 21)),
    (unit::MECH, (20, 16)),
    (unit::MECH, (27, 19)),
    (unit::ANTI_AIR, (21, 18)),
    (unit::RECON, (28, 17)),
    (unit::B_COPTER, (18, 14)),
];

/// Brass Canal: the player (a free CO) against Sasha (Blue Moon) in the Brass Works, then Javier (Green Earth) in the south-east quarter. Two lines, three armies.
fn brass_canal() -> MissionDef {
    let mut m = MissionDef::new("gauntlet_04", "Brass Canal");
    m.objective = "Take the Brass Works from Sasha, then Javier's south-east quarter.";
    m.map = MapSrc::Built("gauntlet_04");
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pick).funds(12000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::SASHA)).team(2).funds(10000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::JAVIER)).team(2).funds(0),
    ];
    m.units = crate::es_campaign::deployment("gauntlet_04");
    m.rank_days = 22;
    let lines = [Wire { army: 2, hq: CANAL_SASHA, zone: Rect::new(0, 0, 13, 9) }, Wire { army: 3, hq: CANAL_JAVIER, zone: Rect::new(17, 12, 29, 21) }];
    wire(&mut m, &lines, vec![arrival(&lines, 1, chest::<3, 15000, 1000>, &JAVIER_WAVE, javier_arrives())]);
    m.intro = Scene::new(vec![
        Line::say(co::SASHA, "Welcome to Brass Canal. Every bridge here has a price, and I own the toll."),
        Line::say(co::SASHA, "A good commander wins with funds and timing. Let me show you both."),
    ]);
    m.victory = Scene::new(vec![Line::say(co::JAVIER, "The canals are yours. A fine campaign. Do tell the Com Towers I said so.")]);
    m
}

fn javier_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::SASHA, Mood::Sad, "Well! That was an expensive loss. Javier, the south is yours."),
        Line::say(co::JAVIER, "Thank you, Sasha. The Com Towers are humming, and my troops stand tall."),
        Line::say(co::JAVIER, "Come, friend. Let us see how you fare against the whole south bank."),
    ])
}

// --- Gauntlet 05, Granite Spine ---------------------------------------------------------------------------------------------------------------------------

/// The HQs (five/gauntlet/spec/gauntlet_05.py): the player's, Jake's (on the field), Grimm's and Von Bolt's (hidden).
pub const SPINE_PLAYER: (u8, u8) = (3, 18);
pub const SPINE_JAKE: (u8, u8) = (28, 12);
pub const SPINE_GRIMM: (u8, u8) = (6, 4);
pub const SPINE_VON_BOLT: (u8, u8) = (27, 4);

/// Grimm's wave: heavy armour and artillery on the north-west shelf, copters over the spine.
const GRIMM_WAVE: [(u8, (u8, u8)); 17] = [
    (unit::MD_TANK, (9, 5)),
    (unit::MD_TANK, (10, 3)),
    (unit::MD_TANK, (5, 9)),
    (unit::MEGATANK, (12, 5)),
    (unit::ARTILLERY, (12, 7)),
    (unit::ARTILLERY, (5, 8)),
    (unit::ARTILLERY, (6, 5)),
    (unit::ROCKETS, (1, 1)),
    (unit::INFANTRY, (12, 9)),
    (unit::INFANTRY, (1, 4)),
    (unit::INFANTRY, (2, 8)),
    (unit::MECH, (7, 8)),
    (unit::MECH, (10, 5)),
    (unit::ANTI_AIR, (8, 5)),
    (unit::B_COPTER, (7, 1)),
    (unit::B_COPTER, (11, 3)),
    (unit::T_COPTER, (4, 3)),
];

/// Von Bolt's wave: the north-east valley's armour, a Neo Tank, missiles, a Bomber and a Fighter.
const VON_BOLT_WAVE: [(u8, (u8, u8)); 17] = [
    (unit::MD_TANK, (29, 3)),
    (unit::MD_TANK, (24, 1)),
    (unit::MD_TANK, (27, 4)),
    (unit::TANK, (19, 4)),
    (unit::TANK, (23, 4)),
    (unit::NEOTANK, (24, 4)),
    (unit::ARTILLERY, (29, 1)),
    (unit::ARTILLERY, (19, 0)),
    (unit::MISSILES, (30, 7)),
    (unit::INFANTRY, (21, 2)),
    (unit::INFANTRY, (26, 6)),
    (unit::INFANTRY, (20, 7)),
    (unit::MECH, (21, 3)),
    (unit::MECH, (20, 3)),
    (unit::FIGHTER, (23, 0)),
    (unit::BOMBER, (24, 2)),
    (unit::ANTI_AIR, (19, 1)),
];

/// Granite Spine: the player (a free CO) against Jake (Orange Star) on the east slopes, then Grimm (Yellow Comet) on the north-west shelf, then Von Bolt (Black Hole) in the north-east valley.
fn granite_spine() -> MissionDef {
    let mut m = MissionDef::new("gauntlet_05", "Granite Spine");
    m.objective = "Cross the spine and take Jake's slopes, Grimm's shelf and Von Bolt's valley.";
    m.map = MapSrc::Built("gauntlet_05");
    m.armies = vec![
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Pick).funds(12000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::JAKE)).team(2).funds(8000),
        ArmyDef::new(colour::YELLOW_COMET, CoSpec::Fixed(co::GRIMM)).team(2).funds(0),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::VON_BOLT)).team(2).funds(0),
    ];
    m.units = crate::es_campaign::deployment("gauntlet_05");
    m.rank_days = 26;
    let lines = [
        Wire { army: 2, hq: SPINE_JAKE, zone: Rect::new(19, 8, 31, 21) },
        Wire { army: 3, hq: SPINE_GRIMM, zone: Rect::new(0, 0, 12, 10) },
        Wire { army: 4, hq: SPINE_VON_BOLT, zone: Rect::new(19, 0, 31, 7) },
    ];
    wire(
        &mut m,
        &lines,
        vec![
            arrival(&lines, 1, chest::<3, 15000, 1000>, &GRIMM_WAVE, grimm_arrives()),
            arrival(&lines, 2, chest::<4, 20000, 1500>, &VON_BOLT_WAVE, von_bolt_arrives()),
        ],
    );
    m.intro = Scene::new(vec![
        Line::say(co::JAKE, "Hey, welcome to the Granite Spine! Rough country, and I love it."),
        Line::say(co::JAKE, "Offroad is my kind of road. Try to keep up!"),
    ]);
    m.victory = Scene::new(vec![Line::say(co::VON_BOLT, "The spine is broken. The machine will remember this, and so will I.")]);
    m
}

fn grimm_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::JAKE, Mood::Sad, "Whoa, they got over the ridge! Grimm, you're up!"),
        Line::say(co::GRIMM, "Do not worry, kid. I have the high ground, and a very large gun."),
        Line::say(co::GRIMM, "Come up and say hello. I do not mind the wait."),
    ])
}

fn von_bolt_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::GRIMM, Mood::Sad, "Hmph. They climbed the shelf. Von Bolt, it is your valley now."),
        Line::say(co::VON_BOLT, "A pity. I had hoped for a longer test of the machine."),
        Line::say(co::VON_BOLT, "No matter. The valley will end the experiment."),
    ])
}

// --- Gauntlet 06, Harvest Run: all of Orange Star -----------------------------------------------------------------------------------------------------------

/// The HQs (five/gauntlet/spec/gauntlet_06.py): Andy's (on the field), Max's, Sami's and Nell's (hidden), the player's (the fifth army).
pub const HARVEST_ANDY: (u8, u8) = (11, 8);
pub const HARVEST_MAX: (u8, u8) = (29, 5);
pub const HARVEST_SAMI: (u8, u8) = (30, 19);
pub const HARVEST_NELL: (u8, u8) = (6, 4);
pub const HARVEST_PLAYER: (u8, u8) = (4, 20);

/// Max's wave: heavy direct-fire tanks and recons on the high road, foot soldiers behind them.
const MAX_WAVE: [(u8, (u8, u8)); 20] = [
    (unit::MD_TANK, (25, 5)),
    (unit::MD_TANK, (27, 9)),
    (unit::MD_TANK, (33, 3)),
    (unit::MD_TANK, (24, 2)),
    (unit::TANK, (29, 2)),
    (unit::TANK, (27, 5)),
    (unit::TANK, (26, 5)),
    (unit::RECON, (27, 1)),
    (unit::RECON, (23, 1)),
    (unit::MEGATANK, (28, 8)),
    (unit::INFANTRY, (26, 8)),
    (unit::INFANTRY, (31, 4)),
    (unit::INFANTRY, (33, 7)),
    (unit::MECH, (28, 2)),
    (unit::MECH, (22, 1)),
    (unit::MECH, (25, 7)),
    (unit::ARTILLERY, (33, 4)),
    (unit::ARTILLERY, (31, 7)),
    (unit::ANTI_AIR, (23, 6)),
    (unit::B_COPTER, (32, 7)),
];

/// Sami's wave: foot soldiers and carriers, a few tanks behind them.
const SAMI_WAVE: [(u8, (u8, u8)); 22] = [
    (unit::INFANTRY, (23, 17)),
    (unit::INFANTRY, (30, 22)),
    (unit::INFANTRY, (32, 15)),
    (unit::INFANTRY, (35, 14)),
    (unit::INFANTRY, (24, 15)),
    (unit::INFANTRY, (32, 17)),
    (unit::MECH, (29, 17)),
    (unit::MECH, (30, 14)),
    (unit::MECH, (28, 14)),
    (unit::APC, (25, 22)),
    (unit::APC, (22, 21)),
    (unit::TANK, (29, 18)),
    (unit::TANK, (25, 20)),
    (unit::TANK, (28, 16)),
    (unit::MD_TANK, (26, 14)),
    (unit::MD_TANK, (34, 19)),
    (unit::ROCKETS, (28, 19)),
    (unit::ARTILLERY, (26, 21)),
    (unit::ARTILLERY, (35, 19)),
    (unit::ANTI_AIR, (26, 20)),
    (unit::T_COPTER, (25, 21)),
    (unit::B_COPTER, (30, 15)),
];

/// Nell's wave: a balanced line from the north-west meadows, with a Fighter and a Bomber.
const NELL_WAVE: [(u8, (u8, u8)); 20] = [
    (unit::INFANTRY, (14, 2)),
    (unit::INFANTRY, (13, 6)),
    (unit::INFANTRY, (14, 1)),
    (unit::INFANTRY, (8, 1)),
    (unit::MECH, (11, 1)),
    (unit::MECH, (4, 3)),
    (unit::MECH, (2, 3)),
    (unit::TANK, (3, 1)),
    (unit::TANK, (1, 1)),
    (unit::TANK, (7, 6)),
    (unit::MD_TANK, (1, 5)),
    (unit::MD_TANK, (5, 2)),
    (unit::MD_TANK, (8, 3)),
    (unit::ARTILLERY, (7, 1)),
    (unit::ARTILLERY, (2, 1)),
    (unit::ROCKETS, (1, 3)),
    (unit::RECON, (8, 2)),
    (unit::ANTI_AIR, (8, 5)),
    (unit::FIGHTER, (10, 4)),
    (unit::BOMBER, (7, 4)),
];

/// Harvest Run: the whole of Orange Star, one CO after another (Andy, Max, Sami, Nell), every line in Orange Star's colour and with Orange Star's HQ: only the army slots differ (1..4).
fn harvest_run() -> MissionDef {
    let mut m = MissionDef::new("gauntlet_06", "Harvest Run");
    m.objective = "Beat all of Orange Star: Andy, then Max, Sami and Nell.";
    m.map = MapSrc::Built("gauntlet_06");
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::ANDY)).team(1).funds(9000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::MAX)).team(1).funds(0),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::SAMI)).team(1).funds(0),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::NELL)).team(1).funds(0),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(20000),
    ];
    m.units = crate::bh_ai::orders(crate::bh_ai::built_units("gauntlet_06"), 5, crate::bh_ai::ATTACK, |u| u.ai == 1);
    m.rank_days = 40;
    let lines = [
        Wire { army: 1, hq: HARVEST_ANDY, zone: Rect::new(0, 0, 16, 12) },
        Wire { army: 2, hq: HARVEST_MAX, zone: Rect::new(20, 0, 35, 9) },
        Wire { army: 3, hq: HARVEST_SAMI, zone: Rect::new(21, 13, 35, 23) },
        Wire { army: 4, hq: HARVEST_NELL, zone: Rect::new(0, 0, 16, 6) },
    ];
    wire(
        &mut m,
        &lines,
        vec![
            arrival(&lines, 1, chest::<2, 15000, 1000>, &MAX_WAVE, max_arrives()),
            arrival(&lines, 2, chest::<3, 20000, 1500>, &SAMI_WAVE, sami_arrives()),
            arrival(&lines, 3, chest::<4, 25000, 2000>, &NELL_WAVE, nell_arrives()),
        ],
    );
    m.intro = Scene::new(vec![
        Line::say(co::ANDY, "Hey there! Welcome to Harvest Run. All of Orange Star's out here today."),
        Line::say(co::ANDY, "I'll start things off. Don't worry, I'll fix my tanks if you break them!"),
    ]);
    m.victory = Scene::new(vec![Line::say(co::NELL, "Oh my! Orange Star beaten, all of us at once? Well done.")]);
    m
}

fn max_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::ANDY, Mood::Sad, "Aw, shucks! Max, I could use some muscle here!"),
        Line::say(co::MAX, "Leave it to me, Andy! Nothing beats a good tank rush!"),
    ])
}

fn sami_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::MAX, Mood::Sad, "Argh! My tanks got stuck in the mud! Sami, you take it!"),
        Line::say(co::SAMI, "Infantry, move out! We'll take this field one soldier at a time."),
    ])
}

fn nell_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::SAMI, Mood::Sad, "Roger that. They broke through. Nell, we're counting on you!"),
        Line::say(co::NELL, "Oh, I'm so nervous! But luck is on my side, so let's give it a try!"),
    ])
}

// --- Gauntlet 07, Chrome Meridian: Flak, then the Silver Nova corps -----------------------------------------------------------------------------------------

/// The HQs (five/gauntlet/spec/gauntlet_07.py): Flak's (on the field), Caulder's, Lili's and Tabitha's (hidden), the player's.
pub const CHROME_FLAK: (u8, u8) = (11, 14);
pub const CHROME_CAULDER: (u8, u8) = (7, 5);
pub const CHROME_LILI: (u8, u8) = (31, 5);
pub const CHROME_TABITHA: (u8, u8) = (32, 20);
pub const CHROME_PLAYER: (u8, u8) = (4, 22);

/// Caulder's wave: the corps' siege engines behind the citadel's ring (artillery, rockets, missiles), armour and foot soldiers in front of them.
const CAULDER_WAVE: [(u8, (u8, u8)); 19] = [
    (unit::ARTILLERY, (8, 8)),
    (unit::ARTILLERY, (3, 5)),
    (unit::ARTILLERY, (14, 6)),
    (unit::ARTILLERY, (3, 6)),
    (unit::ROCKETS, (17, 3)),
    (unit::ROCKETS, (17, 8)),
    (unit::MISSILES, (14, 1)),
    (unit::MD_TANK, (4, 5)),
    (unit::MD_TANK, (9, 5)),
    (unit::MD_TANK, (11, 5)),
    (unit::TANK, (4, 2)),
    (unit::TANK, (14, 2)),
    (unit::INFANTRY, (12, 8)),
    (unit::INFANTRY, (4, 7)),
    (unit::INFANTRY, (14, 3)),
    (unit::MECH, (8, 7)),
    (unit::MECH, (10, 6)),
    (unit::ANTI_AIR, (6, 5)),
    (unit::APC, (9, 8)),
];

/// Lili's wave: fast armour (recons, tanks) and copters over the Meridian.
const LILI_WAVE: [(u8, (u8, u8)); 20] = [
    (unit::RECON, (34, 8)),
    (unit::RECON, (33, 4)),
    (unit::RECON, (30, 6)),
    (unit::TANK, (23, 6)),
    (unit::TANK, (22, 3)),
    (unit::TANK, (33, 10)),
    (unit::TANK, (22, 1)),
    (unit::MD_TANK, (32, 4)),
    (unit::MD_TANK, (26, 5)),
    (unit::MD_TANK, (28, 5)),
    (unit::B_COPTER, (22, 2)),
    (unit::B_COPTER, (31, 2)),
    (unit::B_COPTER, (32, 10)),
    (unit::FIGHTER, (24, 9)),
    (unit::INFANTRY, (26, 4)),
    (unit::INFANTRY, (29, 9)),
    (unit::INFANTRY, (30, 8)),
    (unit::MECH, (33, 5)),
    (unit::MECH, (36, 9)),
    (unit::ANTI_AIR, (25, 5)),
];

/// Tabitha's wave: the corps' heavy armour, a Mega Tank and Neo Tanks, bombers and fighters.
const TABITHA_WAVE: [(u8, (u8, u8)); 20] = [
    (unit::MEGATANK, (29, 22)),
    (unit::NEOTANK, (35, 17)),
    (unit::NEOTANK, (30, 20)),
    (unit::MD_TANK, (27, 20)),
    (unit::MD_TANK, (28, 17)),
    (unit::MD_TANK, (36, 24)),
    (unit::TANK, (22, 15)),
    (unit::TANK, (22, 18)),
    (unit::ARTILLERY, (34, 18)),
    (unit::ARTILLERY, (34, 19)),
    (unit::INFANTRY, (28, 15)),
    (unit::INFANTRY, (26, 16)),
    (unit::INFANTRY, (32, 24)),
    (unit::MECH, (34, 22)),
    (unit::MECH, (27, 19)),
    (unit::BOMBER, (28, 22)),
    (unit::FIGHTER, (23, 21)),
    (unit::ANTI_AIR, (31, 18)),
    (unit::ANTI_AIR, (22, 23)),
    (unit::B_COPTER, (23, 20)),
];

/// The skin's army slot on Chrome Meridian (Caulder's: the three Silver Nova lines are the armies 2, 3 and 4 and share Yellow Comet's colour, which wears the skin).
pub const CHROME_SKIN_ARMY: u8 = 2;
/// The colour the Silver Nova skin sits on for the corps' three armies.
pub const CHROME_HOST: u8 = colour::YELLOW_COMET;

/// Chrome Meridian: Flak (Black Hole), then the Silver Nova corps in turn: Caulder, Lili and Tabitha, whose three armies share one colour (the skin sits on it, so every one of them wears
/// Silver Nova's chrome, its orb-tower HQ and its figures). Black Hole stays Black Hole: the skin is on armies 2..4 only.
fn chrome_meridian() -> MissionDef {
    let mut m = MissionDef::new("gauntlet_07", "Chrome Meridian");
    m.objective = "Break Flak's depot, then the Silver Nova corps: Caulder, Lili and Tabitha.";
    m.map = MapSrc::Built("gauntlet_07");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::FLAK)).team(1).funds(9000),
        ArmyDef::new(CHROME_HOST, CoSpec::Fixed(crate::es_co::CAULDER)).team(1).funds(0),
        ArmyDef::new(CHROME_HOST, CoSpec::Fixed(crate::es_co::LILI)).team(1).funds(0),
        ArmyDef::new(CHROME_HOST, CoSpec::Fixed(crate::es_co::TABITHA)).team(1).funds(0),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(20000),
    ];
    m.skin = Some((CHROME_SKIN_ARMY, 0));
    m.units = crate::bh_ai::orders(crate::bh_ai::built_units("gauntlet_07"), 5, crate::bh_ai::ATTACK, |u| u.ai == 1);
    m.rank_days = 40;
    let lines = [
        Wire { army: 1, hq: CHROME_FLAK, zone: Rect::new(2, 9, 18, 18) },
        Wire { army: 2, hq: CHROME_CAULDER, zone: Rect::new(0, 0, 18, 9) },
        Wire { army: 3, hq: CHROME_LILI, zone: Rect::new(21, 0, 37, 11) },
        Wire { army: 4, hq: CHROME_TABITHA, zone: Rect::new(21, 14, 37, 25) },
    ];
    wire(
        &mut m,
        &lines,
        vec![
            arrival(&lines, 1, chest::<2, 15000, 1000>, &CAULDER_WAVE, caulder_arrives()),
            arrival(&lines, 2, chest::<3, 20000, 1500>, &LILI_WAVE, lili_arrives()),
            arrival(&lines, 3, chest::<4, 25000, 2000>, &TABITHA_WAVE, tabitha_arrives()),
        ],
    );
    m.intro = Scene::new(vec![
        Line::say(co::FLAK, "Hah! Welcome to the Meridian! Cheap tanks, loud guns, and no plan!"),
        Line::say(co::FLAK, "I am the plan. Come on, let's make some noise!"),
    ]);
    m.victory = Scene::new(vec![Line::say(crate::es_co::TABITHA, "The Meridian is yours. The corps will remember the one who broke it.")]);
    m
}

fn caulder_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::FLAK, Mood::Sad, "What?! Nobody told me I'd lose! Somebody else take over!"),
        Line::say(crate::es_co::CAULDER, "A shame. The depot was not built to hold. The citadel is."),
        Line::say(crate::es_co::CAULDER, "Every gate, every tower, measured. Do come in."),
    ])
}

fn lili_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(crate::es_co::CAULDER, Mood::Sad, "The citadel has fallen. It was measured, but not by you."),
        Line::say(crate::es_co::LILI, "Caulder always did take too long. The plains are mine now."),
        Line::say(crate::es_co::LILI, "Fast, light and everywhere at once. Let us see you keep up."),
    ])
}

fn tabitha_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(crate::es_co::LILI, Mood::Sad, "They crossed the Meridian faster than I thought. Tabitha, the rest is yours."),
        Line::say(crate::es_co::TABITHA, "Thank you, Lili. The corps ends here, then."),
        Line::say(crate::es_co::TABITHA, "Come to the south-east. I will show you what silver is made of."),
    ])
}

// --- What the map selector shows (crate::gauntlet_ui) ---------------------------------------------------------------------------------------------------

/// One of the Gauntlet's maps as the selector lists it: read from the map's mission, so a new map is listed by adding its mission to [`def`] (nothing else).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Entry {
    /// The mission's index in [`def`] (the record's index too).
    pub mission: usize,
    pub key: &'static str,
    pub title: &'static str,
    /// The enemy COs in the order they come, with the army colour the map gives each (fixed in the map's data: the player never takes it): the first stage's, then each later stage's.
    pub enemies: Vec<(u8, u8)>,
    /// The enemies' colours stage by stage (the player's army must have a colour free in every stage; a skin's host moves between stages).
    pub stages: Vec<Vec<u8>>,
    /// An enemy line wears a skin (Silver Nova's Caulder, Lili and Tabitha): the skin is on the battlefield already, so the player cannot wear it too (a skin sits on one colour).
    pub enemy_skin: bool,
}

impl Entry {
    /// What the player may wear on this map: every army colour the enemies of no stage wear, and the skins when every stage leaves a colour to host them ([`free_colours_staged`]).
    pub fn free(&self) -> Vec<u8> {
        let mut v = free_colours_staged(&self.stages);
        if self.enemy_skin {
            v.retain(|c| *c < crate::army_skin::SKIN);
        }
        v
    }

    /// The enemy colours of the stage the battle is on (0: the mission's own map).
    pub fn stage_enemies(&self, stage: usize) -> &[u8] {
        self.stages.get(stage).map_or(&[], |v| v.as_slice())
    }
}

/// The army choices a player has against enemies who wear `enemy` (AW2's colours 1..5): the five colours in the Teams screen's order (Orange Star, Blue Moon, Yellow Comet,
/// Green Earth, Black Hole) without the enemies', then the skins (Silver Nova, code `army_skin::SKIN + i`) while one of the five is free to put it on
/// (`army_skin::assign`: a skin sits on the lowest colour nobody has). Never an enemy's colour.
pub fn free_colours(enemy: &[u8]) -> Vec<u8> {
    free_colours_staged(&[enemy.to_vec()])
}

/// [`free_colours`] for a map of several stages (a stage switch changes the enemies): a plain colour must be free in every stage (nobody wears it, ever); a skin needs a free colour to sit on
/// in each stage (it moves at the switch: Iron Crown's Silver Nova is on Black Hole's colour in stage one and on Orange Star's against Asuka).
pub fn free_colours_staged(stages: &[Vec<u8>]) -> Vec<u8> {
    let all: Vec<u8> = stages.iter().flatten().copied().collect();
    let mut v: Vec<u8> = crate::army_skin::order().into_iter().filter(|c| *c < crate::army_skin::SKIN && !all.contains(c)).collect();
    let hosted = stages.iter().all(|enemy| (1..=5u8).any(|c| !enemy.contains(&c)));
    if hosted {
        v.extend((0..crate::army_skin::skins().len() as u8).map(|i| crate::army_skin::SKIN + i));
    }
    v
}

/// The maps the selector lists, in [`def`]'s order.
pub fn entries() -> &'static [Entry] {
    static E: std::sync::OnceLock<Vec<Entry>> = std::sync::OnceLock::new();
    E.get_or_init(|| {
        let fixed = |armies: &[ArmyDef]| -> Vec<(u8, u8)> { armies.iter().filter_map(|a| if let CoSpec::Fixed(c) = a.co { Some((c, a.colour)) } else { None }).collect() };
        def()
            .missions
            .iter()
            .enumerate()
            .map(|(mission, m)| {
                let mut stages = vec![fixed(&m.armies)];
                stages.extend(m.stages.iter().map(|s| fixed(&s.armies)));
                Entry {
                    mission,
                    key: m.key,
                    title: m.title,
                    enemies: stages.iter().flatten().copied().collect(),
                    stages: stages.iter().map(|v| v.iter().map(|e| e.1).collect()).collect(),
                    enemy_skin: m.skin.is_some(),
                }
            })
            .collect()
    })
}

/// The maps in the order the selector lists them: by the number of enemy COs, fewest first (a map's later stages count: Iron Crown's four lines and Asuka are five), ties in [`def`]'s order.
/// Each item is the map's **mission** (its stable identity: the record, the colour memory and the harness all key by it, never by the position in this list), so a new map lands in its
/// place by being added to [`def`] and nothing else.
pub fn order() -> &'static [usize] {
    static O: std::sync::OnceLock<Vec<usize>> = std::sync::OnceLock::new();
    O.get_or_init(|| {
        let mut v: Vec<usize> = (0..entries().len()).collect();
        v.sort_by_key(|&m| (entries()[m].enemies.len(), m));
        v
    })
}

/// A map's place in the selector's list (0 the top): the map-table id the list shows it by is the first one plus this.
pub fn rank_of(mission: usize) -> usize {
    order().iter().position(|&m| m == mission).unwrap_or(mission)
}

/// The Gauntlet mode's maps as a campaign (its missions; no prologue, staff roll or world map: the mode starts a map from Select Mode).
pub fn def() -> CampaignDef {
    let mut missions = vec![cinder_sea(), iron_crown(), dustwind_basin(), brass_canal(), granite_spine(), harvest_run(), chrome_meridian()];
    missions.iter_mut().for_each(crate::bh_ai::spawn_orders);
    CampaignDef {
        source: SOURCE,
        roster: ROSTER.to_vec(),
        prologue: Vec::new(),
        prologue_song: None,
        prologue_scenes: Vec::new(),
        credits: Vec::new(),
        missions,
        final_mission: "gauntlet_01",
        bonds: Vec::new(),
        extra_bonds: 0,
        secret_mission: "",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cinder_sea_is_a_gauntlet_of_three() {
        let d = def();
        let m = &d.missions[0];
        assert_eq!(m.key, "gauntlet_01");
        let cos: Vec<_> = m.armies.iter().map(|a| a.co).collect();
        assert!(matches!(cos[0], CoSpec::Pick), "the player picks one CO");
        assert!(matches!(cos[1], CoSpec::Fixed(c) if c == co::DRAKE));
        assert!(matches!(cos[2], CoSpec::Fixed(c) if c == co::SENSEI));
        assert!(matches!(cos[3], CoSpec::Fixed(c) if c == co::HAWKE));
        assert_eq!(m.hidden.iter().map(|h| h.army).collect::<Vec<_>>(), vec![3, 4]);
        assert_eq!(m.triggers.len(), 3, "Sensei and Hawke each arrive once; Hawke's fall wins");
        assert!(!m.setup, "no Setup phase");
        let map = crate::custom_campaign::built_map("gauntlet_01").expect("the map is built (five/bhmap.py --campaign gauntlet)");
        assert_eq!((map.width, map.height, map.armies), (32, 22, 4));
    }

    #[test]
    fn the_selector_lists_cinder_sea_with_its_enemies_in_order() {
        let e = entries();
        assert_eq!(e.len(), def().missions.len());
        assert_eq!(e[0].title, "Cinder Sea");
        assert_eq!(e[0].enemies, vec![(co::DRAKE, colour::GREEN_EARTH), (co::SENSEI, colour::YELLOW_COMET), (co::HAWKE, colour::BLACK_HOLE)]);
    }

    #[test]
    fn the_free_colours_are_the_five_minus_the_enemies_plus_the_skins() {
        let skins: Vec<u8> = (0..crate::army_skin::skins().len() as u8).map(|i| crate::army_skin::SKIN + i).collect();
        assert!(!skins.is_empty(), "Silver Nova is a skin");
        // Cinder Sea: Orange Star, Blue Moon and Silver Nova
        let mut want = vec![colour::ORANGE_STAR, colour::BLUE_MOON];
        want.extend(&skins);
        assert_eq!(entries()[0].free(), want);
        // no enemy's colour is ever offered, whatever the map
        for enemy in [vec![], vec![1], vec![3, 4], vec![2, 3, 4, 5]] {
            let f = free_colours(&enemy);
            assert!(f.iter().all(|c| !enemy.contains(c)), "{enemy:?} -> {f:?}");
        }
        // every colour taken: nothing to wear (a skin has no colour to sit on)
        assert!(free_colours(&[1, 2, 3, 4, 5]).is_empty());
        // a skin only where a colour is free to host it
        assert_eq!(free_colours(&[1, 2, 3, 4]), [vec![5u8], skins].concat());
    }

    #[test]
    fn the_roster_is_every_co_once() {
        let mut ids: Vec<u8> = ROSTER.iter().map(|r| r.0).collect();
        ids.sort();
        ids.dedup();
        assert_eq!(ids.len(), ROSTER.len());
        assert!(ROSTER.iter().all(|r| r.1), "every CO is open from the start");
    }

    /// The text map's rows (five/gauntlet/*.txt: the rows are the lines of the map's width after the header).
    fn rows(text: &'static str, w: usize) -> Vec<&'static str> {
        text.lines().filter(|l| l.len() == w && !l.starts_with('#') && !l.contains(' ')).collect()
    }

    #[test]
    fn iron_crown_is_a_gauntlet_of_four_in_five_armies() {
        let d = def();
        assert!(d.missions.len() >= 2, "Cinder Sea and Iron Crown, then the maps added after them");
        let m = &d.missions[1];
        assert_eq!(m.key, "gauntlet_02");
        let cos: Vec<_> = m.armies.iter().map(|a| a.co).collect();
        assert!(matches!(cos[0], CoSpec::Fixed(c) if c == co::GRIT));
        assert!(matches!(cos[1], CoSpec::Fixed(c) if c == co::JESS));
        assert!(matches!(cos[2], CoSpec::Fixed(c) if c == co::KANBEI));
        assert!(matches!(cos[3], CoSpec::Fixed(c) if c == co::RACHEL));
        assert!(matches!(cos[4], CoSpec::Pick), "the player (the fifth army) picks one CO");
        let colours: Vec<_> = m.armies.iter().map(|a| a.colour).collect();
        assert_eq!(colours, vec![colour::BLUE_MOON, colour::GREEN_EARTH, colour::YELLOW_COMET, colour::ORANGE_STAR, colour::BLACK_HOLE], "every enemy colour is fixed on its army");
        assert_eq!(m.hidden.iter().map(|h| h.army).collect::<Vec<_>>(), vec![2, 3, 4], "Jess, Kanbei and Rachel are hidden");
        assert_eq!(m.held_hq, Some(IRON_GRIT));
        assert_eq!(m.held_more, vec![IRON_JESS, IRON_KANBEI, IRON_RACHEL]);
        assert_eq!(m.sleepers.len(), 3);
        assert_eq!(m.cut_off.len(), 3);
        assert_eq!(m.triggers.len(), 4, "three arrivals and the stage switch");
        assert!(!m.setup);
        let map = crate::custom_campaign::built_map("gauntlet_02").expect("the map is built (aw2dev maps gen --campaign gauntlet)");
        assert_eq!((map.width, map.height, map.armies), (40, 26, 5));
        assert!(map.width as u32 * map.height as u32 <= 1288, "the engine's five-army limit");
        // no hidden army has a unit on the map at the start (their waves land when they arrive)
        assert!(map.units.iter().all(|u| u.army == 1 || u.army == 5));
    }

    #[test]
    fn iron_crown_waves_land_on_ground_and_inside_their_zones() {
        let m = &def().missions[1];
        let r = rows(include_str!("../five/gauntlet/gauntlet_02.txt"), 40);
        assert_eq!(r.len(), 26);
        let at = |c: (u8, u8)| r[c.1 as usize].as_bytes()[c.0 as usize] as char;
        for (army, wave) in [(2u8, &JESS_WAVE[..]), (3, &KANBEI_WAVE[..]), (4, &RACHEL_WAVE[..])] {
            let zone = m.hidden.iter().find(|h| h.army == army).unwrap().zone;
            for &(kind, c) in wave {
                assert!(".Rf".contains(at(c)), "army {army}: kind {kind} at {c:?} stands on {:?}", at(c));
                assert!(c.0 as i32 >= zone.x0 as i32 && c.0 as i32 <= zone.x1 as i32 && c.1 as i32 >= zone.y0 as i32 && c.1 as i32 <= zone.y1 as i32, "army {army} {c:?} is outside its zone");
            }
        }
        // the hidden HQs' cells are plain ground until their lines come (the HQ is built on them)
        for hq in [IRON_JESS, IRON_KANBEI, IRON_RACHEL] {
            assert!(".R".contains(at(hq)), "{hq:?} is {:?}", at(hq));
        }
        assert_eq!(at(IRON_GRIT), '1');
    }

    #[test]
    fn asuka_keep_is_the_second_stage() {
        let m = &def().missions[1];
        assert_eq!(m.stages.len(), 1);
        let st = &m.stages[0];
        assert!(matches!(st.armies[0].co, CoSpec::Keep), "the player's CO comes along");
        assert_eq!(st.armies[0].colour, colour::ORANGE_STAR, "the player's skin moves off Black Hole's colour");
        assert!(matches!(st.armies[1].co, CoSpec::Fixed(c) if c == crate::co_new::ASUKA));
        assert_eq!(st.armies[1].colour, colour::BLACK_HOLE, "Asuka shows Black Hole's colours");
        assert_eq!(st.held, vec![KEEP_ASUKA]);
        assert_eq!(st.funds_cap, Some(KEEP_CARRY_CAP));
        assert!(matches!(st.carry, Carry::All));
        assert!(st.units.iter().all(|u| u.army == 2), "only Asuka's units: the survivors replace the player's");
        assert!(st.deploy.len() >= 30, "room for the survivors: {}", st.deploy.len());
        assert_eq!(st.triggers.len(), 3, "two day scenes and the Win");
        let map = crate::custom_campaign::built_map("gauntlet_02b").expect("the stage's map is built");
        assert_eq!((map.width, map.height, map.armies), (30, 22, 2));
        let r = rows(include_str!("../five/gauntlet/gauntlet_02b.txt"), 30);
        assert_eq!(r[KEEP_ASUKA.1 as usize].as_bytes()[KEEP_ASUKA.0 as usize], b'2');
        let text = include_str!("../five/gauntlet/gauntlet_02b.txt");
        assert!(text.contains("\nblackhole"), "the stage's map allows Black Hole's inventions");
    }

    #[test]
    fn the_selector_lists_iron_crown_with_all_five_enemies_and_only_emerald_sun_free() {
        let e = &entries()[1];
        assert_eq!(e.key, "gauntlet_02");
        let cos: Vec<u8> = e.enemies.iter().map(|x| x.0).collect();
        assert_eq!(cos, vec![co::GRIT, co::JESS, co::KANBEI, co::RACHEL, crate::co_new::ASUKA], "Grit, Jess, Kanbei, Rachel, then Asuka of stage two");
        let colours: Vec<u8> = e.enemies.iter().map(|x| x.1).collect();
        assert_eq!(colours, vec![colour::BLUE_MOON, colour::GREEN_EARTH, colour::YELLOW_COMET, colour::ORANGE_STAR, colour::BLACK_HOLE]);
        assert_eq!(e.stages.len(), 2);
        assert_eq!(e.free(), vec![crate::army_skin::SKIN], "every plain colour is an enemy's in some stage: Silver Nova is the only choice");
        // the skin's host: the colour stage one leaves free (Black Hole's), then the one stage two leaves (not Black Hole's: Asuka is)
        let host = |stage: usize| {
            let mut c = vec![crate::army_skin::SKIN];
            c.extend_from_slice(e.stage_enemies(stage));
            crate::army_skin::assign(&c).1[0]
        };
        assert_eq!(host(0), colour::BLACK_HOLE);
        assert_ne!(host(1), colour::BLACK_HOLE);
        assert_eq!(host(1), colour::ORANGE_STAR);
        // Cinder Sea is unchanged by the stages
        assert_eq!(entries()[0].free(), free_colours(&[colour::GREEN_EARTH, colour::YELLOW_COMET, colour::BLACK_HOLE]));
    }

    // --- every map, whatever its number (the generic checks a new map gets by being added to `def`) -----------------------------------------------------------

    fn text_of(key: &str) -> &'static str {
        match key {
            "gauntlet_01" => include_str!("../five/gauntlet/gauntlet_01.txt"),
            "gauntlet_02" => include_str!("../five/gauntlet/gauntlet_02.txt"),
            "gauntlet_03" => include_str!("../five/gauntlet/gauntlet_03.txt"),
            "gauntlet_04" => include_str!("../five/gauntlet/gauntlet_04.txt"),
            "gauntlet_05" => include_str!("../five/gauntlet/gauntlet_05.txt"),
            "gauntlet_06" => include_str!("../five/gauntlet/gauntlet_06.txt"),
            "gauntlet_07" => include_str!("../five/gauntlet/gauntlet_07.txt"),
            other => panic!("no text map for {other}: add it to text_of"),
        }
    }

    #[test]
    fn every_map_is_wired_as_a_gauntlet_by_the_rout_rule() {
        for m in def().missions.iter() {
            let n = m.hidden.len();
            assert!(n >= 1, "{}: at least two lines", m.key);
            let first = m.held_hq.unwrap_or_else(|| panic!("{}: the first line's HQ is held", m.key));
            // the lines in order: the first, then the hidden ones; every line but the last is routed by an HQ capture (cut_off), the last is not
            let mut hqs = vec![first];
            hqs.extend(m.hidden.iter().map(|h| h.hq));
            assert_eq!(m.held_more, hqs[1..].to_vec(), "{}: every later HQ is held", m.key);
            assert_eq!(m.cut_off.len(), hqs.len() - 1, "{}: every line but the last is cut off", m.key);
            for (k, (army, hq)) in m.cut_off.iter().enumerate() {
                assert_eq!(*hq, hqs[k], "{}: cut_off line {k}", m.key);
                if k > 0 {
                    assert_eq!(*army, m.hidden[k - 1].army);
                }
            }
            assert!(m.cut_off.iter().all(|(_, hq)| *hq != *hqs.last().unwrap()), "{}: the last line's HQ is not routed (it wins)", m.key);
            assert_eq!(m.sleepers.len(), n, "{}: each hidden line sleeps until the lines before it fall", m.key);
            for (k, (army, before)) in m.sleepers.iter().enumerate() {
                assert_eq!(*army, m.hidden[k].army);
                assert_eq!(before, &hqs[..k + 1].to_vec());
            }
            // an arrival trigger for each hidden line, then the win
            assert_eq!(m.triggers.len(), n + if m.stages.is_empty() { 1 } else { 1 }, "{}: one arrival per hidden line and the closing trigger", m.key);
        }
    }

    #[test]
    fn every_map_wave_lands_on_ground_inside_its_zone() {
        let skip = ["gauntlet_01"]; // (Cinder Sea is a sea map: its waves stand on water and shore)
        for m in def().missions.iter().filter(|m| !skip.contains(&m.key)) {
            let map = crate::custom_campaign::built_map(m.key).unwrap_or_else(|| panic!("{}: the map is built (aw2dev maps gen --campaign gauntlet)", m.key));
            let r = rows(text_of(m.key), map.width as usize);
            assert_eq!(r.len(), map.height as usize, "{}", m.key);
            for h in &m.hidden {
                assert!(".R".contains(r[h.hq.1 as usize].as_bytes()[h.hq.0 as usize] as char), "{}: hidden HQ {:?} is plain ground until its line comes", m.key, h.hq);
                let mut spawned = 0;
                for t in m.triggers.iter() {
                    for a in &t.then {
                        if let Action::Spawn(v) = a {
                            for u in v.iter().filter(|u| u.army == h.army) {
                                spawned += 1;
                                let c = r[u.y as usize].as_bytes()[u.x as usize] as char;
                                let air = matches!(u.kind, unit::FIGHTER | unit::BOMBER | unit::B_COPTER | unit::T_COPTER | unit::STEALTH);
                                assert!(".Rf=,Aa".contains(c) || air && c != '~', "{}: army {} kind {} at ({}, {}) stands on {c:?}", m.key, h.army, u.kind, u.x, u.y);
                                assert!(u.x >= h.zone.x0 && u.x <= h.zone.x1 && u.y >= h.zone.y0 && u.y <= h.zone.y1, "{}: army {} unit at ({}, {}) is outside its zone", m.key, h.army, u.x, u.y);
                            }
                        }
                    }
                }
                assert!(spawned >= 12, "{}: army {} has a wave ({spawned} units)", m.key, h.army);
            }
        }
    }

    #[test]
    fn the_selector_orders_the_maps_by_their_enemy_count_fewest_first() {
        let e = entries();
        let order = order();
        assert_eq!(order.len(), e.len());
        let counts: Vec<usize> = order.iter().map(|&m| e[m].enemies.len()).collect();
        assert!(counts.windows(2).all(|w| w[0] <= w[1]), "fewest enemies first: {counts:?}");
        // ties keep the definition's order (the older, easier map first), a permutation of the missions, and rank_of is its inverse
        for w in order.windows(2) {
            if e[w[0]].enemies.len() == e[w[1]].enemies.len() {
                assert!(w[0] < w[1]);
            }
        }
        let mut sorted = order.to_vec();
        sorted.sort();
        assert_eq!(sorted, (0..e.len()).collect::<Vec<_>>());
        for (rank, &m) in order.iter().enumerate() {
            assert_eq!(rank_of(m), rank);
        }
        // Iron Crown (four lines and Asuka's stage) is last; the maps with two enemies are first
        let keys: Vec<&str> = order.iter().map(|&m| e[m].key).collect();
        assert_eq!(keys.last(), Some(&"gauntlet_02"));
        assert!(e[order[0]].enemies.len() == 2);
    }

    #[test]
    fn the_new_maps_have_the_enemy_counts_and_lines_the_design_asks_for() {
        let e = entries();
        let by = |k: &str| e.iter().find(|x| x.key == k).unwrap();
        assert_eq!(by("gauntlet_03").enemies.iter().map(|x| x.0).collect::<Vec<_>>(), vec![co::KOAL, co::LASH]);
        assert_eq!(by("gauntlet_04").enemies.iter().map(|x| x.0).collect::<Vec<_>>(), vec![co::SASHA, co::JAVIER]);
        assert_eq!(by("gauntlet_05").enemies.iter().map(|x| x.0).collect::<Vec<_>>(), vec![co::JAKE, co::GRIMM, co::VON_BOLT]);
        // Harvest Run: all of Orange Star, four slots, one colour: the player can never wear Orange Star, and the colour pick still offers the other four and the skin
        let h = by("gauntlet_06");
        assert_eq!(h.enemies.iter().map(|x| x.0).collect::<Vec<_>>(), vec![co::ANDY, co::MAX, co::SAMI, co::NELL]);
        assert!(h.enemies.iter().all(|x| x.1 == colour::ORANGE_STAR));
        assert_eq!(h.free(), vec![colour::BLUE_MOON, colour::YELLOW_COMET, colour::GREEN_EARTH, colour::BLACK_HOLE, crate::army_skin::SKIN]);
        // Chrome Meridian: Flak, then the three Silver Nova COs on one colour; the skin is on the field already, so the player may wear plain colours only, never the host's or Black Hole's
        let c = by("gauntlet_07");
        assert_eq!(c.enemies.iter().map(|x| x.0).collect::<Vec<_>>(), vec![co::FLAK, crate::es_co::CAULDER, crate::es_co::LILI, crate::es_co::TABITHA]);
        assert!(c.enemy_skin);
        assert_eq!(c.enemies.iter().map(|x| x.1).collect::<Vec<_>>(), vec![colour::BLACK_HOLE, CHROME_HOST, CHROME_HOST, CHROME_HOST]);
        assert_eq!(c.free(), crate::army_skin::order().into_iter().filter(|c| *c < crate::army_skin::SKIN && *c != colour::BLACK_HOLE && *c != CHROME_HOST).collect::<Vec<_>>());
        let m = &def().missions[c.mission];
        assert_eq!(m.skin, Some((CHROME_SKIN_ARMY, 0)));
        // the skin's lines are the armies that wear the host colour, and Black Hole's line does not
        assert_eq!(m.armies[0].colour, colour::BLACK_HOLE);
        assert!(m.armies[1..4].iter().all(|a| a.colour == m.armies[CHROME_SKIN_ARMY as usize - 1].colour));
        // the other maps' skins are the player's choice only
        assert!(!by("gauntlet_01").enemy_skin && !by("gauntlet_02").enemy_skin);
    }
}
