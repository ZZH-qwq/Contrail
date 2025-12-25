"""Entry point for AI4S status task."""

from loguru import logger

from contrail.ai4s.config import Ai4sConfig
from contrail.ai4s.scheduler import Ai4sScheduler
from contrail.ai4s.tasks import QuotaStatusTask


def run_once(use_scheduler_mode: bool = False):
    config = Ai4sConfig.load()
    config.ensure_directories()

    task = QuotaStatusTask(config=config, via_scheduler=use_scheduler_mode)
    result = task.run()
    task.save(result)
    return result


def run_scheduler():
    config = Ai4sConfig.load()
    scheduler = Ai4sScheduler(config)
    scheduler.start()


if __name__ == "__main__":
    logger.add("log/ai4s_status_{time:YYYY-MM-DD}.log", rotation="00:00", retention="7 days", level="TRACE")
    run_once()
