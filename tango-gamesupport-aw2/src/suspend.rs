//! tangoAW2's own battle state in a suspended game (the map menu's Save),
//! with the Dual Strike pack.
//!
//! AW2 saves a game in progress (`sub_08016D30`) as the 0xE28-byte block
//! `CaptureBattleSaveState` (`sub_08016F38`) fills at 0x02000000: day,
//! army, gPlaySt, the weather block, players, units, changed tiles,
//! inventions, up to +0xDAC. The rest of the block is written to Flash but
//! never read back (`sub_08017208`). State tangoAW2 keeps in its own RAM
//! and that lasts past a turn rides there, after a mark:
//!
//! - the Rules' fog flag while rain forces fog on ([`crate::ds_weather`]):
//!   gPlaySt is saved with the forced fog, and a game continued in rain
//!   kept fog on for good once the rain stopped;
//! - Ex Machina's stun ([`crate::co_powers`]): the units it marked were all
//!   free after Continue.
//!
//! - the map table the game was played on ([`crate::ds_versus`]: Dual
//!   Strike's Versus and War Room maps, or AW2's): a game saved on AW2's
//!   table (without the byte: before it existed) continues on AW2's.
//!
//! (The sandstorm and the map's look are in the weather block, which AW2
//! saves itself; Com Towers are counted on the map.) Without the pack
//! nothing is written: the block is AW2's own, byte for byte.
//!
//! **A DS Campaign mission saved halfway** (Dual Strike's campaign has the
//! map menu's Save: "Save over Mission / Day data"). AW2 saves a campaign
//! mission in slot 2 and marks it in the profile (`0x0200C429`), and AW2
//! CAMPAIGN's Continue resumes it; a DS mission goes to its own slot,
//! [`DS_SLOT`], instead, so AW2's saved mission and its mark are left alone:
//! `sub_08016D30` is trapped at its start (in a session, slot 2: the mark
//! as it is noted) and at its call of the slot writer (the slot made
//! [`DS_SLOT`] and the mark put back, before the writer serializes the
//! profile). The block's tail also gets the session's own state after
//! [`DS_MARK`]: the mission, its flags ([`crate::ds_campaign`]'s 0x20..0x9F),
//! the countdown of Dual Strike's op 0x5A, Means to an End's state (the
//! Hard choice is the flags' 0x60, the records are in the DS record). DS CAMPAIGN's Continue resumes
//! the mission when [`DS_SLOT`] is in AW2's sector directory (the session
//! set up as for the world map, then AW2's own resume, `sub_08017688`); the
//! slot is dropped from the directory (AW2's delete, `sub_0801ABF8`, without
//! its write: the next save writes it) when the mission ends and on a new
//! DS Campaign.
//!
//! **A Survival map saved halfway** goes to [`SURVIVAL_SLOT`] the same way
//! (the War Room's slot 3 and its mark left alone), the run in the tail
//! where a DS mission keeps its session ([`SV_MARK`]); Survival's Continue
//! resumes it through the War Room's Continue handler (trapped:
//! [`WAR_ROOM_CONTINUE`]) and the run comes back when the block is applied.

use mgba::core::Core;

use crate::ds_weather::is_on;

/// The block's staging buffer, its unused tail, and its length.
const BLOCK: u32 = 0x0200_0000;
const TAIL: u32 = BLOCK + 0xDAC;
#[cfg(test)]
const BLOCK_LEN: u32 = 0xE28;
/// The length `sub_08016D30` writes.
const BLOCK_WRITE: u32 = 0xE28;
/// The tail: +0 [`MARK`], +4 version, +5 the rain's fog flag, +6 Dual
/// Strike's maps' table in use (1), +8 the stun.
const MARK: u32 = 0x3257_4154; // "TAW2"
const VERSION: u8 = 1;
const AT_RULE_FOG: u32 = 5;
const AT_DS_TABLE: u32 = 6;
const AT_STUN: u32 = 8;
const TAIL_LEN: u32 = AT_STUN + crate::co_powers::STUN_STATE_LEN as u32;

/// `sub_08016D30` right after `CaptureBattleSaveState` returns (the block
/// filled, not yet written to Flash).
pub const CAPTURED: u32 = 0x0801_6D88;
/// `sub_08016DB8` (Continue) right after the slot is read into the block,
/// before `sub_08017208` applies it (and loads the map from the map table).
pub const LOADED: u32 = 0x0801_6DCC;
/// `sub_08016DB8` (Continue) right after `sub_08017208` returns (the block
/// loaded and applied; a design map's own slot is loaded over the buffer
/// next).
pub const APPLIED: u32 = 0x0801_6DD0;
const CURRENT_ARMY: u32 = 0x0300_33EC;
const GAME_MODE: u32 = 0x0300_3FC1;
const VERSUS: u8 = 3;

