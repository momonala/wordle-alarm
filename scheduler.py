import logging
import time

import schedule

from main import check_wordle_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    times = ["10:00", "17:00", "20:00", "22:30", "23:30"]
    for _time in times:
        schedule.every().day.at(_time).do(check_wordle_status)
    logger.info("Init scheduler!")
    logger.info(f"Scheduled jobs for {times}")
    while True:
        schedule.run_pending()
        time.sleep(1)
