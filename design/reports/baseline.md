# Design lint report

Frozen copy of the first run, at commit `db7cc3c`, before any fix or allowlist entry. The "before" numbers come from here.

**Result: FAIL.** 19 files scanned in `frontend/src`.

| Check | Result |
|---|---|
| Token compliance | 85.7% (162 token uses, 27 hard-coded colours, of which 0 allowed) |
| Contrast (WCAG 2.1 AA) | 556 measurements of 46 declared pairs: 334 pass, 72 fail, 0 known failures, 150 exempt |
| Focus states | 0 findings; global `:focus-visible` rule found |

To fix: 27 hard coded colours, 72 contrast failures.

## Token compliance

Compliance is token uses divided by all colour uses. A token use is `var(--name)` in CSS, or a token read at runtime in TypeScript. A hard-coded colour is a hex, `rgb()`, `hsl()` or named colour outside the token definitions. Allowed exceptions still count as hard-coded.

| File | Token uses | Hard-coded | Compliance |
|---|---|---|---|
| `frontend/src/Ambient.tsx` | 4 | 18 | 18.2% |
| `frontend/src/Settings.tsx` | 0 | 8 | 0.0% |
| `frontend/src/styles.css` | 89 | 0 | 100.0% |
| `frontend/src/tools.css` | 69 | 1 | 98.6% |
| **Total** | **162** | **27** | **85.7%** |

Not counted: 34 bare `[r, g, b]` arrays in TypeScript that do not match a token. They are probably colours, but the scanner cannot tell a colour from any other three numbers. Counting all of them as hard-coded colours would give 72.6%.

### Findings

| Where | Finding | Text | Note | Status |
|---|---|---|---|---|
| `frontend/src/Ambient.tsx:71` | copy of a token | `[237, 239, 245]` | same colour as --slide (day) | **fix** |
| `frontend/src/Ambient.tsx:72` | copy of a token | `[27, 33, 66]` | same colour as --ink (day) | **fix** |
| `frontend/src/Ambient.tsx:73` | copy of a token | `[45, 107, 173]` | same colour as --myelin (day) | **fix** |
| `frontend/src/Ambient.tsx:74` | copy of a token | `[123, 63, 158]` | same colour as --cresyl (day) | **fix** |
| `frontend/src/Ambient.tsx:377` | hard-coded colour | `rgba(255,226,170,${})` |  | **fix** |
| `frontend/src/Ambient.tsx:378` | hard-coded colour | `rgba(255,226,170,${})` |  | **fix** |
| `frontend/src/Ambient.tsx:379` | hard-coded colour | `rgba(255,226,170,0)` |  | **fix** |
| `frontend/src/Ambient.tsx:384` | hard-coded colour | `rgba(220,226,250,0.16)` |  | **fix** |
| `frontend/src/Ambient.tsx:385` | hard-coded colour | `rgba(220,226,250,0)` |  | **fix** |
| `frontend/src/Ambient.tsx:388` | hard-coded colour | `rgba(232,236,248,0.92)` |  | **fix** |
| `frontend/src/Ambient.tsx:401` | hard-coded colour | `rgba(230,236,255,${})` |  | **fix** |
| `frontend/src/Ambient.tsx:432` | hard-coded colour | `rgba(160,186,230,0.32)` |  | **fix** |
| `frontend/src/Ambient.tsx:432` | hard-coded colour | `rgba(64,86,122,0.3)` |  | **fix** |
| `frontend/src/Ambient.tsx:449` | hard-coded colour | `rgba(236,240,255,0.85)` |  | **fix** |
| `frontend/src/Ambient.tsx:449` | hard-coded colour | `rgba(132,150,182,0.55)` |  | **fix** |
| `frontend/src/Ambient.tsx:475` | hard-coded colour | `rgba(196,188,255,${})` |  | **fix** |
| `frontend/src/Ambient.tsx:475` | hard-coded colour | `rgba(255,255,255,${})` |  | **fix** |
| `frontend/src/Ambient.tsx:672` | hard-coded colour | `#fff` |  | **fix** |
| `frontend/src/Settings.tsx:55` | copy of a token | `#2d6bad` | same colour as --myelin (day) | **fix** |
| `frontend/src/Settings.tsx:55` | copy of a token | `#57c4e5` | same colour as --myelin (night) | **fix** |
| `frontend/src/Settings.tsx:56` | copy of a token | `#1f7a5a` | same colour as --myelin (emerald day) | **fix** |
| `frontend/src/Settings.tsx:56` | copy of a token | `#4fd1a1` | same colour as --myelin (emerald night) | **fix** |
| `frontend/src/Settings.tsx:57` | copy of a token | `#9a5b12` | same colour as --myelin (amber day) | **fix** |
| `frontend/src/Settings.tsx:57` | copy of a token | `#f2b25c` | same colour as --myelin (amber night) | **fix** |
| `frontend/src/Settings.tsx:58` | copy of a token | `#b03a6a` | same colour as --myelin (rose day) | **fix** |
| `frontend/src/Settings.tsx:58` | copy of a token | `#f28bb0` | same colour as --myelin (rose night) | **fix** |
| `frontend/src/tools.css:618` | hard-coded colour | `rgb(0 0 0 / 0.12)` |  | **fix** |