/// The Versus rule Skills ([`crate::versus_rules`]) and the CO tag pairs
/// ([`crate::tag`]) ride past the 0xE28-byte block: while the rule is on or
/// a battle has pairs the block is written longer (the staging
/// buffer is 0x2000 bytes; AW2's reader takes the slot's whole length back).
/// A mark, a hash of AW2's part of the block (+0..+0xDAC, so a stale copy
/// from another save is never taken), the rule (and three spare bytes),
/// then the pairs, then Cassius's extra moves ([`crate::es_co::moved_state`]:
/// the units that attacked under Triumph and may still move once; the block's
/// own tail has no room left).
const TAG_AT: u32 = BLOCK + 0xE28;
const TAG_MARK: u32 = 0x3247_4154; // "TAG2"
const RULES: [u32; 1] = [crate::co_skills::VERSUS_RULE];
pub const TAG_LEN: u32 = 8 + 4 + crate::tag::SAVED_LEN as u32 + crate::es_co::MOVED_LEN;

fn block_hash(core: &Core) -> u32 {
    let mut b = vec![0u8; 0xDAC];
    core.raw_read_range(BLOCK, -1, &mut b);
    b.iter()
        .fold(0x811C_9DC5u32, |h, &x| (h ^ x as u32).wrapping_mul(0x0100_0193))
}

fn tag_tail_ok(core: &Core) -> bool {
    core.raw_read_32(TAG_AT, -1) == TAG_MARK && core.raw_read_32(TAG_AT + 4, -1) == block_hash(core)
}

fn captured(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let rules = RULES.map(|r| core.raw_read_8(r, -1) & 1);
    let versus = core.raw_read_8(GAME_MODE, -1) == VERSUS;
    if crate::tag::any(core) || (versus && rules != [0]) || crate::es_co::moved_any(core) {
        let mut t = Vec::with_capacity(TAG_LEN as usize);
        t.extend_from_slice(&TAG_MARK.to_le_bytes());
        t.extend_from_slice(&block_hash(core).to_le_bytes());
        t.extend_from_slice(&[rules[0], 0, 0, 0]);
        t.extend_from_slice(&crate::tag::saved(core));
        t.extend_from_slice(&crate::es_co::moved_state(core));
        core.raw_write_range(TAG_AT, -1, &t);
    }
    let mut b = vec![0u8; TAIL_LEN as usize];
    b[0..4].copy_from_slice(&MARK.to_le_bytes());
    b[4] = VERSION;
    b[AT_RULE_FOG as usize] = crate::ds_weather::rule_fog(core);
    b[AT_DS_TABLE as usize] = crate::ds_versus::in_use(core) as u8;
    b[AT_STUN as usize..].copy_from_slice(&crate::co_powers::stun_state(core));
    core.raw_write_range(TAIL, -1, &b);
}

/// The block read, before the map is loaded: the map table it was saved on
/// (crate::ds_versus).
fn loaded(core: &mut Core) {
    let ours = core.raw_read_32(TAIL, -1) == MARK && core.raw_read_8(TAIL + 4, -1) == VERSION;
    crate::ds_versus::continued(core, ours && core.raw_read_8(TAIL + AT_DS_TABLE, -1) == 1);
}

fn applied(core: &mut Core) {
    if !is_on(core) {
        return;
    }
    let mut b = vec![0u8; TAIL_LEN as usize];
    core.raw_read_range(TAIL, -1, &mut b);
    let ours = u32::from_le_bytes(b[0..4].try_into().unwrap()) == MARK && b[4] == VERSION;
    let army = core.raw_read_8(CURRENT_ARMY, -1);
    crate::ds_weather::set_rule_fog(core, if ours { b[AT_RULE_FOG as usize] } else { 0 });
    crate::co_powers::set_stun_state(core, ours.then(|| &b[AT_STUN as usize..]), army);
    if tag_tail_ok(core) {
        // The rules as the game was saved with them; the skills the armies
        // had on (crate::co_skills: a map start sets them, and a Continue
        // has none), then the pairs (their partners' skills).
        for (k, r) in RULES.iter().enumerate() {
            let v = core.raw_read_8(TAG_AT + 8 + k as u32, -1);
            core.raw_write_8(*r, -1, v);
        }
        if core.raw_read_8(GAME_MODE, -1) == VERSUS {
            crate::co_skills::clear(core);
            crate::co_skills::battle_start(core);
        }
        let mut t = vec![0u8; crate::tag::SAVED_LEN];
        core.raw_read_range(TAG_AT + 12, -1, &mut t);
        crate::tag::restore(core, Some(&t));
        let mut m = vec![0u8; crate::es_co::MOVED_LEN as usize];
        core.raw_read_range(TAG_AT + 12 + crate::tag::SAVED_LEN as u32, -1, &mut m);
        crate::es_co::set_moved_state(core, &m);
        // Read once: a later Continue of a game saved without pairs does
        // not take these.
        core.raw_write_32(TAG_AT, -1, 0);
    } else {
        crate::tag::restore(core, None);
    }
}

