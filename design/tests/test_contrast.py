import pytest

from myelin_design import contrast
from myelin_design.color import Color
from myelin_design.contrast import ConfigError, Pair, evaluate, read_pairs, read_sky, undeclared_pairs


def themed(day: str, night: str, day_alpha: float = 1.0, night_alpha: float = 1.0) -> dict:
    return {"day": {"hex": day, "alpha": day_alpha}, "night": {"hex": night, "alpha": night_alpha}}


DOCUMENT = {
    "themes": ["day", "night"],
    "defaultAccent": "blue",
    "accents": ["blue", "green"],
    "tokens": [
        {"name": "page", "values": themed("#ffffff", "#000000")},
        {"name": "ink", "values": themed("#000000", "#ffffff")},
        {"name": "grey", "values": themed("#767676", "#767676")},
        {"name": "brand", "values": themed("#0000ff", "#8888ff"), "accents": {"green": themed("#008000", "#88ff88")}},
        {"name": "wash", "values": themed("#000000", "#ffffff", 0.5, 0.5)},
    ],
}
SURFACES = {"page": ["page"], "wash": ["page", "wash"], "sky": ["@sky"], "sky-wash": ["@sky", "wash"]}
SKIES = {"day": {"clear": Color(200, 220, 240), "storm": Color(120, 130, 150)}, "night": {"clear": Color(5, 10, 30)}}


def pair(foreground: str, surface: str, kind: str = "text", opacity: float = 1.0, known: str | None = None) -> Pair:
    return Pair(foreground, surface, kind, opacity, "", known)


def test_measures_each_pair_in_each_theme():
    day, night = evaluate(DOCUMENT, SURFACES, [pair("ink", "page")])
    assert (day.theme, night.theme) == ("day", "night")
    assert day.ratio == pytest.approx(21) and night.ratio == pytest.approx(21)
    assert day.status == "pass" and day.threshold == 4.5
    assert day.accent is None and day.sky is None  # the pair depends on neither


def test_threshold_follows_the_kind():
    # #767676 on white is 4.54:1: enough for text. On the 50% wash it is far too low.
    results = evaluate(DOCUMENT, SURFACES, [pair("grey", "page"), pair("grey", "wash"), pair("grey", "wash", "non-text")])
    day = [r for r in results if r.theme == "day"]
    assert [r.status for r in day] == ["pass", "fail", "fail"]
    assert [r.threshold for r in day] == [4.5, 4.5, 3.0]


def test_translucent_background_is_composited_first():
    (day, _night) = evaluate(DOCUMENT, SURFACES, [pair("ink", "wash")])
    assert day.background_hex == "#808080"  # 50% black over white
    assert day.ratio == pytest.approx(5.32, abs=0.01)


def test_opacity_fades_the_foreground_into_the_background():
    (day, _night) = evaluate(DOCUMENT, SURFACES, [pair("ink", "page", opacity=0.5)])
    assert day.foreground_hex == "#808080"
    assert day.ratio == pytest.approx(3.95, abs=0.01)
    assert day.status == "fail"


def test_accent_dependent_pairs_are_measured_under_every_accent():
    results = evaluate(DOCUMENT, SURFACES, [pair("brand", "page")])
    assert [(r.theme, r.accent) for r in results] == [("day", "blue"), ("day", "green"), ("night", "blue"), ("night", "green")]
    assert results[0].foreground_hex == "#0000ff" and results[1].foreground_hex == "#008000"


def test_sky_surfaces_are_measured_against_every_sky_colour():
    results = evaluate(DOCUMENT, SURFACES, [pair("ink", "sky")], SKIES)
    assert [(r.theme, r.sky) for r in results] == [("day", "clear"), ("day", "storm"), ("night", "clear")]
    assert results[0].background_hex == "#c8dcf0"
    # A wash over the sky: the sky is the bottom layer.
    over = evaluate(DOCUMENT, SURFACES, [pair("ink", "sky-wash")], SKIES)
    assert over[0].background_hex == "#646e78"


def test_sky_surface_without_sky_colours_is_a_config_error():
    with pytest.raises(ConfigError):
        evaluate(DOCUMENT, SURFACES, [pair("ink", "sky")])


def test_surface_must_start_opaque():
    with pytest.raises(ConfigError):
        evaluate(DOCUMENT, {"bad": ["wash"]}, [pair("ink", "bad")])


