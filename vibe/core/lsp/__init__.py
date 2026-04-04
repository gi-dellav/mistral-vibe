"""LSP (Language Server Protocol) support for Mistral Vibe."""

from __future__ import annotations

from vibe.core.lsp.config import (
    Diagnostic,
    LSPConfig,
    LSPServerConfig,
    PostEditDiagnosticsResult,
    get_default_lsp_config,
)
from vibe.core.lsp.manager import (
    LSPManager,
    get_lsp_manager,
    set_lsp_config_getter,
    shutdown_lsp_manager,
)

__all__ = [
    "Diagnostic",
    "LSPConfig",
    "LSPManager",
    "LSPServerConfig",
    "PostEditDiagnosticsResult",
    "get_default_lsp_config",
    "get_lsp_manager",
    "set_lsp_config_getter",
    "shutdown_lsp_manager",
]
