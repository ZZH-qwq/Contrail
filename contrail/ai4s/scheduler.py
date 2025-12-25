"""Scheduler for periodic AI4S tasks."""

from __future__ import annotations

import time

import schedule
from loguru import logger

from contrail.ai4s.config import Ai4sConfig
from contrail.ai4s.tasks import NotebookListTask, QuotaStatusTask


class Ai4sScheduler:
    def __init__(self, config: Ai4sConfig):
        self.config = config
        self.scheduler = schedule.Scheduler()
        self.list_task = NotebookListTask(config=self.config, via_scheduler=True)
        self.status_task = QuotaStatusTask(config=self.config, via_scheduler=True)
        self.config.ensure_directories()

    def _run_task(self, task):
        logger.info(f"Running task {task.name}")
        result = task.run()
        if hasattr(task, "save"):
            try:
                task.save(result)
            except Exception as exc:
                logger.error(f"Failed to persist result for {task.name}: {exc}")

    def start(self) -> None:
        interval_list = self.config.runtime.interval_list
        interval_status = self.config.runtime.interval_status
        logger.info(f"Starting scheduler: list every {interval_list} min, status every {interval_status} min")

        # initial run for both tasks
        self._run_task(self.list_task)
        self._run_task(self.status_task)

        self.scheduler.every(interval_list).minutes.do(self._run_task, self.list_task)
        self.scheduler.every(interval_status).minutes.do(self._run_task, self.status_task)

        try:
            while True:
                self.scheduler.run_pending()
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")


__all__ = ["Ai4sScheduler"]
