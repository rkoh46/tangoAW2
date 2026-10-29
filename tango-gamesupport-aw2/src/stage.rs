//! Stages: a custom campaign's mission that goes on, in the same battle, on another map (docs/dev/stages.md).
//!
//! A mission declares later stages ([`crate::custom_campaign::StageDef`]); the action [`crate::custom_campaign::Action::NextStage`] swaps the battle to the next one in place: the scenes
//! of its trigger play, the screen fades out, the stage's map header goes into the battle's map table entry, the battle is initialised afresh on it (the game's own
//! `InitMapGameState`, as a two-front battle starts a second front never played), the stage's deployment is placed, the player's survivors land on its deploy cells, the screen
//! fades in and the stage's own rules (its day-one trigger plays its intro) take over. No world map, no results: the mission's win is the last stage's.
//!
//! - **Records.** A stage is compiled as a mission record of its own after the fronts ([`crate::campaign_model::Custom::stage_records`]); [`record`] gives the record the battle is on, which
//!   [`crate::ds_campaign`] reads for its weather, fog, look, controllers and CO screens. The mission index, the progress and the flags stay the mission's.
//! - **Five-army and four-army stages.** The stage's record says whether the patched five-army game is on ([`crate::five`]); the swap turns it on or off between the fade and the new map's
//!   start, once the patches are in the state the stage wants (the unit table's layout differs: 51 slots an army against 64).
//! - **Carry-over.** [`request`] (called from the trigger's script, before anything fades) takes the player's survivors ([`crate::custom_campaign::Carry`]: all, the first n, or some kinds) out of the
//!   live unit table with their HP, ammo, fuel and the rest of their record (AW2 keeps no experience), its funds, its CO's meter and its tag partner into [`CARRY`]; the swap's
//!   arrival writes them into the new table as the stage's player army, on the stage's deploy cells.
//! - **Suspend.** A battle saved on stage k comes back on it: the stage number is saved with the record (a mark and a byte after AW2's block, [`saved_state`]) and the stage's header is put in
//!   place before AW2's resume loads the map ([`continue_on`]). Nothing else is needed: AW2's own block holds the stage's live state.
//! - **Determinism.** Everything here runs in the emulated frame from emulated RAM (the carry buffer and the stage number are EWRAM, [`crate::ram_map::STAGE`]), reads no clock and no
//!   random number, so netplay peers, replays and save states agree.

use mgba::core::Core;

use crate::campaign_model::{Native, StageRuntime, NO_CO};
use crate::custom_campaign::Carry;

/// This module's stubs ([`crate::campaign_model::stub`]): `MAGIC | n`.
pub const MAGIC: u32 = 0x2C00_0000;

// --- The game ------------------------------------------------------------------------

const PLAY_ST: u32 = 0x0300_3FC0;
const COLOURS: u32 = PLAY_ST + 0x33;
const CONTROLLERS: u32 = PLAY_ST + 0x38;
const COS: u32 = PLAY_ST + 0x3D;
const TEAMS: u32 = PLAY_ST + 0x42;
const TURN_LIMIT: u32 = PLAY_ST + 0x30;
const MAP_STATE: u32 = 0x0300_32D8;
const STATE_IDLE: u16 = 0;
const CURRENT_ARMY: u32 = 0x0300_33EC;
const PLAYERS_PTR: u32 = 0x0849_9598;
const UNITS_PTR: u32 = 0x0849_9594;
const PLAYER: u32 = 0x3C;
const UNIT: u32 = 12;
const MAP: u32 = 0x0201_E450;
const INIT_MAP_STATE: u32 = 0x0803_4890;
const SPAWN_UNITS: u32 = 0x0801_96C0;
const RESET_UNITS: u32 = 0x0802_6798;
const MAP_GRAPHICS: u32 = 0x0802_3348;
const FRAME_CALLBACKS: u32 = 0x0803_662C;
const CO_MUSIC: u32 = 0x0804_3DAC;
const LOCK_MAP: u32 = 0x0803_4F7C;
const UNLOCK_MAP: u32 = 0x0803_4F8C;
const FADES_RUNNING: u32 = 0x0801_16A0;
const START_SLOT_SCRIPT: u32 = 0x0801_52EC;
const EVENT_SLOTS: u32 = 0x0200_C510;
/// A unit record: +0 type, +1 flags (0x08 carried, bit 0x20/0x40 moved ...), +2 x, +3 y, +4 hp / ammo word, +6 fuel, +7 and +8 cargo.
const REC_TYPE: u32 = 0;
const REC_FLAGS: u32 = 1;
const OOZIUM: u8 = crate::roster::OOZIUM;

