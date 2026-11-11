import pytest

from myelin_design import api
from myelin_design.project import Project

PROJECT = Project.default()


# ---- get_design_tokens ----


def test_tokens_unfiltered_has_every_theme_and_accent():
    result = api.get_design_tokens(PROJECT)
    assert result["filter"] == {"theme": None, "accent": None}
    assert result["themes"] == ["day", "night"]
    assert result["accents"] == ["myelin", "emerald", "amber", "rose"]
    by_name = {token["name"]: token for token in result["tokens"]}
    assert len(by_name) == 10
    assert by_name["ink"]["values"]["day"]["hex"] == "#1b2142"
    assert by_name["ink"]["cssVariable"] == "--ink"
    assert set(by_name["myelin"]["accents"]) == {"emerald", "amber", "rose"}
    assert "accents" not in by_name["ink"]


def test_tokens_filtered_by_theme_keeps_only_that_theme():
    result = api.get_design_tokens(PROJECT, theme="night")
    for token in result["tokens"]:
        assert list(token["values"]) == ["night"]
        for values in token.get("accents", {}).values():
            assert list(values) == ["night"]


def test_tokens_filtered_by_accent_resolves_the_accent():
    result = api.get_design_tokens(PROJECT, accent="emerald")
    by_name = {token["name"]: token for token in result["tokens"]}
    assert by_name["myelin"]["values"]["day"]["hex"] == "#1f7a5a"
    assert by_name["myelin"]["values"]["night"]["hex"] == "#4fd1a1"
    assert by_name["ink"]["values"]["day"]["hex"] == "#1b2142"  # not overridden by the accent
    assert all("accents" not in token for token in result["tokens"])


def test_tokens_filtered_by_both():
    result = api.get_design_tokens(PROJECT, theme="day", accent="rose")
    myelin = next(token for token in result["tokens"] if token["name"] == "myelin")
    assert myelin["values"] == {"day": {"css": "#b03a6a", "hex": "#b03a6a", "alpha": 1.0}}


def test_tokens_rejects_unknown_filters():
    with pytest.raises(ValueError, match="use one of: day, night"):
        api.get_design_tokens(PROJECT, theme="dusk")
    with pytest.raises(ValueError, match="unknown accent"):
        api.get_design_tokens(PROJECT, accent="purple")


# ---- check_contrast ----


def test_contrast_of_two_plain_colours_is_one_measurement():
    result = api.check_contrast(PROJECT, "#767676", "white")
    (measurement,) = result["measurements"]
    assert measurement["theme"] is None and measurement["accent"] is None
    assert measurement["ratio"] == 4.54
    assert result["passes_everywhere"] == {"aa_text": True, "aa_large_text": True, "aa_non_text": True}
    assert result["notes"] == []


def test_contrast_reports_each_threshold_separately():
    result = api.check_contrast(PROJECT, "#777777", "#ffffff")
    assert result["lowest_ratio"] == 4.47
    assert result["passes_everywhere"] == {"aa_text": False, "aa_large_text": True, "aa_non_text": True}


def test_contrast_accepts_token_names_in_three_spellings():
    plain = api.check_contrast(PROJECT, "ink", "slide")
    assert [m["ratio"] for m in plain["measurements"]] == [13.6, 14.69]
    assert [m["theme"] for m in plain["measurements"]] == ["day", "night"]
    for spelling in ("--ink", "var(--ink)", " var( --ink ) ".replace("( ", "(").replace(" )", ")")):
        assert api.check_contrast(PROJECT, spelling, "var(--slide)")["measurements"] == plain["measurements"]


def test_contrast_of_an_accent_token_covers_every_accent():
    result = api.check_contrast(PROJECT, "myelin", "slide")
    assert len(result["measurements"]) == 8  # two themes, four accents
    assert {m["accent"] for m in result["measurements"]} == {"myelin", "emerald", "amber", "rose"}
    assert result["lowest_ratio"] == 4.57  # emerald, day
    assert result["passes_everywhere"]["aa_text"] is True


def test_contrast_can_be_narrowed_to_one_theme_and_accent():
    result = api.check_contrast(PROJECT, "myelin", "slide", theme="day", accent="emerald")
    (measurement,) = result["measurements"]
    assert (measurement["theme"], measurement["accent"], measurement["foreground"]) == ("day", "emerald", "#1f7a5a")


def test_contrast_composites_a_translucent_background_over_the_page():
    result = api.check_contrast(PROJECT, "muted", "cresyl-wash", theme="day")
    (measurement,) = result["measurements"]
    assert measurement["background"] == "#e2ddec"  # 10% cresyl over --slide
    assert measurement["ratio"] == 4.35
    assert measurement["aa_text"] is False
    assert result["notes"] == ["The background is translucent, so it was composited over --slide first."]


def test_contrast_composites_a_translucent_literal_in_each_theme():
    result = api.check_contrast(PROJECT, "#000000", "rgb(0 0 0 / 0.5)")
    assert [m["theme"] for m in result["measurements"]] == ["day", "night"]
    assert result["measurements"][0]["background"] == "#77787b"


def test_contrast_composites_a_translucent_foreground():
    result = api.check_contrast(PROJECT, "rgb(0 0 0 / 0.5)", "#ffffff")
    (measurement,) = result["measurements"]
    assert measurement["foreground"] == "#808080"
    assert "foreground is translucent" in result["notes"][0]


