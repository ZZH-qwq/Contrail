"""Notebook List task: collect running notebook metrics."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from selenium.webdriver.common.by import By

from contrail.ai4s.base import BaseTask, WebDriverManager, capture_responses_json
from contrail.ai4s.config import Ai4sConfig


class NotebookListTask(BaseTask):
    def __init__(self, config: Ai4sConfig, via_scheduler: bool = False):
        super().__init__(
            name="ai4s_execute", target_url=config.urls.list_url, config=config, via_scheduler=via_scheduler
        )

    def execute(self, driver, manager: WebDriverManager) -> Any:
        logger.info("Executing task: collect AI4S running notebook metrics")

        self.screenshot(driver)
        self._apply_filter(driver)

        if driver.find_elements(By.CSS_SELECTOR, ".mf-notebook-list .ant-table-default .ant-table-placeholder"):
            logger.info("No data found")
            return {"state": "success"}

        rows = driver.find_elements(By.CSS_SELECTOR, ".mf-notebook-list .ant-table-tbody .ant-table-row-level-0")
        tasks_basic_info: List[Tuple[int, Dict[str, Any]]] = []

        for idx, row in enumerate(rows):
            logger.info(f"Collecting basic info for row {idx + 1}/{len(rows)}")
            task_info = self._collect_task_basic_info(driver, row)
            if task_info:
                tasks_basic_info.append((idx, task_info))
            else:
                logger.warning(f"Failed to collect basic info for row {idx}")
            time.sleep(0.5)

        logger.info(f"Collected {len(tasks_basic_info)} tasks, entering detail pages")
        data: Dict[Any, Any] = {"state": "success"}

        for idx, task_info in tasks_basic_info:
            logger.info(f"Getting details for task {idx + 1}/{len(tasks_basic_info)}: {task_info['task_name']}")
            complete_task = self._collect_task_detail_info(manager, task_info)
            data[idx] = complete_task
            if complete_task is None or "data" not in complete_task:
                data["state"] = "failed"
                logger.warning(f"Failed to get complete data for task: {task_info['task_name']}")

        logger.info("Detail collection complete")
        return data

    def validate(self, result: Any) -> bool:
        return isinstance(result, dict) and "state" in result

    def save(self, payload: Any) -> None:
        if payload is None:
            return
        save_dir = self.config.paths.save_path
        save_dir.mkdir(parents=True, exist_ok=True)
        main_path = save_dir / "ai4s_data.json"
        backup_path = save_dir / "ai4s_data_last_success.json"
        main_path.write_text(json.dumps(payload, ensure_ascii=False, indent=4), encoding="utf-8")
        if payload.get("state") == "success":
            backup_path.write_text(json.dumps(payload, ensure_ascii=False, indent=4), encoding="utf-8")
        logger.info(f"Saved payload to {main_path}")

    def _apply_filter(self, driver) -> None:
        logger.trace("Setting filter")
        try:
            filter_input = driver.find_element(
                By.CSS_SELECTOR,
                ".mf-notebook-list > .du-listpage-toolbar > .aibp-notebook-search-form > .ant-row > .ant-col.ant-col-24:nth-child(1) > .ant-row-flex > .ant-col.ant-col-8:nth-child(2) .ant-select-selection--multiple .ant-select-selection__placeholder",
            )
            self.screenshot(driver)
            filter_input.click()
        except Exception as exc:
            logger.error(f"Error setting filter: {exc}")
            time.sleep(0.5)

        time.sleep(0.5)
        self.screenshot(driver)

        select_item = driver.find_element(
            By.CSS_SELECTOR,
            ".ant-select-dropdown.ant-select-dropdown--multiple.ant-select-dropdown-placement-bottomLeft ul.ant-select-dropdown-menu.ant-select-dropdown-menu-root.ant-select-dropdown-menu-vertical > li.ant-select-dropdown-menu-item:nth-child(3)",
        )
        select_item.click()
        time.sleep(0.5)

        self.screenshot(driver)

        confirm_button = driver.find_element(
            By.CSS_SELECTOR,
            ".mf-notebook-list > .du-listpage-toolbar > .aibp-notebook-search-form > .ant-row > .ant-col.ant-col-24:nth-child(2) > .ant-row-flex > .ant-col.ant-col-8:nth-child(3) > .ant-form-item > .ant-col-offset-6 .button-info > .ant-btn:nth-child(1)",
        )
        confirm_button.click()
        time.sleep(0.5)

        self.screenshot(driver)

    def _collect_task_basic_info(self, driver, row) -> Optional[Dict[str, Any]]:
        try:
            task: Dict[str, Any] = {}

            task_name = row.find_element(By.CSS_SELECTOR, "td:nth-child(2)").text
            task["task_name"] = task_name

            active_time = row.find_element(By.CSS_SELECTOR, "td:nth-child(5)").text
            task["active_time"] = active_time

            resource = row.find_element(By.CSS_SELECTOR, "td:nth-child(6)").text.replace("\n", " ")
            normalized_resource = resource.replace("：", ":")
            task["resource_raw"] = normalized_resource

            try:
                parts = normalized_resource.split(":")
                task["cpus"] = parts[1].split(" ")[0]
                gpu_section = parts[2]
                task["gpu_type"] = gpu_section.split(" / ")[0].split(" ")[-1]
                task["gpu_count"] = gpu_section.split(" / ")[1].split(" ")[0]
                task["memory"] = parts[3].split(" ")[0]
            except Exception:
                logger.warning(f"Unexpected resource format: {normalized_resource}")
                task.setdefault("cpus", normalized_resource)
                task.setdefault("gpu_type", normalized_resource)
                task.setdefault("gpu_count", normalized_resource)
                task.setdefault("memory", normalized_resource)

            user = row.find_element(By.CSS_SELECTOR, "td:nth-last-child(2)").text
            task["user"] = user

            view_button = row.find_element(By.CSS_SELECTOR, "td:last-child > div > .table-action:nth-child(1)")
            detail_link = view_button.get_attribute("href")
            task["detail_link"] = detail_link

            logger.info(f"Collected basic info for task: {task_name}, User: {user}")
            logger.info(f"Resource: {resource}")

            return task
        except Exception as exc:
            logger.error(f"Error collecting basic task info: {exc}")
            return None

    def _collect_task_detail_info(self, driver_manager: WebDriverManager, task: Dict[str, Any]) -> Dict[str, Any]:
        if not task or not task.get("detail_link"):
            return task

        try:
            driver = driver_manager.get_driver()
            if not driver:
                logger.error("No valid driver available for detail collection")
                return task

            driver.get(task["detail_link"])
            time.sleep(2)
            self.screenshot(driver)

            try:
                start_time = driver.find_element(
                    By.CSS_SELECTOR,
                    ".mf-notebook-detail-box.aibp-detail-container div.ant-spin-container > div > div .aibp-detail-section:nth-child(1) .du-gridview > .du-gridview-row:nth-child(2) > .ant-col.ant-col-8:nth-child(1) div.du-gridview-row-content",
                ).text
                task["start_time"] = start_time
            except Exception as exc:
                logger.warning(f"Failed to get start_time for {task['task_name']}: {exc}")
                task["start_time"] = "N/A"

            try:
                driver.execute_script("console.clear();")
                time.sleep(0.5)
                json_data = self._collect_metrics(driver)
                if json_data:
                    task["data"] = json_data
                    logger.info(f"Successfully collected performance data for {task['task_name']}")
                else:
                    logger.warning(f"No performance data found for {task['task_name']}")
            except Exception as exc:
                logger.warning(f"Failed to get performance data for {task['task_name']}: {exc}")

            return task

        except Exception as exc:
            logger.error(f"Error getting task detail info for {task.get('task_name', 'unknown')}: {exc}")
            return task

    @staticmethod
    def _parse_metrics_from_response(payload: dict) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}
        frames = payload.get("results", {}).get("A", {}).get("frames", [])
        for frame in frames:
            query = frame.get("schema", {}).get("meta", {}).get("executedQueryString", "")
            data = frame.get("data")
            if "container_accelerator_duty_cycle" in query:
                metrics["accelerator_duty_cycle"] = data
            elif "container_accelerator_memory_used_bytes" in query:
                metrics["accelerator_memory_used_bytes"] = data
        return metrics

    @classmethod
    def _collect_metrics(cls, driver, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        collected: Dict[str, Any] = {}

        def matcher(response: dict) -> bool:
            url = response.get("url", "")
            mime = response.get("mimeType", "")
            return "monitor/api/ds/query" in url and "application/json" in mime

        payloads = capture_responses_json(driver, matcher=matcher, timeout=timeout)
        for payload in payloads:
            metrics = cls._parse_metrics_from_response(payload)
            collected.update(metrics)
            if "accelerator_duty_cycle" in collected and "accelerator_memory_used_bytes" in collected:
                break
        return collected or None


__all__ = ["NotebookListTask"]