## Contrast

Each pair is a foreground token on a surface. Translucent layers are composited before measuring. Thresholds: 4.5:1 for text, 3:1 for non-text (control boundaries, states, the focus outline). Decorative and inactive pairs are measured but exempt. Ratios are cut to two decimals, never rounded up.

When Background is not Plain, the app paints a sky gradient behind the whole page: the sky colour at the top, 85% of the way to `--slide` two thirds down, and `--slide` at the bottom. So "page" results are exact only with the Plain background, or at the bottom of the screen. "sky" results use the colour at the very top. Over the gradient alone, a pair's real value lies between its page result and its sky result, depending on how high up it sits. Only pairs that occur in the header are measured on the sky. The clouds, mist, sun, moon, rain and cursor glow that are drawn over the gradient are not modelled, and they can lower contrast further, in both themes.

### Below the threshold

One row per pair and theme. "Measured" counts the accents and skies the pair was measured under. Every single measurement is in `lint.json`.

| Pair | Kind | Theme | Measured | Lowest | Lowest at | Shown as | Needs | Result |
|---|---|---|---|---|---|---|---|---|
| `--hair` on page | non-text | day | 1 | 1.32 | - | `#ccd1e0` on `#edeff5` | 3:1 | **1 of 1 fail** |
| `--hair` on page | non-text | night | 1 | 1.41 | - | `#27305a` on `#0e1530` | 3:1 | **1 of 1 fail** |
| `--muted` at 0.55 opacity on page | text | day | 1 | 2.18 | - | `#9ea3b7` on `#edeff5` | 4.5:1 | **1 of 1 fail** |
| `--myelin` on sky-myelin-wash | text | day | 32 | 2.41 | emerald, storm sky | `#1f7a5a` on `#a1b2bf` | 4.5:1 | **32 of 32 fail** |
| `--muted` on sky-cresyl-wash | text | day | 8 | 2.59 | storm sky | `#5d6485` on `#a9acc5` | 4.5:1 | **8 of 8 fail** |
| `--muted` at 0.55 opacity on page | text | night | 1 | 2.86 | - | `#585f7c` on `#0e1530` | 4.5:1 | **1 of 1 fail** |
| `--muted` on sky | text | day | 8 | 2.89 | storm sky | `#5d6485` on `#aeb8c9` | 4.5:1 | **7 of 8 fail** |
| `--muted` on sky | non-text | day | 8 | 2.89 | storm sky | `#5d6485` on `#aeb8c9` | 3:1 | **1 of 8 fail** |
| `--muted` at 0.8 opacity on myelin-wash | text | day | 4 | 3.10 | rose | `#797d99` on `#e8dfe8` | 4.5:1 | **4 of 4 fail** |
| `--muted` at 0.8 opacity on page | text | day | 1 | 3.38 | - | `#7a809b` on `#edeff5` | 4.5:1 | **1 of 1 fail** |
| `--cresyl` on sky | text | day | 8 | 3.44 | storm sky | `#7b3f9e` on `#aeb8c9` | 4.5:1 | **2 of 8 fail** |
| `--ink` at 0.55 opacity on page | text | day | 1 | 3.49 | - | `#7a7e93` on `#edeff5` | 4.5:1 | **1 of 1 fail** |
| `--muted` at 0.8 opacity on myelin-wash | text | night | 4 | 4.04 | myelin | `#7b84a3` on `#152742` | 4.5:1 | **4 of 4 fail** |
| `--myelin` on myelin-wash | text | day | 4 | 4.06 | emerald | `#1f7a5a` on `#dae4e7` | 4.5:1 | **4 of 4 fail** |
| `--muted` on cresyl-wash | text | day | 1 | 4.35 | - | `#5d6485` on `#e2ddec` | 4.5:1 | **1 of 1 fail** |
| `--muted` on myelin-wash | text | day | 4 | 4.45 | rose | `#5d6485` on `#e8dfe8` | 4.5:1 | **3 of 4 fail** |

