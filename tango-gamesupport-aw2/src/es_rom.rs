//! Reads one of AW2's own songs out of the player's ROM, at run time, for the music kit's `rom` references ([`crate::es_music`], docs/dev/music-kit.md).
//!
//! The songs of the game belong to Nintendo and Intelligent Systems: **nothing of them is stored in this repository**. A song file of ours may name
//! a stretch of one of AW2's songs (`rom sonja song=212 track=0 bars=7-14 ...`); when the game builds our song it reads those bytes from the
//! cartridge it is running (the same ROM on every peer, so every peer builds the same song) and copies the events out, transposed, re-voiced and
//! re-timed. This module is only the reader: it plays a track's commands the way the sound engine does (patterns, repeats, running status) and
//! returns the events with their ticks.
//!
//! Nothing here knows any note of any song.

use std::cell::RefCell;
use std::collections::HashMap;

use crate::ds_music::LENGTHS;

/// AW2's song table: (header, player, player) a song, [`SONGS`] songs.
pub const SONG_TABLE: u32 = 0x0824_238C;
pub const SONGS: u32 = 505;

const PAGE: u32 = 4096;
/// Commands executed at most for one track (a runaway guard: AW2's longest song is a few thousand).
const STEPS: usize = 2_000_000;

/// A reader of the ROM: `read(address, buffer)` fills the buffer from the cartridge (addresses `0x08000000..`). Pages of 4 KiB are cached.
pub struct RomView<'a> {
    read: &'a dyn Fn(u32, &mut [u8]),
    pages: RefCell<HashMap<u32, Vec<u8>>>,
}

impl<'a> RomView<'a> {
    pub fn new(read: &'a dyn Fn(u32, &mut [u8])) -> Self {
        RomView {
            read,
            pages: RefCell::new(HashMap::new()),
        }
    }

    /// A view of a whole ROM image held in memory (the tools and the tests).
    pub fn bytes(image: &'a [u8]) -> RomViewOwned<'a> {
        RomViewOwned { image }
    }

    pub fn u8(&self, addr: u32) -> u8 {
        let page = addr & !(PAGE - 1);
        let mut pages = self.pages.borrow_mut();
        let p = pages.entry(page).or_insert_with(|| {
            let mut b = vec![0u8; PAGE as usize];
            (self.read)(page, &mut b);
            b
        });
        p[(addr - page) as usize]
    }

    pub fn u32(&self, addr: u32) -> u32 {
        u32::from_le_bytes([self.u8(addr), self.u8(addr + 1), self.u8(addr + 2), self.u8(addr + 3)])
    }
}

/// A ROM image in memory, to make a [`RomView`] from.
pub struct RomViewOwned<'a> {
    image: &'a [u8],
}

impl RomViewOwned<'_> {
    pub fn with<R>(&self, f: impl FnOnce(&RomView) -> R) -> R {
        let image = self.image;
        let reader = move |addr: u32, out: &mut [u8]| {
            let o = addr.wrapping_sub(0x0800_0000) as usize;
            for (i, b) in out.iter_mut().enumerate() {
                *b = image.get(o + i).copied().unwrap_or(0);
            }
        };
        f(&RomView::new(&reader))
    }
}

/// One event of a source track.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Src {
    /// A note: `len` is `None` for a TIE (held until its EOT).
    Note { key: u8, vel: u8, len: Option<u32> },
    /// End of a tied note of this key.
    Eot(u8),
    /// A controller command (`0xBA..0xC8`) and its value.
    Ctl(u8, u8),
}

/// The voice group a song uses.
pub fn song_group(rom: &RomView, song: u16) -> Result<u32, String> {
    let h = header(rom, song)?;
    Ok(rom.u32(h + 4))
}

fn header(rom: &RomView, song: u16) -> Result<u32, String> {
    if song as u32 >= SONGS {
        return Err(format!("song {song}: AW2 has {SONGS} songs"));
    }
    let h = rom.u32(SONG_TABLE + 8 * song as u32);
    if !(0x0800_0000..0x0A00_0000).contains(&h) {
        return Err(format!(
            "song {song}: the song table does not point into the ROM ({h:#x})"
        ));
    }
    Ok(h)
}