// --- A DS Campaign mission saved halfway ---------------------------------------

/// The Flash slot (save tag) of a DS mission saved halfway (AW2: 0 profile,
/// 2..4 suspends, 5..8 design maps; tangoAW2: 15 the DS Campaign's record,
/// 14 its mission saved halfway). A custom campaign's is its source's
/// `mid_slot` ([`crate::campaign_model::Source`]): the BH Campaign's, 12.
pub const DS_SLOT: u8 = 14;

/// The slot a session's mission is saved in.
fn session_slot(core: &Core) -> u8 {
    crate::campaign_model::SOURCES[crate::ds_campaign::source(core)].mid_slot
}
const CAMPAIGN_SLOT: u32 = 2;
/// The session's state in the block's tail, after the "TAW2" part: +0
/// [`DS_MARK`], +2 the mission, +3 version, +4 the countdown (u32), +8 the
/// flags (16 bytes), +24 the mission's state (Means to an End's, Ring of Fire's: `MTE_LEN` bytes),
/// then Crystal Calamity's Black Onyx (crate::onyx, `SAVED_LEN` bytes).
const DS_AT: u32 = TAIL + TAIL_LEN;
const DS_MARK: u16 = 0x5344; // "DS"
const DS_MTE_LEN: u32 = crate::ds_campaign_rules::MTE_LEN;
const DS_LEN: u32 = 8 + 16 + DS_MTE_LEN + crate::onyx::SAVED_LEN as u32;
/// AW2's campaign-suspend mark in the profile (`sub_08016C9C(2)`).
const CAMPAIGN_MARK: u32 = 0x0200_C429;
/// `sub_08016D30(slot, ..)` past its prologue (`cmp r4, #0`: r4 the slot), and its `bl sub_0801A7D8`
/// (r0 the slot, the block not yet written).
const SAVE_START: u32 = 0x0801_6D3A;
const SAVE_WRITE: u32 = 0x0801_6D8E;
/// While a DS mission is being saved: 0x80 | AW2's campaign mark as it was.
const DS_SAVING: u32 = 0x0203_FFAD;
/// AW2's sector directory in RAM (`gUnknown_0200CC38`): +0x00 each
/// sector's slot, +0x10 the directory the next write saves.
const DIRECTORY: u32 = 0x0200_CC38;
/// AW2's resume of a saved game (`sub_08017688(slot)`).
const RESUME: u32 = 0x0801_7688;
const FLASH: u32 = 0x0E00_0000;

fn save_start(core: &mut Core) {
    // (past its prologue: r4 the slot; five's patches hook the first instruction)
    if !crate::ds_campaign::active(core) || core.gba().cpu().gpr(4) as u32 != CAMPAIGN_SLOT {
        return;
    }
    let mark = core.raw_read_8(CAMPAIGN_MARK, -1);
    core.raw_write_8(DS_SAVING, -1, 0x80 | mark);
}

fn save_write(core: &mut Core) {
    save_write_aw2(core);
    five_save(core);
}

/// A five-army battle's record after the block ([`crate::five::saved_state`]): +0 [`FIVE_MARK`], +4 its length (u16), +6 a hash of AW2's part of the block (the battle it
/// belongs to: a record left in the staging buffer by another save never matches another battle's block), then the state. It follows whatever else the block carries (the pairs'
/// tail, the stage's mark): [`FIVE_AT`] lists where a reader looks.
const FIVE_MARK: u32 = 0x3556_4946; // "FIV5"
const FIVE_HEAD: u32 = 10;
const FIVE_AT: [u32; 2] = [BLOCK_SIZE, BLOCK_SIZE + TAG_LEN];
/// The staging buffer's size and the most a record may take (two Flash sectors, 0xFAD bytes each).
const STAGING: u32 = 0x2000;
const SLOT_MAX: u32 = 2 * 0xFAD;

