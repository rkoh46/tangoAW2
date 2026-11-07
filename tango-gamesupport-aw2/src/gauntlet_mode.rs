//! The Gauntlet mode's maps (docs/dev/gauntlet.md "The Gauntlet mode"): one battle per map against a fixed line-up of COs who come one after another, the player
//! with a free pick of one CO. Each map is a mission of a small custom campaign ([`def`]) played by the campaign engine (AW2's event engine runs only there), so the
//! gauntlet engine ([`crate::custom_campaign`]: `MissionDef::hidden`, `sleepers`, `cut_off`, `Action::Reveal`, `Cond::LineFallen`) works as in BH2's M31.
//! A new map is a spec (`five/gauntlet/spec/gauntlet_NN.py`, `aw2dev maps gen --campaign gauntlet`) and a function here added to [`def`]'s missions.

use mgba::core::Core;

use crate::campaign_music::Track;
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
    // (a two-map run: the selector's list and the army screen say so)
    m.list_title = "Iron Crown *";
    m.stage_titles = &["Asuka's Keep"];
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
    (unit::INFANTRY, (3, 3)),
    (unit::INFANTRY, (8, 7)),
    (unit::INFANTRY, (7, 5)),
    (unit::INFANTRY, (1, 9)),
    (unit::MECH, (4, 4)),
    (unit::MECH, (6, 1)),
    (unit::MECH, (11, 9)),
    (unit::ARTILLERY, (12, 6)),
    (unit::ARTILLERY, (10, 9)),
    (unit::ARTILLERY, (11, 5)),
    (unit::MD_TANK, (7, 8)),
    (unit::MD_TANK, (8, 5)),
    (unit::MD_TANK, (1, 6)),
    (unit::ROCKETS, (4, 2)),
    (unit::ANTI_AIR, (12, 7)),
    (unit::RECON, (11, 7)),
    (unit::B_COPTER, (9, 6)),
    (unit::B_COPTER, (9, 3)),
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
    m.look = 2; // the Desert look: rock and canyon walls, sand
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
    (unit::TANK, (26, 17)),
    (unit::TANK, (23, 18)),
    (unit::TANK, (29, 15)),
    (unit::TANK, (17, 17)),
    (unit::MD_TANK, (24, 17)),
    (unit::MD_TANK, (25, 13)),
    (unit::MD_TANK, (20, 14)),
    (unit::ARTILLERY, (21, 13)),
    (unit::ARTILLERY, (26, 13)),
    (unit::ARTILLERY, (24, 14)),
    (unit::ROCKETS, (23, 14)),
    (unit::INFANTRY, (18, 18)),
    (unit::INFANTRY, (28, 20)),
    (unit::INFANTRY, (18, 15)),
    (unit::INFANTRY, (28, 21)),
    (unit::MECH, (20, 16)),
    (unit::MECH, (27, 19)),
    (unit::ANTI_AIR, (20, 18)),
    (unit::RECON, (23, 17)),
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
    (unit::MD_TANK, (8, 5)),
    (unit::MD_TANK, (8, 3)),
    (unit::MD_TANK, (6, 8)),
    (unit::MEGATANK, (11, 5)),
    (unit::ARTILLERY, (5, 7)),
    (unit::ARTILLERY, (1, 7)),
    (unit::ARTILLERY, (12, 4)),
    (unit::ROCKETS, (1, 1)),
    (unit::INFANTRY, (11, 9)),
    (unit::INFANTRY, (4, 4)),
    (unit::INFANTRY, (2, 8)),
    (unit::MECH, (9, 8)),
    (unit::MECH, (3, 6)),
    (unit::ANTI_AIR, (6, 5)),
    (unit::B_COPTER, (8, 1)),
    (unit::B_COPTER, (11, 3)),
    (unit::T_COPTER, (4, 3)),
];

