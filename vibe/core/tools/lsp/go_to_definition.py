from __future__ import annotations

import asyncio
from typing import ClassVar
from collections.abc import AsyncGenerator
from pathlib import Path

from pydantic import BaseModel, Field

from vibe.core.tools.lsp.base_lsp_tool import BaseLSPTool, LSPToolConfig, LSPToolState
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


class GoToDefinition(
    BaseLSPTool[GoToDefinitionArgs, GoToDefinitionResult, LSPToolConfig, LSPToolState]
):
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

            # Create request parameters
            params = self._create_position_params(
                args.file_path, args.line, args.character
            )

            # Send request to LSP server
            response = await server_process.request("textDocument/definition", params)

            if not response:
                raise ToolError(
                    "No definition found for the symbol at the specified location."
                )

            # Process first location (LSP can return multiple locations)
            location = response[0] if isinstance(response, list) else response
            target_uri = location["uri"]
            target_path = str(Path(target_uri).resolve())

            # Read context around the definition
            context = self._read_context_around_position(
                target_path, location["range"]["start"]["line"], args.context_lines
            )

            # Extract symbol name from context
            symbol_name = self._extract_symbol_name(context)

            yield GoToDefinitionResult(
                file_path=target_path,
                line=location["range"]["start"]["line"],
                character=location["range"]["start"]["character"],
                context=context,
                symbol_name=symbol_name,
            )

        except Exception as e:
            await self._handle_lsp_error(e, "go to definition")

    async def _read_context_around_position(
        self, file_path: str, line: int, context_lines: int
    ) -> str:
        """Read code context around a specific line in a file."""
        try:
            lines = await asyncio.to_thread(self._read_file_lines, file_path)

            # Calculate start and end lines
            start_line = max(0, line - context_lines)
            end_line = min(len(lines), line + context_lines + 1)

            # Extract context lines
            context_lines_content = lines[start_line:end_line]

            # Add line numbers
            result = []
            for i, context_line in enumerate(
                context_lines_content, start=start_line + 1
            ):
                marker = ">>>" if i == line + 1 else "   "  # Mark the definition line
                result.append(f"{marker} {i:4d}: {context_line.rstrip()}")

            return "\n".join(result)

        except Exception as e:
            return f"Unable to read context: {str(e)}"

    def _read_file_lines(self, file_path: str) -> list[str]:
        """Read all lines from a file (runs in thread pool)."""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.readlines()

    async def _extract_symbol_name(self, context: str) -> str:
        """Extract symbol name from context."""
        # Simple heuristic: look for common definition patterns
        lines = context.split("\n")
        for line in lines:
            if ">>>" in line:  # This is the definition line
                # Look for common definition patterns
                if "def " in line:
                    return line.split("def ")[1].split("(")[0].strip()
                elif "class " in line:
                    return line.split("class ")[1].split(":")[0].split("(")[0].strip()
                elif "=" in line:
                    return line.split("=")[0].strip()
                elif ":" in line:
                    return line.split(":")[0].strip()

        return "unknown"