fn five_save(core: &mut Core) {
    // (the slot writer's length is r2)
    let len = core.gba().cpu().gpr(2) as u32;
    // A record from an earlier save is out of the buffer first, wherever a reader would look.
    for at in FIVE_AT {
        if core.raw_read_32(BLOCK + at, -1) == FIVE_MARK {
            core.raw_write_32(BLOCK + at, -1, 0);
        }
    }
    let Some(state) = crate::five::saved_state(core) else {
        return;
    };
    if !(BLOCK_SIZE..=BLOCK_SIZE + TAG_LEN).contains(&len) && len != BLOCK_SIZE + 5 {
        return;
    }
    let total = len + FIVE_HEAD + state.len() as u32;
    if total > STAGING.min(SLOT_MAX) {
        return;
    }
    let mut r = Vec::with_capacity(state.len() + FIVE_HEAD as usize);
    r.extend_from_slice(&FIVE_MARK.to_le_bytes());
    r.extend_from_slice(&(state.len() as u16).to_le_bytes());
    r.extend_from_slice(&block_hash(core).to_le_bytes());
    r.extend_from_slice(&state);
    core.raw_write_range(BLOCK + len, -1, &r);
    core.gba_mut().cpu_mut().set_gpr(2, total as i32);
}

/// The block just applied: a five-army battle saved with it comes back (the game is five-army again, its tables as saved). The record is taken once.
fn five_restore(core: &mut Core) {
    let hash = block_hash(core);
    for at in FIVE_AT {
        let a = BLOCK + at;
        // (bytes: the length and the hash are not aligned in the buffer)
        let mut h = [0u8; FIVE_HEAD as usize];
        core.raw_read_range(a, -1, &mut h);
        if u32::from_le_bytes(h[0..4].try_into().unwrap()) != FIVE_MARK || u32::from_le_bytes(h[6..10].try_into().unwrap()) != hash {
            continue;
        }
        let n = u16::from_le_bytes([h[4], h[5]]) as usize;
        if n == 0 || a + FIVE_HEAD + n as u32 > BLOCK + STAGING {
            continue;
        }
        let mut b = vec![0u8; n];
        core.raw_read_range(a + FIVE_HEAD, -1, &mut b);
        core.raw_write_32(a, -1, 0);
        crate::five::restore_saved(core, &b);
        return;
    }
}

/// What a suspended game's record holds, for `aw2dev save inspect`: the mark's place, the battle's hash, the five-army state's length.
pub fn five_record_in(block: &[u8], tag_len: usize) -> Option<(usize, u32, usize)> {
    let _ = tag_len;
    FIVE_AT.iter().find_map(|&at| {
        let at = at as usize;
        if block.len() < at + FIVE_HEAD as usize || u32::from_le_bytes(block[at..at + 4].try_into().ok()?) != FIVE_MARK {
            return None;
        }
        let n = u16::from_le_bytes(block[at + 4..at + 6].try_into().ok()?) as usize;
        Some((at, u32::from_le_bytes(block[at + 6..at + 10].try_into().ok()?), n))
    })
}

