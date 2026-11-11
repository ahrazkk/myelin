# Myelin design system tooling

Myelin's interface is built on ten colour tokens (CSS custom properties) with day and night themes
and four accents. This folder turns that into something a machine can read and check:

1. **A token contract.** `tokens.json`, exported from the stylesheet and checked against a JSON Schema.
2. **CI quality gates.** A token drift check, and linters for WCAG 2.1 AA contrast, token compliance
   and focus states.
3. **An MCP server.** The tokens and the checks, offered to AI agents as four read-only tools, so
   generated UI code can be grounded in the design system and checked against it.
4. **An evaluation harness.** Measures whether that grounding makes a model's UI code better:
   compile rate, token compliance, contrast and focus, with and without the server.

It is tooling beside the app. It reads `frontend/src`; it does not change how Myelin looks or behaves.

- [`NOTES.md`](NOTES.md) explains the idea behind each piece.
- [`RESULTS.md`](RESULTS.md) has what the linters found.
- [`reports/lint.md`](reports/lint.md) is the current lint report.

## Set up

Python 3.11 or newer.

```bash
cd design
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

`[dev]` includes the MCP SDK. For the linters alone, `pip install -e .` is enough.

## Commands

| Command | What it does | Exit code 1 when |
| --- | --- | --- |
| `python -m myelin_design export` | Writes `tokens.json` from `frontend/src/styles.css` | The CSS has a problem (see below) |
| `python -m myelin_design export --check` | **Token drift gate.** Writes nothing | `tokens.json` does not match the CSS |
| `python -m myelin_design lint` | Runs the three linters and prints a summary | Any finding is not fixed or allowed |
| `python -m myelin_design lint --write` | Also writes `reports/lint.md` and `reports/lint.json` | Same |
| `python -m myelin_design lint --check` | Also checks the committed reports are current | Same, or the reports are out of date |
| `python -m myelin_design serve` | Starts the MCP server over stdio | |
| `python -m myelin_design serve --http` | Starts it on `http://127.0.0.1:8000/mcp` | |

## 1. The token contract

`export` reads every custom property on `:root` and writes one entry per token:

```json
{
  "name": "myelin",
  "cssVariable": "--myelin",
  "role": "accent",
  "description": "Main accent: done states, the selected tab, the primary button. Follows the accent setting.",
  "values": {
    "day":   { "css": "#2d6bad", "hex": "#2d6bad", "alpha": 1.0 },
    "night": { "css": "#57c4e5", "hex": "#57c4e5", "alpha": 1.0 }
  },
  "accents": { "emerald": { "day": { "...": "..." }, "night": { "...": "..." } } }
}
```

The export fails, and says why, if:

- the two night declarations disagree (`[data-theme="night"]` and `@media (prefers-color-scheme: dark)`);
- a token has a day value but no night value, or the other way round;
- a token has no role in [`design.toml`](design.toml), or a role describes a token that is gone;
- a `:root` rule has a shape the exporter does not recognise, or a token is not a colour;
- the result does not match [`tokens.schema.json`](tokens.schema.json).

Roles and descriptions are the one part written by hand. They live in `design.toml`.

## 2. The linters

**Contrast.** WCAG 2.1 relative luminance and contrast ratio, implemented in
[`color.py`](myelin_design/color.py) and tested against published values. Pairs (a foreground token
on a surface) are declared in `design.toml`. Each is measured in both themes, under every accent it
depends on, with translucent layers composited first. Text needs 4.5:1; control boundaries, states
and the focus outline need 3:1. The report lists every pair, not only the failures.

Surfaces named `sky` are measured against the sky the app paints behind the page when Background is
not Plain. Those colours are read from `Ambient.tsx` directly.

**Token compliance.** Scans `frontend/src/**/*.css`, `*.ts` and `*.tsx` for hard-coded colours.
Compliance is token uses divided by all colour uses. A literal that equals a token's value is reported
as a copy of that token. `var(--name)` with an unknown name is always an error.

**Focus.** Fails on `outline: none` or `outline: 0` with no replacement in the same rule, in CSS or
in an inline style, and requires a global `:focus-visible` rule that draws an outline.

### Exceptions

Both kinds need a written reason, and both are checked for staleness: an allowlist entry that matches
nothing, or a known failure that now passes, fails the build until it is removed.

```toml
[[compliance.allow]]
file = "frontend/src/tools.css"
match = "rgb(0 0 0 / 0.12)"          # the exact text, or "*" for the whole file
reason = "Why this colour is not a token."

[[contrast.pair]]
foreground = "muted"
on = ["page"]
kind = "text"
opacity = 0.8
where = ".input::placeholder"
known_failure = "Why this is accepted for now."
```

Allowed colours still count as hard-coded in the compliance percentage.

## 3. The MCP server

