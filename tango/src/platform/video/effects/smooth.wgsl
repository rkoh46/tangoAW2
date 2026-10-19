// Smooth pass-through: plain bilinear between texel centres (Settings > Graphics >
// Pixel scaling > Smooth).

@fragment
fn fs_main(in: VsOut) -> @location(0) vec4<f32> {
    let dims = vec2<f32>(textureDimensions(fb_texture));
    let p = in.uv * dims - vec2<f32>(0.5);
    let base = floor(p);
    let f = p - base;
    let b = vec2<i32>(base);
    let c = mix(
        mix(load(b), load(b + vec2<i32>(1, 0)), f.x),
        mix(load(b + vec2<i32>(0, 1)), load(b + vec2<i32>(1, 1)), f.x),
        f.y,
    );
    return vec4<f32>(c, 1.0);
}
