from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import ClassVar

from pydantic import BaseModel, Field

from glider.core.lsp.config import PostEditDiagnosticsResult
from glider.core.tools.base import InvokeContext
from glider.core.tools.lsp.base_lsp_tool import BaseLSPTool
from glider.core.types import ToolStreamEvent


class PostEditDiagnosticsArgs(BaseModel):
    file_path: str = Field(description="Path to the file that was edited")
    content: str | None = Field(
        default=None, description="Current file content if available"
    )


class PostEditDiagnostics(
    BaseLSPTool[PostEditDiagnosticsArgs, PostEditDiagnosticsResult]
):
    """Check for LSP diagnostics after a file edit."""

    description: ClassVar[str] = (
        "Check for LSP diagnostics after a file edit. "
        "Returns warnings, errors, and other issues found in the code."
    )

    async def run(
        self, args: PostEditDiagnosticsArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | PostEditDiagnosticsResult, None]:
        try:
            # Get diagnostics from LSP manager
            diagnostics_result = await self.lsp_manager.get_diagnostics_for_file(
                args.file_path
            )

            yield diagnostics_result

        except Exception as e:
            await self._handle_lsp_error(e, "post-edit diagnostics")
