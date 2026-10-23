import logging
import subprocess
import sys
import time
from collections.abc import Callable

import schedule

from src.daily_cache import is_played
from src.main import RunMode
from src.main import check_wordle_status
from src.main import play_wordle_incognito
from src.main import send_telegram_alert

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _run_and_alert_on_failure(job: Callable[..., object]) -> None:
    try:
        job(mode=RunMode.REAL)
    except Exception as e:
        logger.exception("Job failed")
        send_telegram_alert(f"Wordle alarm job {job.__name__} failed: {e}")


def _check_wordle_status():
    if is_played():
        logger.info("Wordle already played today, skipping check")
        return
    _run_and_alert_on_failure(check_wordle_status)


def _play_wordle_incognito():
    _run_and_alert_on_failure(play_wordle_incognito)


def _install_browser() -> None:
    """Fetch the Chromium build the installed Playwright expects; a no-op when it is already present."""
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(f"Playwright browser install failed: {result.stderr}")
        send_telegram_alert(f"Wordle alarm could not install Chromium: {result.stderr[-500:]}")


if __name__ == "__main__":
    _install_browser()
    times = ["10:00", "17:00", "20:00", "22:30", "23:30"]
    for _time in times:
        schedule.every().day.at(_time).do(_check_wordle_status)
    schedule.every().day.at("10:00").do(_play_wordle_incognito)
    logger.info("Init scheduler!")
    logger.info(f"⏰ {schedule.get_jobs()}")
    while True:
        schedule.run_pending()
        time.sleep(1)
