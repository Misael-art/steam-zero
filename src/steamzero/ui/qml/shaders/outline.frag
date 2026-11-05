// SPDX-License-Identifier: GPL-3.0-or-later
// Rebuild: qsb --glsl '100 es,120,150' --hlsl 50 --msl 12 -o outline.frag.qsb outline.frag
#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float radius;
    vec4 outlineColor;
    vec2 outputSize;
    vec4 imageRect;
};
layout(binding = 1) uniform sampler2D source;

float alphaAt(vec2 position) {
    vec2 uv = (position - imageRect.xy) / imageRect.zw;
    if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0))))
        return 0.0;
    return texture(source, uv).a;
}

void main() {
    vec2 position = qt_TexCoord0 * outputSize;
    float original = alphaAt(position);
    float dilated = original;
    // Radius is validated at 1..32 by the recipe contract. Iteration follows
    // the requested radius; no dilation by scaling and no aspect-dependent
    // thickness. The disk also reaches holes and concave boundaries.
    int extent = int(ceil(clamp(radius, 1.0, 32.0)));
    for (int y = -extent; y <= extent; ++y) {
        for (int x = -extent; x <= extent; ++x) {
            vec2 offset = vec2(float(x), float(y));
            float weight = clamp(radius + 1.0 - length(offset), 0.0, 1.0);
            if (weight > 0.0)
                dilated = max(dilated, alphaAt(position + offset) * weight);
        }
    }
    fragColor = outlineColor * (dilated * (1.0 - original)) * qt_Opacity;
}
