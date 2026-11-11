"""The evaluation harness, tested with a scripted fake model. No test here calls a real model."""

import copy
import json
import shutil

import pytest

pytest.importorskip("mcp")

from myelin_design import evaluation  # noqa: E402
from myelin_design.evaluation import Task, cost_of, extract_code, run_all, run_once, score_run, sign_test, summarise  # noqa: E402
from myelin_design.project import Project, read_text, write_text  # noqa: E402

PROJECT = Project.default()
APP = "Myelin is a calm habit dashboard."
TASK = Task("streak-badge", "StreakBadge", "Build a streak badge.")

GOOD_TSX = """import "./StreakBadge.css";

export function StreakBadge({ day, total }: { day: number; total: number }) {
  return (
    <p className="streak-badge">
      Day {day} of {total}
    </p>
  );
}
"""
GOOD_CSS = ".streak-badge { color: var(--ink); background: var(--myelin-wash); }\n"
BAD_TSX = """import "./StreakBadge.css";

export function StreakBadge(props: { day: number }) {
  const unused = 1;
  return <p style={{ color: "#2d6bad", outline: "none" }}>{props.day.nope}</p>;
}
"""
BAD_CSS = ".streak-badge { color: #777777; background: #ffffff; }\n.x:focus { outline: none; }\n"


def reply(tsx: str | None, css: str | None, prose: str = "Here it is.") -> str:
    parts = [prose]
    if tsx is not None:
        parts.append(f"```tsx\n{tsx}```")
    if css is not None:
        parts.append(f"```css\n{css}```")
    return "\n\n".join(parts)


def text_response(text: str, input_tokens: int = 100, output_tokens: int = 200) -> dict:
    return {
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


def tool_response(name: str, arguments: dict, tool_id: str = "toolu_1") -> dict:
    return {
        "content": [
            {"type": "thinking", "thinking": "", "signature": "sig"},
            {"type": "tool_use", "id": tool_id, "name": name, "input": arguments},
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 1000, "output_tokens": 50},
    }


class FakeModel:
    """Returns scripted responses in order and remembers every request it was sent."""

    def __init__(self, script):
        self.script = list(script)
        self.requests: list[dict] = []

    async def create(self, **params):
        self.requests.append(copy.deepcopy(params))
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        return copy.deepcopy(item)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- Small pieces ----


def test_extract_code_finds_the_two_blocks():
    assert extract_code(reply(GOOD_TSX, GOOD_CSS)) == (GOOD_TSX, GOOD_CSS)
    assert extract_code("```typescript\nconst a = 1;\n```\n```CSS\n.a{}\n```") == ("const a = 1;\n", ".a{}\n")
    assert extract_code(reply(GOOD_TSX, None)) == (GOOD_TSX, None)
    assert extract_code("No code, sorry.") == (None, None)
    # Only the first block of each kind counts; other languages are ignored.
    assert extract_code("```bash\nnpm i\n```\n```tsx\nA\n```\n```tsx\nB\n```") == ("A\n", None)


def test_cost_uses_the_price_list():
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert cost_of("claude-haiku-5-5", usage) == pytest.approx(0.60)
    assert cost_of("claude-sonnet-5-5", usage) == pytest.approx(12.00)
    cached = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 1_000_000, "cache_read_input_tokens": 1_000_000}
    assert cost_of("claude-haiku-5-5", cached) == pytest.approx(0.125 + 0.01)
    assert cost_of("some-other-model", usage) is None


def test_sign_test_matches_hand_computed_values():
    assert sign_test(5, 0) == pytest.approx(2 / 32)  # 5 of 5 one way: 2 * (1/2)^5
    assert sign_test(9, 0) == pytest.approx(2 / 512)
    assert sign_test(8, 1) == pytest.approx(2 * (1 + 9) / 512)
    assert sign_test(3, 3) == 1.0
    assert sign_test(0, 0) is None


def test_tasks_file_loads_and_fills_the_template():
    app, tasks = evaluation.load_tasks(PROJECT.design_dir / "eval" / "tasks.json")
    assert app.startswith("Myelin is")
    assert len(tasks) == 18
    assert len({task.id for task in tasks}) == 18
    first = tasks[0]
    assert first.name in first.request and "{name}" not in first.request and "{request}" not in first.request
    assert f'"./{first.name}.css"' in first.request


def test_system_prompt_differs_only_by_what_the_condition_adds():
    baseline = evaluation.system_prompt(APP, "baseline", PROJECT)
    context = evaluation.system_prompt(APP, "context", PROJECT)
    mcp = evaluation.system_prompt(APP, "mcp", PROJECT, "Call the tools.")
    assert baseline == f"You are a senior front-end engineer. {APP}"
    assert context.startswith(baseline) and "--cresyl" in context and "Myelin UI guidelines" in context
    assert mcp == f"{baseline}\n\nCall the tools."
    assert "--cresyl" not in baseline and "--cresyl" not in mcp


