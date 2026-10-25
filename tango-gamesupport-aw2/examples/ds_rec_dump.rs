// Scratch (not committed): first frame of mu/001, 002 and 01f..026 as PPM (OS unit palette bmap/046).
fn main() {
    let out = std::env::args().nth(1).unwrap();
    let p = tango_gamesupport_aw2::ds_pack::pack().expect("pack");
    let pal_file = p
        .file("bmap/046")
        .map(|f| tango_gamesupport_aw2::ds_art::lz10(f).unwrap_or_else(|| f.to_vec()))
        .unwrap();
    let pal: Vec<u16> = (0..16)
        .map(|i| u16::from_le_bytes([pal_file[2 * i], pal_file[2 * i + 1]]))
        .collect();
    let names = ["001", "002", "01f", "020", "021", "022", "023", "024", "025", "026"];
    let mut img = vec![255u8; 3 * 32 * 32 * names.len() * 3];
    let w = 32 * names.len();
    for (n, nm) in names.iter().enumerate() {
        let f = p.file(&format!("mu/{nm}")).unwrap();
        for fr in 0..3usize {
            for t in 0..16usize {
                for y in 0..8 {
                    for x in 0..8 {
                        let b = f[fr * 512 + t * 32 + y * 4 + x / 2];
                        let v = if x % 2 == 0 { b & 15 } else { b >> 4 } as usize;
                        let (px, py) = (n * 32 + (t % 4) * 8 + x, fr * 32 + (t / 4) * 8 + y);
                        let c = if v == 0 { 0x7FFF } else { pal[v] };
                        let o = 3 * (py * w + px);
                        img[o] = ((c & 31) * 8) as u8;
                        img[o + 1] = (((c >> 5) & 31) * 8) as u8;
                        img[o + 2] = (((c >> 10) & 31) * 8) as u8;
                    }
                }
            }
        }
    }
    let mut f = format!("P6\n{} {}\n255\n", w, 96).into_bytes();
    f.extend_from_slice(&img);
    std::fs::write(format!("{out}/mu.ppm"), f).unwrap();
}
