//! Music for a custom campaign's scenes (docs/dev/campaign-scenes.md).
//!
//! AW2's own campaign plays a song under every story scene: Black Hole's officers' scenes 411, the allies' 413, Sturm's citadel 220, a CO's own scene that CO's
//! theme (Hawke 402, Hachi 302), the prologue 425, the world map 424 (found by scanning the ROM's event scripts for op 0x41 and tracing the opening:
//! `aw2dev campaign trace`). Dual Strike's mission scripts name the same roles (`BGM_ENEMY_EVENT1`, `BGM_ALLY_EVENT1`, `BGM_HAGEVOLT_EVENT1` ...).
//! A scene names a [`Track`]; the compiler turns it into AW2's song id (a Dual Strike song of the pack where the pack has it, AW2's like song otherwise).
//!
//! The game's own ops do the fading: op 0x41 hands the song to the music proc (`0x0803B55C`: the old song fades out, the new one starts) and op 0x42 fades the
//! music out (`0x0803B5E8`); a scene that plays a song starts with the first and ends with the second (on a battle map: the CO's theme comes back at the next
//! turn) or with the world map's song (a scene on the world map).

use mgba::core::Core;

/// A song a scene plays.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Track {
    /// An AW2 song id (the game's song table, 0..505).
    Aw2(u16),
    /// A Dual Strike story song (its sequence id in the pack, [`crate::ds_music::STORY_SONGS`]), and the AW2 song that stands in without it.
    Ds { seq: u16, like: u16 },
    /// A CO's own theme (AW2's table row, a new CO's Dual Strike theme).
    Co(u8),
}

/// AW2's song for the world map and the prologue, and for a scene on the map's backdrop.
pub const WORLD_MAP_AW2: u16 = 424;
pub const PROLOGUE_AW2: u16 = 425;
pub const MISSION_CARD_AW2: u16 = 404;

/// The roles the BH Campaign's scenes use, by name (`@SONG name` in `bh_text/*.txt`): (name, track, what it is for).
pub const NAMED: &[(&str, Track, &str)] = &[
    (
        "opening",
        Track::Ds {
            seq: 0x29,
            like: PROLOGUE_AW2,
        },
        "the campaign's opening (Dual Strike's BGM_OPENING1; AW2's prologue song without the pack)",
    ),
    (
        "enemy1",
        Track::Ds { seq: 0x16, like: 411 },
        "Black Hole's officers' scene: grim briefing (BGM_ENEMY_EVENT1; AW2 411)",
    ),
    (
        "enemy2",
        Track::Ds { seq: 0x17, like: 411 },
        "Black Hole scene, restless (BGM_ENEMY_EVENT2; AW2 411)",
    ),
    (
        "ally1",
        Track::Ds { seq: 0x19, like: 413 },
        "the Accord's scene: council, resolve (BGM_ALLY_EVENT1; AW2 413)",
    ),
    (
        "ally2",
        Track::Ds { seq: 0x1A, like: 413 },
        "the Accord's scene, warmer (BGM_ALLY_EVENT2; AW2 413)",
    ),
    (
        "entry",
        Track::Ds { seq: 0x2C, like: 413 },
        "an arrival, someone steps onto the stage (BGM_ALLY_ENTRY1; AW2 413)",
    ),
    (
        "pinch",
        Track::Ds { seq: 0x2D, like: 25 },
        "a crisis: the line is breaking (BGM_EVENT_PINCH1; AW2 25, the song of Orange Star's surrender scenes)",
    ),
    (
        "hagevolt",
        Track::Ds { seq: 0x23, like: 220 },
        "Von Bolt's own scene: ledger, greed, old menace (BGM_HAGEVOLT_EVENT1; AW2 220)",
    ),
    (
        "red",
        Track::Ds { seq: 0x3D, like: 411 },
        "an event of the red side (BGM_EVENT_RED1; AW2 411)",
    ),
    (
        "blue",
        Track::Ds { seq: 0x3E, like: 413 },
        "an event of the blue side (BGM_EVENT_BLUE1; AW2 413)",
    ),
    (
        "sturm",
        Track::Aw2(220),
        "Sturm's scene: the citadel, menace and claim (AW2's song at Sturm's citadel)",
    ),
    ("sturm_theme", Track::Co(10), "Sturm's own CO theme (AW2 219)"),
    ("doom", Track::Aw2(409), "Sturm's last words in AW2: the climax"),
    (
        "final",
        Track::Aw2(420),
        "AW2's last push: 'the enemy is weakening, attack the platform!'",
    ),
    ("world_map", Track::Aw2(WORLD_MAP_AW2), "AW2's world map"),
    (
        "prologue",
        Track::Aw2(PROLOGUE_AW2),
        "AW2's prologue (Sturm and Hawke on the Black Hole map)",
    ),
    (
        "ending1",
        Track::Ds { seq: 0x36, like: 420 },
        "the ending (BGM_NML_ENDING1)",
    ),
    (
        "ending2",
        Track::Ds { seq: 0x37, like: 420 },
        "the secret ending (BGM_NML_ENDING2)",
    ),
];