def test_exempt_kinds_are_measured_but_never_fail():
    results = evaluate(DOCUMENT, SURFACES, [pair("grey", "wash", "decorative"), pair("grey", "wash", "inactive")])
    assert {r.status for r in results} == {"info"}
    assert all(r.threshold is None for r in results)


def test_known_failures_are_reported_separately_and_go_stale():
    failing = pair("grey", "wash", known="accepted for now")
    results = evaluate(DOCUMENT, SURFACES, [failing])
    assert {r.status for r in results} == {"known"}
    assert contrast.stale_known_failures([failing], results) == []

    passing = pair("ink", "page", known="no longer true")
    results = evaluate(DOCUMENT, SURFACES, [passing])
    assert {r.status for r in results} == {"pass"}
    assert len(contrast.stale_known_failures([passing], results)) == 1


def test_ratio_in_json_is_cut_not_rounded():
    (day, _night) = evaluate(DOCUMENT, SURFACES, [pair("grey", "page")])
    assert day.ratio == pytest.approx(4.5422, abs=0.0001)
    assert day.to_json()["ratio"] == 4.54


# ---- Reading design.toml ----


def config(pairs: list[dict], surfaces: dict | None = None) -> dict:
    return {"contrast": {"surfaces": surfaces or SURFACES, "pair": pairs}}


def test_read_pairs_expands_one_entry_per_surface():
    entry = {"foreground": "ink", "on": ["page", "wash"], "kind": "text", "opacity": 0.8, "where": ".x"}
    surfaces, pairs = read_pairs(config([entry]), DOCUMENT)
    assert surfaces == SURFACES
    assert pairs == [Pair("ink", "page", "text", 0.8, ".x", None), Pair("ink", "wash", "text", 0.8, ".x", None)]


@pytest.mark.parametrize(
    "entry",
    [
        {"foreground": "nope", "on": ["page"], "kind": "text"},
        {"foreground": "ink", "on": ["nowhere"], "kind": "text"},
        {"foreground": "ink", "on": ["page"], "kind": "huge-text"},
    ],
)
def test_read_pairs_rejects_what_it_cannot_measure(entry):
    with pytest.raises(ConfigError):
        read_pairs(config([entry]), DOCUMENT)


def test_read_pairs_rejects_a_surface_made_of_unknown_tokens():
    with pytest.raises(ConfigError):
        read_pairs(config([], {"bad": ["page", "glass"]}), DOCUMENT)


# ---- Reading the sky from TypeScript ----

SKY_SOURCE = """
type RGB = [number, number, number];
// const SKY_DAY = { fake: [1, 2, 3] };
const SKY_DAY: Record<WeatherScene, RGB> = {
  clear: [196, 218, 243],
  storm: [174, 184, 201], // darkest
};
const SKY_NIGHT: Record<WeatherScene, RGB> = { clear: [4, 8, 28] };
"""


def test_read_sky_reads_the_table_from_source():
    assert read_sky(SKY_SOURCE, "SKY_DAY") == {"clear": Color(196, 218, 243), "storm": Color(174, 184, 201)}
    assert read_sky(SKY_SOURCE, "SKY_NIGHT") == {"clear": Color(4, 8, 28)}


def test_read_sky_fails_loudly_when_the_table_is_gone():
    with pytest.raises(ConfigError):
        read_sky(SKY_SOURCE, "SKY_DUSK")
    with pytest.raises(ConfigError):
        read_sky("const SKY_DAY = {};", "SKY_DAY")


# ---- Pairs the CSS reveals on its own ----

NAMES = {"page", "ink", "grey", "brand", "wash"}


def test_text_colour_with_no_declared_pair_is_reported():
    pairs = [pair("ink", "page")]
    css_text = ".a { color: var(--ink); }\n.b { color: var(--grey); }\n.c { color: inherit; }\n.d { color: var(--other); }"
    assert undeclared_pairs(css_text, SURFACES, pairs, NAMES) == [(2, ".b", "grey", None)]


def test_colour_and_background_in_one_rule_must_be_declared_together():
    css_text = ".btn { color: var(--page); background: var(--brand); }"
    surfaces = {**SURFACES, "accent": ["brand"]}
    assert undeclared_pairs(css_text, surfaces, [pair("page", "page")], NAMES) == [(1, ".btn", "page", "brand")]
    assert undeclared_pairs(css_text, surfaces, [pair("page", "accent")], NAMES) == []
    # A non-text pair does not cover text.
    assert len(undeclared_pairs(css_text, surfaces, [pair("page", "accent", "non-text")], NAMES)) == 1
