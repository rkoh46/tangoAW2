//! The Tag Power's thunder over the map (Dual Strike's "tag break" bolts
//! and their sparks), before crate::tag_screens takes the display, with the
//! Dual Strike pack.
//!
//! **What Dual Strike does** (its script `0x0215C4F4`, the ops of
//! `Task_RunScript`; frame numbers are crate::tag_screens', from the menu's
//! Tag):
//!
//! - `TagBreak_LoadThunder` (141): `/ohashi/res_tagbreak_thunder`'s BG0
//!   tiles (+0, LZ77, 512 tiles), bolt map A (+0x2254) and B (+0x252C),
//!   32x32 each, two BG palettes (+0x280C: A's, then B's), the sparks' OBJ
//!   tiles (+0x284C) and palette (+0x28A8); BG0 blended over every other
//!   layer at EVA = EVB = 16 (additive), and the map dims over 32 frames.
//! - Bolt 1 (173, `PowerScreen_SwapMapWithSparks`): map A in palette slot
//!   1, two spark bursts (`SparkBurst_Start`: (42, 146) 3 frames late and
//!   (172, 112)), `SE_TAG_BREAK` (234); then EVA eases 16 -> 0 over 36
//!   frames (`PowerScreen_EaseOutBlend`, `Math_Ease` curve 1).
//! - Bolt 2 (209, `TagBreak_StartSparks`): map B in B's palette, bursts at
//!   (40, 48) and (158, 86), the sound; EVA 16 -> 0 over 10 frames
//!   (`TagBreak_FadeOutBlend`).
//! - Bolt 3 (219): bolt 1 again (36 frames). Then the tag theme and the
//!   white (crate::tag_screens).
//! - A burst (`SparkBurst_Init` / `_Update`, script `0x0215C2FC`): 36
//!   sparks, one every 10 degrees (end offsets `gSparkBurstOffsets`
//!   `0x0215C35C`, 60 pixels out), each with a random style 0..15: a head
//!   start of 0, 2, 4 or 6 frames and a flight of 32, 16, 24 or 8 frames;
//!   its place and its picture (frames 0..5 of an 8x8 white dot shrinking
//!   8 -> 6 -> 6 -> 4 -> 2 pixels) follow `Math_Ease` curve 4 (`to - (to -
//!   from) (d - t)^2 / d^2`); a spark past its flight is not drawn. The
//!   burst lasts 33 frames.
//!
//! **Here.** The GBA window is Dual Strike's 256x192 screen less 8 pixels
//! each side and 16 above and below, so the bolts and the bursts keep their
//! places on the picture. Each bolt map's tiles in that window (216 and
//! 224) are cut to the 128 of the wave overlay's space, BG0's character
//! block + `0x5600` (as Ex Machina's bolt, crate::power_anim,
//! [`BgLayer::reduced`]), in BG palette 8; the map goes through the game's
//! BG0 buffer. BG0 is raised to priority 0 and blended with BLDALPHA: EVA
//! the bolt's ease, EVB the map's dim (16 less crate::tag_screens' darkening,
//! which BLDY cannot add while the blend is on: the bolt covers the whole
//! screen, so the blend dims everything as the darkening did). The sparks
//! are 8x8 sprites (OBJ tiles `0x1CA..0x1CF`, the meteor's, colour 3 of
//! OBJ palette 15) in sprite-list entries the map leaves parked this frame
//! (crate::power_anim's way); with four bursts up at once there may be
//! fewer entries than sparks, and the ones left out are spread round the
//! bursts. Dual Strike's random styles are a fixed hash of (burst, spark).
//! Everything the thunder covers (the BG0 tiles and buffer, the palettes,
//! the OBJ tiles) is copied first to the start of crate::tag_screens'
//! backup (which the screen only fills from frame 297) and put back when
//! the bolts end or the screen is cut short; the display registers come
//! back from the screen's kept shadows.
//!
//! Everything shown is a function of the screen's frame (RAM): the same on
//! every peer and in every replay.

use mgba::core::Core;
use std::sync::OnceLock;

