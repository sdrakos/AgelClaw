"""Background worker — RQ job processor + schedule checker loop.

Usage:
    python worker.py
"""
import logging
import sys
import time
import threading

from redis import Redis
from rq import Worker, Queue

from config import REDIS_URL
from jobs import check_and_enqueue_schedules

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("timologia.worker")

CHECK_INTERVAL = 60  # seconds


def scheduler_loop(queue: Queue):
    """Periodically check schedules and enqueue due jobs."""
    logger.info("Scheduler loop started (check every %ds)", CHECK_INTERVAL)
    while True:
        try:
            check_and_enqueue_schedules(queue=queue)
        except Exception as e:
            logger.error("Scheduler error: %s", e, exc_info=True)
        time.sleep(CHECK_INTERVAL)


def main():
    logger.info("Starting Timologia worker...")

    redis_conn = Redis.from_url(REDIS_URL)
    queue = Queue("timologia", connection=redis_conn)

    # Start scheduler in a daemon thread
    sched_thread = threading.Thread(
        target=scheduler_loop, args=(queue,), daemon=True, name="scheduler"
    )
    sched_thread.start()
    logger.info("Scheduler thread started")

    # Start RQ worker in main thread
    worker = Worker([queue], connection=redis_conn, name="timologia-worker")
    logger.info("RQ worker listening on queue 'timologia'")
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
