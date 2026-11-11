from myelin_design import css


def test_reads_selectors_declarations_and_lines():
    rules = css.parse(".a {\n  color: red;\n  margin: 0\n}\n\n.b, .c { color: blue; }\n")
    assert [rule.selector for rule in rules] == [".a", ".b, .c"]
    assert [(d.prop, d.value, d.line) for d in rules[0].declarations] == [
        ("color", "red", 2),
        ("margin", "0", 3),  # the last declaration needs no semicolon
    ]
    assert rules[0].line == 1
    assert rules[1].line == 6


def test_rules_inside_media_remember_the_media_query():
    rules = css.parse("@media (prefers-color-scheme: dark) {\n  :root { --x: #000; }\n}\n.after { top: 0; }")
    assert rules[0].selector == ":root"
    assert rules[0].at_rules == ("@media (prefers-color-scheme: dark)",)
    assert rules[1].selector == ".after"
    assert rules[1].at_rules == ()


def test_comments_are_ignored_and_keep_line_numbers_right():
    rules = css.parse("/* a { color: red; }\n   still a comment */\n.real { color: /* inline */ blue; }")
    assert len(rules) == 1
    assert rules[0].line == 3
    assert rules[0].get("color") == "blue"


def test_separators_inside_strings_and_parentheses_are_text():
    rules = css.parse('.a { content: "};{"; background: url(data:image/png;base64,AAAA); color: red; }')
    assert rules[0].get("content") == '"};{"'
    assert rules[0].get("background") == "url(data:image/png;base64,AAAA)"
    assert rules[0].get("color") == "red"


def test_property_names_are_lowercased_but_custom_properties_are_not():
    rule = css.parse(".a { COLOR: red; --Brand: blue; }")[0]
    assert [d.prop for d in rule.declarations] == ["color", "--Brand"]


def test_get_returns_the_last_value_for_a_property():
    assert css.parse(".a { outline: none; outline: 2px solid; }")[0].get("outline") == "2px solid"


def test_keyframes_steps_are_not_mistaken_for_top_level_rules():
    rules = css.parse("@keyframes pulse { from { opacity: 0; } to { opacity: 1; } }")
    assert [(rule.selector, rule.at_rules) for rule in rules] == [
        ("from", ("@keyframes pulse",)),
        ("to", ("@keyframes pulse",)),
    ]


def test_broken_input_gives_a_best_effort_result_and_never_raises():
    assert css.parse("") == []
    assert css.parse("}}}}") == []
    assert css.parse(".a { color: red")[0].get("color") == "red"  # never closed
    # An unclosed string ends at the line break, as in a browser, so the next rule survives.
    rules = css.parse('.a { content: "unclosed\n}\n.b { color: red; }')
    assert [rule.selector for rule in rules] == [".a", ".b"]
    # One unclosed parenthesis must not swallow the rules after it.
    rules = css.parse(".a { width: calc(1px; }\n.b { color: red; }")
    assert [rule.selector for rule in rules] == [".a", ".b"]


def test_deep_nesting_does_not_overflow_the_stack():
    depth = 50_000
    rules = css.parse("a{" * depth + "color:red" + "}" * depth)
    assert len(rules) == depth
