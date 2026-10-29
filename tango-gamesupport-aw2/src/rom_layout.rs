//! The ROM image's free space, in one place (tests only).
//!
//! tangoAW2 grows the cartridge's 8 MB image to 32 MB and keeps its own data in the part past the game (`0x08800000..0x0A000000`): the Dual Strike
//! music, Survival, the wheel's data, the looks, the Dual Strike Campaign, the Versus and tangoAW2's maps, the Dual Strike graphics, the army skins.
//! Each module owns a range and names it with constants of its own; nothing but a test ever compared them, and twice a range grew into another's (the Dual
//! Strike backup of colour 5 over the skin's table of figures: a build menu that decompressed a palette over the game's memory; the screen of the skills
//! over the fourth look's rivers). This module lists every range beside the others and the tests fail when two overlap, when a range leaves the image, or
//! when a module names an address past the game that no range here covers (a new user of free ROM has to be listed before its test passes).
//!
//! Print the map: `cargo test -p tango-gamesupport-aw2 --lib rom_layout -- --nocapture`. Add a range: one line in [`regions`] (and, in the module, the constants
//! its end comes from), then `aw2dev test`. docs/dev/ram-map.md has the table.

/// (start, end, owner): `end` is the first address past the owner's data, taken from the owner's own constants where it has them.
pub(crate) fn regions() -> Vec<(u32, u32, String)> {
    let mut r: Vec<(u32, u32, String)> = Vec::new();
    let mut add = |start: u32, end: u32, name: &str| r.push((start, end, name.to_string()));
    // The Dual Strike music's songs and tables, up to Survival (its own test keeps the blob inside).
    add(crate::ds_music::BASE, 0x08E0_0000, "ds_music: songs and tables");
    // Survival: the table, the maps, the strings (its own test: the strings end before 0x08E40000).
    add(crate::survival::TABLE, 0x08E4_0000, "survival: table, maps, strings");
    add(
        crate::mode_menu::DATA,
        crate::mode_menu::SENTINEL + 4,
        "mode_menu: the wheel's data",
    );
    add(
        crate::online_menu::TEXTS_AT,
        crate::online_menu::SENTINEL + 4,
        "online_menu: texts, wheels, sheet",
    );
    add(
        crate::two_front::ROM,
        crate::two_front::ROM_END,
        "two_front: code and menus",
    );
    add(crate::setup_phase::ROM, crate::setup_phase::ROM_END, "setup_phase");
    add(crate::stage::ROM, crate::stage::ROM_END, "stage: the switch's stubs and script");
    add(
        crate::onyx::ROM,
        crate::onyx::ROM_SENTINEL + 4,
        "onyx: Crystal Calamity's code",
    );
    // One look a biome (Wasteland, Desert, Snow, the Grand Bolt's), each LOOK_SIZE apart and filled to its sentinel; the Normal look further on.
    for b in 1..=crate::wasteland::GRAND_BOLT_LOOK {
        let at = crate::wasteland::look_rom(b);
        add(
            at,
            at + crate::wasteland::AT_SENTINEL + 4,
            &format!("wasteland: look {b}"),
        );
    }
    let normal = crate::wasteland::look_rom(crate::wasteland::DS_NORMAL);
    add(
        normal,
        normal + crate::wasteland::AT_SENTINEL + 4,
        "wasteland: the Normal look",
    );
    add(
        crate::skills_panel::BACKUP,
        crate::skills_panel::BACKUP + crate::skills_panel::CHARS_LEN + crate::skills_panel::MAP_LEN + 0x400,
        "skills_panel: the screen's backup",
    );
    add(
        crate::ds_campaign::DATA,
        crate::ds_campaign::DATA_END,
        "ds_campaign: the campaign's blob",
    );
    add(crate::ds_worldmap::BASE, crate::ds_worldmap::END, "ds_worldmap");
    add(
        crate::ds_music::STORY_BASE,
        crate::ds_music::STORY_END,
        "ds_music: the story's songs",
    );
    add(
        crate::ds_versus::TABLE,
        crate::ds_versus::ROM_END_FOR_MAPS,
        "ds_versus: table, names, Dual Strike's maps",
    );
    add(
        crate::five_map::MAP_DATA,
        crate::five_map::map_data(crate::five_map::MAP_CAPACITY),
        "five_map: tangoAW2's maps",
    );
    add(
        crate::ds_graphics::BLD_NEW,
        crate::ds_graphics::BLD_SENTINEL + 4,
        "ds_graphics: buildings",
    );
    add(
        crate::ds_graphics::UNIT_NEW,
        crate::ds_graphics::UNIT_SENTINEL + 4,
        "ds_graphics: unit sheet",
    );
    add(
        crate::ds_graphics::MOVE_NEW,
        crate::ds_graphics::MOVE_SENTINEL + 4,
        "ds_graphics: moving sheets",
    );
    add(
        crate::ds_graphics::HUD_NEW,
        crate::ds_graphics::HUD_SENTINEL + 4,
        "ds_graphics: HUD",
    );
    add(
        crate::ds_graphics::PIC_NEW,
        crate::ds_graphics::PIC_SENTINEL + 4,
        "ds_graphics: pictures",
    );
    add(
        crate::ds_graphics::MOVE_COUNTRY_NEW,
        crate::ds_graphics::MOVE_COUNTRY_SENTINEL + 4,
        "ds_graphics: the countries' moving sheets",
    );
    // The army skins: their own rooms (header, backups, figures, pictures; `army_skin::rooms` checks them against each other).
    for (start, end, name) in crate::army_skin::rooms() {
        add(start, end, &format!("army_skin: {name}"));
    }
    r
}

