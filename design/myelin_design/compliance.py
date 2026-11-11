"""Token compliance: does the code take its colours from the design tokens, or hard-code them?

Every place a colour is used is a "use". A use is either a token (var(--ink)) or a literal (#1b2142).
Compliance is token uses divided by all uses. The scanners here find the uses; lint.py adds them up.

    CSS         each declaration value is scanned. Token definitions (--ink: #1b2142) are not uses.
    TS and TSX  there is no CSS to parse, so the scanner pulls out string and template literals
                (skipping comments) and looks for colours inside them.

Nothing here executes the code it reads. It is all text scanning, in one pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import css
from .color import NAMED_COLORS, Color, parse_color

TOKEN = "token"  # var(--ink): what we want
LITERAL = "literal"  # #1b2142 or rgb(...): a hard-coded colour
TOKEN_COPY = "token-copy"  # a literal with exactly a token's value: the drift risk
UNKNOWN_TOKEN = "unknown-token"  # var(--inc): a token that does not exist, usually a typo

# Functions that produce a colour. A call with a var() inside is built from tokens, so it is not a literal.
COLOR_FUNCTIONS = frozenset(
    {"rgb", "rgba", "hsl", "hsla", "hwb", "lab", "lch", "oklab", "oklch", "color", "color-mix"}
)
# Named colours are only looked for in properties that take a colour, so "tan" in a font name is not flagged.
_COLOR_PROPERTY_PARTS = (
    "color", "background", "border", "outline", "shadow", "fill", "stroke", "decoration", "caret", "column-rule",
)
_IDENT_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_PLACEHOLDER = "${}"  # stands in for a ${...} expression inside a template literal


@dataclass(frozen=True)
class Use:
    kind: str
    text: str
    line: int
    detail: str = ""

    @property
    def hard_coded(self) -> bool:
        return self.kind in (LITERAL, TOKEN_COPY)


@dataclass(frozen=True)
class Palette:
    """What the scanners need to know about the tokens: their names and their values."""

    names: frozenset[str]
    values: tuple[tuple[Color, str], ...]  # (colour, where it comes from), e.g. (#2d6bad, "--myelin (day)")

    @classmethod
    def from_document(cls, document: dict) -> Palette:
        values: list[tuple[Color, str]] = []
        for token in document["tokens"]:
            variants = [("", token["values"])]
            variants += [(f"{accent} ", themed) for accent, themed in token.get("accents", {}).items()]
            for prefix, themed in variants:
                for theme, entry in themed.items():
                    rgb = parse_color(entry["hex"])
                    values.append((Color(rgb.r, rgb.g, rgb.b, entry["alpha"]), f"{token['cssVariable']} ({prefix}{theme})"))
        return cls(frozenset(token["name"] for token in document["tokens"]), tuple(values))

    def matches(self, color: Color) -> list[str]:
        """The tokens that have exactly this colour (same RGB, same alpha)."""
        return [
            label
            for value, label in self.values
            if (value.r, value.g, value.b) == (color.r, color.g, color.b) and abs(value.a - color.a) < 0.005
        ]

    def matches_rgb(self, r: int, g: int, b: int) -> list[str]:
        """The tokens that have this RGB. Opaque tokens come first; washes only if nothing else matches."""
        same = [(value, label) for value, label in self.values if (value.r, value.g, value.b) == (r, g, b)]
        opaque = [label for value, label in same if value.opaque]
        return opaque or [label for _, label in same]


def _literal(text: str, line: int, palette: Palette) -> Use:
    try:
        same = palette.matches(parse_color(text))
    except ValueError:
        same = []
    if same:
        return Use(TOKEN_COPY, text, line, "same colour as " + ", ".join(same))
    return Use(LITERAL, text, line)


def scan_value(value: str, line: int, palette: Palette, *, named: bool = True, quotes: bool = True) -> list[Use]:
    """Find the colour uses in one CSS value, or in the text of one string literal.

    named: also look for colour names such as "white". quotes: skip over quoted text, as in a CSS
    value like font-family: "Tan Pearl". Both are off for the inside of a JavaScript string.
    """
    uses: list[Use] = []
    i = 0
    n = len(value)
    while i < n:
        ch = value[i]
        if quotes and ch in "\"'":
            end = value.find(ch, i + 1)
            i = n if end == -1 else end + 1
        elif ch == "#":
            j = i + 1
            while j < n and value[j] in _HEX_DIGITS:
                j += 1
            if j - i - 1 in (3, 4, 6, 8) and (j == n or value[j] not in _IDENT_CHARS):
                uses.append(_literal(value[i:j], line, palette))
            i = max(j, i + 1)
        elif ch in _IDENT_CHARS and not ch.isdigit():
            j = i
            while j < n and value[j] in _IDENT_CHARS:
                j += 1
            word = value[i:j].lower()
            is_call = j < n and value[j] == "("
            if is_call and word == "url":
                end = value.find(")", j)
                i = n if end == -1 else end + 1
            elif is_call and word == "var":
                name = value[j + 1 :].lstrip()
                end = 0
                while end < len(name) and name[end] in _IDENT_CHARS:
                    end += 1
                name = name[:end]
                if name.startswith("--"):
                    kind = TOKEN if name[2:] in palette.names else UNKNOWN_TOKEN
                    uses.append(Use(kind, f"var({name})", line))
                i = j + 1  # keep scanning: a fallback such as var(--x, #fff) is still a literal
            elif is_call and word in COLOR_FUNCTIONS:
                end = _closing_paren(value, j)
                call = value[i:end]
                if "var(" in call.lower():
                    i = j + 1  # built from tokens: count the var() uses inside instead
                elif _is_computed(call):
                    i = end  # rgba(${r},${g},${b},...) in a template: the colour comes from code
                else:
                    uses.append(_literal(call, line, palette))
                    i = end
            elif named and not is_call and word in NAMED_COLORS and (i == 0 or value[i - 1] not in "-."):
                uses.append(_literal(value[i:j], line, palette))
                i = j
            else:
                i = j
        else:
            i += 1
    return uses


def _closing_paren(text: str, open_at: int) -> int:
    """The index just past the parenthesis that closes the one at open_at."""
    depth = 0
    for k in range(open_at, len(text)):
        if text[k] == "(":
            depth += 1
        elif text[k] == ")":
            depth -= 1
            if depth == 0:
                return k + 1
    return len(text)


def _is_computed(call: str) -> bool:
    """True for a template such as rgba(${r},${g},${b},0.5), whose three channels all come from code."""
    body = call.partition("(")[2].rstrip(")")
    parts = body.replace(",", " ").replace("/", " ").split()
    return len(parts) >= 3 and all(part == _PLACEHOLDER for part in parts[:3])


def _takes_color(prop: str) -> bool:
    return any(part in prop for part in _COLOR_PROPERTY_PARTS)


def scan_css(text: str, palette: Palette) -> list[Use]:
    """Every colour use in a stylesheet. Custom-property definitions are the token block, not uses."""
    uses: list[Use] = []
    for rule in css.parse(text):
        for declaration in rule.declarations:
            if declaration.prop.startswith("--"):
                continue
            uses += scan_value(declaration.value, declaration.line, palette, named=_takes_color(declaration.prop))
    return uses


# ---- TypeScript and TSX ----


@dataclass(frozen=True)
class _String:
    text: str  # the literal's content, with each ${...} replaced by ${}
    line: int
    start: int  # offset of the opening quote in the source


def split_ts(source: str) -> tuple[str, list[_String]]:
    """Separate code from string literals, dropping comments.

    Returns the code with every comment and string blanked out (same length, same line breaks) and
    the list of string and template literals. Template literals can nest: `a ${ `b` } c`.
    """
    code = list(source)
    strings: list[_String] = []
    n = len(source)
    i = 0
    line = 1
    # Each open template is [start offset, start line, parts so far, brace depth inside ${...}].
    # A depth of 0 means we are in the template's text; above 0 means inside an expression.
    templates: list[list] = []

    def blank(start: int, end: int) -> None:
        for k in range(start, end):
            if code[k] != "\n":
                code[k] = " "

    while i < n:
        ch = source[i]
        in_text = bool(templates) and templates[-1][3] == 0

        if in_text:
            template = templates[-1]
            if ch == "\\":
                template[2].append(source[i : i + 2])
                i += 2
            elif ch == "`":
                start, start_line, parts, _ = templates.pop()
                strings.append(_String("".join(parts), start_line, start))
                blank(start, i + 1)
                i += 1
            elif source.startswith("${", i):
                template[2].append(_PLACEHOLDER)
                template[3] = 1
                i += 2
            else:
                if ch == "\n":
                    line += 1
                template[2].append(ch)
                i += 1
            continue

        if source.startswith("//", i):
            end = source.find("\n", i)
            end = n if end == -1 else end
            blank(i, end)
            i = end
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            end = n if end == -1 else end + 2
            line += source.count("\n", i, end)
            blank(i, end)
            i = end
        elif ch in "\"'":
            j = i + 1
            while j < n and source[j] != ch and source[j] != "\n":
                j += 2 if source[j] == "\\" else 1
            j = min(j, n)
            strings.append(_String(source[i + 1 : j], line, i))
            closed = j < n and source[j] == ch
            blank(i, j + 1 if closed else j)
            i = j + 1 if closed else j
        elif ch == "`":
            templates.append([i, line, [], 0])
            i += 1
        else:
            if ch == "\n":
                line += 1
            elif templates and ch == "{":
                templates[-1][3] += 1
            elif templates and ch == "}":
                templates[-1][3] -= 1  # back to 0 means the ${...} expression has ended
            i += 1

    for start, start_line, parts, _ in templates:  # templates never closed: keep what was read
        strings.append(_String("".join(parts), start_line, start))
    strings.sort(key=lambda string: string.start)
    return "".join(code), strings


_CSS_VARIABLE = re.compile(r"--[a-z][a-z0-9-]*")
_RGB_TRIPLE = re.compile(r"\[\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\]")
# What comes just before a string that is being used as a colour: fillStyle = "white", color: "red".
_COLOR_SLOT = re.compile(
    r"(?:color|background|fill|stroke|fillstyle|strokestyle)[\"']?\s*[:=]\s*$|addcolorstop\([^,()]*,\s*$",
    re.IGNORECASE,
)


def scan_ts(source: str, palette: Palette) -> list[Use]:
    """Every colour use in a TypeScript or TSX file."""
    code, strings = split_ts(source)
    uses: list[Use] = []

    for string in strings:
        text = string.text
        found = scan_value(text, string.line, palette, named=False, quotes=False)
        var_names = {use.text[4:-1] for use in found if use.kind in (TOKEN, UNKNOWN_TOKEN)}
        uses += found
        # A token read at runtime, such as getPropertyValue("--slide"), also takes its colour from the tokens.
        for match in _CSS_VARIABLE.finditer(text):
            name = match.group()
            if name not in var_names and name[2:] in palette.names and (match.start() == 0 or text[match.start() - 1] not in _IDENT_CHARS):
                uses.append(Use(TOKEN, name, string.line, "read at runtime"))
        # A whole string that is a colour name, sitting where a colour goes.
        if text.strip().lower() in NAMED_COLORS and _COLOR_SLOT.search(code[max(0, string.start - 60) : string.start]):
            uses.append(_literal(text.strip(), string.line, palette))

    # A bare [r, g, b] is only called a colour when it is exactly a token's colour: a hand-made copy.
    for match in _RGB_TRIPLE.finditer(code):
        r, g, b = (int(group) for group in match.groups())
        same = palette.matches_rgb(r, g, b) if max(r, g, b) <= 255 else []
        if same:
            line = source.count("\n", 0, match.start()) + 1
            uses.append(Use(TOKEN_COPY, " ".join(match.group().split()), line, "same colour as " + ", ".join(same)))

    uses.sort(key=lambda use: use.line)
    return uses


def count_other_triples(source: str, palette: Palette) -> int:
    """Bare [r, g, b] arrays that are not a token's colour. They may be colours; the scanner cannot tell."""
    code, _ = split_ts(source)
    count = 0
    for match in _RGB_TRIPLE.finditer(code):
        r, g, b = (int(group) for group in match.groups())
        if max(r, g, b) <= 255 and not palette.matches_rgb(r, g, b):
            count += 1
    return count


def scan(text: str, language: str, palette: Palette) -> list[Use]:
    """Scan a snippet. Language is 'css', 'ts' or 'tsx'."""
    language = language.lower().lstrip(".")
    if language == "css":
        return scan_css(text, palette)
    if language in ("ts", "tsx", "js", "jsx"):
        return scan_ts(text, palette)
    raise ValueError(f"unsupported language {language!r}; use css, ts or tsx")


def percentage(token_uses: int, hard_coded: int) -> float | None:
    """Token uses as a share of all colour uses, or None when there are no colour uses at all."""
    total = token_uses + hard_coded
    return None if total == 0 else 100 * token_uses / total