// --- ROM -----------------------------------------------------------------------------

/// The stubs and the swap's script (free ROM between the Setup phase's and the Black Onyx's... see `rom_layout.rs`).
pub const ROM: u32 = 0x08E7_6000;
pub(crate) const ROM_END: u32 = 0x08E7_6800;
const ROM_MAGIC: u32 = 0x3147_5453; // "STG1"
const STUBS_AT: u32 = ROM + 0x10;
const SCRIPT: u32 = ROM + 0x200;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u32)]
enum Stub {
    Begin = 1,
    ScriptsWait,
    Setup,
    PatchWait,
    Load,
    Restore,
    Arrive,
    Music,
    State,
    End,
}
const STUBS: [Stub; 10] = [
    Stub::Begin,
    Stub::ScriptsWait,
    Stub::Setup,
    Stub::PatchWait,
    Stub::Load,
    Stub::Restore,
    Stub::Arrive,
    Stub::Music,
    Stub::State,
    Stub::End,
];

fn stub_at(s: Stub) -> u32 {
    STUBS_AT + 16 * (s as u32 - 1)
}

/// A script slot record: {pointer, immediate, op} (`StepSlotScript`'s table `0x0848A160`): 2 call, 0x17 wait for 1, 0x18 wait for 0, 0x1E fade to black, 0x1F fade from black, 7 end.
fn op(ptr: u32, imm: u16, op: u16) -> [u8; 8] {
    let mut r = [0u8; 8];
    r[0..4].copy_from_slice(&ptr.to_le_bytes());
    r[4..6].copy_from_slice(&imm.to_le_bytes());
    r[6..8].copy_from_slice(&op.to_le_bytes());
    r
}

/// The swap: wait for the trigger's scripts, fade to black, set the stage up, wait for the patches, start the battle afresh, place its deployment, bring the player's survivors, rebuild the
/// scene, fade in.
fn script() -> Vec<u8> {
    let call = |s: Stub| op(stub_at(s) | 1, 0, 2);
    let v: Vec<[u8; 8]> = vec![
        call(Stub::Begin),
        op(stub_at(Stub::ScriptsWait) | 1, 0, 0x18),
        op(0, 0x10, 0x1E),
        op(FADES_RUNNING | 1, 0, 0x18),
        call(Stub::Setup),
        op(stub_at(Stub::PatchWait) | 1, 0, 0x18),
        call(Stub::Load),
        call(Stub::Restore),
        call(Stub::Arrive),
        op(RESET_UNITS | 1, 0, 2),
        op(MAP_GRAPHICS | 1, 0, 2),
        op(FRAME_CALLBACKS | 1, 0, 2),
        call(Stub::Music),
        call(Stub::State),
        op(LOCK_MAP | 1, 0, 2),
        op(0, 0x10, 0x1F),
        op(FADES_RUNNING | 1, 0, 0x18),
        op(UNLOCK_MAP | 1, 0, 2),
        call(Stub::End),
        op(0, 0, 7),
    ];
    v.concat()
}

/// The palette banks of AW2's windows and dialogue box (BG 8 and 13, OBJ 12: the same in every look). The map's graphics loaded in the stage's look overwrite them, and a battle's start
/// loads them again only after its map, which the swap does not go through (the box drew in the map's colours: a pink striped band, M31's Last Citadel in the Snow look). `restore`: false keeps
/// them before the swap ([`crate::ram_map::STAGE_PAL`]), true puts them back in the palette and the buffer AW2 copies at VBlank.
const WINDOW_BANKS: [u32; 3] = [8 * 32, 13 * 32, 0x200 + 12 * 32];
fn keep_window_colours(core: &mut Core, restore: bool) {
    let keep = crate::ram_map::STAGE_PAL.0;
    for (k, &off) in WINDOW_BANKS.iter().enumerate() {
        let mut b = [0u8; 32];
        if restore {
            core.raw_read_range(keep + 32 * k as u32, -1, &mut b);
            for base in [0x0300_20C0u32, 0x0500_0000] {
                core.raw_write_range(base + off, -1, &b);
            }
        } else {
            core.raw_read_range(0x0500_0000 + off, -1, &mut b);
            core.raw_write_range(keep + 32 * k as u32, -1, &b);
        }
    }
}

