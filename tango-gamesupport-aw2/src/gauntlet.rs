//! The Gauntlet mode's plumbing: Select Mode's GAUNTLET entry ([`crate::mode_menu`]) starts one of the Gauntlet maps ([`crate::gauntlet_mode`], docs/dev/gauntlet.md "The
//! Gauntlet mode") on the campaign engine ([`crate::ds_campaign`]: AW2's event engine, which the gauntlet engine needs, runs only in campaign mode), without the campaign's
//! world map, prologue, staff roll or "next mission". The mode is its own campaign **source** (`campaign_model::SOURCES[`[`SOURCE`]`]`) that the Campaign sub-menu never lists.
//!
//! The flow, screen by screen:
//! 1. Select Mode: GAUNTLET (a wheel entry that answers like Battle Maps and Link: A starts the mode at once). The pick stores Campaign's New as the mode and asks
//!    for this source ([`picked`]); the game's own Campaign New handler (trapped, `ds_campaign::start`) runs [`crate::ds_campaign::start_gauntlet`] instead of the campaign's.
//! 2. The start proc ([`start_script`] is `ds_campaign`'s `gauntlet_start_script`): the **map selector** ([`crate::gauntlet_ui`]: the Gauntlet's maps, the enemies each brings in order, the best
//!    result; B goes back to Select Mode), the **CO pick** (AW2's CO screen with every CO the game has: one CO, no partner; B goes back to the selector), the **army colour pick**
//!    (the colours the map's enemies do not wear; B goes back to the CO screen), then `ResetRulesAfterCampaignMap` and the mission proc: the mission card, the intro scene, the battle.
//! 3. The battle, then AW2's own VICTORY / DEFEAT and results screen (score, rank, a record when it beats the best), as in the campaign.
//! 4. The end: `end_of_battle` records the run, `ResetRulesAfterCampaignMap`, and where AW2 would open its world map ([`crate::ds_campaign::AFTER_MAP`]) [`end_script`] runs: the record is
//!    saved, the screen fades and Select Mode comes back. Retrying is picking GAUNTLET again.
//!
//! **Records.** Each map keeps its **top five** results as the War Room does (the same sort, AW2's layout per result: the CO, the days, the score), keyed by the map's own id
//! ([`record_id`]: `gauntlet_NN` is NN, whatever place the map has in the list), saved with this source's record in Flash slot 13 after the BH Campaign's (0x000..0x120) and the BH2
//! Campaign's (0x120..0x240): [`crate::campaign_model::Source::save_offset`] 0x240, magic "AWGA", format [`VERSION`] 2. The slot is shared, so nothing else of it is touched: a record is
//! written by replacing only its own region ([`crate::ds_campaign::merge_record`]). Format 1 (0.9.4: one best word per list position) is converted on load ([`load_record`]).
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

// --- Rules AW2's campaign applies that a Gauntlet run does not want ------------------------------------------------------------------------------------------------------------------------

/// `sub_080261E8(army)`: in campaign mode AW2 offers the Neotank only when the army's colour has its story flag (0x65..0x68; Black Hole's colour none), which a Gauntlet session (every run a
/// first play, no story) never has. Called by the build menu (`0x0802D6CA`). In a Gauntlet session the answer is yes, so every map's bases offer the Neotank as a Versus map with the pack does.
pub const NEOTANK_OPEN: u32 = 0x0802_61E8;
pub fn neotank_open(core: &mut Core) {
    if !session(core) {
        return;
    }
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, 1);
    let lr = cpu.gpr(14) as u32;
    cpu.set_thumb_pc(lr & !1);
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