/// Von Bolt's wave: the north-east valley's armour, a Neo Tank, missiles, a Bomber and a Fighter.
const VON_BOLT_WAVE: [(u8, (u8, u8)); 17] = [
    (unit::MD_TANK, (26, 4)),
    (unit::MD_TANK, (29, 1)),
    (unit::MD_TANK, (22, 6)),
    (unit::TANK, (30, 4)),
    (unit::TANK, (24, 5)),
    (unit::NEOTANK, (27, 5)),
    (unit::ARTILLERY, (25, 3)),
    (unit::ARTILLERY, (21, 0)),
    (unit::MISSILES, (30, 7)),
    (unit::INFANTRY, (22, 2)),
    (unit::INFANTRY, (30, 5)),
    (unit::INFANTRY, (28, 6)),
    (unit::MECH, (21, 3)),
    (unit::MECH, (20, 3)),
    (unit::FIGHTER, (22, 0)),
    (unit::BOMBER, (25, 2)),
    (unit::ANTI_AIR, (28, 1)),
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
    (unit::MD_TANK, (24, 5)),
    (unit::MD_TANK, (27, 9)),
    (unit::MD_TANK, (34, 3)),
    (unit::MD_TANK, (33, 1)),
    (unit::TANK, (29, 2)),
    (unit::TANK, (25, 5)),
    (unit::TANK, (23, 5)),
    (unit::RECON, (26, 1)),
    (unit::RECON, (22, 1)),
    (unit::MEGATANK, (29, 8)),
    (unit::INFANTRY, (25, 8)),
    (unit::INFANTRY, (23, 4)),
    (unit::INFANTRY, (28, 7)),
    (unit::MECH, (28, 2)),
    (unit::MECH, (23, 1)),
    (unit::MECH, (22, 7)),
    (unit::ARTILLERY, (26, 5)),
    (unit::ARTILLERY, (21, 8)),
    (unit::ANTI_AIR, (30, 5)),
    (unit::B_COPTER, (26, 7)),
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
    (unit::APC, (26, 22)),
    (unit::APC, (25, 21)),
    (unit::TANK, (29, 18)),
    (unit::TANK, (33, 20)),
    (unit::TANK, (34, 16)),
    (unit::MD_TANK, (27, 14)),
    (unit::MD_TANK, (31, 20)),
    (unit::ROCKETS, (29, 19)),
    (unit::ARTILLERY, (29, 21)),
    (unit::ARTILLERY, (32, 20)),
    (unit::ANTI_AIR, (30, 20)),
    (unit::T_COPTER, (28, 21)),
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
pub const CHROME_CAULDER: (u8, u8) = (30, 5);
pub const CHROME_LILI: (u8, u8) = (30, 12);
pub const CHROME_TABITHA: (u8, u8) = (30, 20);
pub const CHROME_PLAYER: (u8, u8) = (4, 22);

/// Caulder's wave: the corps' siege engines in the citadel's north ward (artillery, rockets, missiles), armour and foot soldiers in front of them.
const CAULDER_WAVE: [(u8, (u8, u8)); 19] = [
    (unit::ARTILLERY, (30, 7)),
    (unit::ARTILLERY, (27, 4)),
    (unit::ARTILLERY, (32, 5)),
    (unit::ARTILLERY, (30, 5)),
    (unit::ROCKETS, (30, 3)),
    (unit::ROCKETS, (35, 7)),
    (unit::MISSILES, (27, 2)),
    (unit::MD_TANK, (26, 4)),
    (unit::MD_TANK, (28, 4)),
    (unit::MD_TANK, (35, 4)),
    (unit::TANK, (29, 2)),
    (unit::TANK, (33, 2)),
    (unit::INFANTRY, (33, 7)),
    (unit::INFANTRY, (28, 6)),
    (unit::INFANTRY, (34, 3)),
    (unit::MECH, (33, 6)),
    (unit::MECH, (27, 6)),
    (unit::ANTI_AIR, (32, 4)),
    (unit::APC, (29, 6)),
];

/// Lili's wave: fast armour (recons, tanks) and copters over the Meridian.
const LILI_WAVE: [(u8, (u8, u8)); 20] = [
    (unit::RECON, (26, 15)),
    (unit::RECON, (28, 12)),
    (unit::RECON, (33, 13)),
    (unit::TANK, (31, 13)),
    (unit::TANK, (33, 11)),
    (unit::TANK, (35, 15)),
    (unit::TANK, (28, 10)),
    (unit::MD_TANK, (27, 12)),
    (unit::MD_TANK, (30, 12)),
    (unit::MD_TANK, (32, 12)),
    (unit::B_COPTER, (30, 10)),
    (unit::B_COPTER, (27, 11)),
    (unit::B_COPTER, (33, 15)),
    (unit::FIGHTER, (32, 14)),
    (unit::INFANTRY, (26, 12)),
    (unit::INFANTRY, (34, 14)),
    (unit::INFANTRY, (27, 14)),
    (unit::MECH, (35, 12)),
    (unit::MECH, (28, 15)),
    (unit::ANTI_AIR, (26, 13)),
];

/// Tabitha's wave: the corps' heavy armour, a Mega Tank and Neo Tanks, bombers and fighters.
const TABITHA_WAVE: [(u8, (u8, u8)); 20] = [
    (unit::MEGATANK, (27, 23)),
    (unit::NEOTANK, (35, 19)),
    (unit::NEOTANK, (34, 20)),
    (unit::MD_TANK, (30, 20)),
    (unit::MD_TANK, (30, 19)),
    (unit::MD_TANK, (35, 23)),
    (unit::TANK, (27, 18)),
    (unit::TANK, (26, 20)),
    (unit::ARTILLERY, (28, 20)),
    (unit::ARTILLERY, (32, 20)),
    (unit::INFANTRY, (30, 18)),
    (unit::INFANTRY, (33, 18)),
    (unit::INFANTRY, (33, 23)),
    (unit::MECH, (32, 22)),
    (unit::MECH, (34, 19)),
    (unit::BOMBER, (34, 22)),
    (unit::FIGHTER, (35, 21)),
    (unit::ANTI_AIR, (31, 20)),
    (unit::ANTI_AIR, (30, 23)),
    (unit::B_COPTER, (27, 20)),
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
    let lines = [
        Wire { army: 1, hq: CHROME_FLAK, zone: Rect::new(2, 9, 18, 18) },
        Wire { army: 2, hq: CHROME_CAULDER, zone: Rect::new(26, 2, 35, 7) },
        Wire { army: 3, hq: CHROME_LILI, zone: Rect::new(26, 10, 35, 15) },
        Wire { army: 4, hq: CHROME_TABITHA, zone: Rect::new(26, 18, 35, 23) },
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
    m.victory = Scene::new(vec![Line::say(crate::es_co::TABITHA, "You broke my Meridian! I will not forget your face. Stupid weak people!")]);
    m
}

fn caulder_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::FLAK, Mood::Sad, "What?! Nobody told me I'd lose! Somebody else take over!"),
        Line::say(crate::es_co::CAULDER, "A pity. The depot was only a first trial. The citadel is the real experiment."),
        Line::say(crate::es_co::CAULDER, "Every gate and tower is measured. Do come in. I shall take notes."),
    ])
}

fn lili_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(crate::es_co::CAULDER, Mood::Sad, "The citadel has fallen? How tedious. My notes were so tidy."),
        Line::say(crate::es_co::LILI, "Daddy is slow! Now it is my turn! The plains are my playground!"),
        Line::say(crate::es_co::LILI, "Zoom, zoom, zoom! Mr. Bear says catch me if you can! Hee hee!"),
    ])
}

fn tabitha_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(crate::es_co::LILI, Mood::Sad, "They broke my toys! Sister, Sister, the rest is for you! Please?"),
        Line::say(crate::es_co::TABITHA, "Hush, Lili. Go sit behind me. I will end this."),
        Line::say(crate::es_co::TABITHA, "Come to the south-east, little people. I will show you what silver cuts like."),
    ])
}

// --- Gauntlet 08, Tidewater Atoll ---------------------------------------------------------------------------------------------------------------------------

/// The HQs (five/gauntlet/spec/gauntlet_08.py): the player's, Eagle's (on the field), Adder's (hidden).
pub const TIDE_PLAYER: (u8, u8) = (3, 14);
pub const TIDE_EAGLE: (u8, u8) = (25, 4);
pub const TIDE_ADDER: (u8, u8) = (25, 15);

/// Adder's wave: a battleship, two cruisers, a Sub and a Black Boat off his island, bombers, a Fighter and a Copter overhead, troops and armour on it.
const ADDER_WAVE: [(u8, (u8, u8)); 18] = [
    (unit::BATTLESHIP, (19, 16)),
    (unit::CRUISER, (19, 13)),
    (unit::CRUISER, (29, 13)),
    (unit::SUB, (19, 18)),
    (unit::BLACK_BOAT, (29, 16)),
    (unit::BOMBER, (23, 13)),
    (unit::BOMBER, (22, 17)),
    (unit::FIGHTER, (26, 11)),
    (unit::INFANTRY, (21, 16)),
    (unit::INFANTRY, (26, 15)),
    (unit::INFANTRY, (21, 17)),
    (unit::MECH, (27, 17)),
    (unit::MECH, (24, 16)),
    (unit::TANK, (23, 15)),
    (unit::TANK, (25, 12)),
    (unit::ARTILLERY, (24, 11)),
    (unit::ANTI_AIR, (28, 15)),
    (unit::B_COPTER, (25, 16)),
];

/// Tidewater Atoll: the player (a free CO) against Eagle (Green Earth) on the north-east island, then Adder (Black Hole) on the south-east island.
fn tidewater_atoll() -> MissionDef {
    let mut m = MissionDef::new("gauntlet_08", "Tidewater Atoll");
    m.objective = "Take Eagle's island, then Adder's harbour.";
    m.map = MapSrc::Built("gauntlet_08");
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pick).funds(12000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::EAGLE)).team(2).funds(8000),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::ADDER)).team(2).funds(0),
    ];
    m.units = crate::es_campaign::deployment("gauntlet_08");
    let lines = [
        Wire { army: 2, hq: TIDE_EAGLE, zone: Rect::new(19, 0, 29, 9) },
        Wire { army: 3, hq: TIDE_ADDER, zone: Rect::new(18, 10, 29, 19) },
    ];
    wire(&mut m, &lines, vec![arrival(&lines, 1, chest::<3, 15000, 1000>, &ADDER_WAVE, adder_arrives())]);
    m.intro = Scene::new(vec![
        Line::say(co::EAGLE, "Welcome to the atoll! The wind and the sky are on my side."),
        Line::say(co::EAGLE, "Land on my beach if you can. My fighters will be waiting."),
    ]);
    m.victory = Scene::new(vec![Line::say(co::ADDER, "The atoll is yours. Fine flying. I will remember the face.")]);
    m
}

