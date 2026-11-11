"""Colour parsing and the WCAG 2.1 contrast math.

The three ideas in this file:

1. Relative luminance. Screens store colour with a gamma curve, so #808080 is not "half as bright"
   as white. WCAG first undoes that curve for each channel (to get linear light), then weights the
   channels by how bright the eye finds them: green most, blue least.
2. Contrast ratio. (lighter + 0.05) / (darker + 0.05). It runs from 1:1 (same colour) to 21:1
   (black on white). The 0.05 stands for light reflected off the screen.
3. Alpha compositing. A translucent colour has no contrast of its own: what you see depends on what
   is behind it. So it is blended over its background first, and the result is what gets measured.
"""

from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass

AA_TEXT = 4.5  # WCAG 2.1 SC 1.4.3, normal-size text
AA_LARGE_TEXT = 3.0  # SC 1.4.3, text of at least 24px, or 18.66px and bold
AA_NON_TEXT = 3.0  # SC 1.4.11, UI component boundaries, states and focus indicators


@dataclass(frozen=True)
class Color:
    r: int
    g: int
    b: int
    a: float = 1.0

    @property
    def hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    @property
    def opaque(self) -> bool:
        return self.a >= 1.0

    def __str__(self) -> str:
        return self.hex if self.opaque else f"rgb({self.r} {self.g} {self.b} / {self.a:g})"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _number(token: str) -> float:
    """A plain CSS number. float() alone would also accept nan, inf and 1_000."""
    if not token or any(ch not in "0123456789.+-e" for ch in token):
        raise ValueError(f"{token!r} is not a number")
    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"{token!r} is not a finite number")
    return value


def _step(value: float) -> int:
    """Round to a whole 0-255 step, halves up, as CSS does. Python's round() sends 76.5 to 76."""
    return math.floor(value + 0.5)


def _channel(token: str) -> int:
    if token == "none":
        return 0
    if token.endswith("%"):
        return _step(_clamp(_number(token[:-1]), 0, 100) * 255 / 100)
    return _step(_clamp(_number(token), 0, 255))


def _alpha(token: str) -> float:
    if token == "none":
        return 0.0
    if token.endswith("%"):
        return _clamp(_number(token[:-1]) / 100, 0, 1)
    return _clamp(_number(token), 0, 1)


def _hue(token: str) -> float:
    """A hue as a fraction of a full turn."""
    if token == "none":
        return 0.0
    for unit, per_turn in (("deg", 360.0), ("grad", 400.0), ("rad", math.tau), ("turn", 1.0)):
        if token.endswith(unit):
            return (_number(token[: -len(unit)]) / per_turn) % 1.0
    return (_number(token) / 360.0) % 1.0


def _percent(token: str) -> float:
    if token == "none":
        return 0.0
    return _clamp(_number(token.removesuffix("%")) / 100, 0, 1)


def _parse_hex(digits: str) -> Color:
    if any(ch not in "0123456789abcdef" for ch in digits):
        raise ValueError("a hex colour uses only the digits 0-9 and a-f")
    if len(digits) in (3, 4):
        digits = "".join(ch * 2 for ch in digits)
    if len(digits) not in (6, 8):
        raise ValueError("a hex colour has 3, 4, 6 or 8 digits")
    r, g, b = (int(digits[i : i + 2], 16) for i in (0, 2, 4))
    a = int(digits[6:8], 16) / 255 if len(digits) == 8 else 1.0
    return Color(r, g, b, a)


def _parse_function(name: str, body: str) -> Color:
    # Both syntaxes are accepted: rgb(1, 2, 3, 0.5) and rgb(1 2 3 / 0.5).
    parts = body.replace(",", " ").replace("/", " ").split()
    if len(parts) not in (3, 4):
        raise ValueError(f"{name}() takes three values and an optional alpha")
    alpha = _alpha(parts[3]) if len(parts) == 4 else 1.0
    if name in ("rgb", "rgba"):
        return Color(_channel(parts[0]), _channel(parts[1]), _channel(parts[2]), alpha)
    # colorsys takes hue, lightness, saturation, in that order.
    r, g, b = colorsys.hls_to_rgb(_hue(parts[0]), _percent(parts[2]), _percent(parts[1]))
    return Color(_step(r * 255), _step(g * 255), _step(b * 255), alpha)


