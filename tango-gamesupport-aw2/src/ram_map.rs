//! tangoAW2's own state in EWRAM: where each feature keeps its bytes, in one table, with a test that no two features
//! that can be in use at the same time share a byte.
//!
//! AW2 leaves the top of EWRAM unwritten (found by filling it, playing every screen and reading it back; see
//! docs/AW2.md "Free RAM used"). tangoAW2's features keep their state there, in EWRAM and not in Rust statics, so
//! that rollback, netplay and save states carry it. Each feature claims its region in [`REGIONS`]. Two features may
//! share bytes only when they are never live together (a screen's borrowed buffer and a battle's state), and then the
//! pair is listed in [`TIME_SHARED`] with the reason. The test fails the build when a new region overlaps an old one
//! (the battle scenes' palette copy sat inside the two-front store, and a stored front came back with palette colours
//! for units).
//!
//! Room: 0x0203C000..0x0203DFFF (8 KB) was found unwritten by AW2 through the title, battles on land, sea and in the
//! air, Dual Strike battle scenes, enemy turns and a two-front mission's swaps; new state goes there first.

/// A region: (start, length).
pub type Region = (u32, u32);

/// The battle scenes' copy of the map's OBJ palettes (crate::ds_battle): a held flag at +0, ten rows of 32 bytes
/// from +0x10.
pub const BATTLE_MAP_PALETTES: Region = (0x0203_C000, 0x150);

/// The smart Black Factory (crate::bh_factory): two armies' last four picks (4 bytes each), then their savings (a byte
/// each).
pub const FACTORY: Region = (0x0203_C150, 10);

/// The CO screen: how many picks it had when its cursor was last put on a CO not picked (crate::ds_coselect), + 1.
pub const CO_SCREEN_PICKS: Region = (0x0203_C160, 1);

/// Dual Strike's battle points: the battle's destroyed counts and the last bonus (crate::battle_points).
pub const BATTLE_POINTS: Region = (0x0203_C170, 0x20);

/// Dual Strike's History: its record (crate::history::RECORD), then its screen's state (crate::history_ui).
pub const HISTORY: Region = (0x0203_C190, 0x1A4);
pub const HISTORY_SCREEN: Region = (0x0203_C340, 0x60);

/// Dual Strike's battle rules (0x0203C800..0x0203C8FF reserved for them): the second front's end, what each army
/// brings to the main front (crate::two_front, 4 armies of 8 bytes).
pub const SECOND_FRONT_MERGE: Region = (0x0203_C800, 0x20);

/// Kindle's High Society, counted when her Super Power starts (crate::co_powers): 1 + the bonus per army 1..5 (u16).
pub const HIGH_SOCIETY: Region = (0x0203_C820, 10);

/// Olaf's power snow waiting for its second day (crate::ds_weather).
pub const POWER_SNOW: Region = (0x0203_C830, 1);

/// Covering Fire's and Ex Machina's strike site (crate::co_powers): power, army, missiles picked, set, x, y.
pub const STRIKE_SITE: Region = (0x0203_C840, 8);

/// Dual Strike's CPU (crate::ds_ai): the turn's build list, the profile rolls, the armies' behaviours, the
/// development switches.
pub const DS_AI: Region = (0x0203_C700, 0x100);

/// The army skin (crate::army_skin): the colour it sits on, each Teams-screen army's choice, a flag.
pub const ARMY_SKIN: Region = (0x0203_C500, 0x10);

/// A mission's stage switch (crate::stage): the stage, the swap's flags, the survivors carried (40 units of 12 bytes) with the player's funds, CO and meters.
pub const STAGE: Region = (0x0203_DCA0, 0x20 + 12 * 40);

/// Aria's HP-number ramp on the map (crate::aria_sign): the BG palette bank held plus one, the game's own palette of it.
pub const ARIA_SIGN: Region = (crate::aria_sign::STATE, crate::aria_sign::STATE_LEN);

/// What was in the OBJ tiles Aria's strip is drawn in while it is on (crate::aria_sign::place_strip).
pub const ARIA_STRIP_SAVED: Region = (crate::aria_sign::STRIP_SAVED, crate::aria_sign::STRIP_SAVED_LEN);

