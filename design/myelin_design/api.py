"""The four things the MCP server offers, as plain functions.

The server (server.py) is a thin wrapper around these, and the contract test checks that calling a
tool over MCP gives exactly what the function gives. Keeping the logic here means it can be tested,
and used from the command line, without starting a server.

The return types are TypedDicts. The MCP SDK turns each one into a JSON Schema and publishes it as
the tool's output schema, so an agent knows the shape of every answer before it calls.

All four are read-only. lint_snippet treats its input as text to scan: nothing is executed,
imported or written to disk.
"""

from __future__ import annotations

from typing import Any

from typing_extensions import NotRequired, TypedDict

from . import compliance, contrast, css, focus, lint, tokens
from .color import AA_LARGE_TEXT, AA_NON_TEXT, AA_TEXT, Color, composite, contrast_ratio, parse_color, shown
from .project import Project, read_text

MAX_SNIPPET_CHARS = 200_000
LANGUAGES = ("css", "ts", "tsx")


# ---- Shapes ----


class ColorValue(TypedDict):
    css: str
    hex: str
    alpha: float


class ThemedValues(TypedDict, total=False):
    day: ColorValue
    night: ColorValue


class Token(TypedDict):
    name: str
    cssVariable: str
    role: str
    description: str
    values: ThemedValues
    accents: NotRequired[dict[str, ThemedValues]]


class TokenFilter(TypedDict):
    theme: str | None
    accent: str | None


class DesignTokens(TypedDict):
    source: str
    themes: list[str]
    accents: list[str]
    defaultAccent: str
    filter: TokenFilter
    usage: str
    tokens: list[Token]


class ContrastMeasurement(TypedDict):
    theme: str | None
    accent: str | None
    foreground: str
    background: str
    ratio: float
    aa_text: bool
    aa_large_text: bool
    aa_non_text: bool


class ContrastVerdict(TypedDict):
    aa_text: bool
    aa_large_text: bool
    aa_non_text: bool


class ContrastCheck(TypedDict):
    foreground: str
    background: str
    thresholds: dict[str, float]
    lowest_ratio: float
    passes_everywhere: ContrastVerdict
    measurements: list[ContrastMeasurement]
    notes: list[str]


class SnippetFinding(TypedDict):
    rule: str  # "token-compliance", "focus" or "contrast"
    kind: str
    line: int
    text: str
    message: str
    suggestion: str


class SnippetCompliance(TypedDict):
    token_uses: int
    hard_coded: int
    percent: float | None


class SnippetPairs(TypedDict):
    measured: int  # CSS rules that set both a text colour and a background that could be measured
    failing: int  # how many of those are below 4.5:1 in some theme or accent


class SnippetLint(TypedDict):
    language: str
    ok: bool
    token_compliance: SnippetCompliance
    contrast_pairs: SnippetPairs
    findings: list[SnippetFinding]


class PairSummary(TypedDict):
    foreground: str
    surface: str
    layers: list[str]
    kind: str
    opacity: float
    lowest_ratio: float
    needs: float | None
    result: str  # "pass", "fail" or "exempt"
    where: str


class Guidelines(TypedDict):
    format: str
    text: str
    contrast_pairs: list[PairSummary]


# ---- get_design_tokens ----


def get_design_tokens(project: Project, theme: str | None = None, accent: str | None = None) -> DesignTokens:
    """The design tokens from design/tokens.json, optionally narrowed to one theme or one accent."""
    document = tokens.load(project)
    if theme is not None and theme not in document["themes"]:
        raise ValueError(f"unknown theme {theme!r}; use one of: {', '.join(document['themes'])}")
    if accent is not None and accent not in document["accents"]:
        raise ValueError(f"unknown accent {accent!r}; use one of: {', '.join(document['accents'])}")

    def narrow(values: dict[str, Any]) -> ThemedValues:
        return {name: value for name, value in values.items() if theme in (None, name)}  # type: ignore[return-value]

    result: list[Token] = []
    for token in document["tokens"]:
        entry: Token = {
            "name": token["name"],
            "cssVariable": token["cssVariable"],
            "role": token["role"],
            "description": token["description"],
            "values": narrow(token.get("accents", {}).get(accent, token["values"])),
        }
        if accent is None and "accents" in token:
            entry["accents"] = {name: narrow(values) for name, values in token["accents"].items()}
        result.append(entry)

    return {
        "source": document["source"],
        "themes": document["themes"],
        "accents": document["accents"],
        "defaultAccent": document["defaultAccent"],
        "filter": {"theme": theme, "accent": accent},
        "usage": "In CSS write var(--name), for example color: var(--ink). Never copy a hex value into code: "
        "the value changes with the theme and the accent.",
        "tokens": result,
    }


# ---- check_contrast ----