fn adder_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::EAGLE, Mood::Sad, "My island has fallen? Adder, take the harbour. Hold the line!"),
        Line::say(co::ADDER, "With pleasure. The harbour is mine, and the sea is wide."),
        Line::say(co::ADDER, "You will find the water here colder than you expected."),
    ])
}

// --- Gauntlet 09, Silverpine Ford ---------------------------------------------------------------------------------------------------------------------------

/// The HQs (five/gauntlet/spec/gauntlet_09.py): the player's, Hachi's (on the field), Sonja's (hidden).
pub const SILVER_PLAYER: (u8, u8) = (3, 18);
pub const SILVER_HACHI: (u8, u8) = (26, 10);
pub const SILVER_SONJA: (u8, u8) = (6, 4);

/// Sonja's wave: recons and artillery in the north-west woods, foot soldiers and a Copter.
const SONJA_WAVE: [(u8, (u8, u8)); 19] = [
    (unit::INFANTRY, (6, 6)),
    (unit::INFANTRY, (7, 1)),
    (unit::INFANTRY, (7, 6)),
    (unit::INFANTRY, (2, 3)),
    (unit::INFANTRY, (11, 6)),
    (unit::MECH, (13, 2)),
    (unit::MECH, (13, 7)),
    (unit::RECON, (11, 4)),
    (unit::RECON, (6, 4)),
    (unit::RECON, (11, 7)),
    (unit::TANK, (4, 7)),
    (unit::TANK, (6, 5)),
    (unit::MD_TANK, (12, 1)),
    (unit::ARTILLERY, (8, 6)),
    (unit::ARTILLERY, (11, 3)),
    (unit::ARTILLERY, (13, 3)),
    (unit::ROCKETS, (2, 6)),
    (unit::ANTI_AIR, (8, 5)),
    (unit::B_COPTER, (12, 5)),
];

/// Silverpine Ford: the player (a free CO) against Hachi (Green Earth) in the eastern pines, then Sonja (Blue Moon) in the north-west woods.
fn silverpine_ford() -> MissionDef {
    let mut m = MissionDef::new("gauntlet_09", "Silverpine Ford");
    m.objective = "Cross the Silver Pool's river and take Hachi's pines, then Sonja's woods.";
    m.map = MapSrc::Built("gauntlet_09");
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pick).funds(12000),
        ArmyDef::new(colour::GREEN_EARTH, CoSpec::Fixed(co::HACHI)).team(2).funds(8000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::SONJA)).team(2).funds(0),
    ];
    m.units = crate::es_campaign::deployment("gauntlet_09");
    let lines = [
        Wire { army: 2, hq: SILVER_HACHI, zone: Rect::new(17, 0, 31, 21) },
        Wire { army: 3, hq: SILVER_SONJA, zone: Rect::new(0, 0, 14, 8) },
    ];
    wire(&mut m, &lines, vec![arrival(&lines, 1, chest::<3, 15000, 1000>, &SONJA_WAVE, sonja_arrives())]);
    m.intro = Scene::new(vec![
        Line::say(co::HACHI, "Welcome to Silverpine! Fresh air, good soup, and a river to cross."),
        Line::say(co::HACHI, "Cross at the fords if you like. I keep a table by every one."),
    ]);
    m.victory = Scene::new(vec![Line::say(co::SONJA, "The ford is yours. I read the river wrong, and you read it right.")]);
    m
}

fn sonja_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::HACHI, Mood::Sad, "My soup pot, my pines! Sonja, the woods are yours!"),
        Line::say(co::SONJA, "Thank you, Hachi. I have been watching from the trees."),
        Line::say(co::SONJA, "Every path in these woods has a lookout. Come and find them."),
    ])
}

// --- Gauntlet 10, Neon Row ----------------------------------------------------------------------------------------------------------------------------------

/// The HQs (five/gauntlet/spec/gauntlet_10.py): the player's, Colin's (on the field), Kindle's and Jugger's (hidden).
pub const NEON_PLAYER: (u8, u8) = (4, 16);
pub const NEON_COLIN: (u8, u8) = (22, 9);
pub const NEON_KINDLE: (u8, u8) = (4, 3);
pub const NEON_JUGGER: (u8, u8) = (28, 3);

/// Kindle's wave: infantry swarming the north-west blocks, tanks, missiles and copters over the roofs.
const KINDLE_WAVE: [(u8, (u8, u8)); 19] = [
    (unit::INFANTRY, (1, 4)),
    (unit::INFANTRY, (10, 1)),
    (unit::INFANTRY, (11, 3)),
    (unit::INFANTRY, (12, 3)),
    (unit::INFANTRY, (2, 6)),
    (unit::INFANTRY, (8, 2)),
    (unit::MECH, (10, 4)),
    (unit::MECH, (9, 5)),
    (unit::TANK, (3, 5)),
    (unit::TANK, (5, 6)),
    (unit::TANK, (1, 2)),
    (unit::MD_TANK, (2, 0)),
    (unit::MD_TANK, (9, 1)),
    (unit::MISSILES, (9, 3)),
    (unit::ARTILLERY, (11, 2)),
    (unit::ARTILLERY, (9, 6)),
    (unit::ANTI_AIR, (7, 2)),
    (unit::B_COPTER, (3, 0)),
    (unit::B_COPTER, (2, 2)),
];

/// Jugger's wave: tanks and a Mega Tank in the north-east blocks, rockets and artillery behind them.
const JUGGER_WAVE: [(u8, (u8, u8)); 20] = [
    (unit::TANK, (29, 2)),
    (unit::TANK, (16, 2)),
    (unit::TANK, (26, 2)),
    (unit::MD_TANK, (28, 2)),
    (unit::MD_TANK, (27, 4)),
    (unit::MD_TANK, (20, 2)),
    (unit::MEGATANK, (31, 2)),
    (unit::ARTILLERY, (30, 3)),
    (unit::ARTILLERY, (21, 4)),
    (unit::ROCKETS, (27, 5)),
    (unit::ROCKETS, (21, 1)),
    (unit::INFANTRY, (16, 0)),
    (unit::INFANTRY, (30, 0)),
    (unit::INFANTRY, (31, 4)),
    (unit::INFANTRY, (25, 3)),
    (unit::MECH, (17, 6)),
    (unit::MECH, (18, 3)),
    (unit::ANTI_AIR, (20, 0)),
    (unit::RECON, (17, 2)),
    (unit::B_COPTER, (22, 5)),
];