def test_estimate_calls_no_model_and_scales_with_the_plan():
    tasks_file = PROJECT.design_dir / "eval" / "tasks.json"
    two = evaluation.estimate(PROJECT, tasks_file, "claude-haiku-5-5", ["baseline", "mcp"], 3)
    three = evaluation.estimate(PROJECT, tasks_file, "claude-haiku-5-5", ["baseline", "context", "mcp"], 3)
    assert two["runs"] == 108 and three["runs"] == 162
    assert 0 < two["estimated_cost_usd"] < three["estimated_cost_usd"] < 5
    assert evaluation.estimate(PROJECT, tasks_file, "unknown-model", ["baseline"], 1)["estimated_cost_usd"] is None


# ---- One run ----


@pytest.mark.anyio
async def test_baseline_run_sends_no_tools_and_records_usage():
    model = FakeModel([text_response(reply(GOOD_TSX, GOOD_CSS), 120, 800)])
    transcript = await run_once(model, "claude-haiku-5-5", PROJECT, APP, TASK, "baseline", 1)

    (request,) = model.requests
    assert "tools" not in request
    assert request["model"] == "claude-haiku-5-5"
    assert request["messages"] == [{"role": "user", "content": TASK.request}]
    assert transcript["stop_reason"] == "end_turn"
    assert extract_code(transcript["final_text"]) == (GOOD_TSX, GOOD_CSS)
    assert transcript["usage"]["input_tokens"] == 120 and transcript["usage"]["output_tokens"] == 800
    assert transcript["cost_usd"] == pytest.approx((120 * 0.10 + 800 * 0.50) / 1_000_000)
    assert transcript["tool_calls"] == []
    assert json.loads(json.dumps(transcript)) == transcript  # can be saved as JSON


@pytest.mark.anyio
async def test_mcp_run_offers_the_tools_and_feeds_real_results_back():
    model = FakeModel(
        [
            tool_response("lint_snippet", {"code": ".a { color: #2d6bad; }", "language": "css"}),
            text_response(reply(GOOD_TSX, GOOD_CSS)),
        ]
    )
    transcript = await run_once(model, "claude-haiku-5-5", PROJECT, APP, TASK, "mcp", 1)

    first, second = model.requests
    assert [tool["name"] for tool in first["tools"]] == ["get_design_tokens", "check_contrast", "lint_snippet", "get_guidelines"]
    assert all(set(tool) == {"name", "description", "input_schema"} for tool in first["tools"])
    assert "lint_snippet" in first["system"]  # the server's own instructions reach the model

    # The second request carries the model's own turn back unchanged, then the tool's real answer.
    assert second["messages"][1]["role"] == "assistant"
    assert second["messages"][1]["content"][0] == {"type": "thinking", "thinking": "", "signature": "sig"}
    (result,) = second["messages"][2]["content"]
    assert (result["type"], result["tool_use_id"], result["is_error"]) == ("tool_result", "toolu_1", False)
    assert json.loads(result["content"])["findings"][0]["suggestion"].startswith("Use var(--myelin)")

    assert transcript["tool_calls"] == [{"name": "lint_snippet", "is_error": False}]
    assert len(transcript["calls"]) == 2
    assert transcript["usage"]["input_tokens"] == 1100


@pytest.mark.anyio
async def test_a_failing_tool_call_is_reported_to_the_model_as_an_error():
    model = FakeModel([tool_response("get_design_tokens", {"theme": "dusk"}), text_response("done")])
    transcript = await run_once(model, "claude-haiku-5-5", PROJECT, APP, TASK, "mcp", 1)
    (result,) = model.requests[1]["messages"][2]["content"]
    assert result["is_error"] is True and "unknown theme" in result["content"]
    assert transcript["tool_calls"] == [{"name": "get_design_tokens", "is_error": True}]


@pytest.mark.anyio
async def test_a_run_that_never_stops_calling_tools_is_cut_off():
    model = FakeModel([tool_response("get_design_tokens", {})])  # the same reply for ever
    transcript = await run_once(model, "claude-haiku-5-5", PROJECT, APP, TASK, "mcp", 1)
    assert transcript["stop_reason"] == "max_turns"
    assert len(model.requests) == evaluation.MAX_TURNS
    assert transcript["final_text"] == ""


@pytest.mark.anyio
async def test_unknown_condition_is_rejected():
    with pytest.raises(ValueError):
        await run_once(FakeModel([text_response("x")]), "claude-haiku-5-5", PROJECT, APP, TASK, "magic", 1)


# ---- A whole run: saving, resuming, the cost limit ----