| Tool | Returns |
| --- | --- |
| `get_design_tokens(theme?, accent?)` | Every token: name, CSS variable, role, description, values. Narrow by theme or accent. |
| `check_contrast(foreground, background, theme?, accent?)` | The contrast ratio and AA pass or fail for text, large text and non-text. Takes token names (`ink`, `--ink`, `var(--ink)`) or CSS colours. |
| `lint_snippet(code, language)` | Findings for a CSS, TS or TSX snippet: hard-coded colours (with the token to use), unknown tokens, removed focus outlines, low-contrast pairs in CSS; plus a compliance percentage. |
| `get_guidelines()` | The UI rules in [`guidelines.md`](guidelines.md), and every declared colour pair with its measured contrast. |

All four are read-only and annotated as such. Each publishes an output schema. `lint_snippet` scans
its input as text: nothing is executed, imported or written. Input is limited to 200,000 characters.

### Register it with an MCP host

The server is `python -m myelin_design serve`, run with the Python from the virtual environment
above. Use the absolute path to that Python, so the host does not depend on its working directory.

**Claude Code**

```bash
claude mcp add myelin-design -- /absolute/path/to/myelin/design/.venv/bin/python -m myelin_design serve
```

On Windows the Python is `...\design\.venv\Scripts\python.exe`. Then run `/mcp` in a session to see
the four tools.

**VS Code with GitHub Copilot** (agent mode). Create `.vscode/mcp.json`:

```json
{
  "servers": {
    "myelin-design": {
      "type": "stdio",
      "command": "${workspaceFolder}/design/.venv/bin/python",
      "args": ["-m", "myelin_design", "serve"]
    }
  }
}
```

**Over HTTP.** `python -m myelin_design serve --http` listens on `127.0.0.1:8000`, this machine only.
There is no authentication, so do not pass `--host 0.0.0.0` on a network you do not trust.

### What has been verified

- In CI: every tool called through the SDK's MCP client, in memory and over stdio in a separate
  process, returns exactly what the Python function returns, and matches its published schema.
- By hand, once: the HTTP transport, with the SDK client.
- Not yet: registration in Claude Code or VS Code. The commands above follow each host's documentation.

## 4. The evaluation

Does grounding a model in the design system make the UI code it writes better? The harness gives
the same 18 component requests ([`eval/tasks.json`](eval/tasks.json)) to a model under three conditions:

| Condition | What the model gets |
| --- | --- |
| `baseline` | The request and a one-line description of the app |
| `context` | The same, plus the tokens and guidelines pasted into the prompt. No tools |
| `mcp` | The same as baseline, plus the four MCP tools |

Each output is scored automatically: does it compile under the frontend's strict TypeScript settings,
what share of its colours are tokens, do its text and background pairs pass 4.5:1, and does it remove
a focus outline. Latency and cost are recorded per task. Each task runs three times per condition.

```bash
pip install -e ".[eval]"                         # adds the Anthropic SDK
python -m myelin_design eval estimate            # rough cost; calls no model
python -m myelin_design eval run --name haiku --max-cost 2.00    # needs ANTHROPIC_API_KEY; costs money
python -m myelin_design eval score --name haiku  # recompute scores from saved transcripts; free
```

`eval run` will not start without `--max-cost`. Every model call is saved under
`eval/runs/<name>/transcripts`, so `eval score` can recompute the numbers without calling the model
again. The model's code is type-checked and scanned as text; it is never executed. The compile check
needs Node and `npm ci` in `frontend/`.

**Status: built and tested with a scripted fake model. Not yet run against a real model.**

## In CI

The `design` job in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on Ubuntu and
Windows: the drift gate, the linters, then the tests. The tests include the MCP contract tests and
the evaluation scorer, which type-checks sample components with the frontend's TypeScript. CI never
calls a model.

## Layout

| Path | What it is |
| --- | --- |
| `design.toml` | Token roles, contrast pairs and allowed exceptions. The hand-written part. |
| `tokens.json`, `tokens.schema.json` | The contract and its schema. `tokens.json` is generated. |
| `guidelines.md` | The UI rules the server hands to agents. |
| `reports/` | `lint.md` and `lint.json` (current), `baseline.*` (the first run, before any fix). |
| `myelin_design/css.py` | A small CSS reader: rules, selectors, declarations, line numbers. |
| `myelin_design/color.py` | Colour parsing, luminance, contrast ratio, alpha compositing. |
| `myelin_design/tokens.py` | The exporter and the drift checks. |
| `myelin_design/contrast.py`, `compliance.py`, `focus.py` | The three linters. |
| `myelin_design/lint.py`, `report.py` | Run the linters; render the report. |
| `myelin_design/api.py`, `server.py` | The four tools as functions; the MCP wrapper. |
| `myelin_design/evaluation.py` | The evaluation: run, record, score, summarise. |
| `eval/tasks.json` | The 18 component requests, fixed before any model was run. |
| `tests/` | Unit tests, lint tests on a throwaway repo, and the MCP contract tests. |