/// Neon Row: the player (a free CO) against Colin (Blue Moon) in the east-centre blocks, then Kindle (Black Hole) in the north-west blocks, then Jugger (Black Hole) in the north-east blocks.
fn neon_row() -> MissionDef {
    let mut m = MissionDef::new("gauntlet_10", "Neon Row");
    m.objective = "Take the downtown block by block: Colin's, then Kindle's and Jugger's.";
    m.map = MapSrc::Built("gauntlet_10");
    m.armies = vec![
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pick).funds(12000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::COLIN)).team(2).funds(10000),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::KINDLE)).team(2).funds(0),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::JUGGER)).team(2).funds(0),
    ];
    m.units = crate::es_campaign::deployment("gauntlet_10");
    let lines = [
        Wire { army: 2, hq: NEON_COLIN, zone: Rect::new(16, 8, 31, 14) },
        Wire { army: 3, hq: NEON_KINDLE, zone: Rect::new(0, 0, 14, 7) },
        Wire { army: 4, hq: NEON_JUGGER, zone: Rect::new(16, 0, 31, 7) },
    ];
    wire(
        &mut m,
        &lines,
        vec![
            arrival(&lines, 1, chest::<3, 15000, 1000>, &KINDLE_WAVE, kindle_arrives()),
            arrival(&lines, 2, chest::<4, 20000, 1500>, &JUGGER_WAVE, jugger_arrives()),
        ],
    );
    m.intro = Scene::new(vec![
        Line::say(co::COLIN, "Welcome to Neon Row! Every sign on this street is mine."),
        Line::say(co::COLIN, "Money talks here, friend. And it never stops talking."),
    ]);
    m.victory = Scene::new(vec![Line::say(co::JUGGER, "Heh. You took the whole street. Not bad for a nobody.")]);
    m
}

fn kindle_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::COLIN, Mood::Sad, "My shops! My signs! Somebody take this street off my hands!"),
        Line::say(co::KINDLE, "Oh, I will. Let me show you how a real city fights, honey."),
        Line::say(co::KINDLE, "Every block you take, I take two back. Come on in."),
    ])
}

fn jugger_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::KINDLE, Mood::Sad, "Ugh, my streets! You are no fun at all. Jugger, you're up."),
        Line::say(co::JUGGER, "Finally. My turn to bust something up."),
        Line::say(co::JUGGER, "The rest of this street gets flattened. Hope you like rubble."),
    ])
}

// --- Gauntlet 11, Blue Bastion: all of Blue Moon -----------------------------------------------------------------------------------------------------------

/// The HQs (five/gauntlet/spec/gauntlet_11.py): Olaf's (the outer bailey, on the field), Grit's (west ward), Colin's (east ward) and Sasha's (the keep: hidden), the player's (army 5).
pub const BASTION_OLAF: (u8, u8) = (16, 21);
pub const BASTION_GRIT: (u8, u8) = (20, 15);
pub const BASTION_COLIN: (u8, u8) = (32, 15);
pub const BASTION_SASHA: (u8, u8) = (26, 13);
pub const BASTION_PLAYER: (u8, u8) = (3, 22);

/// Grit's wave: artillery and rockets in the west ward, Md Tanks, a Tank and foot soldiers.
const GRIT_WAVE: [(u8, (u8, u8)); 17] = [
    (unit::ARTILLERY, (20, 13)),
    (unit::ARTILLERY, (19, 15)),
    (unit::ARTILLERY, (19, 13)),
    (unit::ARTILLERY, (21, 13)),
    (unit::ROCKETS, (19, 10)),
    (unit::ROCKETS, (20, 15)),
    (unit::MD_TANK, (21, 15)),
    (unit::MD_TANK, (19, 12)),
    (unit::INFANTRY, (19, 11)),
    (unit::INFANTRY, (19, 16)),
    (unit::INFANTRY, (21, 12)),
    (unit::INFANTRY, (20, 11)),
    (unit::MECH, (21, 11)),
    (unit::MECH, (21, 17)),
    (unit::MECH, (18, 15)),
    (unit::ANTI_AIR, (20, 17)),
    (unit::TANK, (18, 17)),
];

/// Colin's wave: cheap tanks and a crowd of infantry in the east ward, copters.
const COLIN_WAVE: [(u8, (u8, u8)); 19] = [
    (unit::TANK, (34, 13)),
    (unit::TANK, (32, 15)),
    (unit::TANK, (32, 13)),
    (unit::TANK, (31, 13)),
    (unit::INFANTRY, (32, 10)),
    (unit::INFANTRY, (33, 15)),
    (unit::INFANTRY, (34, 15)),
    (unit::INFANTRY, (31, 12)),
    (unit::INFANTRY, (32, 11)),
    (unit::INFANTRY, (32, 16)),
    (unit::MECH, (33, 13)),
    (unit::MECH, (33, 11)),
    (unit::MD_TANK, (31, 15)),
    (unit::MD_TANK, (34, 17)),
    (unit::APC, (31, 17)),
    (unit::ANTI_AIR, (33, 17)),
    (unit::B_COPTER, (32, 17)),
    (unit::B_COPTER, (33, 16)),
    (unit::ROCKETS, (34, 10)),
];

/// Sasha's wave: Md Tanks, a Mega Tank and artillery in the keep, a Fighter and a Bomber.
const SASHA_WAVE: [(u8, (u8, u8)); 20] = [
    (unit::MD_TANK, (27, 13)),
    (unit::MD_TANK, (26, 14)),
    (unit::MD_TANK, (26, 13)),
    (unit::MEGATANK, (28, 13)),
    (unit::TANK, (26, 11)),
    (unit::TANK, (29, 13)),
    (unit::TANK, (24, 14)),
    (unit::INFANTRY, (23, 13)),
    (unit::INFANTRY, (25, 12)),
    (unit::INFANTRY, (29, 15)),
    (unit::INFANTRY, (27, 14)),
    (unit::MECH, (28, 12)),
    (unit::MECH, (29, 12)),
    (unit::ARTILLERY, (28, 16)),
    (unit::ARTILLERY, (27, 15)),
    (unit::ARTILLERY, (26, 16)),
    (unit::FIGHTER, (29, 16)),
    (unit::BOMBER, (23, 16)),
    (unit::ANTI_AIR, (25, 15)),
    (unit::ANTI_AIR, (24, 11)),
];

/// Blue Bastion: all of Blue Moon in one fortress, the lines one after another (the same colour on four army slots, as Harvest Run's Orange Star).
fn blue_bastion() -> MissionDef {
    let mut m = MissionDef::new("gauntlet_11", "Blue Bastion");
    m.objective = "Storm the castle ring by ring: Olaf, then Grit, Colin and Sasha in the keep.";
    m.map = MapSrc::Built("gauntlet_11");
    m.armies = vec![
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::OLAF)).team(1).funds(9000),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::GRIT)).team(1).funds(0),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::COLIN)).team(1).funds(0),
        ArmyDef::new(colour::BLUE_MOON, CoSpec::Fixed(co::SASHA)).team(1).funds(0),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(20000),
    ];
    m.units = crate::bh_ai::orders(crate::bh_ai::built_units("gauntlet_11"), 5, crate::bh_ai::ATTACK, |u| u.ai == 1);
    let lines = [
        Wire { army: 1, hq: BASTION_OLAF, zone: Rect::new(13, 5, 39, 22) },
        Wire { army: 2, hq: BASTION_GRIT, zone: Rect::new(18, 10, 21, 17) },
        Wire { army: 3, hq: BASTION_COLIN, zone: Rect::new(31, 10, 34, 17) },
        Wire { army: 4, hq: BASTION_SASHA, zone: Rect::new(23, 11, 29, 16) },
    ];
    wire(
        &mut m,
        &lines,
        vec![
            arrival(&lines, 1, chest::<2, 15000, 1000>, &GRIT_WAVE, grit_arrives()),
            arrival(&lines, 2, chest::<3, 20000, 1500>, &COLIN_WAVE, colin_arrives()),
            arrival(&lines, 3, chest::<4, 25000, 2000>, &SASHA_WAVE, sasha_arrives()),
        ],
    );
    m.intro = Scene::new(vec![
        Line::say(co::OLAF, "Welcome to the Bastion! All of Blue Moon stands behind these walls."),
        Line::say(co::OLAF, "Cold stone, cold hearts. I will hold the outer wall myself."),
    ]);
    m.victory = Scene::new(vec![Line::say(co::SASHA, "The Bastion has fallen. Blue Moon will remember it. And you.")]);
    m
}

