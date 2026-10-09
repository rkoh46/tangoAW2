//! Act 5: Orange Star (the finale's two missions so far: M29 The Orange Gate and
//! M30 Nell's Stand). Its missions are `MissionDef`s (docs/AW2.md "BH Campaign":
//! adding a mission); this file is the act's alone, so builders can work on acts
//! in parallel. A mission names what it needs by key (`Needs::All(vec!["bh28"])`),
//! not by index.
//!
//! The maps are `five/bh/bh29.txt` and `bh30.txt` (built by `five/bhmap.py` into
//! `bh_map_data.rs`). The design is the bible's (docs/BH_CAMPAIGN.md, branch
//! bh-design: 3.2b the inventions, 4.6 and 4.7 the scenes, the mission sheets).
//!
//! **Roles of Orange Star's units** (the AI byte, [`UnitDef::ai`]: 0 stays and still fires, 1 goes for
//! the enemy HQ, 3 for the enemy's properties, 4 at the nearest enemy units). The army pushes: its
//! foot soldiers take the camp's properties (3), its armour and air strike at the nearest enemy (4),
//! its Megatanks and, in M29, Neotanks drive for the HQ (1). A deliberate minority holds (0): the
//! guns behind the walls (Artillery, Missiles, Anti-Air: they fire at whatever crosses but do not walk
//! into the moat's kill zone), the infantry on the wall tops beside the gates, and the keep's guard
//! (M30: a Neotank and two Infantry in the Centre Bailey; M29: the Gate's foot guard).
//! What the CPU builds, and the stage-two reserves (Andy's wall), get the CPU's own roles.

// (the builders' imports: each act uses what it needs)
#![allow(unused_imports)]

use mgba::core::Core;

use crate::bh_campaign::{region, roster};
use crate::custom_campaign::{co, colour, unit, *};

// --- Writing helpers ---------------------------------------------------------------

fn say(c: u8, text: &'static str) -> Line {
    Line::say(c, text)
}

fn happy(c: u8, text: &'static str) -> Line {
    Line::feel(c, Mood::Happy, text)
}

fn sad(c: u8, text: &'static str) -> Line {
    Line::feel(c, Mood::Sad, text)
}

/// Narration and the soldiers: the Black Hole trooper's face.
fn troop(text: &'static str) -> Line {
    Line::soldier(colour::BLACK_HOLE, text)
}

/// A line any of the player's COs may be ([CO]): one row for each, shown for its own player.
fn anyone(text: &'static str, cos: &[u8]) -> Vec<Line> {
    cos.iter().map(|&c| say(c, text).only(c)).collect()
}

/// "On day `d`, at the start of the player's turn": fires once, on that day.
fn on_day(d: u16, cond: Option<Cond>, then: Vec<Action>) -> Trigger {
    let day = Cond::EveryDays { n: 1000, from: d };
    let cond = match cond {
        Some(c) => Cond::All(vec![day, c]),
        None => day,
    };
    Trigger::new(When::TurnStart, cond, then).repeating()
}

/// After each action, while the condition holds.
fn after(cond: Cond, then: Vec<Action>) -> Trigger {
    Trigger::new(When::AfterAction, cond, then).repeating()
}

fn beaten(enemy: u8, hq: (u8, u8)) -> Cond {
    Cond::Any(vec![Cond::ArmyUnitsAtMost { army: enemy, n: 1 }, Cond::OwnerAt { x: hq.0, y: hq.1, army: 1 }])
}

/// An army's CO meter set to `pct` of its first power's bar (AW2's units: `cop_cost`).
fn meter(core: &mut Core, army: u32, pct: u32) {
    let p = crate::tag::player(core, army);
    let co = crate::tag::army_co_of(core, army);
    let uses = core.raw_read_8(p + 0x25, -1);
    let full = crate::tag::cop_cost(core, co, uses);
    core.raw_write_32(p + 0x20, -1, full * pct / 100);
}

