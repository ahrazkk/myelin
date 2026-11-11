"""Read the design tokens out of the stylesheet and build the contract (design/tokens.json).

Myelin declares its tokens as CSS custom properties on :root, in six kinds of rule:

    :root                                            day, default accent
    :root[data-theme="night"]                        night, when the app sets the theme
    @media (prefers-color-scheme: dark)
      :root:not([data-theme="day"])                  night, when the system is dark
    :root[data-accent="X"]                           day, accent X
    :root[data-theme="night"][data-accent="X"]       night, accent X, set by the app
    @media dark :root:not([data-theme="day"])[data-accent="X"]   night, accent X, from the system

Night is written twice because CSS has no way to say "this attribute OR this media query" in one
rule. Two copies can drift apart, so the export checks that they agree and fails if they do not.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import jsonschema

from . import css
from .color import Color, parse_color
from .project import Project, read_text

THEMES = ("day", "night")
ROLES = ("background", "text", "accent", "border", "wash")

_ROOT_PART = re.compile(
    r"""\[data-theme="(?P<theme>[a-z]+)"\]"""
    r"""|\[data-accent="(?P<accent>[a-z][a-z0-9-]*)"\]"""
    r"""|:not\(\[data-theme="(?P<not_theme>[a-z]+)"\]\)"""
)


_DARK_MEDIA = (
    "@media(prefers-color-scheme:dark)",
    "@mediascreenand(prefers-color-scheme:dark)",
    "@mediaalland(prefers-color-scheme:dark)",
)


class TokenError(Exception):
    """The stylesheet and the contract disagree. Carries every problem found, not just the first."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Context:
    """Where a token rule applies. 'via' is how night is switched on: by attribute or by media query."""

    theme: str
    accent: str | None
    via: str  # "base", "attribute" or "media"


def classify(rule: css.Rule) -> Context | None:
    """Work out which theme and accent a rule sets tokens for.

    Returns None for rules that are not on :root alone. Raises ValueError for a :root rule in a
    shape this exporter has not been taught, so a new kind of theme rule cannot be silently dropped.
    """
    selector = rule.selector.replace("'", '"')
    if not selector.startswith(":root") or " " in selector or "," in selector:
        return None
    rest = selector[len(":root") :]
    theme = accent = not_theme = None
    position = 0
    while position < len(rest):
        match = _ROOT_PART.match(rest, position)
        if match is None:
            raise ValueError(f"unrecognised selector {rule.selector!r}")
        theme = match["theme"] or theme
        accent = match["accent"] or accent
        not_theme = match["not_theme"] or not_theme
        position = match.end()

    # The media query must be exactly "the system is dark". A negated or narrowed query, such as
    # "not (prefers-color-scheme: dark)" or "print and (...)", is not the system-night copy.
    in_dark_media = any(at.lower().replace(" ", "") in _DARK_MEDIA for at in rule.at_rules)
    if theme is None and not_theme is None and not rule.at_rules:
        return Context("day", accent, "base")
    if theme == "night" and not_theme is None and not rule.at_rules:
        return Context("night", accent, "attribute")
    if theme is None and not_theme == "day" and in_dark_media and len(rule.at_rules) == 1:
        return Context("night", accent, "media")
    where = f" inside {' '.join(rule.at_rules)}" if rule.at_rules else ""
    raise ValueError(f"unrecognised theme rule {rule.selector!r}{where}")


def _same(first: Color, second: Color) -> bool:
    return (first.r, first.g, first.b) == (second.r, second.g, second.b) and abs(first.a - second.a) < 1e-9


def _color_entry(css_text: str, color: Color) -> dict[str, Any]:
    return {"css": css_text, "hex": color.hex, "alpha": round(color.a, 4)}


