"""The evaluation: does grounding a model in the design system make the UI code it writes better?

The same component requests are given to a model under different conditions:

    baseline   the request and a one-line description of the app. Nothing else.
    context    the same, plus the tokens and guidelines pasted into the prompt as text. No tools.
    mcp        the same as baseline, plus the four MCP tools (and the server's own instructions).

"context" is there to separate two things an MCP server gives a model: information (which the
prompt could also carry) and tools it can call to check its own work (which the prompt cannot).

Every output is scored by machine, with the same linters CI uses:

    compile rate        does it pass tsc --noEmit under the frontend's strict settings?
    token compliance    token uses divided by all colour uses
    contrast            of the text/background pairs its CSS sets, how many pass 4.5:1?
    focus               how many times does it remove the focus outline?
    latency and cost    wall-clock seconds and dollars per task

Model output varies between runs, so each task runs several times per condition. Every model call
is saved to disk, so scores can be recomputed later without calling the model (or paying) again.

Nothing the model writes is executed. It is type-checked and scanned as text.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from . import api
from .project import Project, read_text, write_text

CONDITIONS = ("baseline", "context", "mcp")
MAX_TURNS = 12  # a run that is still calling tools after this many model calls is stopped
MAX_OUTPUT_TOKENS = 16_000

# US dollars per million tokens (input, output), from the Anthropic price list on 3 November 2026.
# Cache writes cost 1.25 times the input price and cache reads 0.1 times.
PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}

_FENCE = re.compile(r"```[ \t]*([A-Za-z]*)[^\n]*\n(.*?)```", re.DOTALL)
_TSC_ERROR = re.compile(r"^(?P<path>[^(\n]+)\((?P<line>\d+),(?P<column>\d+)\): error (?P<code>TS\d+): (?P<message>.*)$")
_TSX_LABELS = ("tsx", "typescript", "ts", "jsx")


class Model(Protocol):
    """The one thing the harness needs from a model: send a request, get the response as a dict."""

    async def create(self, **params: Any) -> dict[str, Any]: ...


class AnthropicModel:
    """The real thing. Imported lazily so that scoring saved runs does not need the SDK or a key."""

    def __init__(self) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic()

    async def create(self, **params: Any) -> dict[str, Any]:
        message = await self._client.messages.create(**params)
        return message.to_dict()


@dataclass(frozen=True)
class Task:
    id: str
    name: str
    request: str


def load_tasks(path: Path) -> tuple[str, list[Task]]:
    """The one-line app description and the tasks, with each request filled into the template."""
    data = json.loads(read_text(path))
    tasks = [
        Task(entry["id"], entry["name"], data["request_template"].format(request=entry["request"], name=entry["name"]))
        for entry in data["tasks"]
    ]
    return data["app"], tasks


# ---- Running ----


def system_prompt(app: str, condition: str, project: Project, server_instructions: str = "") -> str:
    base = f"You are a senior front-end engineer. {app}"
    if condition == "context":
        tokens = api.get_design_tokens(project)
        guidelines = read_text(project.design_dir / "guidelines.md")
        return (
            f"{base}\n\nMyelin's UI guidelines:\n\n{guidelines}\n\n"
            f"Myelin's design tokens, as JSON:\n\n{json.dumps(tokens, indent=1)}"
        )
    if condition == "mcp" and server_instructions:
        return f"{base}\n\n{server_instructions}"
    return base


def _tool_result_text(result: Any) -> str:
    if result.structured_content is not None:
        return json.dumps(result.structured_content)
    return "\n".join(getattr(block, "text", "") for block in result.content)


def cost_of(model: str, usage: dict[str, Any]) -> float | None:
    """What one response cost, in dollars, or None for a model with no listed price."""
    if model not in PRICES:
        return None
    input_price, output_price = PRICES[model]
    tokens_in = (
        (usage.get("input_tokens") or 0)
        + 1.25 * (usage.get("cache_creation_input_tokens") or 0)
        + 0.1 * (usage.get("cache_read_input_tokens") or 0)
    )
    return (tokens_in * input_price + (usage.get("output_tokens") or 0) * output_price) / 1_000_000


async def run_once(
    model: Model, model_name: str, project: Project, app: str, task: Task, condition: str, repetition: int
) -> dict[str, Any]:
    """Give one task to the model under one condition and return everything that happened."""
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}; use one of {', '.join(CONDITIONS)}")

    transcript: dict[str, Any] = {
        "task": task.id,
        "name": task.name,
        "condition": condition,
        "repetition": repetition,
        "model": model_name,
        "calls": [],
        "tool_calls": [],
        "stop_reason": None,
        "final_text": "",
    }
    messages: list[dict[str, Any]] = [{"role": "user", "content": task.request}]

    async def converse(tools: list[dict[str, Any]], system: str, call_tool: Any) -> None:
        for _ in range(MAX_TURNS):
            params: dict[str, Any] = {
                "model": model_name,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "system": system,
                "messages": messages,
            }
            if tools:
                params["tools"] = tools
            started = time.perf_counter()
            response = await model.create(**params)
            seconds = time.perf_counter() - started
            # The reply itself is kept once, in the message list saved at the end.
            transcript["calls"].append(
                {"seconds": round(seconds, 3), "stop_reason": response.get("stop_reason"), "usage": response.get("usage") or {}}
            )
            transcript["stop_reason"] = response.get("stop_reason")
            content = response.get("content", [])
            messages.append({"role": "assistant", "content": content})

            if response.get("stop_reason") == "pause_turn":
                continue
            if response.get("stop_reason") != "tool_use":
                transcript["final_text"] = "\n".join(block.get("text", "") for block in content if block.get("type") == "text")
                return

            results = []
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                result = await call_tool(block["name"], block.get("input") or {})
                transcript["tool_calls"].append({"name": block["name"], "is_error": bool(result.is_error)})
                results.append(
                    {"type": "tool_result", "tool_use_id": block["id"], "content": _tool_result_text(result), "is_error": bool(result.is_error)}
                )
            messages.append({"role": "user", "content": results})
        transcript["stop_reason"] = "max_turns"

    if condition == "mcp":
        from mcp import Client

        from .server import INSTRUCTIONS, build_server

        async with Client(build_server(project)) as client:
            listed = (await client.list_tools()).tools
            tools = [{"name": tool.name, "description": tool.description or "", "input_schema": tool.input_schema} for tool in listed]
            await converse(tools, system_prompt(app, condition, project, INSTRUCTIONS), client.call_tool)
    else:
        await converse([], system_prompt(app, condition, project), None)

    usage_keys = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    totals = {key: sum((call["usage"].get(key) or 0) for call in transcript["calls"]) for key in usage_keys}
    costs = [cost_of(model_name, call["usage"]) for call in transcript["calls"]]
    transcript["messages"] = messages
    transcript["usage"] = totals
    transcript["seconds"] = round(sum(call["seconds"] for call in transcript["calls"]), 3)
    transcript["cost_usd"] = None if any(cost is None for cost in costs) else round(sum(costs), 6)  # type: ignore[arg-type]
    return transcript


def transcript_path(run_dir: Path, task_id: str, condition: str, repetition: int) -> Path:
    return run_dir / "transcripts" / f"{task_id}__{condition}__{repetition}.json"


async def run_all(
    model: Model,
    model_name: str,
    project: Project,
    tasks_file: Path,
    run_dir: Path,
    conditions: list[str],
    repetitions: int,
    max_cost: float,
    concurrency: int = 4,
    log: Any = print,
) -> float:
    """Run every task under every condition, saving each transcript as it finishes.

    A transcript that already exists is not run again, so a stopped run can be continued without
    paying twice. Stops starting new runs once the money spent reaches max_cost. Returns the spend.
    """
    import anyio

    app, tasks = load_tasks(tasks_file)
    write_text(run_dir / "tasks.json", read_text(tasks_file))  # the exact tasks this run used
    spent = 0.0
    for path in sorted((run_dir / "transcripts").glob("*.json")) if (run_dir / "transcripts").exists() else []:
        spent += json.loads(read_text(path)).get("cost_usd") or 0.0

    jobs = [
        (task, condition, repetition)
        for repetition in range(1, repetitions + 1)
        for task in tasks
        for condition in conditions
        if not transcript_path(run_dir, task.id, condition, repetition).exists()
    ]
    limiter = anyio.CapacityLimiter(concurrency)

    async def work(task: Task, condition: str, repetition: int) -> None:
        nonlocal spent
        async with limiter:
            if spent >= max_cost:
                return
            try:
                transcript = await run_once(model, model_name, project, app, task, condition, repetition)
            except Exception as error:  # one failed request must not lose the rest of the run
                log(f"  failed  {task.id} {condition} #{repetition}: {type(error).__name__}: {error}")
                return
            spent += transcript["cost_usd"] or 0.0
            write_text(transcript_path(run_dir, task.id, condition, repetition), json.dumps(transcript, indent=1) + "\n")
            log(f"  done    {task.id} {condition} #{repetition}  {transcript['seconds']:.1f}s  ${spent:.4f} so far")

    async with anyio.create_task_group() as group:
        for job in jobs:
            group.start_soon(work, *job)
    if spent >= max_cost:
        log(f"Stopped at the cost limit of ${max_cost:.2f}. Run again with a higher --max-cost to continue.")
    return spent


# ---- Scoring ----


def extract_code(text: str) -> tuple[str | None, str | None]:
    """The first TSX block and the first CSS block in a reply, or None for whichever is missing."""
    tsx = css_text = None
    for label, body in _FENCE.findall(text):
        label = label.lower()
        if tsx is None and label in _TSX_LABELS:
            tsx = body
        elif css_text is None and label == "css":
            css_text = body
    return tsx, css_text


def type_check(project: Project, files: dict[str, dict[str, str]]) -> dict[str, list[str]] | None:
    """Type-check many outputs in one tsc run. Returns the errors for each key, or None if tsc cannot run.

    files maps a key to {file name: content}. Each key gets its own folder inside the frontend, so
    imports of React resolve and the repo's own strict tsconfig applies. The folder is deleted afterwards.
    The generated code is only compiled with --noEmit. It is never run.
    """
    frontend = project.root / "frontend"
    tsc = frontend / "node_modules" / "typescript" / "bin" / "tsc"
    node = shutil.which("node")
    if node is None or not tsc.exists():
        return None
    work = frontend / ".design-eval"
    shutil.rmtree(work, ignore_errors=True)
    try:
        for key, contents in files.items():
            for name, content in contents.items():
                write_text(work / key / name, content)
        write_text(work / "tsconfig.json", json.dumps({"extends": "../tsconfig.json", "include": ["./**/*.ts", "./**/*.tsx"]}))
        done = subprocess.run(
            [node, str(tsc), "--noEmit", "--pretty", "false", "-p", str(work / "tsconfig.json")],
            cwd=frontend, capture_output=True, text=True, timeout=600, check=False,
        )
        errors: dict[str, list[str]] = {key: [] for key in files}
        for line in done.stdout.splitlines():
            match = _TSC_ERROR.match(line.strip())
            if match is None:
                continue
            parts = Path(match["path"].replace("\\", "/")).parts
            if ".design-eval" in parts:
                key = parts[parts.index(".design-eval") + 1]
                if key in errors:
                    errors[key].append(f"{match['code']} line {match['line']}: {match['message']}")
        return errors
    finally:
        shutil.rmtree(work, ignore_errors=True)


def score_run(project: Project, run_dir: Path) -> list[dict[str, Any]]:
    """Score every saved transcript in a run. Calls no model."""
    transcripts = [json.loads(read_text(path)) for path in sorted((run_dir / "transcripts").glob("*.json"))]
    code = {}
    for index, transcript in enumerate(transcripts):
        tsx, css_text = extract_code(transcript["final_text"])
        code[f"r{index}"] = (transcript, tsx, css_text)

    to_check = {
        key: {f"{t['name']}.tsx": tsx, f"{t['name']}.css": css_text or ""}
        for key, (t, tsx, css_text) in code.items()
        if tsx is not None
    }
    compile_errors = type_check(project, to_check) if to_check else {}

    rows = []
    for key, (transcript, tsx, css_text) in code.items():
        lints = [api.lint_snippet(project, source, language) for source, language in ((tsx, "tsx"), (css_text, "css")) if source is not None]
        token_uses = sum(lint["token_compliance"]["token_uses"] for lint in lints)
        hard_coded = sum(lint["token_compliance"]["hard_coded"] for lint in lints)
        findings = [finding for lint in lints for finding in lint["findings"]]
        pairs = [lint["contrast_pairs"] for lint in lints]
        if tsx is None:
            compiles: bool | None = False  # no component in the reply counts as not compiling
            errors = ["no tsx code block in the reply"]
        elif compile_errors is None:
            compiles, errors = None, []
        else:
            errors = compile_errors[key]
            compiles = not errors
        rows.append(
            {
                "task": transcript["task"],
                "condition": transcript["condition"],
                "repetition": transcript["repetition"],
                "model": transcript["model"],
                "format_ok": tsx is not None and css_text is not None,
                "compiles": compiles,
                "compile_errors": errors,
                "token_uses": token_uses,
                "hard_coded": hard_coded,
                "token_compliance": None if token_uses + hard_coded == 0 else round(100 * token_uses / (token_uses + hard_coded), 2),
                "unknown_tokens": sum(1 for f in findings if f["kind"] == "unknown-token"),
                "contrast_pairs": sum(pair["measured"] for pair in pairs),
                "contrast_failures": sum(pair["failing"] for pair in pairs),
                "focus_findings": sum(1 for f in findings if f["rule"] == "focus"),
                "tool_calls": len(transcript["tool_calls"]),
                "model_calls": len(transcript["calls"]),
                "stop_reason": transcript["stop_reason"],
                "seconds": transcript["seconds"],
                "cost_usd": transcript["cost_usd"],
                "input_tokens": transcript["usage"]["input_tokens"],
                "output_tokens": transcript["usage"]["output_tokens"],
            }
        )
    return rows


# ---- Summarising ----


def _mean(values: list[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def _rate(rows: list[dict[str, Any]], key: str) -> float | None:
    """The percentage of rows where a true/false field is true, ignoring rows where it is unknown."""
    known = [row[key] for row in rows if row[key] is not None]
    return None if not known else 100 * sum(1 for value in known if value) / len(known)


def _metrics(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    pairs = sum(row["contrast_pairs"] for row in rows)
    return {
        "compile_rate": _rate(rows, "compiles"),
        "token_compliance": _mean([row["token_compliance"] for row in rows if row["token_compliance"] is not None]),
        "contrast_pass_rate": None if pairs == 0 else 100 * (pairs - sum(row["contrast_failures"] for row in rows)) / pairs,
        "focus_findings_per_run": _mean([row["focus_findings"] for row in rows]),
        "seconds": _mean([row["seconds"] for row in rows]),
        "cost_usd": _mean([row["cost_usd"] for row in rows if row["cost_usd"] is not None]),
    }


def sign_test(better: int, worse: int) -> float | None:
    """Two-sided exact sign test: how likely is a split this uneven if neither condition were better?

    Ties are left out, as the test requires. With few tasks this can only detect large, consistent effects.
    """
    n = better + worse
    if n == 0:
        return None
    k = min(better, worse)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def summarise(rows: list[dict[str, Any]], reference: str = "baseline") -> dict[str, Any]:
    """Means, run-to-run ranges, and a paired comparison of each condition against the reference.

    Paired means each task is compared with itself under the other condition, so an easy or a hard
    task cannot tilt the result: it is easy or hard on both sides.
    """
    conditions = [c for c in CONDITIONS if any(row["condition"] == c for row in rows)]
    repetitions = sorted({row["repetition"] for row in rows})
    tasks = sorted({row["task"] for row in rows})
    summary: dict[str, Any] = {"conditions": {}, "paired": {}, "tasks": len(tasks), "repetitions": len(repetitions), "runs": len(rows)}

    for condition in conditions:
        mine = [row for row in rows if row["condition"] == condition]
        overall = _metrics(mine)
        per_repetition = [_metrics([row for row in mine if row["repetition"] == r]) for r in repetitions]
        ranges = {}
        for metric in overall:
            values = [m[metric] for m in per_repetition if m[metric] is not None]
            ranges[metric] = None if not values else [min(values), max(values)]
        summary["conditions"][condition] = {
            "runs": len(mine),
            "mean": overall,
            "range_across_repetitions": ranges,
            "runs_with_no_colours": sum(1 for row in mine if row["token_compliance"] is None),
            "runs_not_ended_normally": sum(1 for row in mine if row["stop_reason"] != "end_turn"),
            "contrast_pairs_measured": sum(row["contrast_pairs"] for row in mine),
            "tool_calls_per_run": _mean([row["tool_calls"] for row in mine]),
        }

    def per_task(condition: str, metric: str) -> dict[str, float]:
        values = {}
        for task in tasks:
            value = _metrics([row for row in rows if row["condition"] == condition and row["task"] == task])[metric]
            if value is not None:
                values[task] = value
        return values

    for condition in conditions:
        if condition == reference or reference not in conditions:
            continue
        summary["paired"][f"{condition} vs {reference}"] = {}
        for metric in ("compile_rate", "token_compliance", "contrast_pass_rate", "focus_findings_per_run", "seconds", "cost_usd"):
            ours, theirs = per_task(condition, metric), per_task(reference, metric)
            shared = [task for task in tasks if task in ours and task in theirs]
            differences = [ours[task] - theirs[task] for task in shared]
            higher = sum(1 for d in differences if d > 1e-9)
            lower = sum(1 for d in differences if d < -1e-9)
            summary["paired"][f"{condition} vs {reference}"][metric] = {
                "tasks_compared": len(shared),
                "mean_difference": _mean(differences),
                "tasks_higher": higher,
                "tasks_same": len(shared) - higher - lower,
                "tasks_lower": lower,
                "sign_test_p": sign_test(higher, lower),
            }
    return summary


def estimate(project: Project, tasks_file: Path, model_name: str, conditions: list[str], repetitions: int) -> dict[str, Any]:
    """A rough cost estimate before any model call. It counts characters; it does not call the API.

    Assumptions, stated so they can be argued with: 4 characters per token; a reply of 3,000 tokens
    (code plus thinking); and for the mcp condition, 5 model calls per run that each resend the
    conversation so far, including the tool results.
    """
    app, tasks = load_tasks(tasks_file)
    tokens = lambda text: len(text) / 4  # noqa: E731
    reply = 3_000
    tool_results = tokens(json.dumps(api.get_design_tokens(project))) + tokens(json.dumps(api.get_guidelines(project))) + 2 * 1_500
    per_condition = {}
    for condition in conditions:
        prompt = _mean([tokens(system_prompt(app, condition, project) + task.request) for task in tasks]) or 0
        if condition == "mcp":
            calls = 5
            tool_definitions = 1_200
            # Each call resends everything before it. If the history grows steadily from nothing to
            # (tool results + reply), the calls carry half of that on average.
            input_tokens = calls * (prompt + tool_definitions) + calls * (tool_results + reply) / 2
            output_tokens = reply + (calls - 1) * 300
        else:
            input_tokens, output_tokens = prompt, reply
        per_condition[condition] = {"input_tokens_per_run": round(input_tokens), "output_tokens_per_run": round(output_tokens)}
    runs = len(tasks) * repetitions
    total_in = sum(c["input_tokens_per_run"] for c in per_condition.values()) * runs
    total_out = sum(c["output_tokens_per_run"] for c in per_condition.values()) * runs
    price = PRICES.get(model_name)
    return {
        "model": model_name,
        "tasks": len(tasks),
        "repetitions": repetitions,
        "runs": runs * len(conditions),
        "per_condition": per_condition,
        "input_tokens": total_in,
        "output_tokens": total_out,
        "estimated_cost_usd": None if price is None else round((total_in * price[0] + total_out * price[1]) / 1_000_000, 2),
    }