def parse_color(text: str) -> Color:
    """Parse a CSS colour: hex, rgb(), rgba(), hsl(), hsla() or a named colour.

    Raises ValueError for anything else, including var(...), which has no colour until it is resolved.
    """
    value = text.strip().lower()
    try:
        if value.startswith("#"):
            return _parse_hex(value[1:])
        if value.endswith(")") and "(" in value:
            name, _, body = value[:-1].partition("(")
            if name.strip() in ("rgb", "rgba", "hsl", "hsla"):
                return _parse_function(name.strip(), body)
        if value == "transparent":
            return Color(0, 0, 0, 0.0)
        if value in NAMED_COLORS:
            return _parse_hex(NAMED_COLORS[value])
    except ValueError as error:
        raise ValueError(f"not a colour: {text!r} ({error})") from None
    raise ValueError(f"not a colour: {text!r}")


def composite(top: Color, bottom: Color) -> Color:
    """Blend a translucent colour over an opaque one: the colour the screen actually shows.

    Each channel is top * alpha + bottom * (1 - alpha), on the stored (gamma-encoded) values, which
    is what browsers do. The result is rounded to whole 0-255 steps, like a real pixel.
    """
    if not bottom.opaque:
        raise ValueError("the bottom colour must be opaque; composite the layers from the page upwards")
    if top.opaque:
        return top
    mix = lambda t, b: _step(t * top.a + b * (1 - top.a))  # noqa: E731
    return Color(mix(top.r, bottom.r), mix(top.g, bottom.g), mix(top.b, bottom.b))


def flatten(layers: list[Color]) -> Color:
    """Composite a stack of layers, given bottom first. The bottom layer must be opaque."""
    result = layers[0]
    if not result.opaque:
        raise ValueError("the bottom layer must be opaque")
    for layer in layers[1:]:
        result = composite(layer, result)
    return result


def _linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(color: Color) -> float:
    """WCAG 2.1 relative luminance of an opaque colour: 0 for black, 1 for white."""
    if not color.opaque:
        raise ValueError("luminance needs an opaque colour; composite it over its background first")
    return 0.2126 * _linear(color.r) + 0.7152 * _linear(color.g) + 0.0722 * _linear(color.b)


def contrast_ratio(first: Color, second: Color) -> float:
    """WCAG 2.1 contrast ratio of two opaque colours, from 1.0 to 21.0. The order does not matter."""
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def shown(ratio: float) -> str:
    """A ratio for display, cut to two decimals and never rounded up.

    Rounding 4.497 to "4.50" would print a pass beside a fail. WCAG thresholds are not rounded.
    """
    return f"{math.floor(ratio * 100 + 1e-9) / 100:.2f}"  # the 1e-9 keeps an exact 4.60 from printing as 4.59


