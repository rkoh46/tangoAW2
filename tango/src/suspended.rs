//! Matches cut short by a disconnect, kept to be resumed (ONLINE > LOBBY > RESUME).
//!
//! One file per match in `<data>/suspended/<match id>.taw2s`: a [`SuspendedMatch`] (the newest settled checkpoints
//! of the shared console, who played, the map and day) as bincode, zstd'd. The match's own id names the file, so a
//! match suspended again after being resumed replaces its earlier save.

use std::path::{Path, PathBuf};
use tango_match::SuspendedMatch;

const EXT: &str = "taw2s";

pub fn dir(data_path: &Path) -> PathBuf {
    data_path.join("suspended")
}

fn file(data_path: &Path, match_id: u64) -> PathBuf {
    dir(data_path).join(format!("{match_id:016x}.{EXT}"))
}

pub fn save(data_path: &Path, m: &SuspendedMatch) -> std::io::Result<PathBuf> {
    std::fs::create_dir_all(dir(data_path))?;
    let bytes = bincode::serialize(m).map_err(std::io::Error::other)?;
    let packed = zstd::stream::encode_all(std::io::Cursor::new(bytes), 6)?;
    let path = file(data_path, m.match_id);
    // (written whole, then moved into place: a crash never leaves half a save)
    let tmp = path.with_extension("part");
    std::fs::write(&tmp, packed)?;
    std::fs::rename(&tmp, &path)?;
    Ok(path)
}

fn read(path: &Path) -> Option<SuspendedMatch> {
    let packed = std::fs::read(path).ok()?;
    let bytes = zstd::stream::decode_all(std::io::Cursor::new(packed)).ok()?;
    let m: SuspendedMatch = bincode::deserialize(&bytes).ok()?;
    (m.version == tango_match::suspend::SUSPENDED_VERSION && !m.checkpoints.is_empty()).then_some(m)
}

/// Every saved match that can be read, newest first.
pub fn list(data_path: &Path) -> Vec<SuspendedMatch> {
    let Ok(rd) = std::fs::read_dir(dir(data_path)) else {
        return Vec::new();
    };
    let mut all: Vec<SuspendedMatch> = rd
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.extension().is_some_and(|e| e == EXT))
        .filter_map(|p| read(&p))
        .collect();
    all.sort_by_key(|m| std::cmp::Reverse(m.saved_at));
    all
}

pub fn delete(data_path: &Path, match_id: u64) {
    let _ = std::fs::remove_file(file(data_path, match_id));
}

/// A date for the list: `15 Oct 14:32`.
pub fn date(saved_at: u64) -> String {
    use chrono::TimeZone;
    chrono::Local
        .timestamp_opt(saved_at as i64, 0)
        .single()
        .map_or_else(String::new, |d| d.format("%d %b %H:%M").to_string())
}