/// An army's CO meter full to its Super Power (the computer uses a power it can pay for).
fn charge_super(core: &mut Core, army: u32) {
    let p = crate::tag::player(core, army);
    let co = crate::tag::army_co_of(core, army);
    let uses = core.raw_read_8(p + 0x25, -1);
    let full = crate::tag::scop_cost(core, co, uses);
    core.raw_write_32(p + 0x20, -1, full);
}

/// An army's CO meter full to its first power only (a COP).
fn charge_cop(core: &mut Core, army: u32) {
    meter(core, army, 100);
}

/// Mission variables: bytes of EWRAM the game never touches (the DS Campaign's block ends at
/// 0x0203FD5F; cpu_tactics uses 0x0203FD60..0x0203FD79).
const VAR_FALL_DAY: u32 = 0x0203_FD7C;
const VAR_DUEL_DONE: u32 = 0x0203_FD7D;

/// The units of a built map, with the AI role `role(army, kind, x, y)` gives each (see the module doc).
fn deploy(name: &str, role: fn(u8, u8, u8, u8) -> u8) -> Vec<UnitDef> {
    let Some(m) = crate::bh_map_data::MAPS.iter().find(|m| m.name == name) else { return Vec::new() };
    m.units
        .iter()
        .map(|u| {
            let mut d = UnitDef::new(u.army, u.kind, u.x, u.y).hp(u.hp);
            d.ai = role(u.army, u.kind, u.x, u.y);
            d
        })
        .collect()
}

// --- M29 The Orange Gate -----------------------------------------------------------

/// Factory table F29 (docs/BH_CAMPAIGN.md): per day the three doors' units.
const F29: [(u8, [u8; 3]); 10] = [
    (2, [unit::TANK, unit::TANK, unit::TANK]),
    (3, [0, unit::MD_TANK, 0]),
    (4, [unit::NEOTANK, 0, unit::NEOTANK]),
    (6, [0, unit::MEGATANK, 0]),
    (7, [unit::MD_TANK, 0, unit::MD_TANK]),
    (9, [unit::MISSILES, unit::ROCKETS, unit::MISSILES]),
    (11, [unit::NEOTANK, 0, unit::NEOTANK]),
    (13, [0, unit::MEGATANK, unit::OOZIUM]),
    (15, [unit::NEOTANK, unit::NEOTANK, 0]),
    (18, [unit::ROCKETS, unit::NEOTANK, unit::ANTI_AIR]),
];

fn role29(army: u8, kind: u8, x: u8, y: u8) -> u8 {
    if army != 2 {
        return 0;
    }
    // The Gate's foot guard holds the gateway; guns and Anti-Air stay behind the wall.
    let gate_guard = kind == unit::INFANTRY && matches!((x, y), (16, 17) | (17, 17) | (18, 17) | (17, 21));
    match kind {
        unit::ARTILLERY | unit::MISSILES | unit::ANTI_AIR => 0,
        unit::INFANTRY if gate_guard => 0,
        unit::INFANTRY | unit::MECH => 3,
        unit::NEOTANK | unit::MEGATANK => 1,
        _ => 4,
    }
}

fn nell_power_day5(core: &mut Core) {
    charge_cop(core, 2);
}

fn charge_army2_50(core: &mut Core) {
    meter(core, 2, 50);
}

