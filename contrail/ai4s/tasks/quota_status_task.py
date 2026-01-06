"""Quota Status task: fetch available quota information."""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from loguru import logger
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

from contrail.ai4s.base import BaseTask, WebDriverManager, capture_responses_json
from contrail.ai4s.config import Ai4sConfig


class QuotaStatusTask(BaseTask):
    def __init__(self, config: Ai4sConfig, via_scheduler: bool = False):
        super().__init__(
            name="ai4s_status", target_url=config.tasks.status.url, config=config, via_scheduler=via_scheduler
        )

    def execute(self, driver, manager: WebDriverManager) -> Any:
        logger.info("Executing task: fetch AI4S quota status")
        driver.execute_script("console.clear();")

        new_task_button = driver.find_element(
            By.CSS_SELECTOR, ".mf-notebook-list .du-listpage-toolbar-left .ant-btn-primary"
        )
        new_task_button.click()
        time.sleep(1)
        self.screenshot(driver)

        self._create_notebook_task(driver)

        target_resource = self._capture_target_resource(driver)

        self._set_task_resource(driver)

        json_data = self._capture_status_json(driver)
        if json_data is None or "result" not in json_data:
            logger.error("Failed to retrieve JSON data for task status")
            return None

        json_data["resource_info"] = target_resource

        return json_data

    def _create_notebook_task(self, driver) -> None:
        logger.info("Creating new notebook task")
        try:
            resource_dropdown = driver.find_element(
                By.CSS_SELECTOR, ".ant-drawer-body #computeResourceId .ant-select-selection"
            )
            resource_dropdown.click()
            time.sleep(0.5)
            self.screenshot(driver)
        except Exception as exc:
            logger.error(f"Error creating notebook task: {exc}")

    def _set_task_resource(self, driver) -> None:
        logger.info("Setting task resource configuration")
        try:
            actions = ActionChains(driver)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            time.sleep(0.5)
            self.screenshot(driver)
        except Exception as exc:
            logger.error(f"Error setting task resource configuration: {exc}")

    def _capture_target_resource(self, driver) -> Optional[list]:
        def matcher(response: dict) -> bool:
            url = response.get("url", "")
            mime = response.get("mimeType", "")
            return "compute-resource/list" in url and "application/json" in mime

        payloads = capture_responses_json(driver, matcher=matcher, timeout=10, max_count=1)
        resource_list = payloads[0] if payloads else None
        if resource_list is None or "page" not in resource_list:
            logger.error("Resource list JSON not found or invalid")
            return None

        for resource in resource_list["page"].get("result", []):
            if "name" in resource and self.config.tasks.status.params.get("resource_name", "") == resource["name"]:
                logger.info(f"Found target resource: {resource['name']}")
                return resource

        logger.error("Target resource not found in resource list")
        return None

    def _capture_status_json(self, driver) -> Optional[dict]:
        def matcher(response: dict) -> bool:
            url = response.get("url", "")
            mime = response.get("mimeType", "")
            return "compute-resource/available-quota" in url and "application/json" in mime

        payloads = capture_responses_json(driver, matcher=matcher, timeout=10, max_count=1)
        return payloads[0] if payloads else None

    def validate(self, result: Any) -> bool:
        return result is not None

    def save(self, payload: Any) -> None:
        if payload is None:
            return
        save_dir = self.config.paths.save_path
        save_dir.mkdir(parents=True, exist_ok=True)
        target = save_dir / "ai4s_quota_status.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=4), encoding="utf-8")
        logger.info(f"Saved quota status to {target}")


__all__ = ["QuotaStatusTask"]
