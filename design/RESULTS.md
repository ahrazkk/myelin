# Results

What the tooling found when it was first run on Myelin, at commit `db7cc3c` (v0.3.0), on
10 November 2026, and what changed afterwards (see "After"). Every "before" number comes from
[`reports/baseline.json`](reports/baseline.json), and can be reproduced with the commands at the end.

## Summary

| Check | Result |
| --- | --- |
| Token export | 10 tokens, 2 themes, 4 accents. The two night declarations agree. Valid against the schema. |
| Token compliance | **85.7%**: 162 token uses and 27 hard-coded colours, in 19 files. |
| Contrast (WCAG 2.1 AA) | 46 declared pairs, measured 556 times (themes, accents and skies). **334 pass, 72 fail**, 150 are exempt. |
| Focus states | No findings. The global `:focus-visible` rule exists and nothing removes the outline. |

"Exempt" means decorative or inactive: measured and listed, but WCAG sets no threshold for them.

## What passed

- **Every text and accent token on the page background (`--slide`) passes 4.5:1**, in both themes and
  all four accents. This matches the 14 ratios that were measured by hand before the linter existed.
  It is exact when Background is set to Plain. See finding 2d for the default background.

  | Token on `--slide` | Day | Night |
  | --- | --- | --- |
  | `--ink` | 13.60 | 14.69 |
  | `--muted` | 5.03 | 6.55 |
  | `--cresyl` | 5.99 | 6.57 |
  | `--myelin`, lowest of the four accents | 4.57 (emerald) | 7.78 (rose) |

- `--ink` passes on every surface it is used on, including the washes and the sky (lowest 6.99:1).
- Text on a solid accent fill (`--slide` on `--myelin`) passes: 4.57:1 at its lowest.
- The focus outline (`--cresyl`) passes 3:1 on the page, on both washes and on every sky gradient.
- Both stylesheets are fully tokenised apart from one shadow: 158 token uses, 1 literal.
- No unknown tokens, and no text colour in the CSS without a declared pair.

## Findings

### 1. Hard-coded colours (27)

| Where | Count | What |
| --- | --- | --- |
| `Settings.tsx:55-58` | 8 | The accent picker's swatches repeat the eight `--myelin` accent values as hex. A copy of a token: if a token changes, the swatch is wrong. |
| `Ambient.tsx:71-74` | 4 | Fallback RGB values that repeat the day values of `--slide`, `--ink`, `--myelin` and `--cresyl`. Also copies. |
| `Ambient.tsx:377-672` | 14 | Canvas colours for the sun, moon, stars, rain, snow and lightning. Not copies of tokens. |
| `tools.css:618` | 1 | The shadow under the command reply: `rgb(0 0 0 / 0.12)`. |

Not counted: `Ambient.tsx` also holds 34 bare `[r, g, b]` arrays (sky and cloud colours). The scanner
cannot tell a colour from any other three numbers, so it only counts an array that equals a token.
If all 34 were counted as hard-coded, compliance would be 72.6%.

### 2. Contrast below AA

Grouped by cause. The full table, with every measurement, is in [`reports/baseline.md`](reports/baseline.md).

**a. Text on a translucent wash, day theme.** The washes darken the background a little, and
`--muted` only clears 4.5:1 on the page by half a point.

| Pair | Lowest | Needs | Where |
| --- | --- | --- | --- |
| `--muted` on `--cresyl-wash` | 4.35 | 4.5 | `.btn.quiet` in the focus badge when time is up |
| `--muted` on `--myelin-wash` | 4.45 | 4.5 | Labels inside `.quick-log`; fails in 3 of 4 accents |
| `--myelin` on `--myelin-wash` | 4.06 | 4.5 | `.focus-badge-time`; fails in all 4 accents |

**b. Text made fainter with `opacity`.**

| Pair | Day | Night | Needs | Where |
| --- | --- | --- | --- | --- |
| `--muted` at 0.8 | 3.38 | 4.62 (passes) | 4.5 | `.input::placeholder` |
| `--muted` at 0.8 on `--myelin-wash` | 3.10 | 4.04 | 4.5 | Placeholders inside `.quick-log` |
| `--ink` at 0.55 | 3.49 | 5.17 (passes) | 4.5 | Past days in the Week view (`.week-day.is-before`) |
| `--muted` at 0.55 | 2.18 | 2.86 | 4.5 | Dates and details of past days in the Week view |

**c. `--hair` as the only edge of a control.** 1.32:1 by day and 1.41:1 at night, where 3:1 is needed.
This applies to `.command-input` and `.sql-editor`, whose only boundary is a hairline, and to the
"missed day" cells in the heatmap. Where `--hair` is a separator, or surrounds a control that has a
text label, it is decorative and exempt.

**d. The sky behind the page (day theme).** With Background set to Live weather, which is the
default, the app paints a sky gradient behind the whole page: the sky colour at the top, 85% of the
way to `--slide` two thirds down, `--slide` only at the bottom. The header sits near the top of it.
Measured against the top of each sky:

