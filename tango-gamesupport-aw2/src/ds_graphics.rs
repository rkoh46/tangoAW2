//! "Dual Strike graphics": a preview mode (off by default, pack only) that
//! draws the battle map with Dual Strike's own graphics. It is switched by a
//! development byte ([`crate::wasteland::DS_GRAPHICS`]) and changes nothing
//! while it is zero.
//!
//! - Terrain: [`crate::wasteland`] draws Normal maps with Dual Strike's
//!   Normal look (`bmap/000`, palette `bmap/006`) and its upper-parts layer.
//! - Units: every original unit's idle pictures (per country: Infantry and
//!   Mech differ) and moving sheets from `bmap/01d..01f` and `mu/*`, through
//!   [`crate::ds_unit_art`].
//! - Buildings: the property sheet's pictures (city, base and its smoke,
//!   airport, port, the five HQs, silo, minicannon pods) from `bmap/015`.
//!
//! Where the game reads a table through a literal-pool word the word is
//! pointed at a converted copy in free ROM while the mode is on and back at
//! AW2's own while it is off (every frame, from RAM alone).

use mgba::core::Core;
use std::sync::OnceLock;

use crate::wasteland::ds_graphics;

fn switch32(core: &mut Core, at: u32, want: u32) {
    if core.raw_read_32(at, -1) != want {
        core.raw_write_32(at, -1, want);
    }
}

/// With the mode off: a word is put back to AW2's value only if it holds
/// ours (another feature may have pointed it elsewhere, and with the mode
/// never on nothing is written at all).
fn put_back(core: &mut Core, at: u32, ours: u32, aw2: u32) {
    if core.raw_read_32(at, -1) == ours {
        core.raw_write_32(at, -1, aw2);
    }
}

// --- Buildings ---------------------------------------------------------------

/// AW2's building sheets: the clear sheet (0xB80 bytes from tile 72), the
/// snow sheet, the HQs (five 8-tile pictures a weather) and the base's four
/// smoke frames (4 tiles each), all in one run of ROM.
const BLD_REGION: u32 = 0x080C_FFC4;
const BLD_LEN: usize = 0x2300;
const BLD_NEW: u32 = 0x09E8_0000;
const BLD_SENTINEL: u32 = BLD_NEW + 0x2400;
const MAGIC: u32 = 0x4731_5344; // "DS1G"
const SNOW: usize = 0xB80;
const HQ: usize = 0x1700;
const HQ_SNOW: usize = 0x1C00;
const SMOKE: usize = 0x2100;
/// Pool words reading the region: (word, AW2's value, offset in the region).
const BLD_POOLS: [(u32, u32, usize); 7] = [
    (0x0803_F5F8, BLD_REGION, 0),
    (0x0803_F5FC, BLD_REGION + HQ as u32, HQ),
    (0x0803_F6AC, BLD_REGION + SNOW as u32, SNOW),
    (0x0803_F6B0, BLD_REGION + HQ_SNOW as u32, HQ_SNOW),
    (0x0803_F6E4, BLD_REGION, 0),
    (0x0803_F6E8, BLD_REGION + HQ as u32, HQ),
    (0x0803_F8FC, BLD_REGION + SMOKE as u32, SMOKE),
];
/// OBJ tile numbers in the clear sheet start at 72.
fn at(tile: usize) -> usize {
    32 * (tile - 72)
}
/// Minicannon pods use Black Hole's own indices, as [`crate::ds_art`]'s
/// cannon does; everything else the building shades.
const POD_INDICES: [u8; 16] = [0, 2, 3, 3, 4, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];
const HQ_CELLS: [usize; 5] = [10, 11, 12, 13, 9];

fn cell(sprites: &[u8], n: usize, map: &[u8; 16]) -> Vec<u8> {
    let bmp: Vec<u8> = sprites[256 * n..256 * (n + 1)]
        .iter()
        .map(|&b| map[(b & 15) as usize] | map[(b >> 4) as usize] << 4)
        .collect();
    crate::ds_art::tiles(&bmp, 16, &[(0, 0, 16, 32)])
}

