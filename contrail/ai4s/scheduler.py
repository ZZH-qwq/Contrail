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
        list_cfg = self.config.tasks.list
        status_cfg = self.config.tasks.status

        logger.info(
            "Starting scheduler: list({}) every {} min, status({}) every {} min",
            "on" if list_cfg.scheduled else "off",
            list_cfg.interval,
            "on" if status_cfg.scheduled else "off",
            status_cfg.interval,
        )

        if list_cfg.scheduled:
            self._run_task(self.list_task)
            self.scheduler.every(list_cfg.interval).minutes.do(self._run_task, self.list_task)

        if status_cfg.scheduled:
            self._run_task(self.status_task)
            self.scheduler.every(status_cfg.interval).minutes.do(self._run_task, self.status_task)

        try:
            while True:
                self.scheduler.run_pending()
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")


__all__ = ["Ai4sScheduler"]