/// The image's free space: past the cartridge, up to the 32 MB the image grows to.
pub(crate) const FREE: std::ops::Range<u32> = 0x0880_0000..0x0A00_0000;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_range_lies_in_the_image_and_none_overlaps_another() {
        let mut r = regions();
        r.sort();
        for (s, e, n) in &r {
            println!("{s:#010x}..{e:#010x} {:>7} bytes  {n}", e - s);
            assert!(s < e, "{n}: empty or backwards ({s:#x}..{e:#x})");
            assert!(
                FREE.contains(s) && *e <= FREE.end,
                "{n} ({s:#x}..{e:#x}) leaves the free space of the image"
            );
        }
        for w in r.windows(2) {
            let (a, b) = (&w[0], &w[1]);
            assert!(
                a.1 <= b.0,
                "{} ({:#x}..{:#x}) overlaps {} ({:#x}..{:#x})",
                a.2,
                a.0,
                a.1,
                b.2,
                b.0,
                b.1
            );
        }
        // (the ranges are sorted by start: a range inside a later-starting one is caught by its neighbour)
    }

    /// Every address past the game that a module names in its source lies in a listed range (a module that starts using free ROM has to be added to
    /// [`regions`], where the others can be seen: that is how the Dual Strike backups landed on the skin's figures).
    #[test]
    fn every_address_in_free_rom_that_a_module_names_is_listed() {
        let regions = regions();
        let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("src");
        let mut unlisted = Vec::new();
        for entry in std::fs::read_dir(&dir)
            .unwrap()
            .chain(std::fs::read_dir(dir.join("ai_debug")).unwrap())
        {
            let path = entry.unwrap().path();
            let name = path.file_name().unwrap().to_string_lossy().to_string();
            // (generated map data and texts hold tile ids, not addresses)
            if !name.ends_with(".rs") || name.ends_with("_map_data.rs") || name.contains("_text") {
                continue;
            }
            for (n, line) in std::fs::read_to_string(&path).unwrap().lines().enumerate() {
                let code = line.split("//").next().unwrap();
                let mut rest = code;
                while let Some(i) = rest.find("0x0") {
                    let lit: String = rest[i + 2..]
                        .chars()
                        .take_while(|c| c.is_ascii_hexdigit() || *c == '_')
                        .collect();
                    rest = &rest[i + 2..];
                    let digits: String = lit.chars().filter(|c| *c != '_').collect();
                    if digits.len() != 8 {
                        continue;
                    }
                    let v = u32::from_str_radix(&digits, 16).unwrap();
                    if FREE.contains(&v) && !regions.iter().any(|r| r.0 <= v && v <= r.1) {
                        unlisted.push(format!("{name}:{}: {v:#010x}", n + 1));
                    }
                }
            }
        }
        assert!(
            unlisted.is_empty(),
            "addresses in the image's free space that no range of rom_layout::regions covers:\n{}",
            unlisted.join("\n")
        );
    }
}
