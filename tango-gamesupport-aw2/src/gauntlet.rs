//! The Gauntlet mode's plumbing: Select Mode's GAUNTLET entry ([`crate::mode_menu`]) starts one of the Gauntlet maps ([`crate::gauntlet_mode`], docs/dev/gauntlet.md "The
//! Gauntlet mode") on the campaign engine ([`crate::ds_campaign`]: AW2's event engine, which the gauntlet engine needs, runs only in campaign mode), without the campaign's
//! world map, prologue, staff roll or "next mission". The mode is its own campaign **source** (`campaign_model::SOURCES[`[`SOURCE`]`]`) that the Campaign sub-menu never lists.
//!
//! The flow, screen by screen:
//! 1. Select Mode: GAUNTLET (a wheel entry that answers like Battle Maps and Link: A starts the mode at once). The pick stores Campaign's New as the mode and asks
//!    for this source ([`picked`]); the game's own Campaign New handler (trapped, `ds_campaign::start`) runs [`crate::ds_campaign::start_gauntlet`] instead of the campaign's.
//! 2. The CO pick: AW2's CO screen with every CO the game has (one CO, no partner: the mission's `CoSpec::Pick`; B goes back to Select Mode). The screen is one
//!    proc script ([`start_script`]): fade out, the screen's lists ([`crate::ds_campaign`]'s `FLOW_CO_SETUP`), the CO screen, then (the campaign's own path from its map)
//!    `ResetRulesAfterCampaignMap` and the mission proc: the mission card, the intro scene, the battle.
//! 3. The battle, then AW2's own VICTORY / DEFEAT and results screen (score, rank, a record when it beats the best), as in the campaign.
//! 4. The end: `end_of_battle` records the run, `ResetRulesAfterCampaignMap`, and where AW2 would open its world map ([`crate::ds_campaign::AFTER_MAP`]) [`end_script`] runs: the record is
//!    saved, the screen fades and Select Mode comes back. Retrying is picking GAUNTLET again.
//!
//! **Records.** Each map's best result (AW2's layout: the CO, the days, the score) is the mission's word in the campaign records ([`crate::ds_campaign::RECORDS`]), saved with
//! this source's record in Flash slot 13 after the BH Campaign's (0x000..0x120) and the BH2 Campaign's (0x120..0x240): [`crate::campaign_model::Source::save_offset`]
//! 0x240, magic "AWGA". The slot is shared, so nothing else of it is touched: a record is written by replacing only its own region ([`crate::ds_campaign::merge_record`]).
//!
//! **Save.** The map menu's Save writes the battle in the shared mid-battle slot 12 as the BH Campaigns do, the saved mission's top bits naming this source
//! ([`crate::suspend`]'s `source_tag`: 4 << 5). GAUNTLET on Select Mode continues a saved run (the pick asks for Continue instead of New); holding SELECT with A starts a new one
//! and drops the save. A run's end (won or lost) drops its save.

use mgba::core::Core;

use crate::campaign_model::Model;

/// The Gauntlet's index in [`crate::campaign_model::SOURCES`].
pub const SOURCE: usize = crate::gauntlet_mode::SOURCE;
/// Its record's magic ("AWGA") and place in Flash slot 13 (after the BH and BH2 records).
pub const MAGIC: u32 = 0x4147_5741;
pub const SAVE_OFFSET: u32 = 0x240;

/// 1 while the pick on Select Mode is waiting for its mode store (EWRAM past `ds_campaign::LAST_CONDITION`, free: the DS Campaign's block has no use for it); 2 while the run's end
/// is taking the player back to Select Mode ([`returning`]).
pub const PICKED: u32 = 0x0203_FD54;
const RETURNING: u8 = 2;
/// The wheel's remembered position (the cursor Select Mode opens on) and the Select Mode wheel's procs.
const WHEEL_LAST: u32 = 0x0300_5934;
/// The pick asked for a new run (0) or to continue the saved one (1), kept for [`start_script`]'s callers (the tests).
pub const CONTINUING: u32 = 0x0203_FD55;

/// Keys (REG_KEYINPUT, active low): SELECT.
const KEYINPUT: u32 = 0x0400_0130;
const KEY_SELECT: u16 = 1 << 2;