fn save_write_aw2(core: &mut Core) {
    if is_on(core) && core.gba().cpu().gpr(2) as u32 == BLOCK_WRITE && tag_tail_ok(core) {
        core.gba_mut().cpu_mut().set_gpr(2, (BLOCK_WRITE + TAG_LEN) as i32);
    }
    let saving = core.raw_read_8(DS_SAVING, -1);
    if saving & 0x80 == 0 {
        return;
    }
    core.raw_write_8(DS_SAVING, -1, 0);
    let slot = session_slot(core);
    core.raw_write_8(CAMPAIGN_MARK, -1, saving & 0x7F);
    let mut b = vec![0u8; DS_LEN as usize];
    b[0..2].copy_from_slice(&DS_MARK.to_le_bytes());
    // (the mission in the low five bits; a campaign after the BH Campaign shares slot 12 with it and says which one it is in the top three)
    b[2] = core.raw_read_8(crate::ds_campaign::MISSION, -1) | source_tag(crate::ds_campaign::source(core));
    b[3] = VERSION;
    b[4..8].copy_from_slice(&core.raw_read_32(crate::ds_campaign::COUNTDOWN, -1).to_le_bytes());
    core.raw_read_range(crate::ds_campaign::FLAGS, -1, &mut b[8..24]);
    core.raw_read_range(
        crate::ds_campaign_rules::MTE_TOLD,
        -1,
        &mut b[24..24 + DS_MTE_LEN as usize],
    );
    b[24 + DS_MTE_LEN as usize..].copy_from_slice(&crate::onyx::saved(core));
    core.raw_write_range(DS_AT, -1, &b);
    core.gba_mut().cpu_mut().set_gpr(0, slot as i32);
    // A battle on two fronts (crate::two_front): the front not on the
    // screen and the battle's state follow the block (the slot takes more
    // than one sector: AW2's writer splits a record in 0xFAD-byte parts).
    // The mark follows the block, and the pairs' tail when the block carries one ([`MARK_AT`]): it used to be written over the tail (the pairs of a two-front or stage-2 mission were lost
    // on the resume); a reader looks at both places, so a save of the old layout still loads.
    let at = if core.gba().cpu().gpr(2) as u32 >= BLOCK_SIZE + TAG_LEN { BLOCK_SIZE + TAG_LEN } else { BLOCK_SIZE };
    if let Some(k) = crate::stage::saved_state(core) {
        // A mission saved on a later stage (crate::stage): a mark and the stage number follow (5 bytes of the record).
        let mut t = crate::stage::SAVED_MARK.to_le_bytes().to_vec();
        t.push(k);
        core.raw_write_range(BLOCK + at, -1, &t);
        core.gba_mut().cpu_mut().set_gpr(2, (at + t.len() as u32) as i32);
    } else if let Some(fronts) = crate::two_front::saved_state(core) {
        let mut t = FRONTS_MARK.to_le_bytes().to_vec();
        t.extend_from_slice(&fronts);
        core.raw_write_range(BLOCK + at, -1, &t);
        core.gba_mut().cpu_mut().set_gpr(2, (at + t.len() as u32) as i32);
    }
}

/// Where a stage's or a two-front mission's mark may stand after the block: right after it (no pairs, or a save of the old layout) or after the pairs' tail.
pub const MARK_AT: [u32; 2] = [BLOCK_SIZE, BLOCK_SIZE + TAG_LEN];

/// The place in the staging buffer where `mark` stands, if it does.
fn mark_in_buffer(core: &Core, mark: u32) -> Option<u32> {
    MARK_AT.iter().copied().find(|&at| {
        let mut b = [0u8; 4];
        core.raw_read_range(BLOCK + at, -1, &mut b);
        u32::from_le_bytes(b) == mark
    })
}

/// The block's length as AW2 saves it, and the mark of the two-front state
/// saved after it.
const BLOCK_SIZE: u32 = 0xE28;
const FRONTS_MARK: u32 = 0x5446_3254; // "T2FT"

/// The block just applied by a DS mission's Continue: the session's flags
/// and countdown.
fn applied_ds(core: &mut Core) {
    if !crate::ds_campaign::active(core) || core.raw_read_16(DS_AT, -1) != DS_MARK {
        return;
    }
    let mut b = vec![0u8; DS_LEN as usize];
    core.raw_read_range(DS_AT, -1, &mut b);
    core.raw_write_32(
        crate::ds_campaign::COUNTDOWN,
        -1,
        u32::from_le_bytes(b[4..8].try_into().unwrap()),
    );
    core.raw_write_range(crate::ds_campaign::FLAGS, -1, &b[8..24]);
    core.raw_write_range(crate::ds_campaign_rules::MTE_TOLD, -1, &b[24..24 + DS_MTE_LEN as usize]);
    crate::onyx::restore(core, &b[24 + DS_MTE_LEN as usize..]);
    // A mission saved on a later stage: the stage number.
    if let Some(at) = mark_in_buffer(core, crate::stage::SAVED_MARK) {
        let k = core.raw_read_8(BLOCK + at + 4, -1);
        crate::stage::restore_saved(core, k);
        core.raw_write_32(BLOCK + at, -1, 0);
    }
    // A two-front battle's other front and state (saved after the block).
    if let Some(at) = mark_in_buffer(core, FRONTS_MARK) {
        let mut f = vec![0u8; crate::two_front::SAVED_LEN as usize];
        core.raw_read_range(BLOCK + at + 4, -1, &mut f);
        crate::two_front::restore_saved(core, &f);
        core.raw_write_32(BLOCK + at, -1, 0);
    }
}

/// The sector holding the DS mission saved halfway, if AW2's directory
/// lists one.
fn mid_sector(core: &Core, slot: u8) -> Option<u32> {
    // (its first part: a two-front battle's takes two sectors; the sector's
    // +0x0C is part << 4 | parts - 1)
    (0..16).find(|&i| {
        core.raw_read_8(DIRECTORY + i, -1) == slot && core.raw_read_8(FLASH + 0x1000 * i + 0x0C, -1) >> 4 == 0
    })
}

