import json

import pytest

from myelin_design import lint, report, tokens
from myelin_design.__main__ import main
from myelin_design.project import Project, read_text, write_text

DESIGN_TOML = """
source = "frontend/src/styles.css"
default_accent = "blue"

[tokens.page]
role = "background"
description = "Page."

[tokens.ink]
role = "text"
description = "Text."

[tokens.faint]
role = "text"
description = "Faint text."

[contrast.surfaces]
page = ["page"]

[[contrast.pair]]
foreground = "ink"
on = ["page"]
kind = "text"
where = "body"
"""

STYLES = """
:root { --page: #ffffff; --ink: #000000; --faint: #cccccc; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="day"]) { --page: #000000; --ink: #ffffff; --faint: #333333; }
}
:root[data-theme="night"] { --page: #000000; --ink: #ffffff; --faint: #333333; }

body { background: var(--page); color: var(--ink); }
:focus-visible { outline: 3px solid var(--ink); }
"""


@pytest.fixture
def repo(tmp_path) -> Project:
    """A tiny repo that passes every check."""
    project = Project(tmp_path)
    write_text(project.design_dir / "design.toml", DESIGN_TOML)
    write_text(project.tokens_schema, read_text(Project.default().tokens_schema))
    write_text(project.source_css, STYLES)
    write_text(project.frontend_src / "App.tsx", 'export const App = () => <p style={{ color: "var(--ink)" }}>hi</p>;\n')
    return project


def add(project: Project, name: str, text: str) -> None:
    write_text(project.frontend_src / name, text)


def test_a_clean_repo_passes(repo):
    result = lint.run(repo)
    assert result["ok"] is True
    assert result["files_scanned"] == 2
    assert result["compliance"]["percent"] == 100
    assert result["compliance"]["token_uses"] == 4  # three in styles.css, one in App.tsx
    assert result["contrast"]["measurements"] == 2  # one pair, two themes
    assert result["focus"]["global_rule"]["file"] == "frontend/src/styles.css"
    assert not any(result["problems"].values())


def test_hard_coded_colour_fails_and_lowers_compliance(repo):
    add(repo, "extra.css", ".x { color: var(--ink); border-color: #123456; }")
    result = lint.run(repo)
    assert result["ok"] is False
    assert result["problems"]["hard_coded_colours"] == 1
    assert result["compliance"]["percent"] == pytest.approx(100 * 5 / 6, abs=0.01)
    (finding,) = result["compliance"]["findings"]
    assert (finding["file"], finding["line"], finding["text"]) == ("frontend/src/extra.css", 1, "#123456")


def test_allowlisted_colour_passes_but_still_counts_as_hard_coded(repo):
    add(repo, "extra.css", ".x { box-shadow: 0 1px 2px rgb(0 0 0 / 0.2); }")
    allow = '\n[[compliance.allow]]\nfile = "frontend/src/extra.css"\nmatch = "rgb(0 0 0 / 0.2)"\nreason = "A shadow is not a palette colour."\n'
    write_text(repo.design_dir / "design.toml", DESIGN_TOML + allow)
    result = lint.run(repo)
    assert result["ok"] is True
    assert result["compliance"]["allowed"] == 1
    assert result["compliance"]["hard_coded"] == 1
    assert result["compliance"]["percent"] < 100
    assert result["compliance"]["findings"][0]["allowed"] == "A shadow is not a palette colour."


def test_an_allowlist_entry_that_matches_nothing_fails(repo):
    allow = '\n[[compliance.allow]]\nfile = "frontend/src/gone.css"\nreason = "File was deleted."\n'
    write_text(repo.design_dir / "design.toml", DESIGN_TOML + allow)
    result = lint.run(repo)
    assert result["ok"] is False
    assert result["problems"]["stale_allowlist_entries"] == 1


def test_unknown_token_fails_and_cannot_be_allowlisted(repo):
    add(repo, "extra.css", ".x { color: var(--inc); }")
    allow = '\n[[compliance.allow]]\nfile = "frontend/src/extra.css"\nreason = "Trying to hide a typo."\n'
    write_text(repo.design_dir / "design.toml", DESIGN_TOML + allow)
    result = lint.run(repo)
    assert result["problems"]["unknown_tokens"] == 1
    assert result["compliance"]["findings"][0]["allowed"] is None


