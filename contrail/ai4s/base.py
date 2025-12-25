"""Shared utilities, driver management, and task framework for AI4S automation."""

from __future__ import annotations

import abc
import json
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from loguru import logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from contrail.ai4s.config import Ai4sConfig


def take_screenshot(driver, task_name: str, screenshot_dir: Path, enabled: bool) -> Optional[Path]:
    """Capture a screenshot of the body if enabled."""
    if not enabled:
        return None

    screenshot_dir.mkdir(parents=True, exist_ok=True)
    target_path = screenshot_dir / f"{task_name}.png"
    try:
        body = driver.find_element(By.XPATH, "/html/body")
        body.screenshot(str(target_path))
        logger.debug(f"Saved screenshot to {target_path}")
        return target_path
    except Exception as exc:  # pragma: no cover - best effort only
        logger.warning(f"Failed to take screenshot for {task_name}: {exc}")
        return None


def capture_response_json(
    driver,
    matcher: Callable[[dict], bool],
    timeout: float = 10.0,
) -> Optional[dict]:
    """Capture the first JSON response whose response metadata matches matcher."""
    start_time = time.time()
    while (time.time() - start_time) < timeout:
        try:
            logs = driver.get_log("performance")
            for entry in logs:
                message = json.loads(entry["message"]).get("message", {})
                if message.get("method") != "Network.responseReceived":
                    continue

                response = message.get("params", {}).get("response", {})
                if not matcher(response):
                    continue

                request_id = message.get("params", {}).get("requestId")
                if not request_id:
                    continue

                try:
                    response_body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
                    body_data = response_body.get("body", "") if response_body else ""
                    return json.loads(body_data)
                except json.JSONDecodeError as exc:
                    logger.error(f"Error parsing JSON data: {exc}")
                except Exception as exc:  # pragma: no cover - runtime dependency
                    logger.error(f"Error getting response body: {exc}")
                    continue

        except Exception as exc:
            logger.error(f"Error reading performance logs: {exc}")
            return None

        time.sleep(0.5)

    return None


def capture_responses_json(
    driver,
    matcher: Callable[[dict], bool],
    timeout: float = 10.0,
    max_count: Optional[int] = None,
) -> list[dict]:
    """Capture multiple JSON responses whose response metadata matches matcher.

    Returns all matched payloads within timeout (or up to max_count if provided).
    Deduplicates by requestId to avoid duplicates from repeated log reads.
    """
    start_time = time.time()
    results: list[dict] = []
    seen: set[str] = set()

    while (time.time() - start_time) < timeout:
        try:
            logs = driver.get_log("performance")
            for entry in logs:
                message = json.loads(entry["message"]).get("message", {})
                if message.get("method") != "Network.responseReceived":
                    continue

                params = message.get("params", {})
                response = params.get("response", {})
                request_id = params.get("requestId")
                if not matcher(response) or not request_id or request_id in seen:
                    continue

                seen.add(request_id)
                try:
                    response_body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
                    body_data = response_body.get("body", "") if response_body else ""
                    results.append(json.loads(body_data))
                    if max_count and len(results) >= max_count:
                        return results
                except json.JSONDecodeError as exc:
                    logger.error(f"Error parsing JSON data: {exc}")
                except Exception as exc:  # pragma: no cover
                    logger.error(f"Error getting response body: {exc}")
                    continue

        except Exception as exc:
            logger.error(f"Error reading performance logs: {exc}")
            return results

        time.sleep(0.5)

    return results


