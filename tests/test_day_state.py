from datetime import datetime

import pytest
from playwright._impl._errors import TimeoutError

from src import main
from src.main import DayState
from src.main import check_wordle_status
from src.main import detect_day_state
from src.main import handle_day_state
from src.solver import GameMode


class FakeLocator:
    def __init__(self, count: int):
        self._count = count

    def count(self) -> int:
        return self._count


class FakePage:
    def __init__(self, play: int = 0, cont: int = 0):
        self._counts = {GameMode.PLAY.value: play, GameMode.CONTINUE.value: cont}
        self.counted: list[str] = []

    def get_by_test_id(self, test_id: str) -> FakeLocator:
        page = self

        class _RecordingLocator(FakeLocator):
            def count(self) -> int:
                page.counted.append(test_id)
                return super().count()

        return _RecordingLocator(self._counts.get(test_id, 0))

    def goto(self, url, timeout):
        pass

    def wait_for_timeout(self, ms):
        pass


class FakeContext:
    def __init__(self, page: FakePage):
        self.page = page
        self.closed = False

    def new_page(self) -> FakePage:
        return self.page

    def add_cookies(self, cookies):
        pass

    def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, context: FakeContext):
        self._context = context

    def new_context(self) -> FakeContext:
        return self._context


def _fixed_hour(hour: int) -> type[datetime]:
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 10, hour, 30)

    return FixedDatetime


@pytest.fixture
def calls(monkeypatch):
    log: list[tuple] = []
    monkeypatch.setattr(main, "send_telegram_alert", lambda msg: log.append(("alert", msg)))
    monkeypatch.setattr(
        main, "_auto_solve_and_report", lambda page, mode, label: log.append(("autosolve", mode, label))
    )
    monkeypatch.setattr(main, "mark_played", lambda: log.append(("mark_played",)))
    monkeypatch.setattr(main, "open_stats_panel", lambda page: log.append(("open_stats",)))
    monkeypatch.setattr(
        main,
        "get_wordle_stats",
        lambda page: {"played": 1, "win_percentage": 100, "current_streak": 1, "max_streak": 1},
    )
    return log


@pytest.fixture
def wordle_site(monkeypatch, calls):
    monkeypatch.setattr(main, "load_cookies", lambda: [])

    def _serve(page: FakePage) -> FakeContext:
        context = FakeContext(page)

        class _FakePlaywrightContext:
            def __init__(self, mode):
                pass

            def __enter__(self):
                return FakeBrowser(context)

            def __exit__(self, *exc):
                return False

        monkeypatch.setattr(main, "playwright_context", _FakePlaywrightContext)
        return context

    return _serve


def _stats_panel_raises(monkeypatch, error: Exception) -> None:
    def _raise(page):
        raise error

    monkeypatch.setattr(main, "open_stats_panel", _raise)


@pytest.mark.parametrize(
    ("play", "cont", "expected"),
    [
        (1, 0, DayState.NOT_STARTED),
        (1, 1, DayState.NOT_STARTED),
        (0, 1, DayState.IN_PROGRESS),
        (0, 0, DayState.DONE),
    ],
)
def test_detect_day_state_from_button_counts(play, cont, expected):
    page = FakePage(play=play, cont=cont)

    assert detect_day_state(page) is expected
    assert page.counted == [GameMode.PLAY.value, GameMode.CONTINUE.value]


@pytest.mark.parametrize(
    ("day_state", "hour", "expected"),
    [
        (DayState.NOT_STARTED, 22, [("alert", "🚨 Wordle not played today! 🚨")]),
        (
            DayState.NOT_STARTED,
            23,
            [("alert", "🚨 Wordle not played today! 🚨"), ("autosolve", GameMode.PLAY, "autosolver")],
        ),
        (
            DayState.IN_PROGRESS,
            23,
            [("alert", "🚨 Wordle not finished today! 🚨"), ("autosolve", GameMode.CONTINUE, "autosolver")],
        ),
    ],
)
def test_unfinished_day_alerts_and_autosolves_only_after_22h(monkeypatch, calls, day_state, hour, expected):
    monkeypatch.setattr(main, "datetime", _fixed_hour(hour))

    handle_day_state(FakePage(), day_state)

    assert calls == expected


def test_done_day_marks_played_and_opens_stats_even_late_at_night(monkeypatch, calls):
    monkeypatch.setattr(main, "datetime", _fixed_hour(23))

    handle_day_state(FakePage(), DayState.DONE)

    assert calls == [("mark_played",), ("open_stats",)]


def test_done_day_alerts_when_stats_panel_times_out(monkeypatch, calls):
    _stats_panel_raises(monkeypatch, TimeoutError("timed out"))

    handle_day_state(FakePage(), DayState.DONE)

    assert calls == [("mark_played",), ("alert", "Failed to open stats panel")]


@pytest.mark.parametrize(
    ("play", "cont", "played_today"),
    [(1, 0, False), (0, 1, False), (0, 0, True)],
)
def test_check_wordle_status_reports_played_today_and_closes_context(
    monkeypatch, wordle_site, play, cont, played_today
):
    monkeypatch.setattr(main, "datetime", _fixed_hour(10))
    context = wordle_site(FakePage(play=play, cont=cont))

    assert check_wordle_status() == {"played_today": played_today}
    assert context.closed


def test_check_wordle_status_closes_context_when_a_step_raises(monkeypatch, wordle_site):
    _stats_panel_raises(monkeypatch, RuntimeError("stats broke"))
    context = wordle_site(FakePage())

    with pytest.raises(RuntimeError, match="stats broke"):
        check_wordle_status()
    assert context.closed