use crate::ds_power_art::{BgLayer, BgPlacement, Start};

// --- Dual Strike's timing ----------------------------------------------------------

/// The bolts: frame, map (0 A, 1 B), EVA's ease length.
const BOLTS: [(i32, usize, i32); 3] = [(173, 0, 36), (209, 1, 10), (219, 0, 36)];
/// The bolts are up from the first to here (the white starts at 257).
const LAST_FRAME: i32 = 256;
/// The bursts: the bolt's frame, the centre (Dual Strike's screen), the
/// wait before it.
const BURSTS: [(i32, i32, i32, i32); 6] = [(173, 42, 146, 3), (173, 172, 112, 0), (209, 40, 48, 0), (209, 158, 86, 0), (219, 42, 146, 3), (219, 172, 112, 0)];
/// A burst's first frame after its start (the script's 1-frame wait and its
/// init) and its last frame.
const BURST_DELAY: i32 = 2;
const BURST_FRAMES: i32 = 32;
const SPARKS: usize = 36;
/// Dual Strike's screen less the GBA's: the window's top left.
const WINDOW_X: i32 = 8;
const WINDOW_Y: i32 = 16;

/// `Math_Ease` curve 1: `from + (to - from) t^2 / d^2`.
fn ease_in(from: i32, to: i32, t: i32, d: i32) -> i32 {
    from + (to - from) * t * t / (d * d)
}

/// `Math_Ease` curve 4: `to - (to - from) (d - t)^2 / d^2`.
fn ease_out(from: i32, to: i32, t: i32, d: i32) -> i32 {
    to - (to - from) * (d - t) * (d - t) / (d * d)
}

/// The bolt up at frame `f` (its map) and its EVA, if any.
fn bolt_at(f: i32) -> Option<(usize, u8)> {
    if f > LAST_FRAME {
        return None;
    }
    let &(b, map, d) = BOLTS.iter().rev().find(|&&(b, _, _)| f >= b)?;
    Some((map, ease_in(16, 0, (f - b).min(d), d) as u8))
}

/// A spark's style 0..15 (Dual Strike's `Rng_Next() & 15`): a hash of the
/// burst and the spark.
fn style(burst: usize, spark: usize) -> usize {
    let mut h = (burst as u32 * 64 + spark as u32).wrapping_mul(0x9E37_79B9);
    h ^= h >> 15;
    h = h.wrapping_mul(0x85EB_CA6B);
    h ^= h >> 13;
    (h & 15) as usize
}

/// Spark `i` of a burst with style `s`, `t` frames into the burst: its
/// offset from the centre and its picture (0..5), or None (its flight is
/// over).
fn spark(offsets: &[(i8, i8); SPARKS], i: usize, s: usize, t: i32) -> Option<(i32, i32, usize)> {
    let head = 2 * (s / 4) as i32;
    let d = [32, 16, 24, 8][s % 4];
    let k = t + head;
    if k > d {
        return None;
    }
    let (ox, oy) = offsets[i];
    Some((ease_out(0, ox as i32, k, d), ease_out(0, oy as i32, k, d), ease_out(0, 5, k, d) as usize))
}

// --- The pack's pieces -------------------------------------------------------------

struct Art {
    /// Bolt maps A and B, each in at most [`BG_TILES`] tiles, for the GBA
    /// window (map cell (c, r) is Dual Strike's (c + 1, r + 2)).
    bolts: [BgLayer; 2],
    /// The six pictures of a spark (one 8x8 tile each).
    spark_tiles: Vec<u8>,
    spark_colour: u16,
    offsets: [(i8, i8); SPARKS],
}

const THUNDER: &str = "ohashi/res_tagbreak_thunder";
const SPARK_OFFSETS: u32 = 0x0215_C35C;