TASKS = {
    "app": APP,
    "request_template": "Build {name}: {request}",
    "tasks": [
        {"id": "one", "name": "StreakBadge", "request": "a badge"},
        {"id": "two", "name": "StreakBadge", "request": "another badge"},
    ],
}


@pytest.fixture
def tasks_file(tmp_path):
    path = tmp_path / "tasks.json"
    write_text(path, json.dumps(TASKS))
    return path


@pytest.mark.anyio
async def test_run_all_saves_every_transcript_and_does_not_pay_twice(tmp_path, tasks_file):
    run_dir = tmp_path / "run"
    model = FakeModel([text_response(reply(GOOD_TSX, GOOD_CSS))])
    spent = await run_all(model, "claude-haiku-5-5", PROJECT, tasks_file, run_dir, ["baseline", "context"], 2, max_cost=1.0, log=lambda _: None)

    saved = sorted(path.name for path in (run_dir / "transcripts").glob("*.json"))
    assert len(saved) == 2 * 2 * 2  # tasks x conditions x repetitions
    assert "one__baseline__1.json" in saved and "two__context__2.json" in saved
    assert len(model.requests) == 8
    assert spent == pytest.approx(8 * (100 * 0.10 + 200 * 0.50) / 1_000_000)
    assert json.loads(read_text(run_dir / "tasks.json")) == TASKS  # the run keeps the tasks it used

    again = await run_all(model, "claude-haiku-5-5", PROJECT, tasks_file, run_dir, ["baseline", "context"], 2, max_cost=1.0, log=lambda _: None)
    assert len(model.requests) == 8  # nothing was sent the second time
    assert again == pytest.approx(spent)


@pytest.mark.anyio
async def test_run_all_stops_at_the_cost_limit(tmp_path, tasks_file):
    expensive = text_response(reply(GOOD_TSX, GOOD_CSS), input_tokens=0, output_tokens=1_000_000)  # $0.50 each
    model = FakeModel([expensive])
    spent = await run_all(model, "claude-haiku-5-5", PROJECT, tasks_file, tmp_path / "run", ["baseline"], 3, max_cost=1.0, concurrency=1, log=lambda _: None)
    assert len(model.requests) == 2  # the third run was never started
    assert spent == pytest.approx(1.0)


@pytest.mark.anyio
async def test_one_failed_request_does_not_lose_the_run(tmp_path, tasks_file):
    class Flaky(FakeModel):
        async def create(self, **params):
            if len(self.requests) == 0:
                self.requests.append(params)
                raise RuntimeError("rate limited")
            return await super().create(**params)

    model = Flaky([text_response(reply(GOOD_TSX, GOOD_CSS))])
    messages = []
    await run_all(model, "claude-haiku-5-5", PROJECT, tasks_file, tmp_path / "run", ["baseline"], 1, max_cost=1.0, concurrency=1, log=messages.append)
    assert len(list((tmp_path / "run" / "transcripts").glob("*.json"))) == 1
    assert any("failed" in message and "rate limited" in message for message in messages)


# ---- Scoring saved runs ----


def save(run_dir, task: str, condition: str, repetition: int, text: str, **extra) -> None:
    transcript = {
        "task": task, "name": "StreakBadge", "condition": condition, "repetition": repetition, "model": "claude-haiku-5-5",
        "calls": [{}], "tool_calls": [], "stop_reason": "end_turn", "final_text": text,
        "usage": {"input_tokens": 100, "output_tokens": 200}, "seconds": 2.0, "cost_usd": 0.001,
    }
    transcript.update(extra)
    write_text(evaluation.transcript_path(run_dir, task, condition, repetition), json.dumps(transcript))


def test_scoring_uses_the_same_linters_as_ci(tmp_path):
    save(tmp_path, "one", "mcp", 1, reply(GOOD_TSX, GOOD_CSS), tool_calls=[{"name": "lint_snippet", "is_error": False}])
    save(tmp_path, "one", "baseline", 1, reply(BAD_TSX, BAD_CSS))
    save(tmp_path, "two", "baseline", 1, "I cannot help with that.", stop_reason="refusal")
    rows = {(row["task"], row["condition"]): row for row in score_run(PROJECT, tmp_path)}

    good = rows[("one", "mcp")]
    assert (good["token_uses"], good["hard_coded"], good["token_compliance"]) == (2, 0, 100.0)
    assert (good["contrast_pairs"], good["contrast_failures"], good["focus_findings"]) == (1, 0, 0)
    assert good["format_ok"] is True and good["tool_calls"] == 1

    bad = rows[("one", "baseline")]
    assert (bad["token_uses"], bad["hard_coded"], bad["token_compliance"]) == (0, 3, 0.0)  # one hex in TSX, two in CSS
    assert (bad["contrast_pairs"], bad["contrast_failures"]) == (1, 1)  # #777 on white is 4.47:1
    assert bad["focus_findings"] == 2  # the inline style and the CSS rule

    nothing = rows[("two", "baseline")]
    assert nothing["format_ok"] is False
    assert nothing["compiles"] is False  # a reply with no component does not compile
    assert nothing["token_compliance"] is None  # no colours at all: neither 0% nor 100%