fn grit_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::OLAF, Mood::Sad, "The outer wall is broken! Grit, hold the west ward!"),
        Line::say(co::GRIT, "Heh, leave it to me, Olaf! My guns reach the whole courtyard."),
    ])
}

fn colin_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::GRIT, Mood::Sad, "Blast it! They got past my guns. Colin, you're next!"),
        Line::say(co::COLIN, "Hee hee! Do you know what a wall costs? I just bought two more."),
    ])
}

fn sasha_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::COLIN, Mood::Sad, "My treasury ward! Sasha, hold the keep, quick!"),
        Line::say(co::SASHA, "Stand down, Colin. This is where Blue Moon ends its retreat."),
        Line::say(co::SASHA, "You came a long way to reach me. Let's see if it was worth it."),
    ])
}

// --- Gauntlet 12, Last Eclipse --------------------------------------------------------------------------------------------------------------------------

/// The HQs (five/gauntlet/spec/gauntlet_12.py): Sturm's (on the field), Von Bolt's, Aria's and Asuka's (hidden), the player's (army 5).
pub const ECLIPSE_STURM: (u8, u8) = (19, 13);
pub const ECLIPSE_VON_BOLT: (u8, u8) = (29, 6);
pub const ECLIPSE_ARIA: (u8, u8) = (29, 20);
pub const ECLIPSE_ASUKA: (u8, u8) = (39, 13);
pub const ECLIPSE_PLAYER: (u8, u8) = (3, 13);

/// Von Bolt's wave: armour, a Neo Tank and missiles in the north chamber (clear of the minicannon's lane), a Fighter and a Bomber.
const ECLIPSE_VON_BOLT_WAVE: [(u8, (u8, u8)); 19] = [
    (unit::MD_TANK, (32, 5)),
    (unit::MD_TANK, (30, 7)),
    (unit::MD_TANK, (25, 3)),
    (unit::NEOTANK, (32, 6)),
    (unit::TANK, (29, 5)),
    (unit::TANK, (30, 9)),
    (unit::ARTILLERY, (29, 10)),
    (unit::ARTILLERY, (29, 2)),
    (unit::MISSILES, (28, 10)),
    (unit::MISSILES, (27, 4)),
    (unit::INFANTRY, (25, 9)),
    (unit::INFANTRY, (25, 12)),
    (unit::INFANTRY, (31, 8)),
    (unit::INFANTRY, (25, 4)),
    (unit::MECH, (33, 5)),
    (unit::MECH, (28, 11)),
    (unit::ANTI_AIR, (27, 8)),
    (unit::FIGHTER, (30, 8)),
    (unit::BOMBER, (33, 12)),
];

/// Aria's wave: fast tanks and recons in the south chamber, artillery behind, copters.
const ARIA_WAVE: [(u8, (u8, u8)); 20] = [
    (unit::TANK, (25, 19)),
    (unit::TANK, (27, 19)),
    (unit::TANK, (28, 25)),
    (unit::TANK, (32, 15)),
    (unit::RECON, (28, 20)),
    (unit::RECON, (27, 18)),
    (unit::MD_TANK, (25, 17)),
    (unit::MD_TANK, (29, 17)),
    (unit::ARTILLERY, (33, 20)),
    (unit::ARTILLERY, (29, 20)),
    (unit::ROCKETS, (30, 15)),
    (unit::INFANTRY, (29, 18)),
    (unit::INFANTRY, (28, 16)),
    (unit::INFANTRY, (26, 14)),
    (unit::INFANTRY, (33, 21)),
    (unit::MECH, (30, 24)),
    (unit::MECH, (30, 20)),
    (unit::ANTI_AIR, (31, 22)),
    (unit::B_COPTER, (25, 23)),
    (unit::B_COPTER, (29, 23)),
];

/// Asuka's wave: Neo Tanks, Md Tanks and a Mega Tank in the citadel's yard, missiles, a Fighter and two Bombers.
const ASUKA_WAVE: [(u8, (u8, u8)); 23] = [
    (unit::NEOTANK, (40, 12)),
    (unit::NEOTANK, (38, 14)),
    (unit::NEOTANK, (43, 6)),
    (unit::MD_TANK, (41, 15)),
    (unit::MD_TANK, (42, 19)),
    (unit::MD_TANK, (40, 10)),
    (unit::MEGATANK, (40, 5)),
    (unit::ARTILLERY, (40, 9)),
    (unit::ARTILLERY, (43, 4)),
    (unit::MISSILES, (42, 17)),
    (unit::MISSILES, (39, 20)),
    (unit::INFANTRY, (39, 21)),
    (unit::INFANTRY, (35, 13)),
    (unit::INFANTRY, (39, 13)),
    (unit::INFANTRY, (41, 4)),
    (unit::MECH, (38, 6)),
    (unit::MECH, (41, 14)),
    (unit::MECH, (41, 21)),
    (unit::ANTI_AIR, (37, 21)),
    (unit::ANTI_AIR, (40, 14)),
    (unit::FIGHTER, (42, 14)),
    (unit::BOMBER, (42, 5)),
    (unit::BOMBER, (35, 11)),
];