fn load() -> Option<Art> {
    let pack = crate::ds_pack::pack()?;
    let raw = pack.file(THUNDER)?;
    let lz = |at: usize| crate::ds_art::lz10(raw.get(at..)?);
    let tiles = lz(0)?;
    let pal = |at: usize| -> Option<[u16; 16]> {
        let b = raw.get(at..at + 32)?;
        Some(std::array::from_fn(|k| u16::from_le_bytes([b[2 * k], b[2 * k + 1]])))
    };
    let layer = |map_at: usize, palette: [u16; 16]| -> Option<BgLayer> {
        let m = lz(map_at)?;
        if m.len() < 0x800 || tiles.len() < 0x4000 {
            return None;
        }
        let mut used: Vec<[u8; 32]> = vec![[0; 32]];
        let mut map = vec![0u16; 32 * 32];
        for r in 0..20 {
            for c in 0..30 {
                let k = 2 * (32 * (r + WINDOW_Y as usize / 8) + c + WINDOW_X as usize / 8);
                let e = u16::from_le_bytes([m[k], m[k + 1]]);
                let t = (e & 0x3FF) as usize;
                let px: [u8; 32] = tiles.get(32 * t..32 * t + 32)?.try_into().ok()?;
                let n = match used.iter().position(|u| *u == px) {
                    Some(n) => n,
                    None => {
                        used.push(px);
                        used.len() - 1
                    }
                };
                map[32 * r + c] = n as u16 | (e & 0x0C00);
            }
        }
        let full = BgLayer {
            tiles: used.concat(),
            map,
            palette,
            start: Start::At(0),
            placement: BgPlacement::Scrolling { dx: 0, dy: 0 },
            blend: Vec::new(),
        };
        Some(full.reduced(BG_TILES))
    };
    let bolts = [layer(0x2254, pal(0x280C)?)?, layer(0x252C, pal(0x282C)?)?];
    // The sparks' sheet: a picture every two tiles.
    let s = lz(0x284C)?;
    let spark_tiles: Vec<u8> = (0..6).flat_map(|k| s.get(64 * k..64 * k + 32).unwrap_or(&[0; 32]).to_vec()).collect();
    let spark_colour = pal(0x28A8)?[SPARK_COLOUR as usize];
    let o = pack.arm9_at(SPARK_OFFSETS, 2 * SPARKS)?;
    let offsets = std::array::from_fn(|i| (o[2 * i] as i8, o[2 * i + 1] as i8));
    Some(Art { bolts, spark_tiles, spark_colour, offsets })
}

fn art() -> Option<&'static Art> {
    static ART: OnceLock<Option<Art>> = OnceLock::new();
    ART.get_or_init(load).as_ref()
}

// --- RAM, ROM and the display -----------------------------------------------------------

/// 1 while the thunder has what it covers copied aside (EWRAM, tangoAW2's
/// own: crate::ram_map).
pub const STATE: u32 = 0x0203_C600;
pub const STATE_LEN: u32 = 1;
/// Where what it covers is kept: the start of crate::tag_screens' backup,
/// which that screen only fills when it takes the display (frame 297).
const SAVE: u32 = crate::tag_screens::BACKUP;
const SAVE_BG_TILES: u32 = SAVE;
const SAVE_BG_MAP: u32 = SAVE + 0x1000;
const SAVE_BG_PAL: u32 = SAVE + 0x1800; // the buffer's, then the RAM's
const SAVE_OBJ_TILES: u32 = SAVE + 0x1840;
const SAVE_OBJ_PAL: u32 = SAVE + 0x1900; // the buffer's, then the RAM's
pub const SAVE_END: u32 = SAVE + 0x1940;

/// The wave overlay's tiles: BG0's character block + 0x5600, 128 of them.
const BG_TILE_OFFSET: u32 = 0x5600;
const BG_TILES: usize = 128;
const BG_PALETTE: u32 = 8;
const BG0_MAP_BUFFER: u32 = 0x0849_9578;
const BG_FLUSH: u32 = 0x0300_2F00;
const PAL_BUFFER: u32 = 0x0300_20C0;
const PAL_RAM: u32 = 0x0500_0000;
const OBJ_VRAM: u32 = 0x0601_0000;
const OBJ_TILE: u16 = 0x1CA;
const OBJ_PALETTE: u32 = 15;
const SPARK_COLOUR: u32 = 3;