def read_declarations(css_text: str) -> tuple[dict[tuple[str, Context], tuple[str, Color, int]], list[str]]:
    """Every token declaration in the stylesheet, keyed by (token name, context)."""
    found: dict[tuple[str, Context], tuple[str, Color, int]] = {}
    problems: list[str] = []
    for rule in css.parse(css_text):
        custom = [d for d in rule.declarations if d.prop.startswith("--")]
        if not custom:
            continue
        try:
            context = classify(rule)
        except ValueError as error:
            problems.append(f"line {rule.line}: {error}")
            continue
        if context is None:
            problems.append(
                f"line {rule.line}: custom properties declared outside :root, in {rule.selector!r}"
            )
            continue
        for declaration in custom:
            name = declaration.prop[2:]
            try:
                color = parse_color(declaration.value)
            except ValueError:
                problems.append(
                    f"line {declaration.line}: --{name} is {declaration.value!r}, which is not a "
                    "colour. This exporter only knows colour tokens."
                )
                continue
            key = (name, context)
            if key in found:
                problems.append(
                    f"line {declaration.line}: --{name} is declared twice for the same theme and "
                    f"accent (first on line {found[key][2]})"
                )
                continue
            found[key] = (declaration.value, color, declaration.line)
    return found, problems


def build(css_text: str, config: dict[str, Any]) -> dict[str, Any]:
    """Build the tokens document from stylesheet text. Raises TokenError listing every problem."""
    found, problems = read_declarations(css_text)

    def lookup(name: str, theme: str, accent: str | None, via: str):
        return found.get((name, Context(theme, accent, via)))

    def night(name: str, accent: str | None) -> tuple[str, Color] | None:
        """The night value, after checking that the attribute copy and the media copy agree."""
        label = f"--{name}" + (f" (accent {accent})" if accent else "")
        by_attribute = lookup(name, "night", accent, "attribute")
        by_media = lookup(name, "night", accent, "media")
        if by_attribute is None or by_media is None:
            missing = '[data-theme="night"]' if by_attribute is None else "@media (prefers-color-scheme: dark)"
            problems.append(f"{label} has no night value under {missing}")
            return None
        if not _same(by_attribute[1], by_media[1]):
            problems.append(
                f"night drift: {label} is {by_attribute[0]} under [data-theme=\"night\"] "
                f"(line {by_attribute[2]}) but {by_media[0]} under @media (prefers-color-scheme: dark) "
                f"(line {by_media[2]})"
            )
            return None
        return by_attribute[0], by_attribute[1]

    def themed(name: str, accent: str | None) -> dict[str, Any] | None:
        day = lookup(name, "day", accent, "base")
        if day is None:
            if accent:
                problems.append(f"--{name} (accent {accent}) has a night value but no day value")
            else:
                problems.append(f"--{name} is not declared in the plain :root rule, so it has no day value")
            return None
        dark = night(name, accent)
        if dark is None:
            return None
        return {"day": _color_entry(day[0], day[1]), "night": _color_entry(*dark)}

    names: list[str] = []
    accents: list[str] = []
    for name, context in found:  # dicts keep insertion order, so this is source order
        if name not in names:
            names.append(name)
        if context.accent and context.accent not in accents:
            accents.append(context.accent)

    described = config.get("tokens", {})
    for name in names:
        if name not in described:
            problems.append(f"--{name} is in the CSS but has no role in design.toml")
    for name in described:
        if name not in names:
            problems.append(f"design.toml describes --{name}, which is not in the CSS")
        elif described[name].get("role") not in ROLES:
            problems.append(f"design.toml: --{name} has role {described[name].get('role')!r}; use one of {', '.join(ROLES)}")

    default_accent = config.get("default_accent", "")
    if default_accent in accents:
        problems.append(f"default_accent {default_accent!r} also has a [data-accent] rule in the CSS")

    overridden = {(name, context.accent) for name, context in found if context.accent}

    tokens: list[dict[str, Any]] = []
    for name in names:
        values = themed(name, None)
        overrides: dict[str, Any] = {}
        for accent in accents:
            if (name, accent) in overridden:
                entry = themed(name, accent)
                if entry is not None:
                    overrides[accent] = entry
        meta = described.get(name, {})
        token: dict[str, Any] = {
            "name": name,
            "cssVariable": f"--{name}",
            "role": meta.get("role"),
            "description": meta.get("description", ""),
            "values": values,
        }
        if overrides:
            token["accents"] = overrides
        tokens.append(token)

    if problems:
        raise TokenError(problems)

    return {
        "$schema": "./tokens.schema.json",
        "version": 1,
        "source": config["source"],
        "themes": list(THEMES),
        "defaultAccent": default_accent,
        "accents": [default_accent, *accents],
        "tokens": tokens,
    }


