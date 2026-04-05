from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from vibe.core.tools.base import InvokeContext, ToolError
from vibe.core.tools.lsp.base_lsp_tool import BaseLSPTool
from vibe.core.types import ToolStreamEvent


class ParameterInfo(BaseModel):
    label: str = Field(description="Parameter label")
    documentation: str | None = Field(
        default=None, description="Parameter documentation"
    )


class SignatureInfo(BaseModel):
    label: str = Field(description="Signature label")
    documentation: str | None = Field(
        default=None, description="Signature documentation"
    )
    parameters: list[ParameterInfo] = Field(
        default_factory=list, description="Function parameters"
    )


class SignatureHelpArgs(BaseModel):
    file_path: str = Field(description="Path to the source file")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")


class SignatureHelpResult(BaseModel):
    signatures: list[SignatureInfo] = Field(
        default_factory=list, description="Available signatures"
    )
    active_signature: int = Field(description="Index of the active signature")
    active_parameter: int = Field(description="Index of the active parameter")
    has_signatures: bool = Field(description="Whether any signatures were found")
    file_path: str = Field(description="Path to the file")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")


class SignatureHelp(BaseLSPTool[SignatureHelpArgs, SignatureHelpResult]):
    """Get signature help at a cursor position using LSP."""

    description: ClassVar[str] = (
        "Get signature help at a cursor position using LSP. "
        "Returns function signature information, parameters, and documentation at the specified location."
    )

    async def run(
        self, args: SignatureHelpArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | SignatureHelpResult, None]:
        try:
            server_process = await self._ensure_server_running(args.file_path)

            params = self._create_position_params(
                args.file_path, args.line, args.character
            )

            async with server_process.start_server():
                response = await self._request_with_timeout(
                    server_process, "textDocument/signatureHelp", params
                )

            if not response:
                yield SignatureHelpResult(
                    signatures=[],
                    active_signature=0,
                    active_parameter=0,
                    has_signatures=False,
                    file_path=args.file_path,
                    line=args.line,
                    character=args.character,
                )
                return

            signatures = []
            active_signature = 0
            active_parameter = 0

            if isinstance(response, dict):
                active_signature = response.get("activeSignature", 0)
                active_parameter = response.get("activeParameter", 0)

                for sig in response.get("signatures", []):
                    signature_info = self._parse_signature(sig)
                    if signature_info:
                        signatures.append(signature_info)

            yield SignatureHelpResult(
                signatures=signatures,
                active_signature=active_signature,
                active_parameter=active_parameter,
                has_signatures=len(signatures) > 0,
                file_path=args.file_path,
                line=args.line,
                character=args.character,
            )

        except ToolError:
            raise
        except Exception as e:
            await self._handle_lsp_error(e, "signature help")

    def _parse_signature(self, sig: Any) -> SignatureInfo | None:
        """Parse a signature from LSP response."""
        try:
            if not isinstance(sig, dict):
                return None

            label = ""
            if isinstance(sig.get("label"), str):
                label = sig["label"]
            elif isinstance(sig.get("label"), list):
                label = " ".join(str(x) for x in sig["label"])

            documentation = None
            if "documentation" in sig:
                doc = sig["documentation"]
                if isinstance(doc, str):
                    documentation = doc
                elif isinstance(doc, dict):
                    documentation = doc.get("value", "")

            parameters = []
            for param in sig.get("parameters", []):
                param_info = self._parse_parameter(param)
                if param_info:
                    parameters.append(param_info)

            return SignatureInfo(
                label=label, documentation=documentation, parameters=parameters
            )
        except Exception:
            return None

    def _parse_parameter(self, param: Any) -> ParameterInfo | None:
        """Parse a parameter from LSP response."""
        try:
            if not isinstance(param, dict):
                return None

            label = ""
            if isinstance(param.get("label"), str):
                label = param["label"]
            elif isinstance(param.get("label"), list):
                label = " ".join(str(x) for x in param["label"])

            documentation = None
            if "documentation" in param:
                doc = param["documentation"]
                if isinstance(doc, str):
                    documentation = doc
                elif isinstance(doc, dict):
                    documentation = doc.get("value", "")

            return ParameterInfo(label=label, documentation=documentation)
        except Exception:
            return None