/// The top three bits of a saved mission byte name the campaign when it is neither the DS Campaign's nor the BH Campaign's (those keep 0: their old
/// saves stay valid): the Emerald Sun Campaign (source 2) shares the BH Campaign's slot 12, so the flash keeps fifteen of its sixteen sectors at most.
fn source_tag(source: usize) -> u8 {
    if source >= 2 {
        (source as u8) << 5
    } else {
        0
    }
}

/// The DS mission saved halfway (its index) in `slot`, read from Flash, whatever campaign saved it.
pub fn saved_mission(core: &Core, slot: u8) -> Option<u8> {
    saved_raw(core, slot).map(|b| b & 0x1F)
}

fn saved_raw(core: &Core, slot: u8) -> Option<u8> {
    let at = FLASH + 0x1000 * mid_sector(core, slot)? + 0x52 + (DS_AT - BLOCK);
    (core.raw_read_16(at, -1) == DS_MARK).then(|| core.raw_read_8(at + 2, -1))
}

/// The mission campaign `source` saved halfway (its slot may be shared with another campaign's: only a save of its own counts).
pub fn saved_mission_of(core: &Core, source: usize) -> Option<u8> {
    let slot = crate::campaign_model::SOURCES[source].mid_slot;
    let b = saved_raw(core, slot)?;
    (b & 0xE0 == source_tag(source)).then_some(b & 0x1F)
}

/// [`drop_mid`] for campaign `source`'s own save only (a shared slot may hold another campaign's).
pub fn drop_mid_of(core: &mut Core, source: usize) {
    let slot = crate::campaign_model::SOURCES[source].mid_slot;
    match saved_raw(core, slot) {
        Some(b) if b & 0xE0 != source_tag(source) => {}
        _ => drop_mid(core, slot),
    }
}

/// DS CAMPAIGN's Continue over a mission saved halfway (the session set
/// up): AW2's own resume of [`DS_SLOT`], tail-called from the trapped
/// Continue handler's first instruction (it returns to its caller).
pub fn resume_mid(core: &mut Core, slot: u8) {
    // A two-front battle saved on its second front (a player's turn there,
    // crate::two_front): that front's map header in place before AW2's
    // resume loads the map (its state comes back after the block,
    // [`applied_ds`]).
    if let Some(i) = mid_sector(core, slot) {
        // (bytes: the mark is not word-aligned in Flash)
        for place in MARK_AT {
            let at = FLASH + 0x1000 * i + 0x52 + place;
            let mut mark = [0u8; 4];
            core.raw_read_range(at, -1, &mut mark);
            if u32::from_le_bytes(mark) == FRONTS_MARK {
                let live = core.raw_read_8(at + 4, -1);
                crate::two_front::continue_on(core, live);
            }
            if u32::from_le_bytes(mark) == crate::stage::SAVED_MARK {
                let k = core.raw_read_8(at + 4, -1);
                crate::stage::continue_on(core, k);
            }
        }
    }
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, slot as i32);
    cpu.set_thumb_pc(RESUME);
}

/// The DS mission saved halfway is over (won or lost) or a new DS Campaign
/// is started: its slot leaves AW2's directory as AW2's delete does it
/// (`sub_0801ABF8`), to be written with the next save.
pub fn drop_mid(core: &mut Core, slot: u8) {
    for i in 0..16 {
        if core.raw_read_8(DIRECTORY + i, -1) == slot {
            core.raw_write_8(DIRECTORY + i, -1, 0xFF);
            core.raw_write_8(DIRECTORY + 0x10 + i, -1, 0xFF);
        }
    }
}

/// `SaveScreenCampaign_StartMessage` clears AW2's campaign suspend mark (`sub_08016CEC(2, 0)`: the prompt after a mission, as AW2's own campaign's
/// save replaces the old one). In a DS, BH or Emerald Sun session the mission AW2 saved halfway in slot 2 is still there: the mark is noted at the
/// prompt's start ([`note_aw2_mark`]) and put back after the clearing ([`keep_aw2_mark`], at [`AFTER_MARK_CLEAR`]).
pub const AFTER_MARK_CLEAR: u32 = 0x0803_D944;
/// 0x80 | AW2's campaign mark at the prompt's start, while a session's prompt is up.
const NOTED_MARK: u32 = 0x0203_FFAE;
pub fn note_aw2_mark(core: &mut Core) {
    if crate::ds_campaign::active(core) {
        let mark = core.raw_read_8(CAMPAIGN_MARK, -1);
        core.raw_write_8(NOTED_MARK, -1, 0x80 | mark);
    }
}
pub fn keep_aw2_mark(core: &mut Core) {
    let noted = core.raw_read_8(NOTED_MARK, -1);
    if noted & 0x80 != 0 {
        core.raw_write_8(NOTED_MARK, -1, 0);
        core.raw_write_8(CAMPAIGN_MARK, -1, noted & 0x7F);
    }
}

