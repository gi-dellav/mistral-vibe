from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from vibe.core.tools.base import InvokeContext, ToolError
from vibe.core.tools.lsp.base_lsp_tool import BaseLSPTool
from vibe.core.types import ToolStreamEvent

SYMBOL_KIND_MAP: dict[int, str] = {
    1: "file",
    2: "module",
    3: "namespace",
    4: "package",
    5: "class",
    6: "method",
    7: "property",
    8: "field",
    9: "variable",
    10: "constant",
    11: "function",
    12: "parameter",
    13: "interface",
    14: "enum",
    15: "enum_member",
    16: "string",
    17: "number",
    18: "boolean",
    19: "array",
    20: "object",
    21: "key",
    22: "null",
    23: "event",
    24: "operator",
    25: "type_parameter",
}


class WorkspaceSymbolLocation(BaseModel):
    file_path: str = Field(description="Path to the file")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")


class WorkspaceSymbol(BaseModel):
    name: str = Field(description="Symbol name")
    kind: str = Field(description="Symbol kind (e.g., function, class, method)")
    location: WorkspaceSymbolLocation = Field(
        description="Location of the symbol in the workspace"
    )
    container_name: str | None = Field(
        description="Container name (e.g., class or file containing the symbol)"
    )


class WorkspaceSymbolsArgs(BaseModel):
    query: str = Field(description="Search query for finding symbols")
    file_path: str | None = Field(
        default=None,
        description="Optional file path to provide context for the workspace",
    )
    max_results: int = Field(
        default=50, description="Maximum number of symbols to return"
    )


class WorkspaceSymbolsResult(BaseModel):
    query: str = Field(description="The search query used")
    symbols: list[WorkspaceSymbol] = Field(
        default_factory=list, description="List of matching symbols"
    )
    total_count: int = Field(description="Total number of symbols found")
    was_truncated: bool = Field(description="True if results were truncated")


class WorkspaceSymbols(BaseLSPTool[WorkspaceSymbolsArgs, WorkspaceSymbolsResult]):
    """Search for symbols across the workspace using LSP."""

    description: ClassVar[str] = (
        "Search for symbols across the entire workspace using LSP. "
        "Similar to VS Code's 'Go to Symbol' (Ctrl+T) feature. "
        "Returns matching symbols with their locations."
    )

    async def run(
        self, args: WorkspaceSymbolsArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | WorkspaceSymbolsResult, None]:
        try:
            if args.file_path:
                server_process = await self._ensure_server_running(args.file_path)
            else:
                raise ToolError(
                    "file_path is required to determine the workspace for symbol search"
                )

            params = {"query": args.query}

            response = await server_process.request("workspace/symbol", params)

            if not response or not isinstance(response, list):
                yield WorkspaceSymbolsResult(
                    query=args.query, symbols=[], total_count=0, was_truncated=False
                )
                return

            symbols = []
            for item in response[: args.max_results]:
                if not isinstance(item, dict):
                    continue
                symbol = self._parse_symbol(item)
                if symbol:
                    symbols.append(symbol)

            yield WorkspaceSymbolsResult(
                query=args.query,
                symbols=symbols,
                total_count=len(response),
                was_truncated=len(response) > args.max_results,
            )

        except ToolError:
            raise
        except Exception as e:
            await self._handle_lsp_error(e, "workspace symbols")

    def _parse_symbol(self, item: dict) -> WorkspaceSymbol | None:
        """Parse a symbol item from LSP workspace/symbol response."""
        try:
            name = item.get("name", "")
            if not name:
                return None

            kind_num = item.get("kind", 0)
            kind = SYMBOL_KIND_MAP.get(kind_num, f"unknown({kind_num})")

            location_data = item.get("location", {})
            if isinstance(location_data, dict):
                uri = location_data.get("uri", "")
                range_data = location_data.get("range", {})
            else:
                uri = str(location_data)
                range_data = {}

            file_path = ""
            if uri:
                try:
                    file_path = str(Path(uri).resolve())
                except Exception:
                    file_path = uri

            location = WorkspaceSymbolLocation(
                file_path=file_path,
                line=range_data.get("start", {}).get("line", 0),
                character=range_data.get("start", {}).get("character", 0),
            )

            container_name = item.get("containerName")

            return WorkspaceSymbol(
                name=name, kind=kind, location=location, container_name=container_name
            )

        except Exception:
            return None
