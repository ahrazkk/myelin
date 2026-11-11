import pytest

from myelin_design import compliance
from myelin_design.compliance import LITERAL, TOKEN, TOKEN_COPY, UNKNOWN_TOKEN, Palette, scan_css, scan_ts, split_ts

DOCUMENT = {
    "tokens": [
        {"name": "ink", "cssVariable": "--ink", "values": {"day": {"hex": "#1b2142", "alpha": 1.0}, "night": {"hex": "#e4e8f6", "alpha": 1.0}}},
        {
            "name": "brand",
            "cssVariable": "--brand",
            "values": {"day": {"hex": "#2d6bad", "alpha": 1.0}, "night": {"hex": "#57c4e5", "alpha": 1.0}},
            "accents": {"rose": {"day": {"hex": "#b03a6a", "alpha": 1.0}, "night": {"hex": "#f28bb0", "alpha": 1.0}}},
        },
        {"name": "wash", "cssVariable": "--wash", "values": {"day": {"hex": "#2d6bad", "alpha": 0.09}, "night": {"hex": "#57c4e5", "alpha": 0.1}}},
    ]
}
PALETTE = Palette.from_document(DOCUMENT)


def kinds(uses):
    return [(use.kind, use.text) for use in uses]


# ---- CSS ----


def test_css_token_uses_and_literals():
    uses = scan_css(".a { color: var(--ink); border: 1px solid #ABCDEF; background: rgb(0 0 0 / 0.12); }", PALETTE)
    assert kinds(uses) == [(TOKEN, "var(--ink)"), (LITERAL, "#ABCDEF"), (LITERAL, "rgb(0 0 0 / 0.12)")]


def test_css_token_definitions_are_not_uses():
    assert scan_css(":root { --ink: #1b2142; --wash: rgb(45 107 173 / 0.09); }", PALETTE) == []


def test_css_reports_line_numbers():
    uses = scan_css(".a {\n  color: var(--ink);\n\n  fill: #123456;\n}", PALETTE)
    assert [(use.line, use.text) for use in uses] == [(2, "var(--ink)"), (4, "#123456")]


def test_css_a_literal_equal_to_a_token_is_called_a_copy():
    (use,) = scan_css(".a { color: #2D6BAD; }", PALETTE)
    assert use.kind == TOKEN_COPY
    assert use.detail == "same colour as --brand (day)"
    (accent,) = scan_css(".a { color: #b03a6a; }", PALETTE)
    assert accent.detail == "same colour as --brand (rose day)"
    (wash,) = scan_css(".a { background: rgb(45 107 173 / 0.09); }", PALETTE)
    assert wash.detail == "same colour as --wash (day)"


def test_css_unknown_token_is_flagged():
    assert kinds(scan_css(".a { color: var(--inc); }", PALETTE)) == [(UNKNOWN_TOKEN, "var(--inc)")]


def test_css_var_fallback_literal_is_still_a_literal():
    assert kinds(scan_css(".a { color: var(--ink, #000); }", PALETTE)) == [(TOKEN, "var(--ink)"), (LITERAL, "#000")]


def test_css_colour_built_from_tokens_is_not_a_literal():
    uses = scan_css(".a { color: color-mix(in srgb, var(--ink) 50%, var(--brand)); }", PALETTE)
    assert kinds(uses) == [(TOKEN, "var(--ink)"), (TOKEN, "var(--brand)")]


def test_css_named_colours_only_where_a_colour_goes():
    assert kinds(scan_css(".a { color: white; border: 1px solid RED; }", PALETTE)) == [(LITERAL, "white"), (LITERAL, "RED")]
    quiet = ".a { font-family: Tan, serif; transition: color 1s; animation-name: gold; background: none; color: inherit; fill: currentColor; border-color: transparent; }"
    assert scan_css(quiet, PALETTE) == []


def test_css_ignores_urls_strings_and_non_colours():
    quiet = '.a { background: url(#fff.png); content: "#fff red"; margin: 0 auto; grid-area: a; width: calc(100% - 3px); }'
    assert scan_css(quiet, PALETTE) == []
    assert scan_css(".a { color: #12; fill: #12345; }", PALETTE) == []  # not valid hex lengths


def test_css_hsl_and_modern_functions():
    uses = scan_css(".a { color: hsl(210 50% 40%); background: oklch(60% 0.1 200); }", PALETTE)
    assert kinds(uses) == [(LITERAL, "hsl(210 50% 40%)"), (LITERAL, "oklch(60% 0.1 200)")]


