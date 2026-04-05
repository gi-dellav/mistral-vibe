from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from vibe.core.tools.base import InvokeContext, ToolError
from vibe.core.tools.lsp.base_lsp_tool import BaseLSPTool
from vibe.core.types import ToolStreamEvent


class TypeHierarchyItem(BaseModel):
    name: str = Field(description="Name of the type")
    detail: str | None = Field(
        default=None, description="Type detail (e.g., full signature)"
    )
    file_path: str = Field(description="Path to the file")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")
    kind: str = Field(description="Type kind (class, interface, enum, etc.)")
    context: str = Field(default="", description="Code context around the type")


class TypeHierarchyArgs(BaseModel):
    file_path: str = Field(description="Path to the source file")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")
    direction: str = Field(
        default="both", description="Direction: 'supertypes', 'subtypes', or 'both'"
    )
    context_lines: int = Field(
        default=2, description="Context lines to include around each type"
    )


class TypeHierarchyResult(BaseModel):
    symbol_name: str = Field(description="Name of the symbol")
    file_path: str = Field(description="Path to the file")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")
    supertypes: list[TypeHierarchyItem] = Field(
        default_factory=list, description="Parent types (inheritance hierarchy)"
    )
    subtypes: list[TypeHierarchyItem] = Field(
        default_factory=list, description="Child types (derived classes)"
    )
    has_hierarchy: bool = Field(description="Whether any hierarchy was found")


class TypeHierarchy(BaseLSPTool[TypeHierarchyArgs, TypeHierarchyResult]):
    """Get type hierarchy at a cursor position using LSP."""

    description: ClassVar[str] = (
        "Get type hierarchy at a cursor position using LSP. "
        "Shows inheritance hierarchy - parent types (supertypes) and child types (subtypes)."
    )

    async def run(
        self, args: TypeHierarchyArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | TypeHierarchyResult, None]:
        try:
            server_process = await self._ensure_server_running(args.file_path)

            params = self._create_position_params(
                args.file_path, args.line, args.character
            )

            async with server_process.start_server():
                prepare_response = await self._request_with_timeout(
                    server_process, "typeHierarchy/prepare", params
                )

                if not prepare_response:
                    yield TypeHierarchyResult(
                        symbol_name="",
                        file_path=args.file_path,
                        line=args.line,
                        character=args.character,
                        supertypes=[],
                        subtypes=[],
                        has_hierarchy=False,
                    )
                    return

                items = []
                if isinstance(prepare_response, list):
                    items = prepare_response
                elif isinstance(prepare_response, dict):
                    items = [prepare_response]

                if not items:
                    yield TypeHierarchyResult(
                        symbol_name="",
                        file_path=args.file_path,
                        line=args.line,
                        character=args.character,
                        supertypes=[],
                        subtypes=[],
                        has_hierarchy=False,
                    )
                    return

                primary_item = items[0]
                symbol_name = primary_item.get("name", "")

                supertypes = []
                subtypes = []

                if args.direction in {"supertypes", "both"}:
                    supertypes = await self._get_supertypes(
                        server_process, primary_item, args.context_lines
                    )

                if args.direction in {"subtypes", "both"}:
                    subtypes = await self._get_subtypes(
                        server_process, primary_item, args.context_lines
                    )

                yield TypeHierarchyResult(
                    symbol_name=symbol_name,
                    file_path=args.file_path,
                    line=args.line,
                    character=args.character,
                    supertypes=supertypes,
                    subtypes=subtypes,
                    has_hierarchy=len(supertypes) > 0 or len(subtypes) > 0,
                )

        except ToolError:
            raise
        except Exception as e:
            await self._handle_lsp_error(e, "type hierarchy")

    async def _get_supertypes(
        self, server_process: Any, item: dict[str, Any], context_lines: int
    ) -> list[TypeHierarchyItem]:
        """Get supertypes (parent types) for a type hierarchy item."""
        try:
            params = {"item": item}
            response = await self._request_with_timeout(
                server_process, "typeHierarchy/supertypes", params
            )

            return await self._parse_hierarchy_items(response, context_lines)
        except Exception:
            return []

    async def _get_subtypes(
        self, server_process: Any, item: dict[str, Any], context_lines: int
    ) -> list[TypeHierarchyItem]:
        """Get subtypes (child types) for a type hierarchy item."""
        try:
            params = {"item": item}
            response = await self._request_with_timeout(
                server_process, "typeHierarchy/subtypes", params
            )

            return await self._parse_hierarchy_items(response, context_lines)
        except Exception:
            return []

    async def _parse_hierarchy_items(
        self, response: Any, context_lines: int
    ) -> list[TypeHierarchyItem]:
        """Parse type hierarchy items from LSP response."""
        items = []

        if not response:
            return items

        if isinstance(response, list):
            item_list = response
        elif isinstance(response, dict):
            item_list = response.get("items", [])
        else:
            return items

        for item in item_list:
            if not isinstance(item, dict):
                continue

            try:
                uri = item.get("uri", "")
                file_path = str(Path(uri).resolve()) if uri else ""

                range_start = item.get("range", {}).get("start", {})
                line = range_start.get("line", 0)
                character = range_start.get("character", 0)

                kind_map = {
                    1: "class",
                    2: "interface",
                    3: "enum",
                    4: "module",
                    5: "method",
                    6: "property",
                }
                kind = kind_map.get(item.get("kind", 0), "unknown")

                context = ""
                if file_path:
                    context = await self._read_context_around_position(
                        file_path, line, context_lines
                    )

                items.append(
                    TypeHierarchyItem(
                        name=item.get("name", ""),
                        detail=item.get("detail"),
                        file_path=file_path,
                        line=line,
                        character=character,
                        kind=kind,
                        context=context,
                    )
                )
            except Exception:
                continue

        return items
