import pytest

from myelin_design.color import (
    Color,
    composite,
    contrast_ratio,
    flatten,
    parse_color,
    relative_luminance,
    shown,
)

WHITE = Color(255, 255, 255)
BLACK = Color(0, 0, 0)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("#fff", Color(255, 255, 255)),
        ("#EDEFF5", Color(237, 239, 245)),
        ("#0f08", Color(0, 255, 0, 0x88 / 255)),
        ("#11223344", Color(0x11, 0x22, 0x33, 0x44 / 255)),
        ("rgb(123 63 158 / 0.1)", Color(123, 63, 158, 0.1)),  # the syntax Myelin's washes use
        ("rgba(255, 0, 0, 0.5)", Color(255, 0, 0, 0.5)),
        ("rgb(100% 0% 0% / 50%)", Color(255, 0, 0, 0.5)),
        ("hsl(210 50% 40%)", Color(51, 102, 153)),
        ("hsla(120, 100%, 25%, 0.3)", Color(0, 128, 0, 0.3)),
        ("hsl(0.5turn 100% 50%)", Color(0, 255, 255)),
        ("rebeccapurple", Color(102, 51, 153)),
        ("  White ", Color(255, 255, 255)),
        ("transparent", Color(0, 0, 0, 0.0)),
    ],
)
def test_parses_css_colours(text, expected):
    parsed = parse_color(text)
    assert (parsed.r, parsed.g, parsed.b) == (expected.r, expected.g, expected.b)
    assert parsed.a == pytest.approx(expected.a)


@pytest.mark.parametrize(
    "text",
    ["", "#12", "#ggg", "rgb(1 2)", "rgb(a b c)", "var(--ink)", "currentColor", "notacolour", "url(x)"],
)
def test_rejects_what_is_not_a_colour(text):
    with pytest.raises(ValueError):
        parse_color(text)


def test_luminance_runs_from_black_to_white():
    assert relative_luminance(BLACK) == 0
    assert relative_luminance(WHITE) == pytest.approx(1)
    # Pure green is far brighter to the eye than pure blue: the weights are not equal.
    assert relative_luminance(Color(0, 255, 0)) == pytest.approx(0.7152)
    assert relative_luminance(Color(0, 0, 255)) == pytest.approx(0.0722)


def test_contrast_against_published_values():
    assert contrast_ratio(BLACK, WHITE) == pytest.approx(21)
    assert contrast_ratio(WHITE, WHITE) == pytest.approx(1)
    # #767676 is the well-known lightest grey that passes AA on white; #777777 just fails.
    assert contrast_ratio(parse_color("#767676"), WHITE) == pytest.approx(4.54, abs=0.005)
    assert contrast_ratio(parse_color("#777777"), WHITE) == pytest.approx(4.48, abs=0.005)
    assert contrast_ratio(parse_color("#777777"), WHITE) < 4.5


def test_contrast_does_not_depend_on_the_order():
    a, b = parse_color("#2d6bad"), parse_color("#edeff5")
    assert contrast_ratio(a, b) == contrast_ratio(b, a)


def test_composite_blends_over_the_background():
    assert composite(parse_color("rgb(0 0 0 / 0.5)"), WHITE) == Color(128, 128, 128)
    assert composite(parse_color("rgb(255 0 0 / 0)"), WHITE) == WHITE
    assert composite(parse_color("#123456"), WHITE) == parse_color("#123456")
    # Myelin's --cresyl-wash over --slide in the day theme.
    assert composite(parse_color("rgb(123 63 158 / 0.1)"), parse_color("#edeff5")) == Color(226, 221, 236)


def test_flatten_stacks_layers_from_the_bottom_up():
    wash = parse_color("rgb(0 0 0 / 0.5)")
    assert flatten([WHITE, wash, wash]) == Color(64, 64, 64)


def test_translucent_colours_must_be_composited_before_measuring():
    with pytest.raises(ValueError):
        relative_luminance(parse_color("rgb(0 0 0 / 0.5)"))
    with pytest.raises(ValueError):
        composite(BLACK, parse_color("rgb(0 0 0 / 0.5)"))


def test_shown_ratio_is_never_rounded_up():
    assert shown(4.4999) == "4.49"
    assert shown(4.5) == "4.50"
    assert shown(21.0) == "21.00"
