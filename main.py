import json
import logging
import re
from contextlib import contextmanager
from datetime import datetime

import requests
from playwright.sync_api import sync_playwright

from values import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_cookies() -> list[dict]:
    """Load cookies from cookies.json file."""
    with open("assets/cookies.json", "r") as f:
        return json.load(f)


def send_telegram_alert(message: str):
    """Send notification message to Telegram"""
    message = f"🚨 {message} 🚨"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}

    try:
        requests.post(url, json=payload, timeout=10)
        logger.info(f"{message}. Telegram alert sent.")
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")


@contextmanager
def playwright_context():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


def dump_page_content_to_file(page) -> None:
    """Dump page content to a specified file."""
    page_content = page.content()
    with open("tmp/wordle_page_dump.html", "w", encoding="utf-8") as file:
        file.write(page_content)
    logger.info(f"Page content dumped to tmp/wordle_page_dump.html")


def check_wordle_status() -> dict[str, bool]:
    """Check if today's Wordle has been played."""
    wordle_url = "https://www.nytimes.com/games/wordle/index.html"
    logger.info(f"Starting Wordle check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    with playwright_context() as browser:
        context = browser.new_context()
        context = browser.new_context(storage_state="assets/auth.json")
        page = context.new_page()

        page.goto(wordle_url)
        context.storage_state(path="assets/auth.json")
        page.wait_for_timeout(5000)  # Pause to load the page
        play_button = page.get_by_test_id("Play").count()
        continue_button = page.get_by_test_id("Continue").count()

        if play_button:
            logger.info("Game is not played today")
            has_finished = False
            send_telegram_alert("Wordle not played today!")
        elif continue_button:
            logger.info("Game started today")
            has_finished = False
            send_telegram_alert("Wordle not finished today!")
        else:
            logger.info("Game is played today!")
            has_finished = True

            page.get_by_test_id("See Stats").click()
            page.wait_for_timeout(1000)  # Pause to load the page
            html = page.content()
            patterns = {
                "played": r"Number of games played, (\d+)",
                "win_percentage": r"Win percentage, (\d+)",
                "current_streak": r"Current Streak count, (\d+)",
                "max_streak": r"Max Streak count, (\d+)",
            }
            stats = {
                key: int(re.search(pattern, html).group(1)) if re.search(pattern, html) else None
                for key, pattern in patterns.items()
            }
            logger.info(
                f"Games Played: {stats['played']}, Win %: {stats['win_percentage']}, "
                f"Current Streak: {stats['current_streak']}, Max Streak: {stats['max_streak']}"
            )

    return {"played_today": has_finished}


if __name__ == "__main__":
    result = check_wordle_status()
