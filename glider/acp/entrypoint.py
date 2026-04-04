from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
import sys

import tomli_w

from glider import __version__
from glider.core.config import MissingAPIKeyError, GliderConfig
from glider.core.config.harness_files import (
    get_harness_files_manager,
    init_harness_files_manager,
)
from glider.core.logger import logger
from glider.core.paths import HISTORY_FILE

# Configure line buffering for subprocess communication
sys.stdout.reconfigure(line_buffering=True)  # pyright: ignore[reportAttributeAccessIssue]
sys.stderr.reconfigure(line_buffering=True)  # pyright: ignore[reportAttributeAccessIssue]
sys.stdin.reconfigure(line_buffering=True)  # pyright: ignore[reportAttributeAccessIssue]


@dataclass
class Arguments:
    setup: bool


def parse_arguments() -> Arguments:
    parser = argparse.ArgumentParser(description="Run Glider for Mistral in ACP mode")
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--setup", action="store_true", help="Setup API key and exit")
    args = parser.parse_args()
    return Arguments(setup=args.setup)


def bootstrap_config_files() -> None:
    mgr = get_harness_files_manager()
    config_file = mgr.user_config_file
    if not config_file.exists():
        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with config_file.open("wb") as f:
                tomli_w.dump(GliderConfig.create_default(), f)
        except Exception as e:
            logger.error(f"Could not create default config file: {e}")
            raise

    history_file = HISTORY_FILE.path
    if not history_file.exists():
        try:
            history_file.parent.mkdir(parents=True, exist_ok=True)
            history_file.write_text("Hello Glider!\n", "utf-8")
        except Exception as e:
            logger.error(f"Could not create history file: {e}")
            raise


def handle_debug_mode() -> None:
    if os.environ.get("DEBUG_MODE") != "true":
        return

    try:
        import debugpy
    except ImportError:
        return

    debugpy.listen(("localhost", 5678))
    # uncomment this to wait for the debugger to attach
    # debugpy.wait_for_client()


def main() -> None:
    handle_debug_mode()
    init_harness_files_manager("user", "project")

    from glider.acp.acp_agent_loop import run_acp_server
    from glider.core.config import GliderConfig, load_dotenv_values
    from glider.core.tracing import setup_tracing
    from glider.setup.onboarding import run_onboarding

    load_dotenv_values()
    bootstrap_config_files()
    args = parse_arguments()
    if args.setup:
        run_onboarding()
        sys.exit(0)

    try:
        config = GliderConfig.load()
        setup_tracing(config)
    except MissingAPIKeyError:
        pass  # tracing disabled, but server can still handle the error properly in new_session

    run_acp_server()


if __name__ == "__main__":
    main()
