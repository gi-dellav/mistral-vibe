from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import ClassVar

from pydantic import BaseModel, Field

from vibe.core.lsp.config import get_default_lsp_config
from vibe.core.lsp.manager import get_lsp_manager
from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    InvokeContext,
    ToolError,
)
from vibe.core.types import ToolStreamEvent


class LSPStatusResult(BaseModel):
    enabled: bool = Field(description="Whether LSP support is enabled")
    servers_configured: int = Field(description="Number of configured LSP servers")
    active_servers: int = Field(description="Number of currently active LSP servers")
    server_status: dict[str, str] = Field(
        description="Status of each configured server"
    )


class LSPStatus(BaseTool[BaseModel, LSPStatusResult, BaseToolConfig, BaseToolState]):
    """Get current LSP status and server information."""

    description: ClassVar[str] = (
        "Get current LSP status and server information. "
        "Shows which LSP servers are configured and active."
    )

    async def run(
        self, args: BaseModel, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | LSPStatusResult, None]:
        try:
            lsp_manager = get_lsp_manager()

            server_status = {}
            for server_id, server_config in lsp_manager.config.servers.items():
                status = "disabled" if not server_config.enabled else "configured"

                # Check if server is active (exists in servers dict)
                for server_key in lsp_manager.servers:
                    if server_key.startswith(f"{server_id}:"):
                        status = "active"
                        break

                server_status[server_id] = status

            yield LSPStatusResult(
                enabled=lsp_manager.config.enabled,
                servers_configured=len(lsp_manager.config.servers),
                active_servers=len(lsp_manager.servers),
                server_status=server_status,
            )

        except Exception as e:
            raise ToolError(f"Failed to get LSP status: {e!s}")


class LSPRestartResult(BaseModel):
    success: bool = Field(description="Whether the restart was successful")
    message: str = Field(description="Status message")


class LSPRestart(BaseTool[BaseModel, LSPRestartResult, BaseToolConfig, BaseToolState]):
    """Restart all LSP servers."""

    description: ClassVar[str] = (
        "Restart all LSP servers. "
        "Useful if servers become unresponsive or need to be refreshed."
    )

    async def run(
        self, args: BaseModel, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | LSPRestartResult, None]:
        try:
            lsp_manager = get_lsp_manager()

            # Shutdown all servers
            await lsp_manager.shutdown()

            yield LSPRestartResult(
                success=True,
                message="All LSP servers have been shut down and will be restarted on next use",
            )

        except Exception as e:
            raise ToolError(f"Failed to restart LSP servers: {e!s}")


class LSPConfigureArgs(BaseModel):
    action: str = Field(
        description="Configuration action: 'enable', 'disable', or 'reset'"
    )
    server: str | None = Field(
        default=None, description="Specific server to configure (optional)"
    )


class LSPConfigureResult(BaseModel):
    success: bool = Field(description="Whether the configuration was successful")
    message: str = Field(description="Configuration result message")
    new_status: dict[str, str] = Field(description="New configuration status")


class LSPConfigure(
    BaseTool[LSPConfigureArgs, LSPConfigureResult, BaseToolConfig, BaseToolState]
):
    """Configure LSP settings and servers."""

    description: ClassVar[str] = (
        "Configure LSP settings and servers. "
        "Can enable/disable LSP globally or for specific servers."
    )

    async def run(
        self, args: LSPConfigureArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | LSPConfigureResult, None]:
        try:
            lsp_manager = get_lsp_manager()
            new_status = {}

            if args.action == "reset":
                # Reset to default configuration
                lsp_manager.config = get_default_lsp_config()
                message = "LSP configuration reset to defaults"

            elif args.action == "enable":
                if args.server:
                    # Enable specific server
                    if args.server in lsp_manager.config.servers:
                        lsp_manager.config.servers[args.server].enabled = True
                        message = f"Enabled LSP server: {args.server}"
                    else:
                        raise ToolError(f"Unknown LSP server: {args.server}")
                else:
                    # Enable LSP globally
                    lsp_manager.config.enabled = True
                    message = "LSP support enabled globally"

            elif args.action == "disable":
                if args.server:
                    # Disable specific server
                    if args.server in lsp_manager.config.servers:
                        lsp_manager.config.servers[args.server].enabled = False
                        message = f"Disabled LSP server: {args.server}"
                    else:
                        raise ToolError(f"Unknown LSP server: {args.server}")
                else:
                    # Disable LSP globally
                    lsp_manager.config.enabled = False
                    message = "LSP support disabled globally"
            else:
                raise ToolError(f"Unknown configuration action: {args.action}")

            # Update status
            for server_id, server_config in lsp_manager.config.servers.items():
                status = "disabled" if not server_config.enabled else "enabled"
                new_status[server_id] = status

            yield LSPConfigureResult(
                success=True, message=message, new_status=new_status
            )

        except Exception as e:
            raise ToolError(f"Failed to configure LSP: {e!s}")


# TODO: Add more LSP management commands as needed
# TODO: Add command to list available LSP servers
# TODO: Add command to show detailed server information
# TODO: Add command to test server connectivity
# TODO: Add command to show LSP logs and debugging info