/// Last Eclipse: Sturm, Von Bolt (Black Hole), Aria (Orange Star) and Asuka (Black Hole), one after another in a Black Hole stronghold of sealed chambers whose only gates are pipe seams (three armies of Black Hole's colour on three slots).
fn last_eclipse() -> MissionDef {
    let mut m = MissionDef::new("gauntlet_12", "Last Eclipse");
    m.objective = "Break through the seams: Sturm, Von Bolt, Aria, and Asuka in her citadel.";
    m.map = MapSrc::Built("gauntlet_12");
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)).team(1).funds(9000),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::VON_BOLT)).team(1).funds(0),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(crate::co_new::ARIA)).team(1).funds(0),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(crate::co_new::ASUKA)).team(1).funds(0),
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(20000),
    ];
    m.units = crate::bh_ai::orders(crate::bh_ai::built_units("gauntlet_12"), 5, crate::bh_ai::ATTACK, |u| u.ai == 1);
    m.look = 3; // the Wasteland look: a stronghold on blasted ground
    let lines = [
        Wire { army: 1, hq: ECLIPSE_STURM, zone: Rect::new(14, 0, 23, 25) },
        Wire { army: 2, hq: ECLIPSE_VON_BOLT, zone: Rect::new(25, 0, 33, 12) },
        Wire { army: 3, hq: ECLIPSE_ARIA, zone: Rect::new(25, 14, 33, 25) },
        Wire { army: 4, hq: ECLIPSE_ASUKA, zone: Rect::new(35, 0, 43, 25) },
    ];
    wire(
        &mut m,
        &lines,
        vec![
            arrival(&lines, 1, chest::<2, 15000, 1000>, &ECLIPSE_VON_BOLT_WAVE, eclipse_von_bolt_arrives()),
            arrival(&lines, 2, chest::<3, 20000, 1500>, &ARIA_WAVE, aria_arrives()),
            arrival(&lines, 3, chest::<4, 25000, 2000>, &ASUKA_WAVE, eclipse_asuka_arrives()),
        ],
    );
    m.intro = Scene::new(vec![
        Line::say(co::STURM, "Behold the stronghold! Black Hole's last wall, and I hold the door."),
        Line::say(co::STURM, "Three more walls behind me. You will not see the last."),
    ]);
    m.victory = Scene::new(vec![Line::say(crate::co_new::ASUKA, "The eclipse ends. I will write down how it was done.")]);
    m
}

fn eclipse_von_bolt_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::STURM, Mood::Sad, "The outer works are gone? Von Bolt, the chamber is yours!"),
        Line::say(co::VON_BOLT, "Sturm, you are loud and you are late. I shall finish this."),
        Line::say(co::VON_BOLT, "The machine has measured this chamber. Your end is on the page."),
    ])
}

fn aria_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(co::VON_BOLT, Mood::Sad, "The machine failed me. Aria, the south chamber is yours."),
        Line::say(crate::co_new::ARIA, "Orange Star keeps its promises, even in a place like this."),
        Line::say(crate::co_new::ARIA, "I am not here for Black Hole. I am here for you. Come on."),
    ])
}

fn eclipse_asuka_arrives() -> Scene {
    Scene::new(vec![
        Line::feel(crate::co_new::ARIA, Mood::Sad, "You made it through my line. Asuka waits at the end."),
        Line::say(crate::co_new::ASUKA, "Every wall has been recorded. The last page is the citadel."),
        Line::say(crate::co_new::ASUKA, "The eclipse is mine to end. Approach, and be read."),
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
    /// An enemy line wears a skin (Silver Nova's Caulder, Lili and Tabitha): the skin is on the battlefield already, so the player cannot wear it too (a skin sits on one colour). The enemy
    /// colour (an army of that colour wears the skin, whichever line) and the skin's index.
    pub enemy_skin: Option<(u8, usize)>,
    /// The titles of the maps the run moves to after the first (Iron Crown: Asuka's Keep); empty on a one-map run.
    pub stage_titles: &'static [&'static str],
    /// The enemy lines stage by stage, (CO, colour) in the order they come: stage one's, then each later stage's (`enemies` is these joined). The selector shows a later stage's on SELECT.
    pub stage_lines: Vec<Vec<(u8, u8)>>,
    /// The built map of each later stage (`stage_titles`' order; None for a stage whose map is not a built one: the selector then keeps the first map's picture).
    pub stage_maps: Vec<Option<&'static str>>,
    /// The AW2 map id of each later stage whose map is one of AW2's own ([`MapSrc::Aw2`], read from the ROM at run time: Conquest Run's); None for the others.
    pub stage_aw2: Vec<Option<u8>>,
    /// The run's enemy COs are drawn when it starts (Conquest Run): the selector and the army screen show no face for them.
    pub random_enemies: bool,
}

impl Entry {
    /// What the player may wear on this map: every army colour the enemies of no stage wear, and the skins when every stage leaves a colour to host them ([`free_colours_staged`]).
    pub fn free(&self) -> Vec<u8> {
        let mut v = free_colours_staged(&self.stages);
        if self.enemy_skin.is_some() {
            v.retain(|c| *c < crate::army_skin::SKIN);
        }
        v
    }

    /// An enemy's army code as the battle shows it: the skin an enemy line of this colour wears, else the colour itself.
    pub fn shown_colour(&self, colour: u8) -> u8 {
        match self.enemy_skin {
            Some((c, skin)) if c == colour => crate::army_skin::SKIN + skin as u8,
            _ => colour,
        }
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
                    enemy_skin: m.skin.and_then(|(army, skin)| Some((m.armies.get(army as usize - 1)?.colour, skin))),
                    stage_titles: m.stage_titles,
                    stage_lines: stages.clone(),
                    stage_maps: m.stages.iter().map(|s| if let MapSrc::Built(n) = &s.map { Some(*n) } else { None }).collect(),
                    stage_aw2: m.stages.iter().map(|s| if let MapSrc::Aw2 { id } = &s.map { Some(*id) } else { None }).collect(),
                    random_enemies: m.key == crate::conquest::KEY,
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
        let mut v = order_of(&entries().iter().map(|e| e.enemies.len()).collect::<Vec<_>>());
        // (Conquest Run is the first row of the list, whatever its count of enemies)
        if let Some(at) = v.iter().position(|&m| entries()[m].key == crate::conquest::KEY) {
            let m = v.remove(at);
            v.insert(0, m);
        }
        v
    })
}

/// The selector's order for maps with these enemy counts (by mission index): the missions by count, fewest first, ties in the definition's order.
pub fn order_of(counts: &[usize]) -> Vec<usize> {
    let mut v: Vec<usize> = (0..counts.len()).collect();
    v.sort_by_key(|&m| (counts[m], m));
    v
}

/// A map's place in the selector's list (0 the top): the map-table id the list shows it by is the first one plus this.
pub fn rank_of(mission: usize) -> usize {
    order().iter().position(|&m| m == mission).unwrap_or(mission)
}

/// The song of a map's opening scene, by mission key (a role of `campaign_music::NAMED`). A map not listed gets [`DEFAULT_OPENING`], so a new map is never silent; add a row to give it its own.
/// Every other scene (a line falling and the next CO arriving, a day scene, the victory) plays the CO's theme who speaks last in it: the arriving CO's own song.
pub const OPENING: &[(&str, &str)] = &[
    ("gauntlet_01", "enemy2"),   // Cinder Sea: Drake's waters, the grumbling volcano
    ("gauntlet_02", "ally1"),    // Iron Crown: Blue Moon's council on the river
    ("gauntlet_03", "red"),      // Dustwind Basin: Koal's mesa
    ("gauntlet_04", "enemy2"),   // Brass Canal: Sasha's toll
    ("gauntlet_05", "hagevolt"), // Granite Spine: Von Bolt's mountain
    ("gauntlet_06", "ally2"),    // Harvest Run: Orange Star at home
    ("gauntlet_07", "enemy1"),   // Chrome Meridian: Flak's noise
    ("gauntlet_08", "blue"),     // Tidewater Atoll: Eagle's sky
    ("gauntlet_09", "ally2"),    // Silverpine Ford: Hachi's tables
    ("gauntlet_10", "red"),      // Neon Row: Colin's street
    ("gauntlet_11", "ally1"),    // Blue Bastion: Blue Moon's walls
    ("gauntlet_12", "sturm"),    // Last Eclipse: Sturm's door
];
pub const DEFAULT_OPENING: &str = "enemy1";

