//! Preview of Dual Strike's CO page ([`tango_gamesupport_aw2::ds_co_page`]):
//! every page of the CO pages of the Dual Strike COs named, as PPMs.
//!
//! Usage: TANGOAW2_DS_ROM=<Dual Strike ROM or pack> ds_co_page_preview <out dir> [AW2 CO ids...]

use tango_gamesupport_aw2::ds_co_page::{compose, fallbacks, rgba, tile_count, view_for};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let out = std::path::Path::new(&args[1]);
    std::fs::create_dir_all(out).unwrap();
    tango_gamesupport_aw2::ds_pack::pack().expect("TANGOAW2_DS_ROM");
    let cos: Vec<u8> = if args.len() > 2 {
        args[2..].iter().map(|a| a.parse().unwrap()).collect()
    } else {
        (0..19u8).chain(72..81).collect()
    };
    if let Some(w) = tango_gamesupport_aw2::ds_co_wall::wall() {
        let mut ppm = b"P6\n240 160\n255\n".to_vec();
        for c in &w.pix {
            ppm.extend_from_slice(&[
                ((c & 31) * 255 / 31) as u8,
                (((c >> 5) & 31) * 255 / 31) as u8,
                (((c >> 10) & 31) * 255 / 31) as u8,
            ]);
        }
        std::fs::write(out.join("wall.ppm"), ppm).unwrap();
        eprintln!("wall: {} tiles", w.chars.len() / 32);
    }
    for co in cos {
        let v = view_for(None, None, co);
        for page in 0..4 {
            let cv = compose(&v, page).expect("font and art");
            let mut ppm = format!("P6\n240 160\n255\n").into_bytes();
            for px in rgba(&cv).chunks(4) {
                ppm.extend_from_slice(&px[..3]);
            }
            std::fs::write(out.join(format!("co{co}_p{page}.ppm")), ppm).unwrap();
            eprintln!("co {co} ({}) page {page}: {} tiles", v.name, tile_count(&cv));
        }
    }
    eprintln!("pages left with the frame only: {}", fallbacks());
}
