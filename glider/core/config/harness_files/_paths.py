from __future__ import annotations

from glider.core.paths import GLIDER_HOME, GlobalPath

GLOBAL_TOOLS_DIR = GlobalPath(lambda: GLIDER_HOME.path / "tools")
GLOBAL_SKILLS_DIR = GlobalPath(lambda: GLIDER_HOME.path / "skills")
GLOBAL_AGENTS_DIR = GlobalPath(lambda: GLIDER_HOME.path / "agents")
GLOBAL_PROMPTS_DIR = GlobalPath(lambda: GLIDER_HOME.path / "prompts")
