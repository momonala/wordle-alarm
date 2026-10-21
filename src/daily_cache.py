"""Persist facts that only hold for the current day, so later runs can reuse them.

The 10:00 incognito game learns the answer whichever way it ends: a win finishes on it,
and a loss has NYT reveal it in a toast. Caching it lets the 23:30 streak-saving
auto-solve play the answer directly instead of re-deriving it — and possibly failing
again on a puzzle we already know the answer to.

Once a check sees today's puzzle finished, the later checks that day have nothing to
report, so the scheduler skips them instead of launching a browser again.

Each entry holds a single dated value and self-invalidates once the date rolls over.
"""

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
ANSWER_CACHE_PATH = PROJECT_ROOT / "cache" / "daily_answer.json"
PLAYED_CACHE_PATH = PROJECT_ROOT / "cache" / "played_today.json"


def _store(path: Path, value: str, day: date | None) -> None:
    payload = {"date": (day or date.today()).isoformat(), "value": value}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        logger.debug(f"Cached {path.name} for {payload['date']}")
    except OSError as e:
        logger.warning(f"Failed to write {path.name}: {e}")


def _load(path: Path, day: date | None) -> str | None:
    day = day or date.today()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to read {path.name}: {e}")
        return None

    if payload.get("date") != day.isoformat():
        logger.debug(f"{path.name} is for {payload.get('date')}, not {day.isoformat()}")
        return None
    return payload.get("value")


def store_answer(answer: str, day: date | None = None) -> None:
    """Record the answer for `day` (default today), replacing any earlier entry."""
    _store(ANSWER_CACHE_PATH, answer.lower(), day)


def load_answer(day: date | None = None) -> str | None:
    """Return the cached answer for `day` (default today), or None if it is missing or stale."""
    return _load(ANSWER_CACHE_PATH, day)


def mark_played(day: date | None = None) -> None:
    """Record that `day`'s (default today) puzzle is finished."""
    _store(PLAYED_CACHE_PATH, "played", day)


def is_played(day: date | None = None) -> bool:
    """Whether a check already saw `day`'s (default today) puzzle finished."""
    return _load(PLAYED_CACHE_PATH, day) is not None
