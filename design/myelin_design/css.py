"""A small CSS reader: enough to find rules, their selectors and their declarations.

It is a single pass over the characters, with no regular expressions and no recursion, so it takes
time proportional to the input and cannot be made to hang or overflow the stack. That matters
because the MCP server runs it on text an AI agent hands over. It reads CSS; it never runs anything.

What it understands: comments, strings, parentheses (so the ';' in url(data:...;base64) is not a
separator), style rules, and at-rules that group other rules (@media and friends). It does not
resolve the cascade and it does not validate CSS. Broken input gives a best-effort result.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_GROUP_DEPTH = 32

# At-rules whose block contains other rules, not declarations.
GROUP_AT_RULES = (
    "@media",
    "@supports",
    "@container",
    "@layer",
    "@scope",
    "@starting-style",
    "@keyframes",
    "@-webkit-keyframes",
)


@dataclass(frozen=True)
class Declaration:
    prop: str
    value: str
    line: int


@dataclass(frozen=True)
class Rule:
    selector: str
    at_rules: tuple[str, ...]
    declarations: tuple[Declaration, ...]
    line: int

    def get(self, prop: str) -> str | None:
        """The last value declared for a property, which is the one that wins inside a rule."""
        for declaration in reversed(self.declarations):
            if declaration.prop == prop:
                return declaration.value
        return None


@dataclass
class _Frame:
    selector: str | None  # None for the stylesheet itself and for grouping at-rules
    at_rules: tuple[str, ...]
    line: int
    declarations: list[Declaration] = field(default_factory=list)
    order: int = 0  # the order the block was opened in, so rules can be returned in source order
    is_group: bool = False  # opened by an at-rule such as @media, not by a selector


class _Buffer:
    """Collects the text between separators and remembers the line it started on."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.line = 1
        self.has_text = False

    def add(self, text: str, line: int) -> None:
        if not self.has_text and not text.isspace():
            self.has_text = True
            self.line = line
        self.parts.append(text)

    def take(self) -> tuple[str, int]:
        chunk = " ".join("".join(self.parts).split())
        self.parts = []
        self.has_text = False
        return chunk, self.line


def _is_group(prelude: str) -> bool:
    lowered = prelude.lower()
    return any(
        lowered == name or lowered.startswith((name + " ", name + "("))
        for name in GROUP_AT_RULES
    )


def _add_declaration(frame: _Frame, chunk: str, line: int) -> None:
    if frame.selector is None or ":" not in chunk:
        return
    prop, _, value = chunk.partition(":")
    prop = prop.strip()
    if not prop.startswith("--"):  # custom property names are case-sensitive, others are not
        prop = prop.lower()
    if prop:
        frame.declarations.append(Declaration(prop, value.strip(), line))


def _close(frame: _Frame, rules: list[tuple[int, Rule]]) -> None:
    # A group with no declarations of its own (the usual @media { ... }) is not a rule.
    if frame.selector is not None and (frame.declarations or not frame.is_group):
        rules.append((frame.order, Rule(frame.selector, frame.at_rules, tuple(frame.declarations), frame.line)))


def parse(text: str) -> list[Rule]:
    """Parse CSS text into a flat list of rules, in source order."""
    rules: list[tuple[int, Rule]] = []
    stack: list[_Frame] = [_Frame(selector=None, at_rules=(), line=1)]
    buffer = _Buffer()
    opened = 0  # how many blocks have been opened so far
    line = 1
    depth = 0  # parenthesis depth
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        if ch == "/" and text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
            buffer.add(" ", line)
            line += text.count("\n", i, end)
            i = end
            continue

        if ch in "\"'":
            # A string runs to its closing quote, or to the end of the line if it is never closed.
            j = i + 1
            while j < n and text[j] != ch and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            buffer.add(text[i:j], line)
            line += text.count("\n", i, j)
            i = j
            continue

        if ch == "\n":
            line += 1
            buffer.add(" ", line)
        elif ch == "(":
            depth += 1
            buffer.add(ch, line)
        elif ch == ")":
            depth = max(0, depth - 1)
            buffer.add(ch, line)
        elif ch == ";" and depth == 0:
            chunk, at_line = buffer.take()
            _add_declaration(stack[-1], chunk, at_line)
        elif ch == "{":
            # A brace always ends a parenthesis, so one unclosed '(' cannot swallow the whole file.
            depth = 0
            prelude, at_line = buffer.take()
            parent = stack[-1]
            if _is_group(prelude):
                # A group nested inside a style rule (CSS nesting) still styles that rule's selector.
                # Past MAX_GROUP_DEPTH the list of enclosing at-rules stops growing, which keeps
                # memory proportional to the input however deeply a hostile snippet nests.
                inside = parent.at_rules if len(parent.at_rules) >= MAX_GROUP_DEPTH else parent.at_rules + (prelude,)
                stack.append(_Frame(parent.selector, inside, at_line, order=opened, is_group=True))
            else:
                stack.append(_Frame(prelude, parent.at_rules, at_line, order=opened))
            opened += 1
        elif ch == "}":
            depth = 0
            chunk, at_line = buffer.take()
            _add_declaration(stack[-1], chunk, at_line)
            if len(stack) > 1:
                _close(stack.pop(), rules)
        else:
            buffer.add(ch, line)
        i += 1

    # Input that ends inside a block: keep what was read instead of dropping it.
    chunk, at_line = buffer.take()
    _add_declaration(stack[-1], chunk, at_line)
    while len(stack) > 1:
        _close(stack.pop(), rules)

    rules.sort(key=lambda item: item[0])
    return [rule for _, rule in rules]
