//! Advance Wars 2: Black Hole Rising (USA, `AW2E`).
//!
//! Netplay runs the game's own hot-seat Versus mode on one console that
//! both peers simulate (see `tango_backend_mgba::shared`). The save is
//! the cartridge's 64 KiB Flash, carried as an opaque image: seat 0's
//! save boots the shared console, so the host's unlocks are the match's.

#[cfg(feature = "ui")]
pub mod ui {
    pub use tango_gamesupport_common_ui::editor::EMPTY_SAVE_EDITOR as SAVE_EDITOR;
}

pub mod ai_debug;
pub mod ally_posture;
pub mod army_skin;
pub mod asuka;
pub mod battle_points;
pub mod bh_act1;
pub mod bh_act2;
pub mod bh_act3;
pub mod bh_act4;
pub mod bh_act5;
pub mod bh_act5b;
pub mod bh_ai;
pub mod bh_campaign;
pub mod bh_factory;
pub mod bh_map_data;
pub mod bh_secret;
pub mod bh_smart;
pub mod bh_text;
pub mod bond_ui;
pub mod branding;
pub mod campaign_menu;
pub mod campaign_model;
pub mod campaign_music;
pub mod co_grid;
pub mod co_new;
pub mod co_powers;
pub mod co_roster;
pub mod co_skills;
pub mod com_tower;
pub mod cpu_inventions;
pub mod cpu_tactics;
pub mod crumb;
pub mod crumb_art;
pub mod custom_campaign;
pub mod design;
pub mod design5;
pub mod design_bar;
pub mod design_random;
pub mod ds_ai;
pub mod ds_ai_build;
pub mod ds_ai_move;
pub mod ds_ai_power;
pub mod ds_art;
pub mod ds_backdrop;
pub mod ds_battle;
pub mod ds_campaign;
pub mod ds_campaign_data;
pub mod ds_campaign_rules;
pub mod ds_co_art;
pub mod ds_co_page;
pub mod ds_co_wall;
pub mod ds_coselect;
pub mod ds_credits;
pub mod ds_cursor;
pub mod ds_graphics;
pub mod ds_ground;
pub mod ds_hud;
pub mod ds_look;
pub mod ds_maps;
pub mod ds_menus;
pub mod ds_music;
pub mod ds_pack;
mod ds_plans;
pub mod ds_power_art;
pub mod ds_story_art;
pub mod ds_tilt;
pub mod ds_unit_art;
pub mod ds_unit_pictures;
pub mod ds_units;
pub mod ds_versus;
pub mod ds_weather;
pub mod ds_worldmap;
pub mod es_act1;
pub mod es_act2;
pub mod es_act3;
pub mod es_act4;
pub mod es_campaign;
pub mod es_co;
pub mod es_cos;
pub mod es_map_data;
pub mod es_music;
pub mod es_text;
pub mod factory;
pub mod factory_hp;
pub mod five;
mod five_art;
mod five_map;
mod five_map_data;
mod five_patches;
pub mod fog_view;
pub mod grand_bolt;
pub mod hazard;
pub mod heal_effect;
pub mod history;
pub mod history_ui;
pub mod hold_box;
pub mod inspect;
pub mod invention_art;
pub mod lz77;
pub mod map_anim;
pub mod mode_menu;
pub mod obelisk;
mod obelisk_art;
pub mod online;
pub mod online_art;
pub mod online_browse;
pub mod online_conn;
pub mod online_maps;
pub mod online_menu;
pub mod online_stats;
pub mod online_teams;
pub mod onyx;
pub mod oozium;
mod panel_sprites;
pub mod power_anim;
pub mod power_music;
pub mod proxy_seat;
pub mod pvp;
pub mod ram_map;
pub mod result_view;
pub mod resume_info;
pub mod roster;
pub mod run_dump;
pub mod sandstorm;
pub mod setup_phase;
pub mod skills_panel;
pub mod sky_front;
pub mod sturm_pairs;
pub mod survival;
pub mod survival_maps;
pub mod survival_ui;
pub mod suspend;
pub mod tag;
pub mod tag_extras;
pub mod tag_screens;
pub mod tag_thunder;
pub mod tag_ui;
pub mod test_aid;
pub mod title_card;
pub mod two_front;
pub mod unit_actions;
pub mod unit_names;
pub mod unranked;
pub mod versus_rules;
mod volcano;
pub mod wasteland;

use std::sync::LazyLock;
use tango_gamesupport::{Family, Game, Region, SaveTemplates};

/// The cartridge's Flash chip: 512 Kbit.
pub const SAVE_SIZE: usize = 0x10000;

/// The Flash image, opaque: AW2 checks its own save and there is no
/// editor, so nothing here interprets it.
#[derive(Clone)]
pub struct Save(Vec<u8>);

impl Save {
    pub fn new(data: &[u8]) -> Result<Self, tango_gamesupport_common_dataview::save::Error> {
        if data.len() != SAVE_SIZE {
            return Err(tango_gamesupport_common_dataview::save::Error::InvalidSize(data.len()));
        }
        Ok(Save(data.to_vec()))
    }
}

impl tango_gamesupport_common_dataview::save::Save for Save {
    fn to_sram_dump(&self) -> Vec<u8> {
        self.0.clone()
    }
    fn as_raw_wram(&self) -> std::borrow::Cow<'_, [u8]> {
        self.0.as_slice().into()
    }
    fn rebuild_checksum(&mut self) {}
}

/// A fresh cartridge. Everything unlocks at runtime (see `pvp`), so no
/// completed save is needed.
static AW2_T: SaveTemplates = LazyLock::new(|| {
    vec![(
        "",
        tango_gamesupport_common_dataview::wrap_save(Box::new(Save(vec![0xff; SAVE_SIZE]))),
    )]
});

static ENGINE: tango_backend_mgba::SharedBackend = tango_backend_mgba::SharedBackend::new(&pvp::AW2E);

pub static AW2: Game = Game {
    family: &AW2_FAMILY,
    variant: 0,
    rom_code: b"AW2E",
    revision: 0x00,
    crc32: 0x5ad0e571,
    rom_size: 0x800000,
    region: Region::US,
    parse_save_fn: |data| Ok(tango_gamesupport_common_dataview::wrap_save(Box::new(Save::new(data)?))),
    load_rom_assets_fn: None,
    pvp: &ENGINE,
    save_templates: Some(&AW2_T),
    logo_image: None,
};

pub static AW2_FAMILY: Family = Family {
    id: "aw2",
    games: &[&AW2],
    match_types: pvp::MATCH_TYPES,
    players_colored_by_seat: true,
    translations: &[("en-US", include_str!("../locales/en-US/aw2.ftl"))],
};

pub static FAMILIES: &[&Family] = &[&AW2_FAMILY];