const DISPCNT: u32 = 0x0300_30CC;
const BG0CNT: u32 = 0x0300_2B6C;
const BG0HOFS: u32 = 0x0300_1FF8;
const BG0VOFS: u32 = 0x0300_1418;
const BLDCNT: u32 = 0x0300_30E0;
const EVA: u32 = 0x0300_2020;
const EVB: u32 = 0x0300_2B28;
const BLDY: u32 = 0x0300_1FFC;
const IO: u32 = 0x0400_0000;
const BG0_ON: u16 = 0x0100;
/// BG0 blended over every other layer, the sprites and the backdrop.
const BLEND_BOLT: u16 = 0x3E41;

const OAM_NEXT: u32 = 0x0300_141C;
const SPRITE_LIST: u32 = 0x0300_0278;
const SPRITE_LIST_SIZE: u32 = 0x400;
const RESERVED: u32 = 16;
const PARKED_Y: u16 = 160;

fn copy(core: &mut Core, from: u32, to: u32, len: u32) {
    let mut b = vec![0u8; len as usize];
    core.raw_read_range(from, -1, &mut b);
    core.raw_write_range(to, -1, &b);
}

fn write_if_changed(core: &mut Core, at: u32, b: &[u8]) {
    let mut now = vec![0u8; b.len()];
    core.raw_read_range(at, -1, &mut now);
    if now != b {
        core.raw_write_range(at, -1, b);
    }
}

fn set16(core: &mut Core, at: u32, v: u16) {
    if core.raw_read_16(at, -1) != v {
        core.raw_write_16(at, -1, v);
    }
}

fn bg0_chars(core: &Core) -> u32 {
    0x0600_0000 + 0x4000 * ((crate::tag_screens::kept_shadow(core, BG0CNT) as u32 >> 2) & 3)
}

/// What the thunder covers, copied aside (once).
fn take(core: &mut Core) {
    if core.raw_read_8(STATE, -1) == 1 {
        return;
    }
    let chars = bg0_chars(core);
    copy(core, chars + BG_TILE_OFFSET, SAVE_BG_TILES, 32 * BG_TILES as u32);
    let buffer = core.raw_read_32(BG0_MAP_BUFFER, -1);
    copy(core, buffer, SAVE_BG_MAP, 0x800);
    for (k, base) in [PAL_BUFFER, PAL_RAM].into_iter().enumerate() {
        copy(core, base + 32 * BG_PALETTE, SAVE_BG_PAL + 32 * k as u32, 32);
        copy(core, base + 0x200 + 32 * OBJ_PALETTE, SAVE_OBJ_PAL + 32 * k as u32, 32);
    }
    copy(core, OBJ_VRAM + 32 * OBJ_TILE as u32, SAVE_OBJ_TILES, 32 * 6);
    core.raw_write_8(STATE, -1, 1);
}

/// Everything as it was (the bolts over, or the screen cut short): the
/// tiles, the BG0 buffer, the palettes, and the display shadows the
/// thunder set (from crate::tag_screens' kept ones).
pub fn hide(core: &mut Core) {
    if core.raw_read_8(STATE, -1) != 1 {
        return;
    }
    let chars = bg0_chars(core);
    copy(core, SAVE_BG_TILES, chars + BG_TILE_OFFSET, 32 * BG_TILES as u32);
    let buffer = core.raw_read_32(BG0_MAP_BUFFER, -1);
    copy(core, SAVE_BG_MAP, buffer, 0x800);
    let f = core.raw_read_16(BG_FLUSH, -1);
    core.raw_write_16(BG_FLUSH, -1, f | 1);
    for (k, base) in [PAL_BUFFER, PAL_RAM].into_iter().enumerate() {
        copy(core, SAVE_BG_PAL + 32 * k as u32, base + 32 * BG_PALETTE, 32);
        copy(core, SAVE_OBJ_PAL + 32 * k as u32, base + 0x200 + 32 * OBJ_PALETTE, 32);
    }
    copy(core, SAVE_OBJ_TILES, OBJ_VRAM + 32 * OBJ_TILE as u32, 32 * 6);
    for a in [DISPCNT, BG0CNT, BG0HOFS, BG0VOFS, BLDCNT, EVA, EVB, BLDY] {
        let v = crate::tag_screens::kept_shadow(core, a);
        set16(core, a, v);
    }
    let [c, a, b, y] = [BLDCNT, EVA, EVB, BLDY].map(|a| crate::tag_screens::kept_shadow(core, a));
    set16(core, IO + 0x50, c);
    set16(core, IO + 0x52, a | b << 8);
    set16(core, IO + 0x54, y);
    core.raw_write_8(STATE, -1, 0);
}

