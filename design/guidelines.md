# Myelin UI guidelines

Myelin is a calm, full-screen habit dashboard that also runs as a desktop wallpaper. Its palette comes
from histology: myelin is stained blue, neurons violet. These rules describe how its interface is built.

## Colour

- Take every colour from a design token: `color: var(--ink)`. Do not write hex, `rgb()`, `hsl()` or
  named colours in components. Token values change with the theme and the accent; a copied value does not.
- `--slide` is the page background. `--ink` is main text. `--muted` is secondary text.
- `--myelin` is the main accent: done states, the selected item, the primary button. It follows the
  user's accent setting (myelin blue, emerald, amber or rose).
- `--cresyl` is the second accent: whatever is next, and the keyboard focus outline.
- `--hair` is for hairline separators. `--axon-ahead` is a decorative track colour.
- `--cresyl-wash`, `--myelin-wash` and `--code-bg` are translucent fills. Text on a fill has less
  contrast than on the page, so check the pair with `check_contrast` before using it.
- Text on a solid `--myelin` fill uses `--slide`.
- Do not lower text contrast with `opacity`. Pick a token instead.

## Themes and accents

- There are two themes (day and night) and four accents. Anything you build has to work in all eight.
- Components never test for the theme or the accent. They use tokens, and the tokens change.

## Focus and keyboard

- Never remove the focus outline (`outline: none`, `outline: 0`). One global rule,
  `:focus-visible { outline: 3px solid var(--cresyl); outline-offset: 3px; }`, covers every control.
- A control may add to its focus style (a border colour, for example). It may not replace the outline.
- Every action is a real `<button type="button">`, and every field has a label. Do not put click
  handlers on `<div>` or `<span>`.

## Motion

- Motion is optional. CSS transitions and animations are switched off under
  `:root[data-motion="reduce"]` and `@media (prefers-reduced-motion: reduce)`.
- Animation driven by JavaScript must check both of those before it moves anything.

## Semantics (the ARIA patterns in use)

- Tabs: `role="tablist"` holding `<button role="tab" aria-selected aria-controls>`, and one
  `role="tabpanel"` with `aria-labelledby`.
- One choice from a few: `role="radiogroup"` with an `aria-label`, holding `<button role="radio" aria-checked>`.
- On and off: `<button aria-pressed>`.
- A message that appears after an action: `role="status"`. An error: `role="alert"`.
- A button with only an icon needs an `aria-label`. A decorative `<svg>` gets `aria-hidden="true"`.
- A label that should not be seen uses the `.sr-only` class, not `display: none`.
- A chart or drawing is a `<figure>` with an `aria-label` that says what it shows in words.

## Type and shape

- Controls inherit the font: `font: inherit`.
- Font sizes scale with the screen: `clamp(minimum, viewport-based, maximum)`.
- Numbers that change, such as times and counts, use `font-variant-numeric: tabular-nums`.
- Pills and segmented controls use `border-radius: 999px`.
