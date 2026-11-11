import json

import pytest

from myelin_design import css, tokens
from myelin_design.__main__ import main
from myelin_design.project import Project, read_text, write_text

CONFIG = {
    "source": "frontend/src/styles.css",
    "default_accent": "blue",
    "tokens": {
        "page": {"role": "background", "description": "Page background."},
        "brand": {"role": "accent", "description": "Brand colour."},
        "brand-wash": {"role": "wash", "description": "Translucent brand fill."},
    },
}

# A small stylesheet with the same six kinds of rule as Myelin's.
CSS = """
:root {
  --page: #ffffff;
  --brand: #0000ff;
  --brand-wash: rgb(0 0 255 / 0.1);
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="day"]) {
    --page: #000000;
    --brand: #8888ff;
    --brand-wash: rgb(136 136 255 / 0.1);
  }
}
:root[data-theme="night"] {
  --page: #000000;
  --brand: #8888ff;
  --brand-wash: rgb(136 136 255 / 0.1);
}
:root[data-accent="green"] { --brand: #008000; }
:root[data-theme="night"][data-accent="green"] { --brand: #88ff88; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="day"])[data-accent="green"] { --brand: #88ff88; }
}
body { background: var(--page); }
"""


def problems_for(stylesheet: str, config: dict = CONFIG) -> list[str]:
    with pytest.raises(tokens.TokenError) as raised:
        tokens.build(stylesheet, config)
    return raised.value.problems


def classify(selector: str, *at_rules: str) -> tokens.Context | None:
    return tokens.classify(css.Rule(selector, tuple(at_rules), (), 1))


def test_builds_tokens_with_a_value_per_theme():
    document = tokens.build(CSS, CONFIG)
    assert [token["name"] for token in document["tokens"]] == ["page", "brand", "brand-wash"]
    page = document["tokens"][0]
    assert page["cssVariable"] == "--page"
    assert page["role"] == "background"
    assert page["values"]["day"] == {"css": "#ffffff", "hex": "#ffffff", "alpha": 1.0}
    assert page["values"]["night"]["hex"] == "#000000"
    assert "accents" not in page  # no accent overrides it


def test_translucent_values_keep_their_alpha():
    wash = tokens.build(CSS, CONFIG)["tokens"][2]
    assert wash["values"]["day"] == {"css": "rgb(0 0 255 / 0.1)", "hex": "#0000ff", "alpha": 0.1}


def test_accent_overrides_are_recorded_per_theme():
    document = tokens.build(CSS, CONFIG)
    assert document["accents"] == ["blue", "green"]  # the default first
    brand = document["tokens"][1]
    assert brand["accents"]["green"]["day"]["hex"] == "#008000"
    assert brand["accents"]["green"]["night"]["hex"] == "#88ff88"


def test_classify_tells_the_six_kinds_of_rule_apart():
    dark = "@media (prefers-color-scheme: dark)"
    assert classify(":root") == tokens.Context("day", None, "base")
    assert classify(':root[data-theme="night"]') == tokens.Context("night", None, "attribute")
    assert classify(':root:not([data-theme="day"])', dark) == tokens.Context("night", None, "media")
    assert classify(':root[data-accent="green"]') == tokens.Context("day", "green", "base")
    assert classify(':root[data-theme="night"][data-accent="green"]') == tokens.Context("night", "green", "attribute")
    assert classify(':root:not([data-theme="day"])[data-accent="green"]', dark) == tokens.Context("night", "green", "media")
    assert classify(":root[data-theme='night']") == tokens.Context("night", None, "attribute")  # either quote
    assert classify(".card") is None
    assert classify(':root[data-text="large"] .wall') is None


def test_classify_refuses_theme_rules_it_does_not_understand():
    for selector, at_rules in [
        (':root[data-theme="sepia"]', ()),
        (':root:not([data-theme="day"])', ()),  # only means night inside the dark media query
        (":root", ("@media (prefers-color-scheme: dark)",)),
        (":root", ("@media (min-width: 900px)",)),
        (":root.high-contrast", ()),
    ]:
        with pytest.raises(ValueError):
            classify(selector, *at_rules)


def test_night_drift_between_the_attribute_and_the_media_query_fails():
    drifted = CSS.replace(
        ':root[data-theme="night"] {\n  --page: #000000;', ':root[data-theme="night"] {\n  --page: #000001;'
    )
    assert drifted != CSS
    problems = problems_for(drifted)
    assert len(problems) == 1
    assert "night drift" in problems[0] and "--page" in problems[0]


def test_night_drift_in_an_accent_fails():
    drifted = CSS.replace(
        ':root:not([data-theme="day"])[data-accent="green"] { --brand: #88ff88; }',
        ':root:not([data-theme="day"])[data-accent="green"] { --brand: #88ff89; }',
    )
    assert drifted != CSS
    assert any("night drift" in p and "accent green" in p for p in problems_for(drifted))


def test_the_same_colour_written_differently_is_not_drift():
    restyled = CSS.replace(':root[data-theme="night"] {\n  --page: #000000;', ':root[data-theme="night"] {\n  --page: #000;')
    assert restyled != CSS
    tokens.build(restyled, CONFIG)