def _token_name(text: str, names: set[str]) -> str | None:
    """Accept ink, --ink and var(--ink) as the same token."""
    name = text.strip()
    if name.lower().startswith("var(") and name.endswith(")"):
        name = name[4:-1].split(",")[0].strip()
    name = name.removeprefix("--")
    return name if name in names else None


def check_contrast(
    project: Project, foreground: str, background: str, theme: str | None = None, accent: str | None = None
) -> ContrastCheck:
    """The WCAG 2.1 contrast ratio between two colours, each given as a token name or a CSS colour.

    Tokens change with the theme and accent, so a pair that involves a token is measured in each
    one (or only in the theme and accent asked for). Translucent colours are composited first: the
    background over the page background (--slide), then the foreground over that.
    """
    return _measure(tokens.load(project), _page_token(project), foreground, background, theme, accent)


def _page_token(project: Project) -> str:
    """The token for the page background: the bottom layer of the "page" surface in design.toml."""
    return project.config["contrast"]["surfaces"]["page"][0]


def _measure(
    document: dict[str, Any], page: str, foreground: str, background: str, theme: str | None = None, accent: str | None = None
) -> ContrastCheck:
    names = {token["name"] for token in document["tokens"]}
    accent_names = {token["name"] for token in document["tokens"] if "accents" in token}
    if theme is not None and theme not in document["themes"]:
        raise ValueError(f"unknown theme {theme!r}; use one of: {', '.join(document['themes'])}")
    if accent is not None and accent not in document["accents"]:
        raise ValueError(f"unknown accent {accent!r}; use one of: {', '.join(document['accents'])}")

    parsed: dict[str, tuple[str | None, Color | None]] = {}
    for label, text in (("foreground", foreground), ("background", background)):
        token = _token_name(text, names)
        if token is not None:
            parsed[label] = (token, None)
            continue
        try:
            parsed[label] = (None, parse_color(text))
        except ValueError:
            raise ValueError(
                f"{label} {text!r} is neither a design token nor a CSS colour. Tokens: {', '.join(sorted(names))}"
            ) from None

    used_tokens = {token for token, _ in parsed.values() if token}
    literal_background = parsed["background"][1]
    needs_page = literal_background is not None and not literal_background.opaque
    by_theme = bool(used_tokens) or needs_page or theme is not None
    by_accent = bool(used_tokens & accent_names) or accent is not None

    notes: list[str] = []
    measurements: list[ContrastMeasurement] = []
    for theme_name in ([theme] if theme else document["themes"]) if by_theme else [None]:
        for accent_name in ([accent] if accent else document["accents"]) if by_accent else [None]:
            colors = tokens.resolve(document, theme_name or document["themes"][0], accent_name)
            fg = colors[parsed["foreground"][0]] if parsed["foreground"][0] else parsed["foreground"][1]
            bg = colors[parsed["background"][0]] if parsed["background"][0] else parsed["background"][1]
            assert fg is not None and bg is not None
            if not bg.opaque:
                bg = composite(bg, colors[page])
                note = f"The background is translucent, so it was composited over --{page} first."
                if note not in notes:
                    notes.append(note)
            if not fg.opaque:
                fg = composite(fg, bg)
                note = "The foreground is translucent, so it was composited over the background first."
                if note not in notes:
                    notes.append(note)
            ratio = contrast_ratio(fg, bg)
            measurements.append(
                {
                    "theme": theme_name,
                    "accent": accent_name,
                    "foreground": fg.hex,
                    "background": bg.hex,
                    "ratio": float(shown(ratio)),
                    "aa_text": ratio >= AA_TEXT,
                    "aa_large_text": ratio >= AA_LARGE_TEXT,
                    "aa_non_text": ratio >= AA_NON_TEXT,
                }
            )

    return {
        "foreground": foreground,
        "background": background,
        "thresholds": {"aa_text": AA_TEXT, "aa_large_text": AA_LARGE_TEXT, "aa_non_text": AA_NON_TEXT},
        "lowest_ratio": min(m["ratio"] for m in measurements),
        "passes_everywhere": {
            "aa_text": all(m["aa_text"] for m in measurements),
            "aa_large_text": all(m["aa_large_text"] for m in measurements),
            "aa_non_text": all(m["aa_non_text"] for m in measurements),
        },
        "measurements": measurements,
        "notes": notes,
    }


# ---- lint_snippet ----


def _plain(value: str | None) -> str:
    text = value or ""
    cut = text.lower().find("!important")
    return (text if cut == -1 else text[:cut]).strip()