fn install(core: &mut Core) {
    if core.raw_read_32(ROM, -1) == ROM_MAGIC {
        return;
    }
    for s in STUBS {
        core.raw_write_range(stub_at(s), -1, &crate::campaign_model::stub(MAGIC | s as u32));
    }
    let sc = script();
    assert!(SCRIPT + sc.len() as u32 <= ROM_END);
    core.raw_write_range(SCRIPT, -1, &sc);
    core.raw_write_32(ROM, -1, ROM_MAGIC);
}

// --- RAM -----------------------------------------------------------------------------

/// The module's state ([`crate::ram_map::STAGE`]): +0 the stage the battle is on (0 the mission's own, k its k-th later stage), +1 a swap is running (its begin stub), +2 a Continue has put the
/// stage back (the battle's start must keep it), +3 the survivors' count, +4 the player's army the carried units left (1..5), +8 its funds (u32), +0xC its CO, +0xD its partner (0xFF none), +0x10 the
/// partner's meter (u32), +0x14 the CO's meter (u32), +0x20 the units' 12-byte records.
const STATE: u32 = crate::ram_map::STAGE.0;
const STAGE_AT: u32 = STATE;
const BUSY: u32 = STATE + 1;
const CONTINUED: u32 = STATE + 2;
const CARRY_N: u32 = STATE + 3;
const CARRY_ARMY: u32 = STATE + 4;
const CARRY_FUNDS: u32 = STATE + 8;
const CARRY_CO: u32 = STATE + 0xC;
const CARRY_PARTNER: u32 = STATE + 0xD;
const CARRY_PCHARGE: u32 = STATE + 0x10;
const CARRY_CHARGE: u32 = STATE + 0x14;
const CARRY: u32 = STATE + 0x20;
/// The most units carried (the campaigns' armies start with at most 40: the cap of the carry buffer, [`crate::ram_map::STAGE`]).
pub const CARRY_MAX: u32 = 40;
pub const STATE_LEN: u32 = 0x20 + 12 * CARRY_MAX;

/// The stage the battle is on (0: the mission's own).
pub fn stage(core: &Core) -> u8 {
    core.raw_read_8(STAGE_AT, -1)
}

/// A swap is running: what is on the screen is neither stage's yet.
pub fn swapping(core: &Core) -> bool {
    core.raw_read_8(BUSY, -1) != 0
}

/// The record the battle is on: the mission's index, or the compiled record of its current stage.
pub fn record(core: &Core) -> usize {
    let m = core.raw_read_8(crate::ds_campaign::MISSION, -1) as usize;
    let k = stage(core) as usize;
    if k == 0 {
        return m;
    }
    crate::ds_campaign::campaign(core)
        .and_then(|c| c.model.custom.as_ref().and_then(|x| x.stage_records.get(m)).and_then(|v| v.get(k - 1).copied()))
        .map_or(m, |r| r as usize)
}

fn runtime(core: &Core, k: usize) -> Option<StageRuntime> {
    let m = core.raw_read_8(crate::ds_campaign::MISSION, -1) as usize;
    crate::ds_campaign::campaign(core).and_then(|c| c.model.custom.as_ref().and_then(|x| x.stages.get(m)).and_then(|v| v.get(k - 1).cloned()))
}

fn players(core: &Core) -> u32 {
    crate::five::players(core)
}

/// A new battle starts (the first frame of a mission, [`crate::ds_campaign::map_start`]): on the mission's own stage, unless a Continue has brought a stage back.
pub fn map_start(core: &mut Core) {
    if core.raw_read_8(BUSY, -1) != 0 {
        return;
    }
    if core.raw_read_8(CONTINUED, -1) != 0 {
        core.raw_write_8(CONTINUED, -1, 0);
        return;
    }
    core.raw_write_8(STAGE_AT, -1, 0);
}

