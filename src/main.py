import logging
import os
import re
import shutil
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path

import requests
import typer
from playwright._impl._errors import TimeoutError
from playwright.sync_api import sync_playwright

from src.auth import load_cookies
from src.daily_cache import load_answer
from src.daily_cache import mark_played
from src.daily_cache import store_answer
from src.env import TELEGRAM_CHAT_ID
from src.env import TELEGRAM_TOKEN
from src.page_utils import dismiss_cookie_banner
from src.solver import GameMode
from src.solver import WordleSolveError
from src.solver import solve_wordle

logger = logging.getLogger(__name__)

# Get path relative to project root (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

WORDLE_URL = "https://www.nytimes.com/games/wordle/index.html"
WAIT_FOR_LOAD_TIME_MS = 3000
WAIT_FOR_LOAD_TIME_MS_LONG = 10000
RAM_TMP_DIR = Path("/dev/shm")
PLAYWRIGHT_TMP_PATTERNS = ("playwright_chromiumdev_profile-*", "playwright-artifacts-*")


class RunMode(str, Enum):
    REAL = "real"
    TEST = "test"


def configure_logging(mode: RunMode) -> None:
    level = logging.DEBUG if mode == RunMode.TEST else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        force=True,
    )


def use_ram_for_browser_temp_files(ram_dir: Path = RAM_TMP_DIR) -> None:
    """Point Playwright's temp profile at a RAM-backed dir, clearing any left by a killed run."""
    if not ram_dir.is_dir():
        return
    for pattern in PLAYWRIGHT_TMP_PATTERNS:
        for leftover in ram_dir.glob(pattern):
            shutil.rmtree(leftover, ignore_errors=True)
    os.environ["TMPDIR"] = str(ram_dir)


@contextmanager
def playwright_context(mode: RunMode = RunMode.REAL):
    use_ram_for_browser_temp_files()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=mode != RunMode.TEST,
            args=["--disable-gpu", "--disable-extensions"],
        )
        try:
            yield browser
        finally:
            browser.close()


