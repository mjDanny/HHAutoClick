import logging

logger = logging.getLogger(__name__)


class Scheduler:
    def start(self) -> None:
        logger.info("scheduler skeleton started")

    def stop(self) -> None:
        logger.info("scheduler skeleton stopped")

