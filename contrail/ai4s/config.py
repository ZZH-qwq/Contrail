"""Configuration loading for AI4S tasks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "ai4s_config.json"


@dataclass
class CookieConfig:
    login_entry: str
    cookie_url: str
    cookie_path: Path


@dataclass
class Ai4sPaths:
    chromedriver_path: Path
    save_path: Path
    screenshot_path: Path


@dataclass
class TaskConfig:
    url: str
    scheduled: bool = True
    interval: int = 5
    params: Optional[Dict[str, Any]] = None


@dataclass
class TasksConfig:
    list: TaskConfig
    status: TaskConfig


@dataclass
class Ai4sConfig:
    cookie: CookieConfig
    paths: Ai4sPaths
    tasks: TasksConfig

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Ai4sConfig":
        path = config_path or DEFAULT_CONFIG_PATH
        data = json.loads(path.read_text(encoding="utf-8"))

        cookie_raw = data["cookie"]
        cookie = CookieConfig(
            login_entry=cookie_raw["login_entry"],
            cookie_url=cookie_raw["cookie_url"],
            cookie_path=BASE_DIR / cookie_raw["cookie_path"],
        )

        raw_paths = data["config"]
        paths = Ai4sPaths(
            chromedriver_path=BASE_DIR / raw_paths["chromedriver_path"],
            save_path=BASE_DIR / raw_paths["save_path"],
            screenshot_path=BASE_DIR / raw_paths["screenshot_path"],
        )

        tasks_raw = data["tasks"]
        tasks = TasksConfig(
            list=TaskConfig(**tasks_raw["list"]),
            status=TaskConfig(**tasks_raw["status"]),
        )

        return cls(cookie=cookie, paths=paths, tasks=tasks)

    def ensure_directories(self) -> None:
        self.paths.save_path.mkdir(parents=True, exist_ok=True)
        self.paths.screenshot_path.mkdir(parents=True, exist_ok=True)
        self.cookie.cookie_path.parent.mkdir(parents=True, exist_ok=True)


__all__ = [
    "Ai4sConfig",
    "Ai4sPaths",
    "CookieConfig",
    "TasksConfig",
    "TaskConfig",
    "DEFAULT_CONFIG_PATH",
    "BASE_DIR",
]
