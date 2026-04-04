from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from vibe.core.tools.base import InvokeContext, ToolError
from vibe.core.tools.lsp.base_lsp_tool import BaseLSPTool
from vibe.core.types import ToolStreamEvent


class GoToDefinitionArgs(BaseModel):
    file_path: str = Field(description="Path to the source file")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")
    context_lines: int = Field(
        default=3, description="Context lines to include around definition"
    )


class GoToDefinitionResult(BaseModel):
    file_path: str = Field(description="Path to definition file")
    line: int = Field(description="Line number of definition (0-indexed)")
    character: int = Field(description="Character position of definition (0-indexed)")
    context: str = Field(description="Code context around the definition")
    symbol_name: str = Field(description="Name of the symbol defined")


class GoToDefinition(BaseLSPTool[GoToDefinitionArgs, GoToDefinitionResult]):
    """Navigate to the definition of a symbol using LSP."""

    description: ClassVar[str] = (
        "Navigate to the definition of a symbol using LSP. "
        "Returns the location and context of where the symbol is defined."
    )

    async def run(
        self, args: GoToDefinitionArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | GoToDefinitionResult, None]:
        try:
            server_process = await self._ensure_server_running(args.file_path)

            params = self._create_position_params(
                args.file_path, args.line, args.character
            )

            response = await server_process.request("textDocument/definition", params)

            if not response:
                raise ToolError(
                    "No definition found for the symbol at the specified location."
                )

            if isinstance(response, list):
                if not response:
                    raise ToolError(
                        "No definition found for the symbol at the specified location."
                    )
                location = response[0]
            elif isinstance(response, dict):
                location = response
            else:
                raise ToolError(
                    "Invalid LSP response: expected location or list of locations."
                )

            if not isinstance(location, dict) or "uri" not in location:
                raise ToolError("Invalid location format in LSP response.")

            target_uri = location["uri"]
            target_path = str(Path(target_uri).resolve())

            context = await self._read_context_around_position(
                target_path, location["range"]["start"]["line"], args.context_lines
            )

            symbol_name = await self._extract_symbol_name(
                target_path, location["range"]["start"]["line"]
            )

            yield GoToDefinitionResult(
                file_path=target_path,
                line=location["range"]["start"]["line"],
                character=location["range"]["start"]["character"],
                context=context,
                symbol_name=symbol_name,
            )

        except ToolError:
            raise
        except Exception as e:
            await self._handle_lsp_error(e, "go to definition")
