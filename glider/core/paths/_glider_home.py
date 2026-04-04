from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path

from glider import GLIDER_ROOT


class GlobalPath:
    def __init__(self, resolver: Callable[[], Path]) -> None:
        self._resolver = resolver

    @property
    def path(self) -> Path:
        return self._resolver()


_DEFAULT_GLIDER_HOME = Path.home() / ".glider"


def _get_glider_home() -> Path:
    if glider_home := os.getenv("GLIDER_HOME"):
        return Path(glider_home).expanduser().resolve()
    return _DEFAULT_GLIDER_HOME


GLIDER_HOME = GlobalPath(_get_glider_home)
GLOBAL_ENV_FILE = GlobalPath(lambda: GLIDER_HOME.path / ".env")
SESSION_LOG_DIR = GlobalPath(lambda: GLIDER_HOME.path / "logs" / "session")
TRUSTED_FOLDERS_FILE = GlobalPath(lambda: GLIDER_HOME.path / "trusted_folders.toml")
LOG_DIR = GlobalPath(lambda: GLIDER_HOME.path / "logs")
LOG_FILE = GlobalPath(lambda: GLIDER_HOME.path / "logs" / "glider.log")
HISTORY_FILE = GlobalPath(lambda: GLIDER_HOME.path / "gliderhistory")
PLANS_DIR = GlobalPath(lambda: GLIDER_HOME.path / "plans")

DEFAULT_TOOL_DIR = GlobalPath(lambda: GLIDER_ROOT / "core" / "tools" / "builtins")
LSP_TOOL_DIR = GlobalPath(lambda: GLIDER_ROOT / "core" / "tools" / "lsp")