def test_contrast_rejects_what_it_cannot_read():
    with pytest.raises(ValueError, match="neither a design token nor a CSS colour"):
        api.check_contrast(PROJECT, "inc", "slide")
    with pytest.raises(ValueError, match="background"):
        api.check_contrast(PROJECT, "ink", "linear-gradient(red, blue)")
    with pytest.raises(ValueError, match="unknown theme"):
        api.check_contrast(PROJECT, "ink", "slide", theme="dusk")


# ---- lint_snippet ----


def test_clean_snippet_passes():
    result = api.lint_snippet(PROJECT, ".card { color: var(--ink); border: 1px solid var(--hair); }", "css")
    assert result == {
        "language": "css",
        "ok": True,
        "token_compliance": {"token_uses": 2, "hard_coded": 0, "percent": 100.0},
        "contrast_pairs": {"measured": 0, "failing": 0},
        "findings": [],
    }


def test_snippet_with_no_colours_has_no_percentage():
    result = api.lint_snippet(PROJECT, "export const A = () => <p>hi</p>;", "tsx")
    assert result["ok"] is True
    assert result["token_compliance"]["percent"] is None


def test_snippet_findings_name_the_token_to_use():
    result = api.lint_snippet(PROJECT, ".a { color: #2d6bad; }\n.b { fill: #123456; }\n.c { color: var(--inc); }", "css")
    assert result["ok"] is False
    copy, literal, unknown = result["findings"]
    assert (copy["rule"], copy["kind"], copy["line"]) == ("token-compliance", "token-copy", 1)
    assert copy["suggestion"].startswith("Use var(--myelin) instead")
    assert (literal["kind"], literal["line"], literal["text"]) == ("literal", 2, "#123456")
    assert (unknown["kind"], unknown["line"]) == ("unknown-token", 3)
    assert "--ink" in unknown["suggestion"]
    assert result["token_compliance"] == {"token_uses": 0, "hard_coded": 2, "percent": 0.0}


def test_snippet_focus_findings_in_css_and_tsx():
    css_result = api.lint_snippet(PROJECT, "button:focus { outline: none; }", "css")
    assert [f["rule"] for f in css_result["findings"]] == ["focus"]
    tsx_result = api.lint_snippet(PROJECT, 'const B = () => <button style={{ outline: "none", color: "#fff" }} />;', "tsx")
    assert sorted(f["rule"] for f in tsx_result["findings"]) == ["focus", "token-compliance"]


def test_snippet_contrast_for_a_rule_with_colour_and_background():
    failing = api.lint_snippet(PROJECT, ".tag { color: var(--muted); background: var(--cresyl-wash); }", "css")
    (finding,) = failing["findings"]
    assert (finding["rule"], finding["kind"]) == ("contrast", "low-contrast-text")
    assert "4.35:1 in day" in finding["message"]

    assert failing["contrast_pairs"] == {"measured": 1, "failing": 1}

    passing = api.lint_snippet(PROJECT, ".tag { color: var(--ink); background: var(--cresyl-wash); }", "css")
    assert passing["ok"] is True
    assert passing["contrast_pairs"] == {"measured": 1, "failing": 0}
    # Nothing to measure: no finding, no crash.
    for rule in (".x { color: inherit; background: var(--slide); }", ".x { color: var(--ink); background: url(a.png); }"):
        assert api.lint_snippet(PROJECT, rule, "css")["ok"] is True


def test_snippet_language_and_size_are_checked():
    assert api.lint_snippet(PROJECT, "", ".TSX")["language"] == "tsx"
    with pytest.raises(ValueError, match="unsupported language"):
        api.lint_snippet(PROJECT, "print('hi')", "python")
    with pytest.raises(ValueError, match="limit"):
        api.lint_snippet(PROJECT, "a" * (api.MAX_SNIPPET_CHARS + 1), "css")


def test_snippet_is_scanned_not_executed(tmp_path):
    """Code that would do damage if it ran is just text to the scanner."""
    marker = tmp_path / "ran"
    hostile = f'import {{ writeFileSync }} from "fs";\nwriteFileSync({str(marker)!r}, "x");\nprocess.exit(1);\n`${{require("child_process").execSync("echo hi > {marker.as_posix()}")}}`;\n'
    result = api.lint_snippet(PROJECT, hostile, "ts")
    assert result["ok"] is True
    assert not marker.exists()


def test_snippet_survives_garbage():
    for garbage in ["", "\x00\x01\x02", "}{" * 1000, "`" * 999, "/*" * 500, '"' * 501, "🙂" * 100, "(" * 10_000]:
        for language in api.LANGUAGES:
            assert isinstance(api.lint_snippet(PROJECT, garbage, language)["ok"], bool)


# ---- get_guidelines ----


def test_guidelines_return_the_written_rules_and_the_measured_pairs():
    result = api.get_guidelines(PROJECT)
    assert result["format"] == "markdown"
    assert result["text"].startswith("# Myelin UI guidelines")
    assert ":focus-visible" in result["text"]
    pairs = {(p["foreground"], p["surface"], p["kind"], p["opacity"]): p for p in result["contrast_pairs"]}
    body = pairs[("ink", "page", "text", 1.0)]
    assert (body["lowest_ratio"], body["needs"], body["result"], body["layers"]) == (13.6, 4.5, "pass", ["slide"])
    assert pairs[("axon-ahead", "page", "decorative", 1.0)]["result"] == "exempt"
    assert {p["result"] for p in result["contrast_pairs"]} <= {"pass", "fail", "exempt"}
