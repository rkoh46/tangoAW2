// iOS pass-through: nearest-neighbour with anti-aliased texel borders
// ("sharp" sampling). At a whole-number scale it returns exactly the nearest
// texel, like passthrough.wgsl. At a fractional scale (the phone's full-height
// landscape fit, or Stretch) plain nearest makes some pixel columns wider than
// others and shimmers while the map scrolls; here a texel's interior stays a
// flat colour and only the pixel straddling two texels is blended, by how much
// of it each covers. The scale is read from the screen-space derivative of the
// texel coordinate, so no uniform is needed.

fn texel(p: vec2<i32>) -> vec3<f32> {
    return load(p);
}

@fragment
fn fs_main(in: VsOut) -> @location(0) vec4<f32> {
    let dims = vec2<f32>(textureDimensions(fb_texture));
    let t = in.uv * dims;
    // Screen pixels per texel along each axis (derivatives are texels per pixel).
    let scale = 1.0 / max(vec2<f32>(abs(dpdx(t.x)), abs(dpdy(t.y))), vec2<f32>(1e-4));
    let center = floor(t) + vec2<f32>(0.5);
    // Distance from the texel centre in pixels, limited to half a pixel: more
    // than that from the centre is inside the texel, which stays solid.
    let off = clamp((t - center) * scale, vec2<f32>(-0.5), vec2<f32>(0.5));
    // Bilinear weights at the shifted position.
    let p = center + off;
    let base = floor(p - vec2<f32>(0.5));
    let f = p - vec2<f32>(0.5) - base;
    let b = vec2<i32>(base);
    let c00 = texel(b);
    let c10 = texel(b + vec2<i32>(1, 0));
    let c01 = texel(b + vec2<i32>(0, 1));
    let c11 = texel(b + vec2<i32>(1, 1));
    let c = mix(mix(c00, c10, f.x), mix(c01, c11, f.x), f.y);
    return vec4<f32>(c, 1.0);
}