/// At the map's start: the player's army wears the colour it picked ([`crate::gauntlet_ui`]'s colour pick: one the map's enemies do not wear), or the colour the mission gives it when
/// nothing was picked. AW2's CO screen gives an army the colour of its CO's country (Kanbei's army would be Yellow Comet's, Drake's Green Earth's: the colours of the enemy armies of a
/// map the player picks any CO for), which the Gauntlet's free pick must not do. A skin (Silver Nova) sits on the lowest colour no army has (`army_skin::assign`): [`player_skin`]
/// puts it on while the battle lasts; its designs stay the CO's (the colour only recolours).
pub fn keep_colour(core: &mut Core, m: &crate::campaign_model::MissionInfo) {
    if !session(core) {
        return;
    }
    // (the player's army: the first, or the fifth of a five-army map: Iron Crown's four lines are armies 1..4)
    let five = m.native.as_ref().is_some_and(|n| n.five.is_some());
    let players = core.raw_read_32(0x0849_9598, -1);
    let at = players + 0x3C * if five { 5 } else { 1 } + 0x1A;
    let want = player_colour(core, m, five);
    if core.raw_read_8(at, -1) != want {
        core.raw_write_8(at, -1, want);
    }
    // The enemies keep the colours their map gives them: AW2's CO screen moves an army off a colour another army's CO's country claims (a player's Caulder, whose
    // country is Black Hole's, put Cinder Sea's Hawke on Orange Star's colour, where the Silver Nova skin then sat too: Hawke's army wore Silver Nova's sun).
    let enemies: Vec<(u32, u8)> = if five {
        (1..=4u32).zip(m.colours.iter().copied()).collect()
    } else {
        (2..=4u32).zip(m.colours.iter().skip(1).copied()).collect()
    };
    let count = if five { (m.armies as usize).min(4) } else { (m.armies as usize).saturating_sub(1) };
    for (army, colour) in enemies.into_iter().take(count) {
        let at = players + 0x3C * army + 0x1A;
        if (1..=5).contains(&colour) && core.raw_read_8(at, -1) != colour {
            core.raw_write_8(at, -1, colour);
        }
    }
}

/// The colours the enemies of the map's battle (this stage's record `m`) wear: the armies but the player's.
fn enemy_colours(m: &crate::campaign_model::MissionInfo, five: bool) -> Vec<u8> {
    if five {
        m.colours[..(m.armies as usize).clamp(1, 4)].to_vec()
    } else {
        m.colours[1..(m.armies as usize).clamp(1, 4)].to_vec()
    }
}

/// The colour (1..5) the player's army has in this stage's battle: its pick, a skin's host, or the mission's own.
fn player_colour(core: &Core, m: &crate::campaign_model::MissionInfo, five: bool) -> u8 {
    let choice = crate::ds_campaign::gauntlet_choice(core);
    if choice == 0 {
        return if five { 5 } else { m.colours[0] };
    }
    let mut choices = vec![choice];
    choices.extend(enemy_colours(m, five));
    crate::army_skin::assign(&choices).0[0]
}

/// The skin the player's army wears (its index) and the colour it sits on, once the pick was a skin: from the colour pick on, so the ROM's palettes hold it before the map's graphics load (a
/// palette the game has loaded keeps the colours it was loaded with). The colour is the lowest the enemies of the stage the battle is on do not wear (`army_skin::assign`, as the player's army
/// byte gets it in [`keep_colour`]): on a map with stages the skin moves at the switch (Iron Crown: Black Hole's colour, then Orange Star's against Asuka).
pub fn player_skin(core: &Core) -> Option<(usize, u8)> {
    if !session(core) {
        return None;
    }
    let choice = crate::ds_campaign::gauntlet_choice(core);
    let skin = choice.checked_sub(crate::army_skin::SKIN)? as usize;
    let entry = crate::gauntlet_mode::entries().get(crate::ds_campaign::mission(core) as usize)?;
    let mut choices = vec![choice];
    choices.extend_from_slice(entry.stage_enemies(crate::stage::stage(core) as usize));
    let host = *crate::army_skin::assign(&choices).1.get(skin)?;
    (host != 0 && skin < crate::army_skin::skins().len()).then_some((skin, host))
}

// --- The records: the top five of each map, as the War Room keeps them -------------------------------------------------------------------------------------------------