/// A mission is chosen on the world map: no stage, nothing carried.
pub fn reset(core: &mut Core) {
    if core.raw_read_8(CONTINUED, -1) != 0 {
        return;
    }
    core.raw_write_range(STATE, -1, &vec![0u8; 0x20]);
}

// --- The trigger ----------------------------------------------------------------------

/// `Action::NextStage` ([`crate::custom_campaign::STAGE_NEXT`], run by the trigger's script): the survivors are taken, the swap script starts. Returns what the script engine's call op
/// takes: a tail call into the game's slot-script start.
pub fn request(core: &mut Core) -> u32 {
    install(core);
    let next = stage(core) as usize + 1;
    let Some(rt) = runtime(core, next) else {
        return 0;
    };
    if swapping(core) {
        return 0;
    }
    snapshot(core, &rt);
    core.raw_write_8(BUSY, -1, Stub::Begin as u8);
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, SCRIPT as i32);
    cpu.set_gpr(1, 0);
    cpu.set_thumb_pc(START_SLOT_SCRIPT);
    crate::campaign_model::TAIL_CALLED
}

fn slots(core: &Core) -> u32 {
    if crate::five::active(core) {
        51
    } else {
        64
    }
}

/// The army the player commands in the battle now (1, or the fifth of a five-army mission).
fn player_army(core: &Core) -> u32 {
    if crate::five::active(core) {
        5
    } else {
        1
    }
}

/// The value of a unit as the carry rules rank them: its type's cost (AW2's price table, as the cost rule of the smart factory reads it), scaled by its HP.
fn value(core: &Core, rec: &[u8; 12]) -> u32 {
    let hp = (u16::from_le_bytes([rec[4], rec[5]]) & 0x7F) as u32;
    (core.raw_read_16(crate::roster::table(core) + 0x5C * rec[0] as u32 + 6, -1) as u32) * 10 * hp.max(1) / 100
}

/// The player's survivors and state, into [`CARRY`].
fn snapshot(core: &mut Core, rt: &StageRuntime) {
    let army = player_army(core);
    let stride = slots(core);
    let base = core.raw_read_32(UNITS_PTR, -1);
    let mut recs: Vec<[u8; 12]> = Vec::new();
    for j in 1..stride {
        let at = base + UNIT * ((army - 1) * stride + j);
        let mut r = [0u8; 12];
        core.raw_read_range(at, -1, &mut r);
        if r[REC_TYPE as usize] == 0 || r[REC_TYPE as usize] > OOZIUM {
            continue;
        }
        recs.push(r);
    }
    // (a unit inside a transport comes as a unit of its own, off the transport)
    let keep = |r: &[u8; 12]| match &rt.carry {
        Carry::Kinds(k) => k.contains(&r[0]),
        _ => true,
    };
    recs.retain(keep);
    if let Carry::UpTo(n) = rt.carry {
        recs.sort_by_key(|r| std::cmp::Reverse(value_of(core, r)));
        recs.truncate(n as usize);
    }
    recs.truncate(CARRY_MAX as usize);
    let p = players(core) + PLAYER * army;
    core.raw_write_8(CARRY_N, -1, recs.len() as u8);
    core.raw_write_8(CARRY_ARMY, -1, army as u8);
    core.raw_write_32(CARRY_FUNDS, -1, core.raw_read_32(p, -1));
    core.raw_write_8(CARRY_CO, -1, core.raw_read_8(p + 0x1D, -1));
    let partner = crate::tag::partner(core, army);
    core.raw_write_8(CARRY_PARTNER, -1, partner.unwrap_or(NO_CO));
    core.raw_write_32(CARRY_PCHARGE, -1, crate::tag::partner_charge(core, army));
    core.raw_write_32(CARRY_CHARGE, -1, core.raw_read_32(p + 0x20, -1));
    for (k, r) in recs.iter().enumerate() {
        core.raw_write_range(CARRY + 12 * k as u32, -1, r);
    }
}

fn value_of(core: &Core, r: &[u8; 12]) -> u32 {
    value(core, r)
}

// --- The stubs -----------------------------------------------------------------------