fn buildings(aw2: &[u8]) -> Option<Vec<u8>> {
    let pack = crate::ds_pack::pack()?;
    let sprites = crate::ds_art::lz10(pack.file("bmap/015")?)?;
    let sh = &crate::com_tower::SHADES;
    let mut out = aw2.to_vec();
    for base in [0, SNOW] {
        let mut put = |tile: usize, bytes: &[u8]| {
            out[base + at(tile)..base + at(tile) + bytes.len()].copy_from_slice(bytes)
        };
        put(72, &cell(&sprites, 1, sh));
        put(80, &cell(&sprites, 6, sh));
        put(88, &cell(&sprites, 7, sh));
        put(104, &cell(&sprites, 0, sh));
        put(152, &cell(&sprites, 15, sh));
        put(160, &cell(&sprites, 14, sh)[128..]);
        for (k, d) in (18..22).enumerate() {
            put(112 + 8 * k, &cell(&sprites, d, &POD_INDICES));
        }
    }
    for base in [HQ, HQ_SNOW] {
        for (k, d) in HQ_CELLS.iter().enumerate() {
            out[base + 256 * k..base + 256 * (k + 1)].copy_from_slice(&cell(&sprites, *d, sh));
        }
    }
    for k in 0..4 {
        out[SMOKE + 128 * k..SMOKE + 128 * (k + 1)].copy_from_slice(&cell(&sprites, 2 + k, sh)[..128]);
    }
    Some(out)
}

static BUILDINGS: OnceLock<Option<Vec<u8>>> = OnceLock::new();

fn building_tick(core: &mut Core, on: bool) {
    if !on {
        for (at, aw2, off) in BLD_POOLS {
            put_back(core, at, BLD_NEW + off as u32, aw2);
        }
        return;
    }
    let built = BUILDINGS.get_or_init(|| {
        let mut aw2 = vec![0u8; BLD_LEN];
        core.raw_read_range(BLD_REGION, -1, &mut aw2);
        buildings(&aw2)
    });
    let Some(b) = built else { return };
    if core.raw_read_32(BLD_SENTINEL, -1) != MAGIC {
        core.raw_write_range(BLD_NEW, -1, b);
        core.raw_write_32(BLD_SENTINEL, -1, MAGIC);
    }
    for (at, _, off) in BLD_POOLS {
        switch32(core, at, BLD_NEW + off as u32);
    }
}

// --- Units ---------------------------------------------------------------------

/// The idle sheet getters (`sub_08026190` and its twin): three frames of 27
/// slots of 4 tiles.
pub const UNIT_POOLS: [u32; 2] = [0x0802_6194, 0x0802_66D8];
pub const AW2_UNIT_SHEET: u32 = 0x0810_BE60;
const UNIT_FRAME: usize = 0x6C * 32;
const UNIT_NEW: u32 = 0x09EB_0000;
const UNIT_SENTINEL: u32 = UNIT_NEW + 0x3000;
const AW2_SLOTS: u32 = 0x0849_9608;
/// Moving sheets (LZ77, literal) of the 24 original unit types.
const MOVE_NEW: u32 = 0x09EC_0000;
const MOVE_SIZE: u32 = 0x1000;
const MOVE_SENTINEL: u32 = MOVE_NEW + 32 * MOVE_SIZE;
const AW2_MOVES: u32 = 0x0849_CD88;

/// The sheet the game reads now (AW2's or ours).
pub fn unit_sheet(core: &Core) -> u32 {
    core.raw_read_32(UNIT_POOLS[0], -1)
}

fn idle_sheet(core: &Core) -> Option<Vec<u8>> {
    let mut out = vec![0u8; 3 * UNIT_FRAME];
    core.raw_read_range(AW2_UNIT_SHEET, -1, &mut out);
    for country in 0..5usize {
        for t in 1..=24u8 {
            let mut s = [0u8; 2];
            core.raw_read_range(AW2_SLOTS + 0x32 * country as u32 + 2 * t as u32, -1, &mut s);
            let slot = u16::from_le_bytes(s) as usize;
            // (The ids AW2 lacks hold slot 0, the Md Tank's.)
            if slot >= 0x6C / 4 || (slot == 0 && t != 3) {
                continue;
            }
            for f in 0..3 {
                let tiles = crate::ds_unit_art::map_tiles_ds(t, f, country)?;
                out[f * UNIT_FRAME + 128 * slot..][..128].copy_from_slice(&tiles);
            }
        }
    }
    Some(out)
}

static IDLE: OnceLock<Option<Vec<u8>>> = OnceLock::new();
static NEW_IDLE: OnceLock<Option<Vec<[u8; 128]>>> = OnceLock::new();
static NEW_MOVES: OnceLock<Option<Vec<Vec<u8>>>> = OnceLock::new();
static MOVES: OnceLock<Option<Vec<Vec<u8>>>> = OnceLock::new();

