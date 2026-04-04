from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

from vibe.core.tools.base import InvokeContext, ToolError
from vibe.core.tools.lsp.base_lsp_tool import BaseLSPTool
from vibe.core.types import ToolStreamEvent


class ReferenceLocation(BaseModel):
    file_path: str = Field(description="Path to file containing reference")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")
    context: str = Field(description="Code context around the reference")


class FindReferencesArgs(BaseModel):
    file_path: str = Field(description="Path to the source file")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")
    include_declaration: bool = Field(
        default=False, description="Include the declaration in the results"
    )
    context_lines: int = Field(
        default=1, description="Context lines to include around each reference"
    )
    max_results: int = Field(
        default=20, description="Maximum number of references to return"
    )


class FindReferencesResult(BaseModel):
    symbol_name: str = Field(description="Name of the symbol being referenced")
    references: list[ReferenceLocation] = Field(
        description="List of reference locations"
    )
    total_count: int = Field(description="Total number of references found")
    was_truncated: bool = Field(description="True if results were truncated")


class FindReferences(BaseLSPTool[FindReferencesArgs, FindReferencesResult]):
    """Find all references to a symbol using LSP."""

    description: ClassVar[str] = (
        "Find all references to a symbol using LSP. "
        "Returns locations where the symbol is referenced in the codebase."
    )

    async def run(
        self, args: FindReferencesArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | FindReferencesResult, None]:
        try:
            server_process = await self._ensure_server_running(args.file_path)

            params = {
                **self._create_position_params(
                    args.file_path, args.line, args.character
                ),
                "context": {"includeDeclaration": args.include_declaration},
            }

            async with server_process.start_server():
                response = await server_process.request("textDocument/references", params)

            if not response or not isinstance(response, list):
                raise ToolError(
                    "No references found for the symbol at the specified location."
                )

            references = []
            for location in response[: args.max_results]:
                if not isinstance(location, dict) or "uri" not in location:
                    continue
                file_path = str(Path(location["uri"]).resolve())
                context = await self._read_context_around_position(
                    file_path, location["range"]["start"]["line"], args.context_lines
                )

                references.append(
                    ReferenceLocation(
                        file_path=file_path,
                        line=location["range"]["start"]["line"],
                        character=location["range"]["start"]["character"],
                        context=context,
                    )
                )

            symbol_name = await self._extract_symbol_name(args.file_path, args.line)

            yield FindReferencesResult(
                symbol_name=symbol_name,
                references=references,
                total_count=len(response),
                was_truncated=len(response) > args.max_results,
            )

        except ToolError:
            raise
        except Exception as e:
            await self._handle_lsp_error(e, "find references")