/// Every region, by owner.
pub const REGIONS: &[(&str, Region)] = &[
    ("battle scenes: the map's palettes", BATTLE_MAP_PALETTES),
    ("stages: the stage, the swap's flags and the carried survivors (crate::stage)", STAGE),
    ("army skin: the colour it sits on and the Teams screen's choices (crate::army_skin::STATE)", ARMY_SKIN),
    ("the map menu's End row, the item chosen, the last cell and the map menu's own item (crate::pvp::END_ROW)", (crate::pvp::END_ROW, 5)),
    ("the waiting player's fog view: scratch call (crate::fog_view)", (crate::fog_view::CALL, 0x58)),
    ("CO skills' data (crate::co_skills::DATA)", (0x0203_E000, 0x3C6)),
    ("Grand Bolt's borrowed palette (crate::grand_bolt::BORROWED)", (0x0203_E3C8, 0x24)),
    ("Dual Strike graphics switch and the factory's table-only hook", (0x0203_E3FE, 2)),
    ("skills panel", (0x0203_E3F0, 0x0E)),
    ("two fronts: state", (0x0203_E400, 0x100)),
    ("two fronts: the front off the screen", (0x0203_E500, 0xE97)),
    ("BH Campaign: a side's march and spawn state (crate::custom_campaign::SIDE)", (0x0203_F3A0, 0x60)),
    ("tag pairs (crate::tag::STATE)", (0x0203_F400, 0x100)),
    ("tag screens and the CO page's TAG box (crate::tag_extras::STATE)", (0x0203_F500, 0xD8)),
    ("Crumb's healed units", (0x0203_F5D8, 0x28)),
    ("Cassius's Triumph: the units that attacked and have their extra move left, and the army of the last tick (crate::es_co::MOVED_AFTER_ATTACK)", (crate::es_co::MOVED_AFTER_ATTACK, crate::es_co::MOVED_LEN)),
    ("Emerald Sun Campaign: a mission's own counters (crate::es_campaign::STATE)", (0x0203_C9F0, 0x10)),
    ("smart Black Factory: picks and savings", FACTORY),
    ("CO screen: picks seen", CO_SCREEN_PICKS),
    ("Tag Power's thunder: what it covers is kept aside (crate::tag_thunder::STATE)", (0x0203_C600, 1)),
    ("power music: the army whose music is being picked (crate::power_music::ARMY)", (0x0203_C601, 1)),
    ("battle points: destroyed counts", BATTLE_POINTS),
    ("History: the record", HISTORY),
    ("History: the screen", HISTORY_SCREEN),
    ("Dual Strike's Versus and War Room maps (crate::ds_versus::STATE)", (0x0203_C900, 0x20)),
    ("font tiles kept aside while the Black Cannon's picture is in them (crate::obelisk::FONT_KEPT)", (0x0203_CC00, 0x401)),
    ("War Room records on Dual Strike's maps (crate::ds_versus::ROWS)", (0x0203_E500, 0x474)),
    ("second front's end: what each army brings (crate::two_front)", SECOND_FRONT_MERGE),
    ("Kindle's High Society count (crate::co_powers)", HIGH_SOCIETY),
    ("Olaf's power snow's second day (crate::ds_weather)", POWER_SNOW),
    ("Covering Fire / Ex Machina strike site (crate::co_powers)", STRIKE_SITE),
    ("Dual Strike's CPU", DS_AI),
    ("online: the in-game lobby, its mailbox, an online match's walk (crate::online::STATE)", (crate::online::STATE, crate::online::STATE_LEN)),
    ("a seat that is not there: its yield and the room's host seat (crate::proxy_seat)", (crate::proxy_seat::BASE, crate::proxy_seat::LEN)),
    ("online: the lobby browser's state (crate::online_browse::STATE)", (crate::online_browse::STATE, crate::online_browse::STATE_LEN)),
    ("online: the lobby browser's rows (crate::online_browse::ROWS)", (crate::online_browse::ROWS, crate::online_browse::ROWS_LEN)),
    ("online: the gamertag, the record's lines and a room battle's notes (crate::online_stats)", (crate::online_stats::BASE, crate::online_stats::LEN)),
    ("online: the connection status and its page (crate::online_conn)", (crate::online_conn::BASE, crate::online_conn::LEN)),
    ("online: each seat's CO, colour and partner choices in a room (crate::online_teams::SEL)", (crate::online_teams::SEL, crate::online_teams::SEL_LEN)),
    ("online: an UNRANKED match's map proposals and rules (crate::unranked::STATE)", (crate::unranked::STATE, crate::unranked::STATE_LEN)),
    ("offline Versus' map tabs: the maps' own tabs kept aside (crate::online_maps::OFF)", (0x0203_DB00, crate::online_maps::OFF_LEN)),
    ("the map list's rows, moved and enlarged (crate::five_map::LIST)", (crate::five_map::LIST, crate::five_map::LIST_BYTES)),
    ("online: the saved matches' list and the lobby's note (crate::online::SAVED)", (crate::online::SAVED, crate::online::SAVED_LEN)),
    ("DS Campaign's records", (0x0203_F600, 0x100)),
    ("map animations", (0x0203_F740, 0x60)),
    ("power animations", (0x0203_F7A0, 0x40)),
    ("battle scenes: state and effects", (0x0203_F800, 0x200)),
    ("Survival", (0x0203_FA00, 0x310)),
    ("DS Campaign", (0x0203_FD10, 0x50)),
    ("CPU tactics, heal effect, Oozium, stun, battle distance, Teams list", (0x0203_FD60, 0x1A0)),
    ("design list, joypad and invention picks", (0x0203_FF00, 0x100)),
    ("five armies: the player table, moved (crate::five::PLAYERS: six 0x3C-byte slots)", (crate::five::PLAYERS, 6 * 0x3C)),
    ("five armies: army 5's picks and switches (crate::five ARMY5_*, LABEL_PENDING, VISION_DETOUR, FIVE_ON)", (0x0203_0200, 8)),
    ("five armies: the Teams screen's record, moved (crate::five TEAMS, crate::ds_coselect TEAMS_FIVE)", (0x0203_0300, 0xE0)),
    ("five armies: the AI's threat maps, 5 x 0xC00 (crate::five THREAT)", (0x0203_1000, 5 * 0xC00)),
    ("DS Campaign rules: Means to an End / Ring of Fire state, eruption cells, barrier hit points (crate::ds_campaign_rules)", (0x0203_F700, 0x40)),
    ("CO skills' active bitmaps and the luck / special armies (crate::co_skills::ACTIVE)", (crate::co_skills::ACTIVE, 0x20)),
    ("Teams screen: borrowed tiles while partners show", (0x0203_E800, 0x8A0)),
    ("Aria's Vengeance ramp: the BG palette bank held and the game's colours of it (crate::aria_sign::STATE)", ARIA_SIGN),
    ("Aria's strip: the OBJ tiles it is drawn over, kept (crate::aria_sign::STRIP_SAVED)", ARIA_STRIP_SAVED),
    ("Rules screen: borrowed label tiles", (0x0203_F100, 0x200)),
    ("Versus rules: saved label tiles", (0x0203_E600, 0x200)),
];

