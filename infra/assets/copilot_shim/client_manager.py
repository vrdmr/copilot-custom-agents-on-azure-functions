import asyncio
import logging
import os
import stat
import tempfile
from typing import Optional

from copilot import CopilotClient

from .cli_path import get_copilot_cli_path
from .config import resolve_config_dir

_WRAPPER_PATH = os.path.join(tempfile.gettempdir(), "copilot-wrapper.sh")


def _get_cli_path_with_config_dir() -> str:
    """
    Return the CLI path to use. When a custom config_dir is resolved,
    creates a shell wrapper that injects --config-dir at startup
    (workaround for CLI bug where session.resume ignores configDir).
    """
    cli_path = get_copilot_cli_path()
    config_dir = resolve_config_dir()

    if not config_dir:
        return cli_path

    wrapper_content = f'#!/bin/sh\nexec "{cli_path}" --config-dir "{config_dir}" "$@"\n'

    # Only rewrite if content changed or doesn't exist
    needs_write = True
    if os.path.exists(_WRAPPER_PATH):
        with open(_WRAPPER_PATH, "r") as f:
            needs_write = f.read() != wrapper_content

    if needs_write:
        with open(_WRAPPER_PATH, "w") as f:
            f.write(wrapper_content)
        os.chmod(_WRAPPER_PATH, stat.S_IRWXU)

    print(f"[ClientManager] Using wrapper: {_WRAPPER_PATH} (config_dir={config_dir})")
    return _WRAPPER_PATH


class CopilotClientManager:
    """
    Singleton manager for the CopilotClient.
    """

    _instance: Optional["CopilotClientManager"] = None
    _client: Optional[CopilotClient] = None
    _lock: asyncio.Lock = None
    _started: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._lock = asyncio.Lock()
        return cls._instance

    @classmethod
    async def get_client(cls) -> CopilotClient:
        manager = cls()
        async with manager._lock:
            if manager._client is None or not manager._started:
                cli_path = _get_cli_path_with_config_dir()
                github_token = os.environ.get("GITHUB_TOKEN")
                print("got github token:", github_token is not None)
                manager._client = CopilotClient(
                    {
                        "cli_path": cli_path,
                        "github_token": github_token,
                    }  # type: ignore
                )
                await manager._client.start()
                manager._started = True
                logging.info(f"CopilotClient singleton started (CLI: {cli_path})")
        return manager._client

    @classmethod
    async def shutdown(cls):
        manager = cls()
        async with manager._lock:
            if manager._client and manager._started:
                await manager._client.stop()
                manager._started = False
                manager._client = None
                logging.info("CopilotClient singleton stopped")

    @classmethod
    def is_running(cls) -> bool:
        manager = cls()
        return manager._started
