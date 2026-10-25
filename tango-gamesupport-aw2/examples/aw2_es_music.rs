//! The Emerald Sun themes' compiler as a tool (`aw2dev sound compose`, docs/dev/music-kit.md): compiles the song files and prints one JSON object a song.
//!
//!   aw2_es_music                 every built-in song (or the files of $TANGOAW2_ES_MUSIC)
//!   aw2_es_music FILE.m4t ..     those files
//!   aw2_es_music --dump DIR ..   also write each song's track bytes to DIR/<name>.<track>.bin (the loop label's offset is in the JSON)
//!
//! Exit 1 with the compiler's message on stderr for a song that does not compile.
use tango_gamesupport_aw2::es_music;

fn main() {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    let mut dump = None;
    if let Some(i) = args.iter().position(|a| a == "--dump") {
        dump = Some(args.remove(i + 1));
        args.remove(i);
    }
    let mut songs: Vec<(String, u8, String)> = Vec::new();
    if args.is_empty() {
        for s in es_music::SOURCES.iter() {
            songs.push((s.name.to_string(), s.co, es_music::text(s).into_owned()));
        }
    } else {
        for f in &args {
            let text = std::fs::read_to_string(f).unwrap_or_else(|e| {
                eprintln!("{f}: {e}");
                std::process::exit(1)
            });
            let name = std::path::Path::new(f).file_stem().unwrap().to_string_lossy().into_owned();
            let co = es_music::SOURCES.iter().find(|s| s.name == name).map_or(0, |s| s.co);
            songs.push((name, co, text));
        }
    }
    let mut bad = false;
    for (name, co, text) in songs {
        match es_music::compile(&text) {
            Ok(c) => {
                let tracks: Vec<String> = c.tracks.iter().map(|t| format!("{{\"bytes\":{},\"label\":{}}}", t.bytes.len(), t.label)).collect();
                let voices: Vec<String> = c.voices.iter().map(|v| format!("[{},{}]", v.group, v.index)).collect();
                println!(
                    "{{\"name\":\"{name}\",\"co\":{co},\"bpm\":{},\"bar_ticks\":{},\"reverb\":{},\"priority\":{},\"intro_s\":{:.3},\"loop_s\":{:.3},\"intro_ticks\":{},\"loop_ticks\":{},\"peak_voices\":{},\"peak_at\":{},\"notes\":{},\"bytes\":{},\"tracks\":[{}],\"voices\":[{}]}}",
                    c.bpm,
                    c.bar_ticks,
                    c.reverb,
                    c.priority,
                    c.intro_seconds(),
                    c.loop_seconds(),
                    c.intro_ticks,
                    c.loop_ticks,
                    c.peak_voices,
                    c.peak_at,
                    c.notes,
                    c.bytes(),
                    tracks.join(","),
                    voices.join(",")
                );
                if let Some(d) = &dump {
                    std::fs::create_dir_all(d).unwrap();
                    for (i, t) in c.tracks.iter().enumerate() {
                        std::fs::write(format!("{d}/{name}.{i}.bin"), &t.bytes).unwrap();
                    }
                }
            }
            Err(e) => {
                eprintln!("{name}: {e}");
                bad = true;
            }
        }
    }
    std::process::exit(bad as i32);
}
