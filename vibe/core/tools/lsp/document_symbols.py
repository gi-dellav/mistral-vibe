from __future__ import annotations

from collections.abc import AsyncGenerator
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


class SymbolLocation(BaseModel):
    file_path: str = Field(description="Path to the file")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")
    end_line: int = Field(description="End line number (0-indexed)")
    end_character: int = Field(description="End character position (0-indexed)")


class DocumentSymbol(BaseModel):
    name: str = Field(description="Symbol name")
    kind: str = Field(description="Symbol kind (e.g., function, class, method)")
    detail: str | None = Field(description="Additional detail about the symbol")
    location: SymbolLocation = Field(description="Location of the symbol in the file")
    children: list[DocumentSymbol] = Field(
        default_factory=list, description="Child symbols (for nested structures)"
    )


class DocumentSymbolsArgs(BaseModel):
    file_path: str = Field(description="Path to the source file")
    include_children: bool = Field(
        default=True, description="Include child symbols in the results"
    )
    max_results: int = Field(
        default=100, description="Maximum number of symbols to return"
    )


class DocumentSymbolsResult(BaseModel):
    file_path: str = Field(description="Path to the file")
    symbols: list[DocumentSymbol] = Field(
        default_factory=list, description="List of symbols found in the document"
    )
    total_count: int = Field(description="Total number of symbols found")
    was_truncated: bool = Field(description="True if results were truncated")


class DocumentSymbols(BaseLSPTool[DocumentSymbolsArgs, DocumentSymbolsResult]):
    """List all symbols in a document using LSP."""

    description: ClassVar[str] = (
        "List all symbols (functions, classes, variables, etc.) in a document using LSP. "
        "Returns a hierarchical list of symbols with their names, kinds, and locations."
    )

    async def run(
        self, args: DocumentSymbolsArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | DocumentSymbolsResult, None]:
        try:
            server_process = await self._ensure_server_running(args.file_path)

            params = self._create_text_document_params(args.file_path)

            response = await server_process.request(
                "textDocument/documentSymbol", params
            )

            if not response or not isinstance(response, list):
                yield DocumentSymbolsResult(
                    file_path=args.file_path,
                    symbols=[],
                    total_count=0,
                    was_truncated=False,
                )
                return

            all_symbols = []
            for item in response[: args.max_results]:
                if not isinstance(item, dict):
                    continue
                symbol = self._parse_symbol(item, args.file_path)
                if symbol:
                    all_symbols.append(symbol)

            yield DocumentSymbolsResult(
                file_path=args.file_path,
                symbols=all_symbols,
                total_count=len(response),
                was_truncated=len(response) > args.max_results,
            )

        except ToolError:
            raise
        except Exception as e:
            await self._handle_lsp_error(e, "document symbols")

    def _parse_symbol(self, item: dict, file_path: str) -> DocumentSymbol | None:
        """Parse a symbol item from LSP response."""
        name = item.get("name", "")
        if not name:
            return None

        kind_num = item.get("kind", 0)
        kind = SYMBOL_KIND_MAP.get(kind_num, f"unknown({kind_num})")

        detail = item.get("detail")

        range_data = item.get("range", {})
        location = SymbolLocation(
            file_path=file_path,
            line=range_data.get("start", {}).get("line", 0),
            character=range_data.get("start", {}).get("character", 0),
            end_line=range_data.get("end", {}).get("line", 0),
            end_character=range_data.get("end", {}).get("character", 0),
        )

        children = self._parse_children(item, file_path)

        return DocumentSymbol(
            name=name, kind=kind, detail=detail, location=location, children=children
        )

    def _parse_children(self, item: dict, file_path: str) -> list[DocumentSymbol]:
        """Parse child symbols from a symbol item."""
        children: list[DocumentSymbol] = []
        raw_children = item.get("children")
        if not isinstance(raw_children, list):
            return children

        for child in raw_children[:20]:
            if not isinstance(child, dict):
                continue
            child_symbol = self._parse_symbol(child, file_path)
            if child_symbol:
                children.append(child_symbol)

        return children
