from __future__ import annotations

from typing import Any
from enum import Enum
from pydantic import BaseModel, Field
from pathlib import Path


class StrEnum(str, Enum):
    """String enum for Python 3.10 compatibility."""
    pass


class LSPServerConfig(BaseModel):
    """Configuration for a single LSP server."""
    
    command: list[str] = Field(
        ..., 
        description="Command to start the LSP server (must support --stdio)"
    )
    extensions: list[str] = Field(
        ..., 
        description="File extensions this server handles"
    )
    root_markers: list[str] = Field(
        default_factory=list,
        description="Files/directories that mark workspace roots"
    )
    enabled: bool = Field(
        default=True,
        description="Whether this server is enabled"
    )
    init_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Initialization options for the server"
    )
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables for the server process"
    )


class LSPConfig(BaseModel):
    """Overall LSP configuration."""
    
    enabled: bool = Field(
        default=True,
        description="Whether LSP support is enabled globally"
    )
    servers: dict[str, LSPServerConfig] = Field(
        default_factory=dict,
        description="Configured LSP servers by language identifier"
    )
    auto_activate: bool = Field(
        default=True,
        description="Automatically activate servers when files are opened"
    )
    max_retries: int = Field(
        default=1,
        description="Maximum number of retries for failed LSP requests"
    )
    request_timeout: int = Field(
        default=30,
        description="Timeout for LSP requests in seconds"
    )


class Diagnostic(BaseModel):
    """Represents a single LSP diagnostic."""
    
    file_path: str
    line: int
    character: int
    severity: str  # error, warning, info, hint
    message: str
    code: str | None = None
    source: str | None = None


class PostEditDiagnosticsResult(BaseModel):
    """Result of post-edit diagnostics check."""
    
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    has_errors: bool = False
    has_warnings: bool = False
    summary: str = ""


def get_default_lsp_config() -> LSPConfig:
    """Get default LSP configuration with common language servers."""
    return LSPConfig(
        servers={
            "python": LSPServerConfig(
                command=["pyright-langserver", "--stdio"],
                extensions=[".py", ".pyi"],
                root_markers=["pyproject.toml", "setup.py", "setup.cfg", ".git"],
            ),
            "typescript": LSPServerConfig(
                command=["typescript-language-server", "--stdio"],
                extensions=[".ts", ".tsx", ".js", ".jsx", ".mts", ".cts"],
                root_markers=["package.json", "tsconfig.json", "jsconfig.json"],
            ),
            "rust": LSPServerConfig(
                command=["rust-analyzer"],
                extensions=[".rs"],
                root_markers=["Cargo.toml"],
            ),
        }
    )