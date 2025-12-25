"""Scheduler for periodic AI4S tasks."""

from __future__ import annotations

import time

import schedule
from loguru import logger

from contrail.ai4s.config import Ai4sConfig
from contrail.ai4s.tasks import NotebookListTask


class Ai4sScheduler:
    def __init__(self, config: Ai4sConfig):
        self.config = config
        self.scheduler = schedule.Scheduler()
        self.list_task = NotebookListTask(config=self.config, via_scheduler=True)
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
        logger.info(f"Starting scheduler: list every {interval_list} min")

        # initial run
        self._run_task(self.list_task)

        self.scheduler.every(interval_list).minutes.do(self._run_task, self.list_task)

        try:
            while True:
                self.scheduler.run_pending()
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")


__all__ = ["Ai4sScheduler"]