/// Pairs of regions that overlap but are never in use together, and why.
pub const TIME_SHARED: &[(&str, &str, &str)] = &[
    (
        "two fronts: the front off the screen",
        "Teams screen: borrowed tiles while partners show",
        "the Teams screen is before a battle; a front is stored only during a two-front battle",
    ),
    (
        "two fronts: the front off the screen",
        "Rules screen: borrowed label tiles",
        "the Rules screen is before a battle",
    ),
    (
        "two fronts: the front off the screen",
        "Versus rules: saved label tiles",
        "Versus rules are set before a Versus battle (on one front or two)",
    ),
    (
        "Teams screen: borrowed tiles while partners show",
        "Versus rules: saved label tiles",
        "two screens, never shown together",
    ),
    (
        "War Room records on Dual Strike's maps (crate::ds_versus::ROWS)",
        "two fronts: the front off the screen",
        "the records are in RAM only on the War Room's screens and at its battles' end; during a two-front battle \
         they are given up and read from Flash again",
    ),
    (
        "War Room records on Dual Strike's maps (crate::ds_versus::ROWS)",
        "Teams screen: borrowed tiles while partners show",
        "the Teams screen is Versus'; the records are the War Room's",
    ),
    (
        "War Room records on Dual Strike's maps (crate::ds_versus::ROWS)",
        "Versus rules: saved label tiles",
        "the Rules screen is Versus'; the records are the War Room's",
    ),
];

