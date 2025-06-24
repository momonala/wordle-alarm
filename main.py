import logging
import re
from contextlib import contextmanager
from datetime import datetime

import requests
from playwright.sync_api import sync_playwright

from auth import load_cookies
from solver import GameMode, solve_wordle
from values import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

WORDLE_URL = "https://www.nytimes.com/games/wordle/index.html"
MODE = "REAL"


@contextmanager
def playwright_context():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False if MODE == "TEST" else True)
        yield browser
        browser.close()


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


def dump_page_content_to_file(page) -> None:
    """Dump page content to a specified file."""
    page_content = page.content()
    with open("tmp/wordle_page_dump.html", "w", encoding="utf-8") as file:
        file.write(page_content)
    logger.info(f"Page content dumped to tmp/wordle_page_dump.html")


def get_wordle_stats(page) -> dict[str, int]:
    html = page.content()
    patterns = {
        "played": r"Number of games played, (\d+)",
        "win_percentage": r"Win percentage, (\d+)",
        "current_streak": r"Current Streak count, (\d+)",
        "max_streak": r"Max Streak count, (\d+)",
    }
    return {
        key: int(re.search(pattern, html).group(1)) if re.search(pattern, html) else None
        for key, pattern in patterns.items()
    }


def _is_late_night() -> bool:
    return True
    return datetime.now().hour > 22


def check_wordle_status() -> dict[str, bool]:
    """Check if today's Wordle has been played."""
    logger.info(f"Starting Wordle check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    with playwright_context() as browser:
        context = browser.new_context()
        # context = browser.new_context(storage_state="assets/auth.json")
        page = context.new_page()

        # Load and set cookies before navigating
        cookies = [] #if MODE == "TEST" else load_cookies()
        context.add_cookies(cookies)
        logger.info("Loaded cookies for authentication")

        page.goto(WORDLE_URL)
        page.wait_for_timeout(2000)  # Pause to load the page

        play_button = page.get_by_test_id(GameMode.PLAY.value).count()
        continue_button = page.get_by_test_id(GameMode.CONTINUE.value).count()

        if play_button:
            logger.info("Game is not played today")
            has_finished = False
            send_telegram_alert("Wordle not played today!")
            if _is_late_night():
                score = solve_wordle(page, GameMode.PLAY)
                send_telegram_alert(f"Wordle auto-solved in {score} guesses!")
        elif continue_button:
            logger.info("Game started today")
            has_finished = False
            send_telegram_alert("Wordle not finished today!")
            if _is_late_night():
                score = solve_wordle(page, GameMode.CONTINUE)
                send_telegram_alert(f"Wordle auto-solved in {score} guesses!")
        else:
            logger.info("Game is played today!")
            has_finished = True

            page.get_by_test_id("See Stats").click()
            page.wait_for_timeout(1000)  # Pause to load the page
            stats = get_wordle_stats(page)

            logger.info(
                f"Games Played: {stats['played']}, Win %: {stats['win_percentage']}, "
                f"Current Streak: {stats['current_streak']}, Max Streak: {stats['max_streak']}"
            )

    return {"played_today": has_finished}


if __name__ == "__main__":
    result = check_wordle_status()
