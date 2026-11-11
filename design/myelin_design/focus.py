"""Focus states: a keyboard user must always be able to see where they are (WCAG 2.4.7).

Two checks:

1. No rule may remove the focus outline (outline: none, outline: 0) unless the same rule puts
   something visible in its place (a box-shadow, a border or a background).
2. The stylesheet must have a global :focus-visible rule that draws a visible outline. Myelin
   relies on that one rule for every control, so losing it would silently break keyboard use.

This is a check on the source text. It cannot prove a control is reachable by keyboard; that is
what a browser test is for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import css
from .compliance import split_ts

OUTLINE_REMOVED = "outline-removed"
NO_GLOBAL_FOCUS = "no-global-focus-rule"

_ZERO = re.compile(r"^0(?:\.0+)?[a-z]*$")
_REPLACEMENTS = ("box-shadow", "border", "border-color", "background", "background-color")
_NOTHING = ("none", "0", "0px", "transparent", "initial", "unset", "inherit")
# In TSX code: outline: 0, outlineWidth: 0
_INLINE_ZERO = re.compile(r"\boutline(?:Width)?\s*:\s*0(?![\d.])")
# Just before a string in TSX code: outline: "none", outlineStyle: "none"
_INLINE_SLOT = re.compile(r"\boutline(?:Style|Width)?\s*:\s*$")
# CSS written inside a template literal
_CSS_IN_STRING = re.compile(r"\boutline(?:-style|-width)?\s*:\s*(?:none|0)(?![\w.])", re.IGNORECASE)


@dataclass(frozen=True)
class FocusFinding:
    kind: str
    line: int
    selector: str
    text: str
    message: str


def _outline_state(rule: css.Rule) -> tuple[bool | None, css.Declaration | None]:
    """Whether a rule leaves the outline visible (True), removed (False) or untouched (None).

    Declarations are applied in order, because a later one overrides an earlier one. Also returns
    the declaration that removed the outline, when one did.
    """
    visible: bool | None = None
    culprit: css.Declaration | None = None
    for declaration in rule.declarations:
        value = declaration.value.lower().replace("!important", "").strip()
        parts = value.split()
        if declaration.prop == "outline":
            removed = "none" in parts or any(_ZERO.match(part) for part in parts)
        elif declaration.prop == "outline-style":
            removed = value == "none"
        elif declaration.prop == "outline-width":
            removed = bool(_ZERO.match(value))
        else:
            continue
        if removed:
            visible, culprit = False, declaration
        elif declaration.prop != "outline-width" or visible is None:
            # A new width does not bring back an outline whose style was set to none.
            visible = True if declaration.prop != "outline-width" else visible
    return visible, culprit


def _has_replacement(rule: css.Rule) -> bool:
    """True when the rule sets a box-shadow, border or background to something that can be seen."""
    for prop in _REPLACEMENTS:
        value = (rule.get(prop) or "").lower().replace("!important", "").strip()
        if value and value not in _NOTHING:
            return True
    return False


def is_global_focus_rule(rule: css.Rule) -> bool:
    """A :focus-visible rule that applies to everything and is not inside a media query."""
    selectors = [part.strip() for part in rule.selector.split(",")]
    return not rule.at_rules and any(s in (":focus-visible", "*:focus-visible") for s in selectors)


def scan_css(text: str) -> list[FocusFinding]:
    """Rules that remove the focus outline without replacing it."""
    findings: list[FocusFinding] = []
    for rule in css.parse(text):
        visible, culprit = _outline_state(rule)
        if visible is not False or culprit is None or _has_replacement(rule):
            continue
        findings.append(
            FocusFinding(
                OUTLINE_REMOVED,
                culprit.line,
                rule.selector,
                f"{culprit.prop}: {culprit.value}",
                "removes the focus outline and puts no box-shadow, border or background in its place",
            )
        )
    return findings


def global_focus_rules(text: str) -> list[css.Rule]:
    """The global :focus-visible rules in a stylesheet that draw a visible outline."""
    return [rule for rule in css.parse(text) if is_global_focus_rule(rule) and _outline_state(rule)[0] is True]


def scan_ts(source: str) -> list[FocusFinding]:
    """Inline styles in TSX that remove the outline. A stylesheet cannot override an inline style."""
    code, strings = split_ts(source)
    findings: list[FocusFinding] = []

    def add(line: int, text: str) -> None:
        findings.append(
            FocusFinding(OUTLINE_REMOVED, line, "(inline style)", " ".join(text.split()), "removes the focus outline in an inline style")
        )

    for match in _INLINE_ZERO.finditer(code):
        add(source.count("\n", 0, match.start()) + 1, match.group())
    for string in strings:
        before = code[max(0, string.start - 40) : string.start]
        slot = _INLINE_SLOT.search(before)
        if slot and string.text.strip().lower() in ("none", "0", "0px"):
            add(string.line, f'{slot.group()}"{string.text}"')
        for match in _CSS_IN_STRING.finditer(string.text):
            add(string.line + string.text.count("\n", 0, match.start()), match.group())

    findings.sort(key=lambda finding: finding.line)
    return findings


def scan(text: str, language: str) -> list[FocusFinding]:
    """Scan a snippet. Language is 'css', 'ts' or 'tsx'."""
    language = language.lower().lstrip(".")
    if language == "css":
        return scan_css(text)
    if language in ("ts", "tsx", "js", "jsx"):
        return scan_ts(text)
    raise ValueError(f"unsupported language {language!r}; use css, ts or tsx")