/// The world map's song: AW2's own on AW2's map (what the game itself plays when a mission returns to the map), Dual Strike's on Omega Land.
pub fn world_map_song(omega_land: bool) -> u16 {
    if omega_land {
        crate::ds_music::story_song(crate::ds_music::WORLD_MAP).unwrap_or(WORLD_MAP_AW2)
    } else {
        WORLD_MAP_AW2
    }
}

/// A track by its name: one of [`NAMED`], `aw2:411` (an AW2 song id), `co:hawke` (a CO's theme by the name `bh_text` knows) is resolved by the caller (see [`parse`]).
pub fn named(name: &str) -> Option<Track> {
    NAMED.iter().find(|n| n.0 == name).map(|n| n.1)
}

/// `name`, `aw2:<id>` or `co:<id>`: the track a `@SONG` line names (CO names are the caller's: `co_by_name`).
pub fn parse(s: &str, co_by_name: impl Fn(&str) -> Option<u8>) -> Option<Track> {
    let s = s.trim();
    if let Some(n) = s.strip_prefix("aw2:") {
        return n.trim().parse().ok().map(Track::Aw2);
    }
    if let Some(n) = s.strip_prefix("co:") {
        return co_by_name(&n.trim().to_uppercase()).map(Track::Co);
    }
    named(&s.to_lowercase())
}

/// AW2's CO table: a row's song at +4.
const CO_TABLE: u32 = 0x085D_3DD0;
const CO_ROW: u32 = 0x104;
const AW2_COS: u8 = 19;

impl Track {
    /// The AW2 song id to play: a Dual Strike story song of the pack when the pack has it, else AW2's like one; a CO's theme from AW2's table, a new
    /// CO's Dual Strike theme (AW2's like CO's without the pack).
    pub fn resolve(self, core: &Core) -> u16 {
        match self {
            Track::Aw2(s) => s,
            Track::Ds { seq, like } => crate::ds_music::story_song(seq).unwrap_or(like),
            Track::Co(co) if co < AW2_COS => core.raw_read_16(CO_TABLE + CO_ROW * co as u32 + 4, -1),
            Track::Co(co) => crate::ds_music::song(co)
                .unwrap_or_else(|| core.raw_read_16(CO_TABLE + CO_ROW * crate::co_new::like(co) as u32 + 4, -1)),
        }
    }

    /// The same without a core (the song table of AW2 is read from `rom`): for tools that list the scenes.
    pub fn resolve_rom(self, rom: &[u8]) -> u16 {
        let read = |co: u8| {
            u16::from_le_bytes([
                rom[(CO_TABLE - 0x0800_0000 + CO_ROW * co as u32 + 4) as usize],
                rom[(CO_TABLE - 0x0800_0000 + CO_ROW * co as u32 + 5) as usize],
            ])
        };
        match self {
            Track::Aw2(s) => s,
            Track::Ds { seq, like } => crate::ds_music::story_song(seq).unwrap_or(like),
            Track::Co(co) if co < AW2_COS => read(co),
            Track::Co(co) => crate::ds_music::song(co).unwrap_or_else(|| read(crate::co_new::like(co))),
        }
    }

    /// A short name for listings: the role's name, `aw2:411`, `co:10`.
    pub fn label(self) -> String {
        if let Some(n) = NAMED.iter().find(|n| n.1 == self) {
            return n.0.to_string();
        }
        match self {
            Track::Aw2(s) => format!("aw2:{s}"),
            Track::Co(c) => format!("co:{c}"),
            Track::Ds { seq, .. } => format!("ds:{seq:#x}"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names_are_unique_and_parse_back() {
        for (i, a) in NAMED.iter().enumerate() {
            assert!(NAMED.iter().skip(i + 1).all(|b| b.0 != a.0), "{} twice", a.0);
            assert_eq!(named(a.0), Some(a.1));
            assert_eq!(a.1.label(), a.0, "{}'s label is its name", a.0);
        }
    }

    #[test]
    fn parse_forms() {
        let co = |n: &str| (n == "HAWKE").then_some(14);
        assert_eq!(parse("sturm", co), Some(Track::Aw2(220)));
        assert_eq!(parse("aw2:411", co), Some(Track::Aw2(411)));
        assert_eq!(parse("co:hawke", co), Some(Track::Co(14)));
        assert_eq!(parse("co:nobody", co), None);
        assert_eq!(parse("nonsense", co), None);
    }

    #[test]
    fn like_songs_are_aw2_songs() {
        for n in NAMED {
            if let Track::Ds { like, .. } = n.1 {
                assert!(like < 505, "{}: the stand-in is one of AW2's own songs", n.0);
            }
        }
    }
}
