from __future__ import annotations

import asyncio
import subprocess
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
from collections import defaultdict

from vibe.core.lsp.config import LSPServerConfig, LSPConfig, Diagnostic, PostEditDiagnosticsResult
from vibe.core.logger import logger


class LSPServerProcess:
    """Manages a single LSP server process."""
    
    def __init__(self, config: LSPServerConfig, workspace_root: Path):
        self.config = config
        self.workspace_root = workspace_root
        self.process: subprocess.Popen | None = None
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.request_id = 1
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.initialized = False
        
    async def start(self) -> None:
        """Start the LSP server process."""
        if self.process is not None:
            return
            
        try:
            # Prepare environment
            env = {**self.config.env}
            env.update({
                "PATH": self._get_path_with_env(),
                "LSP_WORKSPACE_ROOT": str(self.workspace_root),
            })
            
            # Start process
            self.process = await asyncio.create_subprocess_exec(
                *self.config.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.workspace_root,
                env=env,
            )
            
            # Create stream readers/writers
            self.reader = asyncio.StreamReader()
            self.writer = asyncio.StreamWriter(
                self.process.stdin, 
                self._create_stream_reader_protocol()
            )
            
            # Start reading messages
            asyncio.create_task(self._read_messages())
            
            # Send initialization request
            await self._send_initialize_request()
            
        except Exception as e:
            await self.stop()
            raise RuntimeError(f"Failed to start LSP server: {e}")
    
    async def stop(self) -> None:
        """Stop the LSP server process."""
        if self.process is None:
            return
        
        try:
            # Send exit notification
            if self.writer:
                exit_msg = {
                    "jsonrpc": "2.0",
                    "method": "exit",
                    "params": {}
                }
                self.writer.write((json.dumps(exit_msg) + "\r\n").encode())
                await self.writer.drain()
            
            # Terminate process
            self.process.terminate()
            await self.process.wait()
            
        except Exception:
            # Force kill if graceful shutdown fails
            self.process.kill()
            await self.process.wait()
        finally:
            self.process = None
            self.reader = None
            self.writer = None
            self.pending_requests.clear()
            self.initialized = False
    
    async def request(self, method: str, params: Any) -> Any:
        """Send a request to the LSP server and wait for response."""
        if not self.initialized:
            await self.start()
            
        future = asyncio.Future()
        request_id = self.request_id
        self.request_id += 1
        self.pending_requests[request_id] = future
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        if self.writer:
            self.writer.write((json.dumps(request) + "\r\n").encode())
            await self.writer.drain()
        
        try:
            return await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError:
            future.cancel()
            del self.pending_requests[request_id]
            raise RuntimeError("LSP request timed out")
    
    async def _send_initialize_request(self) -> None:
        """Send initialize request to LSP server."""
        init_params = {
            "processId": None,
            "rootUri": self.workspace_root.as_uri(),
            "capabilities": {
                "textDocument": {
                    "definition": {"dynamicRegistration": False},
                    "references": {"dynamicRegistration": False},
                    "documentSymbol": {"dynamicRegistration": False},
                    "implementation": {"dynamicRegistration": False},
                    "signatureHelp": {"dynamicRegistration": False},
                },
                "workspace": {
                    "symbol": {"dynamicRegistration": False},
                }
            },
            "initializationOptions": self.config.init_options,
        }
        
        response = await self.request("initialize", init_params)
        self.initialized = True
        
        # Send initialized notification
        initialized_msg = {
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {}
        }
        if self.writer:
            self.writer.write((json.dumps(initialized_msg) + "\r\n").encode())
            await self.writer.drain()
    
    async def _read_messages(self) -> None:
        """Read and process messages from the LSP server."""
        if not self.reader:
            return
        
        buffer = ""
        while True:
            try:
                data = await self.reader.read(4096)
                if not data:
                    break
                
                buffer += data.decode('utf-8', errors='ignore')
                
                # Process complete messages
                while "\r\n" in buffer:
                    message, buffer = buffer.split("\r\n", 1)
                    if message.strip():
                        await self._process_message(message)
                
            except Exception as e:
                logger.warning(f"Error reading LSP messages: {e}")
                break
    
    async def _process_message(self, message: str) -> None:
        """Process a single LSP message."""
        try:
            data = json.loads(message)
            
            if "id" in data:
                # This is a response to a request
                request_id = data["id"]
                if request_id in self.pending_requests:
                    future = self.pending_requests.pop(request_id)
                    if "error" in data:
                        future.set_exception(RuntimeError(data["error"]["message"]))
                    else:
                        future.set_result(data.get("result"))
            
            # TODO: Handle notifications (method field without id)
            # TODO: Handle publishDiagnostics for real-time diagnostics
            
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received from LSP server: {message}")
        except Exception as e:
            logger.warning(f"Error processing LSP message: {e}")
    
    def _create_stream_reader_protocol(self) -> asyncio.Protocol:
        """Create protocol for reading from subprocess stdout."""
        class LSPStreamProtocol(asyncio.Protocol):
            def __init__(self, outer_self):
                self.outer_self = outer_self
                self.buffer = b""
                
            def data_received(self, data: bytes) -> None:
                self.buffer += data
                
            def connection_lost(self, exc: Exception | None) -> None:
                if exc:
                    logger.warning(f"LSP stream connection lost: {exc}")
        
        return LSPStreamProtocol(self)
    
    def _get_path_with_env(self) -> str:
        """Get PATH environment variable including common locations."""
        # TODO: Add more common LSP server locations
        extra_paths = [
            str(Path.home() / ".local" / "bin"),
            str(Path.home() / ".cargo" / "bin"),
            "/usr/local/bin",
        ]
        
        existing_path = self.config.env.get("PATH", "")
        paths = existing_path.split(":") if existing_path else []
        
        for extra_path in extra_paths:
            if extra_path not in paths and Path(extra_path).exists():
                paths.append(extra_path)
        
        return ":".join(paths)