fn bh29() -> MissionDef {
    let mut m = MissionDef::new("bh29", "The Orange Gate");
    m.objective = "Take the Orange Gate and capture Orange Star's HQ.";
    m.map = MapSrc::Built("bh29");
    m.units = deploy("bh29", role29);
    m.factory = F29.to_vec();
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::Pick).funds(14000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Pair(co::NELL, co::MAX)).funds(60000),
    ];
    m.day_limit = 32;
    m.rank_days = 20;
    let mut intro = vec![
        troop("The Orange Gate. Walls, a canal, a woman on the wall."),
        say(co::NELL, "This is the Orange Gate. I would rather you turned back."),
        say(co::NELL, "You will not. I know. So I will ask you to be careful."),
        say(co::STURM, "Kneel, Nell. This gate is mine by nightfall."),
        say(co::NELL, "It is Orange Star's, dear. And I am standing on it."),
        say(co::MAX, "Nell! I'm right here! Nobody touches you!"),
        say(co::SAMI, "Max! The wall's mine! You are the hammer! Move!"),
        say(co::MAX, "Whatever! Charge!"),
        say(co::NELL, "Boys. Mind the canal. And eat something first."),
        say(co::HAWKE, "Nell herself, at the gate. She is counting us."),
        say(co::HAWKE, "Her castle lies behind. This is only her first line."),
        say(co::VON_BOLT, "She has a castle? With a vault? Kehh... does it?"),
        say(co::STURM, "Take the gate. Then the castle. Then her."),
        say(co::HAWKE, "And mind the beams. The Deathray and the Laser do not ask whose side you are on."),
        say(co::FLAK, "Big man! Flak wants the big man!").only(co::FLAK),
        say(co::MAX, "Hah! Come on, big man!").only(co::FLAK),
        say(co::CLONE_ANDY, "Andy's friends. They know me. They won't talk to me.").only(co::CLONE_ANDY),
        say(co::SAMI, "...That's not Andy.").only(co::CLONE_ANDY),
        say(co::MAX, "What did they do to him?").only(co::CLONE_ANDY),
        say(co::CLONE_ANDY, "Nothing. I chose.").only(co::CLONE_ANDY),
        say(co::NELL, "Oh, dear one. You have his eyes. Eat something, too.").only(co::CLONE_ANDY),
    ];
    // (Crumb's lines join when the campaign has him: `@IF CRUMB`.)
    m.intro = Scene::new(std::mem::take(&mut intro));
    m.victory = Scene::new(vec![
        say(co::NELL, "The Gate holds no longer. Max, Sami: fall back. Now."),
        say(co::MAX, "Nell! I'm staying with you!"),
        say(co::SAMI, "Max. We obey. Come on."),
        say(co::NELL, "Sturm. You took the gate. You have not taken my castle."),
        say(co::STURM, "I will have the castle. And you."),
        say(co::NELL, "Then come to it, and meet what I have kept for you."),
        say(co::NELL, "Whole streets sleep behind those walls. I will not move."),
        say(co::MAX, "Sturm! Don't you lay a hand on her!"),
        say(co::STURM, "I promise nothing. Her castle is mine tomorrow."),
        say(co::HAWKE, "She withdraws on purpose. She is drawing us in."),
        say(co::HAWKE, "Everything she has is in that castle. All of it."),
        say(co::VON_BOLT, "All of it? Kehh... all of it!"),
    ]);
    m.after = Scene::new(vec![
        say(co::NELL, "To the black army: please eat and sleep."),
        say(co::NELL, "Tomorrow is hard for everyone. Mine and yours."),
        say(co::STURM, "Turn that off."),
        say(co::STURM, "...Leave it on."),
    ]);
    let wave: Vec<UnitDef> = [(21, 22), (22, 22), (23, 22), (24, 22), (25, 22), (26, 22)]
        .iter()
        .map(|&(x, y)| {
            let mut u = UnitDef::new(2, unit::INFANTRY, x, y);
            u.ai = 3;
            u
        })
        .collect();
    m.triggers = vec![
        // Nell's meter starts at 50%.
        on_day(1, None, vec![Action::Custom(charge_army2_50)]),
        // Day 5: her first power lands on the Gate bridge.
        on_day(
            5,
            None,
            vec![Action::Custom(nell_power_day5), Action::Scene(Scene::new(vec![say(co::NELL, "I was born lucky. I'll spend it on the bridge today.")]))],
        ),
        // Day 8: Max's turn to hit.
        on_day(8, None, vec![Action::Custom(nell_power_day5), Action::Scene(Scene::new(vec![say(co::MAX, "Tanks! Everyone! Tanks!")]))]),
        // Day 10: Sami's infantry wave.
        on_day(10, None, vec![Action::Scene(Scene::new(vec![say(co::SAMI, "Infantry, forward! The gate stays ours! Move out!")])), Action::Spawn(wave)]),
        on_day(16, None, vec![Action::Scene(Scene::new(vec![say(co::SAMI, "Orange Star! For Nell!")]))]),
        after(beaten(2, (29, 25)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh28"]);
    m.flag = region::ORANGE_STAR[4];
    m.stars = 3;
    m
}

// --- M30 Nell's Stand --------------------------------------------------------------

fn role30(army: u8, kind: u8, x: u8, y: u8) -> u8 {
    if army != 2 {
        return 0;
    }
    // The minority that holds: the infantry on the wall tops beside the three gates and two in the Centre
    // Bailey (the keep's guard), a Neotank before the Inner gate, and the guns and Anti-Air.
    let wall_top = kind == unit::INFANTRY && y == 11;
    let keep_guard = (kind == unit::INFANTRY && matches!((x, y), (13, 8) | (23, 8))) || (kind == unit::NEOTANK && (x, y) == (16, 8));
    match kind {
        unit::ARTILLERY | unit::MISSILES | unit::ANTI_AIR => 0,
        _ if wall_top || keep_guard => 0,
        // the heavy armour waits (role 0) from day 7 on ([`release`]): the first wave is foot soldiers Tanks,
        // Rockets and aircraft
        unit::MD_TANK | unit::NEOTANK | unit::MEGATANK => 0,
        unit::INFANTRY | unit::MECH => 3,
        _ => 4,
    }
}

/// Nell's heavy armour leaves its posts in turn (the roles are in the units' records, +0x0B): Md Tanks on day 7, Neotanks on
/// day 9, Megatanks on day 11 (each for the nearest enemy; the Megatanks for the HQ).
fn release(core: &mut Core, kind: u8, role: u8) {
    for (a, k, _, _) in units_of(core, 2) {
        if k == kind {
            core.raw_write_8(a + 0x0B, -1, role);
        }
    }
}

fn release_md_tanks(core: &mut Core) {
    release(core, unit::MD_TANK, 4);
}

fn release_neotanks(core: &mut Core) {
    release(core, unit::NEOTANK, 4);
}

fn release_megatanks(core: &mut Core) {
    release(core, unit::MEGATANK, 1);
}

/// Orange Star's treasury is capped each morning (its income is cut to what the CPU may spend: about two Tanks' worth a base).
const TREASURY_CAP: u32 = 6000;
fn cap_treasury(core: &mut Core) {
    let p = crate::tag::player(core, 2);
    if core.raw_read_32(p, -1) > TREASURY_CAP {
        core.raw_write_32(p, -1, TREASURY_CAP);
    }
}

/// Nell's power days are the script's: her meter is held under her first power's bar except on days 5, 9 and 15, so
/// the computer cannot use one earlier on what it charges in a fight.
fn clamp_nell(core: &mut Core) {
    if !nell_leads(core) || matches!(day(core), 5 | 9 | 15) {
        return;
    }
    let p = crate::tag::player(core, 2);
    let co = crate::tag::army_co_of(core, 2);
    let uses = core.raw_read_8(p + 0x25, -1);
    let top = crate::tag::cop_cost(core, co, uses).saturating_sub(1);
    if core.raw_read_32(p + 0x20, -1) > top {
        core.raw_write_32(p + 0x20, -1, top);
    }
}

fn always(_: &mut Core) -> bool {
    true
}

fn clone_in_pair(core: &mut Core) -> bool {
    crate::tag::army_co_of(core, 1) == co::CLONE_ANDY || crate::tag::partner(core, 1) == Some(co::CLONE_ANDY)
}

fn no_clone_in_pair(core: &mut Core) -> bool {
    !clone_in_pair(core)
}

fn nell_leads(core: &mut Core) -> bool {
    crate::tag::army_co_of(core, 2) == co::NELL
}

fn reset_vars(core: &mut Core) {
    core.raw_write_8(VAR_FALL_DAY, -1, 0);
    core.raw_write_8(VAR_DUEL_DONE, -1, 0);
}

fn charge_nell_60(core: &mut Core) {
    reset_vars(core);
    meter(core, 2, 20);
}

fn nell_cop(core: &mut Core) {
    charge_cop(core, 2);
}

fn nell_super(core: &mut Core) {
    charge_super(core, 2);
}

fn nell_super_again(core: &mut Core) {
    if nell_leads(core) {
        charge_super(core, 2);
    }
}

fn duel_done(core: &mut Core) {
    core.raw_write_8(VAR_DUEL_DONE, -1, 1);
}

fn record_fall(core: &mut Core) {
    core.raw_write_8(VAR_FALL_DAY, -1, day(core).min(255) as u8);
}

/// Stage two has begun (the Great Hall fell) and `n` days have passed since.
fn stage2_after(core: &mut Core, n: u16) -> bool {
    let fall = core.raw_read_8(VAR_FALL_DAY, -1) as u16;
    fall != 0 && day(core) >= fall + n
}

fn s2_first_turn(core: &mut Core) -> bool {
    stage2_after(core, 1)
}

fn duel_due_in_stage2(core: &mut Core) -> bool {
    core.raw_read_8(VAR_DUEL_DONE, -1) == 0 && stage2_after(core, 2)
}

fn duel_due_in_stage2_clone(core: &mut Core) -> bool {
    duel_due_in_stage2(core) && clone_in_pair(core)
}

fn duel_due_in_stage2_plain(core: &mut Core) -> bool {
    duel_due_in_stage2(core) && !clone_in_pair(core)
}

fn duel_not_done(core: &mut Core) -> bool {
    core.raw_read_8(VAR_DUEL_DONE, -1) == 0
}

fn duel_clone_lines() -> Vec<Line> {
    vec![
        say(co::ANDY, "You. Standing there with my face on."),
        say(co::CLONE_ANDY, "Andy. I didn't choose the face."),
        say(co::ANDY, "I know. I know! But you chose the side."),
        say(co::CLONE_ANDY, "And you chose yours. We are both right. Awful, that."),
        say(co::ANDY, "...A duel. Right now. Your best against mine."),
        say(co::CLONE_ANDY, "Okay. Wrench or fists?"),
        happy(co::ANDY, "Wrench!"),
        troop("Two wrenches clash. Neither gives an inch."),
        sad(co::ANDY, "...Same grip. Same swing."),
        say(co::CLONE_ANDY, "Same joke after it."),
        say(co::ANDY, "Tell me it was never a joke."),
        say(co::CLONE_ANDY, "It was never a joke."),
        say(co::ANDY, "Then I will keep fighting you. Fair?"),
        happy(co::CLONE_ANDY, "Fair. And Andy? I am glad it was you."),
    ]
}

fn duel_plain_lines() -> Vec<Line> {
    vec![
        say(co::ANDY, "Hey, Black Hole! I'm not done! I never am!"),
        say(co::ANDY, "Orange Star is being asked to leave home. Not today."),
        say(co::ANDY, "Nell is behind me. I will patch every hole you make!"),
        sad(co::ANDY, "...I just wish someone I knew was on my side."),
    ]
}

/// Andy's wall on the platform and the reserves, all of the army that was Nell's: the Rail Yard (the
/// second HQ) is now the one that matters. They hold their places (role 0: the platform is behind them).
fn rail_yard_reserves() -> Vec<UnitDef> {
    let mut v = Vec::new();
    let mut add = |kind: u8, cells: &[(u8, u8)]| {
        for &(x, y) in cells {
            v.push(UnitDef::new(2, kind, x, y));
        }
    };
    // Andy's wall: 4 Inf, 2 Md Tank, 2 Anti-Air
    add(unit::INFANTRY, &[(32, 5), (32, 7), (34, 5), (34, 7)]);
    add(unit::MD_TANK, &[(33, 5), (33, 7)]);
    add(unit::ANTI_AIR, &[(32, 4), (34, 4)]);
    // The reserves (as many as the army's cap allows): 2 Neotank, 2 Md Tank, 2 Rockets, 2 Inf, 2 Fighter
    add(unit::NEOTANK, &[(32, 6), (34, 6)]);
    add(unit::MD_TANK, &[(32, 8), (34, 8)]);
    add(unit::ROCKETS, &[(35, 5), (35, 7)]);
    add(unit::INFANTRY, &[(35, 4), (35, 8)]);
    add(unit::FIGHTER, &[(35, 6), (34, 2)]);
    v
}

fn bh30() -> MissionDef {
    let mut m = MissionDef::new("bh30", "Nell's Stand");
    m.objective = "Take the Great Hall, then the Rail Yard.";
    m.map = MapSrc::Built("bh30");
    m.units = deploy("bh30", role30);
    // One Orange Star army throughout: when the Great Hall falls its HQ is the Rail Yard (the map's second HQ
    // tile) and Andy leads it (`Action::TakeOver`); `held_hq` makes the Great Hall's capture defeat nobody.
    m.held_hq = Some((18, 3));
    m.armies = vec![
        ArmyDef::new(colour::BLACK_HOLE, CoSpec::PickPair).funds(20000),
        ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::NELL)).funds(20000),
    ];
    m.day_limit = 34;
    m.rank_days = 24;
    let pair = [co::STURM, co::VON_BOLT, co::HAWKE];
    m.intro = Scene::new(vec![
        troop("The Orange Castle. The last gate. The last light."),
        say(co::NELL, "Black Hole. You took the Gate. I did not stop you."),
        say(co::NELL, "You took four nations. You took them kindly. Mostly."),
        say(co::NELL, "I will not hate you. I cannot. But I will stop you."),
        say(co::NELL, "Behind me are ten thousand people. I will hold."),
        say(co::STURM, "You hold with a wall."),
        say(co::NELL, "A wall is what a big sister is, when it counts."),
        say(co::NELL, "Look at my walls. Look at what I have kept. All of it."),
        say(co::HAWKE, "Forty-eight units, eight bases, four airports."),
        say(co::HAWKE, "Tell me this is a bluff."),
        say(co::NELL, "It is not a bluff, dear. It is my family."),
        say(co::ANDY, "Nell! I'm with you! Always!"),
        say(co::NELL, "Andy. Thank you."),
        say(co::NELL, "I would rather you ran. But I know you won't."),
        say(co::CLONE_ANDY, "Andy. Please. I'm not your enemy.").with(co::CLONE_ANDY),
        say(co::ANDY, "I know. That's what hurts.").with(co::CLONE_ANDY),
        say(co::NELL, "Sturm. If you win, be kind to them."),
        say(co::STURM, "Kindness is for the kneeling. The conquered are kept."),
        say(co::NELL, "Then let it learn."),
        say(co::HAWKE, "Begin. Hold the moat. Let her come to us first."),
        say(co::HAWKE, "Keep clear of the Lasers' lines. They do not ask whose side you are on."),
        say(co::VON_BOLT, "She has gold. Let me count... a great deal of gold."),
    ]);
    m.victory = Scene::new({
        let mut v = vec![
            sad(co::ANDY, "The whistle. ...The train is gone. They are safe."),
            say(co::ANDY, "That is enough. That is more than enough."),
            say(co::CLONE_ANDY, "Andy. You did it right. Better than I would have.").with(co::CLONE_ANDY),
            say(co::ANDY, "Don't be kind. ...Thank you.").with(co::CLONE_ANDY),
            say(co::NELL, "Andy. Come here. It is all right. It is done."),
            say(co::NELL, "Sturm. You held your hand at the trains."),
            say(co::STURM, "They are mine now. I do not burn what I own."),
            say(co::NELL, "No. And neither were we. Not really."),
            say(co::NELL, "The flag is yours. Take it gently."),
            say(co::STURM, "The flag is a trophy. It hangs in my hall."),
            say(co::NELL, "You learned."),
            say(co::STURM, "I learned nothing. I took. Do not say otherwise."),
            say(co::NELL, "I will not."),
        ];
        let _ = &mut v;
        v
    });
    m.after = Scene::new(vec![troop("The Orange flag comes down. The last train is a whisper on the rails.")]);
    let stage1_post = vec![
        sad(co::NELL, "The Great Hall is yours. Sturm, I yield the castle."),
        say(co::NELL, "Stand down, everyone. Stand down. Please."),
        sad(co::ANDY, "No."),
        say(co::NELL, "Andy."),
        say(co::ANDY, "The last train has not left. Not while I am standing."),
        say(co::NELL, "Andy, listen to me."),
        say(co::ANDY, "I know the order. Let me break it. Just this once."),
        sad(co::NELL, "...Andy."),
        say(co::ANDY, "Rail Yard! Orange Star, with me! One more hour!"),
        say(co::STURM, "Let him run. I take it all in the end."),
        say(co::HAWKE, "A second headquarters. The Rail Yard. A last train."),
        say(co::STURM, "Then I take it properly."),
        say(co::VON_BOLT, "She yielded! Where is my receipt?!"),
        say(co::CLONE_ANDY, "He will hold. I know how. I would.").with(co::CLONE_ANDY),
        say(co::STURM, "Then we know where to aim.").with(co::CLONE_ANDY),
        troop("Nell lays down her command. Andy takes it up."),
    ];
    let mut evac = vec![
        troop("In the east, trains leave the castle's rail yard."),
        say(co::NELL, "Evacuation trains. The city's children are on board."),
        say(co::NELL, "Give me twelve more days. I was born lucky. Watch me."),
        say(co::HAWKE, "She is buying time. For civilians."),
        say(co::STURM, "...I see. Leave the trains. They carry my subjects."),
    ];
    evac.extend(anyone("We do not attack the trains.", &pair));
    m.triggers = vec![
        on_day(1, None, vec![Action::Custom(charge_nell_60)]),
        // Her meter stays under her first power's bar except on the power days; the treasury is capped each morning.
        Trigger::new(When::AfterAction, Cond::Custom(always), vec![Action::Custom(clamp_nell)]).repeating(),
        Trigger::new(When::TurnStart, Cond::EveryDays { n: 1, from: 2 }, vec![Action::Custom(cap_treasury)]).repeating(),
        on_day(1, Some(Cond::PlayerPair { a: co::STURM, b: co::CLONE_ANDY }), vec![Action::Scene(Scene::new(vec![say(co::STURM, "Together."), say(co::CLONE_ANDY, "Always, sir.")]))]),
        // Day 5: Nell's first power, her Lucky Star.
        on_day(
            5,
            None,
            vec![
                Action::Custom(nell_cop),
                Action::Scene(Scene::new(vec![
                    say(co::NELL, "I was born lucky. I'll spend it today. Every bit of it."),
                    say(co::HAWKE, "Hold the camp. Do not cross this turn."),
                ])),
            ],
        ),
        on_day(6, None, vec![Action::Scene(Scene::new(evac))]),
        // Days 7, 9, 11: the Md Tanks, the Neotanks and the Megatanks leave their posts. Day 9: her Super Power. Day 15: the second, if she still leads.
        on_day(7, None, vec![Action::Custom(release_md_tanks)]),
        on_day(11, None, vec![Action::Custom(release_megatanks)]),
        on_day(9, None, vec![Action::Custom(release_neotanks), Action::Custom(nell_super), Action::Scene(Scene::new(vec![say(co::NELL, "For everyone I love: stand with me! Orange Star, shine!")]))]),
        on_day(
            15,
            Some(Cond::Custom(nell_leads)),
            vec![Action::Custom(nell_super_again), Action::Scene(Scene::new(vec![say(co::NELL, "Now! I am not done! Orange Star, with me!")]))],
        ),
        // The duel (once): day 10 in stage one, else the third day of stage two.
        on_day(
            10,
            Some(Cond::All(vec![Cond::Custom(duel_not_done), Cond::Not(Box::new(Cond::OwnerAt { x: 18, y: 3, army: 1 })), Cond::Custom(clone_in_pair)])),
            vec![Action::Custom(duel_done), Action::Scene(Scene::new(duel_clone_lines()))],
        ),
        on_day(
            10,
            Some(Cond::All(vec![Cond::Custom(duel_not_done), Cond::Not(Box::new(Cond::OwnerAt { x: 18, y: 3, army: 1 })), Cond::Custom(no_clone_in_pair)])),
            vec![Action::Custom(duel_done), Action::Scene(Scene::new(duel_plain_lines()))],
        ),
        Trigger::new(When::TurnStart, Cond::Custom(duel_due_in_stage2_clone), vec![Action::Custom(duel_done), Action::Scene(Scene::new(duel_clone_lines()))]).repeating(),
        Trigger::new(When::TurnStart, Cond::Custom(duel_due_in_stage2_plain), vec![Action::Custom(duel_done), Action::Scene(Scene::new(duel_plain_lines()))]).repeating(),
        // Stage one ends: the Great Hall falls. Nell yields, Andy takes the same army to the Rail Yard
        // (his meter, his powers), 10000 more funds, and the reserves stand on the platform.
        Trigger::new(
            When::AfterAction,
            Cond::OwnerAt { x: 18, y: 3, army: 1 },
            vec![
                Action::Custom(record_fall),
                Action::Scene(Scene::new(stage1_post)),
                Action::TakeOver { army: 2, co: co::ANDY, meter_pct: 30 },
                Action::Spawn(rail_yard_reserves()),
                Action::AddFunds { army: 2, funds: 10000 },
            ],
        ),
        Trigger::new(When::TurnStart, Cond::Custom(s2_first_turn), vec![Action::Scene(Scene::new(vec![say(co::ANDY, "Orange Star! The platform is behind us! Do not move!")]))]),
        // The match is won on the Rail Yard (its capture defeats the army) or by routing the army.
        after(beaten(2, (33, 6)), vec![Action::Win]),
    ];
    m.needs = Needs::All(vec!["bh29"]);
    m.flag = region::ORANGE_STAR[5];
    m.stars = 3;
    m
}

