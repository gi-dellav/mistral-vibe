from __future__ import annotations

from typing import ClassVar
from collections.abc import AsyncGenerator
from pathlib import Path

from pydantic import BaseModel, Field

from vibe.core.tools.lsp.base_lsp_tool import BaseLSPTool, LSPToolConfig, LSPToolState
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
        default=False, 
        description="Include the declaration in the results"
    )
    context_lines: int = Field(
        default=1, 
        description="Context lines to include around each reference"
    )
    max_results: int = Field(
        default=20, 
        description="Maximum number of references to return"
    )


class FindReferencesResult(BaseModel):
    symbol_name: str = Field(description="Name of the symbol being referenced")
    references: list[ReferenceLocation] = Field(description="List of reference locations")
    total_count: int = Field(description="Total number of references found")
    was_truncated: bool = Field(description="True if results were truncated")


class FindReferences(BaseLSPTool[FindReferencesArgs, FindReferencesResult, LSPToolConfig, LSPToolState]):
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
            
            # Create request parameters
            params = {
                **self._create_position_params(args.file_path, args.line, args.character),
                "context": {"includeDeclaration": args.include_declaration}
            }
            
            # Send request to LSP server
            response = await server_process.request("textDocument/references", params)
            
            if not response:
                raise ToolError("No references found for the symbol at the specified location.")
            
            # Process references
            references = []
            for location in response[:args.max_results]:
                file_path = str(Path(location["uri"]).resolve())
                context = self._read_context_around_position(
                    file_path,
                    location["range"]["start"]["line"],
                    args.context_lines
                )
                
                references.append(ReferenceLocation(
                    file_path=file_path,
                    line=location["range"]["start"]["line"],
                    character=location["range"]["start"]["character"],
                    context=context
                ))
            
            # Extract symbol name from original location
            symbol_name = self._extract_symbol_name(args.file_path, args.line)
            
            yield FindReferencesResult(
                symbol_name=symbol_name,
                references=references,
                total_count=len(response),
                was_truncated=len(response) > args.max_results
            )
            
        except Exception as e:
            await self._handle_lsp_error(e, "find references")
    
    def _read_context_around_position(self, file_path: str, line: int, context_lines: int) -> str:
        """Read code context around a specific line in a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Calculate start and end lines
            start_line = max(0, line - context_lines)
            end_line = min(len(lines), line + context_lines + 1)
            
            # Extract context lines
            context_lines = lines[start_line:end_line]
            
            # Add line numbers
            result = []
            for i, context_line in enumerate(context_lines, start=start_line + 1):
                marker = ">>>" if i == line + 1 else "   "
                result.append(f"{marker} {i:4d}: {context_line.rstrip()}")
            
            return "\n".join(result)
            
        except Exception as e:
            return f"Unable to read context: {str(e)}"
    
    def _extract_symbol_name(self, file_path: str, line: int) -> str:
        """Extract symbol name from file at specific line."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if line < len(lines):
                target_line = lines[line].strip()
                # Simple heuristic for symbol extraction
                if 'def ' in target_line:
                    return target_line.split('def ')[1].split('(')[0].strip()
                elif 'class ' in target_line:
                    return target_line.split('class ')[1].split(':')[0].split('(')[0].strip()
                elif '=' in target_line:
                    return target_line.split('=')[0].strip()
                else:
                    # Return first word as symbol name
                    return target_line.split()[0] if target_line.split() else "unknown"
        except Exception:
            return "unknown"