/// Frame `f` of the Tag Power's screen (crate::tag_screens' numbering)
/// while the map shows, the map dimmed by `dim` (0..16, the darkening the
/// screen gives it): the bolt and its sparks, if one is up (true: the
/// thunder set the colour effect); otherwise everything is put back
/// (false).
pub fn frame(core: &mut Core, f: i32, dim: u8) -> bool {
    let (Some(art), Some((map, eva))) = (art(), bolt_at(f)) else {
        hide(core);
        return false;
    };
    take(core);
    // The bolt on BG0.
    let bolt = &art.bolts[map];
    let chars = bg0_chars(core);
    write_if_changed(core, chars + BG_TILE_OFFSET, &bolt.tiles);
    let pal: Vec<u8> = bolt.palette.iter().flat_map(|c| c.to_le_bytes()).collect();
    for base in [PAL_BUFFER, PAL_RAM] {
        write_if_changed(core, base + 32 * BG_PALETTE, &pal);
    }
    let first = (BG_TILE_OFFSET / 32) as u16;
    let entries: Vec<u8> = bolt
        .map
        .iter()
        .flat_map(|&m| {
            let e = if m & 0x3FF == 0 { 0 } else { (m & 0xFFF) + first | (BG_PALETTE as u16) << 12 };
            e.to_le_bytes()
        })
        .collect();
    let buffer = core.raw_read_32(BG0_MAP_BUFFER, -1);
    let mut now = vec![0u8; entries.len()];
    core.raw_read_range(buffer, -1, &mut now);
    if now != entries {
        core.raw_write_range(buffer, -1, &entries);
        let fl = core.raw_read_16(BG_FLUSH, -1);
        core.raw_write_16(BG_FLUSH, -1, fl | 1);
    }
    let cnt = crate::tag_screens::kept_shadow(core, BG0CNT) & !3;
    set16(core, BG0CNT, cnt);
    set16(core, BG0HOFS, 0);
    set16(core, BG0VOFS, 0);
    let d = crate::tag_screens::kept_shadow(core, DISPCNT) | BG0_ON;
    set16(core, DISPCNT, d);
    let evb = 16 - dim.min(16) as u16;
    for (a, v) in [(BLDCNT, BLEND_BOLT), (EVA, eva as u16), (EVB, evb), (BLDY, 0)] {
        set16(core, a, v);
    }
    set16(core, IO + 0x50, BLEND_BOLT);
    set16(core, IO + 0x52, eva as u16 | evb << 8);
    set16(core, IO + 0x54, 0);
    sparks(core, art, f);
    true
}