fn lz_literal(data: &[u8]) -> Vec<u8> {
    let mut out = vec![0x10, data.len() as u8, (data.len() >> 8) as u8, (data.len() >> 16) as u8];
    for block in data.chunks(8) {
        out.push(0);
        out.extend_from_slice(block);
    }
    while out.len() % 4 != 0 {
        out.push(0);
    }
    out
}

fn unit_tick(core: &mut Core, on: bool) {
    let installed = crate::roster::installed(core);
    if !on {
        for at in UNIT_POOLS {
            put_back(core, at, UNIT_NEW, AW2_UNIT_SHEET);
        }
        if installed {
            for (k, (id, _)) in crate::roster::new_units().into_iter().enumerate() {
                for c in 0..5u32 {
                    put_back(
                        core,
                        crate::roster::move_pointer(id as u32, c),
                        MOVE_NEW + MOVE_SIZE * (24 + k as u32),
                        crate::roster::art_move_at(k),
                    );
                }
            }
            if let Some(Some(v)) = NEW_IDLE.get() {
                let n = crate::roster::new_units().len();
                for i in 0..v.len() {
                    let at = crate::roster::art_map_at(i / n, i % n);
                    let mut now = [0u8; 128];
                    core.raw_read_range(at, -1, &mut now);
                    if now == v[i] {
                        if let Some(o) = crate::ds_unit_art::map_tiles(crate::roster::ds_id(crate::roster::new_units()[i % n].0).unwrap_or(0), i / n) {
                            core.raw_write_range(at, -1, &o);
                        }
                    }
                }
            }
            for t in 1..=24u32 {
                for c in 0..5u32 {
                    let orig = core.raw_read_32(AW2_MOVES + 36 * t + 4 * c, -1);
                    put_back(core, crate::roster::move_pointer(t, c), MOVE_NEW + MOVE_SIZE * (t - 1), orig);
                }
            }
        }
        return;
    }
    let idle = IDLE.get_or_init(|| idle_sheet(core));
    if let Some(i) = idle {
        if core.raw_read_32(UNIT_SENTINEL, -1) != MAGIC {
            core.raw_write_range(UNIT_NEW, -1, i);
            core.raw_write_32(UNIT_SENTINEL, -1, MAGIC);
        }
        for at in UNIT_POOLS {
            switch32(core, at, UNIT_NEW);
        }
    }
    if !installed {
        return;
    }
    // The seven new units get the same conversion rules.
    let news = crate::roster::new_units();
    let idle_new = NEW_IDLE.get_or_init(|| {
        let mut v = Vec::new();
        for f in 0..3 {
            for &(id, _) in &news {
                v.push(crate::ds_unit_art::map_tiles_ds(crate::roster::ds_id(id)?, f, 0)?);
            }
        }
        Some(v)
    });
    if let Some(v) = idle_new {
        for (i, t) in v.iter().enumerate() {
            let at = crate::roster::art_map_at(i / news.len(), i % news.len());
            let mut now = [0u8; 128];
            core.raw_read_range(at, -1, &mut now);
            if now != *t {
                core.raw_write_range(at, -1, t);
            }
        }
    }
    let moves_new = NEW_MOVES.get_or_init(|| {
        news.iter()
            .map(|&(id, like)| crate::ds_unit_art::move_sheet_ds(crate::roster::ds_id(id)?, like).map(|s| lz_literal(&s)))
            .collect::<Option<Vec<_>>>()
    });
    if let Some(m) = moves_new {
        for (k, &(id, _)) in news.iter().enumerate() {
            let at = MOVE_NEW + MOVE_SIZE * (24 + k as u32);
            if core.raw_read_32(MOVE_SENTINEL, -1) != MAGIC {
                core.raw_write_range(at, -1, &m[k]);
            }
            for c in 0..5u32 {
                switch32(core, crate::roster::move_pointer(id as u32, c), at);
            }
        }
    }
    let moves = MOVES.get_or_init(|| {
        (1..=24u8)
            .map(|t| crate::ds_unit_art::move_sheet_ds(t, t).map(|s| lz_literal(&s)))
            .collect::<Option<Vec<_>>>()
    });
    if let Some(m) = moves {
        if core.raw_read_32(MOVE_SENTINEL, -1) != MAGIC {
            for (k, lz) in m.iter().enumerate() {
                assert!(lz.len() as u32 <= MOVE_SIZE);
                core.raw_write_range(MOVE_NEW + MOVE_SIZE * k as u32, -1, lz);
            }
            core.raw_write_32(MOVE_SENTINEL, -1, MAGIC);
        }
        for t in 1..=24u32 {
            for c in 0..5u32 {
                switch32(core, crate::roster::move_pointer(t, c), MOVE_NEW + MOVE_SIZE * (t - 1));
            }
        }
    }
}