/// The record's format, the progress record's byte +5: 0 is 0.9.4's (one best word per list position, 8 bytes each from +0x20), 2 the top-five table.
pub const VERSION: u8 = 2;
pub const P_VERSION: u32 = crate::ds_campaign::PROGRESS + 5;
/// The results kept per map (the War Room's five records of a map).
pub const TOP: usize = 5;
/// The table: [`SLOTS`] slots of [`SLOT_LEN`] bytes (+0 the map's id, 0 a free slot; +4.. its five results, best first, one AW2 word each: CO | days << 8 | score << 20), room for
/// [`crate::gauntlet_ui::MAX_MAPS`] (32) maps; in Flash it follows the progress record's 0x20 bytes (a record saved with 16 slots is a prefix of it: the slots after it read as free).
/// In RAM the Gauntlet's record block ([`BLOCK`]) holds the selector's record rows, then the table.
pub const SLOTS: usize = 32;
pub const SLOT_LEN: usize = 0x18;
pub const TABLE_LEN: usize = SLOTS * SLOT_LEN;
/// The Gauntlet's record block in EWRAM (`ram_map`): the War Room record rows the map selector's record box reads, one row of [`ROW`] bytes for each map-table id from
/// [`crate::gauntlet_ui::ROW_BASE`] to 0xFD, then the table. The bytes are time-shared with the Teams screen's borrowed tiles (a Versus screen the Gauntlet never shows), the two-front store
/// (no Gauntlet map has a second front) and the War Room's rows on Dual Strike's maps ([`crate::ds_versus::ROWS`]: kept only while that table is in use, and the Gauntlet runs on Survival's).
pub const BLOCK: u32 = 0x0203_E800;
pub const ROW: u32 = 0x14;
/// The map-table ids the record rows cover (0xFD, the table walk's last id, down to the lowest id the list can use).
pub const ROW_COUNT: u32 = 0xFD - crate::gauntlet_ui::ROW_BASE as u32 + 1;
pub const ROWS: u32 = BLOCK;
pub const ROWS_LEN: u32 = ROW * ROW_COUNT;
pub const TABLE: u32 = BLOCK + ROWS_LEN;
pub const BLOCK_LEN: u32 = ROWS_LEN + TABLE_LEN as u32;
/// The Gauntlet's region of slot 13: the progress record, then the table.
pub const RECORD_LEN: usize = 0x20 + TABLE_LEN;
/// The maps 0.9.4 listed, by the position its records were kept at.
const LEGACY: [&str; 2] = ["gauntlet_01", "gauntlet_02"];

/// A map's id in the records: the number of its `gauntlet_NN` key (the stage keys, `gauntlet_02b`, are not maps).
pub fn record_id(key: &str) -> Option<u8> {
    let n = key.strip_prefix("gauntlet_")?;
    if n.is_empty() || !n.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    n.parse::<u8>().ok().filter(|&v| v != 0)
}

fn word(co: u8, days: u32, score: u32) -> u32 {
    co as u32 | (days & 0xFFF) << 8 | (score & 0xFFF) << 20
}

/// A map's slot in the table (bytes), if it has one.
fn slot_of(table: &[u8], id: u8) -> Option<usize> {
    (0..SLOTS).find(|&s| table[s * SLOT_LEN] == id)
}

/// The results of the map with this id, best first (empty places 0).
pub fn tops(table: &[u8], id: u8) -> [u32; TOP] {
    let mut w = [0u32; TOP];
    if let Some(s) = slot_of(table, id) {
        for (k, w) in w.iter_mut().enumerate() {
            let at = s * SLOT_LEN + 4 + 4 * k;
            *w = u32::from_le_bytes(table[at..at + 4].try_into().unwrap());
        }
    }
    w
}

/// The War Room's place for a new result (`InsertBestScoreRecord`'s search at `0x08017760`): past every record with a higher score, and past those with the same score and no more days; the first
/// record it beats (a lower score, or the same score in more days) is where it goes. 5 means it ranks below all five and is dropped.
pub fn place(results: &[u32; TOP], days: u32, score: u32) -> usize {
    for (k, &w) in results.iter().enumerate() {
        let s = w >> 20;
        if s < score || (s == score && (w >> 8 & 0xFFF) > days) {
            return k;
        }
    }
    TOP
}

/// Inserts a result as the War Room does: sorted by score (more first), then days (fewer first); the fifth falls off. Returns its place (0 first), or None when it ranks below five or the table is
/// full of other maps.
pub fn insert(table: &mut [u8], id: u8, co: u8, days: u32, score: u32) -> Option<usize> {
    let s = slot_of(table, id).or_else(|| slot_of(table, 0))?;
    let mut w = tops(table, id);
    let at = place(&w, days, score);
    if at >= TOP {
        return None;
    }
    for k in (at + 1..TOP).rev() {
        w[k] = w[k - 1];
    }
    w[at] = word(co, days, score);
    table[s * SLOT_LEN] = id;
    for (k, w) in w.iter().enumerate() {
        table[s * SLOT_LEN + 4 + 4 * k..][..4].copy_from_slice(&w.to_le_bytes());
    }
    Some(at)
}

/// 0.9.4's records (one word per list position, 8 bytes each: Normal and an unused Hard) as a table: each position's best is the first place of its map.
pub fn migrate(old: &[u8]) -> Vec<u8> {
    let mut t = vec![0u8; TABLE_LEN];
    for (k, key) in LEGACY.iter().enumerate() {
        let Some(w) = old.get(8 * k..8 * k + 4).map(|b| u32::from_le_bytes(b.try_into().unwrap())) else { continue };
        let Some(id) = record_id(key) else { continue };
        if w != 0 {
            let s = k;
            t[s * SLOT_LEN] = id;
            t[s * SLOT_LEN + 4..s * SLOT_LEN + 8].copy_from_slice(&w.to_le_bytes());
        }
    }
    t
}