| Pair | Lowest | Fails on | Needs | Where |
| --- | --- | --- | --- | --- |
| `--muted` text | 2.89 (storm) | 7 of 8 skies | 4.5 | The tabs, AM/PM, Hijri date, weather line |
| `--cresyl` text | 3.44 (storm) | storm and rain | 4.5 | "Next prayer" line, interview line |
| `--muted` icon | 2.89 (storm) | storm only | 3 | The theme toggle |
| `--myelin` text on its wash over the sky | 2.41 | all 32 | 4.5 | The time in the focus badge |
| `--muted` on `--cresyl-wash` over the sky | 2.59 | all 8 | 4.5 | "Stop" in the focus badge when time is up |

The night theme has no failures against any sky gradient.

How to read these, and what they leave out:

- The header starts about 6% down the gradient, so over the gradient alone the true value is slightly
  better than the figure shown and worse than the same pair on the page.
- **Only pairs that occur in the header are measured on the sky.** Everything lower on the page is
  measured on `--slide`, which is exact only with the Plain background. In Live weather the real
  value for those pairs lies somewhere between their page figure and a sky figure. Pairs with little
  room to spare on the page, such as `--muted` (5.03) and emerald `--myelin` (4.57), may dip below
  4.5:1 in the upper part of the page. The linter does not measure that.
- **Clouds, mist, the sun and moon, rain and the cursor glow are drawn over the gradient and are not
  modelled.** A reviewer's hand calculation put `--muted` at about 4.2:1 over a night cloud, so a
  pass against the sky gradient is not a pass against everything the canvas can paint.

### 3. Findings outside the linters

Found while mapping the app, not by a linter:

- **Tabs and radio groups have no arrow-key navigation.** They use `role="tablist"` and
  `role="radiogroup"`, but each item is its own Tab stop. They work with Tab and Enter. The ARIA
  authoring pattern also expects arrow keys.
- **The SQL editor captures Tab** to insert two spaces, so forward Tab does not leave it (Shift+Tab does).

## What the linters do not show

- Contrast is measured for pairs declared by hand. A pair that was never declared is not measured,
  unless one CSS rule sets both its text colour and its background.
- The classification of each pair (text, non-text, decorative) is a judgment. An auditor could argue
  some of them differently. Each pair's `where` note in `design.toml` records what was decided.
- Nothing here runs in a browser. Rendering, focus order and real keyboard behaviour are not tested.
- Token compliance counts colour uses it can recognise in source text. Numeric RGB arrays are the
  known gap.

## After

### Token compliance: 85.7% to 91.7%

| | Before | After |
| --- | --- | --- |
| Token uses | 162 | 165 |
| Hard-coded colours | 27 | 15 |
| Of those, with no written reason | 27 | 0 |
| Compliance | 85.7% | 91.7% |

What changed:

- The 12 copies of token values are gone. `Settings.tsx` (8 swatch colours) and `Ambient.tsx`
  (4 fallback colours) now read them from `frontend/src/tokens.generated.ts`, which the exporter
  writes from the stylesheet. The drift gate covers that file too.
- The remaining 15 are allowed exceptions with a reason in `design.toml`: 14 canvas scene colours in
  `Ambient.tsx` and one shadow in `tools.css`. They still count as hard-coded, which is why the figure
  is 91.7% and not 100%.
- The three extra token uses come from the contrast fixes below, which added `var(--ink)` and
  `var(--slide)` rules. Removing the copies alone gave 91.5%.

### Contrast: 72 failures to 12

| | Before | After |
| --- | --- | --- |
| Declared pairs | 46 | 38 |
| Measurements | 556 | 444 |
| Failing | 72 | 12 |

Fixed (groups a and b above), in `styles.css` and `tools.css`:

- Secondary text on a wash now uses `--ink`: labels and quiet buttons in `.quick-log`, "Stop" in the
  focus badge, hovered or selected free SQL questions. The focus badge time uses `--ink` too.
- Placeholders are no longer faded, and fields inside `.quick-log` have a `--slide` background.
- Days before the start date in the Week view are marked with `--muted` and a lighter weight
  instead of 0.55 opacity.

The pair count fell because eight pairs no longer occur in the app, so they are no longer declared.

Still failing (12), and not changed:

- `--hair` as the only edge of `.command-input` and `.sql-editor`, and the missed-day heatmap cells (2).
- Header text over the day sky: `--muted` on 7 of 8 skies, `--cresyl` on 2, the theme toggle icon on 1 (10).

Not checked: these fixes were verified by the linter and a clean build, not by looking at the app.

## Reproduce

```bash
cd design
pip install -e ".[dev]"
python -m myelin_design export --check     # exit 0: tokens.json matches the CSS
python -m myelin_design lint --write       # exit 1 while findings remain; writes reports/lint.md
pytest -q
```