fn return_to(core: &mut Core, r0: u32) {
    let cpu = core.gba_mut().cpu_mut();
    let lr = cpu.gpr(14) as u32;
    cpu.set_gpr(0, r0 as i32);
    cpu.set_thumb_pc(lr & !1);
}

fn events_running(core: &Core) -> bool {
    (0..11).any(|k| core.raw_read_32(EVENT_SLOTS + 0x18 * k, -1) != 0)
}

/// The stage the swap goes to (its number, 1-based) and its compiled record.
fn target(core: &Core) -> Option<(usize, usize)> {
    let next = stage(core) as usize + 1;
    let m = core.raw_read_8(crate::ds_campaign::MISSION, -1) as usize;
    let rec = crate::ds_campaign::campaign(core).and_then(|c| {
        c.model
            .custom
            .as_ref()
            .and_then(|x| x.stage_records.get(m))
            .and_then(|v| v.get(next - 1).copied())
    })?;
    Some((next, rec as usize))
}

fn native_of(core: &Core, rec: usize) -> Option<(&'static Native, [u8; 0x5C])> {
    let c = crate::ds_campaign::campaign(core)?;
    let info = c.model.built.missions.get(rec)?;
    let h = c.model.built.headers.iter().find(|h| h.0 as usize == rec)?.1;
    Some((info.native.as_ref()?, h))
}

/// Called by the compiled stubs; `id` is `MAGIC | n`.
pub fn magic(core: &mut Core, id: u32) {
    let n = id & 0xFF;
    let Some(&s) = STUBS.iter().find(|s| **s as u32 == n) else {
        return return_to(core, 0);
    };
    match s {
        Stub::Begin => {
            keep_window_colours(core, false);
            core.raw_write_8(BUSY, -1, s as u8);
            core.raw_write_16(MAP_STATE, -1, STATE_IDLE);
            return_to(core, 0)
        }
        // (1 while the trigger's own scripts still run: the op waits for 0)
        Stub::ScriptsWait => {
            core.raw_write_16(MAP_STATE, -1, STATE_IDLE);
            return_to(core, events_running(core) as u32)
        }
        Stub::Setup => {
            setup(core);
            return_to(core, 0)
        }
        // (the patched five-army game is in the state the stage wants)
        Stub::PatchWait => {
            let want = target(core)
                .and_then(|(_, rec)| native_of(core, rec))
                .is_some_and(|(n, _)| n.five.is_some());
            let on = crate::five::patches_on(core);
            return_to(core, (on != want) as u32)
        }
        Stub::Load => core.gba_mut().cpu_mut().set_thumb_pc(INIT_MAP_STATE),
        Stub::Restore => {
            // The stage's deployment, as a battle's start places it: the unit table and the unit plane start empty.
            let base = core.raw_read_32(UNITS_PTR, -1);
            for i in 0..(12 * 256 / 2) {
                core.raw_write_16(base + 2 * i, -1, 0);
            }
            for i in 0..0xA10 / 2 {
                core.raw_write_16(MAP + 0x12 + 2 * i, -1, 0);
            }
            core.gba_mut().cpu_mut().set_thumb_pc(SPAWN_UNITS)
        }
        Stub::Arrive => {
            arrive(core);
            return_to(core, 0)
        }
        Stub::Music => {
            keep_window_colours(core, true);
            let cpu = core.gba_mut().cpu_mut();
            cpu.set_gpr(0, 1);
            cpu.set_thumb_pc(CO_MUSIC)
        }
        Stub::State => {
            core.raw_write_16(MAP_STATE, -1, 5);
            return_to(core, 0)
        }
        Stub::End => {
            crate::two_front::rebuild_planes(core);
            core.raw_write_8(BUSY, -1, 0);
            return_to(core, 0)
        }
    }
}