fn table(core: &Core) -> Vec<u8> {
    let mut t = vec![0u8; TABLE_LEN];
    core.raw_read_range(TABLE, -1, &mut t);
    t
}

/// The mission's map id in the records.
fn mission_id(mission: usize) -> Option<u8> {
    record_id(crate::gauntlet_mode::entries().get(mission)?.key)
}

/// A map's five results as the table in RAM holds them (best first).
pub fn results_of(core: &Core, mission: usize) -> [u32; TOP] {
    mission_id(mission).map_or([0; TOP], |id| tops(&table(core), id))
}

/// A record just made: the result goes in its place in the map's five (a win only: the caller says), the table is the session's until [`crate::ds_campaign::stage_custom`] saves it. The best of
/// each map is also its word in the campaign records by list position ([`best`]: what `battle_points` reads as the best before a battle).
pub fn record(core: &mut Core, mission: usize, co: u8, days: u32, score: u32) -> Option<usize> {
    let id = mission_id(mission)?;
    let mut t = table(core);
    let at = insert(&mut t, id, co, days, score);
    if at.is_some() {
        core.raw_write_range(TABLE, -1, &t);
        mirror(core);
    }
    at
}

/// Every listed map's best result (its first place) as its word in the campaign records, by list position.
pub fn mirror(core: &mut Core) {
    let t = table(core);
    for e in crate::gauntlet_mode::entries().iter().take(crate::campaign_model::MAX_MISSIONS) {
        let w = record_id(e.key).map_or(0, |id| tops(&t, id)[0]);
        let at = crate::ds_campaign::RECORDS + 8 * e.mission as u32;
        if core.raw_read_32(at, -1) != w {
            core.raw_write_32(at, -1, w);
        }
    }
}

/// The record's region as it is saved: the progress record, then the table.
pub fn region(core: &Core) -> Vec<u8> {
    let mut own = vec![0u8; RECORD_LEN];
    core.raw_read_range(crate::ds_campaign::PROGRESS, -1, &mut own[..0x20]);
    own[5] = VERSION;
    own[0x20..].copy_from_slice(&table(core));
    own
}

/// Loads the region saved in Flash (progress, then the table, or 0.9.4's records: converted) into RAM.
pub fn load_record(core: &mut Core, b: &[u8]) {
    core.raw_write_range(crate::ds_campaign::PROGRESS, -1, &[0u8; 0x20]);
    let n = b.len().min(0x20);
    core.raw_write_range(crate::ds_campaign::PROGRESS, -1, &b[..n]);
    let rest = b.get(0x20..).unwrap_or(&[]);
    let mut t = if b.get(5).copied() == Some(VERSION) { rest.to_vec() } else { migrate(rest) };
    t.resize(TABLE_LEN, 0);
    core.raw_write_range(TABLE, -1, &t[..TABLE_LEN]);
    core.raw_write_8(P_VERSION, -1, VERSION);
    mirror(core);
}

/// A new, empty record (nothing saved yet).
pub fn fresh(core: &mut Core) {
    core.raw_write_range(TABLE, -1, &vec![0u8; TABLE_LEN]);
    core.raw_write_8(P_VERSION, -1, VERSION);
    mirror(core);
}

#[cfg(test)]
mod tests {
    use super::*;

    fn w(co: u8, days: u32, score: u32) -> u32 {
        word(co, days, score)
    }

    #[test]
    fn ids_come_from_the_key() {
        assert_eq!(record_id("gauntlet_01"), Some(1));
        assert_eq!(record_id("gauntlet_12"), Some(12));
        assert_eq!(record_id("gauntlet_02b"), None);
        assert_eq!(record_id("gauntlet_"), None);
        assert_eq!(record_id("gauntlet_00"), None);
        assert_eq!(record_id("bh_03"), None);
        let ids: Vec<_> = crate::gauntlet_mode::entries().iter().map(|e| record_id(e.key)).collect();
        assert!(ids.iter().all(|i| i.is_some()), "every map has a record id");
        let mut u: Vec<_> = ids.clone();
        u.sort();
        u.dedup();
        assert_eq!(u.len(), ids.len(), "and no two share one");
    }

