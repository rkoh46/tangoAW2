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
const MOVE_SENTINEL: u32 = MOVE_NEW + 24 * MOVE_SIZE;
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
            if slot >= 0x6C / 4 {
                continue;
            }
            for f in 0..3 {
                let tiles = crate::ds_unit_art::map_tiles_country(t, f, country)?;
                out[f * UNIT_FRAME + 128 * slot..][..128].copy_from_slice(&tiles);
            }
        }
    }
    Some(out)
}

static IDLE: OnceLock<Option<Vec<u8>>> = OnceLock::new();
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
    let moves = MOVES.get_or_init(|| {
        (1..=24u8)
            .map(|t| crate::ds_unit_art::move_sheet(t, t).map(|s| lz_literal(&s)))
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

/// Every frame with the pack on.
pub fn tick(core: &mut Core, pack: bool) {
    if !pack {
        return;
    }
    let on = ds_graphics(core);
    building_tick(core, on);
    unit_tick(core, on);
}
