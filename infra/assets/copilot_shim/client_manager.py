import asyncio
import logging
import os
from typing import Optional

from copilot import CopilotClient

from .cli_path import get_copilot_cli_path


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
                cli_path = get_copilot_cli_path()
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
