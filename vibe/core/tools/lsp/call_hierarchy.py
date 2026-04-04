from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from vibe.core.tools.base import InvokeContext, ToolError
from vibe.core.tools.lsp.base_lsp_tool import BaseLSPTool
from vibe.core.types import ToolStreamEvent


class CallLocation(BaseModel):
    file_path: str = Field(description="Path to the file")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")
    from_name: str = Field(description="Name of the calling function")
    to_name: str = Field(description="Name of the called function")
    context: str = Field(default="", description="Code context around the call")


class CallHierarchyArgs(BaseModel):
    file_path: str = Field(description="Path to the source file")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")
    direction: str = Field(
        default="both", description="Direction: 'incoming', 'outgoing', or 'both'"
    )
    context_lines: int = Field(
        default=1, description="Context lines to include around each call"
    )


class CallHierarchyResult(BaseModel):
    symbol_name: str = Field(description="Name of the symbol")
    file_path: str = Field(description="Path to the file")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")
    incoming: list[CallLocation] = Field(
        default_factory=list, description="Functions that call this function"
    )
    outgoing: list[CallLocation] = Field(
        default_factory=list, description="Functions called by this function"
    )
    has_calls: bool = Field(description="Whether any calls were found")


class CallHierarchy(BaseLSPTool[CallHierarchyArgs, CallHierarchyResult]):
    """Get call hierarchy at a cursor position using LSP."""

    description: ClassVar[str] = (
        "Get call hierarchy at a cursor position using LSP. "
        "Shows function call relationships - functions that call this (incoming) and functions called by this (outgoing)."
    )

    async def run(
        self, args: CallHierarchyArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | CallHierarchyResult, None]:
        try:
            server_process = await self._ensure_server_running(args.file_path)

            prepare_params = self._create_position_params(
                args.file_path, args.line, args.character
            )

            prepare_response = await server_process.request(
                "textDocument/prepareCallHierarchy", prepare_params
            )

            if not prepare_response:
                yield CallHierarchyResult(
                    symbol_name="",
                    file_path=args.file_path,
                    line=args.line,
                    character=args.character,
                    incoming=[],
                    outgoing=[],
                    has_calls=False,
                )
                return

            items = []
            if isinstance(prepare_response, list):
                items = prepare_response
            elif isinstance(prepare_response, dict):
                items = [prepare_response]

            if not items:
                yield CallHierarchyResult(
                    symbol_name="",
                    file_path=args.file_path,
                    line=args.line,
                    character=args.character,
                    incoming=[],
                    outgoing=[],
                    has_calls=False,
                )
                return

            primary_item = items[0]
            symbol_name = primary_item.get("name", "")

            incoming = []
            outgoing = []

            if args.direction in {"incoming", "both"}:
                incoming = await self._get_incoming_calls(
                    server_process, primary_item, args.context_lines
                )

            if args.direction in {"outgoing", "both"}:
                outgoing = await self._get_outgoing_calls(
                    server_process, primary_item, args.context_lines
                )

            yield CallHierarchyResult(
                symbol_name=symbol_name,
                file_path=args.file_path,
                line=args.line,
                character=args.character,
                incoming=incoming,
                outgoing=outgoing,
                has_calls=len(incoming) > 0 or len(outgoing) > 0,
            )

        except ToolError:
            raise
        except Exception as e:
            await self._handle_lsp_error(e, "call hierarchy")

    async def _get_incoming_calls(
        self, server_process: Any, item: dict[str, Any], context_lines: int
    ) -> list[CallLocation]:
        """Get incoming calls (functions that call this function)."""
        try:
            params = {"item": item}
            response = await server_process.request(
                "callHierarchy/incomingCalls", params
            )

            return await self._parse_call_locations(response, context_lines, "incoming")
        except Exception:
            return []

    async def _get_outgoing_calls(
        self, server_process: Any, item: dict[str, Any], context_lines: int
    ) -> list[CallLocation]:
        """Get outgoing calls (functions called by this function)."""
        try:
            params = {"item": item}
            response = await server_process.request(
                "callHierarchy/outgoingCalls", params
            )

            return await self._parse_call_locations(response, context_lines, "outgoing")
        except Exception:
            return []

    async def _parse_call_locations(
        self, response: Any, context_lines: int, direction: str
    ) -> list[CallLocation]:
        """Parse call locations from LSP response."""
        locations = []

        if not response:
            return locations

        item_list = []
        if isinstance(response, list):
            item_list = response
        elif isinstance(response, dict):
            item_list = response.get("items", [])

        for item in item_list:
            if not isinstance(item, dict):
                continue

            location = await self._parse_single_call_location(
                item, context_lines, direction
            )
            if location:
                locations.append(location)

        return locations

    async def _parse_single_call_location(
        self, item: dict[str, Any], context_lines: int, direction: str
    ) -> CallLocation | None:
        """Parse a single call location from LSP response."""
        from_item = item.get("from", {})
        to_item = item.get("to", {})

        is_incoming = direction == "incoming"

        source_item = from_item if is_incoming else to_item
        uri = source_item.get("uri", "")
        file_path = str(Path(uri).resolve()) if uri else ""
        range_start = source_item.get("range", {}).get("start", {})
        line = range_start.get("line", 0)
        character = range_start.get("character", 0)

        from_name = from_item.get("name", "")
        to_name = to_item.get("name", "")

        context = ""
        if is_incoming and file_path:
            context = await self._read_context_around_position(
                file_path, line, context_lines
            )
        elif not is_incoming and file_path:
            context = await self._read_context_around_position(
                file_path, line, context_lines
            )

        return CallLocation(
            file_path=file_path,
            line=line,
            character=character,
            from_name=from_name,
            to_name=to_name,
            context=context,
        )