def test_a_night_copy_missing_from_one_place_fails():
    without_media = CSS.replace("    --brand-wash: rgb(136 136 255 / 0.1);\n  }\n}", "  }\n}")
    assert without_media != CSS
    assert any("--brand-wash has no night value under @media" in p for p in problems_for(without_media))


def test_every_token_needs_a_role_and_every_role_needs_a_token():
    assert any("--extra is in the CSS but has no role" in p for p in problems_for(CSS.replace("--page: #ffffff;", "--page: #ffffff; --extra: #111111;")))
    stale = {**CONFIG, "tokens": {**CONFIG["tokens"], "gone": {"role": "text", "description": "Removed."}}}
    assert any("--gone, which is not in the CSS" in p for p in problems_for(CSS, stale))
    wrong = {**CONFIG, "tokens": {**CONFIG["tokens"], "page": {"role": "surface", "description": "x"}}}
    assert any("role 'surface'" in p for p in problems_for(CSS, wrong))


def test_tokens_must_be_colours_and_live_on_root():
    assert any("not a colour" in p for p in problems_for(CSS.replace("--brand: #0000ff;", "--brand: 4px;")))
    assert any("outside :root" in p for p in problems_for(CSS + "\n.card { --page: #eeeeee; }"))


def test_all_problems_are_reported_together():
    broken = CSS.replace("--brand: #0000ff;", "--brand: 4px;") + "\n.card { --page: #eeeeee; }"
    assert len(problems_for(broken)) >= 2


def test_resolve_applies_the_accent_over_the_defaults():
    document = tokens.build(CSS, CONFIG)
    assert tokens.resolve(document, "day")["brand"].hex == "#0000ff"
    assert tokens.resolve(document, "day", "green")["brand"].hex == "#008000"
    assert tokens.resolve(document, "night", "green")["brand"].hex == "#88ff88"
    assert tokens.resolve(document, "night", "green")["page"].hex == "#000000"  # not overridden
    assert tokens.resolve(document, "day")["brand-wash"].a == 0.1
    with pytest.raises(ValueError):
        tokens.resolve(document, "dusk")
    with pytest.raises(ValueError):
        tokens.resolve(document, "day", "purple")


# ---- The real repo ----


@pytest.fixture(scope="module")
def project() -> Project:
    return Project.default()


def test_the_real_stylesheet_exports_and_matches_its_schema(project):
    document = tokens.export(project)  # raises on drift or a schema violation
    assert len(document["tokens"]) == 10
    assert document["accents"] == ["myelin", "emerald", "amber", "rose"]
    overridden = [token["name"] for token in document["tokens"] if "accents" in token]
    assert overridden == ["myelin", "myelin-wash"]


def test_the_schema_rejects_a_broken_document(project):
    schema = json.loads(read_text(project.tokens_schema))
    document = tokens.export(project)
    assert tokens.validate(document, schema) == []

    document["tokens"][0]["values"]["day"]["hex"] = "red"
    del document["tokens"][1]["values"]["night"]
    document["tokens"][2]["role"] = "surface"
    problems = tokens.validate(document, schema)
    assert len(problems) == 3


def test_the_committed_tokens_file_is_up_to_date(project):
    """The drift gate, as a test: tokens.json must be exactly what the CSS produces today."""
    assert read_text(project.tokens_json) == tokens.render(tokens.export(project))


# ---- The command line, on a copy of the repo ----


@pytest.fixture
def copy(tmp_path, project) -> Project:
    clone = Project(tmp_path)
    write_text(clone.design_dir / "design.toml", read_text(project.design_dir / "design.toml"))
    write_text(clone.tokens_schema, read_text(project.tokens_schema))
    write_text(clone.source_css, read_text(project.source_css))
    return clone


def test_export_then_check_passes(copy, capsys):
    assert main(["--root", str(copy.root), "export"]) == 0
    assert main(["--root", str(copy.root), "export", "--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_check_fails_when_the_css_changes_after_the_export(copy, capsys):
    assert main(["--root", str(copy.root), "export"]) == 0
    before = read_text(copy.tokens_json)
    # Change a day value only, so the two night copies still agree.
    write_text(copy.source_css, read_text(copy.source_css).replace("--ink: #1b2142;", "--ink: #1b2143;"))

    assert main(["--root", str(copy.root), "export", "--check"]) == 1
    assert "Token drift" in capsys.readouterr().err
    assert read_text(copy.tokens_json) == before  # --check never writes


def test_check_fails_when_tokens_json_is_missing(copy):
    assert main(["--root", str(copy.root), "export", "--check"]) == 1


def test_check_ignores_windows_line_endings(copy):
    assert main(["--root", str(copy.root), "export"]) == 0
    copy.tokens_json.write_bytes(copy.tokens_json.read_bytes().replace(b"\n", b"\r\n"))
    assert main(["--root", str(copy.root), "export", "--check"]) == 0


def test_export_reports_night_drift_and_writes_nothing(copy, capsys):
    stylesheet = read_text(copy.source_css)
    # The first --slide: #0e1530 is the media-query copy; the attribute copy stays as it was.
    write_text(copy.source_css, stylesheet.replace("--slide: #0e1530;", "--slide: #0e1531;", 1))

    assert main(["--root", str(copy.root), "export"]) == 1
    assert "night drift: --slide" in capsys.readouterr().err
    assert not copy.tokens_json.exists()