class WebDriverManager:
    """Manage Chrome WebDriver lifecycle with cookies-based login."""

    def __init__(self, config: Ai4sConfig, target_url: str, headless: bool = True):
        self.config = config
        self.target_url = target_url
        self.headless = headless
        self.driver = None
        self.options = None
        self.service = None
        self._setup_options()

    def _setup_options(self) -> None:
        self.options = Options()
        if self.headless:
            self.options.add_argument("--headless")
        self.options.add_argument("--enable-logging")
        self.options.add_argument("--auto-open-devtools-for-tabs")
        self.options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        self.service = Service(str(self.config.paths.chromedriver_path))

    def _create_driver(self, retries: int = 2) -> bool:
        logger.info("Creating new WebDriver instance")
        last_exception: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                if self.driver:
                    try:
                        self.driver.quit()
                    except Exception:
                        pass

                self.driver = webdriver.Chrome(service=self.service, options=self.options)
                self.driver.set_window_size(1920, 2333)
                logger.info(f"WebDriver created successfully on attempt {attempt}")
                return True
            except Exception as exc:
                logger.error(f"Failed to create WebDriver on attempt {attempt}: {exc}")
                last_exception = exc
                time.sleep(1)
        logger.error(f"All {retries} attempts to create WebDriver failed: {last_exception}")
        return False

    def _login(self) -> bool:
        if not self.driver:
            return False
        try:
            cookies_path = self.config.paths.cookies_path
            cookies = json.loads(cookies_path.read_text(encoding="utf-8"))

            new_expiry_time = int(time.time()) + 86400 * 30
            for cookie in cookies:
                if "expiry" in cookie:
                    cookie["expires"] = new_expiry_time

            self.driver.get("http://aiplatform.ai4s.sjtu.edu.cn/")
            time.sleep(0.5)

            for cookie in cookies:
                self.driver.add_cookie(cookie)

            self.driver.get(self.target_url)
            time.sleep(2)

            logger.info(f"Page title: {self.driver.title}")
            logger.info(f"Current URL: {self.driver.current_url}")

            if self.driver.current_url.find("login?projectType=NORMAL") != -1:
                logger.error("Login failed")
                return False

            logger.info("Login successful")
            return True
        except Exception as exc:
            logger.error(f"Login failed: {exc}")
            return False

    def is_session_valid(self) -> bool:
        if not self.driver:
            return False
        try:
            _ = self.driver.current_url
            return True
        except Exception as exc:
            if "invalid session id" in str(exc) or "session deleted" in str(exc):
                return False
            return True

    def ensure_session(self) -> bool:
        if not self.is_session_valid():
            logger.warning("WebDriver session is invalid, recreating...")
            if self._create_driver() and self._login():
                return True
            return False
        return True

    def get_driver(self):
        if self.ensure_session():
            return self.driver
        return None

    def close(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
            except Exception as exc:  # pragma: no cover
                logger.error(f"Error closing WebDriver: {exc}")
        self.driver = None

    def __enter__(self) -> "WebDriverManager":
        created = self._create_driver()
        if not created:
            raise RuntimeError("Failed to create WebDriver")
        if not self._login():
            raise RuntimeError("Failed to login with provided cookies")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class BaseTask(abc.ABC):
    """Base class for AI4S tasks."""

    def __init__(self, name: str, target_url: str, config: Ai4sConfig, via_scheduler: bool = False):
        self.name = name
        self.target_url = target_url
        self.config = config
        self.via_scheduler = via_scheduler
        self.result: Any = None
        self.success: bool = False

    def screenshot(self, driver) -> Optional[Path]:
        return take_screenshot(driver, self.name, self.config.paths.screenshot_path, enabled=not self.via_scheduler)

    def run(self) -> Any:
        try:
            with WebDriverManager(self.config, self.target_url) as manager:
                driver = manager.get_driver()
                if not driver:
                    self.success = False
                    return None
                self.result = self.execute(driver, manager)
                self.success = self.validate(self.result)
                return self.result
        except Exception as exc:
            logger.error(f"{self.name} task failed: {exc}")
            self.success = False
            return None

    @abc.abstractmethod
    def execute(self, driver, manager: WebDriverManager) -> Any:
        raise NotImplementedError

    def validate(self, result: Any) -> bool:
        return result is not None


__all__ = [
    "BaseTask",
    "WebDriverManager",
    "take_screenshot",
    "capture_response_json",
    "capture_responses_json",
]