    #[test]
    fn the_layout_fits_slot_13_and_leaves_room_for_thirty_two_maps() {
        assert!(SLOTS >= 32);
        assert_eq!(RECORD_LEN, 0x20 + 32 * 0x18);
        assert!(SAVE_OFFSET as usize + RECORD_LEN <= 0xFAE, "the sector's payload");
        assert!(ROWS + ROWS_LEN <= TABLE, "the selector's rows and the table do not overlap");
        assert!(TABLE + TABLE_LEN as u32 <= BLOCK + BLOCK_LEN);
        // a record saved with 16 slots (the first top-five build) is a prefix of today's: its table loads whole and the new slots are free
        assert_eq!(0x20 + 16 * SLOT_LEN, 0x1A0);
    }

    #[test]
    fn results_sort_as_the_war_room_sorts_them() {
        let mut t = vec![0u8; TABLE_LEN];
        // five wins in sequence: 300, 500, 100, 400, 200 points
        for (k, (days, score)) in [(10, 300), (12, 500), (9, 100), (11, 400), (8, 200)].into_iter().enumerate() {
            assert_eq!(insert(&mut t, 1, 1 + k as u8, days, score), Some([0, 0, 2, 1, 3][k]));
        }
        let scores = tops(&t, 1).map(|x| x >> 20);
        assert_eq!(scores, [500, 400, 300, 200, 100]);
        // a sixth, worse than all five, is dropped
        assert_eq!(insert(&mut t, 1, 9, 5, 50), None);
        assert_eq!(tops(&t, 1).map(|x| x >> 20), [500, 400, 300, 200, 100]);
        // a better one goes in its place and pushes the fifth out
        assert_eq!(insert(&mut t, 1, 9, 7, 350), Some(2));
        assert_eq!(tops(&t, 1).map(|x| x >> 20), [500, 400, 350, 300, 200]);
        assert_eq!(tops(&t, 1)[2] as u8, 9, "with its CO");
        // the same score: fewer days first, equal days after the old one
        assert_eq!(insert(&mut t, 1, 3, 20, 500), Some(1), "same score, more days: after the first");
        assert_eq!(insert(&mut t, 1, 4, 5, 500), Some(0), "same score, fewer days: first");
        assert_eq!(insert(&mut t, 1, 5, 5, 500), Some(1), "the same days: after the one there");
        assert_eq!(tops(&t, 1), [w(4, 5, 500), w(5, 5, 500), w(2, 12, 500), w(3, 20, 500), w(4, 11, 400)]);
    }

    #[test]
    fn maps_have_slots_of_their_own() {
        let mut t = vec![0u8; TABLE_LEN];
        insert(&mut t, 2, 1, 10, 300).unwrap();
        insert(&mut t, 1, 2, 11, 400).unwrap();
        insert(&mut t, 2, 3, 12, 600).unwrap();
        assert_eq!(tops(&t, 1), [w(2, 11, 400), 0, 0, 0, 0]);
        assert_eq!(tops(&t, 2), [w(3, 12, 600), w(1, 10, 300), 0, 0, 0]);
        assert_eq!(tops(&t, 3), [0; 5]);
        // thirty-two maps fit, a thirty-third does not
        let mut t = vec![0u8; TABLE_LEN];
        for id in 1..=32u8 {
            assert!(insert(&mut t, id, 1, 5, 100).is_some());
        }
        assert_eq!(insert(&mut t, 33, 1, 5, 100), None);
        assert!(insert(&mut t, 32, 1, 5, 200).is_some(), "a map that has a slot still takes results");
    }

    #[test]
    fn the_old_single_best_record_becomes_the_first_place() {
        let mut old = vec![0u8; 0xE0];
        old[0..4].copy_from_slice(&w(7, 14, 777).to_le_bytes()); // Cinder Sea
        old[8..12].copy_from_slice(&w(6, 30, 555).to_le_bytes()); // Iron Crown
        let t = migrate(&old);
        assert_eq!(tops(&t, 1), [w(7, 14, 777), 0, 0, 0, 0]);
        assert_eq!(tops(&t, 2), [w(6, 30, 555), 0, 0, 0, 0]);
        assert_eq!(tops(&t, 3), [0; 5]);
        assert_eq!(migrate(&[0u8; 0xE0]), vec![0u8; TABLE_LEN]);
    }

    #[test]
    fn a_war_room_row_places_like_the_game() {
        // (the game: past higher scores, and past equal scores in no more days)
        let row = [w(1, 10, 500), w(1, 10, 400), w(1, 10, 400), 0, 0];
        assert_eq!(place(&row, 10, 400), 3);
        assert_eq!(place(&row, 9, 400), 1);
        assert_eq!(place(&row, 10, 600), 0);
        assert_eq!(place(&row, 3, 50), 3);
        assert_eq!(place(&[w(1, 1, 9); 5], 1, 1), 5);
    }
}
