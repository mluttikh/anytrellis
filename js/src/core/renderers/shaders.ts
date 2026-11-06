// The one primitive, in GLSL (WebGL2) and WGSL (WebGPU): six vertices per instance, a box
// for a rectangle or a capsule around a segment, antialiased by distance in the fragment.

export const GLSL_VS = /* glsl */ `#version 300 es
precision highp float;
in vec4 a_coords;
in vec4 a_color;
uniform vec2 u_canvas;
uniform vec4 u_map;
uniform vec2 u_shape;
out vec2 v_local;
out vec2 v_seg;
out vec4 v_color;
flat out int v_kind;
void main() {
  int c = gl_VertexID % 6;
  vec2 corner = vec2((c == 1 || c == 2 || c == 4) ? 1.0 : 0.0, (c == 2 || c == 4 || c == 5) ? 1.0 : 0.0);
  vec2 a = vec2(u_map.y + a_coords.x * u_map.x, u_map.w + a_coords.y * u_map.z);
  vec2 b = vec2(u_map.y + a_coords.z * u_map.x, u_map.w + a_coords.w * u_map.z);
  v_color = a_color;
  v_kind = int(u_shape.y + 0.5);
  vec2 px;
  if (any(isnan(a_coords)) || any(isinf(a_coords))) {
    gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    return;
  }
  if (v_kind == 0) {
    vec2 lo = min(a, b);
    vec2 hi = max(a, b);
    vec2 mid = (lo + hi) * 0.5;
    vec2 half_ = max((hi - lo) * 0.5, vec2(0.5));
    lo = mid - half_;
    hi = mid + half_;
    px = mix(lo, hi, corner);
    v_local = vec2(0.0);
    v_seg = vec2(0.0);
  } else {
    vec2 d = b - a;
    float len = length(d);
    vec2 dir = len > 1e-4 ? d / len : vec2(1.0, 0.0);
    vec2 nrm = vec2(-dir.y, dir.x);
    float r = u_shape.x + 1.0;
    float along = corner.x > 0.5 ? len + r : -r;
    float across = corner.y > 0.5 ? r : -r;
    px = a + dir * along + nrm * across;
    v_local = vec2(along, across);
    v_seg = vec2(len, u_shape.x);
  }
  gl_Position = vec4(px.x / u_canvas.x * 2.0 - 1.0, 1.0 - px.y / u_canvas.y * 2.0, 0.0, 1.0);
}`;

export const GLSL_FS = /* glsl */ `#version 300 es
precision highp float;
in vec2 v_local;
in vec2 v_seg;
in vec4 v_color;
flat in int v_kind;
uniform float u_opacity;
uniform float u_dpr;
out vec4 outColor;
void main() {
  float cover = 1.0;
  if (v_kind == 1) {
    float x = clamp(v_local.x, 0.0, v_seg.x);
    float d = length(vec2(v_local.x - x, v_local.y)) - v_seg.y;
    cover = clamp(0.5 - d * u_dpr, 0.0, 1.0);
  }
  float a = v_color.a * u_opacity * cover;
  if (a < 0.003) discard;
  outColor = vec4(v_color.rgb * a, a);
}`;

export const WGSL = /* wgsl */ `
struct U {
  canvas: vec2f,
  dpr: f32,
  opacity: f32,
  map: vec4f,
  shape: vec2f,
};
@group(0) @binding(0) var<uniform> u: U;

struct Out {
  @builtin(position) pos: vec4f,
  @location(0) local: vec2f,
  @location(1) seg: vec2f,
  @location(2) color: vec4f,
  @location(3) @interpolate(flat) kind: u32,
};

fn bad(v: f32) -> bool {
  return !(abs(v) < 3.0e38);
}

@vertex
fn vs(@builtin(vertex_index) vi: u32, @location(0) coords: vec4f, @location(1) color: vec4f) -> Out {
  var o: Out;
  let c = vi % 6u;
  let corner = vec2f(select(0.0, 1.0, c == 1u || c == 2u || c == 4u), select(0.0, 1.0, c == 2u || c == 4u || c == 5u));
  let a = vec2f(u.map.y + coords.x * u.map.x, u.map.w + coords.y * u.map.z);
  let b = vec2f(u.map.y + coords.z * u.map.x, u.map.w + coords.w * u.map.z);
  o.color = color;
  o.kind = u32(u.shape.y + 0.5);
  if (bad(coords.x) || bad(coords.y) || bad(coords.z) || bad(coords.w)) {
    o.pos = vec4f(2.0, 2.0, 2.0, 1.0);
    return o;
  }
  var px: vec2f;
  if (o.kind == 0u) {
    let mid = (min(a, b) + max(a, b)) * 0.5;
    let half = max((max(a, b) - min(a, b)) * 0.5, vec2f(0.5));
    px = mix(mid - half, mid + half, corner);
    o.local = vec2f(0.0);
    o.seg = vec2f(0.0);
  } else {
    let d = b - a;
    let len = length(d);
    let dir = select(vec2f(1.0, 0.0), d / max(len, 1e-6), len > 1e-4);
    let nrm = vec2f(-dir.y, dir.x);
    let r = u.shape.x + 1.0;
    let along = select(-r, len + r, corner.x > 0.5);
    let across = select(-r, r, corner.y > 0.5);
    px = a + dir * along + nrm * across;
    o.local = vec2f(along, across);
    o.seg = vec2f(len, u.shape.x);
  }
  o.pos = vec4f(px.x / u.canvas.x * 2.0 - 1.0, 1.0 - px.y / u.canvas.y * 2.0, 0.0, 1.0);
  return o;
}

@fragment
fn fs(i: Out) -> @location(0) vec4f {
  var cover = 1.0;
  if (i.kind == 1u) {
    let x = clamp(i.local.x, 0.0, i.seg.x);
    let d = length(vec2f(i.local.x - x, i.local.y)) - i.seg.y;
    cover = clamp(0.5 - d * u.dpr, 0.0, 1.0);
  }
  let a = i.color.a * u.opacity * cover;
  if (a < 0.003) {
    discard;
  }
  return vec4f(i.color.rgb * a, a);
}
`;