// --- A Survival map saved halfway ------------------------------------------------

/// The Flash slot of a Survival map saved halfway (tangoAW2's; 9 was free).
/// The War Room's map menu saves in slot 3 (`sub_08016D04(2)`); a Survival
/// map is saved here instead, so a War Room game saved halfway and its mark
/// (`0x0200C42A`) are kept, as the DS Campaign's [`DS_SLOT`] keeps AW2's.
pub const SURVIVAL_SLOT: u8 = 9;
const WAR_ROOM_SLOT: u32 = 3;
/// AW2's War Room suspend mark in the profile (`sub_08016C9C(3)`).
const WAR_ROOM_MARK: u32 = 0x0200_C42A;
/// The run in the block's tail, where a DS mission keeps its session (the
/// two never run together): +0 [`SV_MARK`], +2 version, +3 kind, +4 the
/// Champion course, +5 maps cleared, +6 the CO, +7 its partner, +8 out of
/// budget, +0x0C what is left, +0x10 the budget, +0x14 points, +0x18 the
/// map's time, +0x1C the funds cap, +0x20 the last map's score (u16).
const SV_AT: u32 = DS_AT;
const SV_MARK: u16 = 0x5653; // "SV"
pub const SV_LEN: usize = 0x24;

/// The run's fields as the block's tail keeps them
/// ([`crate::survival::saved_run`] / [`crate::survival::restore_run`]).
pub type SurvivalRun = [u8; SV_LEN];

/// The Survival map saved halfway, read from Flash: the run's tail (its
/// mark checked), if AW2's directory lists the slot.
pub fn survival_saved(core: &Core) -> Option<SurvivalRun> {
    let at = FLASH + 0x1000 * mid_sector(core, SURVIVAL_SLOT)? + 0x52 + (SV_AT - BLOCK);
    let mut b = [0u8; SV_LEN];
    // (bytes: the tail is not word-aligned in Flash)
    for (k, v) in b.iter_mut().enumerate() {
        *v = core.raw_read_8(at + k as u32, -1);
    }
    (u16::from_le_bytes([b[0], b[1]]) == SV_MARK && b[2] == VERSION).then_some(b)
}

/// Flash sectors a write needs free: the slot's new copy and the new
/// profile (AW2's writer never reuses the old copies' sectors).
const WRITE_NEEDS: usize = 2;

/// Whether a Survival map can be saved now: the slot's write fits, and
/// after it every one-sector save still has the two free sectors it needs
/// (with every other slot in use, docs/AW2.md "Saves", the room left is
/// exactly that).
pub fn survival_save_fits(core: &Core) -> bool {
    let free = (0..16).filter(|&i| core.raw_read_8(DIRECTORY + i, -1) == 0xFF).count();
    let held = (0..16).any(|i| core.raw_read_8(DIRECTORY + i, -1) == SURVIVAL_SLOT);
    let after = if held { free } else { free.saturating_sub(1) };
    free >= WRITE_NEEDS && after >= WRITE_NEEDS
}

/// While a Survival map is being saved: 0x80 | the War Room's mark as it
/// was (Survival's own byte, crate::survival::SAVING).
fn survival_save_start(core: &mut Core) {
    if !crate::survival::playing(core) || core.gba().cpu().gpr(4) as u32 != WAR_ROOM_SLOT {
        return;
    }
    let mark = core.raw_read_8(WAR_ROOM_MARK, -1);
    core.raw_write_8(crate::survival::SAVING, -1, 0x80 | mark);
}

/// At the slot writer's call: the slot made [`SURVIVAL_SLOT`], the War
/// Room's mark put back (before the writer serializes the profile), the run
/// in the tail.
fn survival_save_write(core: &mut Core) {
    let saving = core.raw_read_8(crate::survival::SAVING, -1);
    if saving & 0x80 == 0 {
        return;
    }
    core.raw_write_8(crate::survival::SAVING, -1, 0);
    core.raw_write_8(WAR_ROOM_MARK, -1, saving & 0x7F);
    let mut b = crate::survival::saved_run(core);
    b[0..2].copy_from_slice(&SV_MARK.to_le_bytes());
    b[2] = VERSION;
    core.raw_write_range(SV_AT, -1, &b);
    core.gba_mut().cpu_mut().set_gpr(0, SURVIVAL_SLOT as i32);
}