// --- HP digits and status icons ------------------------------------------------

/// The map's overlay tiles (BG tiles from 0x2A2: the digits 1..9, four status
/// icons, "?"), the getter `sub_08026198`'s literal. Dual Strike's `bmap/01c`
/// uses the same colour indices (1 digit, 2 icon, 15 outline).
const HUD_REGION: u32 = 0x0810_E820;
const HUD_POOL: u32 = 0x0802_619C;
const HUD_NEW: u32 = 0x09EE_0000;
const HUD_LEN: usize = 0x1000;
const HUD_SENTINEL: u32 = HUD_NEW + HUD_LEN as u32 + 4;

fn hud(aw2: &[u8]) -> Option<Vec<u8>> {
    let pack = crate::ds_pack::pack()?;
    let f = crate::ds_art::lz10(pack.file("bmap/01c")?)?;
    let mut out = aw2.to_vec();
    // (AW2 tile - 2, Dual Strike tile): the digits, the four icons (Dual
    // Strike draws each in four frames; the first), "?".
    let mut pairs: Vec<(usize, usize)> = (0..9).map(|k| (k, 1 + k)).collect();
    pairs.extend([(9, 14), (10, 18), (11, 22), (12, 26), (13, 10)]);
    for (a, d) in pairs {
        out[32 * a..32 * a + 32].copy_from_slice(f.get(32 * d..32 * d + 32)?);
    }
    Some(out)
}

static HUD: OnceLock<Option<Vec<u8>>> = OnceLock::new();

fn hud_tick(core: &mut Core, on: bool) {
    if !on {
        put_back(core, HUD_POOL, HUD_NEW, HUD_REGION);
        return;
    }
    let built = HUD.get_or_init(|| {
        let mut aw2 = vec![0u8; HUD_LEN];
        core.raw_read_range(HUD_REGION, -1, &mut aw2);
        hud(&aw2)
    });
    let Some(b) = built else { return };
    if core.raw_read_32(HUD_SENTINEL, -1) != MAGIC {
        core.raw_write_range(HUD_NEW, -1, b);
        core.raw_write_32(HUD_SENTINEL, -1, MAGIC);
    }
    switch32(core, HUD_POOL, HUD_NEW);
}

// --- Missile pad, Fortress and Volcano pictures --------------------------------

/// 64x64 pictures (LZ77) the map headers (+0x10) and `LoadInventionGraphics`
/// name: AW2's address, Dual Strike's cell offset in `bmap/015`, the
/// sub-palette it is drawn with there, and AW2's palette it is shown with
/// (None: Black Hole's, `0x080D3E84`).
const PICTURES: [(u32, usize, usize, Option<u32>); 3] = [
    (0x080D_2DA8, 0x1700, 12, None),
    (0x080D_38AC, 0x1F00, 12, None),
    (0x080D_3268, 0x4700, 13, Some(0x080D_3EC4)),
];
const PIC_NEW: u32 = 0x09EE_2000;
const PIC_SLOT: u32 = 0x1000;
const PIC_SENTINEL: u32 = PIC_NEW + 3 * PIC_SLOT;
/// Words naming a picture: (address, which picture). The headers of the two
/// maps that use the pad and the Fortress, and the volcano's pool word.
const PIC_WORDS: [(u32, usize); 5] = [
    (0x085C_AD3C, 0),
    (0x085C_B524, 0),
    (0x085C_AF64, 1),
    (0x085C_B1E8, 1),
    (0x0803_FE40, 2),
];
const AW2_BLACK_HOLE: u32 = 0x080D_3E84;
const MAP_HEADERS: u32 = 0x0803_FDCC;
const HEADER: u32 = 0x5C;

fn nearest_map(ds: &[u16; 16], aw2: &[u16; 16]) -> [u8; 16] {
    let rgb = |c: u16| [(c & 31) as i32, ((c >> 5) & 31) as i32, ((c >> 10) & 31) as i32];
    let mut map = [0u8; 16];
    for (i, m) in map.iter_mut().enumerate().skip(1) {
        let c = rgb(ds[i]);
        *m = (1..16)
            .min_by_key(|&j| {
                let g = rgb(aw2[j]);
                (0..3).map(|k| (c[k] - g[k]).pow(2)).sum::<i32>()
            })
            .unwrap() as u8;
    }
    map
}