#[cfg(test)]
mod tests {
    use super::*;

    fn overlaps(a: Region, b: Region) -> bool {
        a.0 < b.0 + b.1 && b.0 < a.0 + a.1
    }

    #[test]
    fn regions_do_not_overlap() {
        let shared = |a: &str, b: &str| {
            TIME_SHARED
                .iter()
                .any(|&(x, y, _)| (x == a && y == b) || (x == b && y == a))
        };
        let mut clashes = Vec::new();
        for (i, &(na, a)) in REGIONS.iter().enumerate() {
            for &(nb, b) in &REGIONS[i + 1..] {
                if overlaps(a, b) && !shared(na, nb) {
                    clashes.push(format!(
                        "{na} {:#x}..{:#x} and {nb} {:#x}..{:#x}",
                        a.0,
                        a.0 + a.1,
                        b.0,
                        b.0 + b.1
                    ));
                }
            }
        }
        assert!(clashes.is_empty(), "EWRAM regions overlap:\n{}", clashes.join("\n"));
    }

    #[test]
    fn regions_match_the_modules() {
        let find = |n: &str| REGIONS.iter().find(|r| r.0.starts_with(n)).unwrap().1;
        assert_eq!(crate::ds_battle::MAP_PALS, BATTLE_MAP_PALETTES.0);
        assert_eq!(find("CO skills").0, crate::co_skills::DATA);
        assert!(find("CO skills").0 + find("CO skills").1 >= crate::co_skills::DATA + crate::co_skills::DATA_LEN);
        assert_eq!(
            find("two fronts: the front off").0 + find("two fronts: the front off").1,
            crate::two_front::STORE_END
        );
        assert_eq!(find("tag pairs").0, crate::tag::STATE);
        assert_eq!(find("tag pairs").0 + find("tag pairs").1, crate::tag::STATE_END);
        assert_eq!(find("DS Campaign's records").0, crate::ds_campaign::RECORDS);
        assert_eq!(find("Survival").0, crate::survival::STATE);
        assert_eq!(
            find("Tag Power's thunder"),
            (crate::tag_thunder::STATE, crate::tag_thunder::STATE_LEN)
        );
        assert_eq!(
            find("power music"),
            (crate::power_music::ARMY, crate::power_music::ARMY_LEN)
        );
        assert_eq!(
            BATTLE_POINTS,
            (crate::battle_points::STATE, crate::battle_points::STATE_LEN)
        );
        assert_eq!(HISTORY, (crate::history::RECORD, crate::history::SAVED_LEN));
        assert_eq!(HISTORY_SCREEN, (crate::history_ui::STATE, crate::history_ui::STATE_LEN));
        assert_eq!(find("Dual Strike's Versus").0, crate::ds_versus::STATE);
        assert!(crate::ds_versus::STATE_LEN <= find("Dual Strike's Versus").1);
        assert_eq!(find("War Room records").0, crate::ds_versus::ROWS);
        assert_eq!(find("War Room records").1, crate::ds_versus::ROWS_LEN);
        assert_eq!(ARMY_SKIN, (crate::army_skin::STATE, crate::army_skin::STATE_LEN));
        assert_eq!(find("five armies: the player table").0, crate::five::PLAYERS);
        assert_eq!(find("DS Campaign rules").0, 0x0203_F700);
        assert_eq!(find("CO skills' active").0, crate::co_skills::ACTIVE);
    }

    /// Every region lies in EWRAM (0x02000000..0x02040000) and the five-army block ends where its threat maps end.
    #[test]
    fn regions_are_in_ewram() {
        for &(n, (a, l)) in REGIONS {
            assert!(
                a >= 0x0200_0000 && a + l <= 0x0204_0000,
                "{n}: {a:#x}+{l:#x} is outside EWRAM"
            );
        }
        let t = REGIONS
            .iter()
            .find(|r| r.0.starts_with("five armies: the AI's threat"))
            .unwrap()
            .1;
        assert_eq!(t.0 + t.1, 0x0203_4C00);
    }
}
