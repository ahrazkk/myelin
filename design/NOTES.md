# Notes for Ahraz

Written for you, not for a reviewer. What each piece does, the one idea behind it, and the decisions
that could have gone another way. Reread this the night before an interview.

All entries: 10 November 2026.

---

## The big picture

Myelin already had a small design system: ten colour tokens in `frontend/src/styles.css`, with day
and night values and four accents. What it did not have was anything that *checks* the system, or
anything that lets an AI agent *use* it. This folder adds three layers, each built on the one before:

1. **A contract.** `tokens.json` is the tokens as data, with a schema. A machine can read it.
2. **Gates.** Linters that run in CI and fail the build when the code breaks the system.
3. **An MCP server.** The contract and the checks, offered to AI agents as tools.

The reason for the order: an agent can only stay "on system" if the system is written down in a form
it can query (layer 1) and if there is an automatic way to tell whether its output obeys (layer 2).

---

## Phase 1: the token export

### What it does

`python -m myelin_design export` reads `styles.css`, finds every custom property on `:root`, and
writes `design/tokens.json`. `export --check` does the same work but writes nothing: it compares the
result with the committed file and exits 1 if they differ. That check is the **token drift gate**.

### The one idea: generated files need a "is this still true?" check

`tokens.json` is derived from the CSS. Any derived file can go stale: someone edits the CSS and
forgets to regenerate. The fix is not discipline, it is a check. CI regenerates the file in memory and
fails if it does not match what is committed. For this to work the output has to be **deterministic**:
same input, byte-for-byte the same file. So there is no timestamp and no commit hash in it.

### Why night is declared twice, and why that matters

CSS cannot say "apply this when the attribute is set OR when the system is dark" in one rule. So the
night values exist twice: once under `:root[data-theme="night"]`, once inside
`@media (prefers-color-scheme: dark)`. Two copies of one fact will eventually disagree. The exporter
reads both and fails with a "night drift" message naming the token and both line numbers. It compares
the *colours*, not the text, so `#000` and `#000000` are not drift.

### Roles come from a human

The CSS says `--muted: #5d6485`. It does not say what muted is *for*. That lives in `design.toml`
(role and description for each token). The export fails if a token in the CSS has no role, or if a
role describes a token that no longer exists. So nobody can add a token without deciding what it is.

**For you to confirm:** the roles are my proposal. Read the `[tokens.*]` entries in `design.toml`.
The judgment calls: `--axon-ahead` as `border` (it is a decorative line; there is no "track" role),
and `--code-bg` as `wash` (it is translucent, like the other washes).

### The CSS parser is hand-written (about 150 lines)

**Why not a library?** Three reasons. You can explain every line. It has no dependency. And it is a
single pass with no recursion and no regular expressions, so its running time is proportional to the
input. That last one matters in Phase 3, where the same parser runs on text from an AI agent.

**What it does not do:** resolve the cascade, or validate CSS. It finds rules, selectors,
declarations and line numbers. That is all the linters need.

**Decision that could have gone the other way:** `tinycss2` is a real, spec-following tokenizer and
would be the right call for arbitrary third-party CSS. For two stylesheets we control, a small reader
we fully understand is the better trade.

### Fail loudly on anything unrecognised

If a `:root` rule shows up in a shape the exporter was not taught (say `:root[data-theme="sepia"]`),
it raises an error instead of skipping it. A skipped rule would mean a token silently missing from the
contract. All problems are collected and reported together, not one per run.

---

## Phase 2: the linters

### Contrast: three ideas

**1. Relative luminance.** Screens store colour on a curve (gamma), so `#808080` is not half as bright
as white. WCAG first undoes the curve for each channel:

    c = channel / 255
    linear = c / 12.92                      if c <= 0.03928
             ((c + 0.055) / 1.055) ** 2.4   otherwise

then weights the channels by how bright the eye finds them: `L = 0.2126 R + 0.7152 G + 0.0722 B`.
Green counts most, blue least. (The 0.03928 is WCAG 2.1's number. The sRGB standard says 0.04045. No
8-bit value falls between them, so results are identical.)

**2. Contrast ratio.** `(lighter + 0.05) / (darker + 0.05)`. From 1:1 to 21:1. The 0.05 models light
reflecting off the screen, and stops a division by zero for black.

