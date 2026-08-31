"""Persist the day's Wordle answer so a later run can win it outright.

The 10:00 incognito game learns the answer whichever way it ends: a win finishes on it,
and a loss has NYT reveal it in a toast. Caching it lets the 23:30 streak-saving
auto-solve play the answer directly instead of re-deriving it — and possibly failing
again on a puzzle we already know the answer to.

Only today's answer is of any use, so the cache holds a single dated entry and
self-invalidates once the date rolls over.
"""

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
ANSWER_CACHE_PATH = PROJECT_ROOT / "cache" / "daily_answer.json"


def store_answer(answer: str, day: date | None = None) -> None:
    """Record the answer for `day` (default today), replacing any earlier entry."""
    day = day or date.today()
    payload = {"date": day.isoformat(), "answer": answer.lower()}
    try:
        ANSWER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        ANSWER_CACHE_PATH.write_text(json.dumps(payload), encoding="utf-8")
        logger.debug(f"Cached answer for {payload['date']}")
    except OSError as e:
        logger.warning(f"Failed to cache answer: {e}")


def load_answer(day: date | None = None) -> str | None:
    """Return the cached answer for `day` (default today), or None if it is missing or stale."""
    day = day or date.today()
    try:
        payload = json.loads(ANSWER_CACHE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to read cached answer: {e}")
        return None

    if payload.get("date") != day.isoformat():
        logger.debug(f"Cached answer is for {payload.get('date')}, not {day.isoformat()}")
        return None
    return payload.get("answer")