/// Play track `track` of song `song` as the sound engine does, until `until` ticks or its GOTO / FINE (the first pass only), and return its events
/// in order with the tick each happens at. Patterns (PATT, REPT) are expanded; a PEND outside a pattern is ignored, as the engine does.
pub fn decode(rom: &RomView, song: u16, track: usize, until: u32) -> Result<Vec<(u32, Src)>, String> {
    let h = header(rom, song)?;
    let n = rom.u8(h) as usize;
    if track >= n {
        return Err(format!("song {song} has {n} tracks, not a track {track}"));
    }
    let mut a = rom.u32(h + 8 + 4 * track as u32);
    if !(0x0800_0000..0x0A00_0000).contains(&a) {
        return Err(format!("song {song} track {track}: bad address {a:#x}"));
    }
    let mut out = Vec::new();
    let mut tick = 0u32;
    let mut stack: Vec<(u32, u32, u32)> = Vec::new(); // return address, repeats left, pattern start
    let (mut key, mut vel) = (60u8, 127u8);
    let mut last = 0u8;
    for _ in 0..STEPS {
        if tick >= until {
            break;
        }
        let mut c = rom.u8(a);
        a += 1;
        if c < 0x80 {
            // running status: the arguments of the last note or controller command again
            if last == 0 {
                continue;
            }
            c = last;
            a -= 1;
        } else if c >= 0xBD {
            last = c;
        }
        match c {
            0x80..=0xB0 => tick += if c == 0x80 { 0 } else { LENGTHS[(c - 0x81) as usize] },
            0xB1 => break,
            0xB2 => break,
            0xB3 | 0xB5 => {
                let (cnt, tgt, ret) = if c == 0xB3 {
                    (1, rom.u32(a), a + 4)
                } else {
                    (rom.u8(a).max(1) as u32, rom.u32(a + 1), a + 5)
                };
                if stack.len() >= 8 {
                    return Err(format!("song {song} track {track}: patterns nest too deep"));
                }
                stack.push((ret, cnt, tgt));
                a = tgt;
            }
            0xB4 => {
                if let Some(f) = stack.last_mut() {
                    f.1 -= 1;
                    if f.1 > 0 {
                        a = f.2;
                    } else {
                        a = f.0;
                        stack.pop();
                    }
                }
            }
            0xBA | 0xBB | 0xBC | 0xBD | 0xBE | 0xBF | 0xC0 | 0xC1 | 0xC2 | 0xC3 | 0xC4 | 0xC5 | 0xC8 => {
                out.push((tick, Src::Ctl(c, rom.u8(a))));
                a += 1;
            }
            0xCE | 0xCF..=0xFF => {
                let mut args = [0u8; 3];
                let mut cnt = 0;
                while cnt < 3 && rom.u8(a) < 0x80 {
                    args[cnt] = rom.u8(a);
                    a += 1;
                    cnt += 1;
                }
                if cnt > 0 {
                    key = args[0];
                }
                if cnt > 1 {
                    vel = args[1];
                }
                if c == 0xCE {
                    out.push((tick, Src::Eot(key)));
                } else {
                    let len = if c == 0xCF {
                        None
                    } else {
                        Some(LENGTHS[(c - 0xD0) as usize] + if cnt > 2 { args[2] as u32 } else { 0 })
                    };
                    out.push((tick, Src::Note { key, vel, len }));
                }
            }
            _ => {
                // 0xB6..0xB9, 0xC6, 0xC7, 0xC9..0xCD: not used by the songs we read; skip one argument of the unknown ones like the engine's XCMD
                if matches!(c, 0xC9..=0xCD) {
                    a += 1;
                }
            }
        }
    }
    Ok(out)
}

/// A made-up ROM image for tests (nothing of the game): song 3 with one track, VOL 90, the pattern (E4, then G4 as running status) twice, then C4.
#[cfg(test)]
pub(crate) fn fake_rom() -> Vec<u8> {
    let mut rom = vec![0u8; 0x0100_0000];
    let put = |rom: &mut Vec<u8>, a: u32, b: &[u8]| {
        let o = (a - 0x0800_0000) as usize;
        rom[o..o + b.len()].copy_from_slice(b)
    };
    // song 3 in the table
    let e = (SONG_TABLE - 0x0800_0000) as usize + 8 * 3;
    rom[e..e + 4].copy_from_slice(&0x0800_0100u32.to_le_bytes());
    put(&mut rom, 0x0800_0100, &[1, 0, 0, 173]);
    put(&mut rom, 0x0800_0104, &0x0800_0300u32.to_le_bytes());
    put(&mut rom, 0x0800_0108, &0x0800_0200u32.to_le_bytes());
    // track: VOL 90; PATT p; PATT p; W24; N12 C4; GOTO
    let mut t = vec![0xBE, 90];
    t.extend([0xB3]);
    t.extend(0x0800_0220u32.to_le_bytes());
    t.extend([0xB3]);
    t.extend(0x0800_0220u32.to_le_bytes());
    t.extend([0x81 + 23]); // W24
    t.extend([0xD0 + 11, 60, 100]); // N12 C4 v100
    t.extend([0xB2, 0, 0, 0, 0]);
    put(&mut rom, 0x0800_0200, &t);
    // pattern: N24 E4 v110, W24, running status (the note command again) with key 67, W24, PEND
    put(
        &mut rom,
        0x0800_0220,
        &[0xD0 + 23, 64, 110, 0x81 + 23, 67, 0x81 + 23, 0xB4],
    );
    rom
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fake() -> Vec<u8> {
        fake_rom()
    }

    #[test]
    fn plays_patterns_and_running_status() {
        let img = fake();
        RomView::bytes(&img).with(|r| {
            let ev = decode(r, 3, 0, 1000).unwrap();
            let notes: Vec<_> = ev.iter().filter(|e| matches!(e.1, Src::Note { .. })).collect();
            // each pass of the pattern: E4 at 0, G4 at 24 (running status), twice; then C4
            assert_eq!(notes.len(), 5);
            assert_eq!(
                notes[0].1,
                Src::Note {
                    key: 64,
                    vel: 110,
                    len: Some(24)
                }
            );
            assert_eq!(
                notes[1].1,
                Src::Note {
                    key: 67,
                    vel: 110,
                    len: Some(24)
                }
            );
            assert_eq!(notes[1].0, 24);
            assert_eq!(notes[2].0, 48);
            assert_eq!(
                notes[4],
                &(
                    120,
                    Src::Note {
                        key: 60,
                        vel: 100,
                        len: Some(12)
                    }
                )
            );
            assert!(ev.contains(&(0, Src::Ctl(0xBE, 90))));
        });
    }

    #[test]
    fn a_bad_song_is_an_error() {
        let img = fake();
        RomView::bytes(&img).with(|r| {
            assert!(decode(r, 9999, 0, 10).is_err());
            assert!(decode(r, 3, 4, 10).is_err());
            assert!(decode(r, 5, 0, 10).is_err()); // no header
        });
    }
}