def _css_pair_findings(document: dict[str, Any], page: str, code: str) -> tuple[list[SnippetFinding], int]:
    """Contrast for every CSS rule that sets both a text colour and a background.

    Returns the findings and how many pairs could be measured, so a caller can report a pass rate.
    """
    findings: list[SnippetFinding] = []
    measured = 0
    for rule in css.parse(code):
        # !important does not change a colour, so it is dropped before measuring.
        color = _plain(rule.get("color"))
        background = _plain(contrast.background_of(rule))
        if not color or not background:
            continue
        try:
            check = _measure(document, page, color, background)
        except ValueError:
            continue  # inherit, a gradient, an unknown token: nothing that can be measured
        measured += 1
        if check["passes_everywhere"]["aa_text"]:
            continue
        worst = min(check["measurements"], key=lambda m: m["ratio"])
        where = ", ".join(part for part in (worst["theme"], worst["accent"]) if part)
        findings.append(
            {
                "rule": "contrast",
                "kind": "low-contrast-text",
                "line": rule.line,
                "text": f"{rule.selector} {{ color: {color}; background: {background} }}",
                "message": f"text contrast is {worst['ratio']:.2f}:1" + (f" in {where}" if where else "") + f"; WCAG 2.1 AA needs {AA_TEXT:g}:1",
                "suggestion": "Use --ink for text on this background, or check a pair with check_contrast before using it.",
            }
        )
    return findings, measured


def lint_snippet(project: Project, code: str, language: str) -> SnippetLint:
    """Check a CSS, TS or TSX snippet against the design system. The code is scanned, never run."""
    language = language.lower().strip().lstrip(".")
    if language not in LANGUAGES:
        raise ValueError(f"unsupported language {language!r}; use one of: {', '.join(LANGUAGES)}")
    if len(code) > MAX_SNIPPET_CHARS:
        raise ValueError(f"snippet is {len(code)} characters; the limit is {MAX_SNIPPET_CHARS}")

    document = tokens.load(project)
    palette = compliance.Palette.from_document(document)
    names = ", ".join(f"--{name}" for name in sorted(palette.names))
    findings: list[SnippetFinding] = []

    uses = compliance.scan(code, language, palette)
    for use in uses:
        if use.kind == compliance.TOKEN:
            continue
        if use.kind == compliance.TOKEN_COPY:
            token = use.detail.removeprefix("same colour as ").split(" (")[0]
            message = f"hard-coded copy of a design token ({use.detail})"
            suggestion = f"Use var({token}) instead, so the colour follows the theme and accent."
        elif use.kind == compliance.UNKNOWN_TOKEN:
            message = "this design token does not exist"
            suggestion = f"Use one of: {names}."
        else:
            message = "hard-coded colour; colours must come from design tokens"
            suggestion = f"Replace it with a token: {names}."
        findings.append(
            {"rule": "token-compliance", "kind": use.kind, "line": use.line, "text": use.text, "message": message, "suggestion": suggestion}
        )

    for finding in focus.scan(code, language):
        findings.append(
            {
                "rule": "focus",
                "kind": finding.kind,
                "line": finding.line,
                "text": finding.text,
                "message": finding.message,
                "suggestion": "Keep the global :focus-visible outline. If a control needs its own focus style, add one; do not remove the outline.",
            }
        )

    measured = 0
    if language == "css":
        pair_findings, measured = _css_pair_findings(document, _page_token(project), code)
        findings += pair_findings

    findings.sort(key=lambda finding: (finding["line"], finding["rule"]))
    token_uses = sum(1 for use in uses if use.kind == compliance.TOKEN)
    hard_coded = sum(1 for use in uses if use.hard_coded)
    percent = compliance.percentage(token_uses, hard_coded)
    return {
        "language": language,
        "ok": not findings,
        "token_compliance": {
            "token_uses": token_uses,
            "hard_coded": hard_coded,
            "percent": None if percent is None else round(percent, 2),
        },
        "contrast_pairs": {"measured": measured, "failing": sum(1 for f in findings if f["rule"] == "contrast")},
        "findings": findings,
    }


# ---- get_guidelines ----


def get_guidelines(project: Project) -> Guidelines:
    """Myelin's UI rules (design/guidelines.md), plus the measured contrast of every declared colour pair."""
    report = lint.run(project)["contrast"]
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for result in report["results"]:
        groups.setdefault((result["foreground"], result["surface"], result["kind"], result["opacity"]), []).append(result)
    layers = {(pair["foreground"], pair["surface"], pair["kind"], pair["opacity"]): pair["layers"] for pair in report["pairs"]}

    pairs: list[PairSummary] = []
    for key, members in groups.items():
        worst = min(members, key=lambda r: r["ratio"])
        if worst["threshold"] is None:
            verdict = "exempt"
        else:
            verdict = "pass" if all(r["status"] == "pass" for r in members) else "fail"
        pairs.append(
            {
                "foreground": key[0],
                "surface": key[1],
                "layers": layers[key],
                "kind": key[2],
                "opacity": key[3],
                "lowest_ratio": worst["ratio"],
                "needs": worst["threshold"],
                "result": verdict,
                "where": worst["where"],
            }
        )
    return {
        "format": "markdown",
        "text": read_text(project.design_dir / "guidelines.md"),
        "contrast_pairs": pairs,
    }
