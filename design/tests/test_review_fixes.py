"""Regression tests for defects found by an independent review of this package."""

import pytest

from myelin_design import api, contrast, css, lint, tokens
from myelin_design.color import Color, parse_color
from myelin_design.contrast import ConfigError, Pair, read_pairs
from myelin_design.project import Project, read_text, write_text
from tests.test_contrast import DOCUMENT, SURFACES, config, pair
from tests.test_lint import DESIGN_TOML, STYLES

PROJECT = Project.default()


# ---- css.py ----


def test_declarations_in_a_group_nested_inside_a_rule_are_kept():
    rules = css.parse(".card { color: red; @media (min-width: 600px) { color: blue; outline: none; } }")
    assert [(rule.selector, rule.at_rules, rule.get("color")) for rule in rules] == [
        (".card", (), "red"),
        (".card", ("@media (min-width: 600px)",), "blue"),
    ]


def test_an_ordinary_media_block_is_not_itself_a_rule():
    rules = css.parse("@media print { .a { color: red; } }")
    assert [rule.selector for rule in rules] == [".a"]


def test_rules_come_back_in_source_order_even_on_one_line():
    rules = css.parse(".a { color: red; .b { color: blue; } } .c { top: 0; }")
    assert [rule.selector for rule in rules] == [".a", ".b", ".c"]


def test_deeply_nested_groups_use_bounded_memory():
    depth = 40_000
    rules = css.parse("@media x{" * depth + ".a{color:red}" + "}" * depth)
    assert len(rules) == 1
    assert len(rules[0].at_rules) == css.MAX_GROUP_DEPTH


# ---- color.py ----


def test_channels_round_half_up_like_css():
    assert parse_color("rgb(30% 30% 30%)") == Color(77, 77, 77)  # 76.5 goes up, not to the even 76
    assert parse_color("hsl(0 0% 30%)") == Color(77, 77, 77)
    assert parse_color("rgb(2.5, 3.4, 4.6)") == Color(3, 3, 5)


@pytest.mark.parametrize("text", ["#+1+2+3", "#１２３", "rgb(nan nan nan)", "rgb(inf 0 0)", "rgb(1_0 0 0)", "hsl(1e999 50% 50%)", "#12 345"])
def test_things_that_only_look_like_colours_are_rejected(text):
    with pytest.raises(ValueError):
        parse_color(text)


# ---- contrast pairs in snippets and stylesheets ----


@pytest.mark.parametrize(
    "rule",
    [
        ".a { color: var(--hair) !important; background: var(--slide); }",
        ".a { color: VAR(--hair); background: var(--slide) !IMPORTANT; }",
        ".a { color: var(--hair, #777); background: var(--slide); }",
        ".a { color: var(--hair); background-color: var(--ink); background: var(--slide); }",  # the later one wins
    ],
)
def test_a_low_contrast_pair_is_found_however_it_is_written(rule):
    result = api.lint_snippet(PROJECT, rule, "css")
    assert result["contrast_pairs"] == {"measured": 1, "failing": 1}
    assert any("1.32:1" in finding["message"] for finding in result["findings"])


def test_undeclared_pair_check_sees_through_important_and_fallbacks():
    names = {"page", "ink", "grey", "brand", "wash"}
    declared = [pair("ink", "page")]
    for value in ("var(--grey) !important", "VAR(--grey)", "var(--grey, #777)"):
        assert contrast.undeclared_pairs(f".a {{ color: {value}; }}", SURFACES, declared, names) == [(1, ".a", "grey", None)]


# ---- design.toml mistakes are errors, not silent defaults ----


@pytest.mark.parametrize(
    "entry",
    [
        {"foreground": "ink", "on": ["page"], "kind": "text", "opacity": 55},
        {"foreground": "ink", "on": ["page"], "kind": "text", "opacity": 0},
        {"foreground": "ink", "on": ["page"], "kind": "text", "opacity": "half"},
        {"foreground": "ink", "on": "page", "kind": "text"},
        {"foreground": "ink", "on": [], "kind": "text"},
        {"foreground": "ink", "kind": "text"},
        {"foreground": "ink", "on": ["page"], "kind": "text", "known_failure": ""},
    ],
)
def test_bad_pair_entries_are_rejected(entry):
    with pytest.raises(ConfigError):
        read_pairs(config([entry]), DOCUMENT)


def test_a_repeated_pair_and_an_empty_surface_are_rejected():
    same = {"foreground": "ink", "on": ["page"], "kind": "text"}
    with pytest.raises(ConfigError, match="repeats"):
        read_pairs(config([same, dict(same)]), DOCUMENT)
    with pytest.raises(ConfigError):
        read_pairs(config([], {"empty": []}), DOCUMENT)


