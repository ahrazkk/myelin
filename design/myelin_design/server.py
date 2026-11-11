"""The MCP server: Myelin's design system, offered to AI agents as four read-only tools.

Each tool is a thin wrapper around a function in api.py. This module adds only what MCP needs:
the tool names, the descriptions an agent reads to decide which tool to call, the read-only
annotation, and turning a bad argument into an error message the agent can act on.

Run it with:  python -m myelin_design serve            (stdio, for an MCP host to launch)
              python -m myelin_design serve --http     (streamable HTTP on 127.0.0.1:8000/mcp)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import __version__, api
from .project import Project

T = TypeVar("T")

# Hints for the host. read_only: the tool changes nothing. idempotent: calling it twice is the same
# as calling it once. open_world false: it only looks at this repo, never the network.
# They are hints, not a security boundary: what makes the tools safe is that the code only reads.
READ_ONLY = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False)

INSTRUCTIONS = (
    "Myelin's design system. Before writing UI code for Myelin, call get_guidelines and "
    "get_design_tokens. Use only design tokens for colour (var(--name)); check any text and "
    "background pairing with check_contrast; and run lint_snippet on the code you write, fixing "
    "every finding before you present it."
)


def _call(function: Callable[..., T], *args: object) -> T:
    """Run an api function, turning a bad argument into an error message the agent will see."""
    try:
        return function(*args)
    except ValueError as error:
        raise ToolError(str(error)) from None


def build_server(project: Project | None = None) -> MCPServer:
    """Create the server. Tests pass their own project; the command line uses this repo."""
    project = project or Project.default()
    server = MCPServer("myelin-design", instructions=INSTRUCTIONS, version=__version__)

    @server.tool(title="Get design tokens", annotations=READ_ONLY)
    def get_design_tokens(theme: str | None = None, accent: str | None = None) -> api.DesignTokens:
        """Myelin's colour tokens: name, CSS variable, role, description and value.

        With no arguments, returns every token with its day and night values and its value under
        each accent. Pass theme ("day" or "night") or accent ("myelin", "emerald", "amber", "rose")
        to get only those values. In code, always write var(--name); never copy a hex value.
        """
        return _call(api.get_design_tokens, project, theme, accent)

    @server.tool(title="Check colour contrast", annotations=READ_ONLY)
    def check_contrast(
        foreground: str, background: str, theme: str | None = None, accent: str | None = None
    ) -> api.ContrastCheck:
        """WCAG 2.1 contrast ratio between a foreground and a background.

        Each can be a token name ("ink", "--ink", "var(--ink)") or a CSS colour ("#1b2142",
        "rgb(0 0 0 / 0.5)"). Returns the ratio and whether it passes AA for text (4.5:1), large
        text (3:1) and non-text such as borders and focus rings (3:1). Tokens are measured in every
        theme and accent unless you name one. Translucent colours are composited before measuring.
        """
        return _call(api.check_contrast, project, foreground, background, theme, accent)

    @server.tool(title="Lint a code snippet", annotations=READ_ONLY)
    def lint_snippet(code: str, language: str) -> api.SnippetLint:
        """Check CSS, TS or TSX against Myelin's design system. The code is scanned as text, never run.

        language is "css", "ts" or "tsx". Finds hard-coded colours (and says which token to use
        when one matches), unknown tokens, removed focus outlines, and, in CSS, text and background
        pairs below 4.5:1. Returns the findings with line numbers and a token-compliance percentage.
        """
        return _call(api.lint_snippet, project, code, language)

    @server.tool(title="Get UI guidelines", annotations=READ_ONLY)
    def get_guidelines() -> api.Guidelines:
        """Myelin's UI rules: colour, themes, focus, motion and the ARIA patterns in use.

        Also returns every colour pair the design system declares, with its measured contrast and
        whether it passes, so you can pick a text colour that is known to work on a given surface.
        """
        return _call(api.get_guidelines, project)

    return server


def serve(http: bool = False, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the server and block. Over stdio, stdout is the wire, so nothing here may print."""
    server = build_server()
    if http:
        server.run("streamable-http", host=host, port=port)
    else:
        server.run("stdio")
