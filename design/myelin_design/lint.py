"""Run the three linters over the frontend and collect one report.

    token compliance   colours come from tokens, not literals      (compliance.py)
    contrast           every declared pair meets WCAG 2.1 AA        (contrast.py)
    focus              nothing removes the keyboard focus outline   (focus.py)

The result is plain data (dicts and lists), so it can be written as JSON, rendered as Markdown, or
returned from an MCP tool without any conversion.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from . import compliance, contrast, css, focus, tokens
from .project import Project, read_text

SOURCE_SUFFIXES = (".css", ".ts", ".tsx")


def source_files(project: Project) -> list[Path]:
    # The generated token module holds token values by design. It is checked by the drift gate instead.
    generated = project.tokens_ts
    files = [
        path
        for path in project.frontend_src.rglob("*")
        if path.suffix in SOURCE_SUFFIXES and path.is_file() and (generated is None or path.resolve() != generated.resolve())
    ]
    return sorted(files, key=lambda path: project.relative(path))


def _check_compliance(project: Project, files: list[Path], palette: compliance.Palette) -> dict[str, Any]:
    allow = project.config.get("compliance", {}).get("allow", [])
    for index, entry in enumerate(allow):
        if not isinstance(entry.get("file"), str) or not str(entry.get("reason", "")).strip():
            raise contrast.ConfigError(f"compliance.allow #{index + 1} needs a file and a reason")
    used = [False] * len(allow)
    source = project.config["source"]
    stray_tokens = []
    per_file = []
    findings = []
    other_triples = 0

    for path in files:
        name = project.relative(path)
        text = read_text(path)
        uses = compliance.scan(text, path.suffix, palette)
        counts = Counter(use.kind for use in uses)
        hard_coded = counts[compliance.LITERAL] + counts[compliance.TOKEN_COPY]
        if counts[compliance.TOKEN] or hard_coded or counts[compliance.UNKNOWN_TOKEN]:
            per_file.append({"file": name, "token_uses": counts[compliance.TOKEN], "hard_coded": hard_coded})
        if path.suffix != ".css":
            other_triples += compliance.count_other_triples(text, palette)
        elif name != source:
            # A custom property in another stylesheet would be a token the contract never sees.
            for rule in css.parse(text):
                for declaration in rule.declarations:
                    if declaration.prop.startswith("--"):
                        stray_tokens.append({"file": name, "line": declaration.line, "text": f"{declaration.prop}: {declaration.value}"})

        for use in uses:
            if use.kind == compliance.TOKEN:
                continue
            reason = None
            if use.hard_coded:  # an unknown token is a bug, so it can never be allowed
                for index, entry in enumerate(allow):
                    if (
                        entry["file"] == name
                        and entry.get("match", "*") in ("*", use.text)
                        and use.kind in entry.get("kinds", [use.kind])
                    ):
                        used[index] = True  # every entry that matches is in use; the first gives the reason
                        reason = reason or entry["reason"]
            findings.append(
                {"file": name, "line": use.line, "kind": use.kind, "text": use.text, "detail": use.detail, "allowed": reason}
            )

    token_uses = sum(entry["token_uses"] for entry in per_file)
    hard_coded = sum(entry["hard_coded"] for entry in per_file)
    percent = compliance.percentage(token_uses, hard_coded)
    return {
        "token_uses": token_uses,
        "hard_coded": hard_coded,
        "allowed": sum(1 for f in findings if f["allowed"]),
        "violations": sum(1 for f in findings if not f["allowed"]),
        "unknown_tokens": sum(1 for f in findings if f["kind"] == compliance.UNKNOWN_TOKEN),
        "percent": None if percent is None else round(percent, 2),
        "uncounted_rgb_triples": other_triples,
        "tokens_outside_source": stray_tokens,
        "files": per_file,
        "findings": findings,
        "stale_allow": [
            f"{entry['file']}: {entry.get('match', '*')}" for entry, was_used in zip(allow, used) if not was_used
        ],
    }


def _check_focus(project: Project, files: list[Path]) -> dict[str, Any]:
    findings = []
    global_rule = None
    for path in files:
        name = project.relative(path)
        text = read_text(path)
        for finding in focus.scan(text, path.suffix):
            findings.append(
                {"file": name, "line": finding.line, "kind": finding.kind, "selector": finding.selector, "text": finding.text, "message": finding.message}
            )
        if path.suffix == ".css" and global_rule is None:
            rules = focus.global_focus_rules(text)
            if rules:
                global_rule = {"file": name, "line": rules[0].line, "outline": rules[0].get("outline") or rules[0].get("outline-style")}
    if global_rule is None:
        findings.append(
            {"file": "", "line": 0, "kind": focus.NO_GLOBAL_FOCUS, "selector": ":focus-visible", "text": "", "message": "no global :focus-visible rule draws an outline"}
        )
    return {"global_rule": global_rule, "findings": findings}


def _check_contrast(project: Project, files: list[Path], document: dict[str, Any]) -> dict[str, Any]:
    section = project.config.get("contrast", {})
    surfaces, pairs = contrast.read_pairs(project.config, document)
    skies = None
    if "sky_file" in section:
        source = read_text(project.root / section["sky_file"])
        skies = {
            "day": contrast.read_sky(source, section["sky_day"]),
            "night": contrast.read_sky(source, section["sky_night"]),
        }
    results = contrast.evaluate(document, surfaces, pairs, skies)

    names = {token["name"] for token in document["tokens"]}
    undeclared = []
    for path in files:
        if path.suffix != ".css":
            continue
        for line, selector, foreground, background in contrast.undeclared_pairs(read_text(path), surfaces, pairs, names):
            undeclared.append(
                {"file": project.relative(path), "line": line, "selector": selector, "foreground": foreground, "background": background}
            )

    statuses = Counter(result.status for result in results)
    where = {(pair.foreground, pair.surface, pair.kind, pair.opacity): pair.where for pair in pairs}
    known = {(pair.foreground, pair.surface, pair.kind, pair.opacity): pair.known_failure for pair in pairs}
    return {
        "declared_pairs": len(pairs),
        "measurements": len(results),
        "pass": statuses["pass"],
        "fail": statuses["fail"],
        "known": statuses["known"],
        "exempt": statuses["info"],
        "sky": None if skies is None else {theme: {scene: color.hex for scene, color in sky.items()} for theme, sky in skies.items()},
        "pairs": [
            {"foreground": p.foreground, "surface": p.surface, "layers": surfaces[p.surface], "kind": p.kind, "opacity": p.opacity, "where": p.where, "known_failure": p.known_failure}
            for p in pairs
        ],
        "results": [
            {**result.to_json(), "where": where[(result.foreground, result.surface, result.kind, result.opacity)], "known_failure": known[(result.foreground, result.surface, result.kind, result.opacity)]}
            for result in results
        ],
        "undeclared": undeclared,
        "stale_known": contrast.stale_known_failures(pairs, results),
    }


def run(project: Project) -> dict[str, Any]:
    """Lint the project. The result's "ok" is False when anything needs fixing."""
    document = tokens.export(project)
    files = source_files(project)
    palette = compliance.Palette.from_document(document)

    report = {
        "files_scanned": len(files),
        "compliance": _check_compliance(project, files, palette),
        "contrast": _check_contrast(project, files, document),
        "focus": _check_focus(project, files),
    }
    c, k, f = report["compliance"], report["contrast"], report["focus"]
    report["problems"] = {
        "hard_coded_colours": c["violations"] - c["unknown_tokens"],
        "unknown_tokens": c["unknown_tokens"],
        "stale_allowlist_entries": len(c["stale_allow"]),
        "tokens_outside_the_token_file": len(c["tokens_outside_source"]),
        "contrast_failures": k["fail"],
        "undeclared_pairs": len(k["undeclared"]),
        "stale_known_failures": len(k["stale_known"]),
        "focus_findings": len(f["findings"]),
    }
    report["ok"] = not any(report["problems"].values())
    return report