**3. Alpha compositing.** `--cresyl-wash` is `rgb(123 63 158 / 0.1)`: 10% violet. It has no contrast
of its own, because what you see depends on what is underneath. So the linter blends it over the page
first, channel by channel: `shown = top * alpha + bottom * (1 - alpha)`. Only then does it measure.
**This is the interview question to expect**: "why composite before measuring?" Because luminance is
defined for the colour the screen shows, and a translucent colour is not that colour yet.

Two details worth knowing:

- The result is rounded to whole 0 to 255 steps, like a real pixel, before measuring.
- Ratios are **cut, not rounded**, for display: 4.497 prints as 4.49, never 4.50. WCAG thresholds are
  not rounded, so a printed "4.50" next to a "fail" would be a lie. The pass or fail decision always
  uses the full number.

### Contrast: the pairs are declared by hand, and that is deliberate

A stylesheet does not tell you what text sits on what background. That depends on how elements nest
in the page. A linter that guessed would be wrong in both directions. So `design.toml` lists each
pair (a foreground token on a surface), with a note saying where it occurs in the app.

Two things keep that hand-made list honest:

- **Undeclared-pair check.** When a CSS rule sets a text colour (and maybe a background in the same
  rule), the linter can see that pair on its own. If it is not declared, the build fails.
- **Known failures go stale.** A pair can be marked `known_failure = "reason"` so it does not fail CI.
  But if it later passes, the linter fails until the mark is removed. No permanent excuses.

### Contrast: kinds

| Kind | Threshold | WCAG |
|---|---|---|
| `text` | 4.5:1 | 1.4.3 |
| `large-text` | 3:1 | 1.4.3 (24px, or 18.66px bold) |
| `non-text` | 3:1 | 1.4.11 (control boundaries, states, focus rings) |
| `decorative`, `inactive` | none | measured and reported, never fail |

**Judgment call to be ready for:** 1.4.11 only applies where the graphic is *required* to identify a
control or its state. A border around a button that has a text label is not required. So `--hair`
around `.segmented` is `decorative`, but `--hair` as the only edge of a text field is `non-text`.
I classed the bar under the selected tab as decorative because the selected tab is also bold.
An auditor could argue some of these the other way. The `where` notes say what I decided and why.

### Contrast: the sky (the finding I did not expect)

The brief measured everything against `--slide`, the page background. But by default (Background =
Live weather) the app paints a sky on a canvas behind the page, and the header sits on it. The sky's
top colours are sixteen hard-coded RGB values in `Ambient.tsx` (`SKY_DAY`, `SKY_NIGHT`).

So the linter has surfaces called `sky`. It reads those sixteen colours **straight out of the
TypeScript source** rather than copying them into config, because a copy could drift.

**What it measures:** the colour at the very top of the sky gradient. The gradient is behind the
*whole page*, not only the header: sky colour at the top, 85% of the way to `--slide` two thirds
down, `--slide` at the bottom. So over the gradient a pair's real value lies between its `sky` number
and its `page` number, depending on how high up it sits.

**What it does not measure, and you must say so:** only header pairs are declared on the sky, so
content lower down is measured on `--slide` as if Background were Plain. And the clouds, mist, sun,
moon, rain and cursor glow drawn *over* the gradient are not modelled at all. A pass on `sky` means
"passes against the gradient", not "passes against everything the canvas paints".

**Why this matters for your resume:** the old line said every text colour has 4.5:1 "on the page
background". That is still true. But it is not the whole truth about the default look of the app.

### Token compliance

**The number:** token uses divided by all colour uses. `var(--ink)` is a token use. `#1b2142` is a
hard-coded colour. Token *definitions* (the `:root` block) are neither.

**In CSS** the scanner walks each declaration's value. **In TS and TSX** there is no CSS to parse, so
it first separates code from string literals (dropping comments), then looks for colours inside the
strings. Template literals nest (`` `a ${`b`} c` ``), so that splitter keeps a stack.

Things it does on purpose:

- **"Copy of a token."** A literal that has exactly a token's value is reported with the token's name
  (`#2d6bad` is `--myelin (day)`). That is the real drift risk: change the token and the copy is wrong.