/// The stage's header in the battle's map table entry, its armies in gPlaySt, the five-army game on or off.
fn setup(core: &mut Core) {
    let Some((next, rec)) = target(core) else { return };
    let Some((native, h)) = native_of(core, rec) else { return };
    crate::ds_campaign::write_header(core, &h);
    core.raw_write_8(STAGE_AT, -1, next as u8);
    // (the mission's index and flags are the mission's: only the compiled record changes)
    let c = crate::ds_campaign::campaign(core).expect("campaign");
    let info = &c.model.built.missions[rec];
    let keep_co = core.raw_read_8(CARRY_CO, -1);
    match native.five {
        Some((co, _, team)) => {
            let co = if native.keep { keep_co } else { co };
            crate::five::set_campaign(core, true, co, team)
        }
        None => crate::five::set_campaign(core, false, 0, 0),
    }
    let armies = info.armies as u32;
    for k in 0..4u32 {
        let present = k < armies.min(4);
        core.raw_write_8(COLOURS + 1 + k, -1, h[0x40 + k as usize]);
        core.raw_write_8(TEAMS + 1 + k, -1, h[0x44 + k as usize]);
        let mut co = native.cos[k as usize].0;
        if native.keep && native.five.is_none() && k == 0 {
            co = keep_co;
        }
        core.raw_write_8(COS + 1 + k, -1, if present { co } else { 0 });
        let human = present && native.five.is_none() && k == 0;
        core.raw_write_8(CONTROLLERS + 1 + k, -1, if human { 1 } else if present { 2 } else { 0 });
    }
    core.raw_write_8(TURN_LIMIT, -1, 0);
}

/// The stage's player army gets the survivors (on the deploy cells), the funds, the CO's meter and the tag partner.
fn arrive(core: &mut Core) {
    let Some((next, rec)) = target(core).or_else(|| {
        // (setup has already stored the stage number)
        let m = core.raw_read_8(crate::ds_campaign::MISSION, -1) as usize;
        crate::ds_campaign::campaign(core)
            .and_then(|c| c.model.custom.as_ref().and_then(|x| x.stage_records.get(m)).and_then(|v| v.get(stage(core) as usize - 1).copied()))
            .map(|r| (stage(core) as usize, r as usize))
    }) else {
        return;
    };
    let Some(rt) = runtime(core, stage(core) as usize) else { return };
    let _ = next;
    crate::two_front::fresh_extras(core);
    // The armies the stage does not have are not in the battle: their player records (left by the stage before) are emptied, so no phantom army stays alive and keeps the match from ending.
    let present = crate::ds_campaign::campaign(core)
        .and_then(|c| c.model.built.missions.get(rec))
        .map_or(0, |i| i.armies as u32);
    let pl = players(core);
    for a in present + 1..=5 {
        core.raw_write_range(pl + PLAYER * a, -1, &[0u8; PLAYER as usize]);
    }
    let army = player_army(core);
    let stride = slots(core);
    let base = core.raw_read_32(UNITS_PTR, -1);
    let n = core.raw_read_8(CARRY_N, -1) as u32;
    let w = core.raw_read_16(MAP, -1) as u32;
    let h = core.raw_read_16(MAP + 2, -1) as u32;
    let mut taken: Vec<(u32, u32)> = Vec::new();
    for k in 0..n.min(CARRY_MAX) {
        let mut r = [0u8; 12];
        core.raw_read_range(CARRY + 12 * k, -1, &mut r);
        let spot = rt.deploy.iter().map(|&(x, y)| (x as u32, y as u32)).find(|&c| ground_ok(core, r[0], c, w, h) && !taken.contains(&c) && !occupied(core, c));
        let Some((x, y)) = spot.or_else(|| nearest(core, r[0], rt.deploy.first().map_or((w / 2, h / 2), |c| (c.0 as u32, c.1 as u32)), &taken, w, h)) else {
            continue;
        };
        let Some(j) = (1..stride).find(|&j| core.raw_read_8(base + UNIT * ((army - 1) * stride + j), -1) == 0) else { break };
        r[2] = x as u8;
        r[3] = y as u8;
        // (a fresh arrival: not moved, not carried, no cargo: the transport's cargo came as units of their own)
        r[REC_FLAGS as usize] &= !0x08;
        r[7] = 0;
        r[8] = 0;
        let at = base + UNIT * ((army - 1) * stride + j);
        core.raw_write_range(at, -1, &r);
        let row = core.raw_read_16(MAP + 0x417A + 2 * y, -1) as u32;
        core.raw_write_8(MAP + 0x12 + row + x, -1, ((army - 1) * stride + j) as u8);
        taken.push((x, y));
    }
    let p = players(core) + PLAYER * army;
    core.raw_write_32(p, -1, rt.funds.map_or(core.raw_read_32(CARRY_FUNDS, -1), |f| f.max(0) as u32));
    core.raw_write_32(p + 0x20, -1, core.raw_read_32(CARRY_CHARGE, -1));
    let partner = core.raw_read_8(CARRY_PARTNER, -1);
    if partner != NO_CO {
        crate::tag::form_pair(core, army, partner, core.raw_read_32(CARRY_PCHARGE, -1));
    }
}