@pytest.mark.skipif(
    shutil.which("node") is None or not (PROJECT.root / "frontend" / "node_modules" / "typescript").exists(),
    reason="needs node and the frontend's node_modules (npm ci in frontend/)",
)
def test_compile_rate_uses_the_repos_strict_typescript_settings(tmp_path):
    save(tmp_path, "one", "mcp", 1, reply(GOOD_TSX, GOOD_CSS))
    save(tmp_path, "one", "baseline", 1, reply(BAD_TSX, BAD_CSS))
    rows = {(row["task"], row["condition"]): row for row in score_run(PROJECT, tmp_path)}

    assert rows[("one", "mcp")]["compiles"] is True
    assert rows[("one", "mcp")]["compile_errors"] == []
    bad = rows[("one", "baseline")]
    assert bad["compiles"] is False
    codes = " ".join(bad["compile_errors"])
    assert "TS6133" in codes  # an unused local: only an error because the repo sets noUnusedLocals
    assert "TS2339" in codes  # a property that does not exist
    assert not (PROJECT.root / "frontend" / ".design-eval").exists()  # the scratch folder is removed


def test_type_check_reports_when_it_cannot_run(tmp_path):
    empty = Project(tmp_path)  # no frontend/node_modules here
    assert evaluation.type_check(empty, {"r0": {"A.tsx": "export const a = 1;"}}) is None


# ---- Summarising ----


def row(task: str, condition: str, repetition: int, **values) -> dict:
    base = {
        "task": task, "condition": condition, "repetition": repetition, "compiles": True, "token_compliance": 100.0,
        "contrast_pairs": 2, "contrast_failures": 0, "focus_findings": 0, "seconds": 10.0, "cost_usd": 0.01,
        "tool_calls": 0, "stop_reason": "end_turn",
    }
    return {**base, **values}


def test_summary_means_ranges_and_paired_comparison():
    rows = []
    for task, baseline_compliance in (("a", 0.0), ("b", 20.0), ("c", 100.0)):
        for repetition in (1, 2):
            rows.append(row(task, "baseline", repetition, token_compliance=baseline_compliance, compiles=repetition == 1, contrast_failures=1))
            rows.append(row(task, "mcp", repetition, token_compliance=100.0, seconds=30.0, tool_calls=3))
    summary = summarise(rows)

    assert (summary["tasks"], summary["repetitions"], summary["runs"]) == (3, 2, 12)
    baseline, mcp = summary["conditions"]["baseline"], summary["conditions"]["mcp"]
    assert baseline["mean"]["token_compliance"] == pytest.approx(40.0)
    assert mcp["mean"]["token_compliance"] == pytest.approx(100.0)
    assert baseline["mean"]["compile_rate"] == pytest.approx(50.0)
    assert baseline["range_across_repetitions"]["compile_rate"] == [0.0, 100.0]  # all of run 1 compiled, none of run 2
    assert baseline["mean"]["contrast_pass_rate"] == pytest.approx(50.0)  # 6 of 12 pairs failed
    assert mcp["tool_calls_per_run"] == pytest.approx(3.0)

    paired = summary["paired"]["mcp vs baseline"]
    compliance = paired["token_compliance"]
    assert compliance["mean_difference"] == pytest.approx(60.0)  # (100 + 80 + 0) / 3
    assert (compliance["tasks_higher"], compliance["tasks_same"], compliance["tasks_lower"]) == (2, 1, 0)
    assert compliance["sign_test_p"] == pytest.approx(0.5)  # 2 of 2 untied tasks: not evidence on its own
    assert paired["seconds"]["mean_difference"] == pytest.approx(20.0)  # and it is slower


def test_summary_leaves_out_what_was_not_measured():
    rows = [
        row("a", "baseline", 1, token_compliance=None, compiles=None, contrast_pairs=0, cost_usd=None),
        row("a", "mcp", 1, stop_reason="max_turns"),
    ]
    summary = summarise(rows)
    baseline = summary["conditions"]["baseline"]
    assert baseline["mean"]["token_compliance"] is None and baseline["runs_with_no_colours"] == 1
    assert baseline["mean"]["compile_rate"] is None  # tsc could not run: unknown, not 0%
    assert baseline["mean"]["contrast_pass_rate"] is None
    assert summary["conditions"]["mcp"]["runs_not_ended_normally"] == 1
    assert summary["paired"]["mcp vs baseline"]["token_compliance"]["tasks_compared"] == 0
