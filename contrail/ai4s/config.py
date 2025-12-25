"""Configuration loading for AI4S tasks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "ai4s_config.json"


@dataclass
class RuntimeConfig:
    interval_list: int = 5


@dataclass
class Ai4sPaths:
    chromedriver_path: Path
    cookies_path: Path
    save_path: Path
    screenshot_path: Path


@dataclass
class Ai4sUrls:
    login_entry: str
    save_cookies: str
    list_url: str


@dataclass
class Ai4sConfig:
    urls: Ai4sUrls
    paths: Ai4sPaths
    runtime: RuntimeConfig

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Ai4sConfig":
        path = config_path or DEFAULT_CONFIG_PATH
        data = json.loads(path.read_text(encoding="utf-8"))

        urls = Ai4sUrls(**data["url"])
        raw_paths = data["config"]
        paths = Ai4sPaths(
            chromedriver_path=BASE_DIR / raw_paths["chromedriver_path"],
            cookies_path=BASE_DIR / raw_paths["cookies_path"],
            save_path=BASE_DIR / raw_paths["save_path"],
            screenshot_path=BASE_DIR / raw_paths["screenshot_path"],
        )
        runtime = RuntimeConfig(**data.get("runtime", {}))
        return cls(urls=urls, paths=paths, runtime=runtime)

    def ensure_directories(self) -> None:
        self.paths.save_path.mkdir(parents=True, exist_ok=True)
        self.paths.screenshot_path.mkdir(parents=True, exist_ok=True)
        self.paths.cookies_path.parent.mkdir(parents=True, exist_ok=True)


__all__ = [
    "Ai4sConfig",
    "Ai4sPaths",
    "Ai4sUrls",
    "RuntimeConfig",
    "DEFAULT_CONFIG_PATH",
    "BASE_DIR",
]
