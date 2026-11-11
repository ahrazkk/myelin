import pytest

from myelin_design import focus
from myelin_design.focus import global_focus_rules, scan_css, scan_ts


@pytest.mark.parametrize(
    "rule",
    [
        "button:focus { outline: none; }",
        "button:focus { outline: 0; }",
        "button:focus { outline: 0px solid red; }",
        "a { outline: NONE !important; }",
        "a { outline-style: none; }",
        "a { outline-width: 0; }",
        "a { outline: 2px solid; outline: none; }",  # the later declaration wins
    ],
)
def test_removing_the_outline_is_a_finding(rule):
    (finding,) = scan_css(rule)
    assert finding.kind == focus.OUTLINE_REMOVED
    assert finding.line == 1


@pytest.mark.parametrize(
    "rule",
    [
        "button:focus { outline: none; box-shadow: 0 0 0 3px var(--cresyl); }",
        "button:focus { outline: 0; border-color: var(--myelin); }",
        "button:focus { outline: none; background: var(--myelin-wash); }",
    ],
)
def test_a_replacement_in_the_same_rule_is_accepted(rule):
    assert scan_css(rule) == []


@pytest.mark.parametrize(
    "rule",
    [
        "button:focus { outline: none; box-shadow: none; }",
        "button:focus { outline: none; border: 0; }",
        "button:focus { outline: none; background: transparent; }",
        "button:focus { outline: none; color: red; }",
    ],
)
def test_an_empty_replacement_does_not_count(rule):
    assert len(scan_css(rule)) == 1


@pytest.mark.parametrize(
    "rule",
    [
        "a { outline: 3px solid var(--cresyl); }",
        "a { outline-offset: 2px; }",
        "a { outline: none; outline: 2px solid var(--cresyl); }",  # put back by the later declaration
        "a { outline-width: 10px; }",
        "a { color: red; }",
    ],
)
def test_visible_outlines_are_fine(rule):
    assert scan_css(rule) == []


def test_finding_reports_the_selector_and_line():
    (finding,) = scan_css(".a { color: red; }\n\n.input:focus,\n.btn:focus {\n  outline: none;\n}")
    assert finding.selector == ".input:focus, .btn:focus"
    assert finding.line == 5
    assert finding.text == "outline: none"


def test_global_focus_rule_is_found():
    rules = global_focus_rules(":focus-visible {\n  outline: 3px solid var(--cresyl);\n  outline-offset: 3px;\n}")
    assert len(rules) == 1
    assert rules[0].get("outline") == "3px solid var(--cresyl)"
    assert len(global_focus_rules("*:focus-visible, .x { outline: 2px dashed; }")) == 1


@pytest.mark.parametrize(
    "stylesheet",
    [
        "",
        ".btn:focus-visible { outline: 3px solid; }",  # only for one component
        ":focus-visible { outline: none; }",  # exists, but removes the outline
        ":focus-visible { outline-offset: 3px; }",  # exists, but draws nothing
        "@media (min-width: 900px) { :focus-visible { outline: 3px solid; } }",  # not always on
        ":focus { outline: 3px solid; }",  # a different pseudo-class
    ],
)
def test_global_focus_rule_must_always_draw_an_outline(stylesheet):
    assert global_focus_rules(stylesheet) == []


def test_inline_styles_in_tsx():
    source = (
        'const a = <button style={{ outline: "none" }} />;\n'
        "const b = <input style={{ outline: 0 }} />;\n"
        "const c = <a style={{ outlineStyle: 'none' }} />;\n"
        "const d = { outlineWidth: 0 };\n"
    )
    findings = scan_ts(source)
    assert [finding.line for finding in findings] == [1, 2, 3, 4]
    assert all(finding.kind == focus.OUTLINE_REMOVED for finding in findings)


def test_css_inside_a_template_literal_in_tsx():
    (finding,) = scan_ts("const css = `\n  .x:focus {\n    outline: none;\n  }\n`;")
    assert finding.line == 3


def test_tsx_that_keeps_the_outline_is_fine():
    source = (
        'const a = <button style={{ outline: "2px solid var(--cresyl)" }} />;\n'
        "const b = { outline: 0.5 };\n"
        "const c = { outlineOffset: 0 };\n"
        '// style={{ outline: "none" }}\n'
        'const d = "the outline: none rule is banned";\n'.replace("outline: none", "outline - none")
    )
    assert scan_ts(source) == []


def test_scan_dispatches_on_language():
    assert len(focus.scan("a { outline: none; }", "css")) == 1
    assert len(focus.scan('const s = { outline: "none" };', "tsx")) == 1
    with pytest.raises(ValueError):
        focus.scan("x", "html")