fn palette_at(core: &Core, at: u32) -> [u16; 16] {
    let mut b = [0u8; 32];
    core.raw_read_range(at, -1, &mut b);
    std::array::from_fn(|i| u16::from_le_bytes([b[2 * i], b[2 * i + 1]]))
}

fn pictures(core: &Core) -> Option<Vec<Vec<u8>>> {
    let pack = crate::ds_pack::pack()?;
    let sprites = crate::ds_art::lz10(pack.file("bmap/015")?)?;
    let pal = pack.file("bmap/00e")?;
    let mut out = Vec::new();
    for &(_, at, sub, aw2_pal) in PICTURES.iter() {
        let ds: [u16; 16] = std::array::from_fn(|i| {
            let o = 32 * sub + 2 * i;
            u16::from_le_bytes([pal[o], pal[o + 1]])
        });
        let aw2 = palette_at(core, aw2_pal.unwrap_or(AW2_BLACK_HOLE));
        // The Volcano's indices are AW2's own (Dual Strike's palette is AW2's
        // with the greens made yellow-green, `crate::volcano`).
        let map = if sub == 13 { std::array::from_fn(|i| i as u8) } else { nearest_map(&ds, &aw2) };
        let bmp: Vec<u8> = sprites
            .get(at..at + 0x800)?
            .iter()
            .map(|&b| map[(b & 15) as usize] | map[(b >> 4) as usize] << 4)
            .collect();
        out.push(lz_literal(&crate::ds_art::tiles(&bmp, 64, &[(0, 0, 64, 64)])));
    }
    Some(out)
}

static PICS: OnceLock<Option<Vec<Vec<u8>>>> = OnceLock::new();

/// Where the picture AW2 keeps at `aw2` is read now (ours while the
/// preview is on).
pub fn structure_picture(core: &Core, aw2: u32) -> u32 {
    if !ds_graphics(core) || core.raw_read_32(PIC_SENTINEL, -1) != MAGIC {
        return aw2;
    }
    PICTURES.iter().position(|p| p.0 == aw2).map_or(aw2, |k| PIC_NEW + PIC_SLOT * k as u32)
}

fn picture_tick(core: &mut Core, on: bool) {
    let headers = core.raw_read_32(MAP_HEADERS, -1);
    let mut words: Vec<(u32, usize)> = PIC_WORDS.to_vec();
    if (0x0800_0000..0x0A00_0000).contains(&headers) {
        for id in 0..0x100u32 {
            let at = headers + HEADER * id + 0x10;
            let v = core.raw_read_32(at, -1);
            if let Some(k) = PICTURES.iter().position(|p| p.0 == v) {
                words.push((at, k));
            } else if let Some(k) = (0..3).find(|&k| v == PIC_NEW + PIC_SLOT * k as u32) {
                words.push((at, k));
            }
        }
    }
    if !on {
        for (at, k) in words {
            put_back(core, at, PIC_NEW + PIC_SLOT * k as u32, PICTURES[k].0);
        }
        return;
    }
    let built = PICS.get_or_init(|| pictures(core));
    let Some(b) = built else { return };
    if core.raw_read_32(PIC_SENTINEL, -1) != MAGIC {
        for (k, lz) in b.iter().enumerate() {
            assert!(lz.len() as u32 <= PIC_SLOT);
            core.raw_write_range(PIC_NEW + PIC_SLOT * k as u32, -1, lz);
        }
        core.raw_write_32(PIC_SENTINEL, -1, MAGIC);
    }
    for (at, k) in words {
        let v = core.raw_read_32(at, -1);
        if v == PICTURES[k].0 || v == PIC_NEW + PIC_SLOT * k as u32 {
            switch32(core, at, PIC_NEW + PIC_SLOT * k as u32);
        }
    }
}

/// Every frame with the pack on.
pub fn tick(core: &mut Core, pack: bool) {
    if !pack {
        return;
    }
    let on = ds_graphics(core);
    if on {
        crate::wasteland::restore_front(core);
    } else {
        crate::wasteland::clear_front(core);
    }
    building_tick(core, on);
    unit_tick(core, on);
    hud_tick(core, on);
    picture_tick(core, on);
}
