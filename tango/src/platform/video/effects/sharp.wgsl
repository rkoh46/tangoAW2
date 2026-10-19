// Sharp pass-through (the default): nearest-neighbour with anti-aliased texel
// borders. A texel's interior stays one flat colour and only the screen pixel
// straddling two texels is blended, by how much of it each covers. At a
// whole-number scale the borders fall on pixel edges and the result is exactly
// nearest; at a fractional one (a phone's full-height fit, Stretch) every
// source pixel is a crisp block with at most a one-pixel soft seam, and the
// scaling does not shimmer as the map scrolls. The scale comes from the
// screen-space derivative of the texel coordinate, so no uniform is needed.

@fragment
fn fs_main(in: VsOut) -> @location(0) vec4<f32> {
    let dims = vec2<f32>(textureDimensions(fb_texture));
    let t = in.uv * dims;
    // Texels per screen pixel along each axis.
    let fw = max(vec2<f32>(abs(dpdx(t.x)), abs(dpdy(t.y))), vec2<f32>(1e-4));
    // The nearest texel border, and how far this pixel's centre is past it in
    // pixels: a one-pixel ramp across the border, flat everywhere else.
    let border = floor(t + vec2<f32>(0.5));
    let w = clamp((t - border) / fw + vec2<f32>(0.5), vec2<f32>(0.0), vec2<f32>(1.0));
    let lo = vec2<i32>(border) - vec2<i32>(1, 1);
    let c = mix(
        mix(load(lo), load(lo + vec2<i32>(1, 0)), w.x),
        mix(load(lo + vec2<i32>(0, 1)), load(lo + vec2<i32>(1, 1)), w.x),
        w.y,
    );
    return vec4<f32>(c, 1.0);
}