/// The song of a scene that has none: the theme of the CO speaking last in it (a trooper or narrator: `fallback`).
fn scene_song(sc: &Scene, fallback: Track) -> Track {
    match sc.lines.last().map(|l| l.who) {
        Some(Speaker::Co(c, _)) => Track::Co(c),
        _ => fallback,
    }
}

/// Gives every scene of the map music (the dialogue is never silent): the opening its role from [`OPENING`], every other scene (the triggers', the victory) its last speaker's theme.
fn add_music(m: &mut MissionDef) {
    let role = OPENING.iter().find(|o| o.0 == m.key).map_or(DEFAULT_OPENING, |o| o.1);
    let opening = crate::campaign_music::named(role).unwrap_or(Track::Aw2(411));
    if m.intro.song.is_none() {
        m.intro.song = Some(opening);
    }
    if m.victory.song.is_none() {
        m.victory.song = Some(scene_song(&m.victory, opening));
    }
    for t in m.triggers.iter_mut() {
        for a in t.then.iter_mut() {
            if let Action::Scene(sc) = a {
                if sc.song.is_none() {
                    sc.song = Some(scene_song(sc, opening));
                }
            }
        }
    }
}

// --- Par days: the speed score (docs/dev/gauntlet-mode.md "Scoring") -------------------------------------------------------------------------------------------------

/// Days a well-played run needs for each enemy line (AW2's Speed is 100 up to the map's par day, then falls to 0 at four times the par: a Gauntlet's par is a run's days, not one line's).
pub const PAR_PER_LINE: u16 = 12;
/// Maps whose par is not [`PAR_PER_LINE`] times their lines: the two largest, whose walls and distances cost more days a line (the data: add a map here to give it its own par).
pub const PAR_OVERRIDES: &[(&str, u16)] = &[("gauntlet_11", 52), ("gauntlet_12", 52), (crate::conquest::KEY, crate::conquest::PAR_PER_MAP * crate::conquest::STAGES as u16)];

/// The enemy lines a mission fights: every CO the map fixes, the first stage's and each later stage's (Iron Crown's four and Asuka: five). The same count the selector lists as enemies.
pub fn line_count(m: &MissionDef) -> usize {
    let fixed = |armies: &[ArmyDef]| armies.iter().filter(|a| matches!(a.co, CoSpec::Fixed(_))).count();
    fixed(&m.armies) + m.stages.iter().map(|s| fixed(&s.armies)).sum::<usize>()
}

/// The lines of the Gauntlet map at mission index `mission` (at least 1).
pub fn lines_of(mission: usize) -> usize {
    entries().get(mission).map_or(1, |e| e.enemies.len()).max(1)
}

/// A mission's par days (the map header's, which AW2's Speed reads): its override, else [`PAR_PER_LINE`] days for each line.
pub fn par_days(m: &MissionDef) -> u16 {
    PAR_OVERRIDES.iter().find(|o| o.0 == m.key).map_or(PAR_PER_LINE * line_count(m) as u16, |o| o.1)
}