- **Unknown tokens.** `var(--inc)` is flagged. It is almost always a typo, and CSS fails silently on it.
- **Computed colours are not literals.** `` `rgba(${r},${g},${b},0.5)` `` gets its colour from code.
- **Named colours only where a colour goes.** `color: white` yes; `font-family: Tan` no. In TSX, only
  in a colour slot such as `fillStyle = "white"`.
- **Allowed exceptions still count as hard-coded.** The allowlist stops CI failing. It does not
  improve the percentage. Otherwise the number could be gamed by allowlisting everything.

**Its honest limit:** a bare `[196, 218, 243]` in TypeScript is probably a colour, but the scanner
cannot tell it from any other three numbers, so it only flags a triple when it equals a token. The
report prints how many such triples it skipped and what the percentage would be if they all counted.

### Focus

Two checks: no rule removes the outline without a replacement in the same rule, and a global
`:focus-visible` rule that draws an outline must exist. Declarations are read in order, because a
later one in the same rule wins (`outline: none; outline: 2px solid` is fine).

**Its honest limit:** it reads source text. It cannot prove a control is reachable by keyboard.

---

## Phase 3: the MCP server

### What MCP is, in one paragraph

Model Context Protocol is a standard way for an AI application (the "host": Claude Code, VS Code with
Copilot) to call tools that live in another process (the "server"). The server lists its tools, each
with a name, a description, an input schema and optionally an output schema. The model reads the
descriptions and decides when to call. Messages are JSON-RPC, over stdio or HTTP.

### The four tools

| Tool | What it gives an agent |
|---|---|
| `get_design_tokens(theme?, accent?)` | The contract: every token, role, description and value. |
| `check_contrast(foreground, background, theme?, accent?)` | A measured ratio and AA pass or fail, for tokens or raw colours. |
| `lint_snippet(code, language)` | Findings with line numbers and a suggestion for each, plus a compliance %. |
| `get_guidelines()` | The written rules, and every declared pair with its measured contrast. |

### Design: the server is a thin wrapper

All the logic is in `api.py`, as plain functions that take a project and return a dict. `server.py`
only adds what MCP needs: names, descriptions, annotations, and turning a bad argument into an error
message the agent can read. That split is what makes the contract test possible.

### What the contract test proves (and what it does not)

For every tool, the test calls it through a real MCP client and compares the result with calling the
function directly. It also validates each result against the output schema the tool publishes, checks
every tool is annotated read-only, and runs once over stdio in a separate process.

**It proves:** the wrapper adds and loses nothing; the published schema matches the real data; the
server starts and answers the way a real host would launch it.

**It does not prove:** that the functions are *right* (that is what the other 170 tests are for), or
that a model will choose to call the tools.

### Tool annotations

`read_only_hint=True` tells the host the tool changes nothing, so it can be called without asking the
user. `idempotent_hint=True`: calling twice equals calling once. `open_world_hint=False`: it only
looks at this repo, not the network. **They are hints, not security.** A host should not trust them
from an unknown server. What actually makes these tools safe is that the code only reads.

### Output schemas

The functions' return types are TypedDicts. The SDK turns each into a JSON Schema and publishes it as
the tool's `outputSchema`, and it validates every result against it. So the shape of each answer is
part of the contract, and a change that breaks the shape fails a test.

### Untrusted input

`lint_snippet` gets code written by a model. It is treated as text: scanned, never executed,
imported or written to disk. Input is capped at 200,000 characters. The scanners are single-pass.

### The SDK changed

You built TriageBench on the v1 SDK. This uses **v2.3.0** (October 2026), and v2 broke things:

| v1 (what you used) | v2 (what this uses) |
|---|---|
| `from mcp.server.fastmcp import FastMCP` | `from mcp.server import MCPServer` |
| `create_connected_server_and_client_session` | `async with Client(server) as client:` |
| `result.structuredContent`, `tool.inputSchema` | `result.structured_content`, `tool.input_schema` |
| `ToolAnnotations(readOnlyHint=True)` | `ToolAnnotations(read_only_hint=True)` |
| transport options on the constructor | on `run("streamable-http", port=...)` |

The JSON on the wire is unchanged (still camelCase). Only the Python names moved. I checked each of
these against the installed package, not from memory.