def test_known_failure_is_judged_for_the_whole_entry():
    # grey fails on the wash and passes on the page. One entry covers both, so the mark is not stale.
    entry = {"foreground": "grey", "on": ["page", "wash"], "kind": "text", "known_failure": "Accepted."}
    surfaces, pairs = read_pairs(config([entry]), DOCUMENT)
    results = contrast.evaluate(DOCUMENT, surfaces, pairs)
    assert contrast.stale_known_failures(pairs, results) == []
    # Once nothing in the entry fails, it is stale, and is reported once.
    passing = [Pair("ink", "page", "text", 1.0, "", "Old.", 0), Pair("ink", "page", "non-text", 1.0, "", "Old.", 0)]
    assert len(contrast.stale_known_failures(passing, contrast.evaluate(DOCUMENT, SURFACES, passing))) == 1


def test_sky_table_with_an_unreadable_entry_fails():
    with pytest.raises(ConfigError):
        contrast.read_sky('const SKY = { clear: [1, 2, 3], "storm": [4, 5, 6] };', "SKY")
    with pytest.raises(ConfigError):
        contrast.read_sky("const SKY = { clear: [1, 2, 3], fog: [1.5, 2, 3] };", "SKY")
    with pytest.raises(ConfigError):
        contrast.read_sky("const SKY = { clear: [999, 2, 3] };", "SKY")


# ---- the exporter ----


def test_only_the_plain_dark_media_query_counts_as_system_night():
    def classify(media: str):
        return tokens.classify(css.Rule(':root:not([data-theme="day"])', (media,), (), 1))

    assert classify("@media (prefers-color-scheme: dark)").via == "media"
    assert classify("@media screen and (prefers-color-scheme:dark)").via == "media"
    for media in ("@media not (prefers-color-scheme: dark)", "@media print and (prefers-color-scheme: dark)", "@media (prefers-color-scheme: dark) and (min-width: 900px)"):
        with pytest.raises(ValueError):
            classify(media)


# ---- lint ----


@pytest.fixture
def repo(tmp_path) -> Project:
    project = Project(tmp_path)
    write_text(project.design_dir / "design.toml", DESIGN_TOML)
    write_text(project.tokens_schema, read_text(PROJECT.tokens_schema))
    write_text(project.source_css, STYLES)
    return project


def test_a_token_declared_in_another_stylesheet_fails(repo):
    write_text(repo.frontend_src / "tools.css", ":root { --ink: #111111; }\n.card { --local: 4px; }")
    result = lint.run(repo)
    assert result["problems"]["tokens_outside_the_token_file"] == 2
    assert result["ok"] is False


def test_a_file_with_a_byte_order_mark_is_read_normally(repo):
    repo.source_css.write_bytes(b"\xef\xbb\xbf" + STYLES.encode("utf-8"))
    (repo.design_dir / "design.toml").write_bytes(b"\xef\xbb\xbf" + DESIGN_TOML.encode("utf-8"))
    assert lint.run(repo)["ok"] is True


def test_allowlist_entries_need_a_reason_and_overlapping_ones_are_both_in_use(repo):
    write_text(repo.frontend_src / "x.css", ".x { fill: #123456; }")
    both = (
        '\n[[compliance.allow]]\nfile = "frontend/src/x.css"\nmatch = "#123456"\nreason = "First."\n'
        '\n[[compliance.allow]]\nfile = "frontend/src/x.css"\nreason = "Whole file."\n'
    )
    write_text(repo.design_dir / "design.toml", DESIGN_TOML + both)
    result = lint.run(repo)
    assert result["compliance"]["stale_allow"] == []
    assert result["compliance"]["findings"][0]["allowed"] == "First."

    write_text(repo.design_dir / "design.toml", DESIGN_TOML + '\n[[compliance.allow]]\nfile = "frontend/src/x.css"\nreason = ""\n')
    with pytest.raises(ConfigError):
        lint.run(repo)


def test_config_mistakes_print_one_line_not_a_traceback(repo, capsys):
    from myelin_design.__main__ import main

    write_text(repo.design_dir / "design.toml", DESIGN_TOML.replace('source = "frontend/src/styles.css"', 'source = "frontend/src/missing.css"'))
    assert main(["--root", str(repo.root), "export"]) == 1
    assert "Cannot read" in capsys.readouterr().err
    assert main(["--root", str(repo.root / "nowhere"), "lint"]) == 1
    assert "Cannot read" in capsys.readouterr().err