def render(document: dict[str, Any]) -> str:
    """The exact text of tokens.json. Stable output is what makes the drift check possible."""
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def render_ts(document: dict[str, Any]) -> str:
    """A TypeScript module with the token values the app needs as data.

    CSS can use var(--myelin), but two places in the app need actual values: the accent picker shows
    every accent at once, and the canvas needs a fallback before the stylesheet has loaded. Generating
    this file from the contract means those values cannot drift from the tokens.
    """
    accent_token = next(token for token in document["tokens"] if "accents" in token)
    lines = [
        "// Generated from styles.css by `python -m myelin_design export`. Do not edit by hand.",
        "// CI fails if this file does not match the stylesheet.",
        "",
        "/** The accent colour for each accent setting, by day and by night. */",
        "export const ACCENT_COLORS = {",
    ]
    for accent in document["accents"]:
        values = accent_token.get("accents", {}).get(accent, accent_token["values"])
        lines.append(f'  {accent}: {{ day: "{values["day"]["hex"]}", night: "{values["night"]["hex"]}" }},')
    lines += ["} as const;", "", "/** Day values of the opaque tokens as [red, green, blue], for canvas code. */", "export const DAY_RGB = {"]
    for token in document["tokens"]:
        day = token["values"]["day"]
        if day["alpha"] == 1:
            rgb = parse_color(day["hex"])
            key = token["name"] if token["name"].isidentifier() else f'"{token["name"]}"'
            lines.append(f"  {key}: [{rgb.r}, {rgb.g}, {rgb.b}],")
    lines += ["} as const satisfies Record<string, readonly [number, number, number]>;", ""]
    return "\n".join(lines)


def validate(document: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Check a tokens document against the JSON Schema. Returns the problems; empty means valid."""
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '(root)'}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda e: list(map(str, e.absolute_path)))
    ]


def export(project: Project) -> dict[str, Any]:
    """Build the tokens document for a project and validate it against the schema."""
    document = build(read_text(project.source_css), project.config)
    schema = json.loads(read_text(project.tokens_schema))
    problems = validate(document, schema)
    if problems:
        raise TokenError([f"schema: {problem}" for problem in problems])
    return document


def load(project: Project) -> dict[str, Any]:
    """Read the committed tokens.json."""
    return json.loads(read_text(project.tokens_json))


def resolve(document: dict[str, Any], theme: str, accent: str | None = None) -> dict[str, Color]:
    """Every token's colour for one theme and accent, keyed by token name."""
    if theme not in document["themes"]:
        raise ValueError(f"unknown theme {theme!r}; use one of {', '.join(document['themes'])}")
    accent = accent or document["defaultAccent"]
    if accent not in document["accents"]:
        raise ValueError(f"unknown accent {accent!r}; use one of {', '.join(document['accents'])}")
    colors: dict[str, Color] = {}
    for token in document["tokens"]:
        entry = token.get("accents", {}).get(accent, token["values"])[theme]
        rgb = parse_color(entry["hex"])
        colors[token["name"]] = Color(rgb.r, rgb.g, rgb.b, entry["alpha"])
    return colors