### Decisions that could have gone another way

- **`mcp` is an optional extra.** The linters install and run without it. Only `serve` needs it.
- **`get_guidelines` runs the contrast linter live** rather than reading a saved report, so its pair
  table can never be stale. The cost is a few milliseconds per call.
- **Errors.** A bad argument raises `ValueError` in the function, and the server turns that into a
  `ToolError`. In SDK v2 only `ToolError` messages reach the model; anything else reads
  "Error executing tool", so internals do not leak.

---

## Phase 4: the evaluation harness (built and tested; not yet run against a model)

### The question

Does grounding a model in the design system make the UI code it writes better, and by how much?

### The design: three conditions, not two

| Condition | What the model gets |
|---|---|
| `baseline` | The request and a one-line description of the app. |
| `context` | The same, plus the tokens and guidelines pasted into the prompt as text. No tools. |
| `mcp` | The same as baseline, plus the four MCP tools and the server's own instructions. |

The brief asked for two (baseline and mcp). I added `context` because it answers the first question
an interviewer will ask: **"couldn't you just paste the tokens into the prompt?"** An MCP server gives
a model two different things: *information*, which a prompt can also carry, and *tools to check its
own work*, which a prompt cannot. Comparing `mcp` with `context` separates the two. If `context` does
as well as `mcp`, the honest finding is that the information mattered and the tools did not. You can
drop it with `--conditions baseline,mcp`.

### Why at least three runs per task

A model does not give the same answer twice. One run per task measures the model plus luck. With three
runs you can report a mean and a range, and see whether the gap between conditions is bigger than the
run-to-run wobble. If it is not, there is no result.

### Why paired

Some tasks are harder than others (a confirm dialog versus a badge). If you just compare the two
averages, a hard task drags both down and adds noise. In a paired comparison each task is compared
with *itself* under the other condition, so task difficulty cancels out. The summary reports, per
metric: the mean difference, how many tasks went up, stayed the same and went down, and a sign test.

**The sign test** asks: if neither condition were better, how likely is a split this lopsided? It
only uses the direction of each difference, not its size, so it makes no assumption about the
distribution. With 18 tasks it can only detect large, consistent effects. That is a limit to state,
not to hide.

### Metrics, all automatic

| Metric | How it is measured |
|---|---|
| Compile rate | `tsc --noEmit` under the frontend's own strict tsconfig. All outputs in one tsc run, errors attributed by folder. |
| Token compliance | The same scanner CI uses, on the TSX and the CSS together. |
| Contrast pass rate | Of the CSS rules that set both a text colour and a background, the share at 4.5:1 or better. |
| Focus findings | The same focus linter CI uses. |
| Latency, cost | Wall-clock seconds and dollars per task, from the API's own token counts. |

A reply with no component in it counts as **not compiling**. A reply with no colours has **no**
compliance figure (not 0%, not 100%), and the summary says how many such runs there were.

### Record and replay

Every run is saved as a transcript: the full message list, token usage and timing. `eval score`
recomputes every metric from the transcripts and calls no model. So the numbers can be reproduced,
and a scoring bug can be fixed, without paying again. A run that stops half way can be continued: a
transcript that already exists is not run again.

### Safety

- `eval run` refuses to start without `--max-cost`, and stops starting new runs once that is spent.
- The model's code is never executed. It is type-checked with `--noEmit` and scanned as text.
- The tasks were written down before any model was run (`eval/tasks.json`), and each run folder keeps
  a copy of the exact tasks it used.

### What the evaluation will not show (say these before you are asked)

- **Small task set.** 18 tasks, written by the same person who built the tools.
- **The metrics are the tool's own checks.** The `mcp` condition lets the model run the very linter
  that scores it. A model that learns to satisfy the linter will score well. That is the point of the
  tool, but it also means compliance in `mcp` is partly "did it run the linter and listen".
- **No measure of quality.** Nothing checks whether a component looks right, reads well, or is usable.
  A component can compile, use only tokens, and still be bad.
- **One model, one day.** Results are for the model and version named in the results, on that date.
- **Baseline is at a known disadvantage.** It is never told the token names, so it cannot use them.
  The baseline-versus-mcp gap in token compliance mostly measures "was it told", which is why the
  `context` condition exists.