# The CSS named colours (CSS Color Module Level 4), as hex digits.
NAMED_COLORS = {
    "aliceblue": "f0f8ff", "antiquewhite": "faebd7", "aqua": "00ffff", "aquamarine": "7fffd4",
    "azure": "f0ffff", "beige": "f5f5dc", "bisque": "ffe4c4", "black": "000000",
    "blanchedalmond": "ffebcd", "blue": "0000ff", "blueviolet": "8a2be2", "brown": "a52a2a",
    "burlywood": "deb887", "cadetblue": "5f9ea0", "chartreuse": "7fff00", "chocolate": "d2691e",
    "coral": "ff7f50", "cornflowerblue": "6495ed", "cornsilk": "fff8dc", "crimson": "dc143c",
    "cyan": "00ffff", "darkblue": "00008b", "darkcyan": "008b8b", "darkgoldenrod": "b8860b",
    "darkgray": "a9a9a9", "darkgreen": "006400", "darkgrey": "a9a9a9", "darkkhaki": "bdb76b",
    "darkmagenta": "8b008b", "darkolivegreen": "556b2f", "darkorange": "ff8c00",
    "darkorchid": "9932cc", "darkred": "8b0000", "darksalmon": "e9967a", "darkseagreen": "8fbc8f",
    "darkslateblue": "483d8b", "darkslategray": "2f4f4f", "darkslategrey": "2f4f4f",
    "darkturquoise": "00ced1", "darkviolet": "9400d3", "deeppink": "ff1493",
    "deepskyblue": "00bfff", "dimgray": "696969", "dimgrey": "696969", "dodgerblue": "1e90ff",
    "firebrick": "b22222", "floralwhite": "fffaf0", "forestgreen": "228b22", "fuchsia": "ff00ff",
    "gainsboro": "dcdcdc", "ghostwhite": "f8f8ff", "gold": "ffd700", "goldenrod": "daa520",
    "gray": "808080", "green": "008000", "greenyellow": "adff2f", "grey": "808080",
    "honeydew": "f0fff0", "hotpink": "ff69b4", "indianred": "cd5c5c", "indigo": "4b0082",
    "ivory": "fffff0", "khaki": "f0e68c", "lavender": "e6e6fa", "lavenderblush": "fff0f5",
    "lawngreen": "7cfc00", "lemonchiffon": "fffacd", "lightblue": "add8e6", "lightcoral": "f08080",
    "lightcyan": "e0ffff", "lightgoldenrodyellow": "fafad2", "lightgray": "d3d3d3",
    "lightgreen": "90ee90", "lightgrey": "d3d3d3", "lightpink": "ffb6c1", "lightsalmon": "ffa07a",
    "lightseagreen": "20b2aa", "lightskyblue": "87cefa", "lightslategray": "778899",
    "lightslategrey": "778899", "lightsteelblue": "b0c4de", "lightyellow": "ffffe0",
    "lime": "00ff00", "limegreen": "32cd32", "linen": "faf0e6", "magenta": "ff00ff",
    "maroon": "800000", "mediumaquamarine": "66cdaa", "mediumblue": "0000cd",
    "mediumorchid": "ba55d3", "mediumpurple": "9370db", "mediumseagreen": "3cb371",
    "mediumslateblue": "7b68ee", "mediumspringgreen": "00fa9a", "mediumturquoise": "48d1cc",
    "mediumvioletred": "c71585", "midnightblue": "191970", "mintcream": "f5fffa",
    "mistyrose": "ffe4e1", "moccasin": "ffe4b5", "navajowhite": "ffdead", "navy": "000080",
    "oldlace": "fdf5e6", "olive": "808000", "olivedrab": "6b8e23", "orange": "ffa500",
    "orangered": "ff4500", "orchid": "da70d6", "palegoldenrod": "eee8aa", "palegreen": "98fb98",
    "paleturquoise": "afeeee", "palevioletred": "db7093", "papayawhip": "ffefd5",
    "peachpuff": "ffdab9", "peru": "cd853f", "pink": "ffc0cb", "plum": "dda0dd",
    "powderblue": "b0e0e6", "purple": "800080", "rebeccapurple": "663399", "red": "ff0000",
    "rosybrown": "bc8f8f", "royalblue": "4169e1", "saddlebrown": "8b4513", "salmon": "fa8072",
    "sandybrown": "f4a460", "seagreen": "2e8b57", "seashell": "fff5ee", "sienna": "a0522d",
    "silver": "c0c0c0", "skyblue": "87ceeb", "slateblue": "6a5acd", "slategray": "708090",
    "slategrey": "708090", "snow": "fffafa", "springgreen": "00ff7f", "steelblue": "4682b4",
    "tan": "d2b48c", "teal": "008080", "thistle": "d8bfd8", "tomato": "ff6347",
    "turquoise": "40e0d0", "violet": "ee82ee", "wheat": "f5deb3", "white": "ffffff",
    "whitesmoke": "f5f5f5", "yellow": "ffff00", "yellowgreen": "9acd32",
}