fn class_at(core: &Core, x: u32, y: u32) -> u8 {
    let row = core.raw_read_16(MAP + 0x417A + 2 * y, -1) as u32;
    core.raw_read_8(MAP + 0x1432 + row + x, -1) & 0x1F
}

fn occupied(core: &Core, c: (u32, u32)) -> bool {
    let row = core.raw_read_16(MAP + 0x417A + 2 * c.1, -1) as u32;
    core.raw_read_8(MAP + 0x12 + row + c.0, -1) != 0
}

/// Whether a unit of `kind` can stand on the cell: ground units on land (not sea, river, mountain for treads), ships on sea, air anywhere.
fn ground_ok(core: &Core, kind: u8, c: (u32, u32), w: u32, h: u32) -> bool {
    if c.0 >= w || c.1 >= h {
        return false;
    }
    crate::two_front::unit_may_stand(core, kind, class_at(core, c.0, c.1))
}

/// The free cell nearest `from` the unit can stand on.
fn nearest(core: &Core, kind: u8, from: (u32, u32), taken: &[(u32, u32)], w: u32, h: u32) -> Option<(u32, u32)> {
    let mut best: Option<(u32, (u32, u32))> = None;
    for y in 0..h {
        for x in 0..w {
            let c = (x, y);
            if taken.contains(&c) || occupied(core, c) || !ground_ok(core, kind, c, w, h) {
                continue;
            }
            let d = x.abs_diff(from.0) + y.abs_diff(from.1);
            if best.is_none_or(|b| d < b.0) {
                best = Some((d, c));
            }
        }
    }
    best.map(|b| b.1)
}

// --- Suspend -------------------------------------------------------------------------

/// The mark and the byte saved after AW2's block of a mission saved on a later stage.
pub const SAVED_MARK: u32 = 0x4547_5453; // "STGE"
pub const SAVED_LEN: u32 = 1;

/// The stage to save with a mission saved halfway (None on the mission's own stage).
pub fn saved_state(core: &Core) -> Option<u8> {
    let k = stage(core);
    (k > 0 && crate::ds_campaign::active(core)).then_some(k)
}

/// DS CAMPAIGN's Continue over a battle saved on stage `k` (before AW2's resume): the stage's header in the battle's map table entry, as a swap puts it before the map is read, the five-army game
/// as the stage wants it.
pub fn continue_on(core: &mut Core, k: u8) {
    core.raw_write_8(STAGE_AT, -1, k);
    core.raw_write_8(CONTINUED, -1, 1);
    if let Some((_, rec)) = {
        let m = core.raw_read_8(crate::ds_campaign::MISSION, -1) as usize;
        crate::ds_campaign::campaign(core)
            .and_then(|c| c.model.custom.as_ref().and_then(|x| x.stage_records.get(m)).and_then(|v| v.get(k as usize - 1).copied()))
            .map(|r| (k, r as usize))
    } {
        if let Some((native, h)) = native_of(core, rec) {
            crate::ds_campaign::write_header(core, &h);
            match native.five {
                Some((co, _, team)) => crate::five::set_campaign(core, true, co, team),
                None => crate::five::set_campaign(core, false, 0, 0),
            }
        }
    }
}

/// The record saved with the mission came back (after the block): the stage number kept.
pub fn restore_saved(core: &mut Core, k: u8) {
    core.raw_write_8(STAGE_AT, -1, k);
    core.raw_write_8(BUSY, -1, 0);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn script_and_stubs_fit() {
        assert!(STUBS_AT + 16 * STUBS.len() as u32 <= SCRIPT);
        assert!(SCRIPT + script().len() as u32 <= ROM_END);
        assert!(STATE_LEN as usize == 0x20 + 12 * CARRY_MAX as usize);
    }
}
