from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel

from vibe.core.logger import logger
from vibe.core.tools.base import BaseTool, BaseToolConfig, BaseToolState, ToolError


class BaseLSPTool[ToolArgs: BaseModel, ToolResult: BaseModel](
    BaseTool[ToolArgs, ToolResult, BaseToolConfig, BaseToolState]
):
    """Base class for all LSP tools."""

    description: ClassVar[str] = "Base class for LSP tools"
    _lsp_manager_getter: ClassVar[Callable[[], Any] | None] = None

    def __init__(self, config: BaseToolConfig, state: Any) -> None:
        super().__init__(config, state)
        if BaseLSPTool._lsp_manager_getter:
            self.lsp_manager = BaseLSPTool._lsp_manager_getter()
        else:
            from vibe.core.lsp.manager import get_lsp_manager

            self.lsp_manager = get_lsp_manager()

    @classmethod
    def is_available(cls) -> bool:
        from vibe.core.lsp.manager import get_lsp_manager

        return get_lsp_manager().config.enabled

    async def _ensure_server_running(self, file_path: str) -> Any:
        """Ensure LSP server is running for the given file."""
        server = await self.lsp_manager.ensure_server_for_file(file_path)
        if server is None:
            raise ToolError(
                "No LSP server configured for this file type. "
                "Configure an LSP server in your settings to enable this feature."
            )
        return server

    async def _request_with_timeout(
        self, server_process: Any, method: str, params: dict[str, Any]
    ) -> Any:
        """Send LSP request with timeout."""
        timeout = self.lsp_manager.config.request_timeout
        try:
            return await asyncio.wait_for(
                server_process.request(method, params), timeout=timeout
            )
        except asyncio.TimeoutError:
            raise ToolError(
                f"LSP request '{method}' timed out after {timeout}s. "
                "The LSP server may be unresponsive. Try /restart-lsp to restart servers."
            )

    async def _request_with_retry(
        self,
        server_process: Any,
        method: str,
        params: dict[str, Any],
        max_retries: int | None = None,
    ) -> Any:
        """Send LSP request with retry logic."""
        if max_retries is None:
            max_retries = self.lsp_manager.config.max_retries

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                return await self._request_with_timeout(server_process, method, params)
            except ToolError as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = 0.5 * (2**attempt)
                    logger.warning(
                        f"LSP request '{method}' failed (attempt {attempt + 1}/{max_retries + 1}): {e!s}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.warning(
                        f"LSP request '{method}' failed after {max_retries + 1} attempts: {e!s}"
                    )
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = 0.5 * (2**attempt)
                    logger.warning(
                        f"LSP request '{method}' error (attempt {attempt + 1}/{max_retries + 1}): {e!s}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)

        if last_error:
            raise ToolError(
                f"LSP request '{method}' failed after {max_retries + 1} attempts: {last_error!s}"
            )
        raise ToolError(
            f"LSP request '{method}' failed after {max_retries + 1} attempts"
        )

    async def _handle_lsp_error(self, error: Exception, context: str) -> None:
        """Handle LSP errors with appropriate user messaging."""
        error_msg = f"LSP error in {context}: {error!s}"
        if "not available" in str(error):
            raise ToolError(
                f"{error_msg}. No LSP server configured for this file type."
            )
        elif "timed out" in str(error):
            raise ToolError(f"{error_msg}. The operation took too long.")
        elif "Connection" in str(error) or "connection" in str(error):
            raise ToolError(
                f"{error_msg}. LSP server connection lost. "
                f"Try using /lsp-status to check server status, or /restart-lsp to restart the servers."
            )
        else:
            raise ToolError(error_msg)

    def _create_position_params(
        self, file_path: str, line: int, character: int
    ) -> dict[str, Any]:
        """Create LSP position parameters."""
        return {
            "textDocument": {"uri": Path(file_path).as_uri()},
            "position": {"line": line, "character": character},
        }

    def _create_text_document_params(self, file_path: str) -> dict[str, Any]:
        """Create LSP text document parameters."""
        return {"textDocument": {"uri": Path(file_path).as_uri()}}

    async def _read_context_around_position(
        self, file_path: str, line: int, context_lines: int
    ) -> str:
        """Read code context around a specific line in a file."""
        try:
            lines = await asyncio.to_thread(self._read_file_lines, file_path)

            start_line = max(0, line - context_lines)
            end_line = min(len(lines), line + context_lines + 1)

            context_lines_content = lines[start_line:end_line]

            result = []
            for i, context_line in enumerate(
                context_lines_content, start=start_line + 1
            ):
                marker = ">>>" if i == line + 1 else "   "
                result.append(f"{marker} {i:4d}: {context_line.rstrip()}")

            return "\n".join(result)

        except Exception as e:
            return f"Unable to read context: {e!s}"

    def _read_file_lines(self, file_path: str) -> list[str]:
        """Read all lines from a file (runs in thread pool)."""
        with open(file_path, encoding="utf-8") as f:
            return f.readlines()

    async def _extract_symbol_name(self, file_path: str, line: int) -> str:
        """Extract symbol name from file at specific line."""
        try:
            lines = await asyncio.to_thread(self._read_file_lines, file_path)

            if line < len(lines):
                target_line = lines[line].strip()
                if "def " in target_line:
                    return target_line.split("def ")[1].split("(")[0].strip()
                elif "class " in target_line:
                    return (
                        target_line
                        .split("class ")[1]
                        .split(":")[0]
                        .split("(")[0]
                        .strip()
                    )
                elif "=" in target_line:
                    return target_line.split("=")[0].strip()
                elif target_line.split():
                    return target_line.split()[0]
        except Exception:
            pass
        return "unknown"