class LSPManager:
    """Central manager for LSP servers."""
    
    def __init__(self, config: LSPConfig):
        self.config = config
        self.servers: Dict[str, LSPServerProcess] = {}
        self.workspace_roots: Dict[str, Path] = {}
        self.file_to_server: Dict[str, str] = {}
        
    async def ensure_server_for_file(self, file_path: str) -> LSPServerProcess:
        """Ensure an LSP server is running for the given file."""
        if not self.config.enabled:
            raise RuntimeError("LSP support is disabled")
        
        file_path = str(Path(file_path).resolve())
        
        # Find appropriate server for this file
        server_id = self._find_server_for_file(file_path)
        if not server_id:
            raise RuntimeError(f"No LSP server configured for file: {file_path}")
        
        # Get workspace root
        workspace_root = self._find_workspace_root(file_path, server_id)
        
        # Get or create server process
        server_key = f"{server_id}:{workspace_root}"
        if server_key not in self.servers:
            server_config = self.config.servers[server_id]
            server_process = LSPServerProcess(server_config, workspace_root)
            self.servers[server_key] = server_process
        
        server_process = self.servers[server_key]
        
        # Start server if not running
        if not server_process.initialized:
            await server_process.start()
        
        return server_process
    
    def _find_server_for_file(self, file_path: str) -> str | None:
        """Find the appropriate LSP server for a file based on its extension."""
        file_ext = Path(file_path).suffix.lower()
        
        for server_id, server_config in self.config.servers.items():
            if not server_config.enabled:
                continue
            
            if file_ext in server_config.extensions:
                return server_id
        
        return None
    
    def _find_workspace_root(self, file_path: str, server_id: str) -> Path:
        """Find the workspace root for a file."""
        file_path = Path(file_path).resolve()
        server_config = self.config.servers[server_id]
        
        # Check if we already know the workspace root for this file
        if file_path in self.file_to_server:
            return self.workspace_roots[self.file_to_server[file_path]]
        
        # Find workspace root by looking for root markers
        current_dir = file_path.parent
        while current_dir != current_dir.parent:  # Stop at filesystem root
            for marker in server_config.root_markers:
                marker_path = current_dir / marker
                if marker_path.exists():
                    self.workspace_roots[str(current_dir)] = current_dir
                    self.file_to_server[str(file_path)] = str(current_dir)
                    return current_dir
            current_dir = current_dir.parent
        
        # No root markers found, use file directory
        self.workspace_roots[str(file_path.parent)] = file_path.parent
        self.file_to_server[str(file_path)] = str(file_path.parent)
        return file_path.parent
    
    async def get_diagnostics_for_file(self, file_path: str) -> PostEditDiagnosticsResult:
        """Get diagnostics for a file after editing using LSP textDocument/diagnostic request."""
        try:
            server_process = await self.ensure_server_for_file(file_path)
            
            # Request diagnostics using LSP textDocument/diagnostic method
            params = {
                "textDocument": {
                    "uri": Path(file_path).as_uri()
                }
            }
            
            # Send diagnostic request to LSP server
            response = await server_process.request("textDocument/diagnostic", params)
            
            # Parse the diagnostic report
            diagnostics = self._parse_diagnostic_report(response, file_path)
            
            # Categorize diagnostics
            has_errors = any(d.severity == "error" for d in diagnostics)
            has_warnings = any(d.severity == "warning" for d in diagnostics)
            
            # Generate summary
            error_count = sum(1 for d in diagnostics if d.severity == "error")
            warning_count = sum(1 for d in diagnostics if d.severity == "warning")
            info_count = sum(1 for d in diagnostics if d.severity == "info")
            hint_count = sum(1 for d in diagnostics if d.severity == "hint")
            
            summary_parts = []
            if error_count > 0:
                summary_parts.append(f"{error_count} error{'s' if error_count != 1 else ''}")
            if warning_count > 0:
                summary_parts.append(f"{warning_count} warning{'s' if warning_count != 1 else ''}")
            if info_count > 0:
                summary_parts.append(f"{info_count} info item{'s' if info_count != 1 else ''}")
            if hint_count > 0:
                summary_parts.append(f"{hint_count} hint{'s' if hint_count != 1 else ''}")
            
            if summary_parts:
                summary = "LSP found: " + ", ".join(summary_parts)
            else:
                summary = "No LSP diagnostics found"
            
            return PostEditDiagnosticsResult(
                diagnostics=diagnostics,
                has_errors=has_errors,
                has_warnings=has_warnings,
                summary=summary
            )
            
        except Exception as e:
            logger.warning(f"Failed to get diagnostics for {file_path}: {e}")
            return PostEditDiagnosticsResult(
                diagnostics=[],
                has_errors=False,
                has_warnings=False,
                summary=f"Diagnostics unavailable: {str(e)}"
            )
    
    def _parse_diagnostic_report(self, response: Any, file_path: str) -> list[Diagnostic]:
        """Parse LSP diagnostic report response into Diagnostic objects."""
        diagnostics = []
        
        try:
            # Handle FullDocumentDiagnosticReport
            if isinstance(response, dict) and response.get("kind") == "full":
                items = response.get("items", [])
                for item in items:
                    diagnostic = self._parse_lsp_diagnostic(item, file_path)
                    if diagnostic:
                        diagnostics.append(diagnostic)
            
            # Handle legacy diagnostic format (array of diagnostics)
            elif isinstance(response, list):
                for item in response:
                    diagnostic = self._parse_lsp_diagnostic(item, file_path)
                    if diagnostic:
                        diagnostics.append(diagnostic)
            
            # Handle UnchangedDocumentDiagnosticReport
            elif isinstance(response, dict) and response.get("kind") == "unchanged":
                # No new diagnostics, return empty list
                pass
            
        except Exception as e:
            logger.warning(f"Error parsing diagnostic report: {e}")
        
        return diagnostics
    
    def _parse_lsp_diagnostic(self, lsp_diagnostic: dict, file_path: str) -> Diagnostic | None:
        """Parse a single LSP diagnostic item into our Diagnostic model."""
        try:
            # Convert LSP diagnostic format to our format
            return Diagnostic(
                file_path=file_path,
                line=int(lsp_diagnostic.get("range", {}).get("start", {}).get("line", 0)) + 1,  # LSP uses 0-based, we use 1-based
                character=int(lsp_diagnostic.get("range", {}).get("start", {}).get("character", 0)),
                severity=self._map_lsp_severity(lsp_diagnostic.get("severity")),
                message=str(lsp_diagnostic.get("message", "")),
                code=str(lsp_diagnostic.get("code", "")) if lsp_diagnostic.get("code") else None,
                source=str(lsp_diagnostic.get("source", "")) if lsp_diagnostic.get("source") else None
            )
        except Exception as e:
            logger.warning(f"Error parsing LSP diagnostic: {e}")
            return None
    
    def _map_lsp_severity(self, lsp_severity: int | None) -> str:
        """Map LSP severity numbers to our string severity levels."""
        if lsp_severity is None:
            return "info"
        
        # LSP severity mapping: 1=Error, 2=Warning, 3=Info, 4=Hint
        severity_map = {
            1: "error",
            2: "warning", 
            3: "info",
            4: "hint"
        }
        
        return severity_map.get(lsp_severity, "info")
    
    async def shutdown(self) -> None:
        """Shutdown all LSP servers."""
        for server in self.servers.values():
            try:
                await server.stop()
            except Exception as e:
                logger.warning(f"Error stopping LSP server: {e}")
        self.servers.clear()


# Global LSP manager instance
_lsp_manager: LSPManager | None = None


def get_lsp_manager() -> LSPManager:
    """Get the global LSP manager instance."""
    global _lsp_manager
    if _lsp_manager is None:
        from vibe.core.config import get_global_config
        config = get_global_config()
        lsp_config = config.lsp if hasattr(config, 'lsp') else LSPConfig()
        _lsp_manager = LSPManager(lsp_config)
    return _lsp_manager


async def shutdown_lsp_manager() -> None:
    """Shutdown the global LSP manager."""
    global _lsp_manager
    if _lsp_manager:
        await _lsp_manager.shutdown()
        _lsp_manager = None