/// The mode's maps are playable: the Dual Strike pack is on (offline: the wheel only has the entry then, [`crate::mode_menu`]).
pub fn available(core: &Core) -> bool {
    crate::ds_weather::is_on(core)
}

/// The source's `load`: the maps' campaign compiled for the engine.
pub fn load(core: &Core) -> Option<Model> {
    match crate::custom_campaign::compile(core, &crate::gauntlet_mode::def()) {
        Ok(m) => Some(m),
        Err(e) => {
            eprintln!("Gauntlet: {e}");
            None
        }
    }
}

/// The mode's session is on (a Gauntlet map is being chosen, played or left).
pub fn session(core: &Core) -> bool {
    crate::ds_campaign::active(core) && crate::ds_campaign::source(core) == SOURCE
}

/// The wheel's pick (a trap at the item's `cmp r0, #4`): the request for this source, New or (a run saved halfway) Continue.
pub fn picked(core: &mut Core) {
    let saved = crate::suspend::saved_mission_of(core, SOURCE).is_some();
    let fresh = core.raw_read_16(KEYINPUT, -1) & KEY_SELECT == 0;
    let cont = saved && !fresh;
    core.raw_write_8(PICKED, -1, 1);
    core.raw_write_8(CONTINUING, -1, cont as u8);
    core.raw_write_8(crate::ds_campaign::SOURCE, -1, SOURCE as u8);
    core.raw_write_8(crate::ds_campaign::REQUEST, -1, if cont { 2 } else { 1 });
}

/// The pick is waiting for its mode store.
pub fn is_picked(core: &Core) -> bool {
    core.raw_read_8(PICKED, -1) == 1
}

/// The run's end starts the way back to Select Mode: the wheel is to come back on GAUNTLET (AW2's campaign end puts its remembered position back on Campaign, so [`tick`]
/// keeps it until the wheel is up).
pub fn returning(core: &mut Core) {
    core.raw_write_8(PICKED, -1, RETURNING);
    tick(core);
}

/// Every frame: while the way back to Select Mode is on, the wheel's remembered position is the Gauntlet's (the wheel reads it once, as it starts).
pub fn tick(core: &mut Core) {
    if core.raw_read_8(PICKED, -1) != RETURNING {
        return;
    }
    if crate::campaign_menu::wheel_info(core).is_some() {
        core.raw_write_8(PICKED, -1, 0);
        return;
    }
    if let Some(p) = crate::mode_menu::position_of(core, crate::mode_menu::GAUNTLET) {
        if core.raw_read_32(WHEEL_LAST, -1) != p {
            core.raw_write_32(WHEEL_LAST, -1, p);
        }
    }
}

/// The mode has started (the handler ran): the pick is spent.
pub fn consumed(core: &mut Core) {
    core.raw_write_8(PICKED, -1, 0);
}

/// A best result as AW2 keeps it (`best_score`'s word: CO | days << 8 | score << 20), by mission.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Best {
    pub co: u8,
    pub days: u16,
    pub score: u16,
}

pub fn decode(word: u32) -> Option<Best> {
    (word != 0).then_some(Best {
        co: word as u8,
        days: ((word >> 8) & 0xFFF) as u16,
        score: (word >> 20) as u16,
    })
}

/// A mission's best result in the records in RAM (the session's, or the loaded ones).
pub fn best(core: &Core, mission: u8) -> Option<Best> {
    decode(core.raw_read_32(crate::ds_campaign::RECORDS + 8 * mission as u32, -1))
}

/// At the map's start: the player's army keeps the colour the mission gives it. AW2's CO screen gives an army the colour of its CO's country (Kanbei's army would be Yellow
/// Comet's, Drake's Green Earth's: the colours of the enemy armies of a map the player picks any CO for), which the Gauntlet's free pick must not do.
pub fn keep_colour(core: &mut Core, m: &crate::campaign_model::MissionInfo) {
    if !session(core) {
        return;
    }
    let players = core.raw_read_32(0x0849_9598, -1);
    let at = players + 0x3C + 0x1A;
    let want = m.colours[0];
    if core.raw_read_8(at, -1) != want {
        core.raw_write_8(at, -1, want);
    }
}
