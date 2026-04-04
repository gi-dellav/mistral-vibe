from __future__ import annotations

from typing import Any, ClassVar
from collections.abc import AsyncGenerator
from pathlib import Path

from pydantic import BaseModel

from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    InvokeContext,
    ToolError,
)
from vibe.core.lsp.manager import get_lsp_manager
from vibe.core.lsp.config import LSPConfig
from vibe.core.types import ToolStreamEvent


class LSPToolConfig(BaseToolConfig):
    """Configuration for LSP tools."""
    
    max_retries: int = 1
    request_timeout: int = 30


class LSPToolState(BaseToolState):
    """State for LSP tools."""
    pass


class BaseLSPTool[
    ToolArgs: BaseModel,
    ToolResult: BaseModel,
    ToolConfig: LSPToolConfig,
    ToolState: LSPToolState,
](BaseTool[ToolArgs, ToolResult, ToolConfig, ToolState]):
    """Base class for all LSP tools."""
    
    description: ClassVar[str] = "Base class for LSP tools"
    
    def __init__(self, config: ToolConfig, state: ToolState):
        super().__init__(config, state)
        self.lsp_manager = get_lsp_manager()
    
    async def _ensure_server_running(self, file_path: str) -> Any:
        """Ensure LSP server is running for the given file."""
        return await self.lsp_manager.ensure_server_for_file(file_path)
    
    async def _handle_lsp_error(self, error: Exception, context: str) -> None:
        """Handle LSP errors with appropriate user messaging."""
        error_msg = f"LSP error in {context}: {str(error)}"
        if "not available" in str(error):
            raise ToolError(f"{error_msg}. No LSP server configured for this file type.")
        elif "timed out" in str(error):
            raise ToolError(f"{error_msg}. The operation took too long.")
        else:
            raise ToolError(error_msg)
    
    def _create_position_params(self, file_path: str, line: int, character: int) -> dict[str, Any]:
        """Create LSP position parameters."""
        return {
            "textDocument": {"uri": Path(file_path).as_uri()},
            "position": {"line": line, "character": character}
        }
    
    def _create_text_document_params(self, file_path: str) -> dict[str, Any]:
        """Create LSP text document parameters."""
        return {
            "textDocument": {"uri": Path(file_path).as_uri()}
        }