def send_telegram_alert(message: str):
    """Send notification message to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}

    try:
        requests.post(url, json=payload, timeout=10)
        logger.debug(f"{message}. Telegram alert sent.")
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")


def dump_page_content_to_file(page) -> None:
    """Dump page content to a specified file."""
    page_content = page.content()
    dump_path = PROJECT_ROOT / "tmp" / "wordle_page_dump.html"
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(dump_path), "w", encoding="utf-8") as file:
        file.write(page_content)
    logger.debug("Page content dumped to tmp/wordle_page_dump.html")


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


def open_stats_panel(page) -> dict[str, int]:
    """Open the latest results modal and return the parsed stats."""
    dismiss_cookie_banner(page)

    def _click_button(test_id: str, role_name: str) -> None:
        button = page.get_by_test_id(test_id)
        if not button.count():
            button = page.get_by_role("button", name=role_name)
        button.click()

    _click_button("Admire Puzzle", "Admire Puzzle")
    page.wait_for_timeout(WAIT_FOR_LOAD_TIME_MS)

    _click_button("See Results", "See Results")
    page.wait_for_timeout(WAIT_FOR_LOAD_TIME_MS)


def _format_solve_failure(label: str, error: WordleSolveError) -> str:
    """Build a Telegram message with every guess made plus the revealed answer."""
    lines = [f"❌ {label}: failed ❌"]
    lines.extend(error.state.guess_words())
    lines.append(f"answer: {error.answer.upper()}" if error.answer else "answer: unknown")
    return "\n".join(lines)


def _auto_solve_and_report(page, game_mode: GameMode, label: str) -> None:
    """Run the solver and report the outcome — win or loss — to Telegram."""
    known_answer = load_answer()
    if known_answer:
        logger.debug(f"Using answer cached earlier today: {known_answer}")
    try:
        state = solve_wordle(page, game_mode, known_answer=known_answer)
    except WordleSolveError as e:
        logger.error(f"Wordle solve failed: {e}")
        send_telegram_alert(_format_solve_failure(label, e))
        return

    send_telegram_alert(
        f"👀 Wordle auto-solved in {state.num_guesses} guesses! 👀\n" + "\n".join(state.guess_words())
    )


def _is_late_night() -> bool:
    return datetime.now().hour > 22


def check_wordle_status(mode: RunMode = RunMode.REAL) -> dict[str, bool]:
    """Check if today's Wordle has been played."""
    logger.debug(f"Starting Wordle check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    with playwright_context(mode) as browser:
        context = browser.new_context()
        # context = browser.new_context(storage_state="secrets/auth.json")
        try:
            page = context.new_page()

            # Load and set cookies before navigating
            cookies = load_cookies()
            context.add_cookies(cookies)
            logger.debug("Loaded cookies for authentication")

            page.goto(WORDLE_URL, timeout=WAIT_FOR_LOAD_TIME_MS_LONG)
            page.wait_for_timeout(10000)  # Pause to load the page

            play_button = page.get_by_test_id(GameMode.PLAY.value).count()
            continue_button = page.get_by_test_id(GameMode.CONTINUE.value).count()

            if play_button:
                logger.debug("Game is not played today")
                has_finished = False
                send_telegram_alert("🚨 Wordle not played today! 🚨")
                if _is_late_night():
                    _auto_solve_and_report(page, GameMode.PLAY, "autosolver")
            elif continue_button:
                logger.debug("Game started today")
                has_finished = False
                send_telegram_alert("🚨 Wordle not finished today! 🚨")
                if _is_late_night():
                    _auto_solve_and_report(page, GameMode.CONTINUE, "autosolver")
            else:
                logger.debug("Game is played today!")
                has_finished = True
                mark_played()
                try:
                    open_stats_panel(page)
                except TimeoutError as e:
                    logger.error(f"Failed to open stats panel: {e}")
                    send_telegram_alert("Failed to open stats panel")
                    return {"played_today": has_finished}

                stats = get_wordle_stats(page)
                logger.debug(
                    f"Games Played: {stats['played']}, Win %: {stats['win_percentage']}, "
                    f"Current Streak: {stats['current_streak']}, Max Streak: {stats['max_streak']}"
                )
        finally:
            context.close()

    return {"played_today": has_finished}


def play_wordle_incognito(mode: RunMode = RunMode.REAL) -> None:
    """Play Wordle in incognito mode (no cookies) and report pass/fail via Telegram."""
    logger.debug(f"Starting incognito Wordle play at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    with playwright_context(mode) as browser:
        context = browser.new_context()
        try:
            page = context.new_page()

            page.goto(WORDLE_URL, timeout=WAIT_FOR_LOAD_TIME_MS_LONG)
            page.wait_for_timeout(10000)

            try:
                state = solve_wordle(page, GameMode.PLAY)
                store_answer(state.guess_words()[-1])
                send_telegram_alert(
                    f"✅ autosolver [test] {state.num_guesses}/6! ✅\n" + "\n".join(state.guess_words())
                )
                logger.debug(f"Wordle Incognito solved successfully in {state.num_guesses} guesses")
            except WordleSolveError as e:
                if e.answer:
                    store_answer(e.answer)
                send_telegram_alert(_format_solve_failure("autosolver [test]", e))
                logger.error(f"Wordle solve failed: {e}")
        finally:
            context.close()


def main_cli(
    mode: RunMode = typer.Option(
        RunMode.REAL,
        "--mode",
        "-m",
        help="test: debug logging and visible browser; real: production defaults.",
        case_sensitive=False,
        show_default=True,
    ),
) -> None:
    """Check today's Wordle status."""
    configure_logging(mode)
    check_wordle_status(mode=mode)


def main() -> None:
    typer.run(main_cli)


if __name__ == "__main__":
    main()