### Every pair

The lowest ratio for each pair in each theme, and where it occurs.

| Pair | Kind | Theme | Measured | Lowest | Lowest at | Shown as | Needs | Result |
|---|---|---|---|---|---|---|---|---|
| `--ink` on page | text | day | 1 | 13.60 | - | `#1b2142` on `#edeff5` | 4.5:1 | pass |
| `--ink` on page | text | night | 1 | 14.69 | - | `#e4e8f6` on `#0e1530` | 4.5:1 | pass |
| `--ink` on sky | text | day | 8 | 7.81 | storm sky | `#1b2142` on `#aeb8c9` | 4.5:1 | pass |
| `--ink` on sky | text | night | 8 | 13.63 | fog sky | `#e4e8f6` on `#161d34` | 4.5:1 | pass |
| `--ink` on myelin-wash | text | day | 4 | 12.02 | rose | `#1b2142` on `#e8dfe8` | 4.5:1 | pass |
| `--ink` on myelin-wash | text | night | 4 | 12.25 | myelin | `#e4e8f6` on `#152742` | 4.5:1 | pass |
| `--ink` on cresyl-wash | text | day | 1 | 11.75 | - | `#1b2142` on `#e2ddec` | 4.5:1 | pass |
| `--ink` on cresyl-wash | text | night | 1 | 11.97 | - | `#e4e8f6` on `#29234a` | 4.5:1 | pass |
| `--ink` on code | text | day | 1 | 12.65 | - | `#1b2142` on `#e5e7ee` | 4.5:1 | pass |
| `--ink` on code | text | night | 1 | 13.11 | - | `#e4e8f6` on `#19203a` | 4.5:1 | pass |
| `--ink` on sky-myelin-wash | text | day | 32 | 7.10 | rose, storm sky | `#1b2142` on `#aeadc0` | 4.5:1 | pass |
| `--ink` on sky-myelin-wash | text | night | 32 | 11.21 | myelin, fog sky | `#e4e8f6` on `#1d2e46` | 4.5:1 | pass |
| `--ink` on sky-cresyl-wash | text | day | 8 | 6.99 | storm sky | `#1b2142` on `#a9acc5` | 4.5:1 | pass |
| `--ink` on sky-cresyl-wash | text | night | 8 | 10.97 | fog sky | `#e4e8f6` on `#302a4d` | 4.5:1 | pass |
| `--muted` on page | text | day | 1 | 5.03 | - | `#5d6485` on `#edeff5` | 4.5:1 | pass |
| `--muted` on page | text | night | 1 | 6.55 | - | `#949bbb` on `#0e1530` | 4.5:1 | pass |
| `--muted` on sky | text | day | 8 | 2.89 | storm sky | `#5d6485` on `#aeb8c9` | 4.5:1 | **7 of 8 fail** |
| `--muted` on sky | text | night | 8 | 6.08 | fog sky | `#949bbb` on `#161d34` | 4.5:1 | pass |
| `--muted` on myelin-wash | text | day | 4 | 4.45 | rose | `#5d6485` on `#e8dfe8` | 4.5:1 | **3 of 4 fail** |
| `--muted` on myelin-wash | text | night | 4 | 5.47 | myelin | `#949bbb` on `#152742` | 4.5:1 | pass |
| `--muted` on cresyl-wash | text | day | 1 | 4.35 | - | `#5d6485` on `#e2ddec` | 4.5:1 | **1 of 1 fail** |
| `--muted` on cresyl-wash | text | night | 1 | 5.34 | - | `#949bbb` on `#29234a` | 4.5:1 | pass |
| `--muted` on sky-cresyl-wash | text | day | 8 | 2.59 | storm sky | `#5d6485` on `#a9acc5` | 4.5:1 | **8 of 8 fail** |
| `--muted` on sky-cresyl-wash | text | night | 8 | 4.90 | fog sky | `#949bbb` on `#302a4d` | 4.5:1 | pass |
| `--muted` at 0.8 opacity on page | text | day | 1 | 3.38 | - | `#7a809b` on `#edeff5` | 4.5:1 | **1 of 1 fail** |
| `--muted` at 0.8 opacity on page | text | night | 1 | 4.62 | - | `#79809f` on `#0e1530` | 4.5:1 | pass |
| `--muted` at 0.8 opacity on myelin-wash | text | day | 4 | 3.10 | rose | `#797d99` on `#e8dfe8` | 4.5:1 | **4 of 4 fail** |
| `--muted` at 0.8 opacity on myelin-wash | text | night | 4 | 4.04 | myelin | `#7b84a3` on `#152742` | 4.5:1 | **4 of 4 fail** |
| `--cresyl` on page | text | day | 1 | 5.99 | - | `#7b3f9e` on `#edeff5` | 4.5:1 | pass |
| `--cresyl` on page | text | night | 1 | 6.57 | - | `#d07be8` on `#0e1530` | 4.5:1 | pass |
| `--cresyl` on sky | text | day | 8 | 3.44 | storm sky | `#7b3f9e` on `#aeb8c9` | 4.5:1 | **2 of 8 fail** |
| `--cresyl` on sky | text | night | 8 | 6.09 | fog sky | `#d07be8` on `#161d34` | 4.5:1 | pass |
| `--cresyl` on myelin-wash | text | day | 4 | 5.30 | rose | `#7b3f9e` on `#e8dfe8` | 4.5:1 | pass |
| `--cresyl` on myelin-wash | text | night | 4 | 5.48 | myelin | `#d07be8` on `#152742` | 4.5:1 | pass |
| `--myelin` on page | text | day | 4 | 4.57 | emerald | `#1f7a5a` on `#edeff5` | 4.5:1 | pass |
| `--myelin` on page | text | night | 4 | 7.78 | rose | `#f28bb0` on `#0e1530` | 4.5:1 | pass |
| `--myelin` on myelin-wash | text | day | 4 | 4.06 | emerald | `#1f7a5a` on `#dae4e7` | 4.5:1 | **4 of 4 fail** |
| `--myelin` on myelin-wash | text | night | 4 | 6.67 | rose | `#f28bb0` on `#25213d` | 4.5:1 | pass |
| `--myelin` on sky-myelin-wash | text | day | 32 | 2.41 | emerald, storm sky | `#1f7a5a` on `#a1b2bf` | 4.5:1 | **32 of 32 fail** |
| `--myelin` on sky-myelin-wash | text | night | 32 | 6.12 | rose, fog sky | `#f28bb0` on `#2c2840` | 4.5:1 | pass |
| `--slide` on accent | text | day | 4 | 4.57 | emerald | `#edeff5` on `#1f7a5a` | 4.5:1 | pass |
| `--slide` on accent | text | night | 4 | 7.78 | rose | `#0e1530` on `#f28bb0` | 4.5:1 | pass |
| `--ink` at 0.55 opacity on page | text | day | 1 | 3.49 | - | `#7a7e93` on `#edeff5` | 4.5:1 | **1 of 1 fail** |
| `--ink` at 0.55 opacity on page | text | night | 1 | 5.17 | - | `#84899d` on `#0e1530` | 4.5:1 | pass |
| `--muted` at 0.55 opacity on page | text | day | 1 | 2.18 | - | `#9ea3b7` on `#edeff5` | 4.5:1 | **1 of 1 fail** |
| `--muted` at 0.55 opacity on page | text | night | 1 | 2.86 | - | `#585f7c` on `#0e1530` | 4.5:1 | **1 of 1 fail** |
| `--ink` at 0.55 opacity on page | inactive | day | 1 | 3.49 | - | `#7a7e93` on `#edeff5` | exempt | exempt |
| `--ink` at 0.55 opacity on page | inactive | night | 1 | 5.17 | - | `#84899d` on `#0e1530` | exempt | exempt |
| `--cresyl` on page | non-text | day | 1 | 5.99 | - | `#7b3f9e` on `#edeff5` | 3:1 | pass |
| `--cresyl` on page | non-text | night | 1 | 6.57 | - | `#d07be8` on `#0e1530` | 3:1 | pass |
| `--cresyl` on sky | non-text | day | 8 | 3.44 | storm sky | `#7b3f9e` on `#aeb8c9` | 3:1 | pass |
| `--cresyl` on sky | non-text | night | 8 | 6.09 | fog sky | `#d07be8` on `#161d34` | 3:1 | pass |
| `--cresyl` on myelin-wash | non-text | day | 4 | 5.30 | rose | `#7b3f9e` on `#e8dfe8` | 3:1 | pass |
| `--cresyl` on myelin-wash | non-text | night | 4 | 5.48 | myelin | `#d07be8` on `#152742` | 3:1 | pass |
| `--cresyl` on cresyl-wash | non-text | day | 1 | 5.18 | - | `#7b3f9e` on `#e2ddec` | 3:1 | pass |
| `--cresyl` on cresyl-wash | non-text | night | 1 | 5.35 | - | `#d07be8` on `#29234a` | 3:1 | pass |
| `--cresyl` on sky-cresyl-wash | non-text | day | 8 | 3.08 | storm sky | `#7b3f9e` on `#a9acc5` | 3:1 | pass |
| `--cresyl` on sky-cresyl-wash | non-text | night | 8 | 4.91 | fog sky | `#d07be8` on `#302a4d` | 3:1 | pass |
| `--muted` on page | non-text | day | 1 | 5.03 | - | `#5d6485` on `#edeff5` | 3:1 | pass |
| `--muted` on page | non-text | night | 1 | 6.55 | - | `#949bbb` on `#0e1530` | 3:1 | pass |
| `--muted` on sky | non-text | day | 8 | 2.89 | storm sky | `#5d6485` on `#aeb8c9` | 3:1 | **1 of 8 fail** |
| `--muted` on sky | non-text | night | 8 | 6.08 | fog sky | `#949bbb` on `#161d34` | 3:1 | pass |
| `--muted` on myelin-wash | non-text | day | 4 | 4.45 | rose | `#5d6485` on `#e8dfe8` | 3:1 | pass |
| `--muted` on myelin-wash | non-text | night | 4 | 5.47 | myelin | `#949bbb` on `#152742` | 3:1 | pass |
| `--ink` on page | non-text | day | 1 | 13.60 | - | `#1b2142` on `#edeff5` | 3:1 | pass |
| `--ink` on page | non-text | night | 1 | 14.69 | - | `#e4e8f6` on `#0e1530` | 3:1 | pass |
| `--ink` on cresyl-wash | non-text | day | 1 | 11.75 | - | `#1b2142` on `#e2ddec` | 3:1 | pass |
| `--ink` on cresyl-wash | non-text | night | 1 | 11.97 | - | `#e4e8f6` on `#29234a` | 3:1 | pass |
| `--ink` on sky-cresyl-wash | non-text | day | 8 | 6.99 | storm sky | `#1b2142` on `#a9acc5` | 3:1 | pass |
| `--ink` on sky-cresyl-wash | non-text | night | 8 | 10.97 | fog sky | `#e4e8f6` on `#302a4d` | 3:1 | pass |
| `--myelin` on page | non-text | day | 4 | 4.57 | emerald | `#1f7a5a` on `#edeff5` | 3:1 | pass |
| `--myelin` on page | non-text | night | 4 | 7.78 | rose | `#f28bb0` on `#0e1530` | 3:1 | pass |
| `--myelin` on track | non-text | day | 4 | 3.44 | emerald | `#1f7a5a` on `#ccd1e0` | 3:1 | pass |
| `--myelin` on track | non-text | night | 4 | 5.49 | rose | `#f28bb0` on `#27305a` | 3:1 | pass |
| `--myelin` on myelin-wash | non-text | day | 4 | 4.06 | emerald | `#1f7a5a` on `#dae4e7` | 3:1 | pass |
| `--myelin` on myelin-wash | non-text | night | 4 | 6.67 | rose | `#f28bb0` on `#25213d` | 3:1 | pass |
| `--slide` on accent | non-text | day | 4 | 4.57 | emerald | `#edeff5` on `#1f7a5a` | 3:1 | pass |
| `--slide` on accent | non-text | night | 4 | 7.78 | rose | `#0e1530` on `#f28bb0` | 3:1 | pass |
| `--hair` on page | non-text | day | 1 | 1.32 | - | `#ccd1e0` on `#edeff5` | 3:1 | **1 of 1 fail** |
| `--hair` on page | non-text | night | 1 | 1.41 | - | `#27305a` on `#0e1530` | 3:1 | **1 of 1 fail** |
| `--hair` on page | decorative | day | 1 | 1.32 | - | `#ccd1e0` on `#edeff5` | exempt | exempt |
| `--hair` on page | decorative | night | 1 | 1.41 | - | `#27305a` on `#0e1530` | exempt | exempt |
| `--hair` on myelin-wash | decorative | day | 4 | 1.17 | emerald | `#ccd1e0` on `#dae4e7` | exempt | exempt |
| `--hair` on myelin-wash | decorative | night | 4 | 1.18 | myelin | `#27305a` on `#152742` | exempt | exempt |
| `--myelin` on sky | decorative | day | 32 | 2.63 | emerald, storm sky | `#1f7a5a` on `#aeb8c9` | exempt | exempt |
| `--myelin` on sky | decorative | night | 32 | 7.22 | rose, fog sky | `#f28bb0` on `#161d34` | exempt | exempt |
| `--myelin` on cresyl-wash | decorative | day | 4 | 3.95 | emerald | `#1f7a5a` on `#e2ddec` | exempt | exempt |
| `--myelin` on cresyl-wash | decorative | night | 4 | 6.34 | rose | `#f28bb0` on `#29234a` | exempt | exempt |
| `--myelin` on sky-cresyl-wash | decorative | day | 32 | 2.35 | emerald, storm sky | `#1f7a5a` on `#a9acc5` | exempt | exempt |
| `--myelin` on sky-cresyl-wash | decorative | night | 32 | 5.81 | rose, fog sky | `#f28bb0` on `#302a4d` | exempt | exempt |
| `--axon-ahead` on page | decorative | day | 1 | 1.45 | - | `#c2c8da` on `#edeff5` | exempt | exempt |
| `--axon-ahead` on page | decorative | night | 1 | 1.51 | - | `#2b3462` on `#0e1530` | exempt | exempt |

