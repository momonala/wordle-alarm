import logging
import time

import schedule

from main import check_wordle_status, play_wordle_incognito

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _check_wordle_status():
    try:
        check_wordle_status()
    except Exception as e:
        logger.exception(e)


def _play_wordle_incognito():
    try:
        play_wordle_incognito()
    except Exception as e:
        logger.exception(e)


if __name__ == "__main__":
    times = ["10:00", "17:00", "20:00", "22:30", "23:30"]
    for _time in times:
        schedule.every().day.at(_time).do(_check_wordle_status)
    schedule.every().day.at("10:00").do(_play_wordle_incognito)
    logger.info("Init scheduler!")
    logger.info(f"⏰ {schedule.get_jobs()}")
    while True:
        schedule.run_pending()
        time.sleep(1)