/// The Gauntlet mode's maps as a campaign (its missions; no prologue, staff roll or world map: the mode starts a map from Select Mode).
pub fn def() -> CampaignDef {
    let mut missions = vec![cinder_sea(), iron_crown(), dustwind_basin(), brass_canal(), granite_spine(), harvest_run(), chrome_meridian(), tidewater_atoll(), silverpine_ford(), neon_row(), blue_bastion(), last_eclipse()];
    // (Conquest Run is always the last mission, whatever the number of maps: a new map is added to the list above and the run's index follows; the selector lists it first, `order`)
    missions.push(crate::conquest::mission());
    missions.iter_mut().for_each(crate::bh_ai::spawn_orders);
    missions.iter_mut().for_each(add_music);
    missions.iter_mut().for_each(|m| m.rank_days = par_days(m));
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
    fn every_scene_has_music() {
        for m in &def().missions {
            assert!(m.intro.song.is_some() && m.victory.song.is_some(), "{}: opening and victory", m.key);
            for t in &m.triggers {
                for a in &t.then {
                    if let Action::Scene(sc) = a {
                        assert!(sc.song.is_some(), "{}: a trigger's scene is silent", m.key);
                    }
                }
            }
        }
        for o in OPENING {
            assert!(crate::campaign_music::named(o.1).is_some(), "{}: unknown role {}", o.0, o.1);
        }
        assert!(crate::campaign_music::named(DEFAULT_OPENING).is_some());
    }

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
            "gauntlet_08" => include_str!("../five/gauntlet/gauntlet_08.txt"),
            "gauntlet_09" => include_str!("../five/gauntlet/gauntlet_09.txt"),
            "gauntlet_10" => include_str!("../five/gauntlet/gauntlet_10.txt"),
            "gauntlet_11" => include_str!("../five/gauntlet/gauntlet_11.txt"),
            "gauntlet_12" => include_str!("../five/gauntlet/gauntlet_12.txt"),
            other => panic!("no text map for {other}: add it to text_of"),
        }
    }

    #[test]
    fn every_map_is_wired_as_a_gauntlet_by_the_rout_rule() {
        for m in def().missions.iter().filter(|m| m.key != crate::conquest::KEY) {
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
        let skip = ["gauntlet_01", "gauntlet_08", crate::conquest::KEY]; // (Cinder Sea and Tidewater Atoll are sea maps: their waves stand on water and shore; Conquest Run's maps are AW2's own, read from the ROM, with no waves)
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
        // (Conquest Run is the first row whatever its count; the maps follow, fewest enemies first)
        assert_eq!(e[order[0]].key, crate::conquest::KEY);
        let counts: Vec<usize> = order.iter().skip(1).map(|&m| e[m].enemies.len()).collect();
        assert!(counts.windows(2).all(|w| w[0] <= w[1]), "fewest enemies first: {counts:?}");
        // ties keep the definition's order (the older, easier map first), a permutation of the missions, and rank_of is its inverse
        for w in order.windows(2).skip(1) {
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
        assert!(e[order[1]].enemies.len() == 2);
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
        assert!(c.enemy_skin.is_some());
        // (the army screen shows the three lines as the battle does: in the skin, Black Hole's own colour for Flak)
        assert_eq!(c.enemies.iter().map(|x| c.shown_colour(x.1)).collect::<Vec<_>>(), vec![colour::BLACK_HOLE, crate::army_skin::SKIN, crate::army_skin::SKIN, crate::army_skin::SKIN]);
        assert_eq!(c.enemies.iter().map(|x| x.1).collect::<Vec<_>>(), vec![colour::BLACK_HOLE, CHROME_HOST, CHROME_HOST, CHROME_HOST]);
        assert_eq!(c.free(), crate::army_skin::order().into_iter().filter(|c| *c < crate::army_skin::SKIN && *c != colour::BLACK_HOLE && *c != CHROME_HOST).collect::<Vec<_>>());
        let m = &def().missions[c.mission];
        assert_eq!(m.skin, Some((CHROME_SKIN_ARMY, 0)));
        // the skin's lines are the armies that wear the host colour, and Black Hole's line does not
        assert_eq!(m.armies[0].colour, colour::BLACK_HOLE);
        assert!(m.armies[1..4].iter().all(|a| a.colour == m.armies[CHROME_SKIN_ARMY as usize - 1].colour));
        // the other maps' skins are the player's choice only
        assert!(by("gauntlet_01").enemy_skin.is_none() && by("gauntlet_02").enemy_skin.is_none());
    }

    /// Every enemy CO appears on one map only, except the COs the owner named twice: Last Eclipse's Von Bolt and Asuka (Granite Spine's Von Bolt and Iron Crown's stage two Asuka), and Blue Bastion's Grit, Colin and Sasha (Iron Crown's Grit and Brass Canal's Sasha;
    /// Neon Row's Colin). Nothing else may repeat across the Gauntlet's maps.
    #[test]
    fn no_two_maps_share_an_enemy_co_but_the_named_exceptions() {
        use std::collections::BTreeMap;
        let mut seen: BTreeMap<u8, Vec<&str>> = BTreeMap::new();
        // (Conquest Run's enemies are drawn when a run starts: its stand-in CO is not a line-up)
        for e in entries().iter().filter(|e| !e.random_enemies) {
            let mut cos: Vec<u8> = e.enemies.iter().map(|x| x.0).collect();
            // (a CO appears once on a map, except Harvest Run's and Blue Bastion's one-army lines, which are four different COs)
            cos.sort();
            let n = cos.len();
            cos.dedup();
            assert_eq!(cos.len(), n, "{}: a CO fights twice on one map", e.key);
            for c in cos {
                seen.entry(c).or_default().push(e.key);
            }
        }
        let allowed: &[(u8, &[&str])] = &[
            (co::VON_BOLT, &["gauntlet_05", "gauntlet_12"]),
            (crate::co_new::ASUKA, &["gauntlet_02", "gauntlet_12"]),
            (co::GRIT, &["gauntlet_02", "gauntlet_11"]),
            (co::SASHA, &["gauntlet_04", "gauntlet_11"]),
            (co::COLIN, &["gauntlet_10", "gauntlet_11"]),
        ];
        for (c, maps) in &seen {
            if maps.len() > 1 {
                let ok = allowed.iter().find(|a| a.0 == *c).is_some_and(|a| a.1 == maps.as_slice());
                assert!(ok, "CO {c} is on {maps:?}: only the named repeats are allowed");
            }
        }
    }

    #[test]
    fn par_days_grow_with_the_lines_of_the_run() {
        let d = def();
        for (m, e) in d.missions.iter().zip(entries()) {
            assert_eq!(line_count(m), e.enemies.len(), "{}: the lines are the selector's enemies", m.key);
            assert_eq!(lines_of(e.mission), e.enemies.len());
            assert_eq!(m.rank_days, par_days(m), "{}: the header's par is the Gauntlet's", m.key);
            let natural = PAR_PER_LINE * e.enemies.len() as u16;
            match PAR_OVERRIDES.iter().find(|o| o.0 == m.key) {
                // (Conquest Run's par is a day budget of its own: eight days a map)
                Some(o) if m.key == crate::conquest::KEY => assert_eq!(o.1, crate::conquest::PAR_PER_MAP * crate::conquest::STAGES as u16),
                Some(o) => assert!(o.1 >= natural, "{}: an override only gives more days", m.key),
                None => assert_eq!(m.rank_days, natural, "{}", m.key),
            }
        }
        let par = |k: &str| d.missions.iter().find(|m| m.key == k).unwrap().rank_days;
        assert_eq!((par("gauntlet_03"), par("gauntlet_01"), par("gauntlet_06"), par("gauntlet_02")), (24, 36, 48, 60), "two, three, four and (Iron Crown) five lines");
        assert!(par("gauntlet_11") > par("gauntlet_06") && par("gauntlet_12") > par("gauntlet_06"));
        // AW2's Speed: 100 up to par, 0 at four times par: a run of every map's par days is a perfect Speed
        assert!(d.missions.iter().all(|m| m.rank_days >= 24), "no map got stricter than before: the old pars were 22..44");
    }

    #[test]
    fn the_five_added_maps_have_the_owners_lines() {
        let e = entries();
        let by = |k: &str| e.iter().find(|x| x.key == k).unwrap();
        let cos = |k: &str| by(k).enemies.iter().map(|x| x.0).collect::<Vec<_>>();
        let cols = |k: &str| by(k).enemies.iter().map(|x| x.1).collect::<Vec<_>>();
        assert_eq!(by("gauntlet_08").title, "Tidewater Atoll");
        assert_eq!((cos("gauntlet_08"), cols("gauntlet_08")), (vec![co::EAGLE, co::ADDER], vec![colour::GREEN_EARTH, colour::BLACK_HOLE]));
        assert_eq!(by("gauntlet_09").title, "Silverpine Ford");
        assert_eq!(cos("gauntlet_09"), vec![co::HACHI, co::SONJA]);
        assert_eq!(by("gauntlet_10").title, "Neon Row");
        assert_eq!((cos("gauntlet_10"), cols("gauntlet_10")), (vec![co::COLIN, co::KINDLE, co::JUGGER], vec![colour::BLUE_MOON, colour::BLACK_HOLE, colour::BLACK_HOLE]));
        assert_eq!(by("gauntlet_11").title, "Blue Bastion");
        assert_eq!(cos("gauntlet_11"), vec![co::OLAF, co::GRIT, co::COLIN, co::SASHA]);
        assert!(cols("gauntlet_11").iter().all(|&c| c == colour::BLUE_MOON));
        assert!(!by("gauntlet_11").free().contains(&colour::BLUE_MOON), "the player never wears Blue Moon on the Bastion");
        // Last Eclipse: Sturm, Von Bolt, Aria, Asuka; three Black Hole lines and Aria's Orange Star; the player wears neither colour
        assert_eq!(by("gauntlet_12").title, "Last Eclipse");
        assert_eq!(cos("gauntlet_12"), vec![co::STURM, co::VON_BOLT, crate::co_new::ARIA, crate::co_new::ASUKA]);
        assert_eq!(cols("gauntlet_12"), vec![colour::BLACK_HOLE, colour::BLACK_HOLE, colour::ORANGE_STAR, colour::BLACK_HOLE]);
        let f = by("gauntlet_12").free();
        assert!(!f.contains(&colour::BLACK_HOLE) && !f.contains(&colour::ORANGE_STAR) && f.contains(&colour::BLUE_MOON));
        // twelve maps and Conquest Run, listed first; then the two-enemy maps first and the four-enemy maps last
        assert_eq!(e.len(), 13);
        assert_eq!(e[order()[0]].key, crate::conquest::KEY);
        let counts: Vec<usize> = order().iter().skip(1).map(|&m| e[m].enemies.len()).collect();
        assert_eq!(counts.iter().filter(|&&c| c == 2).count(), 4);
        assert!(counts.windows(2).all(|w| w[0] <= w[1]));
        assert!(counts[counts.len() - 4..].iter().all(|&c| c >= 4), "{counts:?}");
    }
}