def test_contrast_failure_fails(repo):
    pair = '\n[[contrast.pair]]\nforeground = "faint"\non = ["page"]\nkind = "text"\nwhere = ".hint"\n'
    write_text(repo.design_dir / "design.toml", DESIGN_TOML + pair)
    result = lint.run(repo)
    assert result["ok"] is False
    assert result["problems"]["contrast_failures"] == 2  # #ccc on white, #333 on black
    assert "Below the threshold" in report.render(result)


def test_known_contrast_failure_passes_until_it_goes_stale(repo):
    pair = '\n[[contrast.pair]]\nforeground = "faint"\non = ["page"]\nkind = "text"\nwhere = ".hint"\nknown_failure = "Accepted for now."\n'
    write_text(repo.design_dir / "design.toml", DESIGN_TOML + pair)
    result = lint.run(repo)
    assert result["ok"] is True
    assert result["contrast"]["known"] == 2

    write_text(repo.source_css, STYLES.replace("#cccccc", "#555555").replace("#333333", "#aaaaaa"))
    result = lint.run(repo)
    assert result["ok"] is False
    assert result["problems"]["stale_known_failures"] == 1


def test_text_colour_without_a_declared_pair_fails(repo):
    add(repo, "extra.css", ".hint { color: var(--faint); }")
    result = lint.run(repo)
    assert result["problems"]["undeclared_pairs"] == 1
    assert result["contrast"]["undeclared"][0]["selector"] == ".hint"


def test_removed_outline_fails(repo):
    add(repo, "extra.css", ".x:focus { outline: none; }")
    add(repo, "Bad.tsx", 'export const B = () => <button style={{ outline: "none" }} />;\n')
    result = lint.run(repo)
    assert result["problems"]["focus_findings"] == 2
    assert {finding["file"] for finding in result["focus"]["findings"]} == {"frontend/src/extra.css", "frontend/src/Bad.tsx"}


def test_missing_global_focus_rule_fails(repo):
    write_text(repo.source_css, STYLES.replace(":focus-visible { outline: 3px solid var(--ink); }", ""))
    result = lint.run(repo)
    assert result["focus"]["global_rule"] is None
    assert result["problems"]["focus_findings"] == 1


def test_report_is_plain_data_and_renders(repo):
    result = lint.run(repo)
    assert json.loads(json.dumps(result)) == result  # nothing but JSON types
    text = report.render(result)
    assert text.startswith("# Design lint report")
    assert "**Result: pass.**" in text
    assert "100.0%" in text
    assert report.render(lint.run(repo)) == text  # same input, same file


# ---- Command line ----


def test_cli_lint_writes_checks_and_detects_stale_reports(repo, capsys):
    root = ["--root", str(repo.root)]
    assert main([*root, "lint", "--check"]) == 1  # no report committed yet
    assert main([*root, "lint", "--write"]) == 0
    assert (repo.design_dir / "reports" / "lint.md").exists()
    assert json.loads(read_text(repo.design_dir / "reports" / "lint.json"))["ok"] is True
    assert main([*root, "lint", "--check"]) == 0

    add(repo, "extra.css", ".x { color: var(--ink); }")  # still clean, but the numbers change
    assert main([*root, "lint"]) == 0
    assert main([*root, "lint", "--check"]) == 1
    assert "out of date" in capsys.readouterr().err


def test_cli_lint_fails_on_findings(repo, capsys):
    add(repo, "extra.css", ".x { color: #123456; }")
    assert main(["--root", str(repo.root), "lint"]) == 1
    assert "FAIL hard coded colours: 1" in capsys.readouterr().out


def test_cli_lint_reports_config_errors(repo, capsys):
    write_text(repo.design_dir / "design.toml", DESIGN_TOML.replace('on = ["page"]', 'on = ["nowhere"]'))
    assert main(["--root", str(repo.root), "lint"]) == 1
    assert "design.toml" in capsys.readouterr().err


# ---- The real repo ----


def test_the_real_repo_lints_without_crashing():
    """The findings are tracked in design/reports; here we only pin the facts that should never move by accident."""
    project = Project.default()
    result = lint.run(project)
    assert result["focus"]["global_rule"] == {"file": "frontend/src/styles.css", "line": 121, "outline": "3px solid var(--cresyl)"}
    assert result["compliance"]["unknown_tokens"] == 0
    assert result["contrast"]["undeclared"] == []
    assert set(result["contrast"]["sky"]["day"]) == {"clear", "partly", "cloudy", "fog", "drizzle", "rain", "snow", "storm"}
    # Every base token on the page background: the 14 ratios measured by hand before this tool existed.
    document = tokens.export(project)
    assert len(document["tokens"]) == 10
