import logging
import time

import schedule

from src.daily_cache import is_played
from src.main import RunMode, check_wordle_status, play_wordle_incognito

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _check_wordle_status():
    if is_played():
        logger.info("Wordle already played today, skipping check")
        return
    try:
        check_wordle_status(mode=RunMode.REAL)
    except Exception:
        logger.exception("Job failed")


def _play_wordle_incognito():
    try:
        play_wordle_incognito(mode=RunMode.REAL)
    except Exception:
        logger.exception("Job failed")


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