/// The block just applied by Survival's Continue
/// ([`crate::survival::resuming`]): the run back, the skills its armies had
/// on (a map start sets them; a Continue has none), before the tag pairs
/// ([`applied`]) give the partner its own.
fn applied_survival(core: &mut Core) {
    if !crate::survival::resuming(core) {
        return;
    }
    let mut b = [0u8; SV_LEN];
    core.raw_read_range(SV_AT, -1, &mut b);
    if u16::from_le_bytes([b[0], b[1]]) != SV_MARK {
        return;
    }
    crate::survival::restore_run(core, &b);
    // Read once: a War Room game saved later in the same buffer is not one.
    core.raw_write_16(SV_AT, -1, 0);
    crate::co_skills::clear(core);
    crate::co_skills::battle_start(core);
}

/// Survival's Continue (`MainMenuWarRoom_Continue`'s first instruction,
/// the mode its pick stores: [`crate::survival`]): AW2's own resume of
/// [`SURVIVAL_SLOT`] in place of the War Room's slot 3, tail-called (it
/// returns to the mode dispatcher).
pub const WAR_ROOM_CONTINUE: u32 = 0x0803_B904;
/// `StartWarRoom` (mode 5's handler): Survival's SELECT MAP when its slot
/// has gone.
const WAR_ROOM_NEW: u32 = 0x0803_BA00;
fn war_room_continue(core: &mut Core) {
    let Some(resume) = crate::survival::continue_now(core) else {
        return;
    };
    let cpu = core.gba_mut().cpu_mut();
    if resume {
        cpu.set_gpr(0, SURVIVAL_SLOT as i32);
        cpu.set_thumb_pc(RESUME);
    } else {
        cpu.set_thumb_pc(WAR_ROOM_NEW);
    }
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![
        (CAPTURED, Box::new(captured)),
        (LOADED, Box::new(loaded)),
        (
            APPLIED,
            Box::new(|core: &mut Core| {
                five_restore(core);
                applied_survival(core);
                applied(core);
                applied_ds(core);
            }),
        ),
        (
            SAVE_START,
            Box::new(|core: &mut Core| {
                save_start(core);
                survival_save_start(core);
            }),
        ),
        (
            SAVE_WRITE,
            Box::new(|core: &mut Core| {
                save_write(core);
                survival_save_write(core);
            }),
        ),
        (WAR_ROOM_CONTINUE, Box::new(war_room_continue)),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_five_army_record_fits_the_slot() {
        // AW2's block, the pairs' tail, the record's head and the worst case of the state (every unit id in use): two Flash sectors.
        let worst = BLOCK_SIZE + TAG_LEN + FIVE_HEAD + crate::five::SAVED_MAX as u32;
        assert!(worst <= SLOT_MAX, "{worst} bytes");
        assert!(worst <= STAGING);
        // (the reader's places are inside the buffer)
        assert!(FIVE_AT.iter().all(|&a| a + FIVE_HEAD < STAGING));
    }

    /// The stage's / two-front mark has a place of its own after the pairs' tail (it was written over the tail): the two places are different, and the longest record (the other front's state after the
    /// pairs) still fits the staging buffer and the slot's two sectors.
    #[test]
    fn the_fronts_mark_does_not_overlap_the_pairs_tail() {
        assert_eq!(MARK_AT, [BLOCK_SIZE, BLOCK_SIZE + TAG_LEN]);
        assert!(MARK_AT[1] >= MARK_AT[0] + TAG_LEN, "the second place starts after the tail");
        assert_eq!(TAG_AT - BLOCK, MARK_AT[0], "the tail starts at the first place");
        let longest = MARK_AT[1] + 4 + crate::two_front::SAVED_LEN;
        assert!(longest <= STAGING && longest <= SLOT_MAX, "{longest} bytes");
    }

    #[test]
    fn tail_fits_the_block() {
        assert!(TAIL + TAIL_LEN <= BLOCK + BLOCK_LEN);
        assert!(DS_AT + DS_LEN <= BLOCK + BLOCK_LEN);
        assert!(SV_AT + SV_LEN as u32 <= BLOCK + BLOCK_LEN);
        // The longer write still fits one Flash sector (payload from +0x52,
        // the profile's directory from +0xFEF).
        assert!(0x52 + BLOCK_LEN + TAG_LEN <= 0xFEF);
        assert_eq!(TAG_AT, BLOCK + BLOCK_LEN);
    }
}
