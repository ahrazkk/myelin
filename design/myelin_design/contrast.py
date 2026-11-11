"""The contrast linter: WCAG 2.1 AA for every colour pair the design system uses.

A stylesheet does not say which text sits on which background: that depends on how elements nest
on the page. So the pairs are declared by hand in design.toml, each with a note saying where it
occurs, and this module does the measuring:

    surface   a named stack of layers, bottom first, such as ["slide", "myelin-wash"]. The stack is
              composited into one opaque colour before anything is measured.
    pair      a foreground token on a surface, with a kind that sets the threshold:
                text       4.5:1  (SC 1.4.3)
                large-text 3:1    (SC 1.4.3, at least 24px, or 18.66px bold)
                non-text   3:1    (SC 1.4.11: control boundaries, states, focus indicators)
                decorative, inactive: measured and reported, but exempt, so never a failure

Each pair is measured in every theme, under every accent it depends on, and (for surfaces that
include the sky the app paints behind the page) against every sky colour.

One thing the linter can check on its own: when a CSS rule sets both a text colour and a
background, that pair must be declared. That stops a new combination slipping in unmeasured.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from . import css, tokens
from .color import AA_LARGE_TEXT, AA_NON_TEXT, AA_TEXT, Color, composite, contrast_ratio, flatten, shown
from .compliance import split_ts

THRESHOLDS: dict[str, float | None] = {
    "text": AA_TEXT,
    "large-text": AA_LARGE_TEXT,
    "non-text": AA_NON_TEXT,
    "decorative": None,
    "inactive": None,
}
TEXT_KINDS = ("text", "large-text", "inactive")
SKY = "@sky"  # a layer that stands for each sky colour in turn

_VAR = re.compile(r"^var\(\s*--([a-z][a-z0-9-]*)\s*(?:,.*)?\)$")
_SKY_ENTRY = re.compile(r"(\w+)\s*:\s*\[\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\]")


class ConfigError(Exception):
    """design.toml asks for something that cannot be measured."""


@dataclass(frozen=True)
class Pair:
    foreground: str
    surface: str
    kind: str
    opacity: float
    where: str
    known_failure: str | None
    entry: int = 0  # which [[contrast.pair]] entry it came from, counting from 0


@dataclass(frozen=True)
class Result:
    foreground: str
    surface: str
    kind: str
    opacity: float
    theme: str
    accent: str | None  # None when the pair does not depend on the accent
    sky: str | None  # the weather scene, for surfaces that include the sky
    foreground_hex: str  # as shown: after opacity and compositing
    background_hex: str
    ratio: float
    threshold: float | None
    status: str  # "pass", "fail", "known" (a failure accepted in design.toml) or "info" (exempt)

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["ratio"] = float(shown(self.ratio))
        return data


def read_sky(source: str, constant: str) -> dict[str, Color]:
    """Read a table of sky colours, such as SKY_DAY, straight out of the TypeScript source.

    Reading the source means the linter measures what the app paints. A hand-made copy could drift.
    """
    code, _ = split_ts(source)
    start = re.search(rf"\bconst\s+{re.escape(constant)}\b[^=]*=\s*\{{", code)
    if start is None:
        raise ConfigError(f"sky table {constant} not found")
    end = code.find("}", start.end())
    body = code[start.end() : end if end != -1 else len(code)]
    sky = {name: Color(int(r), int(g), int(b)) for name, r, g, b in _SKY_ENTRY.findall(body)}
    if not sky:
        raise ConfigError(f"sky table {constant} has no colours")
    # Every "key: [" in the table must have been read. A skipped scene would never be measured.
    if body.count("[") != len(sky) or any(max(c.r, c.g, c.b) > 255 for c in sky.values()):
        raise ConfigError(f"sky table {constant} has an entry that is not a plain [r, g, b] colour")
    return sky


def read_pairs(config: dict[str, Any], document: dict[str, Any]) -> tuple[dict[str, list[str]], list[Pair]]:
    """The surfaces and pairs from design.toml, checked against the tokens.

    Anything that cannot be measured as written is a ConfigError, never a silent default.
    """
    names = {token["name"] for token in document["tokens"]}
    section = config.get("contrast", {})
    surfaces: dict[str, list[str]] = section.get("surfaces", {})
    for name, layers in surfaces.items():
        if not isinstance(layers, list) or not layers:
            raise ConfigError(f"surface {name!r} must be a list with at least one layer")
        for layer in layers:
            if layer != SKY and layer not in names:
                raise ConfigError(f"surface {name!r} uses {layer!r}, which is not a token")

    pairs: list[Pair] = []
    seen: set[tuple[str, str, str, float]] = set()
    for index, entry in enumerate(section.get("pair", [])):
        label = f"contrast.pair #{index + 1}"
        for key in ("foreground", "on", "kind"):
            if key not in entry:
                raise ConfigError(f"{label} has no {key!r}")
        if entry["foreground"] not in names:
            raise ConfigError(f"{label} uses foreground {entry['foreground']!r}, which is not a token")
        if entry["kind"] not in THRESHOLDS:
            raise ConfigError(f"{label} has kind {entry['kind']!r}; use one of {', '.join(THRESHOLDS)}")
        if not isinstance(entry["on"], list) or not entry["on"]:
            raise ConfigError(f"{label}: 'on' must be a list of surface names")
        opacity = entry.get("opacity", 1.0)
        if isinstance(opacity, bool) or not isinstance(opacity, (int, float)) or not 0 < opacity <= 1:
            raise ConfigError(f"{label}: opacity must be a number above 0 and at most 1, not {opacity!r}")
        known = entry.get("known_failure")
        if known is not None and (not isinstance(known, str) or not known.strip()):
            raise ConfigError(f"{label}: known_failure must give a reason")
        for surface in entry["on"]:
            if surface not in surfaces:
                raise ConfigError(f"{label} uses surface {surface!r}, which is not defined")
            key = (entry["foreground"], surface, entry["kind"], float(opacity))
            if key in seen:
                raise ConfigError(f"{label} repeats an earlier pair: {entry['foreground']} on {surface} ({entry['kind']})")
            seen.add(key)
            pairs.append(Pair(entry["foreground"], surface, entry["kind"], float(opacity), entry.get("where", ""), known, index))
    return surfaces, pairs


def evaluate(
    document: dict[str, Any],
    surfaces: dict[str, list[str]],
    pairs: list[Pair],
    skies: dict[str, dict[str, Color]] | None = None,
) -> list[Result]:
    """Measure every pair in every theme, accent and sky it applies to."""
    accent_tokens = {token["name"] for token in document["tokens"] if "accents" in token}
    results: list[Result] = []
    for pair in pairs:
        layers = surfaces[pair.surface]
        by_accent = pair.foreground in accent_tokens or any(layer in accent_tokens for layer in layers)
        threshold = THRESHOLDS[pair.kind]
        for theme in document["themes"]:
            if SKY in layers:
                if not skies or theme not in skies:
                    raise ConfigError(f"surface {pair.surface!r} needs the sky colours for {theme}")
                scenes: list[tuple[str | None, Color | None]] = list(skies[theme].items())
            else:
                scenes = [(None, None)]
            for accent in document["accents"] if by_accent else [None]:
                colors = tokens.resolve(document, theme, accent)
                for scene, sky in scenes:
                    stack = [sky if layer == SKY else colors[layer] for layer in layers]
                    if not stack[0].opaque:
                        raise ConfigError(f"surface {pair.surface!r} must start with an opaque layer")
                    background = flatten(stack)
                    ink = colors[pair.foreground]
                    foreground = composite(Color(ink.r, ink.g, ink.b, ink.a * pair.opacity), background)
                    ratio = contrast_ratio(foreground, background)
                    if threshold is None:
                        status = "info"
                    elif ratio >= threshold:
                        status = "pass"
                    else:
                        status = "known" if pair.known_failure else "fail"
                    results.append(
                        Result(
                            pair.foreground, pair.surface, pair.kind, pair.opacity, theme, accent, scene,
                            foreground.hex, background.hex, ratio, threshold, status,
                        )
                    )
    return results


def stale_known_failures(pairs: list[Pair], results: list[Result]) -> list[str]:
    """Entries marked as known failures that no longer fail anywhere. The mark should be removed.

    An entry can list several surfaces, and it is judged as a whole: the mark is stale only when
    none of its surfaces has a failing measurement.
    """
    failing = {(r.foreground, r.surface, r.kind, r.opacity) for r in results if r.status in ("known", "fail")}
    problems = []
    for index in sorted({pair.entry for pair in pairs if pair.known_failure}):
        mine = [pair for pair in pairs if pair.entry == index]
        if not any((p.foreground, p.surface, p.kind, p.opacity) in failing for p in mine):
            first = mine[0]
            on = ", ".join(pair.surface for pair in mine)
            problems.append(f"{first.foreground} on {on} ({first.kind}) is marked known_failure but nothing in it fails; remove the mark")
    return problems


def token_in(value: str | None, token_names: set[str]) -> str | None:
    """The design token a CSS value takes its colour from, if it is a single var(--token).

    Accepts the forms that mean the same thing: VAR(--x), var(--x) !important, var(--x, #fff).
    """
    text = (value or "").lower().replace("!important", "").strip()
    match = _VAR.match(text)
    return match[1] if match and match[1] in token_names else None


def background_of(rule: css.Rule) -> str | None:
    """A rule's background: whichever of background and background-color comes last, as in CSS."""
    for declaration in reversed(rule.declarations):
        if declaration.prop in ("background", "background-color"):
            return declaration.value
    return None


def undeclared_pairs(css_text: str, surfaces: dict[str, list[str]], pairs: list[Pair], token_names: set[str]) -> list[tuple[int, str, str, str | None]]:
    """Text colours in a stylesheet that no declared pair covers.

    Returns (line, selector, foreground, background) for each. A rule that sets only a colour needs
    that token declared as text on some surface. A rule that also sets a background needs that exact
    combination declared, on a surface whose top layer is that background.
    """
    declared_text = {pair.foreground for pair in pairs if pair.kind in TEXT_KINDS}
    declared_on = {(pair.foreground, surfaces[pair.surface][-1]) for pair in pairs if pair.kind in TEXT_KINDS}
    missing = []
    for rule in css.parse(css_text):
        foreground = token_in(rule.get("color"), token_names)
        if foreground is None:
            continue
        background = token_in(background_of(rule), token_names)
        covered = (foreground, background) in declared_on if background else foreground in declared_text
        if not covered:
            missing.append((rule.line, rule.selector, foreground, background))
    return missing