/// Act 5's missions, in world-map order (so far the finale's two).
pub fn missions() -> Vec<MissionDef> {
    let mut v = Vec::new();
    // (until M28 is in the tree, a locked placeholder keeps the finale's `needs` valid)
    v.push(dev_stub_bh28());
    v.push(bh29());
    v.push(bh30());
    // The day limit loses: the day after the last is the defeat.
    for m in v.iter_mut().filter(|m| m.key >= "bh29") {
        if m.day_limit > 0 {
            let up = Trigger::new(When::TurnStart, Cond::EveryDays { n: 1000, from: m.day_limit + 1 }, vec![Action::Lose]).repeating();
            m.triggers.push(up);
        }
    }
    v
}

/// Development fallback: a stand-in for M28 while it is not in the tree yet.
fn dev_stub_bh28() -> MissionDef {
    let mut m = MissionDef::new("bh28", "Placeholder 28");
    m.objective = "Rout the Orange Star force.";
    m.map = MapSrc::Ascii(&["1.........", "..ff..c...", "....mm....", "...c..c...", ".........2"]);
    m.armies = vec![ArmyDef::new(colour::BLACK_HOLE, CoSpec::Fixed(co::STURM)), ArmyDef::new(colour::ORANGE_STAR, CoSpec::Fixed(co::NELL))];
    m.units = vec![UnitDef::new(1, unit::INFANTRY, 1, 1), UnitDef::new(2, unit::INFANTRY, 8, 3)];
    m.needs = Needs::Bonds(vec!["bh02"]);
    m.flag = region::ORANGE_STAR[3];
    m
}