/// The bursts' sparks at frame `f`.
fn sparks(core: &mut Core, art: &Art, f: i32) {
    write_if_changed(core, OBJ_VRAM + 32 * OBJ_TILE as u32, &art.spark_tiles);
    for base in [PAL_BUFFER, PAL_RAM] {
        let at = base + 0x200 + 32 * OBJ_PALETTE + 2 * SPARK_COLOUR;
        set16(core, at, art.spark_colour);
    }
    let live: Vec<(usize, i32, i32, i32)> = BURSTS
        .iter()
        .enumerate()
        .filter_map(|(n, &(b, x, y, wait))| {
            let t = f - (b + BURST_DELAY + wait);
            (0..=BURST_FRAMES).contains(&t).then_some((n, x - WINDOW_X, y - WINDOW_Y, t))
        })
        .collect();
    // As crate::power_anim: entries the map left parked this frame (y = 160)
    // past the pass's first 16.
    let base = core.raw_read_32(SPRITE_LIST, -1);
    let (reserved_end, list_end) = (base + 8 * RESERVED, base + SPRITE_LIST_SIZE);
    let mut oam = core.raw_read_32(OAM_NEXT, -1);
    let mut next = oam;
    // (every 7th spark round the circle first, the bursts in turn: the sparks
    // left out for want of entries are spread out)
    'all: for j in 0..SPARKS {
        let i = j * 7 % SPARKS;
        for &(n, x, y, t) in &live {
            let Some((dx, dy, pic)) = spark(&art.offsets, i, style(n, i), t) else { continue };
            let (sx, sy) = (x + dx - 4, y + dy - 4);
            if !(-8..240).contains(&sx) || !(-8..160).contains(&sy) {
                continue;
            }
            while oam + 8 <= list_end && oam >= reserved_end && core.raw_read_16(oam, -1) & 0xFF != PARKED_Y {
                oam += 8;
            }
            if oam + 8 > list_end {
                break 'all;
            }
            core.raw_write_16(oam, -1, (sy & 0xFF) as u16);
            core.raw_write_16(oam + 2, -1, (sx & 0x1FF) as u16);
            core.raw_write_16(oam + 4, -1, (OBJ_TILE + pic.min(5) as u16) | (OBJ_PALETTE as u16) << 12);
            oam += 8;
            if oam <= reserved_end {
                next = oam;
            }
        }
    }
    core.raw_write_32(OAM_NEXT, -1, next);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn timing() {
        assert_eq!(bolt_at(172), None);
        assert_eq!(bolt_at(173), Some((0, 16)));
        assert_eq!(bolt_at(209), Some((1, 16)));
        assert_eq!(bolt_at(208), Some((0, 1)));
        assert_eq!(bolt_at(219), Some((0, 16)));
        assert_eq!(bolt_at(255), Some((0, 0)));
        assert_eq!(bolt_at(257), None);
        // Curve 4 lands on its end; curve 1 starts slowly.
        assert_eq!(ease_out(0, 60, 32, 32), 60);
        assert_eq!(ease_out(0, 5, 0, 8), 0);
        assert_eq!(ease_in(16, 0, 18, 36), 12);
        // Every style is used, each burst its own.
        let s: std::collections::HashSet<usize> = (0..SPARKS).map(|i| style(0, i)).collect();
        assert!(s.len() >= 12);
        assert_ne!((0..SPARKS).map(|i| style(0, i)).collect::<Vec<_>>(), (0..SPARKS).map(|i| style(1, i)).collect::<Vec<_>>());
    }

    #[test]
    fn room() {
        assert!(SAVE_END <= crate::tag_screens::BACKUP + 0x1_0000, "inside the screen's VRAM copy");
        assert!(OBJ_TILE + 6 <= 0x209, "the meteor's tiles");
    }

    /// With `TANGOAW2_DS_ROM`: the bolts fit their tiles and the sparks'
    /// offsets are Dual Strike's 60-pixel circle.
    #[test]
    #[ignore]
    fn the_pack_gives_the_thunder() {
        crate::ds_pack::pack().expect("TANGOAW2_DS_ROM");
        let a = art().expect("the thunder");
        for b in &a.bolts {
            assert!(b.tiles.len() <= 32 * BG_TILES);
            assert!(b.map.iter().all(|&m| (m & 0x3FF) as usize * 32 < b.tiles.len()));
        }
        for &(x, y) in &a.offsets {
            let r = ((x as f64).powi(2) + (y as f64).powi(2)).sqrt();
            assert!((55.0..=65.0).contains(&r), "offset ({x}, {y})");
        }
        assert_eq!(a.spark_colour, 0x7FFF);
        assert!(a.spark_tiles[..32].iter().any(|&b| b != 0));
    }
}
