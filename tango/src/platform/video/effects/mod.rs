//! The pluggable framebuffer effect registry. Each [`Effect`] is a GPU
//! upscaler (or the pass-through) defined as a named constant in a submodule
//! — `hqx::HQ2X`, `mmpx::MMPX`, etc. — built from the WGSL `.wgsl` files in
//! this directory. [`EFFECTS`] maps the `config.video_filter` key to each.

use crate::platform::video::framebuffer::{Effect, WgslRenderer};

pub mod hqx;
pub mod lcd;
pub mod mmpx;

/// Shared infrastructure WGSL (vertex shader, bindings, `load`); prepended to
/// every effect.
pub(crate) const COMMON: &str = include_str!("common.wgsl");

/// Sharp pass-through, the default ("—" / no filter, and the fallback for
/// unknown keys). Each source pixel is a flat block and only the one screen
/// pixel straddling two blocks is blended, so the picture is crisp at any
/// scale and exactly nearest at a whole-number one.
static PASSTHROUGH_RENDERER: WgslRenderer = WgslRenderer::new(&[COMMON, include_str!("sharp.wgsl")]);
pub const PASSTHROUGH: Effect = Effect::new("", "—", 1, &PASSTHROUGH_RENDERER);

/// Settings > Graphics > Pixel scaling "Smooth": plain bilinear.
static SMOOTH_RENDERER: WgslRenderer = WgslRenderer::new(&[COMMON, include_str!("smooth.wgsl")]);
pub const SMOOTH: Effect = Effect::new("smooth", "Smooth", 1, &SMOOTH_RENDERER);

/// "Pixel-perfect": nearest (the frame is only ever drawn at a whole-number scale).
static PIXEL_RENDERER: WgslRenderer = WgslRenderer::new(&[COMMON, include_str!("passthrough.wgsl")]);
pub const PIXEL: Effect = Effect::new("pixel", "Pixel-perfect", 1, &PIXEL_RENDERER);

/// The effect for the unfiltered picture under `config.pixel_scaling`
/// (`"smooth"`, `"pixel"`; anything else is Sharp).
pub fn scaler_for(pixel_scaling: &str) -> &'static Effect {
    match pixel_scaling {
        "smooth" => &SMOOTH,
        "pixel" => &PIXEL,
        _ => &PASSTHROUGH,
    }
}

/// The registry, in pick-list order. The `&str` is the `config.video_filter`
/// key (unchanged from the old CPU registry, so existing configs keep
/// working); the first entry is the canonical pass-through.
pub static EFFECTS: &[&Effect] = &[&PASSTHROUGH, &hqx::HQ2X, &hqx::HQ3X, &hqx::HQ4X, &mmpx::MMPX, &lcd::LCD];

/// Resolve a `config.video_filter` key to its effect. Unknown / empty keys
/// fall back to the pass-through (index 0).
pub fn effect_for(id: &str) -> &'static Effect {
    EFFECTS
        .iter()
        .find(|effect| effect.id == id)
        .cloned()
        .unwrap_or(&PASSTHROUGH)
}

/// `config.video_filter` and `config.pixel_scaling` resolved: a pixel filter
/// (hq2x...) as picked, the unfiltered picture as the pixel-scaling choice.
pub fn effect_for_config(id: &str, pixel_scaling: &str) -> &'static Effect {
    let effect = effect_for(id);
    if effect.id.is_empty() {
        scaler_for(pixel_scaling)
    } else {
        effect
    }
}
