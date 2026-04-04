from __future__ import annotations

from pathlib import Path
from typing import Any

from multilspy import LanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger

from vibe.core.logger import logger
from vibe.core.lsp.config import (
    Diagnostic,
    LSPConfig,
    PostEditDiagnosticsResult,
    get_default_lsp_config,
)

LANGUAGE_SERVER_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".rs": "rust",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mts": "typescript",
    ".mjs": "javascript",
    ".cts": "typescript",
    ".cjs": "javascript",
    ".java": "java",
    ".go": "go",
    ".cs": "csharp",
    ".rb": "ruby",
    ".dart": "dart",
    ".kt": "kotlin",
    ".kts": "kotlin",
}


class LSPManager:
    """Central manager for LSP servers using multilspy."""

    def __init__(self, config: LSPConfig) -> None:
        self.config = config
        self.servers: dict[str, LanguageServer] = {}
        self.workspace_roots: dict[str, Path] = {}

    def _get_language_for_file(self, file_path: str) -> str | None:
        """Get the language identifier for a file based on its extension."""
        file_ext = Path(file_path).suffix.lower()
        return LANGUAGE_SERVER_MAP.get(file_ext)

    def _find_workspace_root(self, file_path: str) -> Path:
        """Find the workspace root for a file."""
        file_path_obj = Path(file_path).resolve()
        parent = file_path_obj.parent

        while parent != parent.parent:
            for marker in [
                "pyproject.toml",
                "setup.py",
                "setup.cfg",
                "package.json",
                "tsconfig.json",
                "jsconfig.json",
                "Cargo.toml",
                "go.mod",
            ]:
                if (parent / marker).exists():
                    self.workspace_roots[str(file_path_obj)] = parent
                    return parent
            parent = parent.parent

        self.workspace_roots[str(file_path_obj)] = file_path_obj.parent
        return file_path_obj.parent

    async def ensure_server_for_file(self, file_path: str) -> LanguageServer:
        """Ensure an LSP server is running for the given file."""
        if not self.config.enabled:
            raise RuntimeError("LSP support is disabled")

        file_path = str(Path(file_path).resolve())
        language = self._get_language_for_file(file_path)

        if not language:
            raise RuntimeError(f"No LSP server configured for file: {file_path}")

        workspace_root = self._find_workspace_root(file_path)
        server_key = f"{language}:{workspace_root}"

        if server_key not in self.servers:
            lsp_config = MultilspyConfig.from_dict({"code_language": language})
            lsp_logger = MultilspyLogger()

            lsp = LanguageServer.create(lsp_config, lsp_logger, str(workspace_root))
            self.servers[server_key] = lsp

        return self.servers[server_key]

    async def get_diagnostics_for_file(
        self, file_path: str
    ) -> PostEditDiagnosticsResult:
        """Get diagnostics for a file after editing using LSP textDocument/diagnostic request."""
        try:
            lsp = await self.ensure_server_for_file(file_path)

            async with lsp.start_server():
                text_document_uri = Path(file_path).as_uri()

                params = {"textDocument": {"uri": text_document_uri}}
                response = await lsp.server.send.text_document_diagnostic(params)  # type: ignore[arg-type]

                diagnostics = self._parse_diagnostic_report(response, file_path)

                has_errors = any(d.severity == "error" for d in diagnostics)
                has_warnings = any(d.severity == "warning" for d in diagnostics)

                error_count = sum(1 for d in diagnostics if d.severity == "error")
                warning_count = sum(1 for d in diagnostics if d.severity == "warning")
                info_count = sum(1 for d in diagnostics if d.severity == "info")
                hint_count = sum(1 for d in diagnostics if d.severity == "hint")

                summary_parts = []
                if error_count > 0:
                    summary_parts.append(
                        f"{error_count} error{'s' if error_count != 1 else ''}"
                    )
                if warning_count > 0:
                    summary_parts.append(
                        f"{warning_count} warning{'s' if warning_count != 1 else ''}"
                    )
                if info_count > 0:
                    summary_parts.append(
                        f"{info_count} info item{'s' if info_count != 1 else ''}"
                    )
                if hint_count > 0:
                    summary_parts.append(
                        f"{hint_count} hint{'s' if hint_count != 1 else ''}"
                    )

                if summary_parts:
                    summary = "LSP found: " + ", ".join(summary_parts)
                else:
                    summary = "No LSP diagnostics found"

                return PostEditDiagnosticsResult(
                    diagnostics=diagnostics,
                    has_errors=has_errors,
                    has_warnings=has_warnings,
                    summary=summary,
                )

        except Exception as e:
            logger.warning(f"Failed to get diagnostics for {file_path}: {e}")
            return PostEditDiagnosticsResult(
                diagnostics=[],
                has_errors=False,
                has_warnings=False,
                summary=f"Diagnostics unavailable: {e!s}",
            )

    def _parse_diagnostic_report(
        self, response: Any, file_path: str
    ) -> list[Diagnostic]:
        """Parse LSP diagnostic report response into Diagnostic objects."""
        diagnostics = []

        try:
            if not response:
                return diagnostics

            if isinstance(response, dict):
                items = response.get("items", [])
                if not items and response.get("kind") == "full":
                    items = (
                        response
                        .get("relatedDocuments", {})
                        .get(Path(file_path).as_uri(), {})
                        .get("items", [])
                    )

                for item in items:
                    diagnostic = self._parse_lsp_diagnostic(item, file_path)
                    if diagnostic:
                        diagnostics.append(diagnostic)

            elif isinstance(response, list):
                for item in response:
                    diagnostic = self._parse_lsp_diagnostic(item, file_path)
                    if diagnostic:
                        diagnostics.append(diagnostic)

        except Exception as e:
            logger.warning(f"Error parsing diagnostic report: {e}")

        return diagnostics

    def _parse_lsp_diagnostic(
        self, lsp_diagnostic: dict, file_path: str
    ) -> Diagnostic | None:
        """Parse a single LSP diagnostic item into our Diagnostic model."""
        try:
            return Diagnostic(
                file_path=file_path,
                line=int(
                    lsp_diagnostic.get("range", {}).get("start", {}).get("line", 0)
                )
                + 1,
                character=int(
                    lsp_diagnostic.get("range", {}).get("start", {}).get("character", 0)
                ),
                severity=self._map_lsp_severity(lsp_diagnostic.get("severity")),
                message=str(lsp_diagnostic.get("message", "")),
                code=str(lsp_diagnostic.get("code", ""))
                if lsp_diagnostic.get("code")
                else None,
                source=str(lsp_diagnostic.get("source", ""))
                if lsp_diagnostic.get("source")
                else None,
            )
        except Exception as e:
            logger.warning(f"Error parsing LSP diagnostic: {e}")
            return None

    def _map_lsp_severity(self, lsp_severity: int | None) -> str:
        """Map LSP severity numbers to our string severity levels."""
        if lsp_severity is None:
            return "info"

        severity_map = {1: "error", 2: "warning", 3: "info", 4: "hint"}
        return severity_map.get(lsp_severity, "info")

    async def shutdown(self) -> None:
        """Shutdown all LSP servers."""
        for server in self.servers.values():
            try:
                await server.server.stop()
            except Exception as e:
                logger.warning(f"Error stopping LSP server: {e}")
        self.servers.clear()


_lsp_manager: LSPManager | None = None


def get_lsp_manager() -> LSPManager:
    """Get the global LSP manager instance."""
    global _lsp_manager
    if _lsp_manager is None:
        lsp_config = get_default_lsp_config()
        _lsp_manager = LSPManager(lsp_config)
    return _lsp_manager


async def shutdown_lsp_manager() -> None:
    """Shutdown the global LSP manager."""
    global _lsp_manager
    if _lsp_manager:
        await _lsp_manager.shutdown()
        _lsp_manager = None
