"""Contract tests: what a tool returns over MCP is exactly what the function returns directly.

An MCP server sits between an agent and the real code. These tests prove the wrapper adds nothing
and loses nothing: same data, and a published schema that the data matches. They talk to the
server through a real MCP client, first in memory and then over stdio in a separate process.
"""

import json
import sys

import jsonschema
import pytest

pytest.importorskip("mcp")

from mcp import Client, StdioServerParameters  # noqa: E402
from mcp.types import TextContent  # noqa: E402

from myelin_design import api  # noqa: E402
from myelin_design.project import DESIGN_DIR, Project  # noqa: E402
from myelin_design.server import build_server  # noqa: E402

PROJECT = Project.default()

# Every tool, the arguments to call it with, and the function that should give the same answer.
CASES = [
    ("get_design_tokens", {}, lambda: api.get_design_tokens(PROJECT)),
    ("get_design_tokens", {"theme": "night"}, lambda: api.get_design_tokens(PROJECT, theme="night")),
    ("get_design_tokens", {"theme": "day", "accent": "rose"}, lambda: api.get_design_tokens(PROJECT, "day", "rose")),
    ("check_contrast", {"foreground": "muted", "background": "myelin-wash"}, lambda: api.check_contrast(PROJECT, "muted", "myelin-wash")),
    ("check_contrast", {"foreground": "#767676", "background": "white"}, lambda: api.check_contrast(PROJECT, "#767676", "white")),
    (
        "check_contrast",
        {"foreground": "myelin", "background": "slide", "theme": "day", "accent": "emerald"},
        lambda: api.check_contrast(PROJECT, "myelin", "slide", "day", "emerald"),
    ),
    (
        "lint_snippet",
        {"code": ".a { color: #2d6bad; outline: none; }\n.b { color: var(--muted); background: var(--cresyl-wash); }", "language": "css"},
        lambda: api.lint_snippet(PROJECT, ".a { color: #2d6bad; outline: none; }\n.b { color: var(--muted); background: var(--cresyl-wash); }", "css"),
    ),
    (
        "lint_snippet",
        {"code": 'export const B = () => <button style={{ color: "var(--ink)" }}>ok</button>;', "language": "tsx"},
        lambda: api.lint_snippet(PROJECT, 'export const B = () => <button style={{ color: "var(--ink)" }}>ok</button>;', "tsx"),
    ),
    ("get_guidelines", {}, lambda: api.get_guidelines(PROJECT)),
]
TOOL_NAMES = ["get_design_tokens", "check_contrast", "lint_snippet", "get_guidelines"]

# A bad argument must come back as an error the agent can read, with the same message as the function's.
ERROR_CASES = [
    ("get_design_tokens", {"theme": "dusk"}, lambda: api.get_design_tokens(PROJECT, theme="dusk")),
    ("check_contrast", {"foreground": "inc", "background": "slide"}, lambda: api.check_contrast(PROJECT, "inc", "slide")),
    ("lint_snippet", {"code": "x", "language": "python"}, lambda: api.lint_snippet(PROJECT, "x", "python")),
]


def as_json(value):
    """What the value looks like after a trip over the wire."""
    return json.loads(json.dumps(value))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(build_server(PROJECT), raise_exceptions=True) as connected:
        yield connected


@pytest.mark.anyio
async def test_the_server_offers_exactly_the_four_tools(client):
    tools = (await client.list_tools()).tools
    assert [tool.name for tool in tools] == TOOL_NAMES


@pytest.mark.anyio
async def test_every_tool_is_annotated_read_only_and_described(client):
    for tool in (await client.list_tools()).tools:
        assert tool.annotations.read_only_hint is True, tool.name
        assert tool.annotations.open_world_hint is False, tool.name
        assert tool.annotations.destructive_hint is not True, tool.name
        assert tool.description and len(tool.description) > 40, tool.name
        assert tool.output_schema and tool.output_schema["type"] == "object", tool.name


@pytest.mark.anyio
@pytest.mark.parametrize(("name", "arguments", "direct"), CASES, ids=[f"{case[0]}:{index}" for index, case in enumerate(CASES)])
async def test_tool_over_mcp_equals_the_direct_function(client, name, arguments, direct):
    result = await client.call_tool(name, arguments)
    assert result.is_error is not True
    expected = as_json(direct())
    assert result.structured_content == expected
    # The text an agent without structured-output support would read carries the same data.
    (block,) = result.content
    assert isinstance(block, TextContent)
    assert json.loads(block.text) == expected


@pytest.mark.anyio
async def test_every_result_matches_the_schema_the_tool_publishes(client):
    schemas = {tool.name: tool.output_schema for tool in (await client.list_tools()).tools}
    for name, arguments, _ in CASES:
        result = await client.call_tool(name, arguments)
        jsonschema.Draft202012Validator(schemas[name]).validate(result.structured_content)


@pytest.mark.anyio
async def test_every_tool_is_covered_by_a_contract_case(client):
    covered = {name for name, _, _ in CASES}
    assert covered == {tool.name for tool in (await client.list_tools()).tools}


@pytest.mark.anyio
@pytest.mark.parametrize(("name", "arguments", "direct"), ERROR_CASES, ids=[case[0] for case in ERROR_CASES])
async def test_bad_arguments_come_back_as_a_readable_error(client, name, arguments, direct):
    with pytest.raises(ValueError) as raised:
        direct()
    result = await client.call_tool(name, arguments)
    assert result.is_error is True
    (block,) = result.content
    assert str(raised.value) in block.text


@pytest.mark.anyio
async def test_input_schema_names_the_required_arguments(client):
    tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    assert tools["lint_snippet"].input_schema["required"] == ["code", "language"]
    assert tools["check_contrast"].input_schema["required"] == ["foreground", "background"]
    assert "required" not in tools["get_design_tokens"].input_schema or tools["get_design_tokens"].input_schema["required"] == []


@pytest.mark.anyio
async def test_the_server_works_over_stdio_in_its_own_process():
    """The way a real host runs it: `python -m myelin_design serve`, talking over stdin and stdout."""
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "myelin_design", "serve"], cwd=str(DESIGN_DIR))
    async with Client(parameters) as remote:
        tools = (await remote.list_tools()).tools
        assert [tool.name for tool in tools] == TOOL_NAMES
        result = await remote.call_tool("check_contrast", {"foreground": "ink", "background": "slide"})
        assert result.is_error is not True
        assert result.structured_content == as_json(api.check_contrast(PROJECT, "ink", "slide"))
