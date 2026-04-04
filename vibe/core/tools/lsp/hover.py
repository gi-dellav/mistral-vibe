from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from vibe.core.tools.base import InvokeContext, ToolError
from vibe.core.tools.lsp.base_lsp_tool import BaseLSPTool
from vibe.core.types import ToolStreamEvent


class HoverArgs(BaseModel):
    file_path: str = Field(description="Path to the source file")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")


class HoverResult(BaseModel):
    contents: str = Field(description="Hover content (markdown/plaintext)")
    has_content: bool = Field(description="Whether hover content was found")
    file_path: str = Field(description="Path to the file")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")


class Hover(BaseLSPTool[HoverArgs, HoverResult]):
    """Get hover information at a cursor position using LSP."""

    description: ClassVar[str] = (
        "Get hover information at a cursor position using LSP. "
        "Returns documentation, type information, and other details about the symbol at the specified location."
    )

    async def run(
        self, args: HoverArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | HoverResult, None]:
        try:
            server_process = await self._ensure_server_running(args.file_path)

            params = self._create_position_params(
                args.file_path, args.line, args.character
            )

            response = await server_process.request("textDocument/hover", params)

            if not response:
                yield HoverResult(
                    contents="",
                    has_content=False,
                    file_path=args.file_path,
                    line=args.line,
                    character=args.character,
                )
                return

            contents = ""
            if isinstance(response, dict):
                contents = self._extract_hover_contents(response.get("contents"))
            elif isinstance(response, list) and response:
                contents = self._extract_hover_contents(response[0].get("contents"))

            yield HoverResult(
                contents=contents,
                has_content=bool(contents),
                file_path=args.file_path,
                line=args.line,
                character=args.character,
            )

        except ToolError:
            raise
        except Exception as e:
            await self._handle_lsp_error(e, "hover")

    def _extract_hover_contents(self, contents: Any) -> str:
        """Extract string content from hover response."""
        if not contents:
            return ""
        if isinstance(contents, str):
            return contents
        if isinstance(contents, dict):
            if "value" in contents:
                return contents["value"]
            return str(contents)
        if isinstance(contents, list):
            parts = []
            for item in contents:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    if "value" in item:
                        parts.append(item["value"])
                    else:
                        parts.append(str(item))
            return "\n".join(parts)
        return str(contents)