### Where each pair occurs

- `--ink` (text) on page, sky, myelin-wash, cresyl-wash, code, sky-myelin-wash, sky-cresyl-wash: Body text. On the sky: the clock and date. On washes: .focus-badge (in the header), .quick-log, .sql-q:hover, .chip.is-on. On code: .sql-editor, .solution pre, .phone-link code.
- `--muted` (text) on page, sky, myelin-wash, cresyl-wash, sky-cresyl-wash: Secondary text (.hint, .tool-sub, .plan-detail). On the sky: .clock-period, .hijri, .tab, .next-at, .weather-line. On washes: labels in .quick-log, .sql-q.is-free:hover, .btn.quiet in .focus-badge.is-up.
- `--muted` at 0.8 opacity (text) on page, myelin-wash: .input::placeholder (opacity 0.8), on the page and inside .quick-log.
- `--cresyl` (text) on page, sky, myelin-wash: What is next: .prayer.is-next, .axon-today, .form-error, td.is-due. On the sky: .next-line, .interview-next, .setup-link. On myelin-wash: .form-error inside .quick-log.
- `--myelin` (text) on page, myelin-wash, sky-myelin-wash: Accent text: .verdict.is-correct, .busy-label, the first plan action. On myelin-wash: .focus-badge-time (in the header, so also over the sky).
- `--slide` (text) on accent: Text on a solid accent fill: .btn.primary, .segmented button[aria-checked=true].
- `--ink` at 0.55 opacity (text) on page: Days before the start date in the Week view: .week-day.is-before (opacity 0.55) .week-day-name, .week-block-title.
- `--muted` at 0.55 opacity (text) on page: Days before the start date in the Week view: .week-day.is-before (opacity 0.55) .week-day-date, .week-block-detail.
- `--ink` at 0.55 opacity (inactive) on page: .btn:disabled (opacity 0.55). Disabled controls are exempt from SC 1.4.3.
- `--cresyl` (non-text) on page, sky, myelin-wash, cresyl-wash, sky-cresyl-wash: The global :focus-visible outline, and the 'next' and 'today' markers (.is-next .check, .chip.is-on, .sheath-today). On the sky: focus on the tabs and theme toggle.
- `--muted` (non-text) on page, sky, myelin-wash: Control boundaries: .check, .input, .sql-q-mark. On the sky: the theme toggle icon. On myelin-wash: inputs inside .quick-log.
- `--ink` (non-text) on page, cresyl-wash, sky-cresyl-wash: The .btn border, and the selected .swatch border. On cresyl-wash: buttons inside .focus-badge.is-up.
- `--myelin` (non-text) on page, track, myelin-wash: Done states: the fill of .is-done .check, .sheath, .sql-q.is-solved .sql-q-mark (on myelin-wash when the row is hovered or selected). On track: the progress fill in .focus-sheath and .pattern-bar.
- `--slide` (non-text) on accent: The tick inside a done .check.
- `--hair` (non-text) on page: Borders that are the only edge of a text field: .command-input, .sql-editor. Also the 'missed day' fill in the heatmap (.heat.is-missed).
- `--hair` (decorative) on page, myelin-wash: Row separators, and borders around controls that already have a text label (.segmented, .swatch, .chip).
- `--myelin` (decorative) on sky, cresyl-wash, sky-cresyl-wash: Accent shapes that repeat what text already says: the bar under the selected tab (the tab is also bold), and the fill of .btn.primary (which has a text label) inside a wash.
- `--axon-ahead` (decorative) on page: The part of the axon not yet walked (.axon-line.ahead, .week-segment::before).

## Focus states

Global rule: `:focus-visible { outline: 3px solid var(--cresyl) }` at `frontend/src/styles.css:121`.

No rule or inline style removes the focus outline.
