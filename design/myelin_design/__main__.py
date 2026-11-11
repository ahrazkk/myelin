"""Command line: python -m myelin_design <command>.

    export            write design/tokens.json from the stylesheet
    export --check    fail if the committed tokens.json is out of date (the token drift gate)
    lint              run the contrast, token-compliance and focus linters; exit 1 on any finding
    lint --write      also write design/reports/lint.md and lint.json
    lint --check      also fail if those committed reports are out of date
    serve             start the MCP server over stdio (needs the "mcp" extra)
    serve --http      start it over streamable HTTP on 127.0.0.1:8000/mcp
    eval estimate     estimate what an evaluation run would cost; calls no model
    eval run          run the evaluation against a model (costs money; needs --max-cost)
    eval score        score a saved run again; calls no model
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
import tomllib
from pathlib import Path

from . import contrast, lint, report, tokens
from .project import Project, read_text, write_text


# What a mistake in design.toml, or a wrong --root, turns into. Reported in one line, not a traceback.
_CONFIG_ERRORS = (contrast.ConfigError, OSError, tomllib.TOMLDecodeError, KeyError, TypeError, AttributeError)


def _config_problem(error: BaseException) -> int:
    if isinstance(error, contrast.ConfigError):
        print(f"design.toml: {error}", file=sys.stderr)
    elif isinstance(error, OSError):
        print(f"Cannot read {error.filename or 'a project file'}: {error.strerror or error}", file=sys.stderr)
    elif isinstance(error, KeyError):
        print(f"design.toml: missing setting {error}", file=sys.stderr)
    else:
        print(f"design.toml is not in the expected shape: {error}", file=sys.stderr)
    return 1


def _export(project: Project, check: bool) -> int:
    try:
        document = tokens.export(project)
        outputs = {project.tokens_json: tokens.render(document)}
        if project.tokens_ts is not None:
            outputs[project.tokens_ts] = tokens.render_ts(document)
    except tokens.TokenError as error:
        print("Token export failed:", file=sys.stderr)
        for problem in error.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    except _CONFIG_ERRORS as error:
        return _config_problem(error)

    status = 0
    for target, expected in outputs.items():
        shown = project.relative(target)
        if not check:
            write_text(target, expected)
            print(f"Wrote {shown}")
            continue
        current = read_text(target) if target.exists() else ""
        if current == expected:
            print(f"{shown} is up to date with {project.config['source']}")
            continue
        print(
            f"Token drift: {shown} does not match {project.config['source']}.\n"
            "Run `python -m myelin_design export` and commit the result.\n",
            file=sys.stderr,
        )
        diff = difflib.unified_diff(
            current.splitlines(), expected.splitlines(), f"{shown} (committed)", f"{shown} (from the CSS)", lineterm=""
        )
        print("\n".join(diff), file=sys.stderr)
        status = 1
    return status


def _lint(project: Project, write: bool, check: bool) -> int:
    try:
        result = lint.run(project)
    except tokens.TokenError as error:
        print("Token export failed:", file=sys.stderr)
        for problem in error.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    except _CONFIG_ERRORS as error:
        return _config_problem(error)

    outputs = {
        project.design_dir / "reports" / "lint.md": report.render(result),
        project.design_dir / "reports" / "lint.json": json.dumps(result, indent=2, ensure_ascii=False) + "\n",
    }
    c, k, f = result["compliance"], result["contrast"], result["focus"]
    percent = "n/a" if c["percent"] is None else f"{c['percent']:.1f}%"
    print(f"Token compliance: {percent} ({c['token_uses']} token uses, {c['hard_coded']} hard-coded, {c['allowed']} allowed)")
    print(f"Contrast: {k['measurements']} measurements, {k['pass']} pass, {k['fail']} fail, {k['known']} known, {k['exempt']} exempt")
    print(f"Focus: {len(f['findings'])} findings")
    for name, count in result["problems"].items():
        if count:
            print(f"  FAIL {name.replace('_', ' ')}: {count}")

    status = 0 if result["ok"] else 1
    for path, text in outputs.items():
        shown = project.relative(path)
        if write:
            write_text(path, text)
            print(f"Wrote {shown}")
        elif check and (not path.exists() or read_text(path) != text):
            print(f"{shown} is out of date. Run `python -m myelin_design lint --write` and commit it.", file=sys.stderr)
            status = 1
    if not write:
        print("See design/reports/lint.md for details." if result["ok"] else "Run with --write and read design/reports/lint.md for details.")
    return status


def _eval(project: Project, args: argparse.Namespace) -> int:
    from . import evaluation  # imported here: it is only needed for this command

    tasks_file = args.tasks or project.design_dir / "eval" / "tasks.json"
    conditions = args.conditions.split(",")
    unknown = [c for c in conditions if c not in evaluation.CONDITIONS]
    if unknown:
        print(f"Unknown condition {unknown[0]!r}. Use: {', '.join(evaluation.CONDITIONS)}", file=sys.stderr)
        return 2

    if args.action == "estimate":
        print(json.dumps(evaluation.estimate(project, tasks_file, args.model, conditions, args.runs), indent=2))
        return 0

    run_dir = project.design_dir / "eval" / "runs" / args.name
    if args.action == "run":
        import anyio

        try:
            model = evaluation.AnthropicModel()
        except ModuleNotFoundError as error:
            print(f'{error.name} is not installed. Run: pip install -e ".[eval]"', file=sys.stderr)
            return 1
        print(f"Running {args.model} on {tasks_file.name}: conditions {conditions}, {args.runs} runs each, cost limit ${args.max_cost:.2f}")
        spent = anyio.run(
            evaluation.run_all, model, args.model, project, tasks_file, run_dir, conditions, args.runs, args.max_cost
        )
        print(f"Spent ${spent:.4f} in total for this run. Transcripts are in {project.relative(run_dir)}/transcripts")

    rows = evaluation.score_run(project, run_dir)
    if not rows:
        print(f"No transcripts in {project.relative(run_dir)}", file=sys.stderr)
        return 1
    summary = evaluation.summarise(rows)
    write_text(run_dir / "scores.json", json.dumps(rows, indent=1) + "\n")
    write_text(run_dir / "summary.json", json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary["conditions"], indent=2))
    print(f"Wrote {project.relative(run_dir)}/scores.json and summary.json")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="myelin_design", description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None, help="repo root (default: the repo this package is in)")
    commands = parser.add_subparsers(dest="command", required=True)

    export = commands.add_parser("export", help="write design/tokens.json from the stylesheet")
    export.add_argument("--check", action="store_true", help="do not write; fail if tokens.json is out of date")

    linter = commands.add_parser("lint", help="run the contrast, token-compliance and focus linters")
    linter.add_argument("--write", action="store_true", help="write design/reports/lint.md and lint.json")
    linter.add_argument("--check", action="store_true", help="fail if the committed reports are out of date")

    server = commands.add_parser("serve", help="start the MCP server")
    server.add_argument("--http", action="store_true", help="serve over streamable HTTP instead of stdio")
    server.add_argument("--host", default="127.0.0.1", help="HTTP host (default: 127.0.0.1, this machine only)")
    server.add_argument("--port", type=int, default=8000, help="HTTP port (default: 8000)")

    evaluate = commands.add_parser("eval", help="evaluate AI-generated UI code with and without the design system")
    evaluate.add_argument("action", choices=["estimate", "run", "score"])
    evaluate.add_argument("--model", default="claude-haiku-5-5", help="model ID (default: claude-haiku-5-5)")
    evaluate.add_argument("--name", default="run", help="folder name under design/eval/runs (default: run)")
    evaluate.add_argument("--conditions", default="baseline,context,mcp", help="comma-separated (default: all three)")
    evaluate.add_argument("--runs", type=int, default=3, help="repetitions of each task per condition (default: 3)")
    evaluate.add_argument("--tasks", type=Path, default=None, help="tasks file (default: design/eval/tasks.json)")
    evaluate.add_argument("--max-cost", type=float, default=None, help="stop once this many US dollars are spent (required for run)")

    args = parser.parse_args(argv)
    project = Project(args.root.resolve()) if args.root else Project.default()
    if args.command == "eval" and args.action == "run" and args.max_cost is None:
        parser.error("eval run spends money: pass --max-cost with a dollar limit")

    if args.command == "export":
        return _export(project, args.check)
    if args.command == "lint":
        return _lint(project, args.write, args.check)
    if args.command == "serve":
        try:
            from .server import serve  # imported here so the linters work without the MCP SDK
        except ModuleNotFoundError as error:
            print(f'The MCP SDK is not installed ({error.name}). Run: pip install -e ".[mcp]"', file=sys.stderr)
            return 1
        serve(http=args.http, host=args.host, port=args.port)
        return 0
    if args.command == "eval":
        return _eval(project, args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