# ---- TypeScript ----


def test_split_ts_separates_strings_from_code_and_drops_comments():
    source = 'const a = "#fff"; // "#000"\n/* "#111" */ const b = \'x\';\n'
    code, strings = split_ts(source)
    assert [(s.text, s.line) for s in strings] == [("#fff", 1), ("x", 2)]
    assert len(code) == len(source)
    assert "#" not in code and code.count("\n") == source.count("\n")


def test_split_ts_template_literals_and_nesting():
    _, strings = split_ts("const a = `x ${f(`y ${1}`)} z ${'q'}`;")
    assert sorted(s.text for s in strings) == ["q", "x ${} z ${}", "y ${}"]


def test_split_ts_survives_unclosed_input():
    for source in ['const a = "never closed', "const a = `never closed ${", "/* never closed", "`${`${`${"]:
        split_ts(source)


def test_ts_hex_in_strings_and_jsx_attributes():
    source = 'const C = { day: "#123456" };\nconst x = <rect fill="#abc" />;\n'
    assert kinds(scan_ts(source, PALETTE)) == [(LITERAL, "#123456"), (LITERAL, "#abc")]


def test_ts_ignores_comments_and_code_that_only_looks_like_a_colour():
    source = '// "#123456"\n/* rgb(1, 2, 3) */\nclass A { #abc = 1; }\nconst href = "#top";\nconst n = 0xffffff;\n'
    assert scan_ts(source, PALETTE) == []


def test_ts_rgba_strings_and_templates():
    source = 'ctx.fillStyle = "rgba(232,236,248,0.92)";\nconst g = `rgba(255,226,170,${0.55 + breathe})`;\n'
    assert kinds(scan_ts(source, PALETTE)) == [(LITERAL, "rgba(232,236,248,0.92)"), (LITERAL, "rgba(255,226,170,${})")]


def test_ts_a_colour_computed_from_variables_is_not_a_literal():
    source = "const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;\nconst f = `rgba(${t[0]},${t[1]},${t[2]},0)`;\n"
    assert scan_ts(source, PALETTE) == []


def test_ts_token_references_count_as_token_uses():
    source = 'const a = { color: "var(--ink)" };\nconst b = style.getPropertyValue("--brand");\nconst c = "var(--nope)";\nconst flag = "--verbose";\n'
    uses = scan_ts(source, PALETTE)
    assert kinds(uses) == [(TOKEN, "var(--ink)"), (TOKEN, "--brand"), (UNKNOWN_TOKEN, "var(--nope)")]


def test_ts_rgb_triples_are_flagged_only_when_they_copy_a_token():
    source = "const fallback = [45, 107, 173];\nconst sky = [196, 218, 243];\nconst data = [1, 2, 3];\n"
    (use,) = scan_ts(source, PALETTE)
    assert (use.kind, use.text, use.line) == (TOKEN_COPY, "[45, 107, 173]", 1)
    assert use.detail == "same colour as --brand (day)"  # the opaque token, not the wash with the same RGB
    assert compliance.count_other_triples(source, PALETTE) == 2


def test_ts_named_colours_only_in_colour_slots():
    source = 'ctx.fillStyle = "white";\nconst s = { backgroundColor: "red" };\ng.addColorStop(0, "black");\nconst scene = "snow";\nconst label = "Red";\ncase "tan": break;\n'
    assert kinds(scan_ts(source, PALETTE)) == [(LITERAL, "white"), (LITERAL, "red"), (LITERAL, "black")]


# ---- Shared ----


def test_scan_dispatches_on_language():
    assert kinds(compliance.scan(".a{color:#123}", "css", PALETTE)) == [(LITERAL, "#123")]
    assert kinds(compliance.scan('const a = "#123";', ".tsx", PALETTE)) == [(LITERAL, "#123")]
    with pytest.raises(ValueError):
        compliance.scan("x", "python", PALETTE)


def test_percentage():
    assert compliance.percentage(162, 27) == pytest.approx(85.714, abs=0.001)
    assert compliance.percentage(5, 0) == 100
    assert compliance.percentage(0, 0) is None  # no colours at all is not 0% and not 100%


def test_hostile_input_finishes_quickly():
    for text in ["(" * 100_000, "rgb(" * 50_000, "var(" * 50_000, "#" * 100_000, "`${" * 50_000, '"' * 100_001]:
        scan_css(".a { color: " + text + " }", PALETTE)
        scan_ts(text, PALETTE)
