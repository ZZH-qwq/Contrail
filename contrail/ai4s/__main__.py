"""Default entrypoint for AI4S scheduler."""

from loguru import logger

from contrail.ai4s.config import Ai4sConfig
from contrail.ai4s.scheduler import Ai4sScheduler


def main():
    config = Ai4sConfig.load()
    logger.add("log/ai4s_scheduler_{time:YYYY-MM-DD}.log", rotation="00:00", retention="7 days", level="INFO")
    scheduler = Ai4sScheduler(config)
    scheduler.start()


if __name__ == "__main__":
    